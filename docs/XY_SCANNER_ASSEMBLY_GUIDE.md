# XY Scanner Assembly Guide - Dual Lead Screw System

## 🎯 Overview

Automated card scanner using dual lead screws for precise XY positioning. Positions cards under camera for batch scanning.

---

## 📦 Parts List

### Mechanical Components

#### Lead Screw System (X2)
- **Lead Screws**: 2x T8 lead screw (2mm pitch, 300mm length for X, 200mm for Y)
- **Lead Nuts**: 2x T8 brass nut with anti-backlash spring
- **Couplers**: 2x 5mm to 8mm flexible coupling
- **Linear Rails**: 2x MGN12H linear rail (300mm X-axis, 200mm Y-axis)
- **Carriages**: 4x MGN12H linear carriage blocks
- **End Supports**: 4x SK8 or SHF8 shaft support brackets

#### Frame
- **Aluminum Extrusion**: 2020 V-slot (or equivalent)
  - 2x 400mm (X-axis rails)
  - 2x 300mm (Y-axis rails)
  - 4x 200mm (vertical supports)
- **Corner Brackets**: 8x 2020 corner brackets
- **T-nuts and Bolts**: M5 hardware kit

#### Scanning Bed
- **Platform**: 300mm x 200mm acrylic/MDF sheet (3-5mm thick)
- **Card Grid**: Printed alignment guide
- **Mounting**: 4x standoffs with rubber feet

### Electronics

#### Stepper Motors
- **Motors**: 2x NEMA 17 stepper motors (1.8° per step, 1.5A+)
- **Torque**: Minimum 40 Nm·cm holding torque
- **Shaft**: 5mm diameter with flat

#### Drivers & Control
- **Stepper Drivers**: 2x A4988 or DRV8825 (with heatsinks)
- **Microcontroller**: Arduino Uno or Mega 2560
- **Power Supply**: 12V 3A DC adapter
- **Wiring**: Stepper motor cables, jumper wires

#### Sensors
- **Limit Switches**: 4x mechanical endstop switches
  - 2x X-axis (min/max)
  - 2x Y-axis (min/max)
- **Optional**: Hall effect sensors for homing precision

#### Camera System
- **Camera**: USB webcam or Raspberry Pi Camera Module
- **Mount**: Adjustable arm or fixed overhead mount
- **Lighting**: LED ring light or strip (5V, ~1-2W)

### Miscellaneous
- **Cable Management**: Cable chains, zip ties
- **Fasteners**: M3, M4, M5 bolts, nuts, washers
- **Lubricant**: PTFE grease for lead screws
- **Anti-vibration**: Rubber dampers for motor mounts

---

## 🔧 Assembly Instructions

### Step 1: Frame Construction

1. **Cut aluminum extrusion** to lengths:
   - X-axis: 2x 400mm
   - Y-axis: 2x 300mm
   - Verticals: 4x 200mm

2. **Assemble base frame**:
   ```
   ┌─────────────────────────┐
   │    400mm (X-axis)       │
   │                         │
   │ 300mm        300mm      │
   │ (Y-axis)     (Y-axis)   │
   │                         │
   └─────────────────────────┘
   ```
   - Connect with corner brackets
   - Ensure square (measure diagonals)

3. **Add vertical supports**:
   - Mount at each corner
   - Height: 200mm for camera clearance

### Step 2: Linear Rail Installation

**X-Axis Rail (300mm)**:
1. Mount MGN12H rail to top of Y-axis extrusion
2. Use M3 bolts every 50mm
3. Ensure rail is straight (use straightedge)
4. Install 2x carriages on rail

**Y-Axis Rail (200mm)**:
1. Mount MGN12H rail to X-axis carriage assembly
2. Perpendicular to X-axis
3. Install 2x carriages for scanning bed mount

### Step 3: Lead Screw Installation

**For Each Axis**:

1. **Mount end supports**:
   - SK8/SHF8 brackets at each end of extrusion
   - Aligned and square

