# ATX Power Supply Wiring Guide for NEXUS Scanner

## ATX 24-Pin Main Connector Pinout

```
        TOP VIEW (clip facing up)
    ┌─────────────────────────┐
    │  1  2  3  4  5  6  7  8  9 10 11 12 │
    │ 13 14 15 16 17 18 19 20 21 22 23 24 │
    └─────────────────────────┘
```

### Pin Assignments:

| Pin | Color | Signal | Voltage | Use for NEXUS |
|-----|-------|--------|---------|---------------|
| 1 | Orange | +3.3V | 3.3V | ESP32 (via regulator) |
| 2 | Orange | +3.3V | 3.3V | ESP32 (via regulator) |
| 3 | Black | GND | Ground | **Common Ground** |
| 4 | Red | +5V | 5V | **NeoPixel Ring 1 Power** |
| 5 | Black | GND | Ground | **Common Ground** |
| 6 | Red | +5V | 5V | **NeoPixel Ring 2 Power** |
| 7 | Black | GND | Ground | **Common Ground** |
| 8 | Gray | PWR_OK | Signal | Leave disconnected |
| 9 | Purple | +5VSB | 5V Standby | Optional (always-on 5V) |
| 10 | Yellow | +12V | 12V | **Stepper Motor 1 (X-axis)** |
| 11 | Yellow | +12V | 12V | **Stepper Motor 2 (Y-axis)** |
| 12 | Orange | +3.3V | 3.3V | Spare |
| 13 | Orange | +3.3V | 3.3V | Spare |
| 14 | Blue | -12V | -12V | NOT USED |
| 15 | Black | GND | Ground | **Common Ground** |
| 16 | **GREEN** | **PS_ON** | Signal | **SHORT TO GND TO TURN ON PSU** |
| 17 | Black | GND | Ground | **Common Ground** |
| 18 | Black | GND | Ground | **Common Ground** |
| 19 | Black | GND | Ground | **Common Ground** |
| 20 | White | -5V | -5V | NOT USED |
| 21 | Red | +5V | 5V | Camera / ESP32 |
| 22 | Red | +5V | 5V | Spare 5V |
| 23 | Red | +5V | 5V | Spare 5V |
| 24 | Black | GND | Ground | **Common Ground** |

---

## Critical: How to Turn On the PSU

**The PSU will NOT turn on unless you short PS_ON to GND!**

### Method 1: Permanent ON (Jumper Wire)
- Connect **Pin 16 (GREEN)** to **Pin 17 (BLACK)** with a wire
- PSU turns on whenever plugged into wall power
- Simple, but no software control

### Method 2: Power Switch
- Wire a toggle switch between **Pin 16 (GREEN)** and **Pin 17 (BLACK)**
- Flip switch ON = PSU powers up
- Flip switch OFF = PSU shuts down

### Method 3: ESP32 Control (Advanced)
- Connect **Pin 16 (GREEN)** to **ESP32 GPIO (e.g., GPIO 4)** via NPN transistor
- ESP32 can turn PSU on/off via software
- Use this if you want remote power control

**For weekend demo:** Use Method 1 (jumper wire). Simple and reliable.

---

## Peripheral Connectors (Molex/SATA)

### 4-Pin Molex Connector
```
    ┌─────────────┐
    │  1  2  3  4  │
    └─────────────┘
```

| Pin | Color | Voltage | Current Limit |
|-----|-------|---------|---------------|
| 1 | Yellow | +12V | 6A per connector |
| 2 | Black | GND | Ground |
| 3 | Black | GND | Ground |
| 4 | Red | +5V | 6A per connector |

**Use for:**
- **Molex Pin 1 (Yellow +12V)** → Stepper drivers VIN
- **Molex Pin 2/3 (Black GND)** → Stepper drivers GND
- **Molex Pin 4 (Red +5V)** → NeoPixel 5V (if you prefer Molex over 24-pin)

---

## NEXUS Scanner Power Distribution

### Component Power Requirements:

