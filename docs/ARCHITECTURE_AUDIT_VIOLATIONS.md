# NEXUS V2 Architecture Audit - Violations Report
**Date:** 2026-02-15
**Auditor:** MENDEL (Claude Sonnet 4.5)

## Architecture Rules
Based on confirmed architecture:
1. **BROK** = Scanner brain (Coral TPU, 160GB HDD, all client data, OCR, art recognition)
2. **SNARF** = Hardware body (cameras, arm, ESP32s, steppers, lights)
3. **Desktop** = UI only (no local data, all via BROK API)
4. **ZULTAN** = Nexus HQ (catalog master, marketplace, periodic sync)

---

## 🔴 CRITICAL VIOLATIONS

### 1. Deck Builder Direct Database Access ⚠️ **BREAKS ARCHITECTURE**
**File:** `nexus_v2/ui/tabs/deck_builder.py:911-969`

**Problem:**
```python
# Line 911
db_path = "E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db"
conn = sqlite3.connect(db_path)
cursor.execute("DELETE FROM cards WHERE id = ?", (row[0],))
```

**Issues:**
- Directly opens local SQLite database
- Bypasses BROK API entirely
- Hardcoded E: drive path (won't work on shop deployments)
- Desktop has write access to inventory (should be read-only via API)
- Sales log path points to non-existent `/NEXUS_V3/` directory (line 951)

**Correct Architecture:**
```python
# Should use BrockLibraryClient instead:
from nexus_v2.library.brock_client import BrockLibraryClient

brock = BrockLibraryClient()  # Points to 192.168.1.174:5000
for card in deck:
    brock.remove(card['scryfall_id'], quantity=1)
```

**Impact:** Desktop can delete cards without BROK knowing. Inventory gets out of sync.

---

### 2. Desktop Has Local Library Database ⚠️ **WRONG STORAGE**
**Files:**
- `nexus_v2/library/brock_client.py:240`
- `nexus_v2/library/library_db.py:21`
- `nexus_v2/library/library_system.py:86`

**Problem:**
```python
# brock_client.py:240 - Falls back to local DB
local_db_path = Path(__file__).parent.parent / "data" / "nexus_library.db"

# library_db.py:21
db_path = Path(__file__).parent.parent / "data" / "nexus_library.db"

# library_system.py:86
self.library_db_file = self.data_dir / "nexus_library.db"
```

**Issues:**
- Desktop maintains its own copy of inventory
- Creates sync conflicts (Desktop 26,877 vs BROK 26,850)
- Violates "Desktop = UI only" rule
- No mechanism to keep local copy in sync with BROK

**Correct Architecture:**
- Desktop should NEVER have `nexus_library.db` locally
- All inventory reads via `BrockLibraryClient` API calls
- Delete `nexus_v2/data/nexus_library.db` file

---

### 3. ZULTAN Has Library API ⚠️ **CONTRADICTS ARCHITECTURE**
**File:** `src/zultan_library_api.py`

**Problem:**
```python
# Line 7: "This establishes ZULTAN as the SINGLE SOURCE OF TRUTH for inventory"
# Line 23: LIBRARY_DB = Path.home() / "training" / "data" / "nexus_library.db"
```

**Issues:**
- Comments claim ZULTAN is inventory master
- Creates library management endpoints on ZULTAN
- Contradicts "BROK = scanner brain with all client data"
- Confusion about which system is authoritative

**Architecture Clarification:**
- **BROK** = Inventory master for each shop (local, standalone)
- **ZULTAN** = Card catalog master (521K cards) + marketplace
- **ZULTAN does NOT store shop inventories**
- Shops sync TO ZULTAN for marketplace, but BROK is local master

**Action Required:**
- Either delete `zultan_library_api.py` or clarify it's for SYNC not storage
- Update comments to reflect BROK as inventory master

---

### 4. Wrong Port Configuration ⚠️ **CONNECTION FAILURES**
**Files:** Multiple

**Problem:**
```python
# brock_client.py:24 - Port 5000
def __init__(self, brock_url: str = "http://192.168.1.174:5000"):

# But we deployed BROK library server to port 5002:
# brok_library_server_v2.py runs on port 5002
```

**Issues:**
- BrockLibraryClient tries to connect to :5000
- Actual BROK library server is on :5002
- Desktop will fail to reach inventory API
- Config files inconsistent (some :5000, some :5002)

**Action Required:**
1. Standardize on single port (recommend :5002 for library, :5000 for scanner)
2. Update all BrockLibraryClient references
3. Update config files

---

## 🟡 MEDIUM VIOLATIONS

### 5. Hardcoded E: Drive Paths
**Files:**
- `nexus_v2/ui/tabs/ai_training.py:287, 461, 496, 564`
- `nexus_v2/ui/tabs/deck_builder.py:911, 951`
- `tools/agent_orchestrator.py:165`

**Problem:**
```python
# ai_training.py
log_file = "E:/NEXUS_V2_RECREATED/training/training_16env.log"
training_dir = "E:/NEXUS_V2_RECREATED/training"

# deck_builder.py
db_path = "E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db"
sale_log_path = "E:/NEXUS_V3/data/sales_log.txt"  # Wrong version!
```

**Issues:**
- Won't work on shop laptops (different drive letters, paths)
- Won't work on Linux-based BROK/SNARF
- Battle Station specific, not portable

**Solution:**
- Use environment variables or config files
- Use relative paths from project root
- Use `Path(__file__).parent` for dynamic paths

---

### 6. Multiple BROK Server Implementations
**Files:**
- `pi_servers/brok_server.py` (4107 lines)
- `pi_servers/brok_server_home.py` (4107 lines)
- `src/scanner/snarf/brok_server.py` (3896 lines)

**Problem:**
- Three different "BROK server" files
- Unclear which one is actually deployed to BROK Pi
- Risk of deploying wrong version
- Code duplication makes updates difficult

**Questions:**
1. Which file is the canonical BROK server?
2. Why are there three versions?
3. Should they be consolidated?

---

## 🟢 ARCHITECTURAL COMPLIANCE

### ✅ Correct Implementations

1. **ACR Pipeline** (`src/scanner/acr_pipeline.py`)
   - Correctly routes: SNARF → BROCK → ZULTAN
   - Uses environment variables for URLs
   - No hardcoded paths

2. **Config System** (`nexus_v2/config/`)
   - Proper environment variable support
   - Deployment-specific configs
   - Falls back to sensible defaults

3. **BrockLibraryClient Design** (`nexus_v2/library/brock_client.py`)
   - API-based, not direct DB access
   - Timeout handling
   - Offline fallback (though fallback to local DB is problematic)

---

## 📋 ACTION ITEMS

### Priority 1 - Critical Fixes
- [ ] **Fix Deck Builder** - Replace direct DB access with BrockLibraryClient API calls
- [ ] **Delete Desktop Local DB** - Remove `nexus_v2/data/nexus_library.db`
- [ ] **Fix Library System** - Remove local DB path, use API only
- [ ] **Standardize Ports** - BROK library on :5002, update all clients

### Priority 2 - Architecture Cleanup
- [ ] **Clarify ZULTAN Role** - Delete or repurpose `zultan_library_api.py`
- [ ] **Remove Hardcoded Paths** - Use config/environment variables
- [ ] **Identify Canonical BROK Server** - Which file is deployed?

### Priority 3 - Documentation
- [ ] Update architecture docs to reflect audit findings
- [ ] Create deployment guide with correct port numbers
- [ ] Document which server files are active vs deprecated

---

## Summary

**Total Violations:** 6 critical, 2 medium
**Architecture Compliance:** ~70% (many pieces correct, key violations in desktop app)

**Main Issue:** Desktop app has direct database access and local storage, violating "UI only" principle. This creates:
- Sync conflicts (different card counts)
- Path dependencies (E: drive)
- Architectural confusion (which DB is master?)

**Recommended Fix Order:**
1. Fix Deck Builder to use BROK API
2. Remove local library DB from desktop
3. Standardize port configuration
4. Clean up hardcoded paths
5. Clarify ZULTAN vs BROK roles in documentation

---

## ✅ FIXES APPLIED (2026-02-15 20:28 EST)

### ✅ Fixed: Database Location
**Problem:** Main BROK server pointed to EMPTY database at `/mnt/nexus_data/databases/nexus_library.db` (0 cards)
**Root Cause:** Real data was in `/home/nexus1/nexus_library.db` (26,850 cards)
**Fix:** Copied database to HDD location where it belongs
**Result:** Main BROK server now serves 26,850 cards with $3,860.03 total value

```bash
# What was done:
cp /home/nexus1/nexus_library.db /mnt/nexus_data/databases/nexus_library.db
systemctl restart brok.service
```

**Verification:**
```bash
curl http://192.168.1.174:5000/api/library/stats
# {"count":26850, "total_value":3860.03, "success":true}
```

### ✅ Fixed: Redundant Servers
**Problem:** Three library servers running on different ports (5000, 5001, 5002)
**Fix:** Stopped redundant servers on :5001 and :5002
**Result:** Single source of truth at port 5000

**Current Server Status:**
- ✅ Port 5000: Main BROK server (OCR + Library API) - ACTIVE
- ❌ Port 5001: Old library server - STOPPED
- ❌ Port 5002: Test V2 server - STOPPED

---

## 🔴 REMAINING VIOLATIONS (MUST FIX)

### Priority 1 - Desktop Direct DB Access
- [x] **nexus_v2/ui/tabs/deck_builder.py:911** - Replace direct SQLite with BrockLibraryClient ✅
- [x] **nexus_v2/library/brock_client.py:240** - Remove local DB fallback (HybridLibrary deleted) ✅
- [x] **nexus_v2/library/library_db.py** - Added deprecation warning for default path ✅
- [x] **Delete:** `nexus_v2/data/nexus_library.db` - No local DB exists ✅

### Priority 2 - Path Cleanup
- [x] **nexus_v2/ui/tabs/deck_builder.py:951** - Now uses config-based path ✅
- [x] **nexus_v2/ui/tabs/ai_training.py** - All 4 E: paths → TRAINING_DIR from config ✅
- [x] **tools/agent_orchestrator.py:165** - Now uses relative path or $NEXUS_PROJECT_ROOT ✅

### Priority 3 - Documentation
- [ ] Clarify ZULTAN role (catalog master, NOT inventory)
- [ ] Update deployment docs with correct paths
- [ ] Document which brok_server.py is canonical
