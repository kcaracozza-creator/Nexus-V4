# NEXUS Hardware Architecture
**Updated: Feb 2026 | DANIELSON System**

---

## Overview

Two ESP32 microcontrollers. Both talk to DANIELSON (desktop PC) via USB serial.

```
DANIELSON (PC)
    ├── USB Serial → ESP32 #1  (Light Controller)
    └── USB Serial → ESP32 #2  (Arm Controller)
```

---

## ESP32 #1 — LIGHT CONTROLLER

| GPIO | Function |
|------|----------|
| 25   | LED channel (qty TBD) |
| 26   | LED channel (qty TBD) |
| 27   | LED channel (qty TBD) |
| 33   | LED channel (qty TBD) |
| 32   | LED channel (qty TBD) |

**Protocol:** JSON over Serial @ 115200 baud

---

## ESP32 #2 — ARM CONTROLLER

### Direct GPIO

| GPIO | Function |
|------|----------|
| 18   | Base stepper PUL+ |
| 19   | Base stepper PUL- |
| 33   | Base stepper DIR+ |
| 25   | Base stepper DIR- |
| 27   | 40x WS2812B lightbox strip |

### PCA9685 (I2C: SDA GPIO 21 / SCL GPIO 22 / Address 0x40)

| Channel | Component | Type |
|---------|-----------|------|
| 1       | Shoulder servo | MG995 |
| 2       | Elbow servo | MG995 |
| 3       | Wrist servo 1 | MG90 |
| 4       | Wrist servo 2 | MG90 |
| 5       | Vacuum pump | Relay |
| 6       | Solenoid release | Relay |

**End effector:** Suction cup

**Protocol:** JSON over Serial @ 115200 baud

---

## Serial Command Reference

### Light Controller Commands
```json
{"cmd": "set_channel", "channel": 25, "value": 255}
{"cmd": "all_off"}
{"cmd": "all_on", "brightness": 128}
{"cmd": "ping"}
```

### Arm Controller Commands
```json
{"cmd": "move_base", "steps": 200, "dir": 1, "speed": 500}
{"cmd": "servo", "channel": 1, "angle": 90}
{"cmd": "relay", "channel": 5, "state": 1}
{"cmd": "lightbox", "r": 255, "g": 255, "b": 255}
{"cmd": "lightbox_off"}
{"cmd": "home"}
{"cmd": "ping"}
```

### Responses
```json
{"status": "ok"}
{"status": "ok", "data": "..."}
{"status": "error", "msg": "..."}
{"status": "pong"}
```

---

## Deprecated / Decommissioned

- BROCK (Pi 5, 192.168.1.169) — **DEAD**
- SNARF (Pi 5, 192.168.1.172) — **DEAD**
- OwlEye 64MP camera system — **DEAD**
- XY gantry / NEMA17 motors — **NOT PART OF THIS SYSTEM**
- WiFi HTTP firmware — **REPLACED by serial**

---

## Current Infrastructure

| System | Role |
|--------|------|
| DANIELSON (desktop PC) | Main controller, runs NEXUS desktop app |
| ZULTAN (192.168.1.152) | AI training, RTX 3060, marketplace backend |
| ESP32 #1 | Light controller |
| ESP32 #2 | Arm controller |
