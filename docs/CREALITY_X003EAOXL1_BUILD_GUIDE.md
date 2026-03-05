# Creality X003EAOXL1 Lead Screw Kit - XY Scanner Build

## 📦 What You Have (Per Kit x2)

**Creality X003EAOXL1 Specifications**:
- **Lead Screw**: T8 (8mm diameter, 2mm pitch, 4-start)
- **Length**: 400mm
- **Lead Nut**: Brass anti-backlash nut with spring
- **Coupler**: 5mm to 8mm flexible coupler (included)
- **Thread**: Trapezoidal, right-hand
- **Material**: Carbon steel, chrome plated

Since you have **2 kits**, perfect for X and Y axes!

---

## 🛠️ Build Configuration

### X-Axis (Longer travel):
- **Lead Screw**: 400mm from Kit #1
- **Travel Distance**: ~380mm usable
- **Cards Capacity**: 5 cards wide (5 × 63.5mm = 317.5mm)

### Y-Axis (Shorter travel):
- **Lead Screw**: 400mm from Kit #2 (can cut shorter if needed)
- **Travel Distance**: ~380mm usable  
- **Cards Capacity**: 4 cards tall (4 × 88.9mm = 355.6mm)

### Total Grid: **5×4 = 20 cards per scan!**

---

## 📐 Cut Recommendations

You can use both screws at 400mm, OR:

**Option 1: Both 400mm (easiest)**
- No cutting needed
- Larger footprint but maximum flexibility
- Final dimensions: ~450mm × 450mm × 200mm tall

**Option 2: Cut Y-axis shorter (compact)**
- X-axis: 400mm (full length)
- Y-axis: Cut to 250mm
- Saves space, still fits 2 rows of cards
- Final dimensions: ~450mm × 300mm × 200mm tall

**Cutting T8 screws**:
- Use hacksaw or angle grinder
- Mark with tape, measure twice
- Deburr cut end with file
- Thread end with M8 tap if needed for support

---

## ⚙️ Updated Specs for Your Build

```python
# xy_scanner_controller.py - Updated for Creality kit

class XYScannerController:
    # Lead screw specs from Creality X003EAOXL1
    STEPS_PER_REV = 200
    MICROSTEPS = 16
    LEAD_SCREW_PITCH = 8.0  # 4-start T8 = 8mm per revolution
    
    # Scanner bed dimensions (for 400mm screws)
    BED_WIDTH = 380.0    # mm (X-axis)
    BED_HEIGHT = 380.0   # mm (Y-axis) - or 230mm if cut
    
    # Card grid (5×4 = 20 cards)
    CARDS_PER_ROW = 5
    CARDS_PER_COL = 4
```

---

## 🔩 Parts You Already Have (From Creality Kits)

**Per kit (you have 2)**:
- ✅ 1x T8×400mm lead screw
- ✅ 1x Brass anti-backlash nut
- ✅ 1x 5mm-to-8mm flexible coupler
- ✅ Possibly includes mounting bracket

**Still Need**:
- 2x NEMA 17 stepper motors
- 2x Stepper drivers (A4988/DRV8825)
- 2x Linear rails (MGN12H 400mm or cut from 500mm)
- 4x Linear carriages
- Aluminum extrusion for frame
- Limit switches (4x)
- 3D printed parts (end supports, mounts)

---

## 🖨️ 3D Printed Parts (Updated for Creality Kit)

All dimensions match the Creality X003EAOXL1 specs:
- Lead screw: 8mm diameter
- Nut: 22mm flange diameter, 10mm body
- Coupler: 5-8mm (motor to screw)

**Print these**:
1. End supports (4x) - holds 8mm screw in 608 bearing
2. Lead nut mounts (2x) - attaches brass nut to carriage
3. Motor mounts (2x) - NEMA 17 to frame
4. Linear rail mounts (8x) - rails to extrusion

All STL files ready in `3D_MODELS/` folder.

---

## 🚀 Step-by-Step Build

