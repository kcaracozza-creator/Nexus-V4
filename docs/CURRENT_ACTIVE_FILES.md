# MTTGG - Current Active Files
**Last Updated:** November 14, 2025

## Arduino Firmware (E:\MTTGG\Arduino)
### ACTIVE - Use These:
- **No_Bullshit_Motors/** - CURRENT FIRMWARE - Motors + IR sensors + automation (no NeoPixels)
- **Buffalo_Bills_Balls/** - Previous automation firmware (backup)
- **Motors_Plus_IR_Sensors/** - Basic motor + sensor test
- **BARE_BONES_Motors_Only_2_4_5_6/** - Minimal motor test (pins 2,4,5,6)
- **Basic_Automation_Timer/** - Timer-based automation test

### Configuration:
- Motor 1: DIR=Pin 2, PWM=Pin 5 (card ejection)
- Motor 2: DIR=Pin 4, PWM=Pin 6 (conveyor)
- Stage IR: Pin 9 (HW201 card detection)
- Line IR: Pin 8 (ejection proof)
- Serial: COM5, 9600 baud

---

## Python Scripts (E:\MTTGG\PYTHON SOURCE FILES)
### ACTIVE - Core System:
- **mtg_core.py** - Main MTG collection/deck building application
- **nikon_camera_integration.py** - Camera integration for card scanning
- **test_motors_simple.py** - Motor testing script
- **test_ir_sensors.py** - IR sensor testing
- **test_buffalo_bills_balls.py** - Automation test script
- **test_twinkle_simple.py** - Simple test script (motors only now)

### Current Test Script:
```python
# test_motors_simple.py - Updated for COM5
# Tests Motor 1 and Motor 2 forward/stop
```

---

## Arduino Commands
```
M1F/M1R/M1S - Motor 1 Forward/Reverse/Stop
M2F/M2R/M2S - Motor 2 Forward/Reverse/Stop
A - Toggle AUTO mode
P - Photo complete (triggers ejection)
S - Status (shows sensor states)
```

---

## Archived Files
All old test scripts, backup files, obsolete firmware, and documentation moved to:
- **E:\MTTGG\_ARCHIVE\Old_Arduino_Sketches/**
- **E:\MTTGG\_ARCHIVE\Old_Test_Scripts/**
- **E:\MTTGG\_ARCHIVE\Old_Batch_Scripts/**
- **E:\MTTGG\_ARCHIVE\Backup_Files/**
- **E:\MTTGG\_ARCHIVE/** (documentation .md files)

---

## What Got Cleaned Up:
✅ Removed Twinkle_Tits (NeoPixel issues)
✅ Archived 40+ .backup and .syntax_backup files
✅ Moved old motor test scripts (test_exact_250, voltage_test, etc.)
✅ Moved syntax fixer scripts (nuclear_option, emergency_fixer, etc.)
✅ Moved old batch/PowerShell launch scripts
✅ Moved documentation files to archive (kept README.md)
✅ Removed obsolete Arduino sketches

---

## Next Steps:
1. Upload **No_Bullshit_Motors.ino** to Arduino
2. Test full automation cycle with cards
3. Integrate Nikon camera for photo capture
4. Validate complete workflow
python camera_automation.pypython camera_automation.pypython camera_automation.py