2. **Install lead screw**:
   - Thread through supports
   - Attach flexible coupler to motor end
   - Leave 2-3mm gap in coupler (prevents binding)

3. **Attach lead nut**:
   - Mount to linear carriage assembly
   - Use anti-backlash spring
   - Ensure smooth rotation

4. **Test movement**:
   - Screw should turn freely
   - No binding or wobble
   - Carriage moves smoothly along entire length

### Step 4: Motor Mounting

**X-Axis Motor**:
1. Mount NEMA 17 to left end of X-axis
2. Use motor mount bracket or custom plate
3. Align shaft with lead screw coupler
4. Tighten coupler set screws (on flat of shaft)

**Y-Axis Motor**:
1. Mount to rear of Y-axis carriage assembly
2. Same alignment procedure
3. Ensure no interference with X-axis movement

### Step 5: Limit Switch Installation

**Placement**:
- **X-Min**: Left end of X-axis
- **X-Max**: Right end of X-axis  
- **Y-Min**: Front of Y-axis
- **Y-Max**: Rear of Y-axis

**Mounting**:
1. Use M3 bolts to extrusion
2. Position so carriage triggers switch at limit
3. Leave 2-3mm actuation distance
4. Test: switch should click when carriage reaches end

### Step 6: Scanning Bed Assembly

1. **Cut platform**: 300mm x 200mm acrylic/MDF

2. **Print card grid template**:
   ```
   ┌──┬──┬──┬──┐
   │  │  │  │  │  4x2 grid = 8 cards
   ├──┼──┼──┼──┤
   │  │  │  │  │  Card size: 63.5mm x 88.9mm
   └──┴──┴──┴──┘  Spacing: 2mm gap
   ```

3. **Mount to Y-axis carriage**:
   - Use standoffs (10-20mm height)
   - 4-point mounting for stability

4. **Add card guides** (optional):
   - 3D print corner guides
   - Ensures cards stay aligned

### Step 7: Electronics Wiring

**Stepper Driver Setup** (A4988/DRV8825):

1. **Microstepping configuration**:
   ```
   MS1  MS2  MS3  | Steps
   ─────────────────────
   L    L    L    | 1 (full step)
   H    L    L    | 1/2
   L    H    L    | 1/4
   H    H    L    | 1/8
   H    H    H    | 1/16 ← Use this
   ```
   Connect MS1, MS2, MS3 to +5V for 1/16 microstepping

2. **Wiring diagram**:
   ```
   Arduino → X-Driver:
     Pin 2 → STEP
     Pin 3 → DIR
     Pin 4 → ENABLE
     GND   → GND
   
   Arduino → Y-Driver:
     Pin 5 → STEP
     Pin 6 → DIR
     Pin 7 → ENABLE
     GND   → GND
   
   Power Supply (12V):
     +12V → VMOT (both drivers)
     GND  → GND (both drivers)
   
   Arduino → Limit Switches:
     Pin 9  → X-Min (with 10kΩ pullup)
     Pin 10 → X-Max
     Pin 11 → Y-Min
     Pin 12 → Y-Max
     GND    → Common ground
   ```

3. **Stepper motor wiring** (standard 4-wire):
   ```
   Motor Coil A: 1A, 1B
   Motor Coil B: 2A, 2B
   
   Driver Connections:
     1A → A1
     1B → A2
     2A → B1
     2B → B2
   ```
   
   **Color code** (common, not universal):
   - Red/Blue = Coil A
   - Green/Black = Coil B

4. **Current limiting** (A4988):
   - Adjust potentiometer on driver
   - Target: 70% of motor rated current
   - Example: 1.5A motor → set to 1.0A
   - Measure VREF with multimeter:
     ```
     VREF = Current × 8 × Rsense
     For 1.0A: VREF = 1.0 × 8 × 0.1 = 0.8V
     ```

### Step 8: Camera Mounting

