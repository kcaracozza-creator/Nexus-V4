# NEXUS Marketplace API Audit
**Date:** 2026-02-15 23:00 EST
**Worker:** nexus-marketplace-api
**URL:** https://nexus-marketplace-api.kcaracozza.workers.dev
**Source:** E:\NEXUS_V2_RECREATED\workers\marketplace\src\index.js

---

## 📊 SUMMARY

**Total Endpoints:** 30+
**Database:** D1 (nexus-marketplace)
**Tables:** 20 (cards, users, sellers, listings, inventory, scans, orders, cart, wallets, reviews, licenses, etc.)
**External Services:** Workers AI, Vectorize
**Security Level:** ⚠️ **CRITICAL ISSUES FOUND**

---

## 🔴 CRITICAL SECURITY ISSUES

### 1. No Authentication - ALL ENDPOINTS PUBLIC ⚠️

**Problem:** Zero authentication on any endpoint
- Anyone can create users
- Anyone can create listings
- Anyone can create orders
- Anyone can access all user data
- Anyone can modify inventory
- Anyone can validate licenses

**Current Code:**
```javascript
// Line 698-708: No auth checks
export default {
  async fetch(request, env) {
    // No API key validation
    // No Authorization header check
    // No rate limiting
    const db = env.DB;
    // Direct database access for any request
  }
}
```

**Required Fix:**
```javascript
// Add authentication middleware
function requireAuth(request) {
  const apiKey = request.headers.get('X-API-Key');
  const validKeys = env.API_KEYS?.split(',') || [];
  if (!validKeys.includes(apiKey)) {
    return err('Unauthorized', 401);
  }
  return null;
}

// Check auth on protected endpoints
if (!path.startsWith('/health') && !path.startsWith('/v1/stats')) {
  const authError = requireAuth(request);
  if (authError) return authError;
}
```

**Impact:** CRITICAL - Anyone can read/write all marketplace data

---

### 2. CORS Wide Open - Any Origin Allowed ⚠️

**File:** index.js:7-11

**Problem:**
```javascript
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',  // ← ALLOWS ANYONE
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};
```

**Issues:**
- Any website can call this API
- No origin whitelist
- Enables CSRF attacks
- Cookie/credential theft risk

**Required Fix:**
```javascript
const ALLOWED_ORIGINS = [
  'https://nexus-marketplace.kcaracozza.workers.dev',
  'https://master.nexus-dev-dashboard.pages.dev',
  // Add shop domains here
];

function getCORSHeaders(origin) {
  if (ALLOWED_ORIGINS.includes(origin)) {
    return {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key',
      'Access-Control-Allow-Credentials': 'true',
    };
  }
  return {}; // No CORS for unauthorized origins
}
```

---

### 3. No Rate Limiting ⚠️

**Problem:** API can be spammed/DoS'd
- No request throttling
- No IP-based limits
- No cost protection (Workers AI calls cost money)
- Bulk operations unprotected (vectorBulkInsert can process 500 cards)

**Required Fix:**
- Use Cloudflare Rate Limiting rules
- OR implement token bucket in Worker
- Add KV-based request counter

---

### 4. SQL Injection Risk (LOW) ⚠️

**Files:** Multiple functions

**Concern:** Dynamic SQL construction
```javascript
// Line 183-184: Sort column from user input
const validSorts = ['created_at', 'price'];
const sortCol = validSorts.includes(sort) ? sort : 'created_at';
sql += ` ORDER BY l.${sortCol} DESC LIMIT ? OFFSET ?`;
```

**Analysis:**
- ✅ Uses parameterized queries (`.bind(...p)`)
- ✅ Whitelist validation for sort columns
- ⚠️ String interpolation for column names (lines 98, 183, 360)

**Recommendation:** Continue using whitelist approach, document why string interpolation is safe

---

### 5. Wallet Auto-Creation Abuse ⚠️

**File:** index.js:409-417

