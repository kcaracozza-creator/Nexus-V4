"""
Business Intelligence Dashboard for MTTGG
Advanced analytics for sales forecasting, inventory turnover, and market trends

Features:
- Sales forecasting with trend analysis
- Inventory turnover rate calculations
- Profit margin analysis by category
- Market trend tracking
- Customer segmentation and lifetime value
- ABC analysis for inventory prioritization
- Seasonal trend detection
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import statistics
import json


class BusinessIntelligence:
    """
    Advanced business intelligence for card shop operations
    Provides actionable insights for inventory and sales optimization
    """
    
    def __init__(self, library_system, qb_integration=None):
        """
        Initialize BI dashboard
        
        Args:
            library_system: NexusLibrarySystem instance
            qb_integration: QuickBooksIntegration instance (optional)
        """
        self.library = library_system
        self.qb = qb_integration
        self.reports_dir = "E:/MTTGG/BI_REPORTS"
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def sales_forecast(self, months_ahead: int = 3) -> Dict:
        """
        Forecast future sales based on historical trends
        
        Args:
            months_ahead: Number of months to forecast
            
        Returns:
            Dictionary with forecast data and confidence metrics
        """
        if not self.qb or not self.qb.sales_data:
            return {
                'status': 'error',
                'message': 'No sales data available for forecasting'
            }
        
        # Aggregate sales by month
        monthly_sales = defaultdict(float)
        monthly_units = defaultdict(int)
        
        for sale in self.qb.sales_data:
            date_str = sale.get('date', '')
            if date_str:
                try:
                    sale_date = datetime.strptime(date_str, '%Y-%m-%d')
                    month_key = sale_date.strftime('%Y-%m')
                    monthly_sales[month_key] += sale['total_price']
                    monthly_units[month_key] += sale['quantity']
                except:
                    continue
        
        if len(monthly_sales) < 2:
            return {
                'status': 'insufficient_data',
                'message': 'Need at least 2 months of sales data for forecasting'
            }
        
        # Calculate trend (simple linear regression)
        months = sorted(monthly_sales.keys())
        revenues = [monthly_sales[m] for m in months]
        units = [monthly_units[m] for m in months]
        
        avg_revenue = statistics.mean(revenues)
        avg_units = statistics.mean(units)
        
        # Calculate growth rate
        if len(revenues) >= 2:
            recent_avg = statistics.mean(revenues[-3:]) if len(revenues) >= 3 else revenues[-1]
            older_avg = statistics.mean(revenues[:3]) if len(revenues) >= 6 else revenues[0]
            growth_rate = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
        else:
            growth_rate = 0
        
        # Generate forecast
        forecasts = []
        last_month = datetime.strptime(months[-1], '%Y-%m')
        
        for i in range(1, months_ahead + 1):
            forecast_month = last_month + timedelta(days=30 * i)
            forecast_revenue = avg_revenue * (1 + growth_rate * i)
            forecast_units = int(avg_units * (1 + growth_rate * i))
            
            forecasts.append({
                'month': forecast_month.strftime('%Y-%m'),
                'revenue': round(forecast_revenue, 2),
                'units': forecast_units,
                'confidence': 'Medium' if abs(growth_rate) < 0.2 else 'Low'
            })
        
        return {
            'status': 'success',
            'historical_months': len(months),
            'avg_monthly_revenue': round(avg_revenue, 2),
            'avg_monthly_units': round(avg_units, 2),
            'growth_rate': round(growth_rate * 100, 2),
            'forecasts': forecasts
        }
    
    def inventory_turnover_analysis(self) -> Dict:
        """
        Calculate inventory turnover rates for all cards
        
        Returns:
            Dictionary with turnover metrics and slow-moving inventory
        """
        if not self.qb or not self.qb.sales_data:
            return {
                'status': 'error',
                'message': 'No sales data available'
            }
        
        # Count sales per card
        card_sales = Counter()
        card_revenue = defaultdict(float)
        
        for sale in self.qb.sales_data:
            card_name = sale.get('card_name', 'Unknown')
            card_sales[card_name] += sale.get('quantity', 0)
            card_revenue[card_name] += sale.get('total_price', 0)
        
        # Get current inventory counts
        inventory_counts = {}
        for box_id, cards in self.library.box_inventory.items():
            for card in cards:
                card_name = card.get('name', 'Unknown')
                inventory_counts[card_name] = inventory_counts.get(card_name, 0) + 1
        
        # Calculate turnover rates
        turnover_data = []
        for card_name, current_stock in inventory_counts.items():
            sales_count = card_sales.get(card_name, 0)
            revenue = card_revenue.get(card_name, 0)
            
            # Turnover rate = Sales / Average Inventory (simplified: current stock)
            turnover_rate = sales_count / current_stock if current_stock > 0 else 0
            
            turnover_data.append({
                'card_name': card_name,
                'current_stock': current_stock,
                'units_sold': sales_count,
                'revenue': round(revenue, 2),
                'turnover_rate': round(turnover_rate, 2),
                'status': self._classify_turnover(turnover_rate)
            })
        
        # Sort by turnover rate
        turnover_data.sort(key=lambda x: x['turnover_rate'], reverse=True)
        
        # Identify slow movers
        slow_movers = [item for item in turnover_data if item['status'] == 'Slow']
        fast_movers = [item for item in turnover_data if item['status'] == 'Fast']
        
        return {
            'status': 'success',
            'total_unique_cards': len(turnover_data),
            'fast_movers': len(fast_movers),
            'slow_movers': len(slow_movers),
            'top_performers': turnover_data[:10],
            'slow_inventory': slow_movers[:20],
            'avg_turnover_rate': round(statistics.mean([x['turnover_rate'] for x in turnover_data]), 2)
        }
    
    def _classify_turnover(self, rate: float) -> str:
        """Classify inventory turnover rate"""
        if rate >= 2.0:
            return 'Fast'
        elif rate >= 1.0:
            return 'Normal'
        elif rate >= 0.5:
            return 'Slow'
        else:
            return 'Very Slow'
    
    def profit_margin_by_category(self) -> Dict:
        """
        Analyze profit margins by card category/type
        
        Returns:
            Dictionary with margin analysis by category
        """
        if not self.qb or not self.qb.sales_data or not self.qb.purchase_data:
            return {
                'status': 'error',
                'message': 'Insufficient transaction data'
            }
        
        # Build cost basis from purchases
        card_costs = {}
        for purchase in self.qb.purchase_data:
            card_name = purchase.get('card_name', 'Unknown')
            cost = purchase.get('total_price', 0)
            qty = purchase.get('quantity', 1)
            card_costs[card_name] = cost / qty if qty > 0 else 0
        
        # Calculate margins by category
        category_data = defaultdict(lambda: {
            'revenue': 0,
            'cost': 0,
            'units_sold': 0,
            'cards': []
        })
        
        for sale in self.qb.sales_data:
            card_name = sale.get('card_name', 'Unknown')
            revenue = sale.get('total_price', 0)
            qty = sale.get('quantity', 0)
            
            # Determine category (simplified)
            category = self._categorize_card(card_name)
            
            cost = card_costs.get(card_name, 0) * qty
            
            category_data[category]['revenue'] += revenue
            category_data[category]['cost'] += cost
            category_data[category]['units_sold'] += qty
            category_data[category]['cards'].append(card_name)
        
        # Calculate margins
        margin_report = []
        for category, data in category_data.items():
            revenue = data['revenue']
            cost = data['cost']
            profit = revenue - cost
            margin_pct = (profit / revenue * 100) if revenue > 0 else 0
            
            margin_report.append({
                'category': category,
                'revenue': round(revenue, 2),
                'cost': round(cost, 2),
                'profit': round(profit, 2),
                'margin_percent': round(margin_pct, 2),
                'units_sold': data['units_sold'],
                'unique_cards': len(set(data['cards']))
            })
        
        # Sort by profit
        margin_report.sort(key=lambda x: x['profit'], reverse=True)
        
        return {
            'status': 'success',
            'categories': margin_report,
            'total_categories': len(margin_report),
            'highest_margin': margin_report[0] if margin_report else None,
            'lowest_margin': margin_report[-1] if margin_report else None
        }
    
    def _categorize_card(self, card_name: str) -> str:
        """Categorize card by type (simplified heuristic)"""
        name_lower = card_name.lower()
        
        # Creature types
        creature_types = ['dragon', 'goblin', 'elf', 'knight', 'wizard', 'angel', 'demon', 'beast']
        if any(ctype in name_lower for ctype in creature_types):
            return 'Creatures'
        
        # Spell types
        if any(word in name_lower for word in ['bolt', 'shock', 'murder', 'path', 'counterspell']):
            return 'Instants/Sorceries'
        
        # Artifacts
        if any(word in name_lower for word in ['sword', 'ring', 'artifact', 'equipment']):
            return 'Artifacts'
        
        # Lands
        if any(word in name_lower for word in ['plains', 'island', 'swamp', 'mountain', 'forest', 'land']):
            return 'Lands'
        
        return 'Other'
    
    def customer_segmentation(self) -> Dict:
        """
        Segment customers by value and behavior
        
        Returns:
            Customer segments with lifetime value
        """
        customer_roi = self.library.get_customer_roi()
        
        if not customer_roi:
            return {
                'status': 'error',
                'message': 'No customer data available'
            }
        
        # Calculate customer lifetime value
        customers = []
        for customer_name, data in customer_roi.items():
            revenue = data['total_revenue']
            profit = data['total_profit']
            transaction_count = data['cards_purchased']
            
            avg_transaction = revenue / transaction_count if transaction_count > 0 else 0
            
            # Segment classification
            if revenue >= 1000 and profit >= 300:
                segment = 'VIP'
            elif revenue >= 500:
                segment = 'High Value'
            elif revenue >= 200:
                segment = 'Medium Value'
            else:
                segment = 'Low Value'
            
            customers.append({
                'customer': customer_name,
                'lifetime_value': round(revenue, 2),
                'total_profit': round(profit, 2),
                'transactions': transaction_count,
                'avg_transaction': round(avg_transaction, 2),
                'segment': segment
            })
        
        # Sort by lifetime value
        customers.sort(key=lambda x: x['lifetime_value'], reverse=True)
        
        # Count segments
        segment_counts = Counter([c['segment'] for c in customers])
        
        return {
            'status': 'success',
            'total_customers': len(customers),
            'vip_customers': segment_counts.get('VIP', 0),
            'high_value_customers': segment_counts.get('High Value', 0),
            'medium_value_customers': segment_counts.get('Medium Value', 0),
            'low_value_customers': segment_counts.get('Low Value', 0),
            'top_10_customers': customers[:10],
            'all_customers': customers
        }
    
    def abc_analysis(self) -> Dict:
        """
        ABC analysis for inventory prioritization
        A items: 80% of revenue from 20% of inventory
        B items: 15% of revenue from 30% of inventory
        C items: 5% of revenue from 50% of inventory
        
        Returns:
            ABC classification for inventory management
        """
        if not self.qb or not self.qb.sales_data:
            return {
                'status': 'error',
                'message': 'No sales data available'
            }
        
        # Calculate revenue per card
        card_revenue = defaultdict(float)
        for sale in self.qb.sales_data:
            card_name = sale.get('card_name', 'Unknown')
            card_revenue[card_name] += sale.get('total_price', 0)
        
        # Sort by revenue
        sorted_cards = sorted(card_revenue.items(), key=lambda x: x[1], reverse=True)
        total_revenue = sum(card_revenue.values())
        
        # Classify into A, B, C
        cumulative_revenue = 0
        a_items = []
        b_items = []
        c_items = []
        
        for card_name, revenue in sorted_cards:
            cumulative_revenue += revenue
            percentage = (cumulative_revenue / total_revenue) * 100
            
            if percentage <= 80:
                a_items.append({'card': card_name, 'revenue': round(revenue, 2)})
            elif percentage <= 95:
                b_items.append({'card': card_name, 'revenue': round(revenue, 2)})
            else:
                c_items.append({'card': card_name, 'revenue': round(revenue, 2)})
        
        return {
            'status': 'success',
            'total_revenue': round(total_revenue, 2),
            'a_items': {
                'count': len(a_items),
                'percentage': round(len(a_items) / len(sorted_cards) * 100, 2),
                'cards': a_items[:20]  # Top 20
            },
            'b_items': {
                'count': len(b_items),
                'percentage': round(len(b_items) / len(sorted_cards) * 100, 2),
                'cards': b_items[:10]
            },
            'c_items': {
                'count': len(c_items),
                'percentage': round(len(c_items) / len(sorted_cards) * 100, 2),
                'cards': c_items[:10]
            }
        }
    
    def generate_comprehensive_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate comprehensive business intelligence report
        
        Args:
            output_file: Path to save report (optional)
            
        Returns:
            Formatted text report
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = f"""
{'='*80}
COMPREHENSIVE BUSINESS INTELLIGENCE REPORT
Generated: {timestamp}
{'='*80}

