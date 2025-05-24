import os
import re
import html
import urllib.parse
import locale
import fcntl
import random
import requests
import logging
from flask import Flask, send_from_directory, abort, redirect, request, render_template_string, url_for, jsonify
from markupsafe import escape
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from difflib import get_close_matches
from threading import Lock
from werkzeug.middleware.proxy_fix import ProxyFix

# -------------------------------
# Configuration (identisch zu PHP)
# -------------------------------
SERVERROOT = "/var/www/html"
MUSIC_PATH = "musik"
PLAYCARD_ENDPOINT = "playcard"

# --- Configuration for the radio stream XML/HTML ---
# IMPORTANT: Replace this with the actual URL where your radio server's XML/HTML is available.
# If this is a local file, you'd change the logic in the route.
RADIO_NOW_PLAYING_URL = "https://jaquearnoux.de/now.xsl" # The URL you provided
RADIO_LOGO = "https://jaquearnoux.de/radio.png" 


# --- DEBUG/TESTING FLAGS ---
# Set to True to prioritize radio stream for shuffle, useful for testing the fallback.
# REMEMBER TO SET TO FALSE FOR NORMAL OPERATION!
TEST_RADIO_SHUFFLE_FALLBACK = False


FORBIDDEN_DIRS = [
    "Georg_Kreisler/Die_alten_boesen_Lieder",
    "Georg_Kreisler/Die_Georg_Kreisler_Platte",
    "Ernst Stankovski - ...es ist noch nicht so lange her ...",
    "wordpress",
    "phpgedview",
    "forbiddendir"
]


MEDIA_DIRS = []
for path in [
    os.path.join(SERVERROOT, "/jaquearnoux"),
    "/home/radio",
    "",
    os.environ.get("AUDIO_PATH")
]:
    if path and os.path.isdir(path):
        MEDIA_DIRS.append(os.path.abspath(path))
    else:
        # No MEDIA_DIR
        #
        print(f"WARNING: Configured media path does not exist or is not a directory: '{path}'")
        pass # Nichts tun, wenn der Pfad nicht existiert


if not MEDIA_DIRS:
    raise RuntimeError("No valid media directories found.")

ALLOWED_EXTENSIONS = {'.mp3', '.mp4', '.ogg', '.ogv', '.webm'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
MUSIC_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a'}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm'}
EXTENSIONS = ALLOWED_EXTENSIONS | IMAGE_EXTENSIONS | MUSIC_EXTENSIONS | VIDEO_EXTENSIONS


MEDIA_INDEX = []
INDEX_LOCK = Lock()

# Set locale for sorting
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'C')  # Fallback to C locale

# -------------------------------
# App Setup
# -------------------------------
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# Fix gegen localhost leak Zeile NACH der Instanziierung der Flask-App:
# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_prefix=1, x_proto=1)
# Oder einfacher (nur die Host-Header):
app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1, x_proto=1) # Minimal, aber oft ausreichend


# Configure storage backend
try:
    import pymemcache
    storage_uri = "memcached://localhost:11211"
    print("Using memcached for rate limiting")  # Debug output
except ImportError:
    storage_uri = "memory://"
    print("Memcached not available, using in-memory storage")  # Debug output

# Rate limiting with explicit storage
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri=storage_uri,
    default_limits=["100 per minute"],
    strategy="fixed-window"  # or "moving-window"
)

playcardurl = PLAYCARD_ENDPOINT


# For templates and the like, where are we at home
def set_globals(app):
    global playcardurl
    with app.app_context():
        playcardurl = url_for(PLAYCARD_ENDPOINT)

# Whatever is lying around on the hard disk, safe strings are a good idea
def safe_string(s):
    try:
        if s is None: # Added check for None
            return ''
        return s.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return '[Invalid UTF-8]'

def is_http(input_string):
    """Prüft, ob der String eine gültige HTTP- oder HTTPS-URL ist,
       unter Verwendung einer robusteren Regex.
    """
    url_pattern = re.compile(
        r'https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
        r'www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
        r'https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|'
        r'www\.[a-zA-Z0-9]+\.[^\s]{2,}'
    )
    return url_pattern.match(input_string) is not None

