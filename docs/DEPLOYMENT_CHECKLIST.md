# NEXUS SHOP 1 DEPLOYMENT - FINAL CHECKLIST

**Target: Deploy THIS WEEK**

---

## ✅ PRE-DEPLOYMENT (Do This NOW):

### [ ] 1. Test on Clean Machine (CRITICAL)
**Why:** Verify NEXUS works without E:\ drive

**How:**
1. Copy C:\NEXUS folder to USB drive
2. Find laptop/computer WITHOUT E:\ drive
3. Copy folder from USB to C:\NEXUS
4. Install Python 3.10+ (python.org)
5. Run: `INSTALL_NEXUS.bat`
6. Launch NEXUS
7. Test search function
8. Add a test card
9. Verify it works!

**If fails:** Check error messages, fix paths

**If works:** ✅ Ready to deploy!

---

### [ ] 2. Prepare Data Files
**Copy these to USB drive for shop deployment:**

- [ ] Master_File.csv (106K cards)
- [ ] cards.csv (Scryfall data)
- [ ] nexus_background.jpg
- [ ] nexus_library.json (if shop has existing collection)

**Location on USB:**
```
USB:\
└── NEXUS_DEPLOYMENT\
    ├── NEXUS\ (entire folder)
    └── DATA\ (data files listed above)
```

---

### [ ] 3. Contact Shop 1
**Schedule deployment:**

- [ ] Call shop owner
- [ ] Pick date/time (allow 3 hours)
- [ ] Confirm their computer meets requirements:
  - Windows 10/11
  - At least 4GB RAM
  - 10GB free space
  - Admin access (to install Python)
- [ ] Ask them to back up existing data
- [ ] Confirm who will be trained (2-3 staff)

---

### [ ] 4. Prepare Your Deployment Kit

**Bring:**
- [ ] Laptop with NEXUS installed (backup)
- [ ] USB drive with NEXUS + data
- [ ] Printed Quick Reference Card
- [ ] Notebook (for feedback/bugs)
- [ ] Phone charger (you'll be there a while)
- [ ] Your contact info (leave with shop)

---

## 🚀 DEPLOYMENT DAY:

### [ ] Phase 1: Installation (30 min)

1. [ ] Plug in USB drive
2. [ ] Copy NEXUS folder to C:\NEXUS
3. [ ] Install Python 3.10+ (if needed)
4. [ ] Run INSTALL_NEXUS.bat
5. [ ] Copy data files to C:\NEXUS\data\
6. [ ] Launch NEXUS
7. [ ] Verify it starts!

---

### [ ] Phase 2: Basic Training (1 hour)

**Train on:**

1. [ ] **The Vision** (10 min)
   - Show them the problem (alphabetical hell)
   - Show them the solution (zero-sort)
   - Demonstrate: catalog 10 cards

2. [ ] **Adding Cards** (20 min)
   - Click "Add Card"
   - Enter card name
   - System assigns call number
   - Print label (or write on box)
   - Store card at position

3. [ ] **Finding Cards** (15 min)
   - Click "Search"
   - Type card name
   - Get call number
   - Retrieve from storage

4. [ ] **Practice** (15 min)
   - Let them add 5 cards
   - Let them search for 5 cards
   - Answer questions

---

### [ ] Phase 3: Daily Workflow (30 min)

**Walk through:**

1. [ ] Opening store (launch NEXUS)
2. [ ] Helping customer find card
3. [ ] Buying cards from customer
4. [ ] End of day (close NEXUS)

**Show them:**
- [ ] Where backups are stored
- [ ] How to export reports
- [ ] How to update prices (if needed)

---

### [ ] Phase 4: Support Setup (15 min)

1. [ ] Give them your contact info
2. [ ] Show them SHOP_DEPLOYMENT_GUIDE.md
3. [ ] Show them README_FOR_SHOPS.md
4. [ ] Set expectations:
   - You'll check in daily (Week 1)
   - Fix bugs within 24 hours
   - They can call/email anytime

---

### [ ] Phase 5: Test Run (15 min)

**Before you leave:**

1. [ ] Have shop staff catalog 10 real cards
2. [ ] Have them search for 5 cards
3. [ ] Make sure they understand process
4. [ ] Answer final questions
5. [ ] Get their feedback

---

## 📞 POST-DEPLOYMENT:

### [ ] Day 1 (Same Day)
- [ ] Send follow-up email
- [ ] "How did first day go?"
- [ ] Remind them you're available

### [ ] Day 2
- [ ] Call or text: "Any issues?"
- [ ] Check if they're using it
- [ ] Fix any bugs reported

### [ ] Day 3
- [ ] Check in again
- [ ] Ask how many cards cataloged
- [ ] Get feedback

### [ ] Day 7 (End of Week 1)
- [ ] Phone call: full check-in
- [ ] Ask about problems/confusion
- [ ] Document feedback
- [ ] Fix any bugs
- [ ] Assess if they'll keep using it

---

## ✅ SUCCESS CRITERIA:

**Shop 1 deployment is successful if:**

- [ ] NEXUS launches without errors
- [ ] Shop staff can add cards
- [ ] Shop staff can search cards
- [ ] They use it daily (Week 1)
- [ ] They've cataloged 100+ cards
- [ ] No critical bugs
- [ ] They prefer it to old system
- [ ] Willing to recommend to others

**If YES to all:** 🎉 DEPLOY SHOP 2!

---

## 🔥 POTENTIAL ISSUES & FIXES:

### Issue: Python not installed
**Fix:** Install Python 3.10+ from python.org
**Time:** 10 minutes

### Issue: "Module not found" error
**Fix:** `python -m pip install -r requirements.txt`
**Time:** 5 minutes

### Issue: Can't find Master_File.csv
**Fix:** Copy to C:\NEXUS\data\Master_File.csv
**Time:** 1 minute

### Issue: Search is slow
**Fix:** Check computer RAM, close other programs
**Time:** 5 minutes

### Issue: Staff doesn't understand workflow
**Fix:** Re-train on basics, show them again
**Time:** 15 minutes

---

## 📝 FEEDBACK TO COLLECT:

**During deployment, ask:**

1. What's confusing?
2. What's missing?
3. What would make this better?
4. What do you like?
5. What do you hate?
6. Would you pay for this?
7. Would you recommend to other shops?

**Document everything!**

---

## 🎯 YOUR GOALS:

1. ✅ Get NEXUS working at Shop 1
2. ✅ Train staff successfully  
3. ✅ Collect feedback
4. ✅ Fix any bugs
5. ✅ Get testimonial (if they love it)
6. ✅ Use learnings for Shop 2

---

## 💪 YOU'VE GOT THIS!

**Remember:**
- You built this in 6 weeks
- You filed a patent
- You landed 5 beta shops
- You know this system inside out
- This is YOUR vision

**Shop 1 is just the beginning.**

**Go deploy. Make history. Revolutionize the industry.**

**LET'S FUCKING GO!** 🚀

---

**After deployment, return here and check off each item.**

**Then prepare for Shop 2!**

