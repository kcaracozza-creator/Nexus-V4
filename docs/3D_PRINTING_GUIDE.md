# 3D Printing Guide for MTTGG Automated Card Sorter

## Overview
This guide covers all 3D printed components needed for the automated card sorting system housed in a PC tower case. Parts can be printed from the included SCAD/STL files or custom STEP files.

---

## Required 3D Printed Parts

### 1. Lead Screw End Supports (4 pieces)
**File:** `3D_MODELS/lead_screw_end_support.scad` or `.stl`
- **Purpose:** SK8-style bearing mounts for 8mm lead screws
- **Quantity:** 4 (2 per axis, both ends)
- **Material:** PETG or ABS (PLA acceptable for low-load applications)
- **Print Settings:**
  - Layer Height: 0.2mm
  - Infill: 50%
  - Perimeters: 3-4
  - Supports: None required
  - Print Time: ~45 minutes each
- **Post-Processing:** 
  - Install 608 bearing (8mm ID, 22mm OD, 7mm thick)
  - Tap M5 holes or use heat-set inserts
- **Notes:** Critical dimension is 8.2mm center hole for lead screw clearance

### 2. Linear Rail Mounts (8 pieces)
**File:** `3D_MODELS/mgn12h_rail_mount.scad` or `.stl`
- **Purpose:** Mount MGN12H linear rails to frame
- **Quantity:** 8 (4 per rail, 2 rails total)
- **Material:** PETG or ABS
- **Print Settings:**
  - Layer Height: 0.2mm
  - Infill: 40%
  - Perimeters: 3
  - Supports: None
  - Print Time: ~30 minutes each
- **Mounting:** M3 screws to rail, M5 screws to 2020 extrusion

### 3. Lead Nut Brackets (2 pieces)
**File:** `3D_MODELS/lead_nut_bracket.scad` or `.stl`
- **Purpose:** Connect T8 anti-backlash nut to XY carriage
- **Quantity:** 2 (one per axis)
- **Material:** PETG or ABS (high strength required)
- **Print Settings:**
  - Layer Height: 0.15mm (critical for screw threads)
  - Infill: 60-80%
  - Perimeters: 4
  - Supports: None
  - Print Time: ~35 minutes each
- **Post-Processing:** May need light reaming of center hole for nut fit

### 4. NEMA 17 Motor Mounts (2 pieces)
**File:** `3D_MODELS/nema17_mount.scad` or `.stl`
- **Purpose:** Mount stepper motors to lead screw ends
- **Quantity:** 2 (one per axis)
- **Material:** PETG or ABS
- **Print Settings:**
  - Layer Height: 0.2mm
  - Infill: 50%
  - Perimeters: 4
  - Supports: None (design has built-in support geometry)
  - Print Time: ~1 hour each
- **Hardware:** M3 screws for motor (31mm spacing), M5 for frame

### 5. Roller Feed Mounts (2 pieces)
**File:** Provided by user as `shuffler.step` or custom design
- **Purpose:** Mount roller servo at card dispensing position
- **Quantity:** 2 (left and right sides)
- **Material:** PETG (food-safe for card contact)
- **Print Settings:**
  - Layer Height: 0.2mm
  - Infill: 40%
  - Perimeters: 3
  - Print Time: ~varies by design
- **Notes:** Must align roller 5mm above pickup position

### 6. Servo Mounts (2 pieces)
**File:** User's `ServoMount1.stl` and `ServoMount2.stl`
- **Purpose:** Mount stopper servo and Z-axis servo
- **Quantity:** 2 (stopper + Z-axis)
- **Material:** PLA or PETG
- **Print Settings:**
  - Layer Height: 0.2mm
  - Infill: 30%
  - Perimeters: 3
  - Print Time: ~20 minutes each

### 7. Card Stopper
**File:** User's `Stopper.stl`
- **Purpose:** Control card stack in hopper (prevents avalanche)
- **Quantity:** 1
- **Material:** PLA (smooth surface for card contact)
- **Print Settings:**
  - Layer Height: 0.15mm (smooth finish)
  - Infill: 30%
  - Perimeters: 3
  - Top/Bottom Layers: 5 (smooth surface)
  - Print Time: ~15 minutes