"""
        
        # Sales Forecast
        forecast = self.sales_forecast(3)
        if forecast['status'] == 'success':
            report += f"""
📈 SALES FORECAST (Next 3 Months)
{'-'*80}
Historical Data: {forecast['historical_months']} months
Average Monthly Revenue: ${forecast['avg_monthly_revenue']:,.2f}
Average Monthly Units: {forecast['avg_monthly_units']}
Growth Rate: {forecast['growth_rate']}%

Forecasts:
"""
            for f in forecast['forecasts']:
                report += f"  {f['month']}: ${f['revenue']:,.2f} ({f['units']} units) - Confidence: {f['confidence']}\n"
        
        # Inventory Turnover
        turnover = self.inventory_turnover_analysis()
        if turnover['status'] == 'success':
            report += f"""

📦 INVENTORY TURNOVER ANALYSIS
{'-'*80}
Total Unique Cards: {turnover['total_unique_cards']}
Fast Movers: {turnover['fast_movers']}
Slow Movers: {turnover['slow_movers']}
Average Turnover Rate: {turnover['avg_turnover_rate']}

Top 5 Fast-Moving Cards:
"""
            for item in turnover['top_performers'][:5]:
                report += f"  {item['card_name']}: {item['turnover_rate']} (Sold {item['units_sold']}, Stock {item['current_stock']})\n"
            
            report += f"\nSlow-Moving Inventory (Action Needed):\n"
            for item in turnover['slow_inventory'][:5]:
                report += f"  {item['card_name']}: {item['turnover_rate']} (Stock {item['current_stock']})\n"
        
        # Profit Margins
        margins = self.profit_margin_by_category()
        if margins['status'] == 'success':
            report += f"""

