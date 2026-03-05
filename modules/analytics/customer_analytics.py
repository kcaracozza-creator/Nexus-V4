"""
Customer Analytics Dashboard for MTTGG Nexus Library System
Generates comprehensive profit and ROI reports for business intelligence

Features:
- Customer profitability rankings
- Supplier ROI analysis
- Overall profit/loss statements
- Export to CSV for accounting
- QuickBooks integration support
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
import json


class CustomerAnalytics:
    """
    Analytics dashboard for customer and supplier profitability
    Integrates with NexusLibrarySystem and QuickBooksIntegration
    """
    
    def __init__(self, library_system):
        """
        Initialize analytics dashboard
        
        Args:
            library_system: NexusLibrarySystem instance
        """
        self.library = library_system
        self.reports_dir = "E:/MTTGG/REPORTS"
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_customer_profit_report(self, output_csv: Optional[str] = None) -> str:
        """
        Generate detailed customer profitability report
        
        Args:
            output_csv: Path to save CSV report (optional)
            
        Returns:
            Formatted text report
        """
        customer_data = self.library.get_profit_by_customer()
        
        if output_csv:
            self._export_customer_csv(customer_data, output_csv)
        
        # Generate text report
        report = []
        report.append("=" * 80)
        report.append("CUSTOMER PROFITABILITY REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("=" * 80)
        report.append("")
        
        if not customer_data:
            report.append("No customer sales data found.")
            return "\n".join(report)
        
        # Summary statistics
        total_customers = len(customer_data)
        total_revenue = sum(c['total_revenue'] for c in customer_data)
        total_profit = sum(c['profit'] for c in customer_data)
        avg_roi = sum(c['roi_percent'] for c in customer_data) / total_customers
        
        report.append(f"Total Customers: {total_customers}")
        report.append(f"Total Revenue: ${total_revenue:,.2f}")
        report.append(f"Total Profit: ${total_profit:,.2f}")
        report.append(f"Average ROI: {avg_roi:.1f}%")
        report.append("")
        report.append("-" * 80)
        report.append("")
        
        # Individual customer breakdown
        report.append(f"{'Customer':<25} {'Cards':<8} {'Revenue':<12} {'Profit':<12} {'ROI':<8}")
        report.append("-" * 80)
        
        for customer in customer_data:
            name = customer['customer'][:24]  # Truncate long names
            cards = customer['cards_sold']
            revenue = customer['total_revenue']
            profit = customer['profit']
            roi = customer['roi_percent']
            
            # Color code profit
            profit_str = f"${profit:,.2f}"
            if profit < 0:
                profit_str = f"-${abs(profit):,.2f}"
            
            report.append(
                f"{name:<25} {cards:<8} ${revenue:>10,.2f} {profit_str:>11} {roi:>6.1f}%"
            )
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def generate_supplier_roi_report(self, output_csv: Optional[str] = None) -> str:
        """
        Generate supplier ROI and profitability report
        
        Args:
            output_csv: Path to save CSV report (optional)
            
        Returns:
            Formatted text report
        """
        supplier_data = self.library.get_profit_by_supplier()
        
        if output_csv:
            self._export_supplier_csv(supplier_data, output_csv)
        
        # Generate text report
        report = []
        report.append("=" * 90)
        report.append("SUPPLIER ROI ANALYSIS")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("=" * 90)
        report.append("")
        
        if not supplier_data:
            report.append("No supplier acquisition data found.")
            return "\n".join(report)
        
        # Summary statistics
        total_suppliers = len(supplier_data)
        total_cost = sum(s['total_cost'] for s in supplier_data)
        total_realized = sum(s['profit_realized'] for s in supplier_data)
        total_potential = sum(s['profit_potential'] for s in supplier_data)
        
        report.append(f"Total Suppliers: {total_suppliers}")
        report.append(f"Total Investment: ${total_cost:,.2f}")
        report.append(f"Profit Realized: ${total_realized:,.2f}")
        report.append(f"Potential Profit: ${total_potential:,.2f}")
        report.append("")
        report.append("-" * 90)
        report.append("")
        
        # Individual supplier breakdown
        header = (
            f"{'Supplier':<20} {'Acquired':<9} {'Sold':<6} {'Stock':<6} "
            f"{'Cost':<12} {'Realized':<10} {'ROI':<8}"
        )
        report.append(header)
        report.append("-" * 90)
        
        for supplier in supplier_data:
            name = supplier['supplier'][:19]
            acquired = supplier['cards_acquired']
            sold = supplier['cards_sold']
            stock = supplier['cards_in_stock']
            cost = supplier['total_cost']
            profit = supplier['profit_realized']
            roi = supplier['roi_realized_percent']
            
            profit_str = f"${profit:,.2f}"
            if profit < 0:
                profit_str = f"-${abs(profit):,.2f}"
            
            line = (
                f"{name:<20} {acquired:<9} {sold:<6} {stock:<6} "
                f"${cost:>10,.2f} {profit_str:>9} {roi:>6.1f}%"
            )
            report.append(line)
        
        report.append("")
        report.append("=" * 90)
        
        return "\n".join(report)
    
    def generate_overall_summary(self, output_csv: Optional[str] = None) -> str:
        """
        Generate overall business summary with all key metrics
        
        Args:
            output_csv: Path to save CSV summary (optional)
            
        Returns:
            Formatted text report
        """
        summary = self.library.get_overall_profit_summary()
        
        # Generate text report
        report = []
        report.append("=" * 80)
        report.append("OVERALL BUSINESS SUMMARY")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("=" * 80)
        report.append("")
        
        # Inventory Overview
        report.append("INVENTORY OVERVIEW")
        report.append("-" * 80)
        report.append(f"Total Cards Acquired: {summary['total_cards_acquired']:,}")
        report.append(f"Cards Sold: {summary['cards_sold']:,}")
        report.append(f"Cards Available: {summary['cards_available']:,}")
        report.append(f"Sell-Through Rate: {summary['sell_through_rate']:.1f}%")
        report.append("")
        
        # Financial Summary
        report.append("FINANCIAL SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Investment (Cost): ${summary['total_cost']:,.2f}")
        report.append(f"Total Revenue (Sales): ${summary['total_revenue']:,.2f}")
        report.append(f"Current Stock Value: ${summary['stock_value']:,.2f}")
        report.append(f"Realized Profit: ${summary['profit_realized']:,.2f}")
        report.append(f"Realized ROI: {summary['roi_realized_percent']:.1f}%")
        report.append("")
        
        # Top Customers
        report.append("TOP 5 CUSTOMERS BY PROFIT")
        report.append("-" * 80)
        if summary['top_customers']:
            for i, customer in enumerate(summary['top_customers'], 1):
                report.append(
                    f"{i}. {customer['customer']:<30} "
                    f"${customer['profit']:>10,.2f} "
                    f"({customer['roi_percent']:.1f}% ROI)"
                )
        else:
            report.append("No customer data available")
        report.append("")
        
        # Top Suppliers
        report.append("TOP 5 SUPPLIERS BY ROI")
        report.append("-" * 80)
        if summary['top_suppliers']:
            for i, supplier in enumerate(summary['top_suppliers'], 1):
                report.append(
                    f"{i}. {supplier['supplier']:<30} "
                    f"{supplier['roi_realized_percent']:>6.1f}% ROI "
                    f"(${supplier['profit_realized']:,.2f} profit)"
                )
        else:
            report.append("No supplier data available")
        report.append("")
        
        report.append("=" * 80)
        
        # Export to CSV if requested
        if output_csv:
            self._export_overall_csv(summary, output_csv)
        
        return "\n".join(report)
    
    def export_quickbooks_reconciliation(self, qb_integration, output_path: str):
        """
        Export reconciliation report for QuickBooks import
        Compares library data with QuickBooks imports
        
        Args:
            qb_integration: QuickBooksIntegration instance
            output_path: Path to save reconciliation report
        """
        qb_summary = qb_integration.get_import_summary()
        library_summary = self.library.get_overall_profit_summary()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("QUICKBOOKS RECONCILIATION REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("QUICKBOOKS DATA\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Imports: {qb_summary['total_imports']}\n")
            f.write(f"Rows Processed: {qb_summary['total_rows_processed']}\n")
            f.write(f"Cards Matched: {qb_summary['total_cards_matched']}\n")
            f.write(f"Match Rate: {qb_summary['match_rate']:.1f}%\n")
            f.write(f"QB Revenue: ${qb_summary['total_revenue']:,.2f}\n")
            f.write(f"QB Cost: ${qb_summary['total_cost']:,.2f}\n")
            f.write(f"QB Gross Profit: ${qb_summary['gross_profit']:,.2f}\n\n")
            
            f.write("LIBRARY SYSTEM DATA\n")
            f.write("-" * 80 + "\n")
            f.write(f"Cards Sold: {library_summary['cards_sold']}\n")
            f.write(f"Library Revenue: ${library_summary['total_revenue']:,.2f}\n")
            f.write(f"Library Cost: ${library_summary['total_cost']:,.2f}\n")
            f.write(f"Library Profit: ${library_summary['profit_realized']:,.2f}\n\n")
            
            f.write("VARIANCE ANALYSIS\n")
            f.write("-" * 80 + "\n")
            revenue_diff = library_summary['total_revenue'] - qb_summary['total_revenue']
            cost_diff = library_summary['total_cost'] - qb_summary['total_cost']
            profit_diff = library_summary['profit_realized'] - qb_summary['gross_profit']
            
            f.write(f"Revenue Variance: ${revenue_diff:,.2f}\n")
            f.write(f"Cost Variance: ${cost_diff:,.2f}\n")
            f.write(f"Profit Variance: ${profit_diff:,.2f}\n\n")
            
            if abs(revenue_diff) > 10 or abs(cost_diff) > 10:
                f.write("⚠️ VARIANCE DETECTED - Manual reconciliation recommended\n")
            else:
                f.write("✅ Data aligned within acceptable variance\n")
    
    def _export_customer_csv(self, customer_data: List[Dict], output_path: str):
        """Export customer profitability to CSV"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'customer', 'cards_sold', 'total_revenue', 'total_cost',
                'profit', 'roi_percent', 'avg_profit_per_card'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(customer_data)
    
    def _export_supplier_csv(self, supplier_data: List[Dict], output_path: str):
        """Export supplier ROI to CSV"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'supplier', 'cards_acquired', 'cards_sold', 'cards_in_stock',
                'total_cost', 'revenue_realized', 'stock_value',
                'profit_realized', 'profit_potential',
                'roi_realized_percent', 'roi_potential_percent'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(supplier_data)
    
    def _export_overall_csv(self, summary: Dict, output_path: str):
        """Export overall summary to CSV"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Cards Acquired', summary['total_cards_acquired']])
            writer.writerow(['Cards Sold', summary['cards_sold']])
            writer.writerow(['Cards Available', summary['cards_available']])
            writer.writerow(['Sell-Through Rate %', f"{summary['sell_through_rate']:.1f}"])
            writer.writerow(['Total Cost', f"${summary['total_cost']:,.2f}"])
            writer.writerow(['Total Revenue', f"${summary['total_revenue']:,.2f}"])
            writer.writerow(['Stock Value', f"${summary['stock_value']:,.2f}"])
            writer.writerow(['Realized Profit', f"${summary['profit_realized']:,.2f}"])
            writer.writerow(['Realized ROI %', f"{summary['roi_realized_percent']:.1f}"])
    
    def print_customer_report(self):
        """Print customer profitability report to console"""
        report = self.generate_customer_profit_report()
        print(report)
    
    def print_supplier_report(self):
        """Print supplier ROI report to console"""
        report = self.generate_supplier_roi_report()
        print(report)
    
    def print_overall_summary(self):
        """Print overall business summary to console"""
        report = self.generate_overall_summary()
        print(report)
    
    def save_all_reports(self, prefix: str = ""):
        """
        Save all reports to files
        
        Args:
            prefix: Optional prefix for filenames
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"{prefix}_{timestamp}" if prefix else timestamp
        
        # Customer report
        customer_txt = os.path.join(self.reports_dir, f"{base_name}_customers.txt")
        customer_csv = os.path.join(self.reports_dir, f"{base_name}_customers.csv")
        with open(customer_txt, 'w', encoding='utf-8') as f:
            f.write(self.generate_customer_profit_report(customer_csv))
        
        # Supplier report
        supplier_txt = os.path.join(self.reports_dir, f"{base_name}_suppliers.txt")
        supplier_csv = os.path.join(self.reports_dir, f"{base_name}_suppliers.csv")
        with open(supplier_txt, 'w', encoding='utf-8') as f:
            f.write(self.generate_supplier_roi_report(supplier_csv))
        
        # Overall summary
        summary_txt = os.path.join(self.reports_dir, f"{base_name}_summary.txt")
        summary_csv = os.path.join(self.reports_dir, f"{base_name}_summary.csv")
        with open(summary_txt, 'w', encoding='utf-8') as f:
            f.write(self.generate_overall_summary(summary_csv))
        
        print(f"\n[REPORTS] Saved to {self.reports_dir}")
        print(f"  - {base_name}_customers.txt/.csv")
        print(f"  - {base_name}_suppliers.txt/.csv")
        print(f"  - {base_name}_summary.txt/.csv")
        
        return {
            'customer_txt': customer_txt,
            'customer_csv': customer_csv,
            'supplier_txt': supplier_txt,
            'supplier_csv': supplier_csv,
            'summary_txt': summary_txt,
            'summary_csv': summary_csv
        }


def demo_analytics():
    """Demonstrate customer analytics system"""
    from nexus_library_system import NexusLibrarySystem
    
    print("\n=== CUSTOMER ANALYTICS DEMO ===\n")
    
    library = NexusLibrarySystem()
    analytics = CustomerAnalytics(library)
    
    # Add some test data
    library.start_new_box("AA")
    
    # Simulate acquisitions and sales
    test_cards = [
        {
            'name': 'Lightning Bolt',
            'acquired_from': 'John Doe',
            'purchase_price': 5.0,
            'market_value': 10.0,
            'sold_to': 'Sarah Smith',
            'sold_price': 12.0,
            'status': 'sold'
        },
        {
            'name': 'Black Lotus',
            'acquired_from': 'John Doe',
            'purchase_price': 1000.0,
            'market_value': 20000.0,
            'status': 'available'
        }
    ]
    
    for card in test_cards:
        library.catalog_card(card)
    
    print("\n" + "=" * 80)
    analytics.print_overall_summary()
    print("\n" + "=" * 80)
    analytics.print_customer_report()
    print("\n" + "=" * 80)
    analytics.print_supplier_report()


if __name__ == "__main__":
    demo_analytics()
