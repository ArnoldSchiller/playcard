#!/bin/bash

# Systemd Unit File Generator for Playcard Service
# Supports uwsgi, uwsgi-http, gunicorn, waitress, flask
# DAU-kompatibel & interaktiv

CLONE_DIR="${1:-$(pwd)}"
SCRIPT_NAME="playcard_server.py"
SCRIPT_PATH="${CLONE_DIR}/${SCRIPT_NAME}"
PORT=8010

if [ ! -d "$CLONE_DIR" ]; then
    echo "Error: Directory '$CLONE_DIR' does not exist" >&2
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script '$SCRIPT_NAME' not found in '$CLONE_DIR'" >&2
    exit 1
fi

SERVICE_USER=$(stat -c '%U' "$CLONE_DIR")
SERVICE_GROUP=$(stat -c '%G' "$CLONE_DIR")

# Detect servers
AVAILABLE_SERVERS=()
if command -v uwsgi >/dev/null; then
    AVAILABLE_SERVERS+=("uwsgi" "uwsgi-http")
fi
if command -v gunicorn >/dev/null; then
    AVAILABLE_SERVERS+=("gunicorn")
fi
if command -v waitress-serve >/dev/null; then
    AVAILABLE_SERVERS+=("waitress")
fi
AVAILABLE_SERVERS+=("flask")

echo -e "\nAvailable server types:"
select SERVER_TYPE in "${AVAILABLE_SERVERS[@]}"; do
    [[ -n "$SERVER_TYPE" ]] && break
    echo "Invalid selection. Try again."
done

# Stop existing matching services (by name)
EXISTING=$(systemctl list-units --type=service --all | grep -o 'playcard[^ ]*.service' || true)
if [ -n "$EXISTING" ]; then
    echo -e "\n\033[33mStopping existing Playcard services...\033[0m"
    for svc in $EXISTING; do
        sudo systemctl stop "$svc"
    done
fi

# Free port if needed
if command -v lsof >/dev/null && lsof -i :$PORT >/dev/null; then
    echo -e "\n\033[33mPort $PORT is in use. Trying to free it...\033[0m"
    sudo kill -9 $(lsof -t -i :$PORT) 2>/dev/null || true
fi

SERVICE_NAME="playcard-${SERVER_TYPE}.service"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}"
TMP_UNIT=$(mktemp "/tmp/${SERVICE_NAME}.XXXXXX")

# uWSGI INI (only for uwsgi / uwsgi-http)
if [[ "$SERVER_TYPE" =~ ^uwsgi ]]; then
    TMP_INI=$(mktemp /tmp/playcard.uwsgi.XXXX.ini)
    UWSGI_APP_FILE="/etc/uwsgi/apps-available/playcard.ini"

    cat > "$TMP_INI" <<EOF
[uwsgi]
module = playcard_server:app
master = true
processes = 4
plugins = python3
vacuum = true
die-on-term = true
env = FLASK_ENV=production
EOF

    if [[ "$SERVER_TYPE" == "uwsgi" ]]; then
        echo "socket = 127.0.0.1:${PORT}" >> "$TMP_INI"
        echo "chmod-socket = 660" >> "$TMP_INI"
    else
        echo "http = 127.0.0.1:${PORT}" >> "$TMP_INI"
    fi
fi

# Generate unit
case $SERVER_TYPE in
    uwsgi|uwsgi-http)
        cat > "$TMP_UNIT" <<EOF
[Unit]
Description=Playcard uWSGI Service (${SERVER_TYPE})
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
ExecStart=/usr/bin/uwsgi --ini ${UWSGI_APP_FILE}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
        ;;
    gunicorn)
        cat > "$TMP_UNIT" <<EOF
[Unit]
Description=Playcard Gunicorn Service
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
Environment=FLASK_ENV=production
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:${PORT} playcard_server:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
        ;;
    waitress)
        cat > "$TMP_UNIT" <<EOF
[Unit]
Description=Playcard Waitress Service
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
Environment=FLASK_ENV=production
ExecStart=/usr/bin/waitress-serve --host=127.0.0.1 --port=${PORT} playcard_server:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
        ;;
    flask)
        cat > "$TMP_UNIT" <<EOF
[Unit]
Description=Playcard Flask Dev Service
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
Environment=FLASK_ENV=production
ExecStart=/usr/bin/python3 ${SCRIPT_PATH}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
        ;;
esac

# Show generated config
echo -e "\n\033[1mGenerated unit file:\033[0m"
cat "$TMP_UNIT"
[[ "$SERVER_TYPE" =~ ^uwsgi ]] && {
    echo -e "\n\033[1mGenerated uWSGI ini:\033[0m"
    cat "$TMP_INI"
}

# Confirm install
read -p $'\nInstall systemd service now? [y/N] ' -n 1 -r
echo
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Saved unit: $TMP_UNIT"
    [[ "$SERVER_TYPE" =~ ^uwsgi ]] && echo "uWSGI ini: $TMP_INI"
    echo "Install manually:"
    echo "  sudo mv \"$TMP_UNIT\" \"$UNIT_FILE\""
    [[ "$SERVER_TYPE" =~ ^uwsgi ]] && echo "  sudo mv \"$TMP_INI\" \"$UWSGI_APP_FILE\""
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable \"$SERVICE_NAME\""
    exit 0
fi

# Perform installation
echo -e "\nInstalling service..."
sudo mv "$TMP_UNIT" "$UNIT_FILE"
[[ "$SERVER_TYPE" =~ ^uwsgi ]] && {
    sudo mkdir -p /etc/uwsgi/apps-available /etc/uwsgi/apps-enabled
    sudo mv "$TMP_INI" "$UWSGI_APP_FILE"
    sudo ln -sf "$UWSGI_APP_FILE" /etc/uwsgi/apps-enabled/
}
sudo chmod 644 "$UNIT_FILE"

# Activate
read -p $'\nEnable and start service? [Y/n] ' -n 1 -r
echo
if [[ ! "$REPLY" =~ ^[Nn]$ ]]; then
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl start "$SERVICE_NAME"
    echo -e "\n\033[32mService started!\033[0m"
    sudo systemctl status "$SERVICE_NAME"
else
    echo "You can start it later with:"
    echo "  sudo systemctl start $SERVICE_NAME"
fi
