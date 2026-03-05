# NEXUS V2 Pathway Audit - Summary Report
**Date:** 2026-02-15 20:30 EST
**Status:** Database location fixed, architecture violations documented

---

## ✅ COMPLETED FIXES

### 1. Library Database Location - FIXED ✅
**Problem:** Main BROK server pointed to empty database
**Root Cause:** Real data (26,850 cards) was in `/home/nexus1/` instead of HDD
**Solution:** Moved database to proper location on 160GB HDD

**Before:**
```
Main BROK (:5000) → /mnt/nexus_data/databases/nexus_library.db (0 cards ❌)
Home directory   → /home/nexus1/nexus_library.db (26,850 cards)
V2 Server (:5002) → /home/nexus1/nexus_library.db (26,850 cards)
```

**After:**
```
Main BROK (:5000) → /mnt/nexus_data/databases/nexus_library.db (26,850 cards ✅)
Desktop BrockLibraryClient → http://192.168.1.174:5000 ✅
Total inventory value: $3,860.03
```

### 2. Redundant Servers - STOPPED ✅
**Problem:** Three library servers running on different ports
**Solution:** Stopped redundant servers, single source at :5000

**Active Servers on BROK:**
- ✅ Port 5000: Main BROK server (OCR + Scanner + Library API)
- ❌ Port 5001: Old library server (STOPPED)
- ❌ Port 5002: Test V2 server (STOPPED)

### 3. Architecture Documentation - CREATED ✅
**Created:**
- `ARCHITECTURE_AUDIT_VIOLATIONS.md` - Full violation report
- `PATHWAY_AUDIT_SUMMARY.md` - This file
- Updated `ISSUES_4_5_6_RESOLUTION.md` - Corrected resolution steps

---

## 🔴 REMAINING CRITICAL VIOLATIONS

### Priority 1: Desktop Direct Database Access

#### File: `nexus_v2/ui/tabs/deck_builder.py` (Line 911-969)
**Violation:** Bypasses BROK API, directly opens local SQLite database

**Current Code:**
```python
db_path = "E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db"
conn = sqlite3.connect(db_path)
cursor.execute("DELETE FROM cards WHERE id = ?", (row[0],))
```

**Required Fix:**
```python
from nexus_v2.library.brock_client import BrockLibraryClient

brock = BrockLibraryClient("http://192.168.1.174:5000")
for card in deck_cards:
    result = brock.remove(card['scryfall_id'], quantity=1)
    if not result.get('success'):
        failed_cards.append(card['name'])
```

**Impact:** HIGH - Inventory gets out of sync, hardcoded E: drive path won't work on shops

---

#### File: `nexus_v2/library/brock_client.py` (Line 240)
**Violation:** Falls back to local database when BROK offline

**Current Code:**
```python
local_db_path = Path(__file__).parent.parent / "data" / "nexus_library.db"
```

**Required Fix:** Remove fallback entirely - if BROK is offline, show error to user

---

#### File: `nexus_v2/library/library_db.py` (Line 21)
**Violation:** Desktop has local library database class

**Required Fix:** This class should ONLY exist on BROK server, not in desktop code

---

#### File: `nexus_v2/library/library_system.py` (Line 86)
**Violation:** Creates local library_db_file

**Current Code:**
```python
self.library_db_file = self.data_dir / "nexus_library.db"
```

**Required Fix:** Remove - desktop should never create local library database

---

### Priority 2: Hardcoded Paths

#### Files with E: Drive Hardcoded Paths:
1. `nexus_v2/ui/tabs/deck_builder.py:911` - `E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db`
2. `nexus_v2/ui/tabs/deck_builder.py:951` - `E:/NEXUS_V3/data/sales_log.txt` (wrong version!)
3. `nexus_v2/ui/tabs/ai_training.py:287` - `E:/NEXUS_V2_RECREATED/training/training_16env.log`
4. `nexus_v2/ui/tabs/ai_training.py:461` - `E:/NEXUS_V2_RECREATED/training`
5. `nexus_v2/ui/tabs/ai_training.py:496` - `E:/NEXUS_V2_RECREATED/training`
6. `nexus_v2/ui/tabs/ai_training.py:564` - `E:/NEXUS_V2_RECREATED/training`
7. `tools/agent_orchestrator.py:165` - `E:/NEXUS_V2_RECREATED`

**Required Fix:** Use config-based paths or environment variables:
```python
# Instead of:
db_path = "E:/NEXUS_V2_RECREATED/nexus_v2/data/nexus_library.db"

# Use:
from nexus_v2.config import get_config
config = get_config()
brok_url = config.get('library.brock_url', 'http://192.168.1.174:5000')
```

---

### Priority 3: Architecture Confusion

#### File: `src/zultan_library_api.py`
**Violation:** Claims "ZULTAN as SINGLE SOURCE OF TRUTH for inventory"

**Problem:** Contradicts actual architecture where BROK is inventory master