**Problem:**
```javascript
async function walletGet(db, userId) {
  let wallet = await db.prepare('SELECT * FROM wallets WHERE user_id = ?').bind(userId).first();
  if (!wallet) {
    // Auto-create wallet - ANYONE can trigger this
    await db.prepare('INSERT INTO wallets (user_id) VALUES (?)').bind(userId).run();
    wallet = await db.prepare('SELECT * FROM wallets WHERE user_id = ?').bind(userId).first();
  }
  return json({ wallet });
}
```

**Issues:**
- Attacker can create millions of wallets
- No user validation (does user_id exist?)
- No rate limiting
- Database bloat

**Required Fix:**
- Only create wallets when users are created
- OR require authentication to create wallet
- Validate user exists before creating wallet

---

## 🟡 ARCHITECTURAL CONCERNS

### 6. Inventory Table - Conflicts with BROK? ⚠️

**Problem:** Marketplace has its own `inventory` table
- BROK has `nexus_library.db` with 26,850 cards
- Marketplace has separate `inventory` table
- No obvious sync mechanism
- Which is source of truth?

**Current Architecture:**
```
BROK (/mnt/nexus_data/databases/nexus_library.db)
  ↓
  26,850 cards - Shop's actual inventory

Marketplace (D1: nexus-marketplace)
  ↓
  inventory table - SEPARATE inventory?
```

**Questions:**
1. Is marketplace `inventory` for shop-to-marketplace sync?
2. Or is it for marketplace-only card tracking?
3. How does BROK sync inventory to marketplace?
4. Should there be a webhook or sync API?

**Recommendation:**
- Document the relationship between BROK inventory and marketplace inventory
- Add sync endpoints: POST /v1/sync/brok-inventory
- OR clarify marketplace inventory is for marketplace listings only

---

### 7. Scans Table - Should Sync with BROK Scanner ⚠️

**File:** index.js:267-293

**Problem:** Marketplace has `scans` table but no BROK integration
- BROK scanner creates scans (ACR pipeline)
- Marketplace stores scans separately
- No sync mechanism

**Required Integration:**
```javascript
// BROK should POST scan results to marketplace
// POST /v1/scans
{
  "scanner_id": "BROK-192.168.1.174",
  "card_id": "uuid-from-cards-table",
  "image_r2_key": "scans/2026-02-15/scan123.jpg",
  "acr_result": {...},
  "acr_confidence": 0.98,
  "acr_stage": "art_match",
  "grade_result": {...}
}
```

**Recommendation:**
- Add BROK scanner integration endpoint
- Document scan upload workflow
- Add authentication for scanner uploads

---

### 8. No ZULTAN Integration ⚠️

**Problem:** No obvious connection to ZULTAN's card catalog
- ZULTAN has 521K MTG + 19.8K Pokemon + 1.84M sports cards
- Marketplace has separate `cards` table
- How do cards get populated?

**Expected Flow:**
```
Shop Scanner → BROK → Marketplace (listing)
                ↓
           Lookup via ZULTAN catalog
```

**Current Reality:**
- Marketplace `cards` table is independent
- No ZULTAN catalog lookup API calls
- Manual card entry via POST /v1/cards?

**Recommendation:**
- Add ZULTAN catalog integration
- GET /v1/catalog/search → proxies to ZULTAN:8000
- Auto-populate marketplace cards from ZULTAN catalog

---

## 🟢 GOOD IMPLEMENTATIONS

### ✅ What's Done Right

1. **Clean REST Design**
   - Consistent `/v1/resource` structure
   - Proper HTTP verbs (GET/POST/PUT/DELETE)
   - Standard JSON responses

2. **Parameterized Queries**
   - Uses `.bind(...p)` throughout
   - No raw string concatenation in WHERE clauses
   - Prevents most SQL injection

3. **UUID Generation**
   - Uses `crypto.randomUUID()`
   - Proper unique ID generation

4. **Error Handling**
   - Centralized `json()` and `err()` functions
   - Try-catch in main router
   - Consistent error format

5. **Workers AI Integration**
   - ResNet-50 for image classification
   - Llama 3.1 for card descriptions
   - BGE embeddings for semantic search

6. **Vectorize Integration**
   - Semantic search via embeddings
   - Metadata filtering
   - Bulk insert support

