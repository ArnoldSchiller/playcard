🎵 Playcard Audio Server

This is a minimal Flask-based audio file server that provides a basic HTML5 interface for playing audio via URLs. It also offers Open Graph (OG) metadata for integration in platforms like Discord or Facebook.
🚀 Features

    Streams .mp3, .ogg, .mp4 audio files

    Auto-generates an audio player page with <audio> tag

    Displays available tracks if no specific title is requested

    Includes basic Open Graph metadata for previews

    Optional cover image display (title.jpeg)

    Secure extension filtering

    Rate limiting via Flask-Limiter

⚠️ Disclaimer

This script does not include full security hardening and is provided for educational or internal use. If exposed publicly, make sure to:

    Use HTTPS

    Harden headers via your reverse proxy or WSGI server

    Protect media files from unwanted access

    Sanitize inputs further (especially if allowing uploads)

🧠 Requirements

    Python 3.7+

    Flask

    Flask-Limiter

Install dependencies with:

pip install flask flask-limiter

🔧 Configuration

Open playcard_server.py and set your audio directory:

AUDIO_PATH = "/absolute/path/to/your/audio/files"

Make sure the folder contains audio files with these extensions: .mp3, .ogg, or .mp4. Filenames must be safe (no ../ or dangerous characters).
🖥️ Running the Server

python playcard_server.py

By default, the server runs at http://127.0.0.1:8010.
📂 Accessing Audio

You can:

    View available tracks:
    http://localhost:8010/musik/playcard

    Play a specific file:
    http://localhost:8010/musik/playcard?title=yourfilename&ext=mp3

If a cover image yourfilename.jpeg exists in the same folder, it will be displayed.
🌐 Open Graph Metadata

When shared, the player page embeds metadata like:

<meta property="og:audio" content="...">
<meta property="og:title" content="...">
<meta property="og:image" content="...">

Useful for social media previews!
🛡 Security Notes

    Requests are limited to 100/minute by IP.

    Only files in the allowed folder are served.

    All inputs are sanitized with os.path.basename.

    File headers are validated (MP3 ID3, OGG, MP4, etc.).

🧾 License

MIT © Arnold Schiller
Feel free to fork and adapt.
