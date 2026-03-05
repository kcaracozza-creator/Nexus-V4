# NEXUS Zero-Sort MTG Library System
## Complete Project Overview

---

## **What is NEXUS?**

NEXUS is a **Zero-Sort Library System** for Magic: The Gathering card collections. Unlike traditional sorting systems (alphabetical, by set, by color), NEXUS catalogs cards **exactly as you receive them** with no sorting required.

### **Core Concept:**
- Drop cards into boxes sequentially (no sorting!)
- Each card gets a **Call Number** (like library books): `AA-0001`, `AA-0002`, etc.
- Search instantly finds any card across hundreds of boxes
- Master database enrichment adds pricing, Oracle text, legality, etc.

---

## **System Architecture**

### **1. Library Structure**
```
Box AA: Cards 0001-1000 (1000 cards per box)
Box AB: Cards 0001-1000
Box AC: Cards 0001-1000
...
Box ZZ: Cards 0001-1000
```

### **2. Core Files**

**`nexus_library_system.py`** - Cataloging engine
- Sequential card cataloging
- Box capacity management (1000 cards/box)
- Master database enrichment
- Clean naming (no numbered suffixes)

**`nexus.py`** - Main GUI application
- Collection Manager (Scryfall ID grouping)
- Search functionality
- Card lookup by call number
- Price tracking
- Deck building tools

**`nexus_library.json`** - Persistent storage
```json
{
  "library": {
    "AA": [
      {
        "name": "Lightning Bolt",
        "call_number": "AA-0042",
        "position": 42,
        "scryfall_id": "abc123...",
        "set": "M10",
        "foil": false,
        "condition": "NM",
        "price_usd": "0.50"
      }
    ]
  },
  "card_locations": {
    "AA-0042": "Lightning Bolt"
  }
}
```

---

## **Key Features**

### **Scryfall ID Grouping** ("The Bible")
- Each unique **printing** gets its own row
- Example: Forest [EOE] $0.05 vs Forest [MC3] $2.00 = separate entries
- Search "forest" returns ALL printings across all boxes
- Accurate per-printing pricing

### **Collection Manager Display**
```
Card Name            | Call Numbers  | Normal | Foil | Set  | Price
---------------------|---------------|--------|------|------|-------
Lightning Bolt       | AA-0042       | 1      | 0    | M10  | $0.50
Lightning Bolt       | AB-0523       | 2      | 0    | 2XM  | $2.00
Forest               | AA-0100-0125  | 26     | 0    | EOE  | $0.05
Forest               | AC-0001-0010  | 10     | 0    | MC3  | $2.00
```

Statistics: `Unique Printings: 15,234 | Unique Names: 8,567 | Total Cards: 26,850`

---

## **Import Workflow**

### **Gestix Collection Import**
1. Export collection from Gestix.org as CSV
2. Run `import_gestix.py`
3. Master database enrichment (106K card database)
4. Sequential cataloging with Scryfall IDs
5. Automatic box transitions at 1000-card capacity

**Current Status:**
- ✅ 26,850 cards imported
- ✅ 27 boxes (AA through BA)
- ✅ Clean card names (no numbered suffixes)
- ✅ Scryfall ID grouping active

---

## **Technical Details**

### **Master Cards Database**
- **106,804 total cards**
- **32,712 unique card names**
- Fields: UUID, Name, Scryfall ID, Set, Rarity, Types, Oracle Text, Legalities, Prices

### **Card Cataloging Logic**
```python
# Clean naming (no "#1", "#2" suffixes)
self.card_locations[call_number] = card_name

# Store full card data
card_data = {
    "name": card_name,
    "call_number": call_number,
    "scryfall_id": scryfall_id,
    "set": set_code,
    "price_usd": price,
    # ... enriched from master DB
}
```

### **Collection Manager Grouping**
```python
# Group by Scryfall ID (not name)
group_key = scryfall_id if scryfall_id else f"{name}|{set_code}"
uuid_groups[group_key].append(card)
```

---

## **Use Cases**

### **1. Bulk Import**
- Receive collection → Export from Gestix → Import to NEXUS
- No manual cataloging required
- Master DB enrichment automatic