- **Post-Processing:** Light sanding for smooth card contact

### 8. Bin Dividers (3 pieces)
**File:** `3D_MODELS/sorting_bin_divider.scad` or `.stl`
- **Purpose:** Separate 4 sorting bins at bottom of tower
- **Quantity:** 3 (creates 4 compartments)
- **Material:** PLA or PETG
- **Print Settings:**
  - Layer Height: 0.3mm (fast print, low detail)
  - Infill: 20%
  - Perimeters: 2
  - Print Time: ~45 minutes each
- **Dimensions:** Custom fit to PC tower width (~180mm)

### 9. Camera Mount
**File:** `3D_MODELS/camera_overhead_mount.scad` or `.stl`
- **Purpose:** Hold camera 200-250mm above card scan position
- **Quantity:** 1
- **Material:** PETG (rigidity, vibration resistance)
- **Print Settings:**
  - Layer Height: 0.2mm
  - Infill: 50%
  - Perimeters: 4
  - Print Time: ~1.5 hours
- **Adjustability:** Design includes slots for height/angle adjustment

### 10. Cable Management Clips (10-15 pieces)
**File:** `3D_MODELS/cable_clip.scad` or `.stl`
- **Purpose:** Route stepper/servo cables inside PC tower
- **Quantity:** 10-15 (as needed)
- **Material:** PLA (disposable, easy to print)
- **Print Settings:**
  - Layer Height: 0.3mm
  - Infill: 20%
  - Perimeters: 2
  - Print Time: ~5 minutes each
- **Mounting:** Adhesive backing or M3 screws

---

## Accepting STEP Files from Contributors

### STEP File Specifications

If someone wants to provide you with custom parts (improved designs, remixes, add-ons), request STEP files with these specifications:

#### General Requirements
- **Format:** STEP AP214 (.step or .stp extension)
- **Units:** Millimeters (mm)
- **Origin:** Clearly defined (typically bottom-left corner or center)
- **Orientation:** Print-ready (flat side on XY plane)
- **File Naming:** Descriptive (e.g., `improved_motor_mount_v2.step`)

#### Critical Dimensions to Communicate
When requesting custom parts, provide these constraints:

**For Lead Screw Components:**
- Lead screw diameter: **8mm**
- Lead screw pitch: **8mm** (T8 4-start)
- Bearing size: **608** (8mm ID, 22mm OD, 7mm thick)
- Frame extrusion: **2020** (20mm × 20mm aluminum)

**For Linear Rail Components:**
- Rail type: **MGN12H**
- Carriage mounting holes: **20mm spacing**
- Rail bolt pattern: **15mm spacing**

**For Motor Mounts:**
- Motor type: **NEMA 17**
- Mounting holes: **31mm spacing** (M3 screws)
- Shaft diameter: **5mm**
- Shaft flat: **0.5mm deep** (for coupler)

**For Servo Mounts:**
- Servo type: **SG90** or **MG90S** (standard micro servo)
- Mounting tabs: **28mm spacing**
- Body dimensions: **23mm × 12.5mm × 29mm**

**For PC Tower Integration:**
- Maximum width: **180mm** (fits inside ATX mid-tower)
- Maximum depth: **380mm** (limited by lead screw length)
- Maximum height: **400mm** (tower internal height)
- Clearance: **5mm minimum** from case walls

#### Conversion Workflow

**If you receive a STEP file:**

1. **Open in FreeCAD** (free, open-source):
   ```bash
   # Install FreeCAD
   # Windows: Download from freecad.org
   # Linux: sudo apt install freecad
   
   # Open STEP file
   File > Open > select .step file
   ```

2. **Verify Dimensions:**
   - Use Measure tool (View > Measure distance)
   - Check critical mounting holes
   - Verify clearances

3. **Export to STL:**
   ```
   File > Export > select .stl format
   Settings:
     - Deviation: 0.1mm (high quality)
     - Angular Deflection: 0.5° (smooth curves)
   ```

