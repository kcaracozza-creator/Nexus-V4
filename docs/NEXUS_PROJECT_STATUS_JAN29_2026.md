# NEXUS V3 - Universal Collectibles Platform
## Project Status: January 29, 2026

---

## EXECUTIVE SUMMARY

**NEXUS** is a universal collectibles management system for trading cards (MTG, Pokemon, Yu-Gi-Oh, Sports).

- **Patent Status:** Filed November 27, 2025 - Kevin Caracozza
- **Codebase:** 146 Python files, 17MB
- **UI Tabs:** 21 functional tabs
- **Hardware Servers:** 19 Pi server scripts

---

## HARDWARE INFRASTRUCTURE

### Network Topology

| Device | IP Address | Role | Hardware |
|--------|------------|------|----------|
| **Zultan** | 192.168.1.152:5000 | GPU Server, AI Training, Marketplace | RTX 3060 12GB, RX 590, 64GB RAM, Ubuntu 22.04 |
| **Brock** | 192.168.1.174:5000 | OCR, AI Learning, Coral TPU | Pi 5, 160GB HDD, OwlEye 64MP |
| **Snarf** | 192.168.1.172:5001 | Hardware Controller, Cameras | Pi 5, ESP32, Arduino Micro |
| **Surface** | 192.168.1.159 | Desktop Client | Windows, NEXUS V2 App |

### Camera Setup

| Location | Camera | Connection | Function |
|----------|--------|------------|----------|
| Snarf | OwlEye 64MP | CSI | Grading, single card high-res |
| Snarf | CZUR Scanner | USB | Bulk scanning |
| Snarf | Webcam | USB | Case video monitoring |
| Brock | OwlEye 64MP | CSI | Card back scanning (type detection) |

### Hardware Controllers (Snarf)

| Controller | Connection | Controls |
|------------|------------|----------|
| ESP32 | USB Serial | Lightbox LEDs (RGBW), Logo ring, PCA9685 servos, Relay |
| Arduino Micro | USB Serial | 3x Scanner ring LEDs (NeoPixel) |

### 5-DOF Robotic Arm

| Joint | Servo | Range | Function |
|-------|-------|-------|----------|
| J0 | Base | 0-180° | Rotation |
| J1 | Shoulder | 0-180° | Lift |
| J2 | Elbow | 0-180° | Extend |
| J3 | Wrist | 0-180° | Angle |
| J4 | Gripper | 0-180° | Grab |

---

## SOFTWARE ARCHITECTURE

### Desktop Application (nexus_v2/)

```
nexus_v2/
├── main.py              # Application launcher
├── ui/
│   ├── app.py           # Main window (21 tabs)
│   ├── theme.py         # Grey theme (#4a4a4a)
│   └── tabs/            # 21 UI tabs
├── scanner/
│   ├── enhanced_scanner.py
│   ├── pi5_scanner_client.py
│   └── universal_scanner.py
├── library/
│   ├── library_db.py
│   └── price_consensus.py
├── data/
│   ├── scryfall_db.py
│   └── yugioh_db.py
├── integrations/
│   └── marketplace_client.py
└── config/
    └── config_manager.py
```

### Pi Servers (pi_servers/)

| Server | Location | Port | Function |
|--------|----------|------|----------|
| brok_server.py | Brock | 5000 | OCR, AI processing, Coral TPU |
| snarf_server.py | Snarf | 5001 | Camera capture, ESP32/Arduino control |
| nexus_touch_ui.py | Snarf | - | Touch display interface |

### Marketplace (Zultan)

| Component | Path | Status |
|-----------|------|--------|
| server.py | /home/zultan/nexus-marketplace/ | Running |
| seller.html | /home/zultan/nexus-marketplace/ | Token auth enabled |
| login.html | /home/zultan/nexus-marketplace/ | Token auth enabled |
| cloudflared | systemd service | Active |

**Public URL:** https://nexus-cards.com (via Cloudflare Tunnel)

---

## RECENT FIXES (January 29, 2026)

### Marketplace Authentication
- **Issue:** Session cookies not working through Cloudflare tunnel
- **Solution:** Token-based auth fallback using X-User-ID header
- **Files Modified:**
  - server.py: Added `get_auth_user_id()` helper, accepts X-User-ID header
  - login.html: Stores user in localStorage, sends X-User-ID on auth check
  - seller.html: Reads localStorage, sends X-User-ID with all API calls

### Hardware Controls
- **Added:** Sliders for all 5 arm servos (J0-J4)
- **Added:** Solenoid ON/OFF buttons
- **Fixed:** Lightbox color control (blue was showing white)
- **Endpoint:** `/api/arm/set` for absolute angle positioning