7. **License Validation**
   - Activation limits
   - Expiration checks
   - Machine ID tracking

8. **Database Relationships**
   - JOINs for listings (card + seller data)
   - Order items tracking
   - Review aggregation to seller ratings

---

## 🔍 MISSING FEATURES

### 9. No Database Schema File

**Problem:** No schema.sql or migrations
- How were tables created?
- What are the column types?
- What indexes exist?
- How to deploy to new environment?

**Required:**
- Create `schema.sql` with full table definitions
- Document all indexes
- Add migration strategy

---

### 10. No Input Validation

**Problem:** Minimal validation beyond required fields
```javascript
// Line 72: Only checks if card_name exists
if (!card_name) return err('card_name required');
// No validation for:
// - card_name length (max?)
// - price format (negative prices?)
// - year range (1900-2100?)
// - quantity limits (max 999?)
// - email format
// - username format (special chars?)
```

**Required Fix:**
```javascript
function validateCardData(body) {
  const errors = [];
  if (!body.card_name) errors.push('card_name required');
  if (body.card_name?.length > 200) errors.push('card_name too long');
  if (body.price_market < 0) errors.push('price cannot be negative');
  if (body.year && (body.year < 1900 || body.year > 2100)) errors.push('invalid year');
  // ... etc
  if (errors.length) return err(errors.join(', '));
  return null;
}
```

---

### 11. No Request Logging/Monitoring

**Problem:** Only console.error on exceptions
- No request logging
- No request ID tracking
- No performance monitoring
- Hard to debug production issues

**Required:**
```javascript
// Add request ID and logging
const requestId = crypto.randomUUID();
console.log({
  requestId,
  method: request.method,
  path: url.pathname,
  timestamp: new Date().toISOString(),
});
// Include requestId in error responses
```

---

### 12. No Pagination Metadata

**Problem:** Paginated endpoints don't return total count
```javascript
// Line 59: Returns count of current page only
return json({ cards: r.results, count: r.results.length, offset, limit });
// Missing: total_count (how many cards exist total?)
```

**Required:**
```javascript
const total = await db.prepare('SELECT COUNT(*) as c FROM cards WHERE 1=1 ...').first();
return json({
  cards: r.results,
  count: r.results.length,
  offset,
  limit,
  total: total.c, // ← Add this
  has_more: offset + r.results.length < total.c
});
```

---

## 🎯 ACTION ITEMS

### Priority 1 - CRITICAL (Security)
- [ ] **Add API Key Authentication** - Prevent unauthorized access
- [ ] **Fix CORS Policy** - Whitelist specific origins only
- [ ] **Add Rate Limiting** - Prevent abuse/DoS
- [ ] **Fix Wallet Auto-Creation** - Require auth or user validation
- [ ] **Document Authentication Strategy** - API keys? OAuth? JWT?

### Priority 2 - HIGH (Architecture)
- [ ] **Document Inventory Sync** - How does BROK sync to marketplace?
- [ ] **Add BROK Scanner Integration** - Webhook for scan uploads
- [ ] **Add ZULTAN Catalog Integration** - Lookup cards from catalog
- [ ] **Create Database Schema File** - schema.sql with migrations
- [ ] **Clarify Data Flow** - Scanner → BROK → Marketplace → Listing

### Priority 3 - MEDIUM (Features)
- [ ] **Add Input Validation** - Validate all fields properly
- [ ] **Add Request Logging** - Track all requests with IDs
- [ ] **Add Pagination Metadata** - Include total counts
- [ ] **Add Health Check Details** - DB connection status, table counts
- [ ] **Add Admin Endpoints** - Bulk operations, cleanup, stats

### Priority 4 - LOW (Nice to Have)
- [ ] **Add Request Caching** - Cache card lookups
- [ ] **Add Bulk Operations** - Batch create/update
- [ ] **Add Soft Deletes** - Mark deleted instead of removing
- [ ] **Add Audit Trail** - Track all changes to orders/listings
- [ ] **Add Webhooks** - Notify on order status changes

---

