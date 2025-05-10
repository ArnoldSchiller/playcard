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
    http://localhost:8010/music/playcard

    Play a specific file:
    http://localhost:8010/music/playcard?title=yourfilename&ext=mp3

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


## Description
A lightweight server to play audio files via HTTP. Ideal for personal radio stations.

## License
This project is licensed under the BSD 2-Clause License - see the [LICENSE](LICENSE) file for details.

![License](https://img.shields.io/badge/license-BSD%202--Clause-blue.svg)

## Setup
Please set the `AUDIO_PATH` variable to the location of your music files before running the server.


```python
AUDIO_PATH = "/path/to/your/music/folder"
```


## Installation


Clone this repository.

Install the necessary dependencies.

pip install -r requirements.txt

Run the server:

    python playcard_server.py

    Visit http://127.0.0.1:8010 in your browser to access the server.


## Apache configuration

Make sure that you have activated mod_proxy and mod_proxy_http. You can activate these modules, if they are not yet activated, with :
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
```


Add the following configuration to your Apache configuration file (usually in /etc/apache2/sites-available/000-default.conf or any other file you use) you can also use conf-available for a playcard-proxy.conf

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

    ProxyPass “/playcard” “http://127.0.0.1:8010/playcard”

    ProxyPassReverse “/playcard” “http://127.0.0.1:8010/playcard”

</IfModule>


# **Your Audio Path Configuration** 

# Replace the path with the path to your music folder, e.g. /var/www/html/music/

# Make sure that the Python server has access to this folder

```

## Nginx configuration
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


## Important notes:

### Audio path:
Make sure the Python server has access to the music folder you specified in the AUDIO_PATH in your Python script. The Apache or Nginx server must also have access to this folder so that the files can be delivered correctly.

### Proxy configuration:
The Apache and Nginx configurations forward requests for /music/playcard to the local Flask server running at http://127.0.0.1:8010. If you change the port or address, make sure you adjust the configuration accordingly.

### Testing:
After the configuration, you can restart your Apache or Nginx server:

    sudo systemctl restart apache2
    sudo systemctl restart nginx

### Troubleshooting:
If you have problems loading the music files, check that the music files are in the correct folder and that the web server (Apache/Nginx) has the correct permissions to access this folder.

## Systemd configuration for the automatic start of the Playcard server

To ensure that the Flask server starts automatically when booting and runs in the background, you can create a Systemd service. Here is an example of a playcard.service file.
### Step 1: Create the systemd service file

Create a new service file for the Flask server:
```bash
sudo vi /etc/systemd/system/playcard.service
```
Add the following configuration to the file:
```ini
[Unit]
Description=Playcard Flask Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/usr/lib/cgi-bin
ExecStart=/usr/bin/python3 /usr/lib/cgi-bin/playcard_server.py
Restart=always
RestartSec=3
Environment="FLASK_ENV=production"

[Install]
WantedBy=multi-user.target
```
If /usr/lib/cgi-bin/playcard_server.py is not located there, adjust the path accordingly.

### Step 2: Reload the systemd services and start the service



After you have created the service file, you can reload the service and start the Flask server:
```bash
# Reload systemd services
sudo systemctl daemon-reload

# Start Flask server
sudo systemctl start playcard.service

# Configure Flask server to start on boot
sudo systemctl enable playcard.service
```
### Step 3: Checking the service status

You can check the status of the Flask server to ensure that the service is running correctly:
```bash
sudo systemctl status playcard.service
```
If the server is running successfully, you should see something like this

● playcard.service - Playcard Flask Service
 Loaded: loaded (/etc/systemd/system/playcard.service; enabled; vendor preset: enabled)
 Active: active (running) since <timestamp>; <time> ago
 Main PID: <PID> (python3)
 CGroup: /system.slice/playcard.service
 └─<PID> /usr/bin/python3 /usr/lib/cgi-bin/playcard_server.py

### Step 4: Troubleshooting

If the service does not start, you can view the logs with journalctl to detect possible errors:

```bash
sudo journalctl -u playcard.service
```
With these instructions, you can start the Playcard server automatically and ensure that it is running when the system boots.

If you still want to make adjustments to the configuration, such as the user or the path to your script, you can do this in the playcard.service file.
