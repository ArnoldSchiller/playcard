# 🎵 Playcard Audio Server

A lightweight Flask web app to browse and stream `.mp3`, `.ogg`, `.mp4` audio files from a local folder.  
Supports OpenGraph previews (ideal for Discord, Telegram, etc.).

## ✨ Features

- Browse and play audio files from a specified directory
- Auto-generated player pages with OpenGraph metadata
- Social-media-ready previews (og:image, og:title, og:audio)
- Built-in rate limiting (100 req/min per IP)
- Unicode-safe, locale-aware filename sorting
- Minimal dependencies, runs with a single script

## 🚀 Quick Start

1. Install Python dependencies:

```
pip install flask flask-limiter
```

2. Set your audio path:

```
export AUDIO_PATH="/absolute/path/to/your/audio/files"
```

3. Run the server:

```
python playcard_server.py
```

By default the app runs on: `http://127.0.0.1:8010`

---

## 📂 Accessing Music

- Browse all tracks:  
  `http://localhost:8010/music/playcard`

- Direct play (example):  
  `http://localhost:8010/music/playcard?title=yourfile&ext=mp3`

- If a cover image named `yourfile.jpg` exists, it will be used for previews.

---

## 🌐 OpenGraph Preview Example

When shared on platforms like Discord:

```html
<meta property="og:title" content="Track Title">
<meta property="og:audio" content="https://yourdomain.com/music/playcard?...">
<meta property="og:image" content="https://yourdomain.com/path/to/cover.jpg">
```

---

## 🔐 Security Notes

- Rate limited (100 requests/minute per IP)
- Input sanitized via `os.path.basename`
- Only .mp3, .ogg, .mp4 served
- No directory traversal possible
- Files must exist inside `AUDIO_PATH`

---

## 🔧 Configuration

Either:

- Set `AUDIO_PATH` as environment variable  
  or
- Modify `MEDIA_DIRS` list directly in `playcard_server.py`

---

## 📦 Deployment Options

### Systemd Unit

Example: `/etc/systemd/system/playcard.service`

```
[Unit]
Description=Playcard Flask Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/usr/lib/cgi-bin
ExecStart=/usr/bin/python3 /usr/lib/cgi-bin/playcard_server.py
Restart=always
Environment="FLASK_ENV=production"

[Install]
WantedBy=multi-user.target
```

Then:

```
sudo systemctl daemon-reload
sudo systemctl enable playcard.service
sudo systemctl start playcard.service
```

---

## 🌐 Reverse Proxy

### Apache config (excerpt)

```
sudo a2enmod proxy
sudo a2enmod proxy_http
```

```
<IfModule mod_proxy.c>
  ProxyPass "/playcard" "http://127.0.0.1:8010/playcard"
  ProxyPassReverse "/playcard" "http://127.0.0.1:8010/playcard"
</IfModule>
```

### Nginx config (excerpt)

```
location /music/playcard {
    proxy_pass http://127.0.0.1:8010/music/playcard;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

---

## 📜 License

BSD 2-Clause License  
See [LICENSE](LICENSE) for details.

![License](https://img.shields.io/badge/license-BSD%202--Clause-blue.svg)

---


