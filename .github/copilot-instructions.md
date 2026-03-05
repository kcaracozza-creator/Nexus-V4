# NEXUS - MTG Card Management System

## Project Overview

NEXUS is a comprehensive Magic: The Gathering card management system with automated scanning, AI-powered deck building, marketplace integration, and business intelligence. The system combines hardware (Arduino-based card scanner with DSLR camera), AI recognition, and a full-featured Tkinter GUI application.

**Main Entry Point:** `PYTHON SOURCE FILES/nexus.py` (9,249 lines, ~179 modules)

## Architecture

### Core System Components

1. **nexus.py** - Main GUI application (`MTTGGCompleteSystem` class)
   - Modular design with graceful degradation (optional imports with `*_AVAILABLE` flags)
   - Gothic-themed dark UI (#0d0d0d background, parchment text #e8dcc4)
   - 13 major tabs: Scanner, Deck Builder, Library, Marketplace, Analytics, Hardware, etc.

2. **Hardware Integration**
   - `arduino_hardware_interface_v2.py` - Serial communication with Arduino
   - `fixed_nikon_camera.py` - DSLR camera control (DirectShow backend)
   - Automated mechanical card scanner (motors, IR sensors, NeoPixel lighting)

3. **AI & Recognition**
   - `ai_card_recognition_v2.py` - OCR + fuzzy matching (Tesseract)
   - `ai_deck_optimizer.py` - Meta analysis, investment tracking, trading bot
   - `recognition_confirmation_gui.py` - 100% accuracy failsafe dialogs

4. **Deck Building**
   - `commander_deck_builder_numpy.py` - Multi-format builder (Commander, Standard, Modern, etc.)
   - NumPy-optimized with Scryfall pricing integration
   - Supports folder-based collection loading from `E:\MTTGG\Inventory\*.csv`

5. **Business & Data Systems**
   - `nexus_library_system.py` - Dewey Decimal organization for cards
   - `card_intake_system.py` - Acquisition tracking
   - `nexus_marketplace.py` - Internal P2P trading
   - `customer_analytics.py` - ROI tracking and reports
   - `business_intelligence.py` - Forecasting and trends
   - `quickbooks_integration.py` - CSV export for accounting

### Configuration & Portability

**NEW:** `config_manager.py` provides environment-based configuration:
- Checks `CONFIG_AVAILABLE` flag before using
- Falls back to hardcoded paths (`E:\MTTGG\*`) in legacy mode
- Uses JSON configs (`config/default.json`, `config/local.json`) + `.env` overrides

```python
# Modern portable pattern:
if CONFIG_AVAILABLE and config:
    base_dir = config.get_path('base_dir').parent
    self.inventory_folder = str(base_dir / "Inventory")
else:
    # Legacy hardcoded fallback
    self.inventory_folder = r"E:\MTTGG\Inventory"
```

### Data File Locations

| Type | Path | Description |
|------|------|-------------|
| Master DB | `MASTER  SHEETS/Master File .csv` | Complete card database with types/colors |
| Inventory | `Inventory/*.csv` | Collection files (combined quantities) |
| Scryfall | `JSON/default-cards-*.json` | Bulk card data |
| Cache | `SCRYFALL_CACHE/` | Local Scryfall cache |
| Decks | `Saved Decks/*.txt` | Generated decklists |
| Templates | `Decklist templates/*.csv` | Pre-built deck templates |
| Images | `Card_Images/` | Card image cache |

## Development Workflows

### Running the Application

```powershell
cd "E:\MTTGG\PYTHON SOURCE FILES"
python nexus.py
```

**Auto-loads Inventory folder on startup** (see `auto_load_collection()` method)

### Testing Deck Builder

```powershell
# Quick test with collection loading
python -c "from commander_deck_builder_numpy import CommanderDeckBuilder; db = CommanderDeckBuilder(); count = db.load_collection_folder('E:/MTTGG/Inventory'); print(f'Loaded {count} cards'); deck = db.build_deck('Commander', strategy='balanced'); print(f'Built {len(deck)} cards')"
```

### Hardware Testing

- `test_arduino_direct.py` - Basic Arduino communication
- `test_dslr_camera.py` - DSLR capture tests
- `complete_mechanical_test.py` - Full scanner validation

### Common Issues

1. **Windows Console Encoding** - Fixed via UTF-8 codec wrapper (lines 14-17 in nexus.py)
2. **Arduino Port Selection** - Use `self.selected_arduino_port` (defaults to "AUTO")
3. **Camera Access** - DirectShow backend required for Nikon DSLRs
4. **Hardcoded deck size** - Always use `deck_size` parameter, not literal `100`
5. **Singleton formats** - Pass `max_copies=1` to `_add_by_type()` in deck builders

## Code Conventions

### Module Import Pattern

```python
try:
    from module_name import ClassName
    MODULE_AVAILABLE = True
    print("✅ Module loaded")
except ImportError:
    MODULE_AVAILABLE = False
    print("⚠️ Module not available")
```

Always check `*_AVAILABLE` flags before using optional features.

### UI Color Scheme

```python
self.colors = {
    'bg_dark': '#0d0d0d',           # Deep black stone
    'bg_medium': '#2a1a2e',         # Dark purple shadow
    'accent_blood': '#8b0000',      # Dark blood red
    'accent_royal': '#4b0082',      # Deep royal purple
    'text_light': '#e8dcc4',        # Parchment cream
    'text_gold': '#d4af37'          # Ancient gold
}
```

**Use `tk.Frame` with `bg='#0d0d0d'` for dark frames** (not `ttk.Frame`)

### Deck Format Constants

```python
FORMATS = ["Commander", "Standard", "Modern", "Pioneer", "Legacy", "Vintage", "Pauper", "Brawl"]
```

Commander = 100 cards (singleton), Standard/Modern = 60 cards (4x limit)

### Collection Loading

**Always prefer folder loading** over single file:
```python
# Combines all CSV files, sums quantities
count = deck_builder.load_collection_folder('E:/MTTGG/Inventory')
```

## Integration Points

### Scryfall API
- Rate limited: 100ms delays between requests
- Cache in `scryfall_cache` for offline access
- Price data from `scryfall_scraper.py`

### Arduino Protocol
- JSON commands over serial: `{"action": "SCAN_START", ...}`
- Status polling: `{"action": "STATUS"}` returns system state
- Hardware states: `system_ready`, `card_in_position`, `scanning`

### Untapped.gg Import
- `untapped_importer.py` - Import decklists from Untapped
- Uses web scraping + API when available

## Key Dependencies

- **tkinter** - GUI framework (no ttk for dark backgrounds)
- **numpy** - Deck building optimization
- **opencv-cv2** - Camera capture
- **pytesseract** - OCR recognition
- **pyserial** - Arduino communication
- **requests** - API calls (Scryfall, TCGPlayer)
- **Pillow** - Image processing

## Testing Strategy

1. **Module isolation** - Each component has `test_*.py` file
2. **Hardware first** - Validate Arduino/camera before GUI tests
3. **Collection required** - Deck building needs loaded inventory
4. **Exit codes** - 0 = success, 1 = error (check terminal history)

## Notes for AI Agents

- **Graceful degradation** - System works with missing optional modules
- **Path flexibility** - Use `CONFIG_AVAILABLE` check for portable vs hardcoded paths
- **No batch completions** - Update status after each operation
- **Windows-specific** - PowerShell commands, backslash paths, UTF-8 encoding fixes
- **Large file handling** - Master File .csv = ~70k cards, use streaming/chunking
- **Gothic theme consistency** - Dark backgrounds, parchment text, blood-red accents

## Quick Reference

```python
# Check if module is available
if ENHANCED_DECK_BUILDER_AVAILABLE:
    deck = self.enhanced_deck_builder.build_deck('Commander')

# Load collection from folder
count = self.enhanced_deck_builder.load_collection_folder(self.inventory_folder)

# Update status bar
self.update_status("✅ Operation complete")

# Hardware command
response = self.arduino.send_command("EJECT")

# Get card price
price = self.scryfall_scraper.get_card_price("Lightning Bolt")
```
