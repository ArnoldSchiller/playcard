#!/bin/bash

# Systemd Unit File Generator for Playcard Service (Dry-Run First)
# Version 3.0 - Fully DAU-safe, sudo-free dry run with full output preview

# Default values
CLONE_DIR="${1:-$(pwd)}"
SCRIPT_NAME="playcard_server.py"
SCRIPT_PATH="${CLONE_DIR}/${SCRIPT_NAME}"
PORT=8010

# Check clone directory
if [ ! -d "$CLONE_DIR" ]; then
    echo "Error: Directory '$CLONE_DIR' does not exist" >&2
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script '$SCRIPT_NAME' not found in '$CLONE_DIR'" >&2
    exit 1
fi

# Determine service ownership
SERVICE_USER=$(stat -c '%U' "$CLONE_DIR")
SERVICE_GROUP=$(stat -c '%G' "$CLONE_DIR")

# Detect server options
AVAILABLE_SERVERS=( )
command -v uwsgi >/dev/null && AVAILABLE_SERVERS+=("uwsgi" "uwsgi-http")
command -v gunicorn >/dev/null && AVAILABLE_SERVERS+=("gunicorn")
command -v waitress-serve >/dev/null && AVAILABLE_SERVERS+=("waitress")
AVAILABLE_SERVERS+=("flask")

# Let user select server type
echo -e "\nAvailable server types:"
select SERVER_TYPE in "${AVAILABLE_SERVERS[@]}"; do
    [[ -n "$SERVER_TYPE" ]] && break
    echo "Invalid choice, please select a valid number."
done

# Create file paths
SERVICE_NAME="playcard-${SERVER_TYPE}.service"
UNIT_FILE_TMP="/tmp/${SERVICE_NAME}"
UWSGI_INI_TMP="/tmp/playcard.ini"

# Generate service content
case "$SERVER_TYPE" in
    uwsgi)
        cat > "$UWSGI_INI_TMP" <<EOF
[uwsgi]
module = playcard_server:app
master = true
processes = 4
socket = 127.0.0.1:${PORT}
chmod-socket = 660
vacuum = true
die-on-term = true
plugins = python3
env = FLASK_ENV=production
EOF

        cat > "$UNIT_FILE_TMP" <<EOF
[Unit]
Description=Playcard uWSGI Service
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
ExecStart=/usr/bin/uwsgi --ini /etc/uwsgi/apps-available/playcard.ini
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
        ;;
    uwsgi-http)
        cat > "$UWSGI_INI_TMP" <<EOF
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

        cat > "$UNIT_FILE_TMP" <<EOF
[Unit]
Description=Playcard uWSGI Service (uwsgi-http)
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
ExecStart=/usr/bin/uwsgi --ini /etc/uwsgi/apps-available/playcard.ini
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
        ;;
    gunicorn)
        cat > "$UNIT_FILE_TMP" <<EOF
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
        cat > "$UNIT_FILE_TMP" <<EOF
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
    flask|*)
        cat > "$UNIT_FILE_TMP" <<EOF
[Unit]
Description=Playcard Flask Development Service
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
Environment=FLASK_ENV=development
ExecStart=/usr/bin/python3 ${SCRIPT_PATH}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
        ;;
esac

# Display results
echo -e "\n\033[1mGenerated systemd service file:\033[0m"
echo "------------------------"
cat "$UNIT_FILE_TMP"
echo "------------------------"

if [[ "$SERVER_TYPE" == uwsgi* ]]; then
    echo -e "\n\033[1mGenerated uWSGI ini file:\033[0m"
    echo "------------------------"
    cat "$UWSGI_INI_TMP"
    echo "------------------------"
fi

# Output installation instructions
echo -e "\n\033[1mInstallation instructions:\033[0m"
echo "This was a dry-run. No system changes were made."
echo "To install this service as root, run the following commands:"
echo ""
echo "sudo mv $UNIT_FILE_TMP /etc/systemd/system/${SERVICE_NAME}"
[[ "$SERVER_TYPE" == uwsgi* ]] && echo "sudo mv $UWSGI_INI_TMP /etc/uwsgi/apps-available/playcard.ini"
[[ "$SERVER_TYPE" == uwsgi* ]] && echo "sudo ln -s /etc/uwsgi/apps-available/playcard.ini /etc/uwsgi/apps-enabled/"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl enable ${SERVICE_NAME}"
echo "sudo systemctl start ${SERVICE_NAME}"

echo -e "\n\033[32mDry run complete. No sudo required.\033[0m"

# Service activation
read -p $'\nEnable and start service now? [Y/n] ' -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "sudo mv $UNIT_FILE_TMP /etc/systemd/system/${SERVICE_NAME}"
[[ "$SERVER_TYPE" == uwsgi* ]] && echo "sudo mv $UWSGI_INI_TMP /etc/uwsgi/apps-available/playcard.ini"
[[ "$SERVER_TYPE" == uwsgi* ]] && echo "sudo ln -s /etc/uwsgi/apps-available/playcard.ini /etc/uwsgi/apps-enabled/"	
    echo sudo systemctl daemon-reload
    echo sudo systemctl enable "${SERVICE_NAME}"
    echo sudo systemctl start "${SERVICE_NAME}"
    sudo mv $UNIT_FILE_TMP /etc/systemd/system/${SERVICE_NAME}
[[ "$SERVER_TYPE" == uwsgi* ]] && sudo mv $UWSGI_INI_TMP /etc/uwsgi/apps-available/playcard.ini
[[ "$SERVER_TYPE" == uwsgi* ]] && sudo ln -s /etc/uwsgi/apps-available/playcard.ini /etc/uwsgi/apps-enabled/	
    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
    sudo systemctl start "${SERVICE_NAME}"
    echo -e "\n\033[32mService activated!\033[0m"
    echo "Check status with: systemctl status ${SERVICE_NAME}"
	
else
    echo -e "\nYou can manage the service later with:"
    echo "  sudo systemctl start|stop|restart ${SERVICE_NAME}"
fi



exit 0
