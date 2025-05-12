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

# --- Configuration and constants ---
SERVERROOT = "/var/www/html"
MUSIC_PATH = "musik/"
MEDIA_PATH = "ogg"
AUDIO_PATH = os.path.join(SERVERROOT, MUSIC_PATH, MEDIA_PATH)
if not os.path.isdir(AUDIO_PATH):
    AUDIO_PATH = os.environ.get("AUDIO_PATH")
if AUDIO_PATH is None:
    raise RuntimeError("Please set AUDIO_PATH environment variable or use the default path.")

ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg']
EXT_PRIORITY = {'.mp3': 1, '.mp4': 2, '.ogg': 3}

# --- Flask application setup ---
app = Flask(__name__)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memcached://127.0.0.1:11211",
    default_limits=["100 per minute"]
)
limiter.init_app(app)

locale.setlocale(locale.LC_ALL, '')

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

# --- Main playcard route ---
@app.route(f"/{MUSIC_PATH}/playcard")
@limiter.limit("100 per minute")
def playcard():
    raw_title = request.args.get("title", "").strip()
    raw_title = unicodedata.normalize("NFC", raw_title)
    requested_ext = request.args.get("ext")

    url_match = re.search(r'https?://[^\s]+', raw_title)
    if url_match:
        parsed = urlparse(url_match.group(0))
        title_with_ext = os.path.basename(parsed.path)
    else:
        title_with_ext = os.path.basename(raw_title)

    title, ext_from_title = os.path.splitext(title_with_ext)
    title = unicodedata.normalize("NFC", title.strip())

    search_extensions = []
    if requested_ext:
        search_extensions = [f".{requested_ext.lower()}"]
    elif ext_from_title.lower() in ALLOWED_EXTENSIONS:
        search_extensions = [ext_from_title.lower()]
    else:
        search_extensions = ALLOWED_EXTENSIONS

    file_path = None
    file_name_exact = None
    rel_path = None
    
    # --- Search all subdirectories for a matching file ---
    for ext in search_extensions:
        for root, dirs, files in os.walk(AUDIO_PATH):
            for f in files:
                base, file_ext = os.path.splitext(f)
                if file_ext.lower() != ext:
                    continue
                base_normalized = unicodedata.normalize("NFC", base).strip()
                title_normalized = unicodedata.normalize("NFC", title).strip()
                if base_normalized == title_normalized:
                    file_path = os.path.normpath(os.path.join(root, f))
                    file_name_exact = f
                    rel_path = os.path.relpath(file_path, AUDIO_PATH)
                    break
            if file_path:
                break
        if file_path:
            break

    # --- If no title given, show selection list of all audio files ---
    if not raw_title:
        titles = {}
        for root, dirs, files in os.walk(AUDIO_PATH):
            for f in files:
                base, ext = os.path.splitext(f)
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                base = unicodedata.normalize("NFC", base.strip())
                rel = os.path.relpath(os.path.join(root, f), AUDIO_PATH)
                if base not in titles or EXT_PRIORITY[ext] < EXT_PRIORITY[titles[base][1]]:
                    titles[base] = (rel, ext)

        html_page = "<html><head><title>Available Titles</title></head><body background=\"https://jaquearnoux.de/radio.png\"><h1>Select a Title</h1><ul>"
        for base in sorted(titles.keys(), key=sort_key_locale):
            rel, ext = titles[base]
            html_page += f'<li><a href="/{MUSIC_PATH}/playcard?title={urllib.parse.quote(base)}&ext={ext[1:]}">{html.escape(base)} ({ext[1:]})</a></li>'
        html_page += "</ul></body></html>"
        return html_page

    if not file_path or not file_path.startswith(os.path.abspath(AUDIO_PATH)):
        return abort(403, "Access denied.")

    # --- Optional image if available ---
    imgpath = os.path.join(os.path.dirname(file_path), f"{title}.jpeg")
    img_rel = os.path.relpath(imgpath, AUDIO_PATH)
    img_html = f'<img src="/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(img_rel)}" width="300"><br>' if os.path.isfile(imgpath) else ""

    base_url = request.url_root.rstrip('/')
    url_encoded_path = urllib.parse.quote(rel_path)

    html_out = f"""<!DOCTYPE html>
<html prefix=\"og: http://ogp.me/ns#\">
  <head>
    <meta charset=\"utf-8\"><title>{html.escape(title)}</title>
    <meta property=\"og:audio\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{url_encoded_path}\" />
    <meta property=\"og:audio:secure_url\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{url_encoded_path}\" />
    <meta property=\"og:audio:type\" content=\"audio/{file_ext[1:]}\" />
    <meta property=\"og:type\" content=\"music\" />
    <meta property=\"og:video\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{url_encoded_path}\">
    <meta property=\"og:video:secure_url\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{url_encoded_path}\">
    <meta property=\"og:url\" content=\"{base_url}/{MUSIC_PATH}/playcard?title={urllib.parse.quote(title)}\" />
    <meta property=\"og:title\" content=\"Jaque Arnoux Radio {html.escape(title)}\" />
    <meta property=\"og:image\" content=\"https://jaquearnoux.de/radio.png\" />
  </head>
  <body background=\"https://jaquearnoux.de/radio.png\">
    <audio controls autoplay>
      <source src=\"/{MUSIC_PATH}/{MEDIA_PATH}/{url_encoded_path}\" type=\"audio/{file_ext[1:]}\">
      Your browser does not support the audio element.
    </audio>
    {img_html}
     <script src=\"radio.js\" async></script>
    <iframe src=\"/{MUSIC_PATH}/{MEDIA_PATH}/{url_encoded_path}\" allow=\"autoplay\"></iframe>
  </body>
</html>"""
    return html_out

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010)
