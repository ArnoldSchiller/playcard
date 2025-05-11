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

# Lokale Umgebung bevorzugt, sonst Umgebungsvariable
AUDIO_PATH = "/var/www/html/musik/" if os.path.isdir("/var/www/html/musik/") else os.environ.get("AUDIO_PATH")
if AUDIO_PATH is None:
    raise RuntimeError("Bitte setze die Umgebungsvariable AUDIO_PATH oder verwende den Standardpfad.")

ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg']
EXT_PRIORITY = {'.mp3': 1, '.mp4': 2, '.ogg': 3}

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

@app.route("/musik/playcard")
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

    if not title:
        files = os.listdir(AUDIO_PATH)
        titles = {}
        for f in files:
            base, ext = os.path.splitext(f)
            base = unicodedata.normalize("NFC", base.strip())
            if ext in ALLOWED_EXTENSIONS:
                if base not in titles or EXT_PRIORITY[ext] < EXT_PRIORITY[titles[base]]:
                    titles[base] = ext
        html_page = "<html><head><title>Verfügbare Titel</title></head><body background=\"https://jaquearnoux.de/radio.png\"><h1>Wähle einen Titel</h1><ul>"
        for base in sorted(titles.keys(), key=sort_key_locale):
            ext = titles[base]
            html_page += f'<li><a href="/musik/playcard?title={urllib.parse.quote(base)}&ext={ext[1:]}">{html.escape(base)} ({ext[1:]})</a></li>'
        html_page += "</ul></body></html>"
        return html_page

    file_path = None
    file_extension = None
    for ext in search_extensions:
        potential_file = os.path.join(AUDIO_PATH, title + ext)
        if os.path.exists(potential_file):
            file_path = os.path.normpath(potential_file)
            file_extension = ext
            break

    if not file_path or not file_path.startswith(os.path.abspath(AUDIO_PATH)):
        return abort(403, "Zugriff verweigert.")

    imgpath = os.path.join(AUDIO_PATH, f"{title}.jpeg")
    img_html = f'<img src="/musik/ogg/{urllib.parse.quote(title)}.jpeg" width="300"><br>' if os.path.isfile(imgpath) else ""

    # Host-URL ermitteln, damit OpenGraph immer korrekt ist
    base_url = request.url_root.rstrip('/')

    html_out = f"""<!DOCTYPE html>
<html prefix="og: http://ogp.me/ns#">
  <head>
    <meta charset="utf-8"><title>{html.escape(title)}</title>
    <meta property="og:audio" content="{base_url}/musik/ogg/{urllib.parse.quote(title)}{file_extension}" />
    <meta property="og:audio:secure_url" content="{base_url}/musik/ogg/{urllib.parse.quote(title)}{file_extension}" />
    <meta property="og:audio:type" content="audio/{file_extension[1:]}" />
    <meta property="og:type" content="music" />
    <meta property="og:video" content="{base_url}/musik/ogg/{urllib.parse.quote(title)}{file_extension}">
    <meta property="og:video:secure_url" content="{base_url}/musik/ogg/{urllib.parse.quote(title)}{file_extension}">
    <meta property="og:url" content="{base_url}/musik/playcard?title={urllib.parse.quote(title)}" />
    <meta property="og:title" content="Jaque Arnoux Radio {html.escape(title)}" />
    <meta property="og:image" content="https://jaquearnoux.de/radio.png" />
  </head>
  <body background="https://jaquearnoux.de/radio.png">
    <audio controls autoplay>
      <source src="/musik/ogg/{urllib.parse.quote(title)}{file_extension}" type="audio/{file_extension[1:]}">
      Dein Browser kann das Audio nicht wiedergeben.
    </audio>
    {img_html}
  </body>
</html>"""
    return html_out

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010)