def is_youtube_url(url_string):
    """Prüft, ob der String eine YouTube-URL ist und extrahiert die Video-ID."""
    # Verwende Raw-Strings (r"...") um SyntaxWarning bei Backslashes zu vermeiden
    youtube_regex = re.compile(
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    match = youtube_regex.match(url_string)
    if match:
        return match.group(6) # Video ID
    return None


def run_once_global():
    """Initialisiert den Media-Index genau einmal pro Serverstart"""
    try:
        # Lockfile im temp directory des Benutzers
        lock_dir = os.path.join(os.environ.get('XDG_RUNTIME_DIR', '/tmp'), 'playcard')
        os.makedirs(lock_dir, exist_ok=True)
        lockfile = os.path.join(lock_dir, f'{PLAYCARD_ENDPOINT}.lock')
        
        with open(lockfile, 'w') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Locale für Sortierung setzen
                for loc in ['de_DE.UTF8', 'en_US.UTF-8', 'C.UTF-8', 'C']:
                    try:
                        locale.setlocale(locale.LC_ALL, loc)
                        break
                    except locale.Error:
                        continue
                
                app.logger.info("Building media index...")
                build_media_index(EXTENSIONS)
                app.logger.info(f"Media index built with {len(MEDIA_INDEX)} entries")
                
            except BlockingIOError:
                app.logger.debug("Lock already held, another process is initializing")
            except Exception as e:
                app.logger.error(f"Error during initialization: {e}")
                # Falls fehlgeschlagen, trotzdem versuchen Index zu bauen
                try:
                    build_media_index(EXTENSIONS)
                except Exception as e:
                    app.logger.critical(f"Failed to build media index: {e}")
    
    except PermissionError as e:
        app.logger.error(f"Permission denied for lockfile: {e}")
        # Ohne Lock fortfahren
        build_media_index(EXTENSIONS)
    except Exception as e:
        app.logger.error(f"Unexpected error in run_once_global: {e}")
        build_media_index(EXTENSIONS)


# Then let's get the available files
def build_media_index(extensions):
    global MEDIA_INDEX
    with INDEX_LOCK:
        MEDIA_INDEX = []

        for media_root in MEDIA_DIRS:
            media_root_norm = os.path.normpath(media_root) # Normalisiere media_root einmal
            for root, _, files in os.walk(media_root_norm): # Walk from normalized path
                for f in files:
                    full_path = os.path.normpath(os.path.join(root, f))
                    # Fügen Sie hier einen Check hinzu, ob full_path wirklich unter media_root liegt
                    # um Directory Traversal zu verhindern, falls os.walk aus irgendeinem Grund
                    # Pfade außerhalb des ursprünglichen media_root liefern sollte (unwahrscheinlich, aber sicher ist sicher)
                    if not full_path.startswith(media_root_norm):
                        app.logger.warning(f"Skipping path outside media_root: {full_path} not in {media_root_norm}")
                        continue
                    
                    if is_forbidden(full_path):
                        continue
                    base, ext = os.path.splitext(f)
                    if ext.lower() in extensions:
                        try:
                            relative_path = get_relative_path(full_path)
                            if not relative_path: # Ensure relative_path is not empty
                                app.logger.warning(f"Empty relative path for {full_path}. Skipping.")
                                continue
                            
                            safe_rel_path = relative_path
                            MEDIA_INDEX.append({
                                'path': full_path,  # Absoluter Pfad
                                'name': safe_string(f), # Voller Dateiname
                                'base': safe_string(base),
                                'ext': ext[1:].lower(),  # ohne Punkt und kleingeschrieben
                                'rel_path': safe_rel_path  # Relativer Pfad
                            })
                        except UnicodeEncodeError as e:
                            app.logger.warning(f"Skipping file with encoding issue: {full_path} - {e}")
                            continue


@app.context_processor
def inject_globals():
    return {
        'playcardurl': url_for('playcard')
    }

@app.route('/')
def root_redirect():
    # Leitet "/" auf "$MUSIK_PATH/$PLAYCARD_ENDPOINT weiter
    return redirect(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}")

# -------------------------------
# Utility Functions (identisch zu PHP)
# -------------------------------
def sort_key_locale(title):
    """Identische Sortierung wie in PHP"""
    title = title.strip()
    if not title:
        return (3, '')
    first_char = title[0]
    if re.match(r'[A-Za-z]', first_char):
        priority = 0
    elif re.match(r'\d', first_char):
        priority = 2
    else:
        priority = 1
    return (priority, locale.strxfrm(title.lower()))

def is_forbidden(path):
    """Genau wie PHP-Version mit case-insensitiver Prüfung"""
    try:
        rel_path = get_relative_path(path).replace('\\', '/').lower()
        for forbidden in FORBIDDEN_DIRS:
            forbidden_norm = forbidden.replace('\\', '/').lower()
            if forbidden_norm in rel_path:
                return True
    except Exception as e:
        app.logger.error(f"Forbidden check error: {e}")
    return False

def get_relative_path(absolute_path):
    """Wie PHP-Version mit korrekter Pfadberechnung"""
    for base in MEDIA_DIRS:
        base = safe_string(os.path.normpath(base))
        if absolute_path.startswith(base):
            return safe_string(absolute_path[len(base):].lstrip('/\\'))
    return safe_string(absolute_path)

def get_safe_relative_path(absolute_path):
    """Ermittelt den relativen Pfad und dekodiert ihn sicher als UTF-8."""
    relative_path = get_relative_path(absolute_path)
    return relative_path.encode('utf-8').decode('utf-8', 'replace') if relative_path else ''


def filter_media_dirs(dirs):
    """Filter out forbidden directories wie in PHP"""
    return [d for d in dirs if not is_forbidden(d)]

def find_file(title_path, extensions):
    """Identische Suchlogik wie in PHP"""
    # 1. Versuch: Direkter Pfad
    for media_root in MEDIA_DIRS:
        full_path = os.path.normpath(os.path.join(media_root, title_path))
        if not full_path.startswith(os.path.normpath(media_root)):
            continue
        if os.path.isfile(full_path):
            if is_forbidden(full_path):
                continue
            ext = os.path.splitext(full_path)[1].lower()
            if ext in extensions:
                try:
                    return {
                        'path': full_path,
                        'name': os.path.basename(full_path),
                        'ext': ext[1:],
                        'rel_path': get_safe_relative_path(full_path)
                         }
                except UnicodeEncodeError:
                    return None
    # 2. Versuch: Dateinamensuche
    search_name = os.path.splitext(os.path.basename(title_path))[0]
    for media_root in MEDIA_DIRS:
        for root, _, files in os.walk(media_root):
            for f in files:
                full_path = os.path.normpath(os.path.join(root, f))
                if is_forbidden(full_path):
                    continue

                base, ext = os.path.splitext(f)
                if (ext.lower() in extensions and
                        search_name.lower() in base.lower()):
                    try:
                        return {
                            'path': full_path,
                            'name': f,
                            'ext': ext[1:],
                            'rel_path': get_safe_relative_path(full_path)
                             }
                    except UnicodeEncodeError:
                        return None
    return None


def find_all_matches(search_term, extensions, limit=10):
    matches = []

    for media_root in MEDIA_DIRS:
        for root, _, files in os.walk(media_root):
            for f in files:
                full_path = os.path.normpath(os.path.join(root, f))
                if is_forbidden(full_path):
                    continue

                base, ext = os.path.splitext(f)
                if ext.lower() not in extensions:
                    continue

                # Fuzzy oder Teilstring-Suche
                if (search_term.lower() in base.lower() or
                        get_close_matches(search_term.lower(), [base.lower()], n=1, cutoff=0.7)):

                    matches.append({
                        'path': full_path,
                        'name': f,
                        'ext': ext[1:],
                        'rel_path': get_safe_relative_path(full_path)
                    })

                if len(matches) >= limit:
                    return matches
    return matches

def find_all_matches_from_index(search_term, limit=10):
    """Verbesserte Suche die genau wie die Originalversion funktioniert"""
    if not search_term:
        return []
    
    search_term_lower = search_term.lower()
    matches = []

    # Zuerst versuchen wir exakte Pfadübereinstimmung
    for entry in MEDIA_INDEX:
        if entry['rel_path'].lower() == search_term_lower:
            return [entry]  # Genau wie die Originalversion - exakter Pfad hat Priorität

    # Dann Teilstring-Suche im Dateinamen
    for entry in MEDIA_INDEX:
        if search_term_lower in entry['name'].lower():
            matches.append(entry)
            if len(matches) >= limit:
                break

    # Falls nichts gefunden, versuche fuzzy match
    if not matches:
        for entry in MEDIA_INDEX:
            if get_close_matches(search_term_lower, [entry['name'].lower()], n=1, cutoff=0.7):
                matches.append(entry)
                if len(matches) >= limit:
                    break

    return matches


def find_cover_image(track_path, track_name_base):
    """Intelligente Suche nach Cover-Bildern wie in PHP"""
    track_dir = os.path.dirname(track_path)

    # DIESE PRÜFUNG IST KRITISCH!
    if not os.path.isdir(track_dir):
        app.logger.warning(f"[find_cover_image] Directory does not exist: '{track_dir}' (derived from track_path: '{track_path}'). Returning None.")
        return None # Wichtig: Hier abbrechen, um den FileNotFoundError zu verhindern.
    
    candidates = []

    for f in os.listdir(track_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue

        img_path = os.path.join(track_dir, f)
        name = os.path.splitext(f)[0]
        score = 0

        # Normalize names for comparison wie in PHP
        norm_track = re.sub(r'[^a-z0-9]', '', track_name_base.lower())
        norm_name = re.sub(r'[^a-z0-9]', '', name.lower())

        if norm_name == norm_track:
            score = 100
        elif norm_track in norm_name:
            score = 80
        elif (re.search(r'\b(cover|folder|front|album)\b', name, re.I) and
              track_name_base.lower() in name.lower()):
            score = 70

        if score > 0:
            candidates.append({'path': img_path, 'score': score})

    if candidates:
        return sorted(candidates, key=lambda x: -x['score'])[0]['path']
    return RADIO_LOGO

# find cover in media index
import os
import threading # Angenommen, du verwendest threading.Lock für INDEX_LOCK

# Annahme: Diese sind global oder zugänglich definiert
# Stelle sicher, dass RADIO_LOGO HIER definiert ist, damit es innerhalb dieser Funktion verwendet werden kann.
RADIO_LOGO = "https://jaquearnoux.de/radio.png"
# MEDIA_INDEX = [] # Dein tatsächlicher Medien-Index
# IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'} # Deine tatsächlichen Bild-Erweiterungen
# INDEX_LOCK = threading.Lock() # Dein Lock für den Index-Zugriff


def _find_cover_by_name_in_index(track_basename, limit=1):
    """
    Sucht im MEDIA_INDEX nach dem besten passenden Cover-Bild anhand des Track-Basenamens.
    Priorisiert exakte Treffer, dann Teilstring-Treffer.
    Gibt die URL des besten Treffers oder RADIO_LOGO zurück.
    """
    if not track_basename:
        return RADIO_LOGO # Hier direkt RADIO_LOGO, wenn der Basename leer ist

    best_match_entry = None  # Speichert das gesamte 'entry' Dictionary des besten Matches
    best_score = -1

    # --- HIER beginnt die Logik, die du bereits hattest, um image_entries zu filtern ---
    with INDEX_LOCK:
        image_extensions_without_dots = {ext.lstrip('.') for ext in IMAGE_EXTENSIONS}
        image_entries = [entry for entry in MEDIA_INDEX if entry.get('ext') in image_extensions_without_dots]
    # --- Ende des bereits vorhandenen Teils ---

    # HIER kommt der Code aus der Schleife
    for entry in image_entries:
        img_basename = entry.get('base', '')
        # img_url = entry.get('path') # Wir verwenden es unten, wenn es ein best_match wird

        current_score = -1 # Initialisiere Score für jedes Bild

        # --- Strikte Übereinstimmungen zuerst ---

        # 1. Exakter Match (höchste Priorität)
        if img_basename == track_basename:
            current_score = 100

        # 2. Track-Basename beginnt mit Bild-Basename, gefolgt von Trennzeichen
        # Bsp: track="Album Name - Track", img="Album Name"
        elif track_basename.startswith(img_basename) and \
             len(track_basename) > len(img_basename) and \
             (track_basename[len(img_basename):].lstrip().startswith("-") or \
              track_basename[len(img_basename):].lstrip().startswith("_") or \
              track_basename[len(img_basename):].lstrip().startswith(" ")):
            current_score = 95

        # 3. Bild-Basename beginnt mit Track-Basename, gefolgt von Trennzeichen
        # Bsp: track="Album Name", img="Album Name - Cover"
        elif img_basename.startswith(track_basename) and \
             len(img_basename) > len(track_basename) and \
             (img_basename[len(track_basename):].lstrip().startswith("-") or \
              img_basename[len(track_basename):].lstrip().startswith("_") or \
              img_basename[len(track_basename):].lstrip().startswith(" ")):
            current_score = 90

        # --- Lockerere, aber immer noch relativ sichere Übereinstimmungen (optional, wenn die obigen nicht reichen) ---
        # (Die Kommentare lasse ich hier weg, da du sie ja schon kennst)

        # elif current_score < 90 and track_basename in img_basename:
        #     current_score = max(current_score, 70)
        # elif current_score < 70 and img_basename in track_basename:
        #     current_score = max(current_score, 60)


        # Nur aktualisieren, wenn der aktuelle Score besser ist
        if current_score > best_score:
            best_score = current_score
            best_match_entry = entry # Speichere das gesamte entry-Dictionary
            # Wenn wir ein perfektes Match haben, können wir aufhören
            if best_score == 100:
                break # Das schnellste und beste Match wurde gefunden

    # --- Die entscheidende Änderung hier ---
    if best_match_entry and best_match_entry.get('path'):
        return best_match_entry.get('path') # Gibt die URL des besten Matches zurück
    else:
        return RADIO_LOGO # Gibt RADIO_LOGO zurück, wenn kein passendes Match gefunden wurde


def generate_open_graph_tags(file_info, request):
    """Generiere OpenGraph Meta-Tags wie in PHP, nun mit Unterstützung für externe URLs und iFrames."""
    scheme = 'https' if request.headers.get('X-Forwarded-Proto') == 'https' else 'http'
    host = request.host
    base_url = f"{scheme}://{host}"
    
    # Standardwerte
    og_type = "music"
    og_audio_tags = ""
    og_video_tags = ""
    
    # Für lokale Dateien oder direkte Medien-URLs
    if not file_info.get('is_iframe'):
        stream_url = file_info['rel_path'] if file_info.get('is_external_url') else \
                     f"{base_url}/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/{urllib.parse.quote(file_info['rel_path'])}"
        audio_type = file_info['ext']

        if f".{audio_type}" in VIDEO_EXTENSIONS:
            og_type = "video.movie" # Oder "video.other"
            og_video_tags = f"""
            <meta property="og:video" content="{stream_url}" />
            <meta property="og:video:secure_url" content="{stream_url}" />
            <meta property="og:video:type" content="video/{audio_type}" />
            """
        else: # Audio
            og_type = "music.song"
            og_audio_tags = f"""
            <meta property="og:audio" content="{stream_url}" />
            <meta property="og:audio:secure_url" content="{stream_url}" />
            <meta property="og:audio:type" content="audio/{audio_type}" />
            """
    else: # Für iFrame-Inhalte (YouTube, etc.)
        og_type = "website" # Oder "video.other" wenn es primär Video ist
        # Hier könnten wir versuchen, eine Thumbnail-URL für YouTube zu generieren
        if 'youtube_video_id' in file_info:
            thumbnail_url = f"https://img.youtube.com/vi/{file_info['youtube_video_id']}/hqdefault.jpg"
            # Korrektur hier: Geschweifte Klammern für w, h müssen verdoppelt werden
            og_video_tags = f"""
            <meta property="og:image" content="{thumbnail_url}" />
            <meta property="og:video" content="{file_info['rel_path']}" />
            <meta property="og:video:secure_url" content="{file_info['rel_path']}" />
            <meta property="og:video:type" content="text/html" /> 
            <meta property="og:video:width" content="640" />
            <meta property="og:video:height" content="360" />
            """
        else:
            # Für generische iFrames, setze ein Standardbild oder lass es weg
            og_video_tags = f'<meta property="og:image" content="{RADIO_LOGO}" />'


    page_url = f"{base_url}/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}?title={urllib.parse.quote(file_info['rel_path'])}"

    return f"""
    <meta property="og:type" content="{og_type}" />
    <meta property="og:title" content="Jaque Arnoux Radio {html.escape(file_info.get('name', ''))}" />
    <meta property="og:url" content="{page_url}" />
    {og_audio_tags}
    {og_video_tags}
    """


def generate_index(structured=True):
    """Index-Generierung unter Verwendung von MEDIA_INDEX, aber mit identischem Verhalten wie die Originalversion"""
    entries = []
    folder_map = {}

    for entry in MEDIA_INDEX:
        if entry['ext'].lower() not in [ext[1:] for ext in ALLOWED_EXTENSIONS]:
            continue
        
        rel_path = entry['rel_path']
        rel_dir = os.path.dirname(rel_path)
        
        # Use 'name' directly for presentation
        name = entry['name']
        
        if structured:
            if rel_dir not in folder_map:
                folder_map[rel_dir] = []
            folder_map[rel_dir].append({
                'name': name,
                'path': rel_path,  # Hier muss der relative Pfad sein, nicht der absolute
                'ext': entry['ext'],
                'rel_path': rel_path # Füge rel_path explizit hinzu für Konsistenz
            })
        entries.append({
            'name': name,
            'path': rel_path,
            'ext': entry['ext'],
            'rel_path': rel_path # Füge rel_path explizit hinzu für Konsistenz
        })

    # Sortierung wie in PHP
    if structured:
        for folder in folder_map:
            folder_map[folder].sort(key=lambda x: sort_key_locale(x['name']))
        # Sortiere die Ordner selbst
        folder_map = dict(sorted(folder_map.items(), key=lambda x: sort_key_locale(x[0])))
    else:
        entries.sort(key=lambda x: sort_key_locale(x['name']))

    return folder_map if structured else entries

def searchform_html():
    global playcardurl
    return f"""
    <form method="POST" action="{url_for('playcard')}">
        <input type="text" name="title" placeholder="Search songs, artists or genres" required>
        <input type="hidden" name="structured" value="1">
        <button type="submit">Search</button>
    </form>
    """

def filter_folder_map(folder_map, search_value):
    filtered_map = {}

    for folder, files in folder_map.items():
        filtered_files = [
            entry for entry in files
            if search_value.lower() in entry['name'].lower()
        ]
        if filtered_files:
            filtered_map[folder] = filtered_files

    return filtered_map

# ----------------------------------
# HTML Ausgabe
# ----------------------------------


def render_index(structured, entries=None, folder_map=None, shuffle_url="#", searchform="", radio_status=None):
    """
    Rendert den Index-Bereich mit strukturierter oder flacher Ansicht
    mit korrekten Links für die Titel und sicherer Handhabung aller Eingaben
    """
    # Sicherheitsfunktion für Einträge
    def fix_entry(entry):
        if not isinstance(entry, dict):
            entry = {}
        return {
            "name": safe_string(entry.get("name", "")),
            "rel_path": safe_string(entry.get("rel_path", entry.get("path", ""))),
            "ext": safe_string(entry.get("ext", ""))
        }

    # Initialisiere Variablen für beide Fälle
    prepared_entries = []
    prepared_folder_map = {}

    # Vorbereitung der Daten
    if structured and folder_map:
        # Strukturierte Ansicht
        for folder, files in folder_map.items():
            safe_folder = safe_string(folder)
            prepared_folder_map[safe_folder] = [fix_entry(f) for f in files if f]
    elif entries:
        # Flache Ansicht
        prepared_entries = [fix_entry(e) for e in entries if e]

    # HTML-Template
    template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Playcard Audio Server</title>
        <link rel="stylesheet" href="/radio.css">
    </head>
    <body>
        <h1>Playcard Streamer</h1>
        {{ searchform|safe }}
        
        <form method="get">
            <input type="hidden" name="structured" value="{{ 0 if structured else 1 }}">
            <button type="submit">
                {% if structured %}🔤 Flat{% else %}📁 Structured{% endif %}
            </button>
        </form>

        {% if shuffle_url != "#" %}
            <p><a href="{{ shuffle_url }}">🔀 Random</a></p>
        {% endif %}

        {% if radio_status and radio_status.artist and radio_status.title %}
            <div class="radio-now-playing">
                <h3>Radio:</h3>
                <p><strong>Artist:</strong> {{ radio_status.artist }}</p>
                <p><strong>Title:</strong> {{ radio_status.title }}</p>
                {% if radio_status.stream_url %}
                    <p><a href="{{ url_for('playcard', title=radio_status.stream_url) }}">▶️  Radio Stream</a></p>
                {% endif %}
            </div>
        {% endif %}

        {% if structured %}
            {% for folder, files in folder_map.items() %}
                <div class="folder">
                    <h2>{{ folder }}</h2>
                    <ul class="song-list">
                        {% for file in files %}
                        <li class="song-item">
                            <a href="?title={{ file.rel_path|urlencode }}">{{ file.name }}</a>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            {% endfor %}
        {% else %}
            <ul class="song-list">
                {% for entry in entries %}
                <li class="song-item">
                    <a href="?title={{ entry.rel_path|urlencode }}">{{ entry.name }}</a>
                </li>
                {% endfor %}
            </ul>
        {% endif %}
    </body>
    </html>
    """

    return render_template_string(
        template,
        structured=structured,
        entries=prepared_entries if not structured else None,
        folder_map=prepared_folder_map if structured else None,
        shuffle_url=shuffle_url,
        searchform=searchform,
        radio_status=radio_status # Pass radio status to template
    )


def render_player(file_info, request, cover_html=""):
    """
    Rendert den Player-Bereich mit allen notwendigen Komponenten.
    Args:
        file_info: Dictionary mit Dateiinformationen. Kann auch 'is_external_url', 'is_youtube',
                   'is_iframe', 'youtube_video_id' enthalten.
        request: Flask request Objekt für OpenGraph Tags
        cover_html: Optionaler HTML-Code für das Cover-Bild
    Returns:
        Gerendertes HTML als String
    """
    player_html = ""
    # Hier wird unterschieden, welcher Player gerendert wird
    if file_info.get('is_youtube') and file_info.get('youtube_video_id'):
        embed_url = f"https://www.youtube.com/embed/{file_info['youtube_video_id']}?autoplay=1"
        player_html = f"""
        <iframe width="640" height="360" src="{embed_url}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
        """
        # Für YouTube gibt es kein lokales Cover, evtl. YouTube Thumbnail hier setzen
        if not cover_html:
            cover_html = f'<img src="https://img.youtube.com/vi/{file_info["youtube_video_id"]}/hqdefault.jpg" width="300" alt="YouTube Thumbnail"><br>'
    elif file_info.get('is_iframe'):
        # Generischer iFrame für andere einbettbare URLs (z.B. andere Playcards)
        embed_url = file_info['rel_path'] # rel_path ist hier die URL für den iFrame
        player_html = f"""
        <iframe width="640" height="360" src="{embed_url}" frameborder="0" allowfullscreen></iframe>
        """
        # Für iFrames ohne spezifisches Cover ein Standardbild oder nichts
        if not cover_html:
             cover_html = f'<img src="{RADIO_LOGO}" width="300" alt="Standard Cover"><br>'
    else:
        # Direkte Medien-Datei (lokal oder extern)
        player_url = file_info['rel_path'] if file_info.get('is_external_url') else \
                     url_for('serve_file', filename=file_info['rel_path'])
        
        media_type = file_info['ext'].lower()
        
        if f".{media_type}" in VIDEO_EXTENSIONS:
            player_html = f"""
            <video controls autoplay width="640">
                <source src="{player_url}" type="video/{media_type}">
                Your browser doesn't support HTML5 video.
            </video>
            """
        else:
            player_html = f"""
            <audio controls autoplay>
                <source src="{player_url}" type="audio/{media_type}">
                Your browser doesn't support HTML5 audio.
            </audio>
            """

    return render_template_string("""
        <!DOCTYPE html>
        <html prefix="og: http://ogp.me/ns#">
        <head>
            <meta charset="utf-8">
            <title>{{ title|e }}</title>
            {{ og_tags|safe }}
            {# Standard OG-Image, kann von generate_open_graph_tags überschrieben werden #}
            <meta property="og:image" content="{{RADIO_LOGO}}" />
            <link rel="stylesheet" href="/radio.css">
        </head>
        <body>
            <div class="player-container">
                <h1>{{ title|e }}</h1>
                {{ player_html|safe }}
                <p><a href="{{ url_for('playcard') }}">Back to index</a></p>
                {{ searchform|safe }}
                {{ cover_html|safe }}
            </div>
            <script src="/radio.js" async></script>
        </body>
        </html>
    """,
    title=file_info.get('name', ''),
    og_tags=generate_open_graph_tags(file_info, request),
    cover_html=cover_html,
    player_html=player_html,
    searchform=searchform_html())

# -------------------------------
# Helper function to get radio streams (extracted from get_radio_status_json)
# -------------------------------
def _get_radio_streams_from_xml():
    """
    Fetches the radio's "now playing" XML/HTML, parses it,
    and returns a list of dictionaries with stream data, or an empty list on error.
    Dependencies (requests, beautifulsoup4, lxml) are imported lazily.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        app.logger.error(f"Missing required libraries for radio status parsing: {e}. Please install them (e.g., pip install requests beautifulsoup4 lxml).")
        return []

    try:
        response = requests.get(RADIO_NOW_PLAYING_URL, timeout=3) # Shorter timeout for shuffle
        response.raise_for_status()
        xml_content = response.text
        soup = BeautifulSoup(xml_content, 'lxml-xml')
        
        streams_data = []
        for server in soup.find_all('SHOUTCASTSERVER'):
            mount = server.find('MOUNT').text if server.find('MOUNT') else None
            server_title = server.find('SERVERTITLE').text if server.find('SERVERTITLE') else "Unknown Radio"
            artist = server.find('ARTIST').text if server.find('ARTIST') else ""
            title = server.find('TITLE').text if server.find('TITLE') else ""

            if mount: # Only add if a mount point exists
                streams_data.append({
                    "mount_point": mount,
                    "server_title": server_title,
                    "artist": artist,
                    "title": title
                })
        app.logger.debug(f"Successfully parsed {len(streams_data)} radio streams from {RADIO_NOW_PLAYING_URL}.")
        return streams_data
    except requests.exceptions.RequestException as e:
        app.logger.warning(f"Could not fetch radio status for shuffle fallback from {RADIO_NOW_PLAYING_URL}: {e}")
        return []
    except Exception as e:
        app.logger.error(f"Error parsing radio status for shuffle fallback: {e}")
        return []

def get_current_radio_status():
    """
    Retrieves the current playing artist and title from the radio stream.
    Returns a dict with 'artist', 'title', 'stream_url' or None if not available.
    """
    streams = _get_radio_streams_from_xml()
    if streams:
        # Assuming the first stream is the primary one
        first_stream = streams[0]
        return {
            "artist": safe_string(first_stream.get('artist', 'Unknown')),
            "title": safe_string(first_stream.get('title', 'Unknown')),
            "stream_url": safe_string(first_stream.get('mount_point'))
        }
    return None


# -------------------------------
# Routes (identisch zu PHP)
# -------------------------------
@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/<path:filename>")
def serve_file(filename):
    """Identische Dateiauslieferung wie in PHP"""
    try:
        filename = os.path.normpath(filename)
        for media_root in MEDIA_DIRS:
            full_path = os.path.normpath(os.path.join(media_root, filename))
            # Critical: Ensure the path is within the media_root to prevent directory traversal
            if not full_path.startswith(os.path.normpath(media_root)):
                app.logger.warning(f"Attempted directory traversal: {full_path} outside {media_root}")
                abort(403, "Forbidden")
            
            if not os.path.isfile(full_path):
                continue
            if is_forbidden(full_path):
                abort(403, "Forbidden")
            return send_from_directory(media_root, filename)
    except Exception as e:
        app.logger.error(f"File serve error: {e}")
    abort(404)

@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}", methods=['GET', 'POST'])
@limiter.limit("100 per minute")
def playcard():
    # Formularverarbeitung
    search_value = ""
    if request.method == "POST":
        search_value = request.form.get("title", "").strip()
        if search_value:
            return redirect(url_for('playcard', title=search_value))
    elif request.method == "GET":
        search_value = request.args.get("title", "").strip()
    
    structured = request.args.get('structured', '1') == '1'

    file_info = None
    cover_html = ""

    if search_value:
        # 1. Ist es eine YouTube-URL?
        youtube_video_id = is_youtube_url(search_value)
        if youtube_video_id:
            app.logger.info(f"YouTube URL detected: {search_value}, ID: {youtube_video_id}")
            file_info = {
                'name': f"YouTube Video: {youtube_video_id}", # Kann später durch echten Titel ersetzt werden
                'ext': 'youtube', # Spezieller "Typ" für YouTube
                'rel_path': search_value,
                'is_external_url': True,
                'is_youtube': True,
                'is_iframe': True, # Auch ein iFrame
                'youtube_video_id': youtube_video_id,
                'path': None
            }
            return render_player(file_info, request, cover_html)
        
        # 2. Ist es eine generische HTTP/HTTPS URL, die nicht YouTube ist?
        #    Hier unterscheiden wir: Ist es eine direkte Mediendatei oder eine einzubettende Seite?
        elif is_http(search_value):
            app.logger.info(f"External URL detected: {search_value}")
            parsed_url = urllib.parse.urlparse(search_value)
            
            path_basename = os.path.basename(parsed_url.path)
            title_from_url = urllib.parse.unquote(os.path.splitext(path_basename)[0])
            ext_from_url = os.path.splitext(path_basename)[1].lstrip('.').lower()

            if not title_from_url:
                segments = parsed_url.path.split('/')
                title_from_url = urllib.parse.unquote(segments[-1]) if segments[-1] else search_value
            
            # Prüfen, ob die URL direkt auf eine Mediendatei zeigt
            is_direct_media_url = False
            if f".{ext_from_url}" in MUSIC_EXTENSIONS or f".{ext_from_url}" in VIDEO_EXTENSIONS:
                is_direct_media_url = True
            
            if is_direct_media_url:
                app.logger.info(f"Direct media URL: {search_value}")
                file_info = {
                    'name': safe_string(title_from_url),
                    'ext': safe_string(ext_from_url),
                    'rel_path': safe_string(search_value), # rel_path ist hier die externe URL
                    'is_external_url': True,
                    'is_iframe': False, # Keine iFrame-Einbettung
                    'path': None
                }
                # Für externe URLs gibt es kein lokales Cover-Bild. Hier könnte ein Standardbild geladen werden.
                cover_html = f'<img src="{RADIO_LOGO}" width="300" alt="Standard Cover"><br>' # Beispiel: Standard-Cover
                return render_player(file_info, request, cover_html)
            else:
                # Es ist eine HTTP/HTTPS URL, aber keine direkte Mediendatei und kein YouTube -> behandle als iFrame
                app.logger.info(f"Generic iframe URL: {search_value}")
                file_info = {
                    'name': safe_string(search_value),
                    'ext': 'html',
                    'rel_path': safe_string(search_value),
                    'is_external_url': True,
                    'is_iframe': True, # Wird als iFrame eingebettet
                    'path': None
                }
                cover_html = f'<img src="{RADIO_LOGO}" width="300" alt="Standard Cover"><br>'
                return render_player(file_info, request, cover_html)
        else:
            # Es ist keine externe URL, also suche lokal
            matches = find_all_matches_from_index(search_value)
            
            if len(matches) == 1:
                file_info = matches[0]
                file_info['is_external_url'] = False # Explizit auf False setzen
                file_info['is_iframe'] = False
                file_info['is_youtube'] = False

                # Cover-Bild suchen (nur für lokale Dateien relevant)
                cover_path = find_cover_image(file_info['path'], os.path.splitext(file_info['name'])[0])
                if cover_path:
                    for media_root in MEDIA_DIRS:
                        if cover_path.startswith(media_root):
                            rel_cover = get_safe_relative_path(cover_path)
                            cover_url = url_for('serve_file', filename=rel_cover)
                            cover_html = f'<img src="{cover_url}" width="300" alt="Cover"><br>'
                            break
                return render_player(file_info, request, cover_html)
            elif len(matches) > 1:
                # Mehrere Treffer, zeige Index mit Suchergebnissen
                if structured:
                    folder_map = generate_index(structured=True)
                    folder_map = filter_folder_map(folder_map, search_value)
                    entries_for_index = []
                    for folder_content in folder_map.values():
                        entries_for_index.extend(folder_content)
                else:
                    entries_for_index = generate_index(structured=False)
                    entries_for_index = [e for e in entries_for_index if search_value.lower() in e['name'].lower()]
                
                # Shuffle URL für Suchergebnisse macht weniger Sinn, daher #
                shuffle_url_for_search = "#"
                radio_status_for_search = get_current_radio_status() # Radio-Status anzeigen, auch bei Suche
                return render_index(
                    structured=structured,
                    entries=entries_for_index if not structured else None,
                    folder_map=folder_map if structured else None,
                    shuffle_url=shuffle_url_for_search,
                    searchform=searchform_html(),
                    radio_status=radio_status_for_search
                )
            else:
                # Keine Treffer für lokale Suche, dann den Standard-Index anzeigen
                app.logger.info(f"No local matches found for '{search_value}'. Displaying full index.")

    # --- Start der Logik für Index-Anzeige und Shuffle-URL ---
    shuffle_track_title = None
    
    # Radio-Status für die Anzeige im Index abrufen
    current_radio_status = get_current_radio_status()

    # Logik für den Shuffle-Link, basierend auf TEST_RADIO_SHUFFLE_FALLBACK
    if TEST_RADIO_SHUFFLE_FALLBACK:
        app.logger.info("TEST_RADIO_SHUFFLE_FALLBACK is TRUE: Prioritizing radio stream for shuffle.")
        if current_radio_status and current_radio_status.get('stream_url'):
            shuffle_track_title = current_radio_status['stream_url']
            app.logger.info(f"Using radio stream '{shuffle_track_title}' as shuffle target (TEST MODE).")
        else:
            app.logger.warning("TEST MODE: No radio stream found for shuffle, falling back to local tracks.")
            music_entries = [entry for entry in MEDIA_INDEX if entry.get('ext') in [ext.lstrip('.') for ext in ALLOWED_EXTENSIONS]]
            if music_entries:
                random_local_track = random.choice(music_entries)
                shuffle_track_title = random_local_track['rel_path']
                app.logger.info(f"Using random local track '{shuffle_track_title}' as shuffle target (TEST MODE, radio failed).")
            else:
                app.logger.warning("TEST MODE: No local music tracks available either. Shuffle link will be inactive.")
    else:
        app.logger.info("TEST_RADIO_SHUFFLE_FALLBACK is FALSE: Prioritizing local tracks for shuffle.")
        music_entries = [entry for entry in MEDIA_INDEX if entry.get('ext') in [ext.lstrip('.') for ext in ALLOWED_EXTENSIONS]]
        if music_entries:
            random_local_track = random.choice(music_entries)
            shuffle_track_title = random_local_track['rel_path']
            app.logger.info(f"Using random local track '{shuffle_track_title}' as shuffle target.")
        else:
            # Wenn keine lokalen Tracks, versuchen, einen Radio-Stream zu bekommen
            app.logger.info("No local music tracks found. Attempting to get radio stream for shuffle fallback.")
            if current_radio_status and current_radio_status.get('stream_url'):
                shuffle_track_title = current_radio_status['stream_url']
                app.logger.info(f"Using radio stream '{shuffle_track_title}' as shuffle fallback.")
            else:
                app.logger.warning("No radio streams found for shuffle fallback.")

    # Generiere den Shuffle-Link, falls ein Titel gefunden wurde
    shuffle_url = "#"
    if shuffle_track_title:
        shuffle_url = url_for('playcard', title=shuffle_track_title)


    if structured:
        folder_map = generate_index(structured=True)
        entries = None # Sicherstellen, dass entries nicht fälschlicherweise gerendert wird
    else:
        entries = generate_index(structured=False)
        folder_map = None # Sicherstellen, dass folder_map nicht fälschlicherweise gerendert wird

    return render_index(
        structured=structured,
        entries=entries,
        folder_map=folder_map,
        shuffle_url=shuffle_url,
        searchform=searchform_html(),
        radio_status=current_radio_status # Aktuellen Radio-Status an das Template übergeben
    )


# -------------------------------
# API for Android
# -------------------------------
@app.route('/api')
def api_redirect():
    """Leitet '/' auf '$MUSIC_PATH/$PLAYCARD_ENDPOINT/api' weiter."""
    return redirect(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api")

# -------------------------------
# API Utilities
# -------------------------------


def _format_song_for_json(file_info):
    """
    Formatiert die Details eines Songs für die JSON-API-Antwort,
    inklusive der Erzeugung externer URLs und der Suche nach Cover-Bildern.
    """
    if not file_info:
        return None

    # Überprüfen, ob 'rel_path' vorhanden ist. Wenn nicht, versuchen wir 'path' zu verwenden.
    rel_path_to_use = file_info.get('rel_path')
    if not rel_path_to_use:
        rel_path_to_use = file_info.get('path') 
        if not rel_path_to_use:
            app.logger.warning(f"[_format_song_for_json] Missing 'rel_path' and 'path' in file_info: {file_info}")
            return None

    stream_url = url_for('serve_file', filename=rel_path_to_use, _external=True)

    cover_url = None
    
    # Use original 'name' for cover search as it's the actual filename
    track_name_base = os.path.splitext(file_info.get('name', '') or '')[0] 

    best_cover_entry = _find_cover_by_name_in_index(track_name_base) 

    if best_cover_entry:
        cover_url = url_for('serve_file', filename=best_cover_entry.get('rel_path'), _external=True)
    else:
        cover_url = RADIO_LOGO # url_for('static', filename='radio.png', _external=True)

    return {
        "name": file_info.get('name', ''), # Originalname für interne API-Nutzung
        "relative_path": rel_path_to_use, 
        "extension": file_info.get('ext', ''),
        "stream_url": stream_url,
        "cover_image_url": cover_url
    }


@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api")
def api_root():
     """Gibt eine Übersicht über die verfügbaren API-Endpunkte zurück."""
     api_endpoints = {
         "index_flat": {
             "description": "Get a flat list of all media entries.",
             "url": url_for('get_index_json', structured=0, _external=True),
             "parameters": {"structured": "0", "search": "Optional search term"}
         },
         "index_structured": {
             "description": "Get a structured (folder-based) list of all media entries.",
             "url": url_for('get_index_json', structured=1, _external=True),
             "parameters": {"structured": "1", "search": "Optional search term"}
         },
         "random_track": {
             "description": "Get details for a random media track.",
             "url": url_for('get_random_track_json', _external=True),
             "parameters": {}
         },
         "track_info": {
             "description": "Get detailed information for a specific track by its relative path.",
             "url": url_for('get_track_info_json', title="<relative_path_to_track>", _external=True),
             "parameters": {"title": "Relative path of the track"}
         },
         "radio_status": {
             "description": "Get current status (listeners, now playing) of the radio stream.",
             "url": url_for('get_radio_status_json', _external=True),
             "parameters": {}
         }
     }
     return jsonify({
         "status": "success",
         "message": "Welcome to the Playcard  API! Below are the available endpoints.",
         "available_endpoints": api_endpoints
     })

@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api/index")
@limiter.limit("100 per minute")
def get_index_json():
    """Gibt den Medienindex als JSON zurück."""
    structured = request.args.get('structured', '1') == '1'
    search_value = request.args.get("search", "").strip()

    all_songs_to_return = [] 


    if structured:
        raw_data = generate_index(structured=True)
        if search_value:
            raw_data = filter_folder_map(raw_data, search_value)

        formatted_structured_data = []
        for folder_name, files in raw_data.items():
            formatted_files_in_folder = []
            for file_info in files:
                formatted_song = _format_song_for_json(file_info)
                if formatted_song:
                    formatted_files_in_folder.append(formatted_song)
                    all_songs_to_return.append(formatted_song) 
            formatted_structured_data.append({"folder_name": folder_name, "files": formatted_files_in_folder})

        return jsonify({
            "type": "structured",
            "data": formatted_structured_data
        })


    else: # Dies ist der "flache" View, der die Flutter-App bevorzugen sollte
        raw_entries = generate_index(structured=False) 
        if search_value:
            raw_entries = [
                e for e in raw_entries 
                if search_value.lower() in e['name'].lower() 
            ]
        
        for entry in raw_entries:
            formatted_song = _format_song_for_json(entry)
            if formatted_song:
                all_songs_to_return.append(formatted_song)

        return jsonify(all_songs_to_return)


@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api/track_info")
@limiter.limit("100 per minute")
def get_track_info_json():
    """Gibt detaillierte Informationen zu einem bestimmten Titel anhand seines relativen Pfads zurück."""
    rel_path = request.args.get('title')
    if not rel_path:
        abort(400, description="Relative path (title) parameter is required.")

    with INDEX_LOCK:
        track_info = next((entry for entry in MEDIA_INDEX if entry.get('rel_path') == rel_path), None)

    if not track_info:
        abort(404, description="Track not found.")

    formatted_track = _format_song_for_json(track_info)
    
    if not formatted_track:
        abort(500, description="Failed to format track information.")

    return jsonify(formatted_track)


@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api/random_track")
@limiter.limit("10 per minute")
def get_random_track_json():
    """Gibt Details zu einem zufälligen Medientitel zurück."""
    # Nur Musikdateien filtern
    music_entries = [entry for entry in MEDIA_INDEX if entry.get('ext') in [ext.lstrip('.') for ext in ALLOWED_EXTENSIONS]]
    
    if not music_entries:
        abort(404, description="No music tracks found to select a random one.")
    
    random_track = random.choice(music_entries)
    
    formatted_track = _format_song_for_json(random_track)
    
    if not formatted_track:
        abort(500, description="Failed to format random track information.")

    return jsonify({
        "status": "success",
        **formatted_track 
    })

# -------------------------------
# New JSON-API Endpoint for Radio Status (mit optionalen Imports)
# -------------------------------

@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api/radio", methods=['GET'])
@limiter.limit("20 per minute")
def get_radio_status_json():
    """
    Fetches the radio's "now playing" XML/HTML, parses it,
    and returns structured information about each stream as JSON.
    Dependencies (requests, beautifulsoup4, lxml) are imported lazily.
    """
    streams_data = _get_radio_streams_from_xml() # Reuse the helper function

    if not streams_data:
        return jsonify({
            "status": "error",
            "message": "Could not fetch or parse radio status information."
        }), 500

    return jsonify({
        "status": "success",
        "radio_streams": streams_data
    })

# -------------------------------
# Run Application
# -------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Sicherstellen, dass der Index nur einmal gebaut wird
    run_once_global()

    # Lokaler Entwicklungsmodus
    app.run(host="127.0.0.1", port=8010, threaded=True) # debug=True hier für detaillierte Fehler

else:
    # Für WSGI-Server (z.B. uWSGI)
    run_once_global()
    application = app # Dies ist das Entry Point für WSGI-Server
