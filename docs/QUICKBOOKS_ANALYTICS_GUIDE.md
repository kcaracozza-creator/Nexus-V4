# QuickBooks Integration & Customer ROI Analytics Guide

## 🎯 OVERVIEW

Your MTTGG system now tracks **ROI per customer** and integrates with **QuickBooks** to link accounting data with your card library. This gives you complete business intelligence:

- **Who are your most profitable customers?**
- **Which suppliers give you the best ROI?**
- **What's your profit per card sold?**
- **How much have you made from each person?**

---

## 💼 QUICKBOOKS INTEGRATION

### Export Data from QuickBooks

#### Customer Sales Export:
1. Open QuickBooks
2. Go to **Reports** → **Sales** → **Sales by Customer Detail**
3. Set date range (e.g., Last Month, This Year, etc.)
4. Click **Export** → **Export to Excel/CSV**
5. Save as: `customer_sales_YYYYMMDD.csv`

Expected columns:
- Customer Name
- Date
- Invoice Number
- Item (card name or description)
- Quantity
- Price
- Amount
- Payment Status

#### Vendor Purchases Export:
1. Open QuickBooks
2. Go to **Reports** → **Expenses** → **Purchases by Vendor Detail**
3. Set date range
4. Click **Export** → **Export to Excel/CSV**
5. Save as: `vendor_purchases_YYYYMMDD.csv`

Expected columns:
- Vendor Name
- Date
- Bill Number / PO Number
- Item
- Quantity
- Cost
- Amount
- Payment Status

---

## 📊 IMPORT INTO MTTGG

### Step 1: Launch System
```bash
python mttgg_complete_system.py
```

### Step 2: Go to Analytics Tab
Click the **"📊 Analytics & ROI"** tab in the main window

### Step 3: Import QuickBooks Data

**Import Customer Sales:**
1. Click **"📥 Import Customer Sales CSV"**
2. Select your QuickBooks sales export file
3. System will match transactions to library cards
4. View import summary (rows processed, cards matched, revenue)

**Import Vendor Purchases:**
1. Click **"📥 Import Vendor Purchases CSV"**
2. Select your QuickBooks purchases export file
3. System matches acquisitions to library inventory
4. View import summary (rows processed, cards matched, cost)

**Note:** The system automatically tries to match QuickBooks item descriptions to card names in your library. Unmatched items can be exported for manual review.

---

## 📈 ANALYTICS REPORTS

### Customer Profit Report
**Shows:** Who bought cards from you and how much profit you made

Click **"👥 Customer Profit Report"** to see:
- Total customers
- Total revenue
- Total profit
- Average ROI percentage
- **Per-customer breakdown:**
  - Cards sold
  - Revenue generated
  - Profit made
  - ROI percentage
  - Average profit per card

**Example Output:**
```
================================================================================
CUSTOMER PROFITABILITY REPORT
Generated: 2025-11-17 14:30
================================================================================

Total Customers: 15
Total Revenue: $4,250.00
Total Profit: $1,890.00
Average ROI: 80.5%

--------------------------------------------------------------------------------

Customer                  Cards    Revenue      Profit       ROI
--------------------------------------------------------------------------------
Sarah Smith              45       $1,250.00    $620.00      98.4%
John Doe                 32       $890.00      $380.00      74.5%
Mike Johnson             28       $750.00      $290.00      63.2%
...
```

**Use Case:** Find your best customers to offer loyalty rewards, VIP pricing, or special services.

---

### Supplier ROI Report
**Shows:** Which suppliers give you the best return on investment

Click **"🏭 Supplier ROI Report"** to see:
- Total suppliers
- Total investment
- Profit realized (from sold cards)
- Potential profit (from unsold inventory)
- **Per-supplier breakdown:**
  - Cards acquired
  - Cards sold
  - Cards in stock
  - Total cost paid
  - Profit realized
  - ROI realized percentage
  - ROI potential percentage

