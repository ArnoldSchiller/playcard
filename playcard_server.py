import os
import re
import html
import urllib.parse
import locale
import fcntl
import random
from flask import Flask, send_from_directory, abort, redirect, request, render_template_string, url_for
from markupsafe import escape
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from difflib import get_close_matches
from threading import Lock


# -------------------------------
# Configuration (identisch zu PHP)
# -------------------------------
SERVERROOT = "/var/www/html"
MUSIC_PATH = "musik"
PLAYCARD_ENDPOINT = "playcard"


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
    os.path.join(SERVERROOT, "/jaquearnoux"),
    "/home/radio/radio/ogg",
    os.environ.get("AUDIO_PATH")
]:
    if path and os.path.isdir(path):
        MEDIA_DIRS.append(os.path.abspath(path))

if not MEDIA_DIRS:
    raise RuntimeError("No valid media directories found.")

ALLOWED_EXTENSIONS = {'.mp3', '.mp4', '.ogg', '.ogv', '.webm'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
EXTENSIONS = ALLOWED_EXTENSIONS | IMAGE_EXTENSIONS

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
