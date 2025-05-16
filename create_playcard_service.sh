#!/bin/bash

# Systemd Unit File Generator for Playcard Flask Service
# Usage: ./create_playcard_service.sh [optional-path]

# Determine clone directory (default to current directory if no argument)
CLONE_DIR="${1:-$(pwd)}"
SCRIPT_NAME="playcard_server.py"
SCRIPT_PATH="$CLONE_DIR/$SCRIPT_NAME"

# Verify directory and script exist
if [ ! -d "$CLONE_DIR" ]; then
    echo "Error: Directory $CLONE_DIR does not exist" >&2
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script $SCRIPT_NAME not found in $CLONE_DIR" >&2
    exit 1
fi

# Get owner and group of the directory
SERVICE_USER=$(stat -c '%U' "$CLONE_DIR")
SERVICE_GROUP=$(stat -c '%G' "$CLONE_DIR")

# Use simple service name
SERVICE_NAME="playcard.service"
UNIT_FILE="/etc/systemd/system/$SERVICE_NAME"
TEMP_FILE="/tmp/$SERVICE_NAME"

# Create the unit file template
cat > "$TEMP_FILE" <<EOF
[Unit]
Description=Playcard Flask Service ($CLONE_DIR)
After=network.target

[Service]
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$CLONE_DIR
ExecStart=/usr/bin/python3 $SCRIPT_PATH
Restart=always
RestartSec=3
Environment="FLASK_ENV=production"

[Install]
WantedBy=multi-user.target
EOF

# Show generated configuration
echo "Generated systemd configuration:"
echo "--------------------------------"
cat "$TEMP_FILE"
echo "--------------------------------"

# Ask about installation
read -p "Do you want to install this as a system service? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Service file saved to $TEMP_FILE"
    echo "You can manually install it later with:"
    echo "  sudo mv $TEMP_FILE $UNIT_FILE"
    echo "  sudo systemctl daemon-reload"
    exit 0
fi

# Installation requires sudo
echo "Installing service requires sudo privileges..."
if ! sudo -v; then
    echo "Error: Failed to get sudo privileges" >&2
    exit 1
fi

sudo mv "$TEMP_FILE" "$UNIT_FILE" && \
sudo chmod 644 "$UNIT_FILE" && \
echo "Successfully installed service unit to $UNIT_FILE"

# Ask about enabling
read -p "Do you want to enable and start the service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl daemon-reload && \
    sudo systemctl enable "$SERVICE_NAME" && \
    sudo systemctl start "$SERVICE_NAME" && \
    echo "Service enabled and started. Check status with: systemctl status $SERVICE_NAME"
else
    echo "You can manually enable/start later with:"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable $SERVICE_NAME"
    echo "  sudo systemctl start $SERVICE_NAME"
fi