**Overhead Mount**:
1. Attach camera to vertical support
2. Position directly above scanning bed
3. Height: 200-300mm (adjust for focus)
4. Ensure entire card grid is in frame
5. USB cable routed with cable management

**Lighting**:
1. Mount LED ring around camera lens
2. Or LED strips around bed perimeter
3. Diffuse lighting (no harsh shadows)
4. Connect to 5V power

---

## ⚙️ Software Setup

### 1. Upload Arduino Sketch

```bash
# Copy sketch to SD card
cp ARDUINO_SKETCHES/xy_scanner_controller.ino /media/sdcard/arduino/

# Or upload directly
arduino-cli compile --fqbn arduino:avr:uno xy_scanner_controller.ino
arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:uno xy_scanner_controller.ino
```

### 2. Test Python Controller

```bash
# Install dependencies
pip install pyserial

# Test connection
python xy_scanner_controller.py --port COM4

# Run calibration
python xy_scanner_controller.py --port COM4 --calibrate

# Test grid scan
python xy_scanner_controller.py --port COM4 --test-grid --rows 4 --cols 2
```

### 3. Calibration Procedure

1. **Measure actual movement**:
   - Command 100mm movement
   - Measure with ruler/calipers
   - Calculate correction factor

2. **Update Arduino code**:
   ```cpp
   #define X_CORRECTION 1.0234  // Example
   #define Y_CORRECTION 0.9876
   ```

3. **Save calibration**:
   - Stored in `xy_scanner_calibration.json`
   - Applied automatically by Python controller

---

## 🎯 Operation

### Manual Jog Mode

```bash
python xy_scanner_controller.py --port COM4

Commands:
  left <mm>   - Move left
  right <mm>  - Move right
  up <mm>     - Move up
  down <mm>   - Move down
  home        - Return to origin
  status      - Show current position
  quit        - Exit
```

### Automated Grid Scan

```python
from xy_scanner_controller import XYScannerController

scanner = XYScannerController(port='COM4')

# Define camera callback
def capture_card():
    # Your camera code here
    return {'captured': True}

# Scan 4x2 grid (8 cards)
results = scanner.scan_grid(
    camera_callback=capture_card,
    cards_per_row=4,
    cards_per_col=2
)

print(f"Scanned {len(results)} cards")
```

---

## 🔍 Troubleshooting

### Motors Not Moving

**Check**:
- Power supply connected (12V to VMOT)
- Stepper drivers enabled (ENABLE pin LOW)
- Motor wiring correct (coils A and B)
- Arduino code uploaded successfully

**Test**:
- Swap X and Y drivers to isolate issue
- Measure voltage at VMOT (should be 12V)
- Check motor resistance (should be 1-10Ω per coil)

### Stuttering/Missed Steps

**Causes**:
- Current too low (increase VREF)
- Speed too fast (decrease in code)
- Mechanical binding (check alignment)
- Power supply insufficient (upgrade to 3A+)

**Solutions**:
- Adjust driver current to 80% motor rating
- Lubricate lead screws with PTFE grease
- Ensure linear rails are straight and parallel
- Add decoupling capacitor (100µF) to VMOT

### Limit Switches Not Working

**Check**:
- Switch normally open (NO) configuration
- Pullup resistors enabled (INPUT_PULLUP in code)
- Wiring polarity (switch between pin and GND)
- Mechanical actuation (carriage triggers switch)

**Test**:
- Use multimeter continuity test
- Monitor Serial output: "LIMIT_SWITCH" message

### Position Drift

**Causes**:
- Missed steps (see above)
- Microstepping configuration incorrect
- Lead screw backlash
- Encoder not used (open-loop system)

**Solutions**:
- Home before each scan session
- Use anti-backlash lead nut
- Enable microstepping (1/16 recommended)
- Consider closed-loop steppers for critical accuracy

---

## 📊 Performance Specs

