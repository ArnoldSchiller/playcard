# Playcard Audio Server 🎵

**Dual-Engine Media Streaming** – Wähle zwischen einer einfachen PHP-Version oder einem leistungsfähigen Flask-Server für deine Audio/Video-Bibliothek.

![Demo](https://jaquearnoux.de/radio.png)

%%%bash
# Nach dem Kopieren ersetzen mit:
sed -i 's/%%%/```/g' README.md
%%%

## 📌 Kernfunktionen (beide Versionen)
- Stream **MP3, OGG, MP4, WebM** aus lokalen Ordnern
- Automatische Cover-Art-Erkennung (`track.jpg` für `track.mp3`)
- OpenGraph-Unterstützung für Social-Media-Vorschauen
- CLI-Modus (direkte Wiedergabe via Terminal)
- Strukturierte/Flache Ordneransicht
- Shuffle-Funktion für Zufallswiedergabe

## 🚀 Schnellstart
### **PHP-Version** (einfach)
%%%bash
git clone https://github.com/yourrepo/playcard-audio-server.git
cd playcard-audio-server
%%%

1. Konfiguriere `$MEDIA_DIRS` in `playcard.php`:
%%%php
$MEDIA_DIRS = ["/pfad/zu/musik", "/anderer/ordner"];
%%%

2. Aufruf im Browser:  
`http://deinserver/playcard.php`

### **Python/Flask-Version** (leistungsfähig)
%%%bash
pip install flask flask-limiter
export AUDIO_PATH="/pfad/zu/musik"
python3 playcard_server.py
%%%

→ Läuft standardmäßig auf `http://localhost:8010`

## 🔧 Vergleich der Versionen
| Feature               | PHP-Version          | Python/Flask-Version |
|-----------------------|----------------------|----------------------|
| **Installation**      | Nur PHP erforderlich | Python + Pip         |
| **Performance**       | Gut für kleine Bibliotheken | Optimiert für große Bibliotheken |
| **CLI-Player**        | `ffplay`-Integration | Benutzerdefinierbar |
| **Rate-Limiting**     | Nein                 | ✅ (100 Anfragen/Min) |
| **Proxy-Freundlich**  | Ja                   | Ja (mit HTTPS-Support) |
| **Systemd-Service**   | Manuell einrichten   | Integrierte Vorlage |

## 🌐 OpenGraph-Vorschau (beide)
%%%html
<meta property="og:audio" content="https://server/stream.mp3">
<meta property="og:image" content="https://server/cover.jpg">
%%%
*Perfekt für Discord/Telegram!*

## 🛡 Sicherheit
### PHP
- Beschränkt auf `$ALLOWED_EXTENSIONS`
- Kein Directory-Traversal möglich

### Python/Flask
- Zusätzlich:
  - Rate-Limiting via `flask-limiter`
  - Eingabe-Sanitisierung mit `os.path.basename`
  - Empfohlen: Hinter HTTPS-Reverse-Proxy betreiben

## 🐧 Systemd-Service (Flask)
%%%ini
[Unit]
Description=Playcard Flask Service
After=network.target

[Service]
User=www-data
ExecStart=/usr/bin/python3 /pfad/zu/playcard_server.py
Restart=always
Environment="AUDIO_PATH=/musik/pfad"
%%%
%%%bash
sudo systemctl enable playcard.service
%%%

## 🔄 Reverse-Proxy
### Apache (Auszug)
%%%apache
ProxyPass "/musik" "http://localhost:8010/musik"
ProxyPassReverse "/musik" "http://localhost:8010/musik"
%%%

### Nginx (Auszug)
%%%nginx
location /musik {
    proxy_pass http://127.0.0.1:8010;
}
%%%

## 📜 License
BSD 2-Clause License  
![License](https://img.shields.io/badge/license-BSD%202--Clause-blue.svg)


---

### Nach dem Kopieren:
1. Datei als `README.md` speichern
2. Backticks zurückersetzen mit:
%%%bash
sed -i 's/%%%/```/g' README.md
%%%