| Component | Voltage | Current | Total Power | Wire Gauge |
|-----------|---------|---------|-------------|------------|
| **NeoPixel Ring 1** | 5V | 1A (16 LEDs) | 5W | 20 AWG |
| **NeoPixel Ring 2** | 5V | 1A (16 LEDs) | 5W | 20 AWG |
| **NEMA 17 Motor 1** | 12V | 1.5A | 18W | 18 AWG |
| **NEMA 17 Motor 2** | 12V | 1.5A | 18W | 18 AWG |
| **A4988 Drivers (2x)** | 12V | 0.1A | 1W | 22 AWG |
| **ESP32** | 5V | 0.5A | 2.5W | 22 AWG |
| **USB Camera** | 5V | 0.5A | 2.5W | From ASUS USB |
| **ASUS Laptop** | 19V | 3A | 57W | Separate AC adapter |
| **TOTAL** | - | - | **52W** | 300W PSU = plenty |

---

## Wiring Diagram

```
ATX PSU 24-Pin Connector
========================

PS_ON (Pin 16 GREEN) ──┬──> Short to GND with jumper wire
                       │
                    ┌──┴──┐
                    │ GND │ (Pin 17 BLACK)
                    └─────┘
                       │
                       └──────> Common Ground for ALL components


+5V Rails (Pins 4, 6, 21, 22, 23 RED)
====================================
    │
    ├──> NeoPixel Ring 1 (5V) ──> Pin 4 RED
    │         └──> GND to Pin 5 BLACK
    │
    ├──> NeoPixel Ring 2 (5V) ──> Pin 6 RED
    │         └──> GND to Pin 7 BLACK
    │
    └──> ESP32 (5V via buck) ──> Pin 21 RED
              └──> GND to Pin 15 BLACK


+12V Rails (Pins 10, 11 YELLOW)
================================
    │
    ├──> Stepper Driver 1 VIN ──> Pin 10 YELLOW
    │         └──> GND to Pin 15 BLACK
    │
    └──> Stepper Driver 2 VIN ──> Pin 11 YELLOW
              └──> GND to Pin 17 BLACK


Ground Reference
================
Pins 3, 5, 7, 15, 17, 18, 19, 24 (ALL BLACK) = Common Ground
- Connect ALL grounds together (star ground or bus bar)
- NeoPixel GND → Common
- Stepper GND → Common
- ESP32 GND → Common
- Camera GND → USB (from ASUS)
```

---

## Step-by-Step Wiring Instructions

### 1. Enable the PSU (Required!)
- Use a short wire (3-4 inches)
- Strip both ends
- Insert one end into **Pin 16 (GREEN)**
- Insert other end into **Pin 17 (BLACK)** or any other BLACK ground pin
- **PSU will now turn on when plugged into wall**

### 2. Wire NeoPixel Rings
- **Ring 1:**
  - Red wire → **Pin 4 (RED +5V)**
  - Black wire → **Pin 5 (BLACK GND)**
  - Data wire → **ESP32 GPIO 16**
  
- **Ring 2:**
  - Red wire → **Pin 6 (RED +5V)**
  - Black wire → **Pin 7 (BLACK GND)**
  - Data wire → **ESP32 GPIO 17**

### 3. Wire Stepper Drivers (A4988 or similar)
- **Driver 1 (X-axis):**
  - VIN → **Pin 10 (YELLOW +12V)**
  - GND → **Pin 15 (BLACK GND)**
  - STEP → Arduino/ESP32 GPIO
  - DIR → Arduino/ESP32 GPIO
  - Motor A+/A-/B+/B- → NEMA 17 Motor 1

- **Driver 2 (Y-axis):**
  - VIN → **Pin 11 (YELLOW +12V)**
  - GND → **Pin 17 (BLACK GND)**
  - STEP → Arduino/ESP32 GPIO
  - DIR → Arduino/ESP32 GPIO
  - Motor A+/A-/B+/B- → NEMA 17 Motor 2

### 4. Wire ESP32
- **Option A: Direct 5V** (if ESP32 has voltage regulator)
  - 5V → **Pin 21 (RED +5V)**
  - GND → **Pin 15 (BLACK GND)**