| Specification | Value |
|--------------|-------|
| **Scan Area** | 300mm x 200mm |
| **Cards per Scan** | 8 (4x2 grid) |
| **Positioning Accuracy** | ±0.1mm |
| **Repeatability** | ±0.05mm |
| **Max Speed** | 50mm/s |
| **Scan Speed** | 20mm/s |
| **Cards per Minute** | ~30 (including capture time) |
| **Total Weight** | ~3kg |
| **Power Consumption** | 12V @ 2A (24W typical) |

---

## 🚀 Integration with Nexus Card System

### Auto-Scan Workflow

1. **Place cards on grid** (4x2 = 8 cards)
2. **Press "Auto Scan" button** in Nexus UI
3. **Scanner homes** (if not already homed)
4. **Moves to first position** (0,0)
5. **Camera captures card**
6. **AI recognizes card** (GPU accelerated)
7. **Moves to next position**
8. **Repeat for all 8 positions**
9. **Returns to home**
10. **Cards added to inventory**

**Total time**: ~15-20 seconds for 8 cards

### Python Integration

```python
# In mttgg_complete_system.py

from xy_scanner_controller import XYScannerController

class MTTGGCompleteSystem:
    def __init__(self, root):
        # ... existing code ...
        
        # Initialize XY scanner
        try:
            self.xy_scanner = XYScannerController(port='COM4')
            print("✅ XY Scanner connected")
        except:
            self.xy_scanner = None
            print("⚠️ XY Scanner not found")
    
    def auto_scan_grid(self):
        """Automated grid scan with camera capture"""
        if not self.xy_scanner:
            messagebox.showerror("Scanner Error", "XY Scanner not connected")
            return
        
        # Scan grid with camera callback
        results = self.xy_scanner.scan_grid(
            camera_callback=self.capture_and_recognize_card,
            cards_per_row=4,
            cards_per_col=2
        )
        
        messagebox.showinfo("Scan Complete", 
                          f"Scanned {len(results)} cards successfully!")
```

---

## 💡 Future Enhancements

### Automatic Card Feeding
- Add card hopper mechanism
- Gravity-fed or motorized pusher
- Scan entire deck automatically

### Dual-Side Scanning
- Flip mechanism after first side capture
- Capture both front and back
- Detects double-faced cards

### Higher Throughput
- Increase to 6x4 grid (24 cards)
- Faster stepper motors (upgrade to servo)
- Pipelined operation (move while processing)

### Precision Upgrades
- Closed-loop steppers with encoders
- Ball screws instead of lead screws
- TMC2209 silent drivers
- Optical homing with photointerrupters

---

## 📚 Resources

- **T8 Lead Screw**: [Amazon](https://www.amazon.com/s?k=T8+lead+screw)
- **MGN12H Linear Rail**: [Amazon](https://www.amazon.com/s?k=MGN12H)
- **NEMA 17 Stepper**: [Amazon](https://www.amazon.com/s?k=NEMA+17)
- **A4988 Driver**: [Pololu](https://www.pololu.com/product/1182)
- **Arduino**: [Arduino.cc](https://www.arduino.cc/)

**Total Build Cost**: ~$150-200 USD

---

## ✅ Assembly Checklist

- [ ] Frame assembled and square
- [ ] Linear rails installed and aligned
- [ ] Lead screws installed, no binding
- [ ] Motors mounted and coupled
- [ ] Limit switches installed and tested
- [ ] Scanning bed mounted
- [ ] Card grid printed and aligned
- [ ] Stepper drivers configured (1/16 microstepping)
- [ ] Current limit adjusted (70-80% motor rating)
- [ ] All wiring completed and checked
- [ ] Arduino sketch uploaded
- [ ] Python controller tested
- [ ] Homing procedure successful
- [ ] Calibration completed
- [ ] Test scan performed
- [ ] Camera mounted and focused
- [ ] Lighting installed
- [ ] Cable management completed
- [ ] Safety guards added (optional)

**Ready for production scanning!** 🎉
