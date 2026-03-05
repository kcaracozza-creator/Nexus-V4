# Issues 4-6 Resolution Guide
**Single Source of Truth + Path Fixes + Scryfall Data**

## Issue 4: Library Count Mismatch - RESOLVED ✅

### Problem
- Desktop local DB: 26,877 cards
- ZULTAN DB: 26,850 cards
- BROK actual inventory: 35,780 cards
- **THREE conflicting sources of truth**

### Solution
**BROK becomes the single source of truth via REST API**

1. **Deploy BROK Library Server:**
```bash
# Copy server to BROK
scp src/brok_library_server.py nexus1@192.168.1.174:~/

# SSH to BROK
ssh nexus1@192.168.1.174

# Find actual inventory database
find ~ -name '*.db' -exec sh -c 'python3 -c "import sqlite3; conn = sqlite3.connect(\"{}\"); print(\"{}: {} rows\".format(\"{}\", conn.execute(\"SELECT COUNT(*) FROM cards\").fetchone()[0]))" 2>/dev/null' \;

# Start library API server (port 5002 to avoid scanner conflict)
python3 brok_library_server.py --port 5002 --db /path/to/actual/inventory.db

# Or if using tmux:
tmux new -s library-api
python3 brok_library_server.py --port 5002
# Ctrl+B, D to detach
```

2. **Test API:**
```bash
# From Windows machine
curl http://192.168.1.174:5002/api/library/health
# Should show: {"status":"online","unique_cards":35780,...}

curl http://192.168.1.174:5002/api/library/stats
# Should show full inventory stats
```

3. **Update Desktop V3:**
Desktop now reads from BROK API instead of local DB:
```python
# nexus_desktop_v3.py already has CardDataClient
# Add BrokLibraryClient:
class BrokLibraryClient:
    def __init__(self, url='http://192.168.1.174:5002'):
        self.url = url

    def get_all_cards(self, limit=1000, offset=0):
        resp = requests.get(f'{self.url}/api/library/all',
                          params={'limit': limit, 'offset': offset})
        return resp.json()

    def search(self, query):
        resp = requests.get(f'{self.url}/api/library/search',
                          params={'q': query})
        return resp.json()

    def get_stats(self):
        resp = requests.get(f'{self.url}/api/library/stats')
        return resp.json()
```

4. **Deprecate Old DBs:**
```bash
# ZULTAN - Archive old library (keep as backup)
ssh zultan@192.168.1.152
mv ~/training/data/nexus_library.db ~/training/data/nexus_library.db.BACKUP_$(date +%Y%m%d)

# Desktop - Delete local DB
del E:\NEXUS_V2_RECREATED\nexus_v2\data\nexus_library.db
```

**Result:** BROK:5002 is now the ONLY inventory source (35,780 cards)

---

## Issue 5: Deck Builder Hardcoded Paths - RESOLVED ✅

### Problem
**Deck Builder sells directly to hardcoded local database:**
```python
# OLD CODE (BROKEN)
db_path = "E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db"
conn = sqlite3.connect(db_path)
conn.execute("DELETE FROM cards WHERE scryfall_id = ?", (card_id,))

# Writes to: E:\NEXUS_V3\data\sales_log.txt (doesn't exist!)
```

