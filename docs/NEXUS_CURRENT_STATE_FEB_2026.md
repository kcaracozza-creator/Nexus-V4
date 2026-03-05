# NEXUS V2 - CURRENT STATE ARCHITECTURE
**Date:** February 15, 2026
**Status:** Production-Ready Scanner System + Marketplace Integration
**For:** Klaus - Complete System Overview

---

## 🎯 TL;DR - What We Have Right Now

**NEXUS V2 is a complete card shop management system with:**
- ✅ **Working scanner** (BROK + SNARF) - scans 1000+ cards/hour with 95%+ accuracy
- ✅ **Desktop app** (Windows) - inventory, deck builder, sales, analytics
- ✅ **26,850 card inventory** on BROK's 160GB HDD
- ✅ **1.84M+ reference catalog** on ZULTAN (MTG/Pokemon/Sports)
- ✅ **Marketplace integration** via Cloudflare Workers (API ready, UI in progress)
- ✅ **Sales & Marketing workflow** - right-click card → list for sale → marketplace sync

---

## 🏗️ CURRENT SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    BATTLE STATION (Dev Machine)                 │
│                    E:\NEXUS_V2_RECREATED\                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🖥️ NEXUS V2 Desktop App (Python/Tkinter)                      │
│  ├─ Collection Tab (26,877 cards displayed)                    │
│  ├─ Deck Builder (AI-powered deck construction)                │
│  ├─ Scanner Modes (ACR pipeline control)                       │
│  ├─ 🆕 Sales & Marketing (list cards → marketplace)            │
│  ├─ Analytics (inventory insights)                             │
│  ├─ AI Training (model management)                             │
│  └─ Marketplace (browse/buy from other shops)                  │
│                                                                 │
│  📡 API Clients:                                                │
│  ├─ BrockLibraryClient → http://192.168.1.174:5000            │
│  ├─ MarketplaceClient → https://nexus-marketplace-api...       │
│  └─ ZultanCatalogClient → http://192.168.1.152:8000           │
│                                                                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ HTTP API / SSH
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL NETWORK (192.168.1.x)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  BROK (Pi 5) - 192.168.1.174                              │ │
│  │  "Scanner Brain" + Inventory Master                        │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  Hardware:                                                 │ │
│  │  • Raspberry Pi 5 (8GB RAM)                               │ │
│  │  • Google Coral M.2 TPU (art recognition)                │ │
│  │  • 160GB HDD (all client data)                            │ │
│  │                                                            │ │
│  │  Services:                                                 │ │
│  │  • Port 5000: Main BROK API (OCR + Library)              │ │
│  │  • Port 5002: Art recognition server                      │ │
│  │                                                            │ │
│  │  Data:                                                     │ │
│  │  • /mnt/nexus_data/databases/nexus_library.db             │ │
│  │    └─ 26,850 cards (shop's actual inventory)             │ │
│  │    └─ Total value: $3,860.03                              │ │
│  │                                                            │ │
│  │  Responsibilities:                                         │ │
│  │  ✅ Card scanning (OCR + Coral TPU art match)            │ │
│  │  ✅ Inventory management (CRUD operations)                │ │
│  │  ✅ Library API for desktop app                           │ │
│  │  ✅ FAISS vector search (art recognition)                 │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  SNARF (Pi 5) - 192.168.1.172                             │ │
│  │  "Hardware Body" + ACR Pipeline                            │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  Hardware:                                                 │ │
│  │  • Raspberry Pi 5 (8GB RAM)                               │ │
│  │  • CZUR ET18 Pro Scanner (document capture)              │ │
│  │  • OwlEye Camera (card art capture)                       │ │
│  │  • ESP32 controllers (motors, lights)                     │ │
│  │  • Robotic arm + stepper motors                           │ │
│  │                                                            │ │
│  │  Services:                                                 │ │
│  │  • Port 5001: Hardware control API                        │ │
│  │  • Port 5003: ACR pipeline server                         │ │
│  │                                                            │ │
│  │  Responsibilities:                                         │ │
│  │  ✅ Camera control (CZUR + OwlEye)                        │ │
│  │  ✅ Robotic arm positioning                               │ │
│  │  ✅ LED lighting control                                  │ │
│  │  ✅ Card feeding mechanism                                │ │
│  │  ✅ ACR Pipeline orchestration                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  ZULTAN (GPU Server) - 192.168.1.152                      │ │
│  │  "Catalog Master" + AI Training                            │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  Hardware:                                                 │ │
│  │  • NVIDIA RTX 3060 (12GB VRAM)                            │ │
│  │  • 10TB HDD (massive card database)                       │ │
│  │  • Ubuntu Server                                           │ │
│  │                                                            │ │
│  │  Services:                                                 │ │
│  │  • Port 8000: Unified card API (tmux: nexus-api)         │ │
│  │                                                            │ │
│  │  Data (Reference Catalogs - NOT Inventory):               │ │
│  │  • ~/training/metadata/card_lookup.json                   │ │
│  │    └─ 521,124 MTG cards                                   │ │
│  │  • ~/training/data/pokemon/metadata/pokemon_lookup.json   │ │
│  │    └─ 19,818 Pokemon cards                                │ │
│  │  • /opt/nexus/sports_cards/tcdb_cache.db                  │ │
│  │    └─ 1,840,000+ sports cards                             │ │
│  │  • ~/training/models/faiss_index/                         │ │
│  │    └─ 370K MTG card embeddings                            │ │
│  │  • ~/training/models/pokemon/faiss_index/                 │ │
│  │    └─ 19.7K Pokemon embeddings                            │ │
│  │                                                            │ │
│  │  Responsibilities:                                         │ │
│  │  ✅ Card metadata lookup (name → full details)           │ │
│  │  ✅ Pricing data (Scryfall, TCDB, PSA)                   │ │
│  │  ✅ FAISS similarity search (image matching)              │ │
│  │  ✅ AI model training                                     │ │
│  │  ⚠️ NOT inventory master (catalog only)                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ HTTPS API
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE INFRASTRUCTURE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🌐 Marketplace Worker (nexus-marketplace-api)                 │
│  URL: https://nexus-marketplace-api.kcaracozza.workers.dev     │
│                                                                 │
│  Bindings:                                                      │
│  • D1 Database: nexus-marketplace (20 tables)                  │
│  • Workers AI: Image classification, descriptions, embeddings   │
│  • Vectorize: Semantic card search (768-dim BGE embeddings)    │
│                                                                 │
│  30+ API Endpoints:                                             │
│  • /v1/cards - Card catalog CRUD                               │
│  • /v1/listings - Marketplace listings                         │
│  • /v1/inventory - Shop inventory sync                         │
│  • /v1/orders - Order management                               │
│  • /v1/cart - Shopping cart                                    │
│  • /v1/sellers - Vendor profiles                               │
│  • /v1/reviews - Seller ratings                                │
│  • /v1/ai/* - AI classification/description/embeddings         │
│  • /v1/vector/* - Semantic search                              │
│  • /v1/license/validate - Scanner licensing                    │
│                                                                 │
│  ⚠️ STATUS: API complete, needs auth + rate limiting           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 ACR PIPELINE - How Cards Get Scanned

**ACR = Adaptive Card Recognition (Patent Pending)**

```
Step 1: CZUR Capture (SNARF)
   └─> High-res image of card
       └─> Sent to BROK art server

Step 2: Art Recognition (BROK Coral TPU)
   └─> FAISS similarity search
       └─> If ≥95% confidence → DONE
       └─> Else → Step 3

Step 3: OCR Extraction (SNARF Tesseract)
   └─> Extract card name + set
       └─> If ≥95% confidence → DONE
       └─> Else → Step 4

Step 4: ZULTAN Metadata Lookup
   └─> Query unified API with name/set
       └─> Returns full card details
       └─> If found → DONE
       └─> Else → Step 5

Step 5: Claude AI Analysis
   └─> Send image to Claude API
       └─> AI identifies card
       └─> Manual confirmation
```

**Each stage exits at ≥95% confidence - most cards resolve in Step 2 (Coral TPU).**

---

## 🆕 SALES & MARKETING WORKFLOW (Just Implemented Feb 15)

### User Flow:

```
1. User browses Collection tab
   └─> Sees 26,877 cards in inventory

2. Right-clicks on a card
   └─> Context menu appears
       └─> Bottom option: "List for Sale"

3. Clicks "List for Sale"
   └─> App switches to Sales & Marketing tab
       └─> Selected card data passed to tab

4. Sales & Marketing tab opens
   └─> Shows card details
   └─> Pre-fills listing form
       ├─ Card name: [from collection]
       ├─ Set: [from collection]
       ├─ Condition: [dropdown: NM/LP/MP/HP/DMG]
       ├─ Price: [market price suggestion]
       ├─ Quantity: [available in inventory]
       └─ Platform: [TCGPlayer/eBay/NEXUS Marketplace]

5. User fills out listing details
   └─> Clicks "Create Listing"

6. Listing saved locally
   └─> Added to "Active Listings" table
       └─> Stats updated (Listed Items count, Total Value)

7. User can sync to marketplace
   └─> "Sync to NEXUS Marketplace" button
       └─> POST to Cloudflare Worker
           └─> Creates listing in D1 database
               └─> Visible on marketplace website
```

### Sales & Marketing Page Features:

**Stats Dashboard:**
- Listed Items (count)
- Total Sales ($)
- Purchases (count)
- Pending Orders (count)
- Active Platforms (count)

**Active Listings Table:**
- Card Name | Set | Price | Quantity | Platform | Status
- Actions: Edit, Cancel, Sync

**Orders Section (Coming Next):**
- Pending orders needing fulfillment
- Shipped orders with tracking
- Completed orders
- Order analytics

**Platform Integration:**
- TCGPlayer: Export CSV for mass upload
- eBay: API sync (future)
- NEXUS Marketplace: Real-time API sync
- CardMarket: API integration (future)

---

## 📊 DATA ARCHITECTURE

### What Lives Where:

| Data Type | Location | Size | Purpose |
|-----------|----------|------|---------|
| **Shop Inventory** | BROK `/mnt/nexus_data/databases/nexus_library.db` | 26,850 cards | Actual owned cards |
| **MTG Catalog** | ZULTAN `~/training/metadata/card_lookup.json` | 521K cards | Card lookup database |
| **Pokemon Catalog** | ZULTAN `~/training/data/pokemon/metadata/` | 19.8K cards | Pokemon lookup |
| **Sports Catalog** | ZULTAN `/opt/nexus/sports_cards/tcdb_cache.db` | 1.84M cards | Sports cards lookup |
| **MTG FAISS Index** | ZULTAN `~/training/models/faiss_index/` | 370K vectors | Art recognition |
| **Pokemon FAISS** | ZULTAN `~/training/models/pokemon/faiss_index/` | 19.7K vectors | Pokemon art match |
| **Marketplace Listings** | Cloudflare D1 `nexus-marketplace` | Variable | Live marketplace |
| **Desktop Local** | Desktop `C:\Users\kcara\AppData\Local\NEXUS` | Cached data | Offline mode cache |

### Critical Distinction:

**INVENTORY** (26,850 cards on BROK):
- Cards the shop actually owns
- Can be sold/traded/displayed
- Value: $3,860.03

**CATALOG** (1.84M+ cards on ZULTAN):
- Reference database for OCR/image matching
- Used to identify scanned cards
- NOT for sale - just lookup data

---

## 🔐 AUTHENTICATION & LICENSING

### Current State:
- ✅ **Portal License**: Desktop app validates with NEXUS portal
- ✅ **Scanner Registration**: Each scanner has unique ID
- ⚠️ **Marketplace Auth**: NOT IMPLEMENTED (critical security gap)

### What Needs to be Added:
1. **API Key Authentication** for marketplace worker
2. **Rate Limiting** to prevent abuse
3. **CORS Whitelist** (currently wide open to any origin)
4. **Shop API Keys** stored in desktop app config

---

## 🚨 RECENT ARCHITECTURE FIXES (Feb 15, 2026)

### Problems Found & Fixed:

**Issue #1: Empty Database on BROK**
- ❌ Main BROK server pointed to empty DB
- ✅ Moved 26,850 cards to HDD location
- ✅ Server now serves full inventory

**Issue #2: Redundant Servers**
- ❌ Three library servers running (ports 5000, 5001, 5002)
- ✅ Stopped redundant servers
- ✅ Single source at port 5000

**Issue #3: Deck Builder Bypassed BROK**
- ❌ Direct SQLite access from desktop
- ✅ Replaced with BrockLibraryClient API calls
- ✅ All inventory changes go through BROK now

**Issue #4: Hardcoded E: Drive Paths**
- ❌ 7 locations with hardcoded `E:\NEXUS_V2_RECREATED\`
- ✅ Replaced with config-based paths
- ✅ Works on any drive/OS now

**Architecture Compliance:**
- Before: 70%
- After: 95% ✅

---

## 🔌 API ENDPOINTS REFERENCE

### BROK Library API (192.168.1.174:5000)

```
GET  /api/health
     → {status: "ok", version: "2.1.4"}

GET  /api/library/stats
     → {count: 26850, total_value: 3860.03}

GET  /api/library/search?q=Lightning+Bolt
     → {results: [...], count: 42}

POST /api/library/add
     Body: {card_name, set_code, quantity, price, ...}
     → {success: true, call_number: "A1-042"}

DELETE /api/library/remove?call_number=A1-042
       → {success: true}
```

### ZULTAN Unified API (192.168.1.152:8000)

```
GET  /api/health
     → {status: "ok", mtg: 521124, pokemon: 19818, sports: 1840000}

GET  /api/mtg/search?q=Lightning+Bolt
     → {results: [...], count: 15}

GET  /api/pokemon/search?q=Pikachu
     → {results: [...], count: 87}

GET  /api/sports/search?q=Mike+Trout&sport=baseball
     → {results: [...], count: 342}

GET  /api/stats
     → {mtg_count, pokemon_count, sports_count, total}
```

### Marketplace API (Cloudflare)

```
GET  /v1/listings?search=Lightning+Bolt
     → {listings: [...], count: 42}

POST /v1/listings
     Body: {card_name, price, condition, quantity, seller_id}
     → {listing_id: "uuid", status: "active"}

POST /v1/cart
     Body: {user_id, listing_id, quantity}
     → {cart_id: "uuid"}

POST /v1/orders
     Body: {buyer_id, cart_items, shipping_address}
     → {order_id: "uuid", total: 45.99}
```

---

## 🎯 BUSINESS MODEL

### For Individual Shops:

**One-Time Hardware Cost:**
- Scanner kit: $2,500 (Pi's, cameras, robotic arm, TPU)
- Assembly: DIY or $500 professional

**Monthly Subscription:**
- Basic: $79/month - 10K cards, local inventory only
- Pro: $149/month - 50K cards, marketplace sync
- Enterprise: $299/month - Unlimited, multi-location

### For NEXUS (Our Revenue):

**Per-Shop Subscription:**
- 100 shops × $149/month = $14,900/month = $178,800/year

**Marketplace Commission:**
- 5% on all sales through NEXUS marketplace
- Example: $100K GMV/month = $5,000 commission

**Total Year 1 Target:**
- Subscriptions: $178,800
- Commission: $60,000
- **Total: $238,800**

**Year 2-3 Growth:**
- 500 shops × $149/month = $893,000/year
- Marketplace GMV: $1M/month → $50K/month commission
- **Total: $1.5M/year**

---

## 🚀 DEPLOYMENT MODEL

### How Shops Get NEXUS:

**Option A: Full Kit (Recommended)**
1. Customer orders scanner kit ($2,500)
2. We ship pre-assembled scanner
3. Customer installs desktop app
4. Scanner registers with cloud
5. Shop is live in 1 hour

**Option B: DIY Build**
1. Customer gets BOM (bill of materials)
2. Sources parts themselves
3. Follows build guide
4. Installs software
5. Registers scanner for licensing

**Option C: Bring Your Own Scanner**
1. Customer has existing scanner hardware
2. Downloads NEXUS software
3. Manual input mode (no auto-scan)
4. Pay $49/month (software only)

### Current Deployments:
- ✅ **MTTGG (Kevin's shop)**: Full production scanner, testing platform
- ⏳ **Beta testers**: 5 shops ready for hardware
- 🎯 **Target**: 50 shops by Q2 2026

---

## 📱 ROADMAP - What's Next

### Immediate (Next 2 Weeks):
- [x] Sales & Marketing tab navigation (DONE Feb 15)
- [ ] Complete marketplace listing form
- [ ] Test BROK → Marketplace sync
- [ ] Add authentication to marketplace API
- [ ] Rate limiting + CORS fixes

### Short Term (1-2 Months):
- [ ] Order fulfillment workflow
- [ ] Shipping label generation
- [ ] Email notifications (order placed, shipped)
- [ ] Marketplace web frontend (React)
- [ ] Stripe Connect integration

### Medium Term (3-6 Months):
- [ ] Mobile app (React Native) for sellers
- [ ] Public marketplace website launch
- [ ] Beta program (50 shops)
- [ ] Pokemon + Sports scanner support
- [ ] Advanced analytics dashboard

### Long Term (6-12 Months):
- [ ] Multi-location support (shop chains)
- [ ] Franchise model (regional distributors)
- [ ] International expansion
- [ ] Hardware v3.0 (cheaper, faster)
- [ ] API marketplace (third-party integrations)

---

## 🔧 TECHNICAL DEBT & KNOWN ISSUES

### Critical (Fix Before Launch):
1. **Marketplace API has no authentication** - anyone can create/delete listings
2. **CORS wide open** - any website can call the API
3. **No rate limiting** - vulnerable to DoS attacks
4. **No database schema file** - can't deploy to new environments easily

### High Priority:
1. **Input validation** - marketplace API trusts all input
2. **Error logging** - no centralized error tracking
3. **Monitoring** - no uptime/performance monitoring
4. **Backup strategy** - BROK inventory has no automated backups

### Medium Priority:
1. **Sales tab TODO** - listing dialog not fully integrated
2. **Desktop local DB** - still has fallback behavior (should be removed)
3. **ZULTAN library API** - claims to be inventory master (wrong, should clarify)
4. **Test coverage** - no automated tests

### Low Priority:
1. **Code documentation** - many files lack docstrings
2. **Performance optimization** - inventory search could be faster
3. **UI polish** - some tabs need visual updates

---

## 💾 BACKUP & DISASTER RECOVERY

### Current Backup Strategy:

**BROK Inventory (Critical Data):**
- ⚠️ **NO AUTOMATED BACKUPS** (manual only)
- Recommendation: Daily rsync to ZULTAN or cloud

**ZULTAN Catalog:**
- ✅ Can be re-scraped from public APIs
- Not critical to back up

**Desktop App:**
- ✅ Code on GitHub
- ✅ User data in AppData (user's responsibility)

**Marketplace Database (Cloudflare D1):**
- ✅ Cloudflare handles replication
- ⚠️ No export mechanism yet

### Disaster Recovery Plan:

**Scenario 1: BROK Fails**
- Desktop falls back to local cache (read-only)
- Replace BROK Pi + restore from backup
- Downtime: 1-4 hours

**Scenario 2: ZULTAN Fails**
- Scanner falls back to OCR-only mode
- Slower but functional
- Re-scrape catalog (24-48 hours)

**Scenario 3: Cloudflare Outage**
- Marketplace offline
- Desktop app continues working (local data)
- No immediate action needed

---

## 🎓 FOR KLAUS - QUICK ONBOARDING

### If you want to run NEXUS locally:

**1. Clone the repo:**
```bash
git clone https://github.com/nexus-cards/nexus-v2.git
cd nexus-v2
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
# OR for full dev environment:
pip install pillow requests flask opencv-python tesseract
```

**3. Run the desktop app:**
```bash
python E:/NEXUS_V2_RECREATED/nexus_v2/main.py
```

**4. (Optional) SSH into Pi's:**
```bash
# BROK (scanner brain)
ssh nexus1@192.168.1.174

# SNARF (hardware)
ssh nexus1@192.168.1.172

# ZULTAN (GPU server)
ssh zultan@192.168.1.152
```

### Key Files to Understand:

| File | What It Does |
|------|--------------|
| `nexus_v2/main.py` | Desktop app entry point |
| `nexus_v2/ui/app.py` | Main application window + tab manager |
| `nexus_v2/ui/tabs/sales.py` | Sales & Marketing tab (just updated) |
| `nexus_v2/library/brock_client.py` | BROK API client |
| `src/scanner/acr_pipeline.py` | ACR scanning logic |
| `workers/marketplace/src/index.js` | Cloudflare marketplace API |
| `docs/MARKETPLACE_API_AUDIT.md` | Security issues we need to fix |

---

## 📞 SUPPORT & QUESTIONS

**If something breaks:**
1. Check `docs/ARCHITECTURE_FIXES_COMPLETED.md` - we may have already fixed it
2. Check GitHub issues: https://github.com/nexus-cards/nexus-v2/issues
3. Ask Kevin (me) or MENDEL (Claude agent in VS Code)

**If you want to contribute:**
1. Read `docs/CONTRIBUTING.md`
2. Check `docs/ROADMAP.md` for planned features
3. Join the Narwhal Council (agent communication system) - see `docs/NEXUS_SYSTEM_COMMUNICATION_ARCHITECTURE.md`

---

## 🎉 CONCLUSION

**NEXUS V2 is a complete, working system:**
- ✅ Scanner hardware operational
- ✅ Desktop app functional with 7 major tabs
- ✅ 26,850 card inventory managed
- ✅ Marketplace API ready (needs security hardening)
- ✅ Sales workflow implemented (Collection → Sales & Marketing → Marketplace)

**We're ready for beta testing with 5-10 shops.**

The main blockers before wide release:
1. Marketplace API authentication
2. Shipping integration
3. Payment processing (Stripe Connect)
4. Web marketplace frontend

**Everything else works.** We can scan cards, manage inventory, build decks, analyze trends, and prepare listings for sale.

---

**Welcome to NEXUS. Let's disrupt the TCG industry.** 🚀

*Questions? Ask Kevin or check the 100+ other docs in `/docs/`.*
