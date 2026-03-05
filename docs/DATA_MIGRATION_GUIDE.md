# NEXUS Data Migration Guide

## Moving from E:\MTTGG to Portable Structure

After running `fix_paths.py`, you need to migrate your data files to the new portable structure.

---

## Step 1: Run the Path Fixer

```bash
python fix_paths.py
```

This will:
- ✅ Fix all hardcoded E:\ paths in the code
- ✅ Create the new directory structure
- ✅ Add portable path configuration

---

## Step 2: Copy Your Data Files

### From E:\MTTGG\ to new structure:

```
OLD LOCATION                                  →  NEW LOCATION
================================================================

E:\MTTGG\MASTER  SHEETS\Master File .csv     →  data\Master_File.csv
E:\MTTGG\MASTER  SHEETS\cards.csv            →  data\cards.csv
E:\Downloads\Master File.csv                  →  data\Master_File.csv

E:\MTTGG\nexus_library.json                  →  data\nexus_library.json
E:\MTTGG\gestix_collection.csv               →  data\gestix_collection.csv
E:\MTTGG\box_labels.txt                      →  data\box_labels.txt

E:\MTTGG\nexus_background.jpg                →  assets\nexus_background.jpg

E:\MTTGG\Inventory\*.csv                     →  data\inventory\*.csv
E:\MTTGG\Decklist templates\*.txt            →  data\deck_templates\*.txt
E:\MTTGG\Saved Decks\*.txt                   →  data\saved_decks\*.txt

E:\MTTGG\JSON\*.json                         →  data\json\*.json

E:\MTTGG\Card_Images\*.jpg                   →  assets\card_images\*.jpg

E:\MTTGG\PYTHON SOURCE FILES\mttgg_config.json  →  config\mttgg_config.json

E:\MTTGG\recognition_cache\*                 →  cache\recognition_cache\*

E:\MTTGG\MOTOR_2_TROUBLESHOOTING_GUIDE.md    →  docs\MOTOR_2_TROUBLESHOOTING_GUIDE.md
E:\MTTGG\MOTOR_2_WIRING_CHECK.md             →  docs\MOTOR_2_WIRING_CHECK.md

E:\MTTGG\ARDUINO_SKETCHES\*.ino              →  arduino_sketches\*.ino
```

---

## Step 3: Quick Copy Script (Windows)

Save this as `migrate_data.bat`:

```batch
@echo off
echo Migrating NEXUS data files to portable structure...

REM Master database files
copy "E:\MTTGG\MASTER  SHEETS\Master File .csv" "data\Master_File.csv"
copy "E:\MTTGG\MASTER  SHEETS\cards.csv" "data\cards.csv"

REM Library data
copy "E:\MTTGG\nexus_library.json" "data\nexus_library.json"
copy "E:\MTTGG\gestix_collection.csv" "data\gestix_collection.csv"

REM Assets
copy "E:\MTTGG\nexus_background.jpg" "assets\nexus_background.jpg"

REM Config
copy "E:\MTTGG\PYTHON SOURCE FILES\mttgg_config.json" "config\mttgg_config.json"

REM Inventory (all CSV files)
xcopy "E:\MTTGG\Inventory\*.csv" "data\inventory\" /Y

REM Deck templates
xcopy "E:\MTTGG\Decklist templates\*" "data\deck_templates\" /Y

REM Saved decks
xcopy "E:\MTTGG\Saved Decks\*" "data\saved_decks\" /Y

REM JSON files
xcopy "E:\MTTGG\JSON\*.json" "data\json\" /Y

REM Documentation
copy "E:\MTTGG\MOTOR_2_TROUBLESHOOTING_GUIDE.md" "docs\" 2>nul
copy "E:\MTTGG\MOTOR_2_WIRING_CHECK.md" "docs\" 2>nul

REM Arduino sketches
xcopy "E:\MTTGG\ARDUINO_SKETCHES\*.ino" "arduino_sketches\" /Y 2>nul

echo.
echo ✅ Migration complete!
echo.
echo Test NEXUS now to make sure everything works.
pause
```

---

## Step 4: Test on Your Machine

1. Run `nexus.py`
2. Check that it loads your 26,850 cards
3. Test search functionality
4. Verify all features work

---

## Step 5: Test on Clean Machine (CRITICAL)

**Before deploying to Shop 1:**

1. Copy the ENTIRE folder to a USB drive
2. Plug into a laptop that does NOT have E:\ drive
3. Run NEXUS
4. Make sure it works

**If it fails:**
- Check error messages
- Verify all data files copied correctly
- Make sure no E:\ paths remain

---

## Final Portable Structure

```
NEXUS/
├── nexus.py
├── nexus_library_system.py
├── import_gestix.py
├── fix_paths.py
├── requirements.txt
│
├── data/
│   ├── Master_File.csv (106,804 cards)
│   ├── cards.csv
│   ├── nexus_library.json (your 26,850 cataloged cards)
│   ├── gestix_collection.csv
│   ├── inventory/
│   ├── deck_templates/
│   ├── saved_decks/
│   └── json/
│
├── assets/
│   ├── nexus_background.jpg
│   └── card_images/
│
├── cache/
│   └── recognition_cache/
│
├── config/
│   └── mttgg_config.json
│
├── docs/
│   ├── MOTOR_2_TROUBLESHOOTING_GUIDE.md
│   └── MOTOR_2_WIRING_CHECK.md
│
├── arduino_sketches/
│   └── scooby_3channel.ino
│
└── backups/
    └── (automatic backups will go here)
```

---

## Troubleshooting

**Problem:** NEXUS won't start after migration

**Solution:** Check that Master_File.csv is in data/ folder

---

**Problem:** Can't find card images

**Solution:** Copy card images to assets/card_images/

---

**Problem:** Library is empty (shows 0 cards)

**Solution:** Make sure nexus_library.json is in data/ folder

---

**Problem:** Still getting E:\ errors

**Solution:** Run fix_paths.py again, check for any paths we missed

---

## Ready to Deploy?

Once NEXUS works on a clean machine:

✅ You're ready to deploy to Shop 1!

**Next steps:**
1. Create installer (see INSTALLER_CREATION_GUIDE.md)
2. Package everything for shops
3. Schedule Shop 1 deployment

---

**Questions? Issues?**

Check the console output for specific error messages and paths that failed.