**Example Output:**
```
==========================================================================================
SUPPLIER ROI ANALYSIS
Generated: 2025-11-17 14:30
==========================================================================================

Total Suppliers: 8
Total Investment: $2,500.00
Profit Realized: $1,200.00
Potential Profit: $3,800.00

------------------------------------------------------------------------------------------

Supplier             Acquired  Sold   Stock  Cost         Realized   ROI
------------------------------------------------------------------------------------------
CardShop USA        250       180    70     $1,200.00    $850.00    70.8%
Local Collector     150       120    30     $800.00      $480.00    60.0%
eBay Lot Purchase   100       45     55     $500.00      $150.00    30.0%
...
```

**Use Case:** 
- Focus on suppliers with highest ROI
- Avoid suppliers with low ROI (<30%)
- Track which acquisition sources are profitable

---

### Overall Summary
**Shows:** Big picture view of your entire business

Click **"💰 Overall Summary"** to see:
- **Inventory Overview:**
  - Total cards acquired
  - Cards sold
  - Cards available
  - Sell-through rate %
  
- **Financial Summary:**
  - Total cost (what you paid)
  - Total revenue (what you sold for)
  - Current stock value
  - Realized profit
  - Realized ROI %
  
- **Top 5 Customers** (by profit)
- **Top 5 Suppliers** (by ROI)

**Example Output:**
```
================================================================================
OVERALL BUSINESS SUMMARY
Generated: 2025-11-17 14:30
================================================================================

INVENTORY OVERVIEW
--------------------------------------------------------------------------------
Total Cards Acquired: 1,250
Cards Sold: 450
Cards Available: 800
Sell-Through Rate: 36.0%

FINANCIAL SUMMARY
--------------------------------------------------------------------------------
Total Investment (Cost): $2,500.00
Total Revenue (Sales): $4,250.00
Current Stock Value: $8,500.00
Realized Profit: $1,750.00
Realized ROI: 70.0%

TOP 5 CUSTOMERS BY PROFIT
--------------------------------------------------------------------------------
1. Sarah Smith                      $620.00 (98.4% ROI)
2. John Doe                         $380.00 (74.5% ROI)
...

TOP 5 SUPPLIERS BY ROI
--------------------------------------------------------------------------------
1. CardShop USA                     70.8% ROI ($850.00 profit)
2. Local Collector                  60.0% ROI ($480.00 profit)
...
```

**Use Case:** Monthly business review, investor reports, planning next purchases

---

## 💾 SAVE REPORTS

Click **"💾 Save All Reports"** to export everything to files:

Files created in `E:\MTTGG\REPORTS\`:
- `MTTGG_YYYYMMDD_HHMMSS_customers.txt` (readable report)
- `MTTGG_YYYYMMDD_HHMMSS_customers.csv` (Excel import)
- `MTTGG_YYYYMMDD_HHMMSS_suppliers.txt`
- `MTTGG_YYYYMMDD_HHMMSS_suppliers.csv`
- `MTTGG_YYYYMMDD_HHMMSS_summary.txt`
- `MTTGG_YYYYMMDD_HHMMSS_summary.csv`

**Use CSV files for:**
- Import into Excel/Google Sheets
- Create charts and graphs
- Share with accountant
- Tax preparation

---

## 🔧 ADVANCED FEATURES

### Python API Direct Usage

You can also use the analytics system from Python code:

```python
from nexus_library_system import NexusLibrarySystem
from customer_analytics import CustomerAnalytics
from quickbooks_integration import QuickBooksIntegration

# Initialize systems
library = NexusLibrarySystem()
analytics = CustomerAnalytics(library)
qb = QuickBooksIntegration(library)

# Import QuickBooks data
sales_results = qb.import_customer_sales("path/to/sales.csv")
purchase_results = qb.import_vendor_purchases("path/to/purchases.csv")

# Get specific customer ROI
customer_roi = library.get_customer_roi("Sarah Smith")
print(f"Profit from Sarah: ${customer_roi['profit']:.2f}")
print(f"ROI: {customer_roi['roi_percent']:.1f}%")

