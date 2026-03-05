#!/bin/bash
# NEXUS Pi5 Scanner Deployment Script
# Deploy to: Brok (192.168.1.174) or Snarf (192.168.1.172)

set -e  # Exit on error

echo "=== NEXUS Pi5 Scanner Deployment ==="
echo ""

# Check if running on Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "WARNING: Not running on Raspberry Pi"
fi

# Configuration
PI_USER=${NEXUS_USER:-nexus1}
INSTALL_DIR="/home/$PI_USER/nexus_scanner"
CONFIG_DIR="/home/$PI_USER"
SCAN_DIR="/home/$PI_USER/scans"
CACHE_DIR="/home/$PI_USER/cache"

echo "Installation directory: $INSTALL_DIR"
echo "User: $PI_USER"
echo ""

# Create directories
echo "Creating directories..."
sudo -u $PI_USER mkdir -p "$INSTALL_DIR"
sudo -u $PI_USER mkdir -p "$SCAN_DIR"
sudo -u $PI_USER mkdir -p "$CACHE_DIR"

# Install dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-opencv \
    python3-serial \
    python3-flask \
    python3-numpy \
    python3-picamera2 \
    libcamera-apps \
    v4l-utils

echo "Installing Python packages..."
sudo -u $PI_USER pip3 install --break-system-packages \
    opencv-python \
    pyserial \
    flask \
    requests \
    numpy \
    picamera2

# Copy scanner script
echo "Copying scanner script..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
sudo -u $PI_USER cp "$SCRIPT_DIR/nexus_pi5_scanner.py" "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/nexus_pi5_scanner.py"

# Create systemd service
echo "Creating systemd service..."
cat > /tmp/nexus_scanner.service <<EOF
[Unit]
Description=NEXUS Pi5 Scanner Server
After=network.target

[Service]
Type=simple
User=$PI_USER
WorkingDirectory=$INSTALL_DIR
Environment="NEXUS_BROK_URL=http://192.168.1.174:5000"
Environment="SCANNER_PORT=5001"
Environment="SCAN_DIR=$SCAN_DIR"
Environment="CACHE_DIR=$CACHE_DIR"
ExecStart=/usr/bin/python3 $INSTALL_DIR/nexus_pi5_scanner.py --server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/nexus_scanner.service /etc/systemd/system/
sudo systemctl daemon-reload

# Create default config
echo "Creating default configuration..."
cat > "$CONFIG_DIR/scanner_config.json" <<EOF
{
    "brok_url": "http://192.168.1.174:5000",
    "server_host": "0.0.0.0",
    "server_port": 5001,
    "esp32_port": "/dev/ttyUSB0",
    "arduino_port": "/dev/ttyACM0",
    "owleye_index": 0,
    "czur_index": 10,
    "webcam_index": 8,
    "scan_dir": "$SCAN_DIR",
    "cache_dir": "$CACHE_DIR"
}
EOF
sudo chown $PI_USER:$PI_USER "$CONFIG_DIR/scanner_config.json"

# Set serial permissions
echo "Setting serial port permissions..."
sudo usermod -a -G dialout $PI_USER
sudo usermod -a -G video $PI_USER

# List available cameras
echo ""
echo "=== Available Cameras ==="
v4l2-ctl --list-devices

# List serial ports
echo ""
echo "=== Available Serial Ports ==="
ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No serial devices found"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Start scanner server:"
echo "  sudo systemctl start nexus_scanner"
echo ""
echo "Enable on boot:"
echo "  sudo systemctl enable nexus_scanner"
echo ""
echo "View logs:"
echo "  sudo journalctl -u nexus_scanner -f"
echo ""
echo "Test manually:"
echo "  python3 $INSTALL_DIR/nexus_pi5_scanner.py --interactive"
echo ""
echo "API Endpoints:"
echo "  http://localhost:5001/health"
echo "  http://localhost:5001/api/scan"
echo "  http://localhost:5001/api/status"
echo ""
