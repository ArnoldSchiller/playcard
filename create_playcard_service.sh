#!/bin/bash

# Systemd Unit File Generator for Playcard Flask Service
# Usage: ./create_playcard_service.sh [optional-path]

# Determine clone directory (default to current directory)
CLONE_DIR="${1:-$(pwd)}"
SCRIPT_NAME="playcard_server.py"
SCRIPT_PATH="${CLONE_DIR}/${SCRIPT_NAME}"

# Verify paths
if [ ! -d "$CLONE_DIR" ]; then
    echo "Error: Directory '$CLONE_DIR' does not exist" >&2
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script '$SCRIPT_NAME' not found in '$CLONE_DIR'" >&2
    exit 1
fi

# Get ownership info
SERVICE_USER=$(stat -c '%U' "$CLONE_DIR")
SERVICE_GROUP=$(stat -c '%G' "$CLONE_DIR")

# Service configuration
SERVICE_NAME="playcard.service"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}"
TEMP_FILE=$(mktemp /tmp/${SERVICE_NAME}.XXXXXX)

# Generate unit file
cat > "$TEMP_FILE" <<EOF
[Unit]
Description=Playcard Flask Service (${CLONE_DIR})
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${CLONE_DIR}
ExecStart=/usr/bin/python3 ${SCRIPT_PATH}
Restart=always
RestartSec=3
Environment="FLASK_ENV=production"

[Install]
WantedBy=multi-user.target
EOF

# Display configuration
echo -e "\n\033[1mGenerated systemd configuration:\033[0m"
echo "----------------------------------------"
cat "$TEMP_FILE"
echo "----------------------------------------"

# Installation prompt
read -p $'\nInstall as system service? [y/N] ' -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\nService file saved to: \033[34m${TEMP_FILE}\033[0m"
    echo "To install manually:"
    echo "  sudo mv \"${TEMP_FILE}\" \"${UNIT_FILE}\""
    echo "  sudo systemctl daemon-reload"
    exit 0
fi

# Install service
echo -e "\n\033[1mInstalling service...\033[0m"
if ! sudo mv "$TEMP_FILE" "$UNIT_FILE" 2>/dev/null; then
    echo -e "\033[31mError: Installation failed (sudo required)\033[0m" >&2
    exit 1
fi

sudo chmod 644 "$UNIT_FILE"
echo -e "Service installed to: \033[34m${UNIT_FILE}\033[0m"

# Service activation
read -p $'\nEnable and start service now? [Y/n] ' -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl start "$SERVICE_NAME"
    echo -e "\n\033[32mService activated!\033[0m"
    echo "Check status with: systemctl status ${SERVICE_NAME}"
else
    echo -e "\nYou can manage the service later with:"
    echo "  sudo systemctl start|stop|restart ${SERVICE_NAME}"
fi