💰 PROFIT MARGIN BY CATEGORY
{'-'*80}
"""
            for cat in margins['categories']:
                report += f"""
{cat['category']}:
  Revenue: ${cat['revenue']:,.2f}
  Cost: ${cat['cost']:,.2f}
  Profit: ${cat['profit']:,.2f}
  Margin: {cat['margin_percent']}%
  Units Sold: {cat['units_sold']}
"""
        
        # Customer Segmentation
        segments = self.customer_segmentation()
        if segments['status'] == 'success':
            report += f"""

👥 CUSTOMER SEGMENTATION
{'-'*80}
Total Customers: {segments['total_customers']}
VIP Customers: {segments['vip_customers']}
High Value: {segments['high_value_customers']}
Medium Value: {segments['medium_value_customers']}
Low Value: {segments['low_value_customers']}

Top 5 Customers by Lifetime Value:
"""
            for cust in segments['top_10_customers'][:5]:
                report += f"  {cust['customer']}: ${cust['lifetime_value']:,.2f} ({cust['segment']})\n"
        
        # ABC Analysis
        abc = self.abc_analysis()
        if abc['status'] == 'success':
            report += f"""

📊 ABC INVENTORY ANALYSIS
{'-'*80}
Total Revenue: ${abc['total_revenue']:,.2f}

A Items (High Priority): {abc['a_items']['count']} cards ({abc['a_items']['percentage']}% of inventory)
B Items (Medium Priority): {abc['b_items']['count']} cards ({abc['b_items']['percentage']}% of inventory)
C Items (Low Priority): {abc['c_items']['count']} cards ({abc['c_items']['percentage']}% of inventory)

Top 5 A-Class Cards:
"""
            for item in abc['a_items']['cards'][:5]:
                report += f"  {item['card']}: ${item['revenue']:,.2f}\n"
        
        report += f"\n{'='*80}\n"
        report += "END OF BUSINESS INTELLIGENCE REPORT\n"
        report += f"{'='*80}\n"
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
        
        return report
