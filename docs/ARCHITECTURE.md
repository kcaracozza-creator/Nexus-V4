# NEXUS Architecture Documentation

## 🏗️ System Overview

NEXUS is built as a modular, extensible platform designed to scale from individual collectors to enterprise shop chains. The architecture prioritizes:

- **Modularity**: Each subsystem is independent and replaceable
- **Scalability**: Designed to handle 1M+ cards and 10,000+ shops
- **Extensibility**: Easy to add new card games, features, and integrations
- **Performance**: Optimized for real-time operations and AI processing

---

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NEXUS Application (GUI)                  │
│                       nexus.py (10,010 lines)                │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌─────▼─────┐
    │  Library │          │  Scanner  │
    │  System  │          │  Module   │
    └────┬─────┘          └─────┬─────┘
         │                      │
    ┌────▼──────────────────────▼────┐
    │         Core Modules            │
    │  ┌──────────────────────────┐  │
    │  │ scanner/  (Recognition)  │  │
    │  │ scrapers/ (Data Fetch)   │  │
    │  │ deck_builder/ (AI)       │  │
    │  │ analytics/ (BI)          │  │
    │  │ marketplace/ (Trading)   │  │
    │  └──────────────────────────┘  │
    └────┬───────────────────────┬────┘
         │                       │
    ┌────▼─────┐          ┌─────▼─────┐
    │ External │          │ Hardware  │
    │   APIs   │          │  Devices  │
    └──────────┘          └───────────┘
```

---

## 🧩 Core Components

### 1. Main Application (`nexus.py`)

**Purpose**: Primary GUI application and orchestration layer

**Responsibilities**:
- User interface (Tkinter-based)
- Tab management (Library, Deck Builder, Scanner, Analytics, etc.)
- Event handling and user interactions
- Coordinate between subsystems
- Application lifecycle management

**Key Classes**:
- `NexusApp`: Main application window and tab coordinator
- Tab-specific frames for each major feature

**Size**: 10,010 lines (consolidated from multiple legacy systems)

---

### 2. Library System (`nexus_library_system.py`)

**Purpose**: Card database and collection management

**Responsibilities**:
- SQLite database for collections
- Card data storage and retrieval
- Collection statistics and analytics
- Import/export functionality
- Search and filtering

**Database Schema**:
```sql
CREATE TABLE cards (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    set_code TEXT,
    collector_number TEXT,
    quantity INTEGER DEFAULT 1,
    condition TEXT,
    foil BOOLEAN,
    price REAL,
    date_added TIMESTAMP,
    UNIQUE(name, set_code, collector_number, foil)
);

CREATE TABLE decks (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    format TEXT,
    commander TEXT,
    date_created TIMESTAMP,
    last_modified TIMESTAMP
);

CREATE TABLE deck_cards (
    deck_id INTEGER,
    card_id INTEGER,
    quantity INTEGER,
    category TEXT,  -- 'main', 'sideboard', 'commander'
    FOREIGN KEY (deck_id) REFERENCES decks(id),
    FOREIGN KEY (card_id) REFERENCES cards(id)
);
```

---

### 3. Scanner Module (`nexus_scanner_module.py`)

**Purpose**: Hardware integration and network scanner support

**Responsibilities**:
- Coordinate multiple scanner sources
- Network scanner protocol
- Hardware abstraction layer
- Real-time scanning operations

**Supported Scanner Types**:
- Local camera (USB webcam, 8K camera)
- Raspberry Pi remote scanner
- Android mobile scanner
- Network scanner clients

---

### 4. Module Ecosystem

#### A. Scanner Module (`modules/scanner/`)

**Files**:
- `simple_camera_scanner.py`: Basic camera operations
- `ai_card_recognition_v2.py`: Computer vision + OCR
- `recognition_confirmation_gui.py`: User verification interface

**Technologies**:
- OpenCV: Image capture and processing
- Tesseract OCR: Text recognition
- NumPy: Image array manipulation
- Fuzzy matching: Name disambiguation

**Process Flow**:
```
Camera Capture → Image Processing → OCR →
Fuzzy Match → Scryfall Lookup → Confirmation → Add to Collection
```

#### B. Scrapers Module (`modules/scrapers/`)

**Files**:
- `scryfall_scraper.py`: Scryfall API integration
- `tcgplayer_scraper.py`: TCGPlayer price data

**Scryfall Integration**:
```python
class ScryfallScraper:
    def search_card(name: str) -> dict:
        """Search for card by name"""
        # API: https://api.scryfall.com/cards/named
        
    def get_card_by_set(name: str, set_code: str) -> dict:
        """Get specific printing"""
        
    def get_bulk_data() -> list:
        """Download complete card database"""
        
    def get_card_image(name: str) -> PIL.Image:
        """Download card image"""
