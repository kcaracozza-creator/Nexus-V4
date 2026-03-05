# 🎴 NEXUS - Zero-Sort Card Library System

**Stop sorting alphabetically. Start cataloging sequentially.**

---

## What is NEXUS?

NEXUS is a **Zero-Sort Library System** for game shops that sell Magic: The Gathering cards (and other TCGs).

**The Problem:** Alphabetical sorting takes HOURS and is a nightmare to maintain.

**The Solution:** Catalog cards in ANY order. Let the computer do the searching.

---

## How It Works:

### Traditional Method (Alphabetical):
1. Sort cards A-Z ❌ (takes hours)
2. File cards alphabetically ❌ (tedious)
3. When card arrives: find correct spot ❌ (time-consuming)
4. Cards get misfiled ❌ (frustrating)

### NEXUS Method (Zero-Sort):
1. Scan cards in ANY order ✅ (no sorting needed!)
2. System assigns: AA-0001, AA-0002, AA-0003... ✅
3. Put card in box at that position ✅ (sequential)
4. Computer remembers everything ✅ (instant search)

**Save hours per week. Never mis-file cards again.**

---

## Quick Start:

### Step 1: Install (5 minutes)
1. Run `INSTALL_NEXUS.bat`
2. Follow on-screen instructions
3. Done!

### Step 2: Copy Data Files
1. Copy to `C:\NEXUS\data\`:
   - Master_File.csv
   - cards.csv
2. Copy to `C:\NEXUS\assets\`:
   - nexus_background.jpg

### Step 3: Launch NEXUS
1. Double-click desktop shortcut
2. NEXUS opens!

---

## Basic Usage:

### Adding Cards (Cataloging):
1. Click "Add Card"
2. Type card name: "Lightning Bolt"
3. NEXUS assigns: **AA-0234**
4. Print label, stick on storage box
5. Put card in Box AA, position 234
6. Done! Computer remembers.

### Finding Cards (Search):
1. Click "Search"
2. Type card name
3. Results show: **AA-0234**
4. Go to Box AA, position 234
5. Grab the card!

### That's It!
No sorting. No filing. Just scan and store.

---

## Features:

✅ **Zero-Sort Cataloging** - No alphabetical sorting needed  
✅ **Lightning-Fast Search** - Find any card in <1 second  
✅ **Sequential Box System** - AA, AB, AC... (1000 cards per box)  
✅ **Call Number Tracking** - Every card has a location  
✅ **Collection Management** - Track inventory easily  
✅ **Price Tracking** - Update prices from TCGPlayer/Scryfall  
✅ **Customer Tracking** - Know who bought what  
✅ **Sales Analytics** - See what's selling  
✅ **Inventory Reports** - Export to Excel  

---

## System Requirements:

- **Windows 10/11**
- **Python 3.10+** (free from python.org)
- **4GB RAM minimum**
- **10GB free disk space**
- **Internet connection** (for price updates)

---

## The Call Number System:

### Box IDs: AA, AB, AC... ZZ
- Each box holds 1000 cards
- 676 boxes total (AA-ZZ = 676,000 cards!)

### Positions: 0001-1000
- Sequential numbering
- First card: 0001
- Last card: 1000

### Call Numbers:
- **AA-0001** = Box AA, Position 1
- **AA-0234** = Box AA, Position 234
- **AB-0567** = Box AB, Position 567
- **ZZ-1000** = Box ZZ, Position 1000

**The computer tracks everything. You just need the boxes.**

---

## Daily Workflow:

### Opening:
1. Launch NEXUS
2. Ready to help customers

### Customer Asks for Card:
1. Search card name
2. Get call number
3. Retrieve from storage
4. Sell or hold

### Buying Collection:
1. Click "Add Card" for each new card
2. NEXUS assigns sequential numbers
3. Store cards in boxes
4. Done!

### Closing:
1. NEXUS auto-saves
2. Close program
3. That's it!

---

## Support:

**Need Help?**
- Check: `SHOP_DEPLOYMENT_GUIDE.md`
- Email: [your support email]
- Phone: [your support number]
- Response time: <24 hours

**Found a Bug?**
- Report immediately
- We fix critical bugs within 4 hours
- Updates pushed automatically

---

## Current Status: BETA

You're a beta tester! Thank you for helping us perfect NEXUS.

**What this means:**
- Some bugs may exist (we fix them fast!)
- Features being added regularly
- Your feedback shapes the product
- Discounted pricing for early adopters

**Your role:**
- Use NEXUS daily
- Report any issues
- Suggest improvements
- Help us make it better

---

## Pricing (Beta):

### Beta Pricing (Limited Time):
- **$49/month** for first 6 months
- Then **$99/month** regular price
- Unlimited cards
- All features included
- Priority support
- Locked-in rate forever (early adopter special)

### What You Get:
- All updates (free)
- Bug fixes (priority)
- New features (as released)
- Email/phone support
- Training materials
- Community access

**No long-term contract. Cancel anytime.**

---

## FAQ:

**Q: What if I already have cards cataloged alphabetically?**  
A: Keep your current system. Add NEW cards to NEXUS. Gradually migrate when you have time.

**Q: Can I use this for Pokemon/Yu-Gi-Oh?**  
A: Not yet, but coming soon! Magic first, other games later.

**Q: What if my computer crashes?**  
A: NEXUS auto-backs up to `C:\NEXUS\backups\`. Your data is safe.

**Q: Do I need special hardware?**  
A: No! Works with any Windows computer. Scanner hardware is optional.

**Q: How long does cataloging take?**  
A: ~5 seconds per card (search name, click add, print label)

**Q: What if I forget a call number?**  
A: Just search the card name. NEXUS tells you the location.

---

## File Structure:

```
C:\NEXUS\
├── nexus.py (main application)
├── nexus_library_system.py (database engine)
├── requirements.txt (dependencies)
│
├── data/
│   ├── Master_File.csv (106,804 card database)
│   ├── cards.csv (Scryfall data)
│   ├── nexus_library.json (YOUR collection data)
│   └── inventory/ (reports, exports)
│
├── assets/
│   ├── nexus_background.jpg (UI background)
│   └── card_images/ (card images)
│
├── backups/
│   └── (automatic backups)
│
└── config/
    └── mttgg_config.json (settings)
```

---

## Getting Started Checklist:

- [ ] Install Python 3.10+
- [ ] Run INSTALL_NEXUS.bat
- [ ] Copy data files to C:\NEXUS\data\
- [ ] Launch NEXUS
- [ ] Test search function
- [ ] Add a test card
- [ ] Print a test label
- [ ] Read SHOP_DEPLOYMENT_GUIDE.md
- [ ] Start cataloging!

---

## Welcome to the Zero-Sort Revolution! 🚀

**Questions? Issues? Feedback?**

We're here to help. Let's make card management effortless.

**Your success is our success.**

---

Built with ❤️ for game shops everywhere.

**NEXUS - Because life's too short to sort alphabetically.**