# Get specific supplier ROI
supplier_roi = library.get_supplier_roi("CardShop USA")
print(f"ROI from CardShop: {supplier_roi['roi_realized_percent']:.1f}%")

# Get all top customers
top_customers = library.get_profit_by_customer()
for customer in top_customers[:5]:  # Top 5
    print(f"{customer['customer']}: ${customer['profit']:.2f}")

# Generate and save reports
analytics.save_all_reports(prefix="Monthly")
```

### Name Mapping (for mismatched names)

If QuickBooks uses different customer names than your library:

```python
qb.add_customer_mapping(
    qb_name="Smith, Sarah J.",      # Name in QuickBooks
    library_name="Sarah Smith"       # Name in library system
)

qb.add_vendor_mapping(
    qb_name="CardShop USA Inc.",
    library_name="CardShop USA"
)
```

---

## 📋 UNMATCHED ITEMS

After importing QuickBooks data, some items might not match library cards (e.g., non-card items, typos, different names).

Click **"📋 Export Unmatched Items"** to create a CSV of items that couldn't be matched.

Review this file to:
1. Identify data entry errors
2. Find non-card items to ignore
3. Create name mappings for future imports
4. Manually reconcile discrepancies

---

## 💡 BUSINESS INSIGHTS YOU CAN GET

### Customer Analysis
- **Who are your whales?** (high-profit customers)
- **Who buys bulk?** (high volume, lower margin)
- **Who buys premium?** (low volume, high margin)
- **Customer lifetime value** (total profit over time)

### Supplier Analysis
- **Which suppliers have best cards?** (highest resale value)
- **Which suppliers overprice?** (low ROI)
- **Which sources are reliable?** (consistent good ROI)
- **Where to invest next?** (focus on proven suppliers)

### Inventory Decisions
- **Which cards sit too long?** (low sell-through rate)
- **Which cards flip fast?** (high sell-through, restock)
- **Price optimization** (are you leaving money on table?)
- **Acquisition budgeting** (allocate $ to best suppliers)

### Pricing Strategy
- **Am I pricing too low?** (high sell-through but low profit)
- **Am I pricing too high?** (low sell-through, high stock)
- **Competitive positioning** (profit margin vs competitors)

---

## 🎯 RECOMMENDED WORKFLOW

### Weekly:
1. Import last week's QuickBooks sales
2. Review top 5 customers
3. Identify hot-selling cards
4. Restock from best suppliers

### Monthly:
1. Import full month's QuickBooks data
2. Generate all reports
3. Calculate month-over-month growth
4. Plan next month's purchases based on ROI data

### Quarterly:
1. Full reconciliation with QuickBooks
2. Review all supplier relationships
3. Customer outreach to top 10 customers
4. Adjust pricing based on realized ROI

---

## ⚠️ TROUBLESHOOTING

### "Analytics system not available"
- Make sure library system initialized correctly
- Check that `nexus_library_system.py` is in PYTHON SOURCE FILES folder
- Restart application

### "QuickBooks integration not available"
- Check that `quickbooks_integration.py` exists
- Make sure library system is initialized first
- Restart application

### Import shows 0 cards matched
- Check CSV column names match expected format
- Review item descriptions (must contain card names)
- Export unmatched items to see what didn't match
- Try adding name mappings for common variations

### Profit numbers don't match QuickBooks
- Ensure all invoices are exported
- Check date ranges match
- Export unmatched items - might be missing cards
- Some transactions might not be card sales (shipping, fees, etc.)

---

## 📞 SUPPORT

If you need help:
1. Check the unmatched items report
2. Review QuickBooks export format
3. Verify library system has cards cataloged
4. Check that acquisitions have `acquired_from` field populated

---

## 🚀 NEXT LEVEL

With this data, you can:
- Build customer loyalty programs
- Offer VIP pricing to top customers
- Negotiate better rates with proven suppliers
- Set data-driven acquisition budgets
- Track your business growth month-over-month
- Make decisions based on REAL PROFIT DATA, not guesses

**"If it don't make dollars, it don't make sense!"** - Now you can PROVE the dollars! 💰
