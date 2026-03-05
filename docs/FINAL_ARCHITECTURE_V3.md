# NEXUS V3 Final Architecture
**Clarified after Issues 4-6 Resolution**

## The Truth About Inventory Files

### BROK Approved Inventory (~26,850-28,000 cards)
**This is the MASTER - cards that have been:**
1. Scanned on BROK
2. Confirmed by user
3. Assigned call numbers (physical location)
4. Approved for client inventory

**Location:** `BROK:~/nexus_library.db` or equivalent
**Status:** **IMPERATIVE - Must stay on BROK device**
**Purpose:** Client's actual owned collection with call numbers

### BROK Scan Cache/History (~35,780 entries)
**This is likely:**
- ALL scans ever performed (including duplicates, rejects, re-scans)
- Scan history log
- NOT the approved inventory

**Purpose:** Audit trail, not source of truth for collection

### Desktop Local Copy (~26,877 cards)
**This is:**
- Stale copy of BROK approved inventory
- Out of sync (27 card difference)
- Should be replaced with real-time BROK API access

### ZULTAN Copy (~26,850 cards)
**This is:**
- Another stale copy
- Should NOT exist
- ZULTAN's job is card universe (521K cards), not client inventory

---

## Correct V3 Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DESKTOP V3 (UI)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Collection│  │Deck Build│  │ Scanner  │  │ Analytics│   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│       │ GET         │ POST        │ GET         │ GET      │
│       │ inventory   │ remove      │ inventory   │ stats    │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│            BROK:5002 - Inventory API                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  APPROVED INVENTORY (~26,850 cards)                   │  │
│  │  - Scanned + Confirmed + Call Numbers                 │  │
│  │  - nexus_library.db (MASTER)                          │  │
│  │  - REST API: /api/library/*                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  When user scans new card:                                  │
│  1. Scan → BROK OCR                                         │
│  2. Lookup metadata → ZULTAN:8000 ↓                         │
│  3. User confirms + assigns call number                     │
│  4. Add to approved inventory DB                            │
│  5. Desktop auto-refreshes                                  │
└─────────────┬───────────────────────────────────────────────┘
              │ GET metadata
              │ (prices, images, sets)
              ▼
┌─────────────────────────────────────────────────────────────┐
│         ZULTAN:8000 - Card Universe Metadata                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  MTG: 521,124 cards                                   │  │
│  │  Pokemon: 19,818 cards                                │  │
│  │  Sports: 1,835,350 cards                              │  │
│  │  /api/mtg/search, /api/pokemon/search                │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Does NOT store client inventory                            │
│  Only provides: names, sets, prices, images, oracle IDs     │
└─────────────────────────────────────────────────────────────┘
```

---

## What Each System Does

### BROK (Master Inventory)
**Role:** Client's approved collection with call numbers

**Stores:**
- Card name
- Scryfall ID (for metadata lookup)
- Call number (physical location: Box 23, Row 5, etc.)
- Quantity owned
- Date added
- Confirmation status

**API Endpoints:**
```
GET  /api/library/all          # All approved cards
GET  /api/library/search?q=X   # Search owned cards
POST /api/library/add          # Add approved scan
POST /api/library/remove       # Remove from inventory (sale)
GET  /api/library/stats        # Count, value, etc.
```

**Does NOT store:**
- Card prices (gets from ZULTAN)
- Card images (gets from ZULTAN)
- Full card metadata (gets from ZULTAN)

### ZULTAN (Card Universe)
**Role:** Metadata provider for ALL possible cards

**Stores:**
- Every MTG card ever printed (521K)
- Every Pokemon card (19.8K)
- Every sports card (1.84M)
- Current prices (TCGPlayer, CardMarket)
- Image URLs (Scryfall)
- Set data, rarity, oracle text

**API Endpoints:**
```
GET /api/mtg/search?q=X        # Find MTG card
GET /api/pokemon/search?q=X    # Find Pokemon card
GET /api/sports/search?q=X     # Find sports card
GET /api/stats                 # Database stats
```

**Does NOT store:**
- Client inventory
- Call numbers
- What the client owns

### Desktop (UI Client)
**Role:** Display interface ONLY

**Responsibilities:**
- Show inventory from BROK API
- Enrich with metadata from ZULTAN API
- Send add/remove commands to BROK
- NO local database files

**Example Flow - Viewing Collection:**
```python
# Get owned cards from BROK
inventory = requests.get('http://192.168.1.174:5002/api/library/all').json()

# For each card, get metadata from ZULTAN
for card in inventory['results']:
    metadata = requests.get(
        'http://192.168.1.152:8000/api/mtg/search',
        params={'oracle_id': card['oracle_id']}
    ).json()

    # Display: name (BROK) + image (ZULTAN) + price (ZULTAN) + call# (BROK)
```

---

## Issues 4-6 Resolution (CORRECTED)

### Issue 4: Library Mismatch
**Problem:** Desktop has 26,877, ZULTAN has 26,850, unclear which is master

**Solution:**
- BROK is master (~26,850 approved cards)
- Desktop pulls from BROK API
- ZULTAN deletes its copy (shouldn't have one)
- Desktop deletes local DB (uses API only)

### Issue 5: Hardcoded Paths
**Problem:** Deck Builder writes to `E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db`

**Solution:**
- Replace direct DB access with BROK API calls
- POST to `/api/library/remove` for sales
- POST to `/api/sales/log` for audit trail

### Issue 6: Scryfall Data
**Problem:** Desktop loads 50K card JSON (incomplete)

**Solution:**
- Desktop uses ZULTAN:8000 for metadata (521K cards)
- No local JSON files
- Real-time prices and images from API

---

## Deployment Steps (CORRECTED)

### Step 1: Deploy BROK Library API
```bash
# Copy server to BROK
scp src/brok_library_server.py nexus1@192.168.1.174:~/

# SSH and start (point to existing approved inventory DB)
ssh nexus1@192.168.1.174
python3 brok_library_server.py --port 5002 --db ~/nexus_library.db

# Test
curl http://192.168.1.174:5002/api/library/health
# Should show ~26,850 approved cards
```

### Step 2: Update Desktop
```python
# nexus_desktop_v3.py already uses:
# - CardDataClient (ZULTAN:8000) for metadata
# - Need to add BrokLibraryClient for inventory

class BrokLibraryClient:
    def __init__(self, url='http://192.168.1.174:5002'):
        self.url = url

    def get_all_cards(self):
        """Get approved inventory from BROK"""
        return requests.get(f'{self.url}/api/library/all').json()

    def remove_card(self, scryfall_id, quantity=1):
        """Remove from inventory (for sales)"""
        return requests.post(f'{self.url}/api/library/remove', json={
            'scryfall_id': scryfall_id,
            'quantity': quantity
        })

# Use in Collection tab:
inventory = self.brok_library.get_all_cards()
for card in inventory['results']:
    # Enrich with ZULTAN metadata
    metadata = self.card_api.search_mtg(card['card_name'])
    # Display: name + call# (BROK) + price + image (ZULTAN)
```

### Step 3: Clean Up
```bash
# Delete ZULTAN copy (shouldn't exist)
ssh zultan@192.168.1.152
mv ~/training/data/nexus_library.db ~/BACKUP/nexus_library.db.$(date +%Y%m%d)

# Delete Desktop local copy
del E:\NEXUS_V2_RECREATED\nexus_v2\data\nexus_library.db

# Archive old Scryfall JSON
move E:\MTTGG\cards.json E:\BACKUP\cards.json.$(date +%Y%m%d)
```

---

## Summary

**BROK** = Master inventory (26,850 approved cards with call numbers)
**ZULTAN** = Metadata provider (521K card universe)
**Desktop** = UI that combines both via APIs

**Key Rule:**
- Inventory (what we own) → BROK
- Metadata (prices, images) → ZULTAN
- Desktop = Display only, no local data

This ensures:
✅ Single source of truth (BROK)
✅ No path conflicts
✅ Real-time sync
✅ Call numbers preserved on BROK
✅ Complete metadata (521K cards from ZULTAN)
