# ESP32 SCANNER FIRMWARE - UPLOAD GUIDE

## 📋 Prerequisites

### Required Software
1. **Arduino IDE 2.x** (Download: https://www.arduino.cc/en/software)
2. **ESP32 Board Support**
3. **Adafruit NeoPixel Library**

### Hardware Required
- ESP32 DevKit v1 (or compatible)
- USB cable (micro-USB or USB-C depending on board)
- 2x NeoPixel Ring (16 LEDs each)
- 5V/3A Power Supply for NeoPixels

---

## ⚙️ Step 1: Install ESP32 Board Support

### In Arduino IDE:
1. Open **File → Preferences**
2. In "Additional Board Manager URLs", add:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Click **OK**
4. Open **Tools → Board → Boards Manager**
5. Search for: `esp32`
6. Install: **esp32 by Espressif Systems** (latest version)
7. Wait for installation (takes 2-5 minutes)

---

## 📚 Step 2: Install Adafruit NeoPixel Library

### In Arduino IDE:
1. Open **Tools → Manage Libraries** (or Ctrl+Shift+I)
2. Search for: `Adafruit NeoPixel`
3. Install: **Adafruit NeoPixel by Adafruit** (latest version)
4. Click **Install All** if prompted for dependencies

---

## 🔌 Step 3: Connect ESP32

1. **Plug ESP32 into USB port** on ASUS laptop
2. **Wait for driver installation** (Windows will auto-install)
3. Check Device Manager:
   - Should show: **COM# (USB-SERIAL CH340)** or similar
   - Note the COM port number (e.g., COM5)

### Driver Issues?
If ESP32 not detected, install CH340 driver:
- Download: https://sparks.gogo.co.nz/ch340.html
- Install and restart computer

---

## 📂 Step 4: Open Firmware in Arduino IDE

1. Open Arduino IDE
2. **File → Open**
3. Navigate to: `E:\MTTGG\ARDUINO_SKETCHES\nexus_esp32_scanner_v2.ino`
4. Click **Open**

---

## ⚡ Step 5: Configure Arduino IDE

### Board Settings:
1. **Tools → Board → esp32 → ESP32 Dev Module** (or your specific board)

### Port Settings:
2. **Tools → Port → COM# (USB-SERIAL CH340)** (your ESP32 port)

### Upload Speed:
3. **Tools → Upload Speed → 115200** (recommended for stability)

### Flash Settings (Advanced):
- Flash Size: **4MB**
- Partition Scheme: **Default 4MB with spiffs**
- Flash Mode: **QIO**
- Flash Frequency: **80MHz**
- Core Debug Level: **None** (or "Info" for debugging)

---

## 🚀 Step 6: Upload Firmware

1. **Click Upload button** (→ arrow icon) or press **Ctrl+U**
2. Arduino IDE will:
   - ✅ Compile code
   - ✅ Connect to ESP32
   - ✅ Upload firmware
   - ✅ Verify upload

### Expected Output:
```
Sketch uses 274552 bytes (20%) of program storage space.
Global variables use 17984 bytes (5%) of dynamic memory.

esptool.py v4.5.1
Serial port COM5
Connecting.....
Chip is ESP32-D0WDQ6 (revision v1.0)
Features: WiFi, BT, Dual Core, 240MHz, VRef calibration in efuse, Coding Scheme None
Crystal is 40MHz
MAC: xx:xx:xx:xx:xx:xx
Uploading stub...
Running stub...
Stub running...
Changing baud rate to 460800
Changed.
Writing at 0x00010000... (100%)
Wrote 274552 bytes (176234 compressed) at 0x00010000 in 4.2 seconds

Hard resetting via RTS pin...
```

### Upload Success?
- ✅ IDE shows "Done uploading"
- ✅ ESP32's blue LED blinks during upload
- ✅ ESP32 restarts automatically

---

## ✅ Step 7: Test Serial Communication

1. **Open Serial Monitor**: Tools → Serial Monitor (or Ctrl+Shift+M)
2. **Set baud rate**: 115200 (bottom-right dropdown)
3. **Set line ending**: "Newline" or "Both NL & CR"

### Expected Startup Output:
```
========================================
NEXUS CARD SCANNER - ESP32 READY
========================================
Firmware Version: 2.0
Lighting: 2x16 NeoPixel Rings
Default Brightness: 200
Default Color Temp: 5000K
========================================
Ready for commands (L1, L0, B255, etc.)
========================================
```

### Test Commands:
Type these in Serial Monitor and press Enter:

| Command | Expected Result |
|---------|----------------|
| `L1` | Lights turn ON (white) |
| `L0` | Lights turn OFF |
| `B255` | Brightness = MAX |
| `B128` | Brightness = 50% |
| `TEST` | Rainbow test pattern |
| `STATUS` | Print current settings |

---

## 🔧 Troubleshooting

### ❌ "Port COM# not available"
**Solution:**
- Close Python scripts or Serial Monitor
- Unplug/replug ESP32
- Check Device Manager for correct port
- Try different USB port

### ❌ "Failed to connect to ESP32"
**Solution:**
- Hold **BOOT button** on ESP32 while clicking Upload
- Release BOOT button after "Connecting..." appears
- Check USB cable (some are power-only)
- Install CH340 drivers

### ❌ "Compilation error: Adafruit_NeoPixel.h not found"
**Solution:**
- Install Adafruit NeoPixel library (Step 2)
- Restart Arduino IDE

### ❌ "Upload failed: Timeout"
**Solution:**
- Lower upload speed: Tools → Upload Speed → 115200
- Press ESP32 reset button before upload
- Try shorter/better USB cable

### ❌ "LEDs don't light up"
**Solution:**
- Check NeoPixel power supply (5V/3A)
- Verify data pin connections (GPIO 16, 17)
- Common ground between ESP32 and power supply
- Test with `TEST` command in Serial Monitor

---

## 📝 Serial Command Reference

### Lighting Control
| Command | Description | Example |
|---------|-------------|---------|
| `L1` or `ON` | Turn lights ON | `L1` |
| `L0` or `OFF` | Turn lights OFF | `L0` |
| `B<0-255>` | Set brightness | `B200` |
| `C<R,G,B>` | Set RGB color | `C255,255,255` |
| `T<K>` | Set color temp (2700-6500K) | `T5000` |

### Camera Control
| Command | Description |
|---------|-------------|
| `CAP` or `CAPTURE` | Trigger camera |
| `SCAN` | Full scan sequence (lights + camera) |

### Diagnostics
| Command | Description |
|---------|-------------|
| `TEST` | Run LED test pattern |
| `STATUS` | Print current settings (JSON) |
| `RESET` | Reset to defaults |

---

## 🔗 Hardware Connections

### NeoPixel Rings
```
Ring 1 Data Pin  →  ESP32 GPIO 16
Ring 2 Data Pin  →  ESP32 GPIO 17
Rings 5V         →  External 5V Power Supply (3A+)
Rings GND        →  Common Ground (ESP32 + PSU)
ESP32 GND        →  Power Supply GND
```

### Camera Trigger (Optional)
```
GPIO 4           →  Camera shutter relay/trigger
```

### Power
```
ESP32 5V/VIN     →  USB power or external 5V
ESP32 GND        →  Common ground
```

**⚠️ WARNING:** NeoPixels need external 5V power supply (3A+ for 32 LEDs at full brightness). Do NOT power 32 LEDs from ESP32's 5V pin (max 500mA).

---

## 🎯 Next Steps

1. ✅ Upload firmware to ESP32
2. ✅ Test with Serial Monitor
3. ✅ Connect NeoPixel rings
4. ✅ Run hardware test: `python esp32_scanner_test.py`
5. ✅ Integrate with NEXUS demo system

---

## 📞 Support

**Firmware Location:** `E:\MTTGG\ARDUINO_SKETCHES\nexus_esp32_scanner_v2.ino`

**Test Script:** `E:\MTTGG\PYTHON SOURCE FILES\esp32_scanner_test.py`

**Issues?**
- Check Serial Monitor (115200 baud) for error messages
- Run `TEST` command to verify LEDs working
- Verify connections match wiring diagram above
