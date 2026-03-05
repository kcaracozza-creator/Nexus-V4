# NEXUS Physical Location Tracking System
## Technical Specification

---

## OVERVIEW

The Physical Location Tracking System assigns unique Box ID + Card Number coordinates to every scanned card, enabling instant retrieval from physical storage. This eliminates the #1 pain point for card shops: "I know I have it, but where is it?"

**Key Benefit:** Find any card in <10 seconds vs 5+ minutes of manual searching.

---

## ARCHITECTURE

### 1. Storage Organization Scheme

#### Box Naming Convention
- **Format:** `[SECTION]-[BOX_NUMBER]`
- **Examples:**
  - `A-1`: Section A, Box 1
  - `B-12`: Section B, Box 12
  - `VAULT-3`: High-value vault storage, Box 3

#### Card Numbering
- **Sequential numbering** within each box
- **Range:** 1 to 999 (standard box holds 500-800 cards)
- **Assignment:** Auto-incremented by scanning order

#### Complete Location Example
```
Card: Lightning Bolt
Location: Box B-A, Card #147
Meaning: Section B, Box A, 147th card in that box
```

---

## DATABASE SCHEMA

### Inventory Table
```sql
CREATE TABLE inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Card Information
    card_name TEXT NOT NULL,
    set_name TEXT,
    rarity TEXT,
    condition TEXT,
    foil BOOLEAN DEFAULT 0,
    language TEXT DEFAULT 'English',
    
    -- Financial Data
    cost_basis REAL,
    current_price REAL,
    last_price_update TEXT,
    
    -- Physical Location (KEY FEATURE)
    box_id TEXT NOT NULL,          -- e.g., "B-A", "VAULT-1"
    card_number INTEGER NOT NULL,  -- Sequential position in box
    shelf_location TEXT,           -- Optional: physical shelf/wall location
    
    -- Metadata
    scan_date TEXT,
    last_updated TEXT,
    days_in_inventory INTEGER DEFAULT 0,
    image_path TEXT,               -- Path to card scan image
    
    -- Index for fast lookup
    UNIQUE(box_id, card_number)
);

CREATE INDEX idx_card_name ON inventory(card_name);
CREATE INDEX idx_location ON inventory(box_id, card_number);
CREATE INDEX idx_set_name ON inventory(set_name);
```

### Box Metadata Table
```sql
CREATE TABLE boxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    box_id TEXT UNIQUE NOT NULL,
    description TEXT,              -- e.g., "Modern Red Cards"
    capacity INTEGER DEFAULT 800,
    current_count INTEGER DEFAULT 0,
    shelf_location TEXT,           -- Physical shelf/room location
    created_date TEXT,
    last_modified TEXT
);

CREATE INDEX idx_box_id ON boxes(box_id);
```

### Location Log (Audit Trail)
```sql
CREATE TABLE location_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER,
    old_box_id TEXT,
    old_card_number INTEGER,
    new_box_id TEXT,
    new_card_number INTEGER,
    moved_date TEXT,
    reason TEXT,                   -- e.g., "Reorganization", "Sold and restocked"
    FOREIGN KEY (card_id) REFERENCES inventory(id)
);
```

---

## SCANNER INTEGRATION WORKFLOW

### Step 1: Initialize Box
```python
def initialize_box(box_id: str, description: str = "", shelf_location: str = ""):
    """
    Create a new storage box before scanning cards into it
    """
    cursor.execute("""
        INSERT INTO boxes (box_id, description, shelf_location, created_date)
        VALUES (?, ?, ?, ?)
    """, (box_id, description, shelf_location, datetime.now().isoformat()))
    
    return box_id
```

### Step 2: Scan Card and Assign Location
```python
def scan_card_with_location(card_data: dict, box_id: str):
    """
    Scan card and automatically assign next available card number in box
    """
    # Get next card number for this box
    cursor.execute("""
        SELECT COALESCE(MAX(card_number), 0) + 1
        FROM inventory
        WHERE box_id = ?
    """, (box_id,))
    
    next_card_number = cursor.fetchone()[0]
    
    # Insert card with location
    cursor.execute("""
        INSERT INTO inventory 
        (card_name, set_name, rarity, condition, cost_basis, current_price,
         box_id, card_number, scan_date, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (card_data['name'], card_data['set'], card_data['rarity'], 
          card_data['condition'], card_data['cost'], card_data['price'],
          box_id, next_card_number, 
          datetime.now().isoformat(), datetime.now().isoformat()))
    
    # Update box count
    cursor.execute("""
        UPDATE boxes 
        SET current_count = current_count + 1,
            last_modified = ?
        WHERE box_id = ?
    """, (datetime.now().isoformat(), box_id))
    
    return {
        "box_id": box_id,
        "card_number": next_card_number,
        "location_string": f"Box {box_id}, Card #{next_card_number}"
    }
```

