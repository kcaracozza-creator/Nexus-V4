# NEXUS V2 - COMPLETE PROCESS FLOWS
**Every Process, Input to Output**
**Date:** February 15, 2026

---

## 📋 TABLE OF CONTENTS

1. [Card Scanning Flow](#1-card-scanning-flow)
2. [List Card for Sale Flow](#2-list-card-for-sale-flow)
3. [Marketplace Listing Creation Flow](#3-marketplace-listing-creation-flow)
4. [Customer Purchase Flow](#4-customer-purchase-flow)
5. [Order Fulfillment Flow](#5-order-fulfillment-flow)
6. [Inventory Sync Flow](#6-inventory-sync-flow)
7. [Price Update Flow](#7-price-update-flow)
8. [Deck Building Flow](#8-deck-building-flow)

---

## 1. CARD SCANNING FLOW

### INPUT: Physical card placed in scanner

### PROCESS:

```
Step 1: USER ACTION
├─ User places card in scanner tray
└─ User clicks "Scan" in Desktop App

Step 2: DESKTOP → SNARF (HTTP)
├─ Desktop sends: POST http://192.168.1.172:5003/api/scan/start
├─ Request body: {mode: "auto", pipeline: "acr"}
└─ SNARF receives scan command

Step 3: SNARF HARDWARE CONTROL
├─ SNARF activates LED ring (GPIO 14)
├─ SNARF triggers CZUR camera (USB)
├─ CZUR captures high-res image (4K)
├─ Image saved: /tmp/scan_[timestamp].jpg
└─ SNARF returns: {image_path: "/tmp/scan_123.jpg", status: "captured"}

Step 4: SNARF → BROK ART RECOGNITION (HTTP)
├─ SNARF sends: POST http://192.168.1.174:5002/api/art/match
├─ Request body: {image: base64_encoded_image}
└─ BROK receives image for art matching

Step 5: BROK CORAL TPU PROCESSING
├─ BROK decodes image
├─ BROK extracts art region (top 60% of card)
├─ BROK generates embedding (512-dim vector)
├─ BROK queries FAISS index (370K MTG cards)
├─ FAISS returns top 5 matches with similarity scores
├─ If score ≥ 0.95: SUCCESS
│  └─ Returns: {card_id: "abc123", name: "Lightning Bolt", set: "LEA", confidence: 0.98}
└─ If score < 0.95: FALLBACK TO STEP 6

Step 6: SNARF OCR EXTRACTION (if art match failed)
├─ SNARF runs Tesseract OCR
├─ OCR extracts text from 5 regions:
│  ├─ Name (top 20%)
│  ├─ Mana cost (top-right corner)
│  ├─ Type line (middle)
│  ├─ Set symbol (bottom-left)
│  └─ Collector number (bottom)
├─ Regex patterns extract structured data
├─ If confidence ≥ 0.95: SUCCESS
│  └─ Returns: {name: "Lightning Bolt", set: "LEA", confidence: 0.96}
└─ If confidence < 0.95: FALLBACK TO STEP 7

Step 7: SNARF → ZULTAN METADATA LOOKUP (HTTP)
├─ SNARF sends: GET http://192.168.1.152:8000/api/mtg/search?q=Lightning+Bolt&set=LEA
└─ ZULTAN receives lookup request

Step 8: ZULTAN DATABASE QUERY
├─ ZULTAN queries card_lookup.json (521K cards)
├─ Fuzzy match on card name + set code
├─ Returns: {
│    id: "uuid",
│    name: "Lightning Bolt",
│    set: "Limited Edition Alpha",
│    set_code: "LEA",
│    collector_number: "161",
│    rarity: "common",
│    price_usd: 250.00,
│    image_url: "https://cards.scryfall.io/...",
│    oracle_id: "...",
│    colors: ["R"],
│    mana_cost: "{R}",
│    type_line: "Instant"
│  }
└─ ZULTAN → SNARF: Full card metadata

Step 9: SNARF → DESKTOP (WebSocket)
├─ SNARF sends card data to Desktop via WebSocket
└─ Desktop receives: {card: {...}, status: "identified", confidence: 0.98}

Step 10: DESKTOP → BROK INVENTORY ADD (HTTP)
├─ Desktop sends: POST http://192.168.1.174:5000/api/library/add
├─ Request body: {
│    card_name: "Lightning Bolt",
│    set_code: "LEA",
│    collector_number: "161",
│    quantity: 1,
│    price: 250.00,
│    condition: "NM",
│    foil: false,
│    image_url: "https://..."
│  }
└─ BROK receives inventory add request

Step 11: BROK DATABASE WRITE
├─ BROK opens SQLite: /mnt/nexus_data/databases/nexus_library.db
├─ BROK executes:
│    INSERT INTO cards (card_name, set_code, collector_number, quantity, price, condition, foil, date_added)
│    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
├─ BROK generates call_number: "A1-042" (box A1, position 42)
├─ BROK commits transaction
└─ BROK returns: {success: true, call_number: "A1-042", total_cards: 26851}

Step 12: DESKTOP UI UPDATE
├─ Desktop updates inventory count: 26,850 → 26,851
├─ Desktop updates total value: $3,860.03 → $4,110.03
├─ Desktop shows notification: "Lightning Bolt added to inventory"
└─ Desktop refreshes Collection tab
```

### OUTPUT: Card in inventory, database updated, UI refreshed

**API Calls Made:**
- Desktop → SNARF: `POST /api/scan/start`
- SNARF → BROK: `POST /api/art/match`
- SNARF → ZULTAN: `GET /api/mtg/search`
- Desktop → BROK: `POST /api/library/add`

**Data Flow:**
`Physical Card → Image → Embedding → FAISS → Metadata → Database → UI`

**Time:** ~1-2 seconds (most cards), ~5-10 seconds (if OCR needed)

---

## 2. LIST CARD FOR SALE FLOW

### INPUT: User right-clicks card in Collection tab

### PROCESS:

```
Step 1: USER ACTION
├─ User right-clicks on card in Collection tab
├─ Context menu appears
└─ User clicks "List for Sale"

Step 2: DESKTOP TAB NAVIGATION
├─ collection_tab._list_for_sale() is called
├─ Gets selected card from tree:
│    card_group = {
│      name: "Lightning Bolt",
│      set_name: "Limited Edition Alpha",
│      set_code: "LEA",
│      collector_number: "161",
│      quantity: 1,
│      foil: false,
│      price: 250.00,
│      call_number: "A1-042"
│    }
├─ Checks if sales_tab and parent_notebook exist
└─ Switches to Sales tab:
     for i in range(notebook.index('end')):
       if 'Sales' in notebook.tab(i, 'text'):
         notebook.select(i)

Step 3: DESKTOP SALES TAB ACTIVATION
├─ sales_tab.open_listing_for_card(card_group) is called
├─ Sales tab receives card data
└─ Sales tab displays card info

Step 4: LISTING FORM PRE-POPULATION
├─ Card Name: "Lightning Bolt" (read-only)
├─ Set: "Limited Edition Alpha (LEA)" (read-only)
├─ Condition: "Near Mint" (dropdown)
├─ Price: $250.00 (from market price, editable)
├─ Quantity: 1 (max = available in inventory)
├─ Platform: "NEXUS Marketplace" (dropdown: TCGPlayer/eBay/NEXUS/Manual)
└─ Notes: (optional text field)

Step 5: USER FILLS FORM
├─ User reviews pre-filled data
├─ User adjusts price: $245.00 (undercut market)
├─ User sets quantity: 1
├─ User selects platform: "NEXUS Marketplace"
└─ User clicks "Create Listing"

Step 6: DESKTOP LOCAL STORAGE
├─ listing_data = {
│    id: uuid(),
│    card_name: "Lightning Bolt",
│    set_code: "LEA",
│    set_name: "Limited Edition Alpha",
│    collector_number: "161",
│    price: 245.00,
│    quantity: 1,
│    condition: "NM",
│    foil: false,
│    platform: "NEXUS Marketplace",
│    status: "draft",
│    created_at: datetime.now(),
│    call_number: "A1-042",
│    image_url: "https://cards.scryfall.io/..."
│  }
├─ Desktop saves to local array: sales_tab.listed_items.append(listing_data)
└─ Desktop adds to Active Listings table (UI)

Step 7: DESKTOP UI UPDATE
├─ Stats dashboard updates:
│  ├─ Listed Items: 0 → 1
│  └─ Total Sales: $0.00 → $245.00
├─ Active Listings table shows new row:
│  └─ Lightning Bolt | LEA | $245.00 | 1 | NEXUS Marketplace | Draft
└─ "Sync to Marketplace" button becomes active
```

### OUTPUT: Listing created locally, ready to sync

**API Calls Made:** None (all local)

**Data Flow:**
`Collection Tab → Sales Tab → Local Array → UI Update`

**Time:** Instant (local only)

---

## 3. MARKETPLACE LISTING CREATION FLOW

### INPUT: User clicks "Sync to NEXUS Marketplace"

### PROCESS:

```
Step 1: USER ACTION
├─ User reviews listings in Active Listings table
├─ User clicks "Sync to NEXUS Marketplace" button
└─ Desktop shows confirmation dialog: "Upload 1 listing(s)?"

Step 2: DESKTOP MARKETPLACE CLIENT
├─ Desktop imports: from integrations.marketplace_client import MarketplaceClient
├─ Desktop initializes: client = MarketplaceClient()
├─ Client reads config:
│    marketplace_url = "https://nexus-marketplace-api.kcaracozza.workers.dev"
│    api_key = os.getenv('NEXUS_API_KEY') or config.get('marketplace.api_key')
│    user_id = config.get('user.id')
│    shop_id = config.get('shop.id')
└─ Client prepares request

Step 3: DESKTOP → MARKETPLACE API (HTTPS)
├─ Desktop sends: POST https://nexus-marketplace-api.kcaracozza.workers.dev/v1/listings
├─ Headers:
│    Content-Type: application/json
│    Authorization: Bearer <api_key> (⚠️ NOT IMPLEMENTED YET)
│    X-Shop-ID: <shop_id>
├─ Request body: {
│    seller_id: "user-uuid-123",
│    card_id: null, (will be created if doesn't exist)
│    card_name: "Lightning Bolt",
│    set_code: "LEA",
│    set_name: "Limited Edition Alpha",
│    collector_number: "161",
│    condition: "NM",
│    grade: null,
│    grade_service: null,
│    price: 245.00,
│    quantity: 1,
│    currency: "USD",
│    image_r2_key: null, (future: upload to R2)
│    scan_data: {call_number: "A1-042", scanned_at: "2026-02-15T..."}
│  }
└─ Cloudflare Worker receives request

Step 4: CLOUDFLARE WORKER PROCESSING
├─ Worker validates request (⚠️ currently skips auth)
├─ Worker checks if card exists in catalog:
│    SELECT * FROM cards WHERE card_name = ? AND set_code = ?
├─ If card doesn't exist:
│    Worker creates card:
│      INSERT INTO cards (id, card_name, set_code, set_name, collector_number, card_type, rarity, year, image_url)
│      VALUES (uuid(), 'Lightning Bolt', 'LEA', 'Limited Edition Alpha', '161', 'mtg', 'common', 1993, '...')
│    card_id = uuid()
└─ Else: card_id = existing_card_id

Step 5: CLOUDFLARE D1 DATABASE WRITE
├─ Worker executes:
│    INSERT INTO listings (
│      id, card_id, seller_id, price, condition, grade, grade_service,
│      quantity, currency, image_r2_key, scan_data, status, created_at
│    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', datetime('now'))
├─ Worker binds values: [uuid(), card_id, seller_id, 245.00, 'NM', null, null, 1, 'USD', null, '{"call_number":"A1-042"}', 'active']
├─ D1 commits transaction
└─ Worker returns: {
     success: true,
     listing_id: "listing-uuid-456",
     card_id: "card-uuid-789",
     status: "active",
     created_at: "2026-02-15T12:34:56Z"
   }

Step 6: DESKTOP RECEIVES RESPONSE
├─ Desktop parses JSON response
├─ Desktop updates local listing:
│    listing.marketplace_id = "listing-uuid-456"
│    listing.status = "Listed"
│    listing.synced_at = datetime.now()
├─ Desktop updates Active Listings table:
│    Status: Draft → Listed
└─ Desktop shows success message: "1 listing synced to NEXUS Marketplace!"

Step 7: DESKTOP STATS UPDATE
├─ Active Platforms: 0 → 1
├─ Listed Items: 1 (stays same)
└─ Status indicator turns green
```

### OUTPUT: Listing live on marketplace, visible to customers

**API Calls Made:**
- Desktop → Marketplace: `POST /v1/listings`

**Data Flow:**
`Desktop Local → HTTPS → Cloudflare Worker → D1 Database → Response → Desktop Update`

**Time:** ~500ms - 2 seconds

---

## 4. CUSTOMER PURCHASE FLOW

### INPUT: Customer clicks "Buy Now" on marketplace website

### PROCESS:

```
Step 1: CUSTOMER ACTION
├─ Customer browses marketplace website
├─ Customer searches: "Lightning Bolt LEA"
├─ Customer sees listing: $245.00, NM, MTTGG (shop name)
└─ Customer clicks "Add to Cart"

Step 2: MARKETPLACE WEBSITE → CLOUDFLARE (HTTPS)
├─ Website sends: POST /v1/cart
├─ Request body: {
│    user_id: "customer-uuid-999",
│    listing_id: "listing-uuid-456",
│    quantity: 1
│  }
└─ Worker receives cart request

Step 3: CLOUDFLARE D1 CART ADD
├─ Worker executes:
│    INSERT INTO cart_items (id, user_id, listing_id, quantity, added_at)
│    VALUES (uuid(), 'customer-uuid-999', 'listing-uuid-456', 1, datetime('now'))
└─ Worker returns: {cart_item_id: "cart-uuid-111", success: true}

Step 4: CUSTOMER PROCEEDS TO CHECKOUT
├─ Customer clicks "Checkout"
├─ Website shows cart summary:
│    1x Lightning Bolt (LEA, NM) - $245.00
│    Shipping: $5.00
│    Tax: $15.00
│    Total: $265.00
└─ Customer enters shipping address + payment method

Step 5: MARKETPLACE WEBSITE → CLOUDFLARE (HTTPS)
├─ Website sends: POST /v1/orders
├─ Request body: {
│    buyer_id: "customer-uuid-999",
│    seller_id: "user-uuid-123",
│    items: [{
│      listing_id: "listing-uuid-456",
│      card_name: "Lightning Bolt",
│      price: 245.00,
│      quantity: 1,
│      condition: "NM"
│    }],
│    shipping_address: "123 Main St, City, State 12345",
│    shipping_cost: 5.00,
│    notes: null
│  }
└─ Worker receives order request

Step 6: CLOUDFLARE ORDER CREATION
├─ Worker generates order_id = uuid()
├─ Worker calculates:
│    subtotal = 245.00
│    shipping = 5.00
│    total = 250.00
├─ Worker executes:
│    INSERT INTO orders (
│      id, buyer_id, seller_id, status, subtotal, shipping_cost, total,
│      shipping_address, notes, created_at
│    ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, datetime('now'))
└─ Worker inserts order items:
     INSERT INTO order_items (id, order_id, listing_id, card_name, price, quantity, condition)
     VALUES (uuid(), order_id, 'listing-uuid-456', 'Lightning Bolt', 245.00, 1, 'NM')

Step 7: CLOUDFLARE LISTING UPDATE
├─ Worker marks listing as sold:
│    UPDATE listings
│    SET status = 'sold', sold_at = datetime('now')
│    WHERE id = 'listing-uuid-456'
└─ Worker clears cart:
     DELETE FROM cart_items WHERE user_id = 'customer-uuid-999'

Step 8: CLOUDFLARE → DESKTOP NOTIFICATION (WebSocket or Poll)
├─ ⚠️ NOT IMPLEMENTED YET
├─ Future: WebSocket push notification
├─ Current: Desktop polls /v1/orders?seller_id=X&status=pending
└─ Desktop receives: {
     orders: [{
       order_id: "order-uuid-888",
       buyer_email: "customer@example.com",
       card_name: "Lightning Bolt",
       quantity: 1,
       price: 245.00,
       shipping_address: "123 Main St...",
       status: "pending",
       created_at: "2026-02-15T13:00:00Z"
     }],
     count: 1
   }

Step 9: DESKTOP SALES TAB UPDATE
├─ Desktop receives new order
├─ Desktop adds to "Pending Orders" section
├─ Desktop shows notification: "New order! Lightning Bolt x1 - $245.00"
├─ Desktop plays sound alert
└─ Stats update:
     Pending: 0 → 1
     Total Sales: $245.00 → $490.00 (if multiple listings)
```

### OUTPUT: Order created, seller notified, inventory reserved

**API Calls Made:**
- Website → Marketplace: `POST /v1/cart`
- Website → Marketplace: `POST /v1/orders`
- Desktop → Marketplace: `GET /v1/orders?seller_id=X&status=pending`

**Data Flow:**
`Customer Website → Cloudflare → D1 Database → Desktop Notification`

**Time:** ~1-3 seconds

---

## 5. ORDER FULFILLMENT FLOW

### INPUT: Seller clicks "Ship Order" in Desktop Sales tab

### PROCESS:

```
Step 1: SELLER ACTION
├─ Seller opens Sales & Marketing tab
├─ Seller sees order in "Pending Orders" section:
│    Order #12345
│    Lightning Bolt (LEA, NM) x1 - $245.00
│    Ship to: John Doe, 123 Main St...
│    Status: Pending
├─ Seller clicks "View Details"
└─ Seller clicks "Ship Order"

Step 2: DESKTOP SHIPPING LABEL GENERATION
├─ ⚠️ NOT IMPLEMENTED YET
├─ Future: Desktop → Shippo/EasyPost API
├─ Current: Manual shipping label creation
├─ Seller enters tracking number manually
└─ Seller confirms shipment

Step 3: DESKTOP → BROK INVENTORY UPDATE (HTTP)
├─ Desktop sends: DELETE http://192.168.1.174:5000/api/library/remove?call_number=A1-042&quantity=1
└─ BROK receives inventory decrement request

Step 4: BROK DATABASE UPDATE
├─ BROK finds card by call_number: "A1-042"
├─ BROK checks current quantity: 1
├─ BROK executes:
│    DELETE FROM cards WHERE call_number = 'A1-042'
│    (if quantity was > 1, would UPDATE quantity = quantity - 1)
├─ BROK logs sale:
│    INSERT INTO sales_log (call_number, card_name, price, quantity, date_sold)
│    VALUES ('A1-042', 'Lightning Bolt', 245.00, 1, datetime('now'))
└─ BROK returns: {success: true, removed: 1, total_cards: 26850}

Step 5: DESKTOP → MARKETPLACE ORDER UPDATE (HTTPS)
├─ Desktop sends: PUT https://nexus-marketplace-api.kcaracozza.workers.dev/v1/orders/order-uuid-888
├─ Request body: {
│    status: "shipped",
│    tracking_number: "1Z999AA10123456784"
│  }
└─ Worker receives order update

Step 6: CLOUDFLARE ORDER UPDATE
├─ Worker executes:
│    UPDATE orders
│    SET status = 'shipped',
│        tracking_number = '1Z999AA10123456784',
│        shipped_at = datetime('now'),
│        updated_at = datetime('now')
│    WHERE id = 'order-uuid-888'
└─ Worker returns: {success: true, status: "shipped"}

Step 7: CLOUDFLARE → CUSTOMER EMAIL NOTIFICATION
├─ ⚠️ NOT IMPLEMENTED YET
├─ Future: Worker → SendGrid/Mailgun
├─ Email template:
│    Subject: "Your NEXUS order has shipped!"
│    Body:
│      Order #12345 has been shipped!
│      Tracking: 1Z999AA10123456784
│      Expected delivery: Feb 18-20
└─ Customer receives email

Step 8: DESKTOP UI UPDATE
├─ Order moves from "Pending" to "Shipped" section
├─ Stats update:
│    Pending: 1 → 0
│    Shipped: 0 → 1
├─ Inventory count: 26,851 → 26,850
└─ Total value: $4,110.03 → $3,865.03
```

### OUTPUT: Order shipped, inventory decremented, customer notified

**API Calls Made:**
- Desktop → BROK: `DELETE /api/library/remove`
- Desktop → Marketplace: `PUT /v1/orders/:id`
- Worker → SendGrid: `POST /v3/mail/send` (future)

**Data Flow:**
`Desktop → BROK Inventory Update → Marketplace Order Update → Email Notification`

**Time:** ~1-2 seconds

---

## 6. INVENTORY SYNC FLOW

### INPUT: Scheduled task (every 5 minutes) or manual "Sync Now" button

### PROCESS:

```
Step 1: DESKTOP SCHEDULER TRIGGER
├─ Timer fires every 5 minutes
├─ Or user clicks "Sync Inventory" button
└─ Desktop calls: inventory_sync.sync_to_marketplace()

Step 2: DESKTOP → BROK FULL INVENTORY FETCH (HTTP)
├─ Desktop sends: GET http://192.168.1.174:5000/api/library/all?limit=10000
└─ BROK receives inventory fetch request

Step 3: BROK DATABASE QUERY
├─ BROK executes:
│    SELECT * FROM cards ORDER BY date_added DESC LIMIT 10000
├─ BROK fetches all 26,850 cards
└─ BROK returns: {
     cards: [
       {call_number: "A1-042", card_name: "Lightning Bolt", set_code: "LEA", quantity: 1, price: 245.00, ...},
       {call_number: "A1-043", card_name: "Black Lotus", set_code: "LEA", quantity: 1, price: 15000.00, ...},
       ... (26,850 total)
     ],
     total: 26850
   }

Step 4: DESKTOP DIFF CALCULATION
├─ Desktop compares local listings to BROK inventory
├─ Desktop identifies changes:
│    Added: 5 new cards (not yet listed)
│    Removed: 1 card (sold, need to delist)
│    Updated: 3 cards (price changed)
└─ Desktop prepares sync batch

Step 5: DESKTOP → MARKETPLACE BULK UPDATE (HTTPS)
├─ Desktop sends: POST /v1/inventory/bulk-sync
├─ Request body: {
│    seller_id: "user-uuid-123",
│    add: [
│      {card_name: "Black Lotus", set_code: "LEA", price: 14500.00, quantity: 1, condition: "LP"},
│      ... (4 more)
│    ],
│    remove: [
│      {listing_id: "listing-uuid-456"} (Lightning Bolt already sold)
│    ],
│    update: [
│      {listing_id: "listing-uuid-789", price: 150.00} (price changed)
│    ]
│  }
└─ Worker receives bulk sync request

Step 6: CLOUDFLARE BULK PROCESSING
├─ Worker processes additions:
│    For each add:
│      - Create card if doesn't exist
│      - Create listing
│      - INSERT INTO listings (...)
├─ Worker processes removals:
│    For each remove:
│      - UPDATE listings SET status = 'delisted' WHERE id = ?
├─ Worker processes updates:
│    For each update:
│      - UPDATE listings SET price = ?, updated_at = datetime('now') WHERE id = ?
└─ Worker returns: {
     added: 5,
     removed: 1,
     updated: 3,
     success: true
   }

Step 7: DESKTOP UI UPDATE
├─ Desktop shows sync status:
│    "Sync complete! +5 new listings, -1 removed, 3 updated"
├─ Stats update:
│    Listed Items: 50 → 54
│    Total Sales: recalculated
└─ Last sync time: "Just now"
```

### OUTPUT: Marketplace inventory matches BROK inventory

**API Calls Made:**
- Desktop → BROK: `GET /api/library/all`
- Desktop → Marketplace: `POST /v1/inventory/bulk-sync`

**Data Flow:**
`BROK Inventory → Desktop → Diff Calculation → Marketplace Bulk Update`

**Time:** ~5-15 seconds (depending on changes)

---

## 7. PRICE UPDATE FLOW

### INPUT: ZULTAN price scraper runs (daily) or manual price update request

### PROCESS:

```
Step 1: ZULTAN SCHEDULED SCRAPER
├─ Cron job: 0 2 * * * (2 AM daily)
├─ ZULTAN runs: ~/training/price_scraper.py
└─ Scraper fetches latest prices

Step 2: ZULTAN → SCRYFALL API (HTTPS)
├─ Scraper sends: GET https://api.scryfall.com/bulk-data/default-cards
├─ Scryfall returns: 50MB+ JSON file with all MTG cards + prices
├─ Scraper downloads: /tmp/scryfall_bulk.json
└─ Scraper parses JSON (521K cards)

Step 3: ZULTAN DATABASE UPDATE
├─ For each card in bulk data:
│    UPDATE card_lookup
│    SET price_usd = ?, price_usd_foil = ?, price_updated_at = datetime('now')
│    WHERE id = ?
├─ ZULTAN updates 521,124 cards
└─ ZULTAN logs: "Price update complete: 521,124 cards updated"

Step 4: DESKTOP PRICE REFRESH (Auto or Manual)
├─ Desktop sends: GET http://192.168.1.174:5000/api/library/all
├─ BROK returns inventory with OLD prices
└─ Desktop sends batch price lookup:
     POST http://192.168.1.152:8000/api/batch-price-lookup
     Body: {
       cards: [
         {id: "abc123", name: "Lightning Bolt", set: "LEA"},
         ... (26,850 cards)
       ]
     }

Step 5: ZULTAN BATCH PRICE LOOKUP
├─ For each card:
│    SELECT price_usd, price_usd_foil
│    FROM card_lookup
│    WHERE name = ? AND set_code = ?
├─ ZULTAN returns: {
│    prices: [
│      {id: "abc123", price: 250.00, price_foil: 300.00, last_updated: "2026-02-15"},
│      ... (26,850 prices)
│    ]
│  }
└─ Desktop receives updated prices

Step 6: DESKTOP → BROK PRICE UPDATE (HTTP)
├─ Desktop sends: POST http://192.168.1.174:5000/api/library/batch-update-prices
├─ Request body: {
│    updates: [
│      {call_number: "A1-042", price: 250.00},
│      {call_number: "A1-043", price: 14500.00},
│      ... (26,850 updates)
│    ]
│  }
└─ BROK receives price update batch

Step 7: BROK BATCH UPDATE
├─ BROK opens transaction
├─ For each update:
│    UPDATE cards SET price = ?, price_updated_at = datetime('now')
│    WHERE call_number = ?
├─ BROK commits transaction
└─ BROK returns: {updated: 26850, success: true}

Step 8: DESKTOP UI REFRESH
├─ Desktop fetches updated inventory
├─ Desktop recalculates total value:
│    Old: $3,860.03
│    New: $3,945.21 (+$85.18)
├─ Desktop shows notification: "Prices updated! +$85.18"
└─ Collection tab refreshes with new prices
```

### OUTPUT: All prices updated across BROK inventory and Desktop UI

**API Calls Made:**
- ZULTAN → Scryfall: `GET /bulk-data/default-cards`
- Desktop → BROK: `GET /api/library/all`
- Desktop → ZULTAN: `POST /api/batch-price-lookup`
- Desktop → BROK: `POST /api/library/batch-update-prices`

**Data Flow:**
`Scryfall → ZULTAN → Desktop → BROK → Desktop UI`

**Time:** ~30-60 seconds for full inventory update

---

## 8. DECK BUILDING FLOW

### INPUT: User creates new deck, clicks "AI Suggest Cards"

### PROCESS:

```
Step 1: USER ACTION
├─ User opens Deck Builder tab
├─ User creates new deck: "Mono Red Burn"
├─ User selects format: "Modern"
├─ User adds initial cards:
│    4x Lightning Bolt
│    4x Lava Spike
└─ User clicks "AI Suggest Cards"

Step 2: DESKTOP AI ANALYSIS
├─ Desktop analyzes current deck:
│    theme = "burn/aggro"
│    colors = ["R"]
│    avg_cmc = 1.0
│    missing_slots = 52
└─ Desktop prepares AI request

Step 3: DESKTOP → ZULTAN AI SUGGESTIONS (HTTP)
├─ Desktop sends: POST http://192.168.1.152:8000/api/deck/suggest
├─ Request body: {
│    current_deck: [
│      {name: "Lightning Bolt", quantity: 4},
│      {name: "Lava Spike", quantity: 4}
│    ],
│    format: "modern",
│    budget: null,
│    theme: "burn"
│  }
└─ ZULTAN receives suggestion request

Step 4: ZULTAN AI PROCESSING
├─ ZULTAN loads deck AI model
├─ ZULTAN queries synergy database:
│    SELECT card_name, synergy_score
│    FROM card_synergies
│    WHERE archetype = 'burn' AND format = 'modern'
│    ORDER BY synergy_score DESC
├─ ZULTAN filters by budget and color identity
└─ ZULTAN returns: {
     suggestions: [
       {name: "Eidolon of the Great Revel", quantity: 4, reason: "Punishes opponents, burn synergy"},
       {name: "Monastery Swiftspear", quantity: 4, reason: "Prowess aggro threat"},
       {name: "Skullcrack", quantity: 3, reason: "Prevents lifegain"},
       ... (10 more suggestions)
     ]
   }

Step 5: DESKTOP INVENTORY CHECK
├─ For each suggested card:
│    Desktop sends: GET http://192.168.1.174:5000/api/library/search?q=Eidolon+of+the+Great+Revel
│    BROK returns: {
│      results: [
│        {call_number: "B3-017", quantity: 2, price: 25.00, condition: "NM"}
│      ],
│      owned: 2,
│      needed: 4
│    }
├─ Desktop marks cards:
│    ✅ Lightning Bolt (owned: 4, needed: 4)
│    ✅ Lava Spike (owned: 4, needed: 4)
│    ⚠️ Eidolon (owned: 2, needed: 4) - BUY 2 MORE
│    ❌ Monastery Swiftspear (owned: 0, needed: 4) - BUY 4
└─ Desktop displays suggestions with ownership status

Step 6: USER ADDS CARDS TO DECK
├─ User selects suggestions
├─ User clicks "Add to Deck"
├─ Desktop adds cards to deck list
└─ Desktop creates buylist for missing cards

Step 7: DESKTOP BUYLIST GENERATION
├─ Desktop identifies missing cards:
│    Need to buy:
│      2x Eidolon of the Great Revel ($25.00 each = $50.00)
│      4x Monastery Swiftspear ($8.00 each = $32.00)
│      ... (other missing cards)
│    Total cost: $185.00
├─ Desktop shows buylist:
│    "Missing 15 cards - Total: $185.00"
│    Option 1: "Search Marketplace"
│    Option 2: "Export to TCGPlayer"
└─ User clicks "Search Marketplace"

Step 8: DESKTOP → MARKETPLACE SEARCH (HTTPS)
├─ Desktop sends: POST /v1/listings/batch-search
├─ Request body: {
│    cards: [
│      {name: "Eidolon of the Great Revel", quantity: 2},
│      {name: "Monastery Swiftspear", quantity: 4}
│    ],
│    sort: "price_asc"
│  }
└─ Worker returns listings from multiple sellers

Step 9: DESKTOP SHOWS PURCHASE OPTIONS
├─ Desktop displays marketplace listings:
│    Eidolon of the Great Revel:
│      Seller A: $24.00 (NM) x4 available
│      Seller B: $25.50 (LP) x2 available
│    Monastery Swiftspear:
│      Seller C: $7.50 (NM) x10 available
├─ User adds to cart
└─ Proceeds to checkout (see Purchase Flow above)
```

### OUTPUT: Complete deck built with AI suggestions, missing cards identified and purchaseable

**API Calls Made:**
- Desktop → ZULTAN: `POST /api/deck/suggest`
- Desktop → BROK: `GET /api/library/search` (for each card)
- Desktop → Marketplace: `POST /v1/listings/batch-search`

**Data Flow:**
`User Deck → AI Analysis → Synergy Database → Suggestions → Inventory Check → Buylist → Marketplace Search`

**Time:** ~3-5 seconds

---

## 📊 SUMMARY: ALL API ENDPOINTS

### BROK (192.168.1.174:5000)
```
GET  /api/health
GET  /api/library/stats
GET  /api/library/all
GET  /api/library/search?q=<name>
POST /api/library/add
DELETE /api/library/remove?call_number=<id>
POST /api/library/batch-update-prices
```

### SNARF (192.168.1.172:5001/5003)
```
POST /api/scan/start
POST /api/hardware/led/on
POST /api/hardware/led/off
POST /api/hardware/arm/move
GET  /api/hardware/status
POST /api/acr/pipeline (port 5003)
```

### ZULTAN (192.168.1.152:8000)
```
GET  /api/health
GET  /api/mtg/search?q=<name>
GET  /api/pokemon/search?q=<name>
GET  /api/sports/search?q=<name>&sport=<sport>
GET  /api/stats
POST /api/batch-price-lookup
POST /api/deck/suggest
```

### MARKETPLACE (Cloudflare)
```
GET  /v1/listings
POST /v1/listings
PUT  /v1/listings/:id
DELETE /v1/listings/:id

GET  /v1/cart/:user_id
POST /v1/cart
DELETE /v1/cart/item/:id

POST /v1/orders
GET  /v1/orders
PUT  /v1/orders/:id

POST /v1/inventory/bulk-sync
POST /v1/listings/batch-search
POST /v1/users
GET  /v1/sellers
POST /v1/reviews
POST /v1/license/validate
```

---

## ⚡ CRITICAL DATA PATHS

### Scan → Inventory
`Card → CZUR → SNARF → BROK Coral TPU → FAISS → ZULTAN Metadata → BROK SQLite → Desktop UI`

### List → Marketplace
`Desktop Local → Marketplace API → D1 Database → Live Listing`

### Purchase → Fulfillment
`Customer Website → D1 Order → Desktop Notification → BROK Inventory Decrement → Shipment`

### Price Update
`Scryfall → ZULTAN Catalog → Desktop → BROK Inventory → Desktop UI`

### Deck Build
`User Input → ZULTAN AI → Synergy DB → BROK Inventory Check → Marketplace Search → Purchase`

---

**Every process, every API call, every data transformation - complete.** 🎯