- **Option B: USB Power** (easiest)
  - Use USB cable from ASUS laptop or powered USB hub
  - GND → **Pin 15 (BLACK GND)** (common ground!)

### 5. Common Ground (CRITICAL!)
- All BLACK wires from components MUST connect to PSU GND
- Use wire nuts, terminal blocks, or solder to create common ground bus
- **BAD grounds = erratic behavior, damaged components**

---

## Safety Notes

### ⚠️ DO NOT:
- ❌ Connect +12V to 5V components (will destroy ESP32, NeoPixels)
- ❌ Reverse polarity (red to black) - instant smoke
- ❌ Exceed current ratings (use Molex for high current, not 24-pin)
- ❌ Hot-plug components while PSU is on
- ❌ Touch exposed wires while PSU is powered

### ✅ DO:
- ✅ Double-check voltages with multimeter before connecting components
- ✅ Use heat shrink tubing or electrical tape on all connections
- ✅ Secure wires with zip ties (prevent shorts)
- ✅ Test PSU output voltages FIRST (Green to Black = PSU ON, measure pins with multimeter)
- ✅ Add fuses on +12V lines if possible (5A fuses protect motors)

---

## Testing Procedure

### Step 1: Test PSU Alone
1. Plug in PSU (wall power OFF)
2. Short **Pin 16 (GREEN)** to **Pin 17 (BLACK)** with jumper
3. Plug into wall → PSU fan should spin
4. Use multimeter to verify:
   - Pin 4 (RED) = +5V
   - Pin 10 (YELLOW) = +12V
   - Pin 3 (BLACK) = 0V (ground reference)

### Step 2: Test NeoPixels
1. Connect ONE NeoPixel ring to 5V/GND
2. Connect data pin to ESP32 GPIO 16
3. Upload test sketch, run rainbow pattern
4. If works, connect second ring

### Step 3: Test Steppers
1. Connect stepper driver to +12V/GND
2. Connect motor to driver
3. Send STEP pulses from Arduino
4. Motor should rotate smoothly
5. If works, connect second motor

### Step 4: Full System Test
1. All components connected
2. Power on PSU
3. ESP32 connects to WiFi
4. NeoPixels turn on via HTTP command
5. Steppers home X and Y axes
6. Camera captures test image
7. AI grades test card

---

## Wire Color Code Reminder

**ATX PSU Standard Colors:**
- 🟡 **YELLOW** = +12V (motors)
- 🔴 **RED** = +5V (LEDs, logic)
- 🟠 **ORANGE** = +3.3V (optional)
- ⚫ **BLACK** = Ground (0V reference)
- 🟢 **GREEN** = PS_ON (short to black to power on)
- ⚪ **WHITE** = -5V (not used)
- 🔵 **BLUE** = -12V (not used)
- 🟣 **PURPLE** = +5V Standby (always on when plugged in)
- 🩶 **GRAY** = Power Good signal (optional)

**Always verify with multimeter before connecting!**

---

## Quick Reference Card (Print This!)

```
┌─────────────────────────────────────────────────┐
│  NEXUS SCANNER - ATX POWER QUICK REFERENCE      │
├─────────────────────────────────────────────────┤
│  Turn ON PSU:  Pin 16 (GREEN) → Pin 17 (BLACK) │
│                                                  │
│  NeoPixel 1:   Pin 4 (RED +5V), Pin 5 (GND)    │
│  NeoPixel 2:   Pin 6 (RED +5V), Pin 7 (GND)    │
│                                                  │
│  Stepper 1:    Pin 10 (YELLOW +12V), Pin 15 (GND) │
│  Stepper 2:    Pin 11 (YELLOW +12V), Pin 17 (GND) │
│                                                  │
│  ESP32:        Pin 21 (RED +5V), Pin 15 (GND)   │
│                                                  │
│  Common GND:   Pins 3,5,7,15,17,18,19,24 (BLACK)│
└─────────────────────────────────────────────────┘
```

---

**You're ready to wire it up!** Start with PSU test (Green to Black), verify voltages, then add components one at a time. Any questions on a specific connection?