### Step 3: Print Location Labels
```python
def generate_box_label(box_id: str):
    """
    Generate printable label for physical box
    Includes QR code for quick scanning
    """
    cursor.execute("""
        SELECT box_id, description, current_count, capacity
        FROM boxes
        WHERE box_id = ?
    """, (box_id,))
    
    box_data = cursor.fetchone()
    
    label = f"""
    ╔════════════════════════════════╗
    ║   NEXUS INVENTORY BOX         ║
    ║                                ║
    ║   Box ID: {box_data[0]:<19} ║
    ║   {box_data[1]:<28} ║
    ║                                ║
    ║   Cards: {box_data[2]}/{box_data[3]:<17} ║
    ║                                ║
    ║   [QR CODE PLACEHOLDER]        ║
    ╚════════════════════════════════╝
    """
    
    return label
```

---

## USER INTERFACE FEATURES

### 1. Quick Search Interface
```python
def quick_find(search_term: str):
    """
    Customer asks for a card - show location instantly
    """
    cursor.execute("""
        SELECT card_name, box_id, card_number, condition, current_price
        FROM inventory
        WHERE card_name LIKE ?
        ORDER BY condition DESC
    """, (f"%{search_term}%",))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            "card_name": row[0],
            "location": f"Box {row[1]}, Card #{row[2]}",
            "condition": row[3],
            "price": row[4],
            "retrieval_time": "< 10 seconds"
        })
    
    return results
```

### 2. Box Contents View
```python
def view_box_contents(box_id: str):
    """
    Show all cards in a specific box (useful for reorganization)
    """
    cursor.execute("""
        SELECT card_number, card_name, set_name, condition, current_price
        FROM inventory
        WHERE box_id = ?
        ORDER BY card_number ASC
    """, (box_id,))
    
    return cursor.fetchall()
```

### 3. Move Card to New Location
```python
def relocate_card(card_id: int, new_box_id: str, reason: str = "Reorganization"):
    """
    Move card to different box (updates location, logs change)
    """
    # Get old location
    cursor.execute("SELECT box_id, card_number FROM inventory WHERE id = ?", (card_id,))
    old_location = cursor.fetchone()
    
    # Get next card number in new box
    cursor.execute("""
        SELECT COALESCE(MAX(card_number), 0) + 1
        FROM inventory WHERE box_id = ?
    """, (new_box_id,))
    new_card_number = cursor.fetchone()[0]
    
    # Update card location
    cursor.execute("""
        UPDATE inventory
        SET box_id = ?, card_number = ?, last_updated = ?
        WHERE id = ?
    """, (new_box_id, new_card_number, datetime.now().isoformat(), card_id))
    
    # Log the move
    cursor.execute("""
        INSERT INTO location_history 
        (card_id, old_box_id, old_card_number, new_box_id, new_card_number, moved_date, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (card_id, old_location[0], old_location[1], 
          new_box_id, new_card_number, datetime.now().isoformat(), reason))
    
    return f"Card moved from Box {old_location[0]}, Card #{old_location[1]} to Box {new_box_id}, Card #{new_card_number}"
```

---

## PHYSICAL ORGANIZATION BEST PRACTICES

### Recommended Storage Layout

#### Small Shop (< 10,000 cards)
```
Section A: Commons (Boxes A-1 through A-5)
Section B: Uncommons (Boxes B-1 through B-5)
Section C: Rares (Boxes C-1 through C-10)
Section D: Foils (Boxes D-1 through D-3)
VAULT: High-value cards >$50 (VAULT-1, VAULT-2)
```

#### Medium Shop (10,000 - 50,000 cards)
```
Organize by game:
  MTG-A-1 through MTG-A-50
  PKM-A-1 through PKM-A-30
  YGO-A-1 through YGO-A-20
  
Then by rarity/value within each game
```

#### Large Shop (50,000+ cards)
```
Organize by set + color/type:
  MTG-IKO-W-1 (Ikoria, White cards, Box 1)
  MTG-IKO-U-1 (Ikoria, Blue cards, Box 1)
  PKM-BS-H-1 (Base Set, Holos, Box 1)
```

### Box Capacity Guidelines
- **Standard 800-count box:** Good for commons/uncommons
- **500-count box:** Better for rares (easier to search physically)
- **300-count box:** High-value cards (reduce handling)
- **Binders:** Display cards (NEXUS can track binder page + slot)

---

## INTEGRATION WITH DECK BUILDER

### Smart Deck Building with Location Priority

When customer requests a deck, system:

1. **Find all required cards** in inventory
2. **Prioritize by age** (oldest first to move dead stock)
3. **Show locations** for efficient picking

