#!/bin/bash
# DANIELSON Deployment Script
# Run on DANIELSON after SSH in: bash deploy.sh
#
# Prerequisites: Linux laptop with Coral M.2 TPU, 160GB HDD mounted at /mnt/nexus_data

set -e

echo "=========================================="
echo "  DANIELSON — Unified Scanner Deployment"
echo "=========================================="

# Check if running as the right user
USER=$(whoami)
echo "[INFO] Running as: $USER"
echo "[INFO] Hostname: $(hostname)"

# 1. System packages
echo ""
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip python3-venv \
    fswebcam v4l-utils \
    tesseract-ocr \
    libopencv-dev python3-opencv \
    libusb-1.0-0-dev \
    2>/dev/null

# 2. Coral Edge TPU runtime (if M.2 TPU present)
echo ""
echo "[2/7] Setting up Coral Edge TPU..."
if lspci | grep -qi "coral\|google\|edge tpu"; then
    echo "[OK] Coral M.2 TPU detected"
    # Add Coral repo if not present
    if ! dpkg -l | grep -q libedgetpu; then
        echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | \
            sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
        curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
        sudo apt-get update -qq
        sudo apt-get install -y -qq libedgetpu1-std
    fi
    echo "[OK] EdgeTPU runtime installed"
else
    echo "[WARN] Coral M.2 TPU not detected via lspci — will use CPU fallback"
fi

# 3. Python dependencies
echo ""
echo "[3/7] Installing Python packages..."
pip3 install --break-system-packages --quiet \
    flask \
    opencv-python-headless \
    numpy \
    requests \
    pyserial \
    pytesseract \
    tflite-runtime \
    faiss-cpu \
    2>/dev/null || pip3 install --quiet \
    flask opencv-python-headless numpy requests pyserial pytesseract tflite-runtime faiss-cpu

# 4. Create data directories on local SSD
echo ""
echo "[4/7] Setting up data directories..."
DATA_DIR="$HOME/danielson"
mkdir -p "$DATA_DIR"/{scans,cache,inventory,models/faiss_index,models/pokemon/faiss_index}
echo "[OK] Data directories at $DATA_DIR"

# 5. Copy server files
echo ""
echo "[5/7] Setting up DANIELSON server..."
INSTALL_DIR="$HOME/danielson"
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
mkdir -p "$INSTALL_DIR"

# Core server
cp danielson_server.py "$INSTALL_DIR/"
echo "[OK] danielson_server.py"

# nexus_auth pipeline (auth mode + NFT minter)
AUTH_DEST="$INSTALL_DIR/nexus_auth"
mkdir -p "$AUTH_DEST"
for f in auth_engine.py auth_ui.py item_types.py nft_minter.py __init__.py; do
    SRC="$REPO_ROOT/nexus_auth/$f"
    if [ -f "$SRC" ]; then
        cp "$SRC" "$AUTH_DEST/"
        echo "[OK] nexus_auth/$f"
    else
        echo "[WARN] nexus_auth/$f not found — skipping"
    fi
done

# Launchers
for launcher in launch_shop.py launch_venue.py; do
    SRC="$REPO_ROOT/$launcher"
    if [ -f "$SRC" ]; then
        cp "$SRC" "$INSTALL_DIR/"
        echo "[OK] $launcher"
    fi
done

# NFT Python deps (web3 optional)
echo "[INFO] Installing NFT minter deps (qrcode; web3 optional)..."
pip3 install --break-system-packages --quiet qrcode pillow 2>/dev/null
pip3 install --break-system-packages --quiet web3 2>/dev/null \
    && echo "[OK] web3 installed (live Polygon minting enabled)" \
    || echo "[INFO] web3 not installed — NFT mint will run in demo mode"

echo "[OK] Server installed to $INSTALL_DIR/"

# 6. Create systemd service
echo ""
echo "[6/7] Creating systemd service..."
sudo tee /etc/systemd/system/danielson.service > /dev/null << 'SVCEOF'
[Unit]
Description=DANIELSON Unified Scanner Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=DEPLOY_USER
WorkingDirectory=DEPLOY_HOME/danielson
ExecStart=/usr/bin/python3 DEPLOY_HOME/danielson/danielson_server.py
Restart=on-failure
RestartSec=5
Environment=DANIELSON_PORT=5001
Environment=ZULTAN_URL=http://192.168.1.152:8000
Environment=RELAY_URL=https://narwhal-council-relay.kcaracozza.workers.dev
Environment=NEXUS_DATA=DEPLOY_HOME/danielson
Environment=DANIELSON_ARM_PORT=/dev/ttyUSB0
Environment=DANIELSON_LIGHT_PORT=/dev/ttyUSB1
Environment=PYTHONPATH=DEPLOY_HOME/danielson

[Install]
WantedBy=multi-user.target
SVCEOF

# Replace placeholders with actual user
sudo sed -i "s|DEPLOY_USER|$USER|g" /etc/systemd/system/danielson.service
sudo sed -i "s|DEPLOY_HOME|$HOME|g" /etc/systemd/system/danielson.service

sudo systemctl daemon-reload
sudo systemctl enable danielson
sudo systemctl start danielson

echo ""
echo "=========================================="
echo "  DANIELSON DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
echo "  Server: http://$(hostname -I | awk '{print $1}'):5001"
echo "  Status: sudo systemctl status danielson"
echo "  Logs:   sudo journalctl -u danielson -f"
echo "  Stop:   sudo systemctl stop danielson"
echo ""

# 7. Touchscreen kiosk setup (7" scanner station display)
echo ""
echo "[7/7] Setting up touchscreen validator kiosk..."
sudo apt-get install -y -qq unclutter 2>/dev/null

# Copy validator files
VALIDATOR_DIR="$INSTALL_DIR/validator"
mkdir -p "$VALIDATOR_DIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCANNER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -f "$SCANNER_DIR/touch_validator.py" ]; then
    cp "$SCANNER_DIR/touch_validator.py" "$VALIDATOR_DIR/"
    cp "$SCANNER_DIR/start_validator.sh" "$VALIDATOR_DIR/"
    chmod +x "$VALIDATOR_DIR/start_validator.sh"
    echo "[OK] Validator files copied to $VALIDATOR_DIR/"
else
    echo "[WARN] touch_validator.py not found in $SCANNER_DIR — copy manually"
fi

# Create XDG autostart entry (Ubuntu Desktop / GNOME)
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/nexus-validator.desktop" << DSKEOF
[Desktop Entry]
Type=Application
Name=NEXUS Touch Validator
Comment=Proof of Presence kiosk on 7-inch touchscreen
Exec=$VALIDATOR_DIR/start_validator.sh
Hidden=false
X-GNOME-Autostart-enabled=true
DSKEOF
echo "[OK] Autostart entry created at $AUTOSTART_DIR/nexus-validator.desktop"
echo "     Disable with: rm $AUTOSTART_DIR/nexus-validator.desktop"

# Quick health check
sleep 2
if curl -s http://localhost:5001/health | grep -q "ok"; then
    echo ""
    echo "  [OK] DANIELSON is ONLINE"
else
    echo ""
    echo "  [WARN] Server may still be starting — check logs"
fi
