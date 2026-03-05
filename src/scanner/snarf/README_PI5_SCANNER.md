# NEXUS Pi5 Scanner - Deployment Guide

## Overview
Universal card scanner for Raspberry Pi 5 with multi-camera support, hardware control, and OCR integration.

**Patent Pending** - Filed Nov 27, 2025 by Kevin Caracozza

## Hardware Setup

### Cameras
- **OwlEye 64MP** (CSI) - High-resolution scanning, grading
- **CZUR Scanner** (USB) - Bulk document scanning
- **USB Webcam** - Motion detection, monitoring

### Controllers
- **ESP32** (`/dev/ttyUSB0`) - Lightbox, logo ring, servos, relay
- **Arduino Micro** (`/dev/ttyACM0`) - 3x scanner ring LEDs

## Quick Start

### 1. Deploy to Pi5

```bash
# Copy files to Pi
scp nexus_pi5_scanner.py deploy_pi5_scanner.sh nexus1@192.168.1.174:~

# SSH to Pi
ssh nexus1@192.168.1.174

# Run deployment
chmod +x deploy_pi5_scanner.sh
sudo ./deploy_pi5_scanner.sh
```

### 2. Start Scanner

```bash
# Start as service
sudo systemctl start nexus_scanner

# Enable on boot
sudo systemctl enable nexus_scanner

# Check status
sudo systemctl status nexus_scanner
```

### 3. Test Scanner

```bash
# Health check
curl http://192.168.1.174:5001/health

# Get status
curl http://192.168.1.174:5001/api/status

# Scan a card
curl -X POST http://192.168.1.174:5001/api/scan \
  -H "Content-Type: application/json" \
  -d '{"camera": "owleye", "mode": "ocr"}'
```

## Usage Modes

### 1. Server Mode (Default for deployment)
```bash
python3 nexus_pi5_scanner.py --server
```
Runs Flask API server on port 5001.

### 2. Interactive Mode (Testing)
```bash
python3 nexus_pi5_scanner.py --interactive
```
Commands:
- `scan` - Single card scan
- `multi` - Multi-pass scan protocol
- `lights` - Change lighting profile
- `status` - Show scanner status
- `quit` - Exit

### 3. Single Scan Mode
```bash
python3 nexus_pi5_scanner.py
```
Scans one card and exits.

## API Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "scanner_initialized": true,
  "cameras": ["owleye", "czur", "webcam"],
  "timestamp": "2026-01-22T10:30:00"
}
```

### POST /api/scan
Scan a card with specified camera and mode.

**Request:**
```json
{
  "camera": "owleye",
  "mode": "ocr"
}
```

**Response:**
```json
{
  "success": true,
  "scan_id": 1,
  "filename": "scan_20260122_103000_owleye_ocr.jpg",
  "filepath": "/home/nexus1/scans/scan_20260122_103000_owleye_ocr.jpg",
  "camera": "owleye",
  "mode": "ocr",
  "ocr": {
    "name": "Lightning Bolt",
    "set": "LEA",
    "confidence": 98.5
  }
}
```

### POST /api/multi_scan
Execute multi-pass scan protocol (motion, back, flat, surface, foil).

**Response:**
```json
{
  "motion": {...},
  "back": {...},
  "flat": {...},
  "surface": {...},
  "foil": {...},
  "best_result": {...}
}
```

### POST /api/lights
Control lighting system.

**Request (profile):**
```json
{
  "profile": "ocr"
}
```

Profiles: `ocr`, `grading`, `foil`, `off`

**Request (custom):**
```json
{
  "lightbox": {
    "r": 255,
    "g": 255,
    "b": 255,
    "w": 200
  }
}
```

### GET /api/capture/{camera}
Capture raw image without processing.

Returns JPEG image.

### GET /api/status
Get scanner status.

**Response:**
```json
{
  "initialized": true,
  "scan_count": 42,
  "cameras": ["owleye", "czur", "webcam"],
  "esp32_connected": true,
  "arduino_connected": true,
  "brok_url": "http://192.168.1.174:5000"
}
```

## Configuration

### Environment Variables
```bash
NEXUS_BROK_URL=http://192.168.1.174:5000
SCANNER_HOST=0.0.0.0
SCANNER_PORT=5001
ESP32_PORT=/dev/ttyUSB0
ARDUINO_PORT=/dev/ttyACM0
SCAN_DIR=/home/nexus1/scans
CACHE_DIR=/home/nexus1/cache
CONFIG_FILE=/home/nexus1/scanner_config.json
```

### Config File (scanner_config.json)
```json
{
  "brok_url": "http://192.168.1.174:5000",
  "server_port": 5001,
  "esp32_port": "/dev/ttyUSB0",
  "arduino_port": "/dev/ttyACM0",
  "owleye_index": 0,
  "czur_index": 10,
  "webcam_index": 8,
  "scan_dir": "/home/nexus1/scans"
}
```

## Camera Setup

### Check Available Cameras
```bash
v4l2-ctl --list-devices
```

Typical mapping:
- `/dev/video0-7` - CSI cameras (OwlEye)
- `/dev/video8-9` - HD Webcam
- `/dev/video10-11` - CZUR Scanner

### Test Camera
```bash
# OwlEye CSI
libcamera-still -o test_owleye.jpg

