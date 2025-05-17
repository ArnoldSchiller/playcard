# Playcard Audio Server 🎵

**Dual-Engine Media Streaming** - Choose between a simple PHP version or a powerful Flask server for your audio/video library.


![Demo](playcard.png)



## 📌 Core functions (both versions)
- Stream **MP3, OGG, MP4, WebM** from local folders
- Automatic cover art detection (`track.jpg` for `track.mp3`)
- OpenGraph support for social media previews
- CLI mode (direct playback via terminal)
- Structured/flat folder view
- Shuffle function for random playback



## 🚀 Quick start
### **PHP-Version** (simple)
```bash
git clone https://github.com/ArnoldSchiller/playcard.git
cd playcard
```


1. configure `$MEDIA_DIRS` in `playcard.php`:
```php
$MEDIA_DIRS = ["/path/to/music", "/other/folder"];
````

2nd call in the browser: 
`http://deinserver/playcard.php`

### **Python/Flask version** (powerful)

### 1. Install requirements

```bash
pip install flask flask-limiter
export AUDIO_PATH="/pfad/zu/musik"
python3 playcard_server.py
```
Or via `apt` (recommended on Debian/Ubuntu):

```bash
sudo apt install python3-flask python3-flask-limiter
```

### 2. Set your audio path:

```bash
export AUDIO_PATH="/absolute/path/to/your/audio/files"
```

### 3. Run the server:

```
python3 playcard_server.py
```

By default the app runs on: `http://127.0.0.1:8010`

→ Runs on `http://localhost:8010` by default

## 🔧 Comparison of versions
| Feature | PHP version | Python/Flask version |
|-----------------------|----------------------|----------------------|
| **Installation** | PHP only required | Python + Pip |
| **Performance** | Good for small libraries | Optimized for large libraries |
| **CLI- Player** | `ffplay` integration | Customizable |
| **Rate limiting** | No | ✅ (100 requests/min) |
| **Proxy friendly** | Yes | Yes (with HTTPS support) |
| **Systemd service** | Set up manually | See template here in README |



## 🌐 OpenGraph-Vorschau (both)
```html
<meta property="og:audio" content="https://server/stream.mp3">
<meta property="og:image" content="https://server/cover.jpg">
```
*Perfect for Facebook/Discord/Telegram!*

## 🛡 Security
### PHP
- Restricted to `$ALLOWED_EXTENSIONS`
- No directory traversal possible

### Python/Flask
- Additionally:
  - Rate limiting via `flask-limiter`
  - Input sanitization with `os.path.basename`
  - Recommended: Run behind HTTPS reverse proxy


## 🐧 Systemd-Service (Flask)
```ini
[Unit]
Description=Playcard Flask Service
After=network.target

[Service]
User=www-data
ExecStart=/usr/bin/python3 /path/to/playcard_server.py
Restart=always
Environment="AUDIO_PATH=/music/path"
```

```bash
sudo systemctl enable playcard.service
```

## 🔄 Reverse-Proxy
### Apache (example)
```apache
ProxyPass "/music" "http://localhost:8010/music"
ProxyPassReverse "/music" "http://localhost:8010/music"
```

### Nginx (example)
```nginx
location /musik {
    proxy_pass http://127.0.0.1:8010;
}
```

## 📜 License
BSD 2-Clause License  
![License](https://img.shields.io/badge/license-BSD%202--Clause-blue.svg)

## Apache advanced configuration

Make sure that you have activated mod_proxy and mod_proxy_http. You can activate these modules, if they are not yet activated, with :
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
```


Add the following configuration to your Apache configuration file (usually in /etc/apache2/conf-available/playcard-proxy.conf or any other file you use) you can also use conf-available for a playcard-proxy.conf

```apache
# Example for Apache configuration


# Make sure that CGI is activated

<Directory “/usr/lib/cgi-bin”>

    AllowOverride None

    Options +ExecCGI

    AddHandler cgi-script .cgi .py

    Require all granted

</Directory>


# Example for proxy configuration

<IfModule mod_proxy.c>

    # Forward requests for /music/folder to the Flask server

    ProxyPass “/playcard” “http://127.0.0.1:8010/musik/playcard”

    ProxyPassReverse “/playcard” “http://127.0.0.1:8010/musik/playcard”

</IfModule>
```

```bash
sudo a2enmod playcard_proxy
sudo apache2 restart
```
## Nginx advanced configuration
Example configuration for Nginx:

If you are using Nginx, you can use the following configuration in your Nginx configuration file (/etc/nginx/sites-available/default or another file):

```nginx
# Example for Nginx configuration

server {
    listen 80;
    server_name yourdomain.com; # Replace with your actual domain name or IP address

    location /music/playcard {
        proxy_pass http://127.0.0.1:8010/musik/playcard; # Forward to the Flask server
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # **Your Audio Path Configuration** 
    # Replace the path with the path to your music folder, e.g. /var/www/html/music/ogg
    # Make sure that the Python server has access to this folder
}
```




## Remarks

### Environment variable for the audio path:
The path to the music file is set by AUDIO_PATH = os.environ.get("AUDIO_PATH", None). If this value is not set, the error "Server not configured. Please set AUDIO_PATH as an environment variable." is returned, informing the user that they must set the path.

### Allowed file extensions:
Only .mp3, .mp4 and .ogg are accepted as permitted audio formats. This ensures that no unwanted or dangerous file types are served.

### File and title matching:
The script checks whether the requested file exists in the specified AUDIO_PATH and whether it has the correct file extensions. If no file is specified, a list of available tracks is displayed.

### Open Graph (OG) meta tags:
When the page is shared on social media, OG metadata is included to create an engaging preview, including a cover image and audio file.

### Limiting:
The Flask Limiter extension ensures that the number of requests per IP address is limited to 100 per minute.

### File access check:
Checks whether the requested file actually exists in the specified directory and whether access to the file is allowed (avoiding security issues such as directory traversal).

## Further notes:

If you are using the script in a production environment, remember to take the appropriate security measures, e.g. enforce HTTPS, and make sure that sensitive data is not exposed in logs or error messages.

Secure it against cross-site scripting in Apache with mod_security.


---

