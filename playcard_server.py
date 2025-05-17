import os
import re
import html
import urllib.parse
import locale
from flask import Flask, send_from_directory, abort, request, render_template_string
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# -------------------------------
# Configuration (identisch zu PHP)
# -------------------------------
SERVERROOT = "/var/www/html"
MUSIC_PATH = "musik"

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

ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg', '.ogv', '.webm']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png']

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
        base = os.path.normpath(base)
        if absolute_path.startswith(base):
            return absolute_path[len(base):].lstrip('/\\')
    return absolute_path

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
                return {
                    'path': full_path,
                    'name': os.path.basename(full_path),
                    'ext': ext[1:],
                    'rel_path': get_relative_path(full_path)
                }
    
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
                    return {
                        'path': full_path,
                        'name': f,
                        'ext': ext[1:],
                        'rel_path': get_relative_path(full_path)
                    }
    return None

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
    stream_url = f"{base_url}/{MUSIC_PATH}/playcard/{urllib.parse.quote(file_info['rel_path'])}"
    page_url = f"{base_url}/{MUSIC_PATH}/playcard?title={urllib.parse.quote(file_info['rel_path'])}"
    
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
    """Index-Generierung wie in PHP"""
    entries = []
    folder_map = {}
    
    for media_root in filter_media_dirs(MEDIA_DIRS):
        for root, _, files in os.walk(media_root):
            rel_dir = os.path.relpath(root, media_root)
            if rel_dir == '.':
                rel_dir = ''
                
            for f in files:
                full_path = os.path.normpath(os.path.join(root, f))
                if is_forbidden(full_path):
                    continue
                    
                ext = os.path.splitext(f)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    rel_path = os.path.join(rel_dir, f).replace('\\', '/')
                    entry = {
                        'name': f,
                        'path': rel_path,
                        'ext': ext[1:]
                    }
                    
                    if structured:
                        if rel_dir not in folder_map:
                            folder_map[rel_dir] = []
                        folder_map[rel_dir].append(entry)
                    entries.append(entry)
    
    # Sortierung wie in PHP
    if structured:
        for folder in folder_map:
            folder_map[folder].sort(key=lambda x: sort_key_locale(x['name']))
        folder_map = dict(sorted(folder_map.items(), key=lambda x: sort_key_locale(x[0])))
    else:
        entries.sort(key=lambda x: sort_key_locale(x['name']))
    
    return folder_map if structured else entries

# -------------------------------
# Routes (identisch zu PHP)
# -------------------------------
@app.route(f"/{MUSIC_PATH}/playcard/<path:filename>")
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

@app.route(f"/{MUSIC_PATH}/playcard")
@limiter.limit("100 per minute")
def playcard():
    """Identische Logik wie PHP-Version"""
    raw_title = request.args.get('title', '').strip()
    structured = request.args.get('structured', '1') == '1'
    
    if not raw_title:
        # Index-Generierung wie in PHP
        if structured:
            folder_map = generate_index(structured=True)
            shuffle_track = next(iter(folder_map.values()))[0] if folder_map else None
            shuffle_url = f"?title={urllib.parse.quote(shuffle_track['path'])}" if shuffle_track else "#"
            
            return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head><title>Playcard Music Streamer</title>
                <link rel="stylesheet" href="/radio.css"></head>
                <body>
                    <h1>Playcard Music Streamer</h1>
                    <form method="get">
                        <input type="hidden" name="structured" value="0">
                        <button type="submit">🔤 Flat View</button>
                    </form>
                    {% if shuffle_url %}<p><a href="{{ shuffle_url }}">🔀 Random Title</a></p>{% endif %}
                    <div class="tracklist">
                        {% for folder, files in folder_map.items() %}
                        <div class="folder">
                            <h2>{{ folder or 'Root' }}</h2>
                            {% for file in files %}
                            <div class="track">
                                <a href="?title={{ file.path|urlencode }}">{{ file.name }}</a>
                            </div>
                            {% endfor %}
                        </div>
                        {% endfor %}
                    </div>
                </body>
                </html>
            """, folder_map=folder_map, shuffle_url=shuffle_url)
        else:
            entries = generate_index(structured=False)
            shuffle_track = entries[0] if entries else None
            shuffle_url = f"?title={urllib.parse.quote(shuffle_track['path'])}" if shuffle_track else "#"
            
            return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head><title>Playcard Music Streamer</title>
                <link rel="stylesheet" href="/radio.css"></head>
                <body>
                    <h1>Playcard Music Streamer</h1>
                    <form method="get">
                        <input type="hidden" name="structured" value="1">
                        <button type="submit">📁 Structured View</button>
                    </form>
                    {% if shuffle_url %}<p><a href="{{ shuffle_url }}">🔀 Random Title</a></p>{% endif %}
                    <div class="tracklist">
                        {% for entry in entries %}
                        <div class="track">
                            <a href="?title={{ entry.path|urlencode }}">{{ entry.name }}</a>
                        </div>
                        {% endfor %}
                    </div>
                </body>
                </html>
            """, entries=entries, shuffle_url=shuffle_url)
    
    # Restliche Implementierung wie im Original
    file_info = find_file(raw_title, ALLOWED_EXTENSIONS)
    if not file_info:
        abort(404)
    
    # Cover-Bild suchen wie in PHP
    cover_html = ""
    cover_path = find_cover_image(file_info['path'], os.path.splitext(file_info['name'])[0])
    if cover_path:
        for media_root in MEDIA_DIRS:
            if cover_path.startswith(media_root):
                rel_cover = get_relative_path(cover_path)
                cover_url = f"/{MUSIC_PATH}/playcard/{urllib.parse.quote(rel_cover)}"
                cover_html = f'<img src="{cover_url}" width="300" alt="Cover"><br>'
                break
    
    # Player HTML wie in PHP
    player_url = f"/{MUSIC_PATH}/playcard/{urllib.parse.quote(file_info['rel_path'])}"
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
                <p><a href="?">Back to index</a></p>
            </div>
            <script src="/radio.js" async></script>
        </body>
        </html>
    """, 
    title=html.escape(file_info['name']),
    og_tags=generate_open_graph_tags(file_info, request),
    cover_html=cover_html,
    player_html=player_html)
# -------------------------------
# Run Application
# -------------------------------

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010, threaded=True)