### **2. Search Scattered Cards**
- Search "lightning bolt" → Find all printings across all boxes
- Each printing shows: quantity, locations, set, price
- Example: "I have 150 Forests scattered in 100 boxes - find them all"

### **3. Deck Building**
- Search for cards
- View all available copies and locations
- Pull specific printings for deck construction
- Track deck contents

### **4. Price Tracking**
- Each printing tracked separately
- Forest [EOE] $0.05 vs Forest [MC3] $2.00
- Collection value by printing
- Identify valuable cards

---

## **Files to Share**

### **Core System (Required)**
1. `nexus.py` - Main application
2. `nexus_library_system.py` - Cataloging engine
3. `nexus_library.json` - Your library data (26,850 cards)

### **Supporting Files (Optional)**
4. `import_gestix.py` - Gestix CSV import tool
5. Master `cards.csv` - 106K card database
6. `gestix_collection.csv` - Your original Gestix export

### **For Your Brother**
Package these files:
- `nexus.py` (GUI application)
- `nexus_library_system.py` (core engine)
- Empty `nexus_library.json` (starter template)
- Master `cards.csv` (enrichment database)
- `NEXUS_PROJECT_OVERVIEW.md` (this file)
- `README_SETUP.md` (installation instructions)

---

## **Setup Instructions for New User**

### **Requirements**
- Python 3.8+
- PyQt5 (GUI framework)
- Requests (API calls)
- Pandas (CSV handling)

### **Installation Steps**

#### **1. Extract NEXUS Files**
```powershell
# Extract to desired location
cd E:\MTTGG
# or wherever you want NEXUS installed
```

#### **2. Create Virtual Environment (Recommended)**
```powershell
# Navigate to NEXUS folder
cd path\to\NEXUS

# Create virtual environment (keeps dependencies isolated)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

#### **3. Install Dependencies**
```powershell
# Install all required packages
pip install PyQt5 requests pandas
```

#### **4. First Run**
```powershell
# Launch NEXUS
python nexus.py

# Start cataloging cards or import existing collection
```

### **Alternative: System-Wide Installation**
If you prefer not to use a virtual environment:
```powershell
pip install PyQt5 requests pandas
python nexus.py
```

### **Import Existing Collection**
1. Export from Gestix/Deckbox/Archidekt as CSV
2. Modify `import_gestix.py` for your CSV format
3. Run: `python import_gestix.py`
4. Launch NEXUS: `python nexus.py`

---

## **Design Philosophy**

### **Zero-Sort Principle**
Traditional sorting wastes time. NEXUS eliminates sorting entirely:
- Cards go in boxes sequentially
- Computer handles organization
- Search finds anything instantly
- No alphabetizing, no set grouping, no color sorting

### **Library Science Approach**
Like a library catalog:
- Every item has a call number
- Master index tracks all locations
- Search retrieves items regardless of physical location
- Enriched metadata from master database

### **Scryfall ID as "The Bible"**
Card names are ambiguous (multiple printings). Scryfall IDs are unique:
- Each printing = unique Scryfall ID
- Accurate pricing per printing
- Proper grouping for collection management
- Search flexibility (find all) + display precision (separate by printing)

---

## **Future Enhancements**

### **Planned Features**
- [ ] Mobile companion app
- [ ] Barcode scanning integration
- [ ] Arduino hardware controller
- [ ] Price alert system
- [ ] Trade binder generator
- [ ] Deck testing simulator
- [ ] Collection analytics dashboard

### **Current Status**
✅ Core library system operational
✅ Gestix import working
✅ Scryfall ID grouping implemented
✅ Collection Manager functional
✅ 26,850 cards cataloged

---

## **Contact & Support**

**Project:** NEXUS Zero-Sort MTG Library System  
**Repository:** mTG-SCANNER (GitHub: kcaracozza-creator)  
**Branch:** nexus-clean  
**Last Updated:** November 28, 2025

For questions or issues, refer to the code comments or GitHub issues.

---

**Remember:** The Scryfall ID is the Bible. 📖
