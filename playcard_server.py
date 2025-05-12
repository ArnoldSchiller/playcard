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

# Define base directories and media path based on local environment or environment variable
SERVERROOT = "/var/www/html"
MUSIC_PATH = "musik"
MEDIA_PATH = "ogg"
AUDIO_PATH = os.path.join(SERVERROOT, MUSIC_PATH, MEDIA_PATH) if os.path.isdir(os.path.join(SERVERROOT, MUSIC_PATH, MEDIA_PATH)) else os.environ.get("AUDIO_PATH")

if AUDIO_PATH is None:
    raise RuntimeError("Please set the AUDIO_PATH environment variable or ensure the default path exists.")

# Define allowed media extensions and their priority for choosing among duplicates
ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg', '%20.mp4', '%20.mp3', '%20.ogg']
EXT_PRIORITY = {'.mp3': 1, '.mp4': 2, '.ogg': 3}

# Initialize Flask app and request limiter
app = Flask(__name__)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memcached://127.0.0.1:11211",
    default_limits=["100 per minute"]
)
limiter.init_app(app)

# Set locale for sorting
locale.setlocale(locale.LC_ALL, '')

# Define sorting key for display list based on locale and character category
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

# Define the route for generating a playcard page
title_route = f"/{MUSIC_PATH}/playcard"
@app.route(title_route)
@limiter.limit("100 per minute")
def playcard():
    # Parse query parameters
    raw_title = request.args.get("title", "").strip()
    raw_title = unicodedata.normalize("NFC", raw_title)
    requested_ext = request.args.get("ext")

    # Extract filename from URL if title is a URL
    url_match = re.search(r'https?://[^\s]+', raw_title)
    if url_match:
        parsed = urlparse(url_match.group(0))
        title_with_ext = os.path.basename(parsed.path)
    else:
        title_with_ext = os.path.basename(raw_title)

    # Split filename and extension, normalize title
    title, ext_from_title = os.path.splitext(title_with_ext)
    title = unicodedata.normalize("NFC", title.strip())

    # Determine list of extensions to search
    if requested_ext:
        search_extensions = [f".{requested_ext.lower()}"]
    elif ext_from_title.lower() in ALLOWED_EXTENSIONS:
        search_extensions = [ext_from_title.lower()]
    else:
        search_extensions = ALLOWED_EXTENSIONS

    # If no specific title, list all available files
    if not title:
        files = os.listdir(AUDIO_PATH)
        titles = {}
        for f in files:
            base, ext = os.path.splitext(f)
            base = unicodedata.normalize("NFC", base.strip())
            if ext in ALLOWED_EXTENSIONS:
                if base not in titles or EXT_PRIORITY[ext] < EXT_PRIORITY[titles[base]]:
                    titles[base] = ext

        html_page = "<html><head><title>Available Titles</title></head><body background=\"https://jaquearnoux.de/radio.png\"><h1>Select a Title</h1><ul>"
        for base in sorted(titles.keys(), key=sort_key_locale):
            ext = titles[base]
            html_page += f'<li><a href="/{MUSIC_PATH}/playcard?title={urllib.parse.quote(base)}&ext={ext[1:]}">{html.escape(base)} ({ext[1:]})</a></li>'
        html_page += "</ul></body></html>"
        return html_page

    # Look for a matching file
    file_path = None
    file_extension = None
    file_name_exact = None

    for ext in search_extensions:
        for f in os.listdir(AUDIO_PATH):
            base, file_ext = os.path.splitext(f)
            if file_ext.lower() != ext:
                continue
            base_normalized = unicodedata.normalize("NFC", base).strip()
            title_normalized = unicodedata.normalize("NFC", title).strip()
            if base_normalized == title_normalized:
                file_path = os.path.normpath(os.path.join(AUDIO_PATH, f))
                file_extension = ext
                file_name_exact = f
                break
        if file_path:
            break

    # Reject access if file not found or outside allowed path
    if not file_path or not file_path.startswith(os.path.abspath(AUDIO_PATH)):
        return abort(403, "Access denied.")

    # Check for optional cover image
    imgpath = os.path.join(AUDIO_PATH, f"{title}.jpeg")
    img_html = f'<img src="/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(title)}.jpeg" width="300"><br>' if os.path.isfile(imgpath) else ""

    # Build OpenGraph-friendly HTML response
    base_url = request.url_root.rstrip('/')
    html_out = f"""<!DOCTYPE html>
<html prefix=\"og: http://ogp.me/ns#\">
  <head>
    <meta charset=\"utf-8\"><title>{html.escape(title)}</title>
    <meta property=\"og:audio\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(file_name_exact)}\" />
    <meta property=\"og:audio:secure_url\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(file_name_exact)}\" />
    <meta property=\"og:audio:type\" content=\"audio/{file_extension[1:]}\" />
    <meta property=\"og:type\" content=\"music\" />
    <meta property=\"og:video\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(file_name_exact)}\">
    <meta property=\"og:video:secure_url\" content=\"{base_url}/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(file_name_exact)}\">
    <meta property=\"og:url\" content=\"{base_url}/{MUSIC_PATH}/playcard?title={urllib.parse.quote(title)}\" />
    <meta property=\"og:title\" content=\"Jaque Arnoux Radio {html.escape(title)}\" />
    <meta property=\"og:image\" content=\"https://jaquearnoux.de/radio.png\" />
  </head>
  <body background=\"https://jaquearnoux.de/radio.png\">
    <audio controls autoplay>
      <source src=\"/{MUSIC_PATH}/{MEDIA_PATH}/{urllib.parse.quote(file_name_exact)}\" type=\"audio/{file_extension[1:]}\">
      Your browser does not support the audio element.
    </audio>
    {img_html}
    <script src=\"radio.js\" async></script>
    <iframe src=\"/{MUSIC_PATH}/{MEDIA_PATH}/{title}{file_extension}\" allow=\"autoplay\"></iframe>
  </body>
</html>"""
    return html_out

# Run the app if this file is executed directly
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010)