4. **Slice in Cura/PrusaSlicer:**
   - Import .stl file
   - Apply print settings from this guide
   - Check for overhangs (add supports if needed)
   - Generate G-code

**If you receive other CAD formats:**
- **.STL** - Ready to print (no conversion needed)
- **.OBJ** - Import to FreeCAD, export as STL
- **.3MF** - Native format for modern slicers (use directly)
- **.IGES** - Similar to STEP (FreeCAD can import)
- **.F3D** (Fusion 360) - Open in Fusion 360, export as STEP or STL
- **.SLDPRT** (SolidWorks) - Requires SolidWorks or eDrawings Viewer to convert

---

## Print Settings Reference

### Material Selection Guide

| Part Type | Best Material | Alternative | Why |
|-----------|---------------|-------------|-----|
| End Supports | PETG | ABS | Bearing press-fit, temperature stability |
| Rail Mounts | PETG | ABS | Structural rigidity, low creep |
| Lead Nut Brackets | ABS | PETG | High strength, minimal flex |
| Motor Mounts | PETG | ABS | Vibration resistance, thermal stability |
| Roller Mounts | PETG | PLA | Card contact (smooth, food-safe) |
| Servo Mounts | PLA | PETG | Low load, easy printing |
| Stopper | PLA | PETG | Smooth surface, low friction |
| Bin Dividers | PLA | PETG | Fast print, low strength needed |
| Camera Mount | PETG | ABS | Rigidity, no vibration |
| Cable Clips | PLA | Any | Disposable, bulk printing |

### Universal Print Profile

**For all structural parts (unless specified otherwise):**
```
Layer Height: 0.2mm
First Layer: 0.25mm
Infill: 50%
Infill Pattern: Grid or Gyroid
Perimeters: 3-4
Top/Bottom Layers: 4
Print Speed: 50mm/s (perimeters 30mm/s)
Bed Temperature: 60°C (PLA), 80°C (PETG/ABS)
Nozzle Temperature: 210°C (PLA), 240°C (PETG), 250°C (ABS)
Cooling: 100% (PLA), 50% (PETG), 0% (ABS)
Supports: None (parts designed to print support-free)
Brim: Optional (recommended for ABS to prevent warping)
```

### Time and Material Estimates

**Total Print Time:** ~12-15 hours (all parts)
**Total Material:** ~500-600g filament (~$10-12 material cost)

| Part | Quantity | Time Each | Filament Each | Total Time | Total Filament |
|------|----------|-----------|---------------|------------|----------------|
| End Supports | 4 | 45 min | 25g | 3 hrs | 100g |
| Rail Mounts | 8 | 30 min | 15g | 4 hrs | 120g |
| Lead Nut Brackets | 2 | 35 min | 20g | 1.2 hrs | 40g |
| Motor Mounts | 2 | 1 hr | 35g | 2 hrs | 70g |
| Roller Mounts | 2 | 40 min | 20g | 1.3 hrs | 40g |
| Servo Mounts | 2 | 20 min | 10g | 40 min | 20g |
| Stopper | 1 | 15 min | 8g | 15 min | 8g |
| Bin Dividers | 3 | 45 min | 30g | 2.25 hrs | 90g |
| Camera Mount | 1 | 1.5 hrs | 40g | 1.5 hrs | 40g |
| Cable Clips | 12 | 5 min | 3g | 1 hr | 36g |

---

## Quality Control Checklist

Before installing printed parts, verify:

- [ ] **Dimensional accuracy** - Measure critical holes with calipers
- [ ] **No warping** - Parts sit flat on table
- [ ] **Clean holes** - Remove stringing/elephants foot
- [ ] **Smooth surfaces** - Light sanding where parts contact cards
- [ ] **Heat-set inserts** - Install M3/M5 brass inserts if designed for them
- [ ] **Test fit bearings** - 608 bearings should press-fit snugly
- [ ] **Test fit hardware** - M3/M5 screws thread smoothly
- [ ] **Check strength** - Flex parts gently to detect layer delamination

