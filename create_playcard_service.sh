#!/bin/bash

# Smart Systemd Service Installer for Playcard
# Supports flask, gunicorn, waitress, uwsgi – fallback-safe
# DAU-freundlich + root-ready

CLONE_DIR="${1:-$(pwd)}"
SCRIPT_NAME="playcard_server.py"
SCRIPT_PATH="${CLONE_DIR}/${SCRIPT_NAME}"

# Pfadprüfung
if [ ! -d "$CLONE_DIR" ]; then
    echo "Error: Directory '$CLONE_DIR' does not exist." >&2
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script '$SCRIPT_NAME' not found in '$CLONE_DIR'." >&2
    exit 1
fi

# User/Group
SERVICE_USER=$(stat -c '%U' "$CLONE_DIR")
SERVICE_GROUP=$(stat -c '%G' "$CLONE_DIR")

# Server-Erkennung
EXEC_CMD=""
SERVER_TYPE=""
cd "$CLONE_DIR" || exit 1

if command -v gunicorn >/dev/null && grep -q 'Flask' "$SCRIPT_PATH"; then
    EXEC_CMD="gunicorn -b 127.0.0.1:8010 playcard_server:app"
    SERVER_TYPE="gunicorn"
elif command -v waitress-serve >/dev/null; then
    EXEC_CMD="waitress-serve --host=127.0.0.1 --port=8010 playcard_server:app"
    SERVER_TYPE="waitress"
elif command -v uwsgi >/dev/null; then
    EXEC_CMD="uwsgi --http 127.0.0.1:8010 --wsgi-file playcard_server.py --callable app"
    SERVER_TYPE="uwsgi"
else
    EXEC_CMD="/usr/bin/python3 ${SCRIPT_PATH}"
    SERVER_TYPE="flask"
fi

# Unit-Datei
SERVICE_NAME="playcard-${SERVER_TYPE}.service"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}"
TMP_UNIT=$(mktemp "/tmp/${SERVICE_NAME}.XXXXXX")

cat > "$TMP_UNIT" <<EOF
[Unit]
Description=Playcard ${SERVER_TYPE^} Service
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
ExecStart=${EXEC_CMD}
Restart=always
RestartSec=3
EOF

# Nur bei Flask ENV setzen
if [ "$SERVER_TYPE" = "flask" ]; then
    echo 'Environment="FLASK_ENV=production"' >> "$TMP_UNIT"
fi

cat >> "$TMP_UNIT" <<EOF

[Install]
WantedBy=multi-user.target
EOF

# Ausgabe
echo -e "\n\033[1mGenerated systemd unit:\033[0m"
echo "----------------------------------------"
cat "$TMP_UNIT"
echo "----------------------------------------"
echo -e "\nTemporary file: \033[34m${TMP_UNIT}\033[0m"

# Entscheidung
read -p $'\nInstall and enable systemd service now? [y/N] ' -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\nTo install manually:"
    echo "  sudo mv \"${TMP_UNIT}\" \"${UNIT_FILE}\""
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable \"${SERVICE_NAME}\""
    echo "  sudo systemctl start \"${SERVICE_NAME}\""
    echo -e "\n\033[32mGive these steps to your admin if needed.\033[0m"
    exit 0
fi

# Installationsteil (erst ab hier sudo)
echo -e "\n\033[1mInstalling service as root...\033[0m"
if ! sudo mv "$TMP_UNIT" "$UNIT_FILE"; then
    echo -e "\033[31mError: sudo failed – not installed.\033[0m" >&2
    echo "Temp file remains at: $TMP_UNIT"
    exit 1
fi

sudo chmod 644 "$UNIT_FILE"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo -e "\n\033[32mService installed and started: ${SERVICE_NAME}\033[0m"
echo "Check: sudo systemctl status ${SERVICE_NAME}"
