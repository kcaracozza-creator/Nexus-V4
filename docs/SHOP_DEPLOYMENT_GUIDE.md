# NEXUS - Shop Deployment Guide

## 🚀 QUICK START FOR SHOP 1

**Time to Deploy: 30 minutes**

---

## What Shop 1 Gets:

✅ **Zero-Sort Card Library System**
- Catalog cards in ANY order (no alphabetical sorting needed)
- Sequential cataloging (AA-0001, AA-0002, etc.)
- Lightning-fast search (finds cards in <1 second)
- Track 100,000+ cards easily

✅ **Features Included:**
- Card cataloging & search
- Collection management
- Price tracking
- Inventory reports
- Customer tracking
- Sales analytics

---

## PRE-DEPLOYMENT CHECKLIST:

### What You Need:

1. **Shop's Computer:**
   - Windows 10 or 11
   - Python 3.10+ installed
   - At least 4GB RAM
   - 10GB free disk space

2. **Data Files (from your E:\MTTGG):**
   - [ ] Master_File.csv (106,804 card database)
   - [ ] cards.csv (Scryfall database)
   - [ ] nexus_background.jpg (UI background)
   - [ ] nexus_library.json (if they have existing collection)

3. **USB Drive:**
   - Copy entire NEXUS folder to USB
   - Bring to shop

---

## DEPLOYMENT STEPS:

### Step 1: Copy NEXUS to Shop Computer (5 min)

1. Plug in USB drive
2. Copy entire `NEXUS` folder to: `C:\NEXUS\`
3. Eject USB drive

### Step 2: Install Python (if needed) (10 min)

1. Download Python 3.11 from: https://www.python.org/downloads/
2. Run installer
3. **CRITICAL:** Check "Add Python to PATH"
4. Click "Install Now"
5. Wait for completion

### Step 3: Install Dependencies (5 min)

1. Open Command Prompt (cmd)
2. Navigate to NEXUS:
   ```
   cd C:\NEXUS
   ```
3. Install requirements:
   ```
   python -m pip install -r requirements.txt
   ```
4. Wait for installation to complete

### Step 4: Launch NEXUS (2 min)

1. Double-click `nexus.py`
   
   **OR**
   
2. From Command Prompt:
   ```
   python nexus.py
   ```

3. NEXUS should launch!

### Step 5: Verify It Works (5 min)

Test these features:

- [ ] **Search:** Try searching for "Lightning Bolt"
- [ ] **Add Card:** Catalog a test card
- [ ] **Collection View:** Check that cards appear
- [ ] **Reports:** Generate inventory report

If all work: **✅ DEPLOYMENT SUCCESS!**

---

## TRAINING THE SHOP STAFF (2 hours)

### Session 1: The Vision (15 min)

Explain:
- NO MORE alphabetical sorting
- Scan cards in ANY order
- Computer does the searching
- Save hours per week

### Session 2: Basic Operations (45 min)

**Adding Cards:**
1. Click "Add Card" button
2. Enter card name
3. System assigns call number (AA-0001, AA-0002, etc.)
4. Print label, stick on storage box
5. Put card in box at that position

**Finding Cards:**
1. Click "Search" tab
2. Type card name
3. Results show call number (e.g., "AA-0234")
4. Go to Box AA, position 234
5. Grab the card

**Key Message:** "The computer remembers where everything is. You just scan and store."

### Session 3: Daily Workflow (30 min)

**Opening Store:**
1. Launch NEXUS
2. Ready to help customers

**Customer Wants a Card:**
1. Search card name
2. Find call number
3. Retrieve from storage
4. Sell/hold for customer

**Buying Cards from Customers:**
1. Click "Add Card" for each new card
2. Assign sequential call numbers
3. Store cards in boxes
4. Done!

**End of Day:**
1. NEXUS auto-saves
2. Close program
3. That's it!

### Session 4: Power Features (30 min)

- Price updates
- Inventory reports
- Customer tracking
- Sales analytics

---

## TROUBLESHOOTING:

### Problem: NEXUS won't start

**Solution:**
1. Check Python is installed: `python --version`
2. Should show: `Python 3.10.x` or higher
3. If not, reinstall Python (check "Add to PATH")

---

### Problem: "Module not found" error

**Solution:**
1. Open cmd as Administrator
2. Run: `cd C:\NEXUS`
3. Run: `python -m pip install -r requirements.txt --upgrade`

---

### Problem: Can't find cards.csv or Master_File.csv

**Solution:**
1. Make sure you copied data files to: `C:\NEXUS\data\`
2. Check files are named exactly: `Master_File.csv` and `cards.csv`

---

### Problem: Search is slow

**Solution:**
1. Close other programs
2. Restart NEXUS
3. If still slow, computer might need more RAM

---

## POST-DEPLOYMENT FOLLOW-UP:

### Day 1:
- ✅ Call shop, confirm NEXUS is working
- ✅ Answer any questions
- ✅ Check if staff is using it

### Day 3:
- ✅ Check in, see how many cards cataloged
- ✅ Get feedback on what's confusing
- ✅ Fix any bugs

### Week 1:
- ✅ On-site visit (if possible)
- ✅ Watch them use it
- ✅ Identify workflow improvements
- ✅ Document feedback for v2.0

### Week 2:
- ✅ Check if they're using it daily
- ✅ Get testimonial if they love it
- ✅ Ask for referrals to other shops

---

## SUCCESS METRICS:

**Shop 1 is successful if:**

- ✅ Using NEXUS daily
- ✅ Cataloged 500+ cards in first week
- ✅ Staff finds it easier than old system
- ✅ No major bugs
- ✅ Willing to recommend to other shops

**If YES to all:** Deploy Shop 2!

---

## EMERGENCY CONTACTS:

**If something breaks:**
- Email: [your email]
- Phone: [your number]
- Response time: <24 hours

**Critical bugs:**
- Response time: <4 hours
- Remote support available

---

## DATA BACKUP:

**NEXUS auto-saves to:**
- `C:\NEXUS\data\nexus_library.json`

**Backup strategy:**
1. Copy nexus_library.json weekly
2. Store on USB drive
3. Keep 3 backups (weekly rotation)

**To restore:**
1. Copy backed-up nexus_library.json
2. Replace current file
3. Restart NEXUS

---

## WHAT'S NEXT:

**After Shop 1 is live:**

1. ✅ Gather feedback
2. ✅ Fix any bugs
3. ✅ Document improvements
4. ✅ Deploy Shop 2 (with lessons learned)
5. ✅ Repeat until all 5 beta shops are live

**Then:**
- Polish based on beta feedback
- Create marketing materials
- Launch to public
- Scale to 50+ shops

---

## YOU'VE GOT THIS! 🚀

**Remember:**
- Shop 1 is a BETA tester
- Bugs are expected
- They knew this when they signed up
- Fast fixes beat perfect launches
- Get it working, then make it perfect

**Let's revolutionize how shops manage cards!**

---

**Questions before deployment?**
Review this checklist again. If all looks good, GO DEPLOY! 💪