# USB camera
ffmpeg -f v4l2 -i /dev/video10 -frames 1 test_czur.jpg
```

## Hardware Control

### ESP32 Commands
- `LIGHT:r,g,b,w` - Set lightbox RGBW
- `LOGO:r,g,b` - Set logo ring RGB
- `SERVO:channel,angle` - Set servo position (0-180)
- `RELAY:state` - Set relay (0/1)

### Arduino Commands
- `RING:id,r,g,b` - Set ring color (id: 0-2)
- `ALL:r,g,b` - Set all rings

## Troubleshooting

### No Cameras Found
```bash
# Check camera modules
vcgencmd get_camera

# Check USB cameras
lsusb

# List all video devices
ls -la /dev/video*
```

### Serial Port Issues
```bash
# List serial devices
ls -la /dev/ttyUSB* /dev/ttyACM*

# Check permissions
sudo usermod -a -G dialout $USER
sudo usermod -a -G video $USER

# Test serial port
sudo minicom -D /dev/ttyUSB0 -b 115200
```

### Service Won't Start
```bash
# Check logs
sudo journalctl -u nexus_scanner -f

# Test manually
python3 /home/nexus1/nexus_scanner/nexus_pi5_scanner.py --interactive

# Check config
cat /home/nexus1/scanner_config.json
```

### Network Issues
```bash
# Check network
ip addr show

# Test Brok connection
curl http://192.168.1.174:5000/health

# Test local scanner
curl http://localhost:5001/health
```

## Deployment Targets

### Brok (192.168.1.174)
- OCR processing server
- OwlEye 64MP for card back detection
- Coral TPU for AI acceleration

### Snarf (192.168.1.172)
- Hardware control server
- OwlEye 64MP for grading/scanning
- CZUR for bulk scanning
- Webcam for monitoring
- ESP32 + Arduino control

## Integration with NEXUS V2

The scanner integrates with the main NEXUS V2 application via:

1. **Scanner Client** ([nexus_v2/scanner/scanner_client.py](E:\NEXUS_V2_RECREATED\nexus_v2\scanner\scanner_client.py))
2. **Hardware Scanner Tab** ([nexus_v2/ui/tabs/hardware_scanner.py](E:\NEXUS_V2_RECREATED\nexus_v2\ui\tabs\hardware_scanner.py))
3. **Collection Tab** for viewing scanned cards

## Files
- `nexus_pi5_scanner.py` - Main scanner implementation
- `deploy_pi5_scanner.sh` - Deployment script
- `scanner_config.json` - Configuration file
- `nexus_scanner.service` - Systemd service

## License
Copyright 2025-2026 Kevin Caracozza - All Rights Reserved
Patent Filed: November 27, 2025