```python
def build_deck_with_locations(decklist: List[str]):
    """
    Build deck from inventory, showing pick locations
    Prioritizes old inventory first
    """
    pick_list = []
    
    for card_name in decklist:
        cursor.execute("""
            SELECT card_name, box_id, card_number, condition, 
                   current_price, days_in_inventory
            FROM inventory
            WHERE card_name = ?
            ORDER BY days_in_inventory DESC, condition DESC
            LIMIT 1
        """, (card_name,))
        
        result = cursor.fetchone()
        
        if result:
            pick_list.append({
                "card_name": result[0],
                "location": f"Box {result[1]}, Card #{result[2]}",
                "condition": result[3],
                "price": result[4],
                "days_old": result[5],
                "priority": "HIGH" if result[5] > 90 else "NORMAL"
            })
    
    return pick_list
```

**Demo Output:**
```
Deck: Modern Burn
Pick List (oldest inventory first):

1. Lightning Bolt - Box B-A, Card #147 - NM - $3.00 [HIGH PRIORITY - 95 days old]
2. Monastery Swiftspear - Box C-5, Card #289 - NM - $0.50 [NORMAL]
3. Eidolon of the Great Revel - Box C-2, Card #441 - LP - $8.00 [HIGH PRIORITY - 120 days old]
...

Total: 60 cards
Old inventory moved: $45.00 (6 cards >90 days)
Total deck value: $150.00
```

---

## MOBILE APP INTEGRATION (Future)

### QR Code Scanning
- Print QR codes on box labels
- Employee scans box QR with phone
- App shows contents + highlights target card
- "You're looking for Card #147 in this box"

### Voice Search
- Employee: "Where's Lightning Bolt?"
- App: "Box B-A, Card 147. Shelf 3, left side."

---

## REPORTING FEATURES

### Location Utilization Report
```sql
SELECT 
    box_id,
    current_count,
    capacity,
    (current_count * 100.0 / capacity) as utilization_percent,
    SUM(current_price) as box_value
FROM boxes
JOIN inventory ON boxes.box_id = inventory.box_id
GROUP BY boxes.box_id
ORDER BY utilization_percent DESC;
```

**Shows:**
- Which boxes are full (need new boxes)
- Which boxes are empty (consolidate)
- Value density per box

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Core Functionality (Weekend Demo)
- [x] Database schema created
- [x] Box initialization function
- [x] Card scanning with auto-numbering
- [x] Quick search by card name
- [x] Basic location display

### Phase 2: Enhanced Features (Week 2)
- [ ] Box label printing with QR codes
- [ ] Card relocation tracking
- [ ] Box utilization reports
- [ ] Deck builder location integration

### Phase 3: Advanced Features (Month 2)
- [ ] Mobile app for box scanning
- [ ] Voice search integration
- [ ] Barcode scanner support
- [ ] Multi-location support (multiple stores)

---

## CUSTOMER VALUE PROPOSITION

### Time Savings Math

**Without NEXUS:**
- Customer asks for Lightning Bolt
- Search 5 boxes manually: 5-10 minutes
- 20 searches/day = 2+ hours wasted

**With NEXUS:**
- Search: "Lightning Bolt"
- Result: "Box B-A, Card #147"
- Walk to box, pull card: 30 seconds
- 20 searches/day = 10 minutes total

**ROI: 110 minutes saved per day = $27.50/day @ $15/hr labor = $825/month**

**System pays for itself 8x over** at $99/month pricing.

---

## COMPETITIVE DIFFERENTIATION

| Feature | NEXUS | Spreadsheets | Binders | Memory |
|---------|-------|--------------|---------|--------|
| **Find card speed** | <10 sec | 1-5 min | 5-10 min | 5-15 min |
| **Physical location** | ✅ Box + Card # | ❌ None | ✅ Page # | ❌ "I think..." |
| **Auto-assignment** | ✅ Yes | ❌ Manual | ❌ Manual | ❌ N/A |
| **Reorganization** | ✅ Logged | ❌ Re-enter | ❌ Lose track | ❌ Forget |
| **Scale** | Unlimited | ❌ Breaks >1K | ❌ Limited | ❌ Impossible |

**Nobody else solves the physical tracking problem at scale.**

---

## DEMO SCRIPT FOR WEEKEND

1. **Setup:** Show 3 physical boxes labeled B-A, B-B, B-C
2. **Scan:** Feed 20 cards through scanner
3. **System:** Auto-assigns locations (B-A #1, B-A #2, etc.)
4. **Search:** Customer asks for "Tarmogoyf"
5. **Result:** "Box B-B, Card #14" (instant)
6. **Retrieve:** Walk to box, pull card #14 - it's there!
7. **Wow Factor:** "That took 8 seconds. Without this, I'd spend 5 minutes searching."

---

## CONCLUSION

The Physical Location Tracking System turns card shops from chaotic piles into organized retail operations. It's the difference between "I think I have that somewhere" and "Box B-A, Card #147 - I'll grab it now."

**This feature alone justifies the $99/month price.**