### Mouse Wheel Scrolling
- **Fixed:** Added mouse wheel bindings to all scrollable widgets
- **Files:** app.py, collection.py, deck_builder.py, marketplace.py

---

## API ENDPOINTS

### Snarf Server (192.168.1.172:5001)

| Endpoint | Method | Function |
|----------|--------|----------|
| `/api/capture` | POST | Capture image from camera |
| `/api/lightbox` | POST | Control RGBW lightbox LEDs |
| `/api/ring/<n>` | POST | Control scanner ring LEDs |
| `/api/arm/home` | POST | Home all arm servos |
| `/api/arm/set` | POST | Set individual servo angle |
| `/api/arm/move` | POST | Relative arm movement |
| `/api/relay` | POST | Control vacuum/solenoid relay |

### Brock Server (192.168.1.174:5000)

| Endpoint | Method | Function |
|----------|--------|----------|
| `/api/scan` | POST | Full card scan with OCR |
| `/api/identify` | POST | Card identification from image |
| `/api/ocr` | POST | Raw OCR on image |

### Marketplace (nexus-cards.com)

| Endpoint | Method | Auth | Function |
|----------|--------|------|----------|
| `/health` | GET | No | Health check |
| `/api/auth/login` | POST | No | User login (returns token) |
| `/api/auth/me` | GET | Token/Session | Get current user |
| `/api/seller/dashboard` | GET | Token | Seller stats & listings |
| `/api/listings` | GET | No | Browse listings |
| `/api/cart` | GET/POST | Token | Cart management |

---

## SSH ACCESS

```bash
ssh zultan@192.168.1.152      # GPU Server - Marketplace, AI Training
ssh Nexus1@192.168.1.174      # Brock - OCR/Coral TPU
ssh nexus@192.168.1.172       # Snarf - Hardware/Cameras
```

---

## DEPLOYMENT

### Desktop App
```powershell
cd E:\NEXUS_V2_RECREATED
python nexus_v2/main.py
```

### Deploy to Snarf
```powershell
scp pi_servers/snarf_server.py nexus@192.168.1.172:/home/nexus/
ssh nexus@192.168.1.172 "sudo systemctl restart nexus-scanner"
```

### Deploy to Brock
```powershell
scp pi_servers/brok_server.py Nexus1@192.168.1.174:/home/Nexus1/
ssh Nexus1@192.168.1.174 "sudo systemctl restart brok"
```

### Marketplace (Zultan)
```bash
ssh zultan@192.168.1.152
cd /home/zultan/nexus-marketplace
sudo systemctl restart nexus-marketplace
```

---

## AI AGENT TEAM

| Agent | Model | Role | Specialty |
|-------|-------|------|-----------|
| **Clouse** | Opus 4.5 | Strategic Analysis | Business architecture, $10.8B vision |
| **Mendel** | Sonnet | Feature Developer | Code implementation, bug fixes |
| **Jaques** | Opus 4 | Patent Attorney | IP protection, 101-claim strategy |

---

## SCANNER PIPELINE

```
[Card on Lightbox]
       ↓
[Snarf: CZUR/OwlEye Capture]
       ↓
[Brock: OCR + AI Identification]
       ↓
[Desktop: Display Results + Library Update]
```

### Fixed Crop Values (CZUR on Snarf)
- **Lightbox region:** x=350, y=40, w=837, h=1012
- **Card within lightbox:** x=170, y=120, w=500, h=720

---

## KNOWN ISSUES

| Issue | Status | Notes |
|-------|--------|-------|
| Config warning on startup | Low priority | ScannerConfig parameter |
| Library shows 0 cards | Config needed | Requires path configuration |
| /gpu 404 spam in logs | Harmless | External polling from 192.168.1.159 |

---

## KEY FILES

| File | Purpose |
|------|---------|
| CLAUDE.md | Project context for AI agents |
| nexus_v2/main.py | Application entry point |
| nexus_v2/ui/app.py | Main window with all tabs |
| pi_servers/brok_server.py | OCR/AI server for Brock |
| pi_servers/snarf_server.py | Hardware control server for Snarf |
| servers/nexus_marketplace/server.py | Marketplace backend |

---

## METRICS

- **Python Files:** 146
- **UI Tabs:** 21
- **Pi Servers:** 19 scripts
- **Total Codebase:** 17MB
- **Patent Claims:** 101 (filed)
- **Hardware Nodes:** 4 (Zultan, Brock, Snarf, Surface)

---

**Last Updated:** January 29, 2026 @ 6:10 PM EST
**Status:** Marketplace auth fixed, hardware controls enhanced, seller page working
