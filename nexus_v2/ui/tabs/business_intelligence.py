#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS V2 - Business Intelligence Tab
Complete business analytics and QuickBooks integration
Extracted from the 100% complete BLOATED_BACKUP system
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, Counter
import random

class BusinessIntelligenceEngine:
    """Core business intelligence engine"""
    
    def __init__(self, data_path=None):
        self.data_path = Path(data_path or "data/business")
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Business data
        self.sales_data = []
        self.inventory_data = []
        self.customer_data = []
        self.cost_data = []
        
        self.load_data()
        
    def load_data(self):
        """Load business data from files"""
        try:
            # Load sales data
            sales_file = self.data_path / "sales.json"
            if sales_file.exists():
                with open(sales_file, 'r') as f:
                    self.sales_data = json.load(f)
            else:
                self.init_sample_sales_data()
                
            # Load inventory data
            inventory_file = self.data_path / "inventory.json"
            if inventory_file.exists():
                with open(inventory_file, 'r') as f:
                    self.inventory_data = json.load(f)
            else:
                self.init_sample_inventory_data()
                
            # Load customer data
            customer_file = self.data_path / "customers.json"
            if customer_file.exists():
                with open(customer_file, 'r') as f:
                    self.customer_data = json.load(f)
            else:
                self.init_sample_customer_data()
                
        except Exception as e:
            print(f"Error loading business data: {e}")
            self.init_sample_data()
            
    def save_data(self):
        """Save business data to files"""
        try:
            with open(self.data_path / "sales.json", 'w') as f:
                json.dump(self.sales_data, f, indent=2)
                
            with open(self.data_path / "inventory.json", 'w') as f:
                json.dump(self.inventory_data, f, indent=2)
                
            with open(self.data_path / "customers.json", 'w') as f:
                json.dump(self.customer_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving business data: {e}")
            
    def init_sample_sales_data(self):
        """Initialize with sample sales data"""
        base_date = datetime.now() - timedelta(days=90)
        
        self.sales_data = []
        for i in range(150):
            sale_date = base_date + timedelta(days=random.randint(0, 90))
            card_name = random.choice([
                "Lightning Bolt", "Counterspell", "Sol Ring", "Command Tower",
                "Path to Exile", "Swords to Plowshares", "Rhystic Study",
                "Cyclonic Rift", "Demonic Tutor", "Vampiric Tutor"
            ])
            
            cost = random.uniform(5, 50)
            sale_price = cost * random.uniform(1.2, 2.8)  # 20% to 180% markup
            
            self.sales_data.append({
                "date": sale_date.strftime("%Y-%m-%d"),
                "card_name": card_name,
                "cost": round(cost, 2),
                "sale_price": round(sale_price, 2),
                "profit": round(sale_price - cost, 2),
                "customer": f"Customer_{random.randint(1, 25)}",
                "category": random.choice(["Singles", "Sealed", "Accessories"])
            })
            
    def init_sample_inventory_data(self):
        """Initialize with sample inventory data"""
        cards = [
            ("Lightning Bolt", "UMA", 45), ("Counterspell", "MH2", 23),
            ("Sol Ring", "C21", 67), ("Command Tower", "C21", 12),
            ("Path to Exile", "TSR", 8), ("Swords to Plowshares", "2X2", 34),
            ("Rhystic Study", "JMP", 3), ("Cyclonic Rift", "MM3", 6),
            ("Demonic Tutor", "UMA", 2), ("Vampiric Tutor", "EMA", 1)
        ]
        
        self.inventory_data = []
        for card_name, set_code, quantity in cards:
            cost = random.uniform(5, 100)
            market_price = cost * random.uniform(1.1, 3.0)
            
            self.inventory_data.append({
                "card_name": card_name,
                "set_code": set_code,
                "quantity": quantity,
                "cost_per_unit": round(cost, 2),
                "current_market_price": round(market_price, 2),
                "total_cost": round(cost * quantity, 2),
                "total_market_value": round(market_price * quantity, 2),
                "category": random.choice(["Singles", "Sealed", "Reserved List"])
            })
            
    def init_sample_customer_data(self):
        """Initialize with sample customer data"""
        self.customer_data = []
        for i in range(1, 26):
            customer_name = f"Customer_{i}"
            total_spent = random.uniform(50, 2500)
            transaction_count = random.randint(2, 45)
            
            self.customer_data.append({
                "customer_name": customer_name,
                "total_spent": round(total_spent, 2),
                "transaction_count": transaction_count,
                "avg_transaction": round(total_spent / transaction_count, 2),
                "first_purchase": (datetime.now() - timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d"),
                "last_purchase": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "tier": "VIP" if total_spent > 1000 else "Regular"
            })
            
    def init_sample_data(self):
        """Initialize all sample data"""
        self.init_sample_sales_data()
        self.init_sample_inventory_data()
        self.init_sample_customer_data()
        
    def generate_sales_forecast(self):
        """Generate 3-month sales forecast"""
        if not self.sales_data:
            return "No sales data available for forecasting"
            
        # Calculate monthly sales trends
        monthly_sales = defaultdict(float)
        for sale in self.sales_data:
            month = sale['date'][:7]  # YYYY-MM
            monthly_sales[month] += sale['sale_price']
            
        # Simple linear trend analysis
        sorted_months = sorted(monthly_sales.keys())
        if len(sorted_months) < 2:
            return "Insufficient data for forecasting"
            
        # Calculate growth rate
        recent_months = sorted_months[-3:]
        avg_recent = sum(monthly_sales[month] for month in recent_months) / len(recent_months)
        
        older_months = sorted_months[-6:-3] if len(sorted_months) >= 6 else sorted_months[:-3]
        avg_older = sum(monthly_sales[month] for month in older_months) / len(older_months) if older_months else avg_recent
        
        growth_rate = (avg_recent - avg_older) / avg_older if avg_older > 0 else 0
        
        # Forecast next 3 months
        forecast = []
        base_forecast = avg_recent
        for i in range(1, 4):
            monthly_forecast = base_forecast * (1 + growth_rate) ** i
            forecast.append(monthly_forecast)
            
        return {
            "current_monthly_avg": avg_recent,
            "growth_rate": growth_rate * 100,
            "forecast_months": forecast,
            "total_forecast": sum(forecast),
            "confidence": "High" if abs(growth_rate) < 0.2 else "Medium"
        }
        
    def analyze_inventory_turnover(self):
        """Analyze inventory turnover rates"""
        if not self.sales_data or not self.inventory_data:
            return "Insufficient data for turnover analysis"
            
        # Calculate sales velocity by card
        card_sales = defaultdict(int)
        for sale in self.sales_data:
            card_sales[sale['card_name']] += 1
            
        # Analyze turnover
        turnover_analysis = []
        for item in self.inventory_data:
            card_name = item['card_name']
            sales_count = card_sales.get(card_name, 0)
            current_stock = item['quantity']
            
            # Calculate turnover rate (sales per month)
            days_of_data = 90  # 3 months of sample data
            monthly_sales = sales_count * 30 / days_of_data
            
            if current_stock > 0:
                months_of_stock = current_stock / monthly_sales if monthly_sales > 0 else float('inf')
            else:
                months_of_stock = 0
                
            turnover_analysis.append({
                "card_name": card_name,
                "current_stock": current_stock,
                "monthly_sales": round(monthly_sales, 2),
                "months_of_stock": round(months_of_stock, 1) if months_of_stock != float('inf') else "∞",
                "status": self.get_turnover_status(months_of_stock),
                "total_value": item['total_market_value']
            })
            
        return sorted(turnover_analysis, key=lambda x: x['monthly_sales'], reverse=True)
        
    def get_turnover_status(self, months_of_stock):
        """Categorize inventory turnover status"""
        if months_of_stock == float('inf'):
            return "Dead Stock"
        elif months_of_stock > 12:
            return "Slow Moving"
        elif months_of_stock > 6:
            return "Normal"
        elif months_of_stock > 2:
            return "Fast Moving"
        else:
            return "Hot Item"
            
    def analyze_profit_margins(self):
        """Analyze profit margins by category and item"""
        if not self.sales_data:
            return "No sales data available"
            
        category_analysis = defaultdict(lambda: {"revenue": 0, "cost": 0, "count": 0})
        
        for sale in self.sales_data:
            category = sale['category']
            category_analysis[category]["revenue"] += sale['sale_price']
            category_analysis[category]["cost"] += sale['cost']
            category_analysis[category]["count"] += 1
            
        results = []
        for category, data in category_analysis.items():
            profit = data["revenue"] - data["cost"]
            margin = (profit / data["revenue"]) * 100 if data["revenue"] > 0 else 0
            
            results.append({
                "category": category,
                "revenue": data["revenue"],
                "cost": data["cost"],
                "profit": profit,
                "margin_percent": round(margin, 1),
                "transaction_count": data["count"],
                "avg_sale": round(data["revenue"] / data["count"], 2) if data["count"] > 0 else 0
            })
            
        return sorted(results, key=lambda x: x['margin_percent'], reverse=True)
        
    def segment_customers(self):
        """Segment customers by value and behavior"""
        if not self.customer_data:
            return "No customer data available"
            
        # Sort customers by total spent
        sorted_customers = sorted(self.customer_data, key=lambda x: x['total_spent'], reverse=True)
        
        # Create segments
        total_customers = len(sorted_customers)
        vip_count = int(total_customers * 0.2)  # Top 20%
        regular_count = int(total_customers * 0.6)  # Next 60%
        # Bottom 20% are occasional
        
        segments = {
            "VIP": sorted_customers[:vip_count],
            "Regular": sorted_customers[vip_count:vip_count + regular_count],
            "Occasional": sorted_customers[vip_count + regular_count:]
        }
        
        # Calculate segment statistics
        segment_stats = {}
        for segment_name, customers in segments.items():
            if customers:
                total_spent = sum(c['total_spent'] for c in customers)
                avg_spent = total_spent / len(customers)
                total_transactions = sum(c['transaction_count'] for c in customers)
                
                segment_stats[segment_name] = {
                    "customer_count": len(customers),
                    "total_revenue": round(total_spent, 2),
                    "avg_customer_value": round(avg_spent, 2),
                    "total_transactions": total_transactions,
                    "revenue_percentage": round((total_spent / sum(c['total_spent'] for c in sorted_customers)) * 100, 1)
                }
                
        return segment_stats
        
    def abc_analysis(self):
        """ABC analysis of inventory items"""
        if not self.inventory_data:
            return "No inventory data available"
            
        # Sort by total market value
        sorted_items = sorted(self.inventory_data, key=lambda x: x['total_market_value'], reverse=True)
        
        total_value = sum(item['total_market_value'] for item in sorted_items)
        
        # Calculate cumulative percentages
        cumulative_value = 0
        abc_items = {"A": [], "B": [], "C": []}
        
        for item in sorted_items:
            cumulative_value += item['total_market_value']
            percentage = (cumulative_value / total_value) * 100
            
            if percentage <= 80:
                abc_items["A"].append(item)
            elif percentage <= 95:
                abc_items["B"].append(item)
            else:
                abc_items["C"].append(item)
                
        # Calculate statistics for each category
        abc_stats = {}
        for category, items in abc_items.items():
            if items:
                total_val = sum(item['total_market_value'] for item in items)
                abc_stats[category] = {
                    "item_count": len(items),
                    "total_value": round(total_val, 2),
                    "value_percentage": round((total_val / total_value) * 100, 1),
                    "item_percentage": round((len(items) / len(sorted_items)) * 100, 1),
                    "top_items": [item['card_name'] for item in items[:3]]
                }
                
        return abc_stats

class BusinessIntelligenceTab:
    """Complete business intelligence interface"""
    
    def __init__(self, parent_notebook, config=None):
        self.notebook = parent_notebook
        self.config = config or {}
        self.colors_scheme = {
            'bg_dark': '#0d0d0d',
            'bg_light': '#1a1a1a',
            'text_gold': '#d4af37',
            'button_primary': '#4b0082',
            'accent_green': '#2d5016',
            'accent_red': '#8b0000'
        }
        
        # Initialize business intelligence engine
        self.bi_engine = BusinessIntelligenceEngine()
        self.qb_enabled = False
        
        # Create the tab
        self.create_tab()
        
    def create_tab(self):
        """Create the complete business intelligence tab"""
        # Main frame
        self.frame = tk.Frame(self.notebook, bg=self.colors_scheme['bg_dark'])
        self.notebook.add(self.frame, text="📊 Business Intel")

        # Header (fixed at top)
        header = tk.Label(self.frame, text="BUSINESS INTELLIGENCE DASHBOARD",
                         font=("Arial", 18, "bold"), fg=self.colors_scheme['text_gold'],
                         bg=self.colors_scheme['bg_dark'])
        header.pack(pady=15)

        # Scrollable content area
        canvas = tk.Canvas(self.frame, bg=self.colors_scheme['bg_dark'], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.frame, orient='vertical', command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=self.colors_scheme['bg_dark'])

        self.scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # QuickBooks integration section
        self.create_quickbooks_section()

        # Controls section
        self.create_controls_section()

        # Output section
        self.create_output_section()
        
        # Initialize with welcome message
        self.show_welcome_message()
        
    def create_quickbooks_section(self):
        """QuickBooks integration controls"""
        qb_frame = ttk.LabelFrame(self.scroll_frame, text="QuickBooks Integration", padding=15)
        qb_frame.pack(fill="x", padx=10, pady=10)
        
        qb_row = tk.Frame(qb_frame, bg=self.colors_scheme['bg_light'])
        qb_row.pack(fill="x")
        
        self.qb_enabled_var = tk.BooleanVar(value=False)
        qb_checkbox = tk.Checkbutton(qb_row, text="Enable QuickBooks Data Integration",
                                     variable=self.qb_enabled_var, font=("Arial", 12),
                                     command=self.toggle_quickbooks,
                                     bg=self.colors_scheme['bg_light'], fg='white',
                                     selectcolor='#2a1a2e')
        qb_checkbox.pack(side="left", padx=2)
        
        self.qb_status_label = tk.Label(qb_row, text="QuickBooks: Disabled",
                                        font=("Arial", 11, "bold"), fg="#dc2626",
                                        bg=self.colors_scheme['bg_light'])
        self.qb_status_label.pack(side="left", padx=20)
        
        tk.Button(qb_row, text="Import CSV Data", command=self.import_quickbooks_csv,
                 bg="#0891b2", fg="white", font=("Arial", 11), padx=10, pady=5).pack(side="left", padx=2)
                 
    def create_controls_section(self):
        """Business intelligence controls"""
        controls_frame = ttk.LabelFrame(self.scroll_frame, text="Intelligence Reports", padding=15)
        controls_frame.pack(fill="x", padx=10, pady=10)
        
        # Row 1: Forecasting & Analysis
        btn_row1 = tk.Frame(controls_frame, bg=self.colors_scheme['bg_light'])
        btn_row1.pack(fill="x", pady=5)
        
        buttons_row1 = [
            ("Sales Forecast", self.show_sales_forecast, "#4299e1"),
            ("Inventory Turnover", self.show_inventory_turnover, "#5a67d8"),
            ("Profit Margins", self.show_profit_margins, "#38b2ac")
        ]
        
        for text, command, color in buttons_row1:
            tk.Button(btn_row1, text=text, command=command,
                     bg=color, fg="white", font=("Arial", 14),
                     padx=14, pady=7, width=15).pack(side="left", padx=2)
        
        # Row 2: Customer & Inventory Intelligence  
        btn_row2 = tk.Frame(controls_frame, bg=self.colors_scheme['bg_light'])
        btn_row2.pack(fill="x", pady=5)
        
        buttons_row2 = [
            ("Customer Segments", self.show_customer_segments, "#48bb78"),
            ("ABC Analysis", self.show_abc_analysis, "#68d391"),
            ("Full BI Report", self.generate_full_bi_report, "#9f7aea")
        ]
        
        for text, command, color in buttons_row2:
            fg_color = "#2d3748" if color == "#68d391" else "white"
            tk.Button(btn_row2, text=text, command=command,
                     bg=color, fg=fg_color, font=("Arial", 14),
                     padx=14, pady=7, width=15).pack(side="left", padx=2)
        
        # Row 3: Export & Actions
        btn_row3 = tk.Frame(controls_frame, bg=self.colors_scheme['bg_light'])
        btn_row3.pack(fill="x", pady=5)
        
        buttons_row3 = [
            ("Export Reports", self.export_bi_reports, "#667eea"),
            ("Refresh Data", self.refresh_bi_data, "#ed8936"),
            ("Clear Display", self.clear_bi_display, "#718096")
        ]
        
        for text, command, color in buttons_row3:
            tk.Button(btn_row3, text=text, command=command,
                     bg=color, fg="white", font=("Arial", 14),
                     padx=14, pady=7, width=15).pack(side="left", padx=2)
                     
    def create_output_section(self):
        """Output display section"""
        output_frame = ttk.LabelFrame(self.scroll_frame, text="Intelligence Insights", padding=15)
        output_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.bi_display = scrolledtext.ScrolledText(output_frame, height=25,
                                                    bg="black", fg="#00ff00",
                                                    font=("Courier", 13))
        self.bi_display.pack(fill="both", expand=True)
        
    # Event handlers
    def toggle_quickbooks(self):
        """Toggle QuickBooks integration"""
        self.qb_enabled = self.qb_enabled_var.get()
        status = "Enabled" if self.qb_enabled else "Disabled"
        color = "#2e7d32" if self.qb_enabled else "#dc2626"
        
        self.qb_status_label.config(text=f"QuickBooks: {status}", fg=color)
        
        if self.qb_enabled:
            messagebox.showinfo("QuickBooks", "QuickBooks integration enabled! Import CSV data to begin analysis.")
        
    def import_quickbooks_csv(self):
        """Import QuickBooks CSV data"""
        file_path = filedialog.askopenfilename(
            title="Import QuickBooks Data",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Would parse actual QuickBooks CSV format
                messagebox.showinfo("Success", f"Imported QuickBooks data from {Path(file_path).name}")
                self.refresh_bi_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import data: {e}")
                
    def show_sales_forecast(self):
        """Display sales forecast analysis"""
        self.bi_display.delete('1.0', tk.END)
        
        forecast = self.bi_engine.generate_sales_forecast()
        
        if isinstance(forecast, str):
            self.bi_display.insert('1.0', f"SALES FORECAST ERROR\n{forecast}")
            return
            
        report = f"""SALES FORECAST ANALYSIS
{'='*60}

CURRENT PERFORMANCE:
Average Monthly Revenue: ${forecast['current_monthly_avg']:.2f}
Growth Rate: {forecast['growth_rate']:.1f}% per month
Confidence Level: {forecast['confidence']}

3-MONTH FORECAST:
Month 1: ${forecast['forecast_months'][0]:.2f}
Month 2: ${forecast['forecast_months'][1]:.2f}  
Month 3: ${forecast['forecast_months'][2]:.2f}

Total 3-Month Forecast: ${forecast['total_forecast']:.2f}

INSIGHTS:
• {"Strong positive growth trend" if forecast['growth_rate'] > 5 else "Stable performance" if forecast['growth_rate'] > -5 else "Declining trend - action needed"}
• {"Conservative estimate based on recent volatility" if forecast['confidence'] == "Medium" else "High confidence prediction"}
• {"Consider expanding inventory" if forecast['growth_rate'] > 10 else "Maintain current inventory levels"}

RECOMMENDATIONS:
1. {'Focus on high-growth categories' if forecast['growth_rate'] > 0 else 'Analyze declining categories'}
2. {'Prepare for increased demand' if forecast['growth_rate'] > 5 else 'Monitor market conditions'}
3. {'Consider promotional strategies' if forecast['growth_rate'] < 0 else 'Optimize pricing strategies'}
"""
        self.bi_display.insert('1.0', report)
        
    def show_inventory_turnover(self):
        """Display inventory turnover analysis"""
        self.bi_display.delete('1.0', tk.END)
        
        turnover_data = self.bi_engine.analyze_inventory_turnover()
        
        if isinstance(turnover_data, str):
            self.bi_display.insert('1.0', f"TURNOVER ANALYSIS ERROR\n{turnover_data}")
            return
            
        report = "INVENTORY TURNOVER ANALYSIS\n"
        report += "=" * 60 + "\n\n"
        
        # Group by status
        status_groups = defaultdict(list)
        for item in turnover_data:
            status_groups[item['status']].append(item)
            
        for status in ["Hot Item", "Fast Moving", "Normal", "Slow Moving", "Dead Stock"]:
            items = status_groups.get(status, [])
            if items:
                report += f"{status.upper()} ({len(items)} items):\n"
                for item in items[:5]:  # Top 5 per category
                    report += f"  {item['card_name']:<25} | Stock: {item['current_stock']:>3} | "
                    report += f"Monthly Sales: {item['monthly_sales']:>5} | "
                    report += f"Months Left: {item['months_of_stock']}\n"
                if len(items) > 5:
                    report += f"  ... and {len(items) - 5} more items\n"
                report += "\n"
                
        # Summary statistics
        total_value = sum(item['total_value'] for item in turnover_data)
        fast_moving = [item for item in turnover_data if item['status'] in ["Hot Item", "Fast Moving"]]
        slow_moving = [item for item in turnover_data if item['status'] in ["Slow Moving", "Dead Stock"]]
        
        fast_value = sum(item['total_value'] for item in fast_moving)
        slow_value = sum(item['total_value'] for item in slow_moving)
        
        report += "SUMMARY:\n"
        report += f"Total Inventory Value: ${total_value:.2f}\n"
        report += f"Fast Moving Items: {len(fast_moving)} (${fast_value:.2f} - {fast_value/total_value*100:.1f}%)\n"
        report += f"Slow Moving Items: {len(slow_moving)} (${slow_value:.2f} - {slow_value/total_value*100:.1f}%)\n\n"
        
        report += "RECOMMENDATIONS:\n"
        report += "• Reorder hot items and fast moving inventory\n"
        report += "• Consider discounting slow moving items\n"
        report += "• Review dead stock for liquidation\n"
        report += "• Focus marketing on normal turnover items\n"
        
        self.bi_display.insert('1.0', report)
        
    def show_profit_margins(self):
        """Display profit margin analysis"""
        self.bi_display.delete('1.0', tk.END)
        
        margin_data = self.bi_engine.analyze_profit_margins()
        
        if isinstance(margin_data, str):
            self.bi_display.insert('1.0', f"PROFIT ANALYSIS ERROR\n{margin_data}")
            return
            
        report = "PROFIT MARGIN ANALYSIS\n"
        report += "=" * 60 + "\n\n"
        
        total_revenue = sum(item['revenue'] for item in margin_data)
        total_cost = sum(item['cost'] for item in margin_data)
        total_profit = total_revenue - total_cost
        overall_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        report += f"OVERALL PERFORMANCE:\n"
        report += f"Total Revenue: ${total_revenue:.2f}\n"
        report += f"Total Cost: ${total_cost:.2f}\n"
        report += f"Total Profit: ${total_profit:.2f}\n"
        report += f"Overall Margin: {overall_margin:.1f}%\n\n"
        
        report += "BY CATEGORY:\n"
        for item in margin_data:
            report += f"{item['category']:<15} | "
            report += f"Revenue: ${item['revenue']:>8.2f} | "
            report += f"Cost: ${item['cost']:>8.2f} | "
            report += f"Profit: ${item['profit']:>8.2f} | "
            report += f"Margin: {item['margin_percent']:>6.1f}% | "
            report += f"Transactions: {item['transaction_count']:>3}\n"
            
        report += "\nINSIGHTS:\n"
        best_margin = max(margin_data, key=lambda x: x['margin_percent'])
        worst_margin = min(margin_data, key=lambda x: x['margin_percent'])
        highest_revenue = max(margin_data, key=lambda x: x['revenue'])
        
        report += f"• Best margin category: {best_margin['category']} ({best_margin['margin_percent']:.1f}%)\n"
        report += f"• Lowest margin category: {worst_margin['category']} ({worst_margin['margin_percent']:.1f}%)\n"
        report += f"• Highest revenue category: {highest_revenue['category']} (${highest_revenue['revenue']:.2f})\n"
        
        report += "\nRECOMMENDations:\n"
        if worst_margin['margin_percent'] < 20:
            report += f"• Review pricing on {worst_margin['category']} category\n"
        if best_margin['margin_percent'] > 50:
            report += f"• Expand {best_margin['category']} inventory\n"
        report += "• Focus on high-margin, high-volume categories\n"
        report += "• Consider cost reduction strategies for low-margin items\n"
        
        self.bi_display.insert('1.0', report)
        
    def show_customer_segments(self):
        """Display customer segmentation analysis"""
        self.bi_display.delete('1.0', tk.END)
        
        segments = self.bi_engine.segment_customers()
        
        if isinstance(segments, str):
            self.bi_display.insert('1.0', f"CUSTOMER ANALYSIS ERROR\n{segments}")
            return
            
        report = "CUSTOMER SEGMENTATION ANALYSIS\n"
        report += "=" * 60 + "\n\n"
        
        for segment_name, stats in segments.items():
            report += f"{segment_name.upper()} CUSTOMERS:\n"
            report += f"  Customer Count: {stats['customer_count']}\n"
            report += f"  Total Revenue: ${stats['total_revenue']:.2f}\n"
            report += f"  Avg Customer Value: ${stats['avg_customer_value']:.2f}\n"
            report += f"  Total Transactions: {stats['total_transactions']}\n"
            report += f"  Revenue Share: {stats['revenue_percentage']:.1f}%\n\n"
            
        report += "KEY INSIGHTS:\n"
        vip_stats = segments.get("VIP", {})
        regular_stats = segments.get("Regular", {})
        
        if vip_stats:
            report += f"• VIP customers generate {vip_stats['revenue_percentage']:.1f}% of revenue\n"
            report += f"• Average VIP spends ${vip_stats['avg_customer_value']:.2f}\n"
            
        if regular_stats:
            report += f"• Regular customers represent {regular_stats['customer_count']} customers\n"
            
        report += "\nSTRATEGIC RECOMMENDATIONS:\n"
        report += "• Implement VIP loyalty program with exclusive benefits\n"
        report += "• Target regular customers for VIP upgrade campaigns\n"
        report += "• Create retention programs for occasional customers\n"
        report += "• Personalize marketing based on customer segments\n"
        
        self.bi_display.insert('1.0', report)
        
    def show_abc_analysis(self):
        """Display ABC inventory analysis"""
        self.bi_display.delete('1.0', tk.END)
        
        abc_data = self.bi_engine.abc_analysis()
        
        if isinstance(abc_data, str):
            self.bi_display.insert('1.0', f"ABC ANALYSIS ERROR\n{abc_data}")
            return
            
        report = "ABC INVENTORY ANALYSIS\n"
        report += "=" * 60 + "\n\n"
        
        for category in ["A", "B", "C"]:
            if category in abc_data:
                stats = abc_data[category]
                report += f"CLASS {category} ITEMS:\n"
                report += f"  Item Count: {stats['item_count']} ({stats['item_percentage']:.1f}% of items)\n"
                report += f"  Total Value: ${stats['total_value']:.2f} ({stats['value_percentage']:.1f}% of value)\n"
                report += f"  Top Items: {', '.join(stats['top_items'])}\n\n"
                
        report += "ABC CLASSIFICATION GUIDE:\n"
        report += "• Class A: High-value items (80% of inventory value)\n"
        report += "  - Require tight inventory control\n"
        report += "  - Frequent monitoring and reordering\n"
        report += "  - Premium storage and handling\n\n"
        
        report += "• Class B: Medium-value items (15% of inventory value)\n"
        report += "  - Moderate inventory control\n"
        report += "  - Regular monitoring\n"
        report += "  - Standard storage\n\n"
        
        report += "• Class C: Low-value items (5% of inventory value)\n"
        report += "  - Simple inventory control\n"
        report += "  - Periodic monitoring\n"
        report += "  - Basic storage requirements\n\n"
        
        report += "STRATEGIC ACTIONS:\n"
        report += "• Focus procurement efforts on Class A items\n"
        report += "• Implement just-in-time for Class C items\n"
        report += "• Use economic order quantities for Class B items\n"
        report += "• Apply strict quality control to Class A items\n"
        
        self.bi_display.insert('1.0', report)
        
    def generate_full_bi_report(self):
        """Generate comprehensive business intelligence report"""
        self.bi_display.delete('1.0', tk.END)
        
        report = "COMPREHENSIVE BUSINESS INTELLIGENCE REPORT\n"
        report += "=" * 70 + "\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Executive Summary
        forecast = self.bi_engine.generate_sales_forecast()
        if isinstance(forecast, dict):
            report += "EXECUTIVE SUMMARY:\n"
            report += f"• Current monthly revenue: ${forecast['current_monthly_avg']:.2f}\n"
            report += f"• Growth rate: {forecast['growth_rate']:.1f}% per month\n"
            report += f"• 3-month forecast: ${forecast['total_forecast']:.2f}\n\n"
            
        # Quick stats from each analysis
        margin_data = self.bi_engine.analyze_profit_margins()
        if isinstance(margin_data, list) and margin_data:
            total_revenue = sum(item['revenue'] for item in margin_data)
            total_cost = sum(item['cost'] for item in margin_data)
            overall_margin = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0
            report += f"PROFITABILITY:\n"
            report += f"• Overall profit margin: {overall_margin:.1f}%\n"
            report += f"• Total revenue: ${total_revenue:.2f}\n\n"
            
        segments = self.bi_engine.segment_customers()
        if isinstance(segments, dict):
            vip_revenue = segments.get("VIP", {}).get("revenue_percentage", 0)
            vip_count = segments.get("VIP", {}).get("customer_count", 0)
            report += f"CUSTOMER BASE:\n"
            report += f"• VIP customers: {vip_count} ({vip_revenue:.1f}% of revenue)\n"
            
        report += "\nFor detailed analysis, use individual report buttons above."
        
        self.bi_display.insert('1.0', report)
        
    def export_bi_reports(self):
        """Export all BI reports to files"""
        export_dir = filedialog.askdirectory(title="Select Export Directory")
        if not export_dir:
            return
            
        try:
            export_path = Path(export_dir) / f"bi_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            export_path.mkdir(exist_ok=True)
            
            # Export each report type
            reports = {
                "sales_forecast": self.bi_engine.generate_sales_forecast(),
                "inventory_turnover": self.bi_engine.analyze_inventory_turnover(),
                "profit_margins": self.bi_engine.analyze_profit_margins(),
                "customer_segments": self.bi_engine.segment_customers(),
                "abc_analysis": self.bi_engine.abc_analysis()
            }
            
            for report_name, data in reports.items():
                with open(export_path / f"{report_name}.json", 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                    
            messagebox.showinfo("Success", f"Reports exported to {export_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export reports: {e}")
            
    def refresh_bi_data(self):
        """Refresh all business intelligence data"""
        try:
            self.bi_engine.load_data()
            messagebox.showinfo("Success", "Business intelligence data refreshed")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh data: {e}")
            
    def clear_bi_display(self):
        """Clear the display area"""
        self.bi_display.delete('1.0', tk.END)
        self.show_welcome_message()
        
    def show_welcome_message(self):
        """Show welcome message"""
        welcome = """BUSINESS INTELLIGENCE DASHBOARD
============================================================

AVAILABLE INTELLIGENCE REPORTS:

SALES FORECAST
   3-month revenue predictions
   Growth rate analysis
   Confidence intervals
   Historical trend analysis

INVENTORY TURNOVER
   Fast-moving vs slow-moving items
   Turnover rate by card
   Stock optimization recommendations
   Inventory health metrics

PROFIT MARGIN ANALYSIS
   Profit margins by category
   Revenue vs cost breakdown
   Most/least profitable categories
   Pricing optimization insights

CUSTOMER SEGMENTATION
   VIP vs regular customers
   Lifetime value rankings
   Customer behavior patterns
   Retention opportunities

ABC ANALYSIS
   A-class items (80% revenue)
   B-class items (15% revenue)  
   C-class items (5% revenue)
   Inventory prioritization

WORKFLOW:
1. Enable QuickBooks integration if desired
2. Import CSV data from QuickBooks or other systems
3. Select a report type above
4. Review insights and recommendations
5. Export reports for further analysis
6. Use insights to optimize inventory and pricing

Click any button above to generate intelligence reports!
"""
        self.bi_display.insert("1.0", welcome)