```

**Caching Strategy**:
- Local image cache: `Card_Images/`
- JSON cache: `scryfall_data_cache.json`
- 24-hour TTL for price data
- Persistent cache for card data

#### C. Deck Builder Module (`modules/deck_builder/`)

**Files**:
- `commander_deck_builder.py`: Original deck builder
- `commander_deck_builder_numpy.py`: NumPy-optimized version

**AI Features**:
- Mana curve optimization
- Color distribution balancing
- Synergy detection (keyword matching)
- Budget optimization
- Format legality checking

**Deck Building Algorithm**:
```python
def build_deck(commander: str, strategy: str) -> Deck:
    # 1. Analyze commander abilities
    commander_colors = get_color_identity(commander)
    commander_keywords = extract_keywords(commander)
    
    # 2. Score available cards
    for card in collection:
        score = 0
        score += color_match_score(card, commander_colors)
        score += synergy_score(card, commander_keywords)
        score += mana_curve_score(card, current_curve)
        score += meta_score(card, format_meta)
        
    # 3. Select top cards by score
    deck_cards = select_top_cards(scored_cards, 99)
    
    # 4. Optimize mana base
    lands = calculate_mana_base(deck_cards, commander_colors)
    
    return Deck(commander, deck_cards + lands)
```

**NumPy Optimization**:
- Vectorized scoring operations
- Matrix operations for synergy calculations
- 10-100x faster than loop-based approach

#### D. Analytics Module (`modules/analytics/`)

**Files**:
- `customer_analytics.py`: Business intelligence

**Features**:
- Sales tracking
- Customer segmentation
- Inventory turnover
- Profit margin analysis
- Purchase patterns

#### E. Marketplace Module (`modules/marketplace/`)

**Files**:
- `nexus_marketplace.py`: P2P trading platform

**Features** (Planned):
- Seller listings
- Buyer search
- Transaction handling
- Rating system
- Escrow integration

---

### 5. Configuration System (`config/config_manager.py`)

**Purpose**: Portable, environment-aware configuration

**Features**:
- Auto-detect USB drive vs. local installation
- Environment-specific paths
- API key management
- Hardware configuration
- User preferences

**Config Structure**:
```python
{
    "system": {
        "mode": "usb" | "local",
        "install_path": "E:/MTTGG/PYTHON SOURCE FILES"
    },
    "paths": {
        "master_file": "E:/MTTGG/MASTER SHEETS/Master File .csv",
        "inventory": "E:/MTTGG/Inventory",
        "card_images": "E:/MTTGG/Card_Images"
    },
    "scanner": {
        "camera_index": 1,
        "arduino_port": "COM3",
        "led_pin": 13
    },
    "api": {
        "scryfall": "https://api.scryfall.com",
        "tcgplayer_key": "..."
    }
}
```

---

## 🔄 Data Flow

### Scanning Workflow

```
User clicks "Scan Card"
    ↓
nexus.py → nexus_scanner_module.py
    ↓
simple_camera_scanner.py captures image
    ↓
ai_card_recognition_v2.py processes image
    ↓
Tesseract OCR extracts text
    ↓
Fuzzy match against Scryfall database
    ↓
recognition_confirmation_gui.py shows results
    ↓
User confirms
    ↓
nexus_library_system.py adds to collection
    ↓
Update inventory, statistics, UI
```

### Deck Building Workflow

```
User selects "Build Deck"
    ↓
nexus.py → commander_deck_builder_numpy.py
    ↓
Load collection from nexus_library_system.py
    ↓
Fetch meta data from scryfall_scraper.py
    ↓
AI scoring algorithm evaluates cards
    ↓
Select optimal 99 + lands
    ↓
Generate decklist
    ↓
Test deck in battle_simulator
    ↓
Display results and save to Generated Decks/
```

---

## 🔌 External Integrations

### Scryfall API

**Base URL**: `https://api.scryfall.com`