---

## Assembly Order

Print and install in this sequence to minimize rework:

1. **End Supports** (4) - Install bearings first
2. **Motor Mounts** (2) - Attach motors before frame assembly
3. **Rail Mounts** (8) - Pre-attach to rails
4. **Lead Nut Brackets** (2) - Install anti-backlash nuts
5. **Camera Mount** (1) - Test height before final assembly
6. **Roller/Servo Mounts** (4) - Install servos before mounting
7. **Stopper** (1) - Attach to servo horn
8. **Bin Dividers** (3) - Install after XY frame is complete
9. **Cable Clips** (12) - Add during wiring phase

---

## Troubleshooting Print Issues

### Problem: Bearing doesn't fit in end support
- **Too tight:** Ream hole with 8mm drill bit in small increments
- **Too loose:** Wrap bearing with thin tape or use retaining compound

### Problem: Screw holes too small
- **Solution:** Tap threads with M3/M5 tap, or drill to clearance diameter (3.2mm for M3, 5.2mm for M5)

### Problem: Part warps during printing
- **ABS:** Use heated enclosure, reduce cooling fan
- **PETG:** Reduce bed temperature to 70°C, use glue stick
- **PLA:** Increase bed adhesion (brim, raft, or glue stick)

### Problem: Layer delamination (part splits)
- **Cause:** Insufficient layer adhesion
- **Fix:** Increase nozzle temperature by 5-10°C, slow down print speed

### Problem: Stringing between parts
- **Fix:** Enable retraction (5mm distance, 45mm/s speed for direct drive)
- **Post-processing:** Light heat gun pass or careful cutting

---

## Sharing Your Prints

If you modify or improve any designs, consider sharing:

1. **Export as STEP file** from your CAD software
2. **Include print settings** that worked well
3. **Document changes** from original design
4. **Test thoroughly** before sharing
5. **Upload to Thingiverse/Printables** with attribution to MTTGG project

**Recommended License:** Creative Commons BY-SA 4.0 (allows commercial use with attribution)

---

## Contact for Custom Parts

If you need custom components designed:

1. **Describe the function** (what does it do?)
2. **Provide constraints** (size limits, mounting points)
3. **Include reference images** (sketches, photos of existing parts)
4. **Specify material** (will affect design features)
5. **Request STEP format** for maximum compatibility

**Example Request:**
> "I need a custom camera mount that attaches to 2020 extrusion with M5 bolts, holds a Logitech C920 webcam, and allows 45° tilt adjustment. Maximum height 250mm from bed. Please provide as STEP file for PETG printing."

---

## Resources

**CAD Software (Free):**
- FreeCAD - https://freecad.org
- OpenSCAD - https://openscad.org (code-based modeling)
- Tinkercad - https://tinkercad.com (browser-based, beginner-friendly)

**Slicing Software (Free):**
- Cura - https://ultimaker.com/software/ultimaker-cura
- PrusaSlicer - https://www.prusa3d.com/page/prusaslicer_424/
- SuperSlicer - https://github.com/supermerill/SuperSlicer

**File Repositories:**
- Thingiverse - https://thingiverse.com
- Printables - https://printables.com
- MyMiniFactory - https://myminifactory.com

**STEP File Viewers (Free):**
- FreeCAD (Windows/Linux/Mac)
- eDrawings Viewer (Windows/Mac)
- Online STEP Viewer - https://shapr3d.com/step-viewer

---

## Conclusion

All parts are designed for **standard FDM printers** (Ender 3, Prusa MK3, etc.) with **minimum 200mm × 200mm build volume**. No resin printing or exotic materials required.

**Estimated Total Cost:** $10-12 in filament + time
**Estimated Total Time:** 12-15 hours (can run overnight)

Print in batches to optimize bed space and reduce print time. Parts can be printed in any color - consider using different colors for organization (e.g., X-axis parts in red, Y-axis parts in blue).

**Ready to print?** Start with the end supports and motor mounts - these are the most critical and time-consuming parts.