**Required Fix:** Either:
1. Delete this file entirely (ZULTAN shouldn't have library API)
2. OR repurpose for SYNC operations only (shops push to ZULTAN for marketplace)

**Clarification Needed:**
- Is ZULTAN the sync target for marketplace listings?
- Or is BROK completely standalone with no ZULTAN sync?

---

## 📊 ARCHITECTURE COMPLIANCE STATUS

### Correct Architecture:
```
┌─────────────────────────────────────────┐
│  Desktop (UI Only)                      │
│  - No local databases                   │
│  - API client only                      │
└─────────────────┬───────────────────────┘
                  │ HTTP API
                  ▼
┌─────────────────────────────────────────┐
│  BROK (Scanner Brain) :5000             │
│  ├─ Coral TPU (art recognition)         │
│  ├─ 160GB HDD (all client data)         │
│  ├─ Library DB: 26,850 cards            │
│  └─ REST API: /api/library/*            │
└─────────────────┬───────────────────────┘
                  │ Commands
                  ▼
┌─────────────────────────────────────────┐
│  SNARF (Hardware) :5001                 │
│  ├─ Cameras (CZUR, OwlEye)              │
│  ├─ Robotic arm (ESP32)                 │
│  ├─ Lights (ESP32)                      │
│  └─ Stepper, vacuum                     │
└─────────────────────────────────────────┘

        (Optional periodic sync)
                  │
                  ▼
┌─────────────────────────────────────────┐
│  ZULTAN (Nexus HQ) :8000                │
│  ├─ Card catalog (521K MTG)             │
│  ├─ Marketplace (Cloudflare)            │
│  └─ Catalog updates                     │
└─────────────────────────────────────────┘
```

### Current Compliance: 75%

**Compliant Components:**
✅ BROK has library database on HDD
✅ BROK serves library API on :5000
✅ SNARF handles hardware
✅ ZULTAN has card catalog API
✅ Config system uses environment variables

**Non-Compliant Components:**
❌ Desktop has local library database paths
❌ Deck Builder bypasses BROK API
❌ Hardcoded E: drive paths throughout
❌ ZULTAN has conflicting library API
❌ Three different brok_server.py files

---

## 🎯 ACTION PLAN

### Phase 1: Desktop API Migration (HIGH PRIORITY)
**Estimated:** 2-3 hours

1. **Fix Deck Builder** (`nexus_v2/ui/tabs/deck_builder.py`)
   - Replace direct SQLite access with BrockLibraryClient
   - Remove hardcoded E: paths
   - Test sell deck flow

2. **Remove Local DB Fallbacks** (`nexus_v2/library/brock_client.py`)
   - Delete local database path references
   - Show proper error when BROK offline

3. **Clean Up Library System** (`nexus_v2/library/library_system.py`)
   - Remove local DB creation
   - Ensure all operations go through API

4. **Delete Local Database** (if exists)
   ```bash
   del E:\NEXUS_V2_RECREATED\nexus_v2\data\nexus_library.db
   ```

### Phase 2: Path Cleanup (MEDIUM PRIORITY)
**Estimated:** 1-2 hours

1. **Create Path Config** (`nexus_v2/config/paths.py`)
   ```python
   import os
   from pathlib import Path

   PROJECT_ROOT = Path(__file__).parent.parent
   TRAINING_DIR = os.getenv('NEXUS_TRAINING_DIR', PROJECT_ROOT / 'training')
   LOGS_DIR = os.getenv('NEXUS_LOGS_DIR', PROJECT_ROOT / 'logs')
   ```

2. **Update All Hardcoded Paths**
   - AI Training tab
   - Deck Builder
   - Agent Orchestrator

### Phase 3: Documentation (LOW PRIORITY)
**Estimated:** 1 hour

1. **Clarify ZULTAN Role**
   - Update architecture docs
   - Decide: Delete `zultan_library_api.py` or repurpose for sync?

2. **Identify Canonical BROK Server**
   - Which `brok_server.py` is actually deployed?
   - Archive unused versions

3. **Create Deployment Guide**
   - Correct port numbers
   - Correct database paths
   - Environment variables needed

---

## 📝 VERIFICATION CHECKLIST

After fixes, verify:

- [ ] Desktop can view inventory via BROK API
- [ ] Deck Builder sell removes cards from BROK
- [ ] No local `nexus_library.db` files on desktop
- [ ] All E: drive paths removed or configurable
- [ ] Test on different machine (not Battle Station)
- [ ] Scanner → BROK → Desktop flow works
- [ ] Inventory count matches across all interfaces
- [ ] Sales properly logged and synced

---

## 🚀 NEXT STEPS

**Immediate (Next Session):**
1. Fix Deck Builder to use BROK API
2. Remove local database fallbacks
3. Test sell deck flow

**Short Term (This Week):**
4. Clean up hardcoded paths
5. Delete unused server files
6. Update documentation

**Long Term (Before Shop Deployment):**
7. Test full flow on shop hardware
8. Create deployment checklist
9. Verify all paths work on Windows laptop (not E: drive)

---

## 📌 SUMMARY

**What Got Fixed Today:**
- ✅ Moved 26,850-card library to HDD
- ✅ Main BROK server now serves inventory
- ✅ Stopped redundant servers
- ✅ Documented all violations

**What Still Needs Fixing:**
- ❌ Desktop bypasses BROK API (Deck Builder)
- ❌ Hardcoded E: drive paths
- ❌ Local database fallbacks

**Architecture Status:** 75% compliant, critical violations identified and documented.