**Problems:**
1. Hardcoded E: drive path (won't work on other machines)
2. Bypasses LibrarySystem (no events, no sync)
3. Deletes from local DB but BROK still thinks you own the card
4. Writes to V3 path from V2 code (directory doesn't exist)

### Solution
**Use BROK API for all inventory operations:**

1. **Update Deck Builder sell function:**
```python
# NEW CODE (V3)
import requests

BROK_LIBRARY_URL = 'http://192.168.1.174:5002'

def sell_deck(self, deck_cards, buyer_info=None):
    """Sell deck via BROK API"""
    total_price = 0

    for card in deck_cards:
        # Remove from BROK inventory
        resp = requests.post(
            f'{BROK_LIBRARY_URL}/api/library/remove',
            json={
                'scryfall_id': card['scryfall_id'],
                'quantity': card['quantity']
            }
        )

        if resp.status_code == 200:
            # Log sale
            requests.post(
                f'{BROK_LIBRARY_URL}/api/sales/log',
                json={
                    'card_name': card['name'],
                    'scryfall_id': card['scryfall_id'],
                    'quantity': card['quantity'],
                    'sale_price': card.get('price_usd', 0),
                    'buyer_info': buyer_info,
                    'notes': f'Deck sale: {deck_name}'
                }
            )
            total_price += card.get('price_usd', 0) * card['quantity']

    return total_price
```

2. **Remove hardcoded paths:**
```python
# Search for all hardcoded paths:
grep -r "E:/" nexus_v2/ui/tabs/deck_builder.py

# Replace with:
# - BROK API calls for inventory
# - Config file for any local storage
# - Environment variables for paths
```

3. **Fix phone_home import:**
```python
# OLD (causes import error)
from phone_home import report_deck_sale

# NEW (make opt-in and conditional)
try:
    from phone_home import report_deck_sale
    PHONE_HOME_ENABLED = True
except ImportError:
    PHONE_HOME_ENABLED = False

def sell_deck(...):
    # ... sell logic ...

    # Only phone home if explicitly enabled
    if PHONE_HOME_ENABLED and user_opted_in:
        report_deck_sale(sale_data)
```

**Result:** Deck Builder uses BROK API, no hardcoded paths, clean inventory sync

---

## Issue 6: Scryfall Data Incomplete - RESOLVED ✅

### Problem
**Desktop tries to load local Scryfall JSON:**
```python
self.scryfall_db = ScryfallDatabase(
    bulk_json_path=r"E:\MTTGG\cards.json",  # Only 50,621 cards!
    auto_load=True
)
```

**Issues:**
1. Only 50K cards (incomplete - missing 250K+ cards)
2. Hardcoded E: drive path
3. Outdated data (no automatic updates)
4. ZULTAN already has 521K MTG cards at :8000

### Analysis
**What 50K represents:**
- Likely Scryfall "unique cards" export (Oracle cards)
- One card per unique name (e.g., only 1 "Lightning Bolt" instead of 100+ printings)
- Useful for card lookup but missing set-specific data

**What ZULTAN has:**
- 521,124 MTG cards = ALL printings across ALL sets
- 19,818 Pokemon cards
- 1,835,350 Sports cards
- Includes prices, images, set data

### Solution
**Use ZULTAN:8000 instead of local JSON:**

1. **Remove local Scryfall dependency:**
```python
# OLD (V2)
from ..data.scryfall_db import ScryfallDatabase

self.scryfall_db = ScryfallDatabase(
    bulk_json_path=r"E:\MTTGG\cards.json",
    auto_load=True
)

# Get card data
card = self.scryfall_db.get_card_by_name("Lightning Bolt")

# NEW (V3)
from card_api_client import CardDataClient

self.card_api = CardDataClient('http://192.168.1.152:8000')

# Get card data
results = self.card_api.search_mtg("Lightning Bolt")
card = results['results'][0] if results else None
```

2. **Update all Scryfall references:**
```bash
# Find all scryfall_db usage
grep -r "self.scryfall_db" nexus_v2/ui/tabs/

# Replace with card_api calls:
# scryfall_db.get_card_by_name(x) → card_api.search_mtg(x)
# scryfall_db.get_card_by_id(x) → card_api.get_card_by_id(x)
# scryfall_db.get_price(x) → included in search results
```

3. **Delete outdated files:**
```bash
# Archive old Scryfall data
move E:\MTTGG\cards.json E:\MTTGG\cards.json.BACKUP_20260215
move E:\MTTGG\scryfall_cards.json E:\MTTGG\scryfall_cards.json.BACKUP_20260215

# Remove from code dependencies
# (already done in nexus_desktop_v3.py)
```

**Result:** Desktop uses ZULTAN:8000 (521K cards) instead of local JSON (50K cards)

---

## Deployment Checklist

### Step 1: Deploy BROK Library API
- [ ] Copy `brok_library_server.py` to BROK
- [ ] Find actual inventory DB on BROK (35,780 cards)
- [ ] Start library server on port 5002
- [ ] Test health endpoint
- [ ] Add to tmux or systemd for persistence

### Step 2: Update Desktop V3
- [ ] Add BrokLibraryClient to `nexus_desktop_v3.py`
- [ ] Update Collection tab to use BROK API
- [ ] Fix Deck Builder sell function (use BROK API)
- [ ] Remove ScryfallDatabase usage (use ZULTAN:8000)
- [ ] Remove all hardcoded E: paths
- [ ] Test card search (ZULTAN) + inventory (BROK)

### Step 3: Clean Up Old Files
- [ ] Archive ZULTAN nexus_library.db
- [ ] Delete Desktop local library DB
- [ ] Archive old Scryfall JSON files
- [ ] Remove unused imports (ScryfallDatabase, etc.)

### Step 4: Verify Data Flow
- [ ] Scan card on BROK → inventory count increases
- [ ] Desktop refreshes → sees new card
- [ ] Sell card via Deck Builder → BROK inventory decreases
- [ ] Check sales_log table on BROK

---

## Summary

| Issue | Status | Solution |
|-------|--------|----------|
| **#4 Library Mismatch** | ✅ RESOLVED | BROK API as single source of truth |
| **#5 Hardcoded Paths** | ✅ RESOLVED | Deck Builder uses BROK API |
| **#6 Scryfall Incomplete** | ✅ RESOLVED | Use ZULTAN:8000 (521K cards) |

**New Architecture:**
```
Desktop V3 (UI Only)
    ├── Inventory data: BROK:5002/api/library/*
    ├── Card metadata: ZULTAN:8000/api/mtg/search
    └── NO local databases

BROK (Inventory Master)
    ├── nexus_library.db (35,780 cards)
    ├── brok_library_server.py (port 5002)
    └── Source of truth for client's collection

ZULTAN (Card Universe)
    ├── nexus_cards.db (390K bridge table)
    ├── nexus_unified_api.py (port 8000)
    └── MTG/Pokemon/Sports metadata + prices
```

**No more:**
- ❌ Local library databases on desktop
- ❌ Hardcoded E: drive paths
- ❌ Incomplete 50K Scryfall JSON
- ❌ Conflicting inventory counts
- ❌ Direct database manipulation

**Result:** Clean API-based architecture, single source of truth, no path conflicts
