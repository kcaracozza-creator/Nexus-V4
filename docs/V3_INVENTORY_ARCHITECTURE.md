# NEXUS V3 Inventory Architecture
**Single Source of Truth: BROK**

## Current Problem (Issue #4)
- Desktop local DB: 26,877 cards
- ZULTAN DB: 26,850 cards
- BROK DB: 35,780 cards (actual client inventory)
- **THREE sources of truth = data corruption risk**

## V3 Solution

### Master Inventory: BROK (192.168.1.174)
```
BROK = Client's physical inventory (what they actually own)
- Storage: ~/nexus_library.db or scanner internal DB
- Size: 35,780 cards (real number)
- API: BROK:5000/api/library/* (needs to be added)
```

### Card Universe: ZULTAN (192.168.1.152:8000)
```
ZULTAN = All possible cards (metadata, prices, images)
- MTG: 521K cards
- Pokemon: 19.8K cards
- Sports: 1.84M cards
- API: Already exists at :8000/api/mtg/search, etc.
```

### Desktop V3: Read-Only Client
```
Desktop = UI that reads from BROK + ZULTAN
- Inventory data: BROK:5000/api/library/*
- Card metadata: ZULTAN:8000/api/{mtg|pokemon|sports}/search
- NO local database files
- NO hardcoded paths
```

## Required Changes

### 1. BROK Needs Library API Endpoints
Add to BROK:5000 (scanner_v3.py or separate service):
```python
GET  /api/library/all          # Get all owned cards
GET  /api/library/search?q=X   # Search owned cards
GET  /api/library/stats        # Inventory stats
POST /api/library/add          # Add card (from scan)
POST /api/library/remove       # Remove card (from sale)
GET  /api/library/count        # Total count
```

### 2. Desktop V3 Library Client
Replace `LibrarySystem(local_db)` with:
```python
class BrokLibraryClient:
    """Read inventory from BROK master"""
    def __init__(self, brok_url='http://192.168.1.174:5000'):
        self.url = brok_url

    def get_all_cards(self):
        return requests.get(f'{self.url}/api/library/all').json()

    def search(self, query):
        return requests.get(f'{self.url}/api/library/search', params={'q': query}).json()
```

### 3. Deck Builder Fix (Issue #5)
**Before (BROKEN):**
```python
db_path = "E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db"  # Hardcoded!
conn = sqlite3.connect(db_path)
conn.execute("DELETE FROM cards WHERE scryfall_id = ?", (card_id,))
```

**After (V3):**
```python
# Use BROK API
requests.post('http://192.168.1.174:5000/api/library/remove', json={
    'scryfall_id': card_id,
    'quantity': 1
})
```

### 4. Scan Workflow
```
1. User scans card on BROK
2. BROK OCR → ZULTAN lookup (metadata)
3. User confirms → BROK adds to local inventory DB
4. Desktop auto-refreshes from BROK API
```

## Migration Steps

### Step 1: Find BROK's actual inventory location
```bash
ssh nexus1@192.168.1.174
# Where is the 35,780 card database?
# Check scanner_v3 config
# Likely: ~/scanner_data/ or ~/scans/ or embedded in scanner process
```

### Step 2: Add BROK library API
- Modify scanner_v3.py or create library_server.py
- Expose REST endpoints for inventory CRUD
- Port 5000 (or 5002 if conflict)

### Step 3: Update Desktop V3
- Remove local nexus_library.db usage
- Replace with BrokLibraryClient
- All Collection/Deck/Sales tabs use BROK API

### Step 4: Deprecate local DBs
- ZULTAN ~/training/data/nexus_library.db → archive only
- Desktop E:/nexus_library.db → delete
- BROK becomes only writeable inventory

## Data Flow Diagram
```
┌─────────────────────────────────────────────┐
│              DESKTOP V3                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │Collection│  │Deck Build│  │ Scanner  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │ GET         │ POST        │ GET    │
└───────┼─────────────┼─────────────┼────────┘
        │             │             │
        ▼             ▼             ▼
┌────────────────────────────────────────────┐
│         BROK:5000 (Master Inventory)       │
│  ┌──────────────────────────────────────┐  │
│  │  nexus_library.db (35,780 cards)     │  │
│  │  /api/library/* REST API             │  │
│  └──────────────────────────────────────┘  │
└─────────────┬──────────────────────────────┘
              │ Lookup metadata
              ▼
┌────────────────────────────────────────────┐
│       ZULTAN:8000 (Card Universe)          │
│  MTG: 521K | Pokemon: 19.8K | Sports: 1.8M │
│  /api/mtg/search, /api/pokemon/search      │
└────────────────────────────────────────────┘
```

## Issue #5 Fix: Deck Builder Database
**Problem:** Hardcoded `E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db`

**Solution:**
```python
# OLD - deck_builder.py line ~450
def sell_deck(self, deck_cards):
    db_path = "E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db"  # WRONG!
    conn = sqlite3.connect(db_path)

# NEW - Use BROK API
def sell_deck(self, deck_cards):
    for card in deck_cards:
        requests.post(f'{BROK_URL}/api/library/remove', json={
            'scryfall_id': card['scryfall_id'],
            'quantity': card['quantity']
        })
    # Log sale to BROK
    requests.post(f'{BROK_URL}/api/sales/log', json={
        'deck_name': deck_name,
        'cards': deck_cards,
        'total_price': total,
        'timestamp': datetime.now().isoformat()
    })
```

## Issue #6 Fix: Scryfall Data
**Problem:** Desktop tries to load `E:\MTTGG\cards.json` (50K cards, incomplete)

**Solution:** Use ZULTAN:8000 instead
```python
# OLD - app.py
self.scryfall_db = ScryfallDatabase(
    bulk_json_path=r"E:\MTTGG\cards.json",  # Only 50K cards!
    auto_load=True
)

# NEW - Use ZULTAN API
self.card_api = CardDataClient('http://192.168.1.152:8000')
# Has 521K MTG cards already loaded
```

**Why 50K is wrong:**
- Scryfall "default cards" = ~100K oracle cards (one per unique name)
- Scryfall "all cards" = ~300K+ (all printings)
- ZULTAN has 521K (all MTG printings across all sets)
- Desktop 50K JSON is outdated partial export

**Action:**
1. Stop using local Scryfall JSON
2. Point all card lookups to ZULTAN:8000
3. ZULTAN already has the full dataset

## Summary

| Component | Current | V3 Target |
|-----------|---------|-----------|
| **Inventory Master** | 3 conflicting DBs | BROK only (35,780) |
| **Card Metadata** | Local JSON (50K) | ZULTAN API (521K) |
| **Deck Builder** | Hardcoded paths | BROK API |
| **Desktop** | Local DB (26,877) | API client only |
| **Scan adds** | Unknown destination | BROK via API |
| **Sale removes** | Local DB only | BROK via API |

**Result:** Single source of truth, no path conflicts, real-time sync
