#!/bin/bash

# Universal Systemd Unit File Generator for Playcard Flask Service
# Supports: uWSGI (http), Gunicorn, Waitress, or fallback Flask
# Usage: ./create_playcard_service.sh [optional-path-to-app]

CLONE_DIR="${1:-$(pwd)}"
SCRIPT_NAME="playcard_server.py"
SCRIPT_PATH="${CLONE_DIR}/${SCRIPT_NAME}"
UWSGI_APP_FILE="/etc/uwsgi/apps-available/playcard.ini"
PORT=8010

# Path checks
if [ ! -d "$CLONE_DIR" ]; then
    echo "❌ Directory '$CLONE_DIR' does not exist" >&2
    exit 1
fi
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Script '$SCRIPT_NAME' not found in '$CLONE_DIR'" >&2
    exit 1
fi

# Owner info
SERVICE_USER=$(stat -c '%U' "$CLONE_DIR")
SERVICE_GROUP=$(stat -c '%G' "$CLONE_DIR")

# Detect WSGI options
AVAILABLE_SERVERS=()
command -v uwsgi >/dev/null && AVAILABLE_SERVERS+=("uwsgi")
command -v gunicorn >/dev/null && AVAILABLE_SERVERS+=("gunicorn")
command -v waitress-serve >/dev/null && AVAILABLE_SERVERS+=("waitress")
AVAILABLE_SERVERS+=("flask")

# Choose best available
SERVER_TYPE="${AVAILABLE_SERVERS[0]}"
echo -e "\n✅ Detected server: \033[1m$SERVER_TYPE\033[0m (based on availability: ${AVAILABLE_SERVERS[*]})"

# Service config
SERVICE_NAME="playcard-${SERVER_TYPE}.service"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}"
TMP_UNIT=$(mktemp /tmp/${SERVICE_NAME}.XXXXXX)

# Optional uWSGI config
if [[ "$SERVER_TYPE" == "uwsgi" ]]; then
    sudo mkdir -p /etc/uwsgi/apps-{available,enabled}
    TMP_INI=$(mktemp /tmp/playcard.ini.XXXXXX)
    cat > "$TMP_INI" <<EOF
[uwsgi]
module = playcard_server:app
http = 127.0.0.1:${PORT}
master = true
processes = 4
vacuum = true
die-on-term = true
plugins = python3
env = FLASK_ENV=production
EOF
    echo "📝 Created temporary uWSGI .ini config: $TMP_INI"
fi

# Generate systemd unit
case "$SERVER_TYPE" in
    uwsgi)
        EXEC_CMD="/usr/bin/uwsgi --ini ${UWSGI_APP_FILE}"
        ;;
    gunicorn)
        EXEC_CMD="/usr/bin/gunicorn -w 4 -b 127.0.0.1:${PORT} playcard_server:app"
        ;;
    waitress)
        EXEC_CMD="/usr/bin/waitress-serve --host=127.0.0.1 --port=${PORT} playcard_server:app"
        ;;
    flask|*)
        EXEC_CMD="/usr/bin/python3 ${SCRIPT_PATH}"
        ;;
esac

cat > "$TMP_UNIT" <<EOF
[Unit]
Description=Playcard ${SERVER_TYPE^} Service
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
Environment=FLASK_ENV=production
ExecStart=${EXEC_CMD}
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo -e "\n🧾 Generated systemd unit for \033[1m$SERVER_TYPE\033[0m:\n----------------------------------------"
cat "$TMP_UNIT"
echo "----------------------------------------"

# Prompt installation
read -p $'\nInstall and enable systemd service now? [y/N] ' -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n💡 Skipped installation. Generated files:"
    echo "Systemd unit: $TMP_UNIT"
    [[ "$SERVER_TYPE" == "uwsgi" ]] && echo "uWSGI config: $TMP_INI"
    exit 0
fi

# Move files
echo "🚀 Installing..."
sudo mv "$TMP_UNIT" "$UNIT_FILE"
sudo chmod 644 "$UNIT_FILE"

if [[ "$SERVER_TYPE" == "uwsgi" ]]; then
    sudo mv "$TMP_INI" "$UWSGI_APP_FILE"
    sudo ln -sf "$UWSGI_APP_FILE" /etc/uwsgi/apps-enabled/
fi

# Activate
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# Status output
echo -e "\n✅ \033[1mService ${SERVICE_NAME} installed and started!\033[0m"
echo "🔍 Check status: sudo systemctl status ${SERVICE_NAME}"
echo "🌐 App should be available on: http://127.0.0.1:${PORT}"

# Optional Apache Hint
echo -e "\n💡 To reverse proxy with Apache, use this config:"
cat <<EOF

<Location "/musik/playcard">
    ProxyPass "http://127.0.0.1:${PORT}"
    ProxyPassReverse "http://127.0.0.1:${PORT}"
    
</Location>

Enable required modules:
  sudo a2enmod proxy proxy_http
  sudo systemctl reload apache2
EOF

exit 0
