import re
import urllib.parse
from flask import Flask, send_from_directory, abort, request
from urllib.parse import urlparse
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memcached://127.0.0.1:11211",
    default_limits=["100 per minute"]
)
limiter.init_app(app)

# Set your audio directory path here
AUDIO_PATH = os.environ.get("AUDIO_PATH", None)

ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg']
EXT_PRIORITY = {'.mp3': 1, '.mp4': 2, '.ogg': 3}

def sort_key(title):
    return (not re.match(r'^[A-Za-z]', title), title.lower())

def is_allowed_extension(filename):
    return any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS)

def is_valid_audiofile(filename):
    if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        return False

    try:
        with open(filename, 'rb') as f:
            header = f.read(4)
            if header.startswith(b'ID3'):
                return True
            elif header.startswith(b'OggS'):
                return True
            elif header[0:4] == b'ftyp':
                return True
            elif filename.endswith('.mid'):
                return True
    except Exception as e:
        print(f"Error reading file {filename}: {e}")
        return False

    return False

@app.route("/playcard")
@limiter.limit("100 per minute")
def playcard():
    if AUDIO_PATH is None:
        return "Server not configured. Please set AUDIO_PATH as an environment variable.", 500

    title = os.path.basename(request.args.get("title", "")).strip()
    raw_title = request.args.get("title", "").strip()

    if raw_title.startswith("http"):
        parsed = urlparse(raw_title)
        title_with_ext = os.path.basename(parsed.path)
    else:
        title_with_ext = os.path.basename(raw_title)

    title, ext_from_title = os.path.splitext(title_with_ext)
    requested_ext = request.args.get('ext')

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
            if ext in ALLOWED_EXTENSIONS:
                if base not in titles or EXT_PRIORITY[ext] < EXT_PRIORITY[titles[base]]:
                    titles[base] = ext

        html = "<html><head><title>Available Titles</title></head><body background=\"https://jaquearnoux.de/radio.png\"><h1>Select a title</h1><ul>"
        for base in sorted(titles.keys(), key=sort_key):
            ext = titles[base]
            html += f'<li><a href="/playcard?title={base}&ext={ext[1:]}">{base} ({ext[1:]})</a></li>'
        html += "</ul></body></html>"

        return html

    file_path = None
    file_extension = None
    for ext in search_extensions:
        potential_file = os.path.join(AUDIO_PATH, title + ext)
        if os.path.exists(potential_file):
            file_path = os.path.normpath(potential_file)
            file_extension = ext
            break

    if not file_path or not file_path.startswith(os.path.abspath(AUDIO_PATH)):
        return abort(404, "File not found or access denied.")

    imgpath = os.path.join(AUDIO_PATH, f"{title}.jpeg")
    img_html = f'<img src="/media/{title}.jpeg" width="300"><br>' if os.path.isfile(imgpath) else ""

    media_url = f"/media/{title}{file_extension}"

    html = f"""<!DOCTYPE html>
<html prefix=\"og: http://ogp.me/ns#\">
  <head>
    <meta charset=\"utf-8\"><title>{title}</title>
    <meta property=\"og:audio\" content=\"https://example.com{media_url}\" />
    <meta property=\"og:audio:secure_url\" content=\"https://example.com{media_url}\" />
    <meta property=\"og:audio:type\" content=\"audio/{file_extension[1:]}\" />
    <meta property=\"og:type\" content=\"music\" />
    <meta property=\"og:video\" content=\"https://example.com{media_url}\">
    <meta property=\"og:video:secure_url\" content=\"https://example.com{media_url}\">
    <meta property=\"og:url\" content=\"https://example.com/playcard?title={title}\" />
    <meta property=\"og:title\" content=\"Jaque Arnoux Radio {title}\" />
    <meta property=\"og:image\" content=\"https://example.com/radio.png\" />
  </head>
  <body background=\"https://example.com/radio.png\">
    <audio controls autoplay>
      <source src=\"{media_url}\" type=\"audio/{file_extension[1:]}\">
      Your browser cannot play this audio.
    </audio>
    {img_html}
  </body>
</html>"""

    return html

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8010)