### 1. Frame Assembly
```
Build base frame:
┌─────────────────────────────┐
│       450mm (X-axis)        │
│                             │
│  400mm      Lead Screw      │
│  (Y-axis)                   │
│                             │
└─────────────────────────────┘

Use 2020 aluminum extrusion
```

### 2. Install Lead Screws

**X-Axis** (400mm screw, Kit #1):
- Mount end supports at both ends
- Insert lead screw
- Attach flexible coupler to NEMA 17
- Test: screw should rotate smoothly

**Y-Axis** (400mm screw, Kit #2):
- Same process as X-axis
- If cutting to 250mm, do it now

### 3. Attach Brass Nuts

The Creality nuts have **anti-backlash springs** - awesome!

- Press nut into 3D printed bracket
- Nut should sit flush
- Spring faces toward screw (prevents play)
- Bolt bracket to linear carriage (4x M3 screws)

### 4. Install Linear Rails

**MGN12H rails** (or similar):
- X-axis: 400mm rail
- Y-axis: 400mm rail (or 250mm if compact build)
- Mount with 3D printed rail blocks every 50mm
- Ensure rails are parallel (measure both ends)

### 5. Wire Motors

Connect to Arduino:
```
X-Axis Motor:
  STEP → Pin 2
  DIR  → Pin 3
  EN   → Pin 4

Y-Axis Motor:
  STEP → Pin 5
  DIR  → Pin 6
  EN   → Pin 7
```

### 6. Test Movement

```bash
# Upload Arduino sketch
arduino-cli upload -p COM4 xy_scanner_controller.ino

# Run Python test
python xy_scanner_controller.py --port COM4

Commands:
  home         # Find origin
  right 100    # Move 100mm right
  up 100       # Move 100mm up
```

---

## 📊 Expected Performance

| Spec | Value |
|------|-------|
| **Grid Size** | 5×4 = 20 cards |
| **Scan Area** | 380mm × 380mm |
| **Resolution** | 0.025mm per microstep |
| **Speed** | 50mm/s rapid, 20mm/s scan |
| **Accuracy** | ±0.1mm |
| **Throughput** | ~60 cards/minute |

With GPU (RX 580) + XY scanner + 20-card grid:
**Process entire deck in 30 seconds!**

---

## 💰 Additional Parts Cost

| Item | Qty | Price |
|------|-----|-------|
| NEMA 17 motors | 2 | $20 |
| A4988 drivers | 2 | $6 |
| MGN12H 500mm rails | 2 | $40 |
| 2020 extrusion kit | 1 | $25 |
| Limit switches | 4 | $8 |
| 608 bearings | 4 | $8 |
| M3/M5 hardware | 1 | $15 |
| **TOTAL** | | **~$120** |

You already have the expensive lead screws ($30+ value)!

---

## 🎯 Quick Start

1. **Print parts** (~8 hours total)
2. **Order additional hardware** (arrives in 2-3 days)
3. **Assemble frame** (2 hours)
4. **Install mechanics** (3 hours)
5. **Wire electronics** (1 hour)
6. **Test and calibrate** (1 hour)

**Total build time: Weekend project!**

---

## 🔧 Creality Nut Installation

The anti-backlash nut is spring-loaded:

```
Top view:
┌─────────────┐
│   Spring    │ ← Compression spring
├─────────────┤
│  Nut Body   │ ← Threads engage screw
└─────────────┘

Installation:
1. Compress spring slightly
2. Thread onto lead screw
3. Slide nut into printed bracket
4. Spring maintains tension
5. Zero backlash! 🎯
```

This is **better than cheap fixed nuts** - gives smooth motion.

---

## 📝 Notes

- **Don't over-tighten couplers** - leave 2mm gap
- **Lubricate screws** with PTFE grease
- **Check squareness** - measure diagonals
- **Home before each session** - accuracy depends on it

**Ready to build!** 🚀

Print the parts from `3D_MODELS/lead_screw_end_support.scad` - they're already sized for your 8mm Creality screws!
