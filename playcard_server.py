import os
import re
import html
import urllib.parse
import locale
import fcntl
import random
import requests # For fetching the external XML/HTML content
import logging
from flask import Flask, send_from_directory, abort, redirect, request, render_template_string, url_for, jsonify
from markupsafe import escape
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from difflib import get_close_matches
from threading import Lock
from werkzeug.middleware.proxy_fix import ProxyFix
# -------------------------------
# Configuration 
# -------------------------------
SERVERROOT = "/var/www/html"
MUSIC_PATH = "musik"
PLAYCARD_ENDPOINT = "playcard"

# --- Configuration for the radio stream XML/HTML ---
# IMPORTANT: Replace this with the actual URL where your radio server's XML/HTML is available.
# If this is a local file, you'd change the logic in the route.
RADIO_NOW_PLAYING_URL = "https://jaquearnoux.de/now.xsl" # The URL you provided


FORBIDDEN_DIRS = [
    "Georg_Kreisler/Die_alten_boesen_Lieder",
    "Georg_Kreisler/Die_Georg_Kreisler_Platte", 
    "Ernst Stankovski - ...es ist noch nicht so lange her ...",
    "wordpress",
    "phpgedview",
    "schillerli"
]


MEDIA_DIRS = []
for path in [
    os.path.join(SERVERROOT, ""),
    "/home/cdrip",
    os.environ.get("AUDIO_PATH")
]:
    if path and os.path.isdir(path):
        MEDIA_DIRS.append(os.path.abspath(path))


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
        return s.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return '[Invalid UTF-8]'

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
            for root, _, files in os.walk(media_root):
                for f in files:
                    full_path = os.path.normpath(os.path.join(root, f))
                    if is_forbidden(full_path):
                        continue
                    base, ext = os.path.splitext(f)
                    if ext.lower() in extensions:
                        try:
                            relative_path = get_relative_path(full_path)
                            safe_rel_path = relative_path
                            MEDIA_INDEX.append({
                                'path': full_path,  # Absoluter Pfad
                                'name': safe_string(f),
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
    # 2. Versuch: Dateinamenssuche
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
    return None

# find cover in media index
def _find_cover_by_name_in_index(track_basename, limit=1):
    """
    Sucht im MEDIA_INDEX nach dem besten passenden Cover-Bild anhand des Track-Basenamens.
    Priorisiert exakte Treffer, dann Teilstring-Treffer.
    Gibt den besten Eintrag zurück oder None.
    """
    if not track_basename:
        return None

    # Wir verwenden den originalen track_basename für die Suche,
    # da wir die Groß-/Kleinschreibung berücksichtigen wollen (oder zumindest strenger sein wollen).
    # track_basename_lower bestehen
    # und nutze es für die Vergleiche. Im Moment lassen wir es weg, um strenger zu sein.
    
    best_match = None
    best_score = -1

    with INDEX_LOCK:
        image_extensions_without_dots = {ext.lstrip('.') for ext in IMAGE_EXTENSIONS}
        image_entries = [entry for entry in MEDIA_INDEX if entry.get('ext') in image_extensions_without_dots]

        for entry in image_entries:
            img_basename = entry.get('base', '') # Holen wir den originalen base-Wert des Bildes
            current_score = 0

            # Priorität 1: Exakter Match des Basenamens (case-sensitive)
            # Wenn der Dateiname des Tracks und des Covers exakt übereinstimmen
            if img_basename == track_basename: # KEIN .lower() hier für case-sensitive
                current_score = 100
            
            # Priorität 2: Der Bild-Basename ist ein TEILSTRING des Track-Basenamens (case-sensitive)
            # Beispiel: "Lets Be Closer" (Bild) ist Teil von "Lets Be Closer (Feat. Artist)" (Track)
            elif img_basename and img_basename in track_basename: # KEIN .lower() hier
                # Optional: Wenn img_basename am ANFANG des track_basename steht, höherer Score
                if track_basename.startswith(img_basename):
                    current_score = 98
                else:
                    current_score = 95
            
            # Priorität 3: Der Track-Basename ist ein TEILSTRING des Bild-Basenamens (case-sensitive)
            # Beispiel: "Song" (Track) ist Teil von "Song - Album Cover" (Bild)
            elif track_basename in img_basename: # KEIN .lower() hier
                current_score = 90

            # Alle weiteren Fuzzy- oder generischen Keyword-Suchen werden hier ÜBERSPRUNGEN.
            # Dadurch wird die Suche deutlich weniger tolerant.

            if current_score > best_score:
                best_score = current_score
                best_match = entry
    
    # Optional: Wenn du einen Mindest-Score behalten willst, um auch bei 90 oder 95 zu filtern,
    # müsstest du eine Variable einführen, z.B. MIN_ACCEPTABLE_COVER_SCORE = 90.
    # Ansonsten wird jeder gefundene Teil-Match zurückgegeben.
    
    # Wenn kein Match mit Score > 0 gefunden wurde, oder du einen festen Mindest-Score willst:
    # return best_match if best_score > 89 else None # Beispiel: nur Matches mit 90 oder mehr akzeptieren
    # Da du keine neuen Variablen willst, geben wir einfach den besten gefundenen Match zurück.
    return best_match





def generate_open_graph_tags(file_info, request):
    """Generiere OpenGraph Meta-Tags wie in PHP"""
    scheme = 'https' if request.headers.get('X-Forwarded-Proto') == 'https' else 'http'
    host = request.host
    base_url = f"{scheme}://{host}"
    stream_url = f"{base_url}/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/{urllib.parse.quote(file_info['rel_path'])}"
    page_url = f"{base_url}/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}?title={urllib.parse.quote(file_info['rel_path'])}"

    return f"""
    <meta property="og:type" content="music" />
    <meta property="og:title" content="Jaque Arnoux Radio {html.escape(file_info['name'])}" />
    <meta property="og:url" content="{page_url}" />
    <meta property="og:audio" content="{stream_url}" />
    <meta property="og:audio:secure_url" content="{stream_url}" />
    <meta property="og:audio:type" content="audio/{file_info['ext']}" />
    <meta property="og:video" content="{stream_url}">
    <meta property="og:video:secure_url" content="{stream_url}">
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
        name = entry['name']
        
        if structured:
            if rel_dir not in folder_map:
                folder_map[rel_dir] = []
            folder_map[rel_dir].append({
                'name': name,
                'path': rel_path,  # Hier muss der relative Pfad sein, nicht der absolute
                'ext': entry['ext']
            })
        entries.append({
            'name': name,
            'path': rel_path,
            'ext': entry['ext']
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



def render_index(structured, entries=None, folder_map=None, shuffle_url="#", searchform=""):
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
        <h1>Playcard Music Streamer</h1>
        {{ searchform|safe }}
        
        <form method="get">
            <input type="hidden" name="structured" value="{{ 0 if structured else 1 }}">
            <button type="submit">
                {% if structured %}🔤 Flache Ansicht{% else %}📁 Strukturierte Ansicht{% endif %}
            </button>
        </form>

        {% if shuffle_url != "#" %}
            <p><a href="{{ shuffle_url }}">🔀 Zufälliger Titel</a></p>
        {% endif %}

        {% if structured %}
            {% for folder, files in folder_map.items() %}
                <div class="folder">
                    <h2>{{ folder or 'Root' }}</h2>
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
        searchform=searchform
    )







def render_player(file_info, request, cover_html=""):
    """
    Rendert den Player-Bereich mit allen notwendigen Komponenten
    Args:
        file_info: Dictionary mit Dateiinformationen (path, name, ext, rel_path)
        request: Flask request Objekt für OpenGraph Tags
        cover_html: Optionaler HTML-Code für das Cover-Bild
    Returns:
        Gerendertes HTML als String
    """
    # Player HTML generieren
    player_url = url_for('serve_file', filename=file_info['rel_path'])
    if file_info['ext'] in ['mp4', 'webm', 'ogv']:
        player_html = f"""
        <video controls autoplay width="640">
            <source src="{player_url}" type="video/{file_info['ext']}">
            Your browser doesn't support HTML5 video.
        </video>
        """
    else:
        player_html = f"""
        <audio controls autoplay>
            <source src="{player_url}" type="audio/{file_info['ext']}">
            Your browser doesn't support HTML5 audio.
        </audio>
        """

    return render_template_string("""
        <!DOCTYPE html>
        <html prefix="og: http://ogp.me/ns#">
        <head>
            <meta charset="utf-8">
            <title>{{ title }}</title>
            {{ og_tags|safe }}
            <meta property="og:image" content="https://jaquearnoux.de/radio.png" />
            <link rel="stylesheet" href="/radio.css">
        </head>
        <body>
            <div class="player-container">
                <h1>{{ title }}</h1>
                {{ cover_html|safe }}
                {{ player_html|safe }}
                <p><a href="{{ url_for('playcard') }}">Back to index</a></p>
                {{ searchform|safe }}
            </div>
            <script src="/radio.js" async></script>
        </body>
        </html>
    """,
    title=html.escape(file_info['name']),
    og_tags=generate_open_graph_tags(file_info, request),
    cover_html=cover_html,
    player_html=player_html,
    searchform=searchform_html())


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
            if not full_path.startswith(media_root):
                continue
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

    # Suchlogik
    if search_value:
        matches = find_all_matches_from_index(search_value)
        
        # Genau wie im Original: Bei genau einem Treffer direkt anzeigen
        if len(matches) == 1:
            file_info = matches[0]
            
            # Cover-Bild suchen
            cover_html = ""
            cover_path = find_cover_image(file_info['path'], os.path.splitext(file_info['name'])[0])
            if cover_path:
                for media_root in MEDIA_DIRS:
                    if cover_path.startswith(media_root):
                        rel_cover = get_safe_relative_path(cover_path)
                        cover_url = url_for('serve_file', filename=rel_cover)
                        cover_html = f'<img src="{cover_url}" width="300" alt="Cover"><br>'
                        break
            
            return render_player(file_info, request, cover_html)

    # Index-Anzeige (keine Suche oder mehrere Treffer)
    if structured:
        folder_map = generate_index(structured=True)
        if search_value:  # Falls Suche aktiv, Ergebnisse filtern
            folder_map = filter_folder_map(folder_map, search_value)
        shuffle_track = next(iter(folder_map.values()))[0] if folder_map else None
    else:
        entries = generate_index(structured=False)
        if search_value:  # Falls Suche aktiv, Ergebnisse filtern
            entries = [e for e in entries if search_value.lower() in e['name'].lower()]
        shuffle_track = entries[0] if entries else None

    # Sicherstellen, dass shuffle_track das richtige Format hat
    shuffle_url = url_for('playcard', title=shuffle_track['rel_path']) if shuffle_track and 'rel_path' in shuffle_track else "#"

    return render_index(
        structured=structured,
        entries=entries if not structured else None,
        folder_map=folder_map if structured else None,
        shuffle_url=shuffle_url,
        searchform=searchform_html()
    )

# -------------------------------
# API for Android
# -------------------------------
							
@app.route('/api')
def api_redirect():
    """Leitet '/' auf '$MUSIC_PATH/$PLAYCARD_ENDPOINT' weiter."""
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
    # Dies behebt das Problem, dass die aufrufende Funktion 'path' anstelle von 'rel_path' liefert.
    rel_path_to_use = file_info.get('rel_path')
    if not rel_path_to_use:
        rel_path_to_use = file_info.get('path') # Nutze 'path', falls 'rel_path' fehlt
        if not rel_path_to_use:
            app.logger.warning(f"[_format_song_for_json] Missing 'rel_path' and 'path' in file_info: {file_info}")
            return None
        # app.logger.debug(f"[_format_song_for_json] Using 'path' as 'rel_path': {rel_path_to_use}") # Debug-Ausgabe, falls nötig

    stream_url = url_for('serve_file', filename=rel_path_to_use, _external=True)

    cover_url = None
    
    # track_name_base wird weiterhin aus 'name' abgeleitet
    track_name_base = os.path.splitext(file_info.get('name', '') or '')[0]
    # app.logger.debug(f"Formatting song: '{file_info.get('name')}', searching cover for base name: '{track_name_base}'")

    best_cover_entry = _find_cover_by_name_in_index(track_name_base) # Diese Funktion ist in Ordnung

    if best_cover_entry:
        # app.logger.debug(f"Cover found: '{best_cover_entry.get('rel_path')}' for track '{track_name_base}'")
        # best_cover_entry['rel_path'] sollte hier immer vorhanden sein, da es aus dem MEDIA_INDEX kommt.
        cover_url = url_for('serve_file', filename=best_cover_entry.get('rel_path'), _external=True)
    else:
        # app.logger.debug(f"No specific cover found for track '{track_name_base}', using fallback image.")
        cover_url = url_for('static', filename='radio.png', _external=True)

    return {
        "name": file_info.get('name', ''),
        "relative_path": rel_path_to_use, # Jetzt korrekt auf den tatsächlich verwendeten relativen Pfad gesetzt
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
         "message": "Welcome to the Playcard Music Streamer API! Below are the available endpoints.",
         "available_endpoints": api_endpoints
     })

@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api/index")
@limiter.limit("100 per minute")
def get_index_json():
    """Gibt den Medienindex als JSON zurück."""
    # Der Client (z.B. Flutter) kann 'structured=1' explizit anfordern,
    # oder 'structured=0' für eine flache Liste.
    # Wichtig: Der Standard für die Suche sollte das Format sein, das Flutter am liebsten hat.
    # Wenn Flutter eine flache Liste will, sollte structured standardmäßig '0' sein.
    structured_request = request.args.get('structured', '0') == '1' # Standard auf '0' für flache Liste
    search_value = request.args.get("search", "").strip()

    # Diese Liste wird für die flache Ansicht verwendet, oder um die Songs
    # auch aus der strukturierten Ansicht zu sammeln, falls benötigt.
    all_songs_to_return = [] 

    if structured_request:
        # Wenn der Client explizit "structured=1" angefordert hat, gib die verschachtelte Struktur zurück
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
                    # Optional: Füge den Song auch zur flachen Liste hinzu, falls später benötigt
                    # all_songs_to_return.append(formatted_song) 
            formatted_structured_data.append({"folder_name": folder_name, "files": formatted_files_in_folder})

        return jsonify({
            "type": "structured",
            "data": formatted_structured_data
        })

    else: # Dies ist der "flache" View, der die Flutter-App bevorzugen sollte
        # Hole alle Einträge flach vom Index
        raw_entries = generate_index(structured=False) 
        if search_value:
            # Filterung der flachen Liste basierend auf dem Suchbegriff
            raw_entries = [
                e for e in raw_entries 
                if search_value.lower() in e['name'].lower() or \
                   search_value.lower() in os.path.splitext(e['name'])[0].lower()
            ]
        
        # Formatiere alle gefundenen Einträge
        for entry in raw_entries:
            formatted_song = _format_song_for_json(entry)
            if formatted_song:
                all_songs_to_return.append(formatted_song)

        # Gib hier eine reine Liste von Songs zurück (ohne "data": [] oder "type": "")
        # Dies ist das Format, das du für die Flutter-App wahrscheinlich bevorzugst.
        return jsonify(all_songs_to_return)




# Beispiel: JSON-Endpunkt für ein einzelnes Dateidetail (optional, kann aber nützlich sein)
@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api/track_info")
@limiter.limit("100 per minute")
def get_track_info_json():
    """Gibt detaillierte Informationen zu einem bestimmten Titel anhand seines relativen Pfads zurück."""
    rel_path = request.args.get('title')
    if not rel_path:
        # Hier ist die Fehlermeldung konsistent mit Flasks Abort-Standard
        abort(400, description="Relative path (title) parameter is required.")

    with INDEX_LOCK:
        # Finde den Eintrag im globalen Index basierend auf dem relativen Pfad.
        # Der MEDIA_INDEX enthält bereits die 'path'-Informationen.
        track_info = next((entry for entry in MEDIA_INDEX if entry.get('path') == rel_path), None)

    if not track_info:
        abort(404, description="Track not found.")

    # Nutze die zentrale Formatierungsfunktion, die auch das Cover sucht und die URLs generiert.
    formatted_track = _format_song_for_json(track_info)
    
    if not formatted_track:
        # Fehlerbehandlung, falls die Formatierung fehlschlägt.
        abort(500, description="Failed to format track information.")

    return jsonify(formatted_track)






@app.route(f"/{MUSIC_PATH}/{PLAYCARD_ENDPOINT}/api/random_track")
@limiter.limit("10 per minute")
def get_random_track_json():
    """Gibt Details zu einem zufälligen Medientitel zurück."""
    # Nur Musikdateien filtern
    music_entries = [entry for entry in MEDIA_INDEX if entry.get('ext') in [ext.lstrip('.') for ext in ALLOWED_EXTENSIONS]]
    
    if not music_entries:
        # Geänderte Fehlermeldung, damit sie konsistent mit anderen 404-Abbrüchen ist
        abort(404, description="No music tracks found to select a random one.")
    
    random_track = random.choice(music_entries)
    
    # Formatiere den zufälligen Track wie üblich mit der Hilfsfunktion
    formatted_track = _format_song_for_json(random_track)
    
    if not formatted_track:
        # Fehlerbehandlung, falls die Formatierung fehlschlägt
        abort(500, description="Failed to format random track information.")

    # Die JSON-Antwort sollte hier direkt das formatierte Track-Dictionary sein
    # zusammen mit einem Status, falls gewünscht. Der '**' Operator entpackt das formatted_track Dictionary.
    return jsonify({
        "status": "success",
        **formatted_track # Hier werden die Schlüssel und Werte aus formatted_track entpackt
    })

# -------------------------------
# New JSON-API Endpoint for Radio Status
# -------------------------------

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
    try:
        # Lazy imports: Only import if this function is called
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        app.logger.error(f"Missing required libraries for radio status API: {e}. Please install them (e.g., pip install requests beautifulsoup4 lxml).")
        return jsonify({
            "status": "error",
            "message": "Required libraries for radio status API are not installed on the server."
        }), 503 # Service Unavailable

    try:
        # 1. Fetch the external XML/HTML content
        response = requests.get(RADIO_NOW_PLAYING_URL, timeout=5) # 5-second timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        xml_content = response.text

        # 2. Parse the content using BeautifulSoup
        soup = BeautifulSoup(xml_content, 'lxml-xml')

        streams_data = []
        for server in soup.find_all('SHOUTCASTSERVER'):
            mount = server.find('MOUNT').text if server.find('MOUNT') else None
            current_listeners_raw = server.find('CURRENTLISTENERS').text if server.find('CURRENTLISTENERS') else '0'
            peak_listeners_raw = server.find('PEAKLISTENERS').text if server.find('PEAKLISTENERS') else '0'
            max_listeners_raw = server.find('MAXLISTENERS').text if server.find('MAXLISTENERS') else 'unlimited'
            server_title = server.find('SERVERTITLE').text if server.find('SERVERTITLE') else None

            artist = ''
            title = ''
            song_tag = server.find('SONG')
            if song_tag:
                artist_tag = song_tag.find('ARTIST')
                title_tag = song_tag.find('TITLE')
                if artist_tag:
                    artist = artist_tag.text.strip()
                if title_tag:
                    title = title_tag.text.strip()

            current_listeners = int(re.sub(r'\D', '', current_listeners_raw))
            peak_listeners = int(re.sub(r'\D', '', peak_listeners_raw))
            max_listeners = int(re.sub(r'\D', '', max_listeners_raw)) if 'unlimited' not in max_listeners_raw.lower() else 'unlimited'

            streams_data.append({
                "mount_point": mount,
                "server_title": server_title,
                "current_listeners": current_listeners,
                "peak_listeners": peak_listeners,
                "max_listeners": max_listeners,
                "now_playing": {
                    "artist": artist,
                    "title": title
                }
            })

        return jsonify({
            "status": "success",
            "radio_streams": streams_data
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching radio status from {RADIO_NOW_PLAYING_URL}: {e}")
        return jsonify({"status": "error", "message": f"Could not fetch radio status from external URL: {e}"}), 500
    except Exception as e:
        app.logger.error(f"Error parsing radio status: {e}")
        return jsonify({"status": "error", "message": f"Error processing radio status data: {e}"}), 500







# -------------------------------
# Run Application
# -------------------------------

if __name__ == "__main__":
    run_once_global()
    app.run(host="127.0.0.1", port=8010, threaded=True)
elif __name__ == '__main__':
    run_once_global()
    app.run(debug=True)
else:
    run_once_global()
    application = app  # <- Wichtig für uWSGI
