import os
import re
import html
import urllib.parse
import unicodedata
import locale
from flask import Flask, send_from_directory, abort, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# -------------------------------
# Configuration
# -------------------------------

# Base server directory
SERVERROOT = "/var/www/html"

# Path used in URLs
MUSIC_PATH = "musik"

# Optional media directories (checked in order)
MEDIA_DIRS = [
    os.path.join(SERVERROOT, "musik", "ogg"),
    os.path.join(SERVERROOT, "/home/radio"),
    os.environ.get("AUDIO_PATH")  # Can be set via environment
]

# Filter valid, existing directories
MEDIA_DIRS = [os.path.abspath(d) for d in MEDIA_DIRS if d and os.path.isdir(d)]

if not MEDIA_DIRS:
    raise RuntimeError("No valid media directories found.")

# Allowed audio file extensions
ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg']

# Set locale for proper sorting (e.g. with German umlauts)
locale.setlocale(locale.LC_ALL, '')

# -------------------------------
# App Setup
# -------------------------------

app = Flask(__name__)

# Use Memcached if available for rate limiting
try:
    import pymemcache.client
    use_memcached = True
except ImportError:
    use_memcached = False

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri="memcached://127.0.0.1:11211" if use_memcached else None,
    default_limits=["100 per minute"]
)

limiter.init_app(app)

# -------------------------------
# Utility Functions
# -------------------------------

def sort_key_locale(title):
    """Sort titles by first character type: letters first, then symbols, then numbers."""
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
    return (priority, title.lower())

def find_file(title_path, extensions):
    """Search for a file by normalized title and extension in MEDIA_DIRS."""
    title_normalized = unicodedata.normalize("NFC", os.path.splitext(title_path.strip())[0])
    for media_root in MEDIA_DIRS:
        candidate_path = os.path.join(media_root, title_path)
        if os.path.isfile(candidate_path):
            ext = os.path.splitext(candidate_path)[1].lower()
            if ext in extensions:
                return candidate_path, os.path.basename(candidate_path), ext

        for root, _, files in os.walk(media_root):
            for f in files:
                base, ext = os.path.splitext(f)
                if ext.lower() not in extensions:
                    continue
                if unicodedata.normalize("NFC", base.strip()) == os.path.basename(title_normalized):
                    return os.path.join(root, f), f, ext
    return None, None, None

def safe_quote(text):
    """Safely quote a string for use in URLs."""
    try:
        return urllib.parse.quote(text)
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        print(f"[WARN] Failed to quote {text!r}: {e}")
        return None

# -------------------------------
# Routes
# -------------------------------

@app.route(f"/{MUSIC_PATH}/playcard/<path:title>")
def playcard_audio(title):
    """Serve a specific audio file."""
    title_path = unicodedata.normalize("NFC", title)
    for media_root in MEDIA_DIRS:
        full_path = os.path.normpath(os.path.join(media_root, title_path))
        if os.path.isfile(full_path) and full_path.startswith(media_root):
            rel_dir = os.path.relpath(os.path.dirname(full_path), media_root)
            return send_from_directory(media_root, os.path.join(rel_dir, os.path.basename(full_path)))
    return abort(404)