## 📋 ARCHITECTURE COMPLIANCE

### Current State: ⚠️ **INCOMPLETE**

**Missing Integrations:**
- ❌ No BROK inventory sync
- ❌ No BROK scanner webhook
- ❌ No ZULTAN catalog lookup
- ❌ No desktop app integration (how does desktop use this?)

**Expected Architecture:**
```
┌─────────────────────────────────────────┐
│  Desktop (UI)                           │
│  - Manages shop's listings              │
│  - Views marketplace                    │
└─────────────────┬───────────────────────┘
                  │ API calls
                  ▼
┌─────────────────────────────────────────┐
│  BROK (Scanner Brain)                   │
│  ├─ nexus_library.db (26,850 cards)     │
│  ├─ Scans → POST /v1/scans              │
│  └─ Inventory sync → POST /v1/inventory │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Marketplace Worker (Cloudflare)        │
│  ├─ D1 Database (listings, orders)      │
│  ├─ Vectorize (semantic search)         │
│  └─ Workers AI (classify, describe)     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  ZULTAN (Catalog Master)                │
│  ├─ Card catalog (1.84M+ cards)         │
│  ├─ Metadata lookup                     │
│  └─ Price data (PSA, TCDB, Scryfall)    │
└─────────────────────────────────────────┘
```

**What's Missing:**
1. BROK → Marketplace sync endpoints
2. Marketplace → ZULTAN catalog lookup
3. Authentication for scanner/shop uploads
4. Desktop app integration (how does it list cards for sale?)

---

## 🔧 FILES TO CREATE

1. **E:\NEXUS_V2_RECREATED\workers\marketplace\schema.sql**
   - Full D1 schema with all tables
   - Indexes
   - Foreign keys

2. **E:\NEXUS_V2_RECREATED\workers\marketplace\README.md**
   - API documentation
   - Authentication guide
   - Integration examples
   - Deployment instructions

3. **E:\NEXUS_V2_RECREATED\workers\marketplace\src\auth.js**
   - API key validation
   - Role-based access control
   - Rate limiting logic

4. **E:\NEXUS_V2_RECREATED\workers\marketplace\src\validators.js**
   - Input validation functions
   - Schema validation
   - Data sanitization

---

## 📝 COMPARISON WITH MAIN CODEBASE AUDIT

### Similar Issues Found:
- ✅ Architecture unclear (same as zultan_library_api.py confusion)
- ✅ Missing integration points (BROK/ZULTAN/Desktop)
- ✅ No clear sync mechanism (like deck_builder.py bypassing BROK)

### Marketplace-Specific Issues:
- ❌ No authentication (main codebase assumes local network)
- ❌ Public internet exposure (main codebase is private)
- ❌ CORS wide open (main codebase doesn't have CORS)

---

## ✅ VERIFICATION CHECKLIST

Before deploying to production:
- [ ] API keys configured in wrangler.toml
- [ ] CORS origins whitelisted
- [ ] Rate limiting enabled
- [ ] Schema documented
- [ ] BROK sync tested
- [ ] ZULTAN catalog integration tested
- [ ] Desktop app integration tested
- [ ] All endpoints have auth
- [ ] All inputs validated
- [ ] Error handling comprehensive
- [ ] Request logging enabled
- [ ] Monitoring/alerts configured

---

## 🚀 DEPLOYMENT SAFETY

**Current Status:** ⚠️ **NOT PRODUCTION READY**

**Blockers:**
1. No authentication - CRITICAL
2. CORS wide open - CRITICAL
3. No rate limiting - HIGH
4. No BROK integration - HIGH
5. No ZULTAN integration - HIGH

**Recommended Next Steps:**
1. Add authentication FIRST (block all public access)
2. Add CORS whitelist
3. Add rate limiting
4. Document and implement BROK sync
5. Add ZULTAN catalog integration
6. Create schema.sql
7. Test full integration flow
8. Deploy to production with monitoring

---

**Session Complete!** Marketplace API audited. Found 12 issues (4 critical security, 3 architectural, 5 missing features). Ready for remediation phase. 🔍
