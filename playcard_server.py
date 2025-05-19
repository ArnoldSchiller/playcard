import os
import re
import html
import urllib.parse
import locale
import fcntl
from flask import Flask, send_from_directory, abort, redirect, request, render_template_string, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from difflib import get_close_matches
from threading import Lock


# -------------------------------
# Configuration (identisch zu PHP)
# -------------------------------
SERVERROOT = os.environ.get("SERVERROOT", "/var/www/html") # Default-Wert falls nicht gesetzt
MUSIC_PATH = os.environ.get("MUSIC_PATH", "musik")
PLAYCARD_ENDPOINT = os.environ.get("PLAYCARD_ENDPOINT", "playcard")


FORBIDDEN_DIRS = [
    "Artist/Album",
    "Artist_Artist/Some_fancy_Album",
    "Name Artist - ...Some fance text album ...",
    "wordpress",
    "phpgedview",
    "forbidden_folder"
]

MEDIA_DIRS = []
for path in [
    os.path.join(SERVERROOT, ""),
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
        return s.encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
    except Exception:
        return '[Invalid UTF-8]'

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
                            safe_rel_path = relative_path.encode('utf-8').decode('utf-8', 'replace') if relative_path else ''
                            MEDIA_INDEX.append({
                                'path': full_path,
                                'name': safe_string(f),
                                'base': safe_string(base),
                                'ext': ext[1:],  # ohne Punkt
                                'rel_path': safe_rel_path
                            })
                        except UnicodeEncodeError as e:
                            app.logger.warning(f"Skipping file with encoding issue: {full_path} - {e}")
                            continue


def run_once_global():
    lockfile = f'/tmp/{PLAYCARD_ENDPOINT}_init.lock'
    with open(lockfile, 'w') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Init-Code nur einmal ausführen:
            print("Initialisierung (einmalig pro Serverstart)")
            build_media_index(EXTENSIONS) # Build index on startup
        except BlockingIOError:
            # Lock bereits gehalten → andere Instanz hat init schon gemacht
            pass

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
    search_term_lower = search_term.lower()
    matches = []

    for entry in MEDIA_INDEX:
        base_lower = entry['base'].lower()
        if (search_term_lower in base_lower or
                get_close_matches(search_term_lower, [base_lower], n=1, cutoff=0.7)):
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
    """Index-Generierung unter Verwendung von MEDIA_INDEX"""
    entries = []
    folder_map = {}

    for entry in MEDIA_INDEX:
        if structured:
            rel_dir = os.path.dirname(entry['rel_path'])
            if rel_dir not in folder_map:
                folder_map[rel_dir] = []
            folder_map[rel_dir].append(entry)
            entries.append(entry)  # Für den Fall der flachen Ansicht trotzdem sammeln
        else:
            entries.append(entry)

    # Sortierung wie in PHP
    if structured:
        for folder in folder_map:
            folder_map[folder].sort(key=lambda x: sort_key_locale(x['name']))
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
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head><title>Playcard Music Streamer</title>
        <link rel="stylesheet" href="/radio.css"></head>
        <body>
            <h1>Playcard Music Streamer</h1>
            {{ searchform|safe }}
            <form method="get">
                <input type="hidden" name="structured" value="{{ 0 if structured else 1 }}">
                <button type="submit">{{ "🔤 Flat View" if structured else "📁 Structured View" }}</button>
            </form>
            {% if shuffle_url %}<p><a href="{{ shuffle_url }}">🔀 Random Title</a></p>{% endif %}
            <div class="tracklist">
                {% if structured %}
                    {% for folder, files in folder_map.items() %}
                    <div class="folder">
                        <h2>{{ folder or 'Root' }}</h2>
                        {% for file in files %}
                        <div class="track">
                            <a href="?title={{ file.rel_path|urlencode }}">{{ file.name }}</a>
                        </div>
                        {% endfor %}
                    </div>
                    {% endfor %}
                {% else %}
                    {% for entry in entries %}
                    <div class="track">
                        <a href="?title={{ entry.rel_path|urlencode }}">{{ entry.name }}</a>
                    </div>
                    {% endfor %}
                {% endif %}
            </div>
        </body>
        </html>
    """, structured=structured, entries=entries, folder_map=folder_map, shuffle_url=shuffle_url, searchform=searchform)

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
    # Formularverarbeitung (neu)
    search_value = ""
    if request.method == "POST":
        search_value = request.form.get("title", "").strip()
        if search_value:
            return redirect(url_for('playcard', title=search_value))
    elif request.method == "GET":
        search_value = request.args.get("title") or request.args.get("search") or ""
    search_value = search_value.strip()

    # """Identische Logik wie PHP-Version"""
    raw_title = search_value # Nutze den bereits verarbeiteten Suchbegriff
    structured = request.args.get('structured', '1') == '1'
    matches = find_all_matches_from_index(raw_title, limit=10)

    if not raw_title:
        if structured:
            folder_map = generate_index(structured=True)
            if search_value:
                folder_map = filter_folder_map(folder_map, search_value)
            shuffle_track = next(iter(folder_map.values()))[0] if folder_map and folder_map.values() and next(iter(folder_map.values())) else None
        else:
            entries = generate_index(structured=False)
            if search_value:
                entries = [entry for entry in entries if search_value.lower() in entry['name'].lower()]
            shuffle_track = entries[0] if entries else None

        shuffle_url = url_for('playcard', title=shuffle_track['path']) if shuffle_track else "#"

        return render_index(
            structured=structured,
            entries=entries if not structured else None,
            folder_map=folder_map if structured else None,
            shuffle_url=shuffle_url,
            searchform=searchform_html()
        )


    elif len(matches) == 1:
            # Nur 1 Match → direkt Player anzeigen
            file_info = matches[0]

    else:
        file_info = find_file(raw_title, ALLOWED_EXTENSIONS)
    if not file_info:
        abort(404)

    # Cover-Bild suchen wie in PHP
    cover_html = ""
    cover_path = find_cover_image(file_info['path'], os.path.splitext(file_info['name'])[0])
    if cover_path:
        for media_root in MEDIA_DIRS:
            if cover_path.startswith(media_root):
                rel_cover = get_safe_relative_path(cover_path)
                cover_url = url_for('serve_file', filename=rel_cover)
                cover_html = f'<img src="{cover_url}" width="300" alt="Cover"><br>'
                break

    # Player HTML wie in PHP
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
# Run Application
# -------------------------------

if __name__ == "__main__":
    run_once_global()
    app.run(host="127.0.0.1", port=8010, threaded=True)