@app.route(f"/{MUSIC_PATH}/playcard")
@limiter.limit("100 per minute")
def playcard():
    """List or serve a playable page for a given title."""
    raw_title = request.args.get("title", "").strip()
    requested_ext = request.args.get("ext")
    raw_title = urllib.parse.unquote(raw_title).replace("\\", "/")

    search_extensions = [f".{requested_ext.lower()}"] if requested_ext else ALLOWED_EXTENSIONS

    if not raw_title:
        # Generate HTML list of available files
        folder_map = {}
        for media_root in MEDIA_DIRS:
            for root, dirs, files in os.walk(media_root):
                rel_dir = os.path.relpath(root, media_root)
                for f in files:
                    base, ext = os.path.splitext(f)
                    if ext.lower() in ALLOWED_EXTENSIONS:
                        rel_file = os.path.relpath(os.path.join(root, f), media_root).replace("\\", "/")
                        folder_display = rel_dir if rel_dir != "." else "All Titles"
                        if folder_display not in folder_map:
                            folder_map[folder_display] = []
                        folder_map[folder_display].append((rel_file, ext.lower()))

        for k in folder_map:
            folder_map[k].sort(key=lambda item: sort_key_locale(item[0]))

        sorted_folders = sorted(folder_map.keys(), key=lambda k: sort_key_locale(k))

        html_page = "<html><head><title>Available Tracks</title></head><body background=\"https://jaquearnoux.de/radio.png\"><h1>Select a Track</h1>"
        for folder_display in sorted_folders:
            html_page += f"<h2>{html.escape(folder_display)}</h2><ul>"
            for full_title, ext in folder_map[folder_display]:
                quoted_title = safe_quote(full_title)
                if not quoted_title:
                    continue
                html_page += f'<li><a href="/{MUSIC_PATH}/playcard?title={quoted_title}&ext={ext[1:]}">{html.escape(os.path.basename(full_title))} ({ext[1:]})</a></li>'
            html_page += "</ul>"
        html_page += "</body></html>"
        return html_page

    # Serve single track
    file_path, file_name_exact, file_extension = find_file(raw_title, search_extensions)

    if not file_path:
        return abort(404, "File not found.")

    playcard_rel_path = None
    for media_root in MEDIA_DIRS:
        if file_path.startswith(media_root):
            playcard_rel_path = os.path.relpath(file_path, media_root).replace("\\", "/")
            break

    if not playcard_rel_path:
        return abort(403, "Access denied.")

    # Build base URL (supporting reverse proxy headers)
    # scheme = request.headers.get("X-Forwarded-Proto", request.scheme) # Get Proto from proxy
    scheme = "https" # hardcoded https
    host = request.headers.get("X-Forwarded-Host", request.host)
    base_url = f"{scheme}://{host}".rstrip("/")

    quoted_file = safe_quote(playcard_rel_path)
    audio_url = f"{base_url}/{MUSIC_PATH}/playcard/{quoted_file}"

    # Optional cover image (same name + .jpeg)
    imgpath = os.path.splitext(file_path)[0] + ".jpeg"
    img_html = ""
    if os.path.isfile(imgpath):
        img_rel = urllib.parse.quote(os.path.relpath(imgpath, media_root).replace("\\", "/"))
        img_html = f'<img src="/{MUSIC_PATH}/playcard/{img_rel}" width="300"><br>'

    # Render playback page
    html_out = f"""<!DOCTYPE html>
<html prefix="og: http://ogp.me/ns#">
  <head>
    <meta charset="utf-8"><title>{html.escape(file_name_exact)}</title>
    <meta property="og:audio" content="{audio_url}" />
    <meta property="og:audio:secure_url" content="{audio_url}" />
    <meta property="og:audio:type" content="audio/{file_extension[1:]}" />
    <meta property="og:type" content="music" />
    <meta property="og:video" content="{audio_url}">
    <meta property="og:video:secure_url" content="{audio_url}">
    <meta property="og:url" content="{base_url}/{MUSIC_PATH}/playcard?title={quoted_file}" />
    <meta property="og:title" content="Jaque Arnoux Radio {html.escape(file_name_exact)}" />
    <meta property="og:image" content="https://jaquearnoux.de/radio.png" />
    <link rel="stylesheet" href="radio.css" />
  </head>
  <body background="https://jaquearnoux.de/radio.png">
    <p>{html.escape(file_name_exact)}</p>
    <audio controls autoplay>
      <source src="{audio_url}" type="audio/{file_extension[1:]}">
      Dein Browser kann Audio nicht abspielen.
    </audio></br>
    {img_html}
    <script src="radio.js" async></script>
    <iframe src="{audio_url}" allow="autoplay"></iframe>
  </body>
</html>
"""
    return html_out

# -------------------------------
# Main Entry Point
# -------------------------------

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010)
