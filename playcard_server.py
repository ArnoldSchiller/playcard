import os
import re
import html
import urllib.parse
import unicodedata
import locale
from urllib.parse import urlparse
from flask import Flask, send_from_directory, abort, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Configuration ---
# Use default directory or environment variable
SERVERROOT = "/var/www/html"
MUSIC_PATH = "musik/"
MEDIA_PATH = "ogg"
AUDIO_PATH = os.path.join(SERVERROOT, MUSIC_PATH, MEDIA_PATH) if os.path.isdir(os.path.join(SERVERROOT, MUSIC_PATH, MEDIA_PATH)) else os.environ.get("AUDIO_PATH")
if AUDIO_PATH is None:
    raise RuntimeError("Set AUDIO_PATH environment variable or use default path.")

# Allowed audio file types
ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg']
EXT_PRIORITY = {'.mp3': 1, '.mp4': 2, '.ogg': 3}

# --- Initialize Flask app ---
# Check if memcached is available
try:
    import pymemcache.client
    use_memcached = True
except ImportError:
    use_memcached = False

# Create Flask app
app = Flask(__name__)

# Conditionally configure Flask-Limiter
if use_memcached:
    # If pymemcache is available, use memcached
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        storage_uri="memcached://127.0.0.1:11211",
        default_limits=["100 per minute"]
    )
else:
    # Otherwise, use in-memory storage
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["100 per minute"]
    )


limiter.init_app(app)
locale.setlocale(locale.LC_ALL, '')

# Sort key based on locale and initial character
def sort_key_locale(title):
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

@app.route(f"/{MUSIC_PATH}/playcard")
@limiter.limit("100 per minute")
def playcard():
    # Read and normalize input
    raw_title = request.args.get("title", "").strip()
    requested_ext = request.args.get("ext")

    raw_title = urllib.parse.unquote(raw_title).replace("\\", "/")
    title_path = unicodedata.normalize("NFC", raw_title)

    file_path = None
    file_name_exact = None
    file_extension = None

    # Determine search extensions
    if requested_ext:
        search_extensions = [f".{requested_ext.lower()}"]
    else:
        search_extensions = ALLOWED_EXTENSIONS

    # Try direct path resolution if title looks like a path
    candidate_path = os.path.join(AUDIO_PATH, title_path)
    if os.path.isfile(candidate_path) and candidate_path.startswith(os.path.abspath(AUDIO_PATH)):
        file_path = candidate_path
        file_name_exact = os.path.basename(candidate_path)
        file_extension = os.path.splitext(file_name_exact)[1].lower()
    else:
        # Otherwise search manually by filename match
        for root, _, files in os.walk(AUDIO_PATH):
            for f in files:
                base, ext = os.path.splitext(f)
                if ext.lower() not in search_extensions:
                    continue
                base_normalized = unicodedata.normalize("NFC", base.strip())
                title_normalized = unicodedata.normalize("NFC", os.path.splitext(title_path)[0].strip())
                if base_normalized == os.path.basename(title_normalized):
                    file_path = os.path.join(root, f)
                    file_extension = ext
                    file_name_exact = f
                    break
            if file_path:
                break

    # If no title is specified in the query, display a structured index of all available files
    # If no specific title is given, build an overview page
    if not raw_title:
        # Dictionary to group songs by subfolder (relative to AUDIO_PATH)
        folder_map = {}

        for root, dirs, files in os.walk(AUDIO_PATH):
            rel_dir = os.path.relpath(root, AUDIO_PATH)

            for f in files:
                base, ext = os.path.splitext(f)
                if ext.lower() in ALLOWED_EXTENSIONS:
                    # Normalize title (strip spaces, normalize accents etc.)
                    base_clean = unicodedata.normalize("NFC", base.strip())

                    # Build title path (relative from AUDIO_PATH, slash-separated)
                    if rel_dir == ".":
                        full_title = base_clean
                    else:
                        full_title = os.path.join(rel_dir, base_clean)

                    # Use relative folder name as display category
                    folder_display = rel_dir if rel_dir != "." else "Alle Titel"

                    if folder_display not in folder_map:
                        folder_map[folder_display] = []
                    folder_map[folder_display].append((full_title, ext.lower()))

        # Sort each folder’s content using sort_key_locale
        for k in folder_map:
            folder_map[k].sort(key=lambda item: sort_key_locale(item[0]))

        # Sort folder names alphabetically
        sorted_folders = sorted(folder_map.keys(), key=lambda k: sort_key_locale(k))

        # Build the overview HTML
        html_page = "<html><head><title>Verfügbare Titel</title></head><body background=\"https://jaquearnoux.de/radio.png\"><h1>Wähle einen Titel</h1>"

        for folder_display in sorted_folders:
            html_page += f"<h2>{html.escape(folder_display)}</h2><ul>"
            for full_title, ext in folder_map[folder_display]:
                quoted_title = urllib.parse.quote(full_title)
                html_page += f'<li><a href="/{MUSIC_PATH}playcard?title={quoted_title}&ext={ext[1:]}">{html.escape(os.path.basename(full_title))} ({ext[1:]})</a></li>'
            html_page += "</ul>"

        html_page += "</body></html>"
        return html_page



    # Final path safety check
    if not file_path or not file_path.startswith(os.path.abspath(AUDIO_PATH)):
        return abort(403, "Access denied.")

    # Optional image if exists
    imgpath = os.path.splitext(file_path)[0] + ".jpeg"
    rel_img = os.path.relpath(imgpath, AUDIO_PATH).replace("\\", "/")
    img_html = f'<img src="/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(rel_img)}" width="300"><br>' if os.path.isfile(imgpath) else ""

    base_url = request.url_root.rstrip('/')
    quoted_file = urllib.parse.quote(os.path.relpath(file_path, AUDIO_PATH).replace("\\", "/"))

    # Build HTML output
    html_out = f"""<!DOCTYPE html>
<html prefix=\"og: http://ogp.me/ns#\">
  <head>
    <meta charset=\"utf-8\"><title>{html.escape(file_name_exact)}</title>
    <meta property=\"og:audio\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{quoted_file}\" />
    <meta property=\"og:audio:secure_url\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{quoted_file}\" />
    <meta property=\"og:audio:type\" content=\"audio/{file_extension[1:]}\" />
    <meta property=\"og:type\" content=\"music\" />
    <meta property=\"og:video\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{quoted_file}\">
    <meta property=\"og:video:secure_url\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{quoted_file}\">
    <meta property=\"og:url\" content=\"{base_url}/{MUSIC_PATH}/playcard?title={urllib.parse.quote(title_path)}\" />
    <meta property=\"og:title\" content=\"Jaque Arnoux Radio {html.escape(file_name_exact)}\" />
    <meta property=\"og:image\" content=\"https://jaquearnoux.de/radio.png\" />
  </head>
  <body background=\"https://jaquearnoux.de/radio.png\">
    <audio controls autoplay>
      <source src="/{MUSIC_PATH}/{MEDIA_PATH}/{quoted_file}" type="audio/{file_extension[1:]}">
      Your browser does not support audio playback.
    </audio>
    {img_html}
    <script src="radio.js" async></script>
    <iframe src="/{MUSIC_PATH}/{MEDIA_PATH}/{quoted_file}" allow="autoplay"></iframe>
  </body>
</html>"""
    return html_out

# Run development server
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010)