**Key Endpoints**:
- `/cards/named?fuzzy={name}`: Fuzzy card search
- `/cards/search?q={query}`: Advanced search
- `/bulk-data`: Full database download
- `/cards/{set}/{number}`: Specific card

**Rate Limits**:
- 10 requests per second
- Respect 50-100ms delays
- Use bulk data for initialization

### TCGPlayer (Scraping)

**Method**: Web scraping (no official API for pricing)
**Caching**: Essential due to rate limits
**Fallback**: Scryfall prices if TCGPlayer unavailable

### Hardware APIs

**Arduino**:
- Protocol: Serial (9600 baud)
- Commands: `MOTOR_1_FWD`, `LED_ON`, `SCAN`, etc.
- Firmware: Custom (included in repo)

**Camera**:
- OpenCV VideoCapture
- DirectShow backend (Windows)
- V4L2 backend (Linux)

---

## 🚀 Performance Optimizations

### 1. Database Indexing

```sql
CREATE INDEX idx_cards_name ON cards(name);
CREATE INDEX idx_cards_set ON cards(set_code);
CREATE INDEX idx_deck_cards_deck ON deck_cards(deck_id);
```

### 2. Image Caching

- Cache all Scryfall images locally
- Lazy loading (only load when viewed)
- Thumbnail generation for grid views

### 3. NumPy Vectorization

**Before**:
```python
# Slow loop
for card in cards:
    score = calculate_score(card)
```

**After**:
```python
# Fast vectorized
scores = np.dot(card_features, weight_matrix)
```

**Result**: 10-100x faster deck building

### 4. Lazy Initialization

- Don't load Scryfall database until needed
- Defer hardware initialization
- Background thread for slow operations

---

## 🔐 Security Considerations

### API Keys

- Store in `.env` files (gitignored)
- Never commit to repository
- Use config_manager for secure access

### User Data

- Collections are local SQLite
- No cloud storage without explicit opt-in
- User controls all data

### Hardware Safety

- Firmware includes safety limits
- Motor timeouts prevent damage
- LED brightness limits

---

## 🧪 Testing Strategy

### Current State

- Manual testing during development
- Hardware tested on actual devices
- Battle simulator for deck validation

### Future Plans

```python
# Unit tests
def test_deck_legality():
    deck = build_commander_deck(...)
    assert deck.is_legal()
    assert len(deck.mainboard) == 99
    
# Integration tests
def test_scanning_workflow():
    image = load_test_image()
    card = scanner.scan(image)
    assert card.name == "Lightning Bolt"
    
# Performance tests
def test_deck_building_speed():
    start = time.time()
    deck = build_deck(collection_1000)
    assert time.time() - start < 5.0  # 5 sec max
```

---

## 📈 Scalability Plan

### Phase 1: Individual Users (Current)
- Single-user application
- Local database
- Manual scanning

### Phase 2: Small Shops (2025-2026)
- Multi-user support
- Network database (PostgreSQL)
- Automated scanning
- API server for remote access

### Phase 3: Shop Chains (2027+)
- Cloud infrastructure (AWS/Azure)
- Multi-location inventory
- Real-time sync
- Mobile apps
- Marketplace platform

---

## 🔮 Future Architecture

```
                    ┌─────────────┐
                    │   Mobile    │
                    │    Apps     │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼─────┐      ┌────▼─────┐      ┌────▼─────┐
   │  Desktop │      │   Web    │      │   API    │
   │  Client  │      │  Portal  │      │ Partners │
   └────┬─────┘      └────┬─────┘      └────┬─────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                    ┌──────▼──────┐
                    │    Cloud    │
                    │   Backend   │
                    │  (FastAPI)  │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼─────┐      ┌────▼─────┐      ┌────▼─────┐
   │PostgreSQL│      │   Redis  │      │    S3    │
   │ Database │      │   Cache  │      │  Storage │
   └──────────┘      └──────────┘      └──────────┘
```

---

## 📚 Additional Resources

- [Scryfall API Documentation](https://scryfall.com/docs/api)
- [MTG Comprehensive Rules](https://magic.wizards.com/en/rules)
- [NumPy Performance Guide](https://numpy.org/doc/stable/user/performance.html)
- [Tkinter Documentation](https://docs.python.org/3/library/tkinter.html)

---

**Last Updated**: November 26, 2025
