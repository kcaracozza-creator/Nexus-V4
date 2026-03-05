"""
QuickBooks CSV Integration for MTTGG Nexus Library System
Imports customer transaction data from QuickBooks exports to link with card library

Supports:
- QuickBooks Customer Sales Export (CSV)
- QuickBooks Vendor Purchases Export (CSV)
- Automatic matching to library acquisition/sales data
- ROI calculation per customer and supplier
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json


class QuickBooksIntegration:
    """
    Integrates QuickBooks export data with MTTGG library system
    Links external accounting data to card inventory transactions
    """
    
    def __init__(self, library_system=None):
        """
        Initialize QuickBooks integration
        
        Args:
            library_system: NexusLibrarySystem instance to link transactions (optional)
        """
        self.library = library_system
        self.customer_map = {}  # Maps QB customer names to standardized names
        self.vendor_map = {}    # Maps QB vendor names to standardized names
        self.import_history = []
        self.sales_data = []    # Store imported sales records
        self.purchase_data = [] # Store imported purchase records
        
    def import_customer_sales(self, csv_path: str) -> Dict:
        """
        Import customer sales data from QuickBooks CSV export
        
        Expected CSV columns:
        - Customer Name
        - Date
        - Invoice Number
        - Item (product/service description)
        - Quantity
        - Price
        - Amount
        - Payment Status
        
        Args:
            csv_path: Path to QuickBooks customer sales CSV export
            
        Returns:
            Dict with import statistics and warnings
        """
        if not os.path.exists(csv_path):
            return {"success": False, "error": f"File not found: {csv_path}"}
        
        results = {
            "success": True,
            "total_rows": 0,
            "matched_cards": 0,
            "unmatched_items": [],
            "customers_processed": set(),
            "total_revenue": 0.0,
            "import_date": datetime.now().isoformat()
        }
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    results["total_rows"] += 1
                    
                    customer = self._normalize_name(row.get('Customer Name', ''))
                    date_str = row.get('Date', '')
                    item = row.get('Item', '')
                    quantity = int(row.get('Quantity', 1))
                    price = float(row.get('Price', 0.0))
                    amount = float(row.get('Amount', 0.0))
                    
                    results["customers_processed"].add(customer)
                    results["total_revenue"] += amount
                    
                    # Try to match item to cards in library
                    matched = self._match_sale_to_library(
                        customer=customer,
                        date_str=date_str,
                        item=item,
                        quantity=quantity,
                        price=price,
                        amount=amount
                    )
                    
                    if matched:
                        results["matched_cards"] += matched
                    else:
                        results["unmatched_items"].append({
                            "customer": customer,
                            "item": item,
                            "quantity": quantity,
                            "amount": amount
                        })
            
            results["customers_processed"] = list(results["customers_processed"])
            self.import_history.append(results)
            return results
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def import_vendor_purchases(self, csv_path: str) -> Dict:
        """
        Import vendor purchase data from QuickBooks CSV export
        
        Expected CSV columns:
        - Vendor Name
        - Date
        - Bill Number / PO Number
        - Item
        - Quantity
        - Cost
        - Amount
        - Payment Status
        
        Args:
            csv_path: Path to QuickBooks vendor purchases CSV export
            
        Returns:
            Dict with import statistics
        """
        if not os.path.exists(csv_path):
            return {"success": False, "error": f"File not found: {csv_path}"}
        
        results = {
            "success": True,
            "total_rows": 0,
            "matched_cards": 0,
            "unmatched_items": [],
            "vendors_processed": set(),
            "total_cost": 0.0,
            "import_date": datetime.now().isoformat()
        }
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    results["total_rows"] += 1
                    
                    vendor = self._normalize_name(row.get('Vendor Name', ''))
                    date_str = row.get('Date', '')
                    item = row.get('Item', '')
                    quantity = int(row.get('Quantity', 1))
                    cost = float(row.get('Cost', 0.0))
                    amount = float(row.get('Amount', 0.0))
                    
                    results["vendors_processed"].add(vendor)
                    results["total_cost"] += amount
                    
                    # Try to match purchase to cards in library
                    matched = self._match_purchase_to_library(
                        vendor=vendor,
                        date_str=date_str,
                        item=item,
                        quantity=quantity,
                        cost=cost,
                        amount=amount
                    )
                    
                    if matched:
                        results["matched_cards"] += matched
                    else:
                        results["unmatched_items"].append({
                            "vendor": vendor,
                            "item": item,
                            "quantity": quantity,
                            "amount": amount
                        })
            
            results["vendors_processed"] = list(results["vendors_processed"])
            self.import_history.append(results)
            return results
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _normalize_name(self, name: str) -> str:
        """Normalize customer/vendor name for consistent matching"""
        return name.strip().title()
    
    def _match_sale_to_library(self, customer: str, date_str: str, 
                                item: str, quantity: int, 
                                price: float, amount: float) -> int:
        """
        Match QuickBooks sale to library cards and update sold_to field
        
        Returns:
            Number of cards matched
        """
        matched_count = 0
        
        # Search library for cards matching item description
        # This is fuzzy matching - could be card name in item description
        search_results = self.library.search_cards(item)
        
        if not search_results:
            return 0
        
        # Try to match by quantity and find unsold cards
        for card in search_results[:quantity]:  # Match up to quantity sold
            if card.get('status') == 'available':
                # Update card as sold to this customer
                card_name = card.get('name')
                try:
                    # Parse date from QuickBooks format (usually MM/DD/YYYY)
                    sold_date = datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                except:
                    sold_date = datetime.now().strftime('%Y-%m-%d')
                
                # Update library record using card name
                if hasattr(self.library, 'mark_card_sold'):
                    self.library.mark_card_sold(
                        card_name=card_name,
                        sold_to=customer,
                        sold_price=price
                    )
                    matched_count += 1
        
        return matched_count
    
    def _match_purchase_to_library(self, vendor: str, date_str: str,
                                    item: str, quantity: int,
                                    cost: float, amount: float) -> int:
        """
        Match QuickBooks purchase to library cards and update acquired_from field
        
        Returns:
            Number of cards matched
        """
        matched_count = 0
        
        # Search library for cards matching item description
        search_results = self.library.search_cards(item)
        
        if not search_results:
            return 0
        
        # Try to match by quantity and find cards from unknown source
        for card in search_results[:quantity]:
            if not card.get('acquired_from') or card.get('acquired_from') == 'Unknown':
                # Update card acquisition info
                call_number = card.get('call_number')
                try:
                    acquired_date = datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                except:
                    acquired_date = datetime.now().strftime('%Y-%m-%d')
                
                # Extract box ID from call number (format: AA-0234)
                box_id = call_number.split('-')[0] if '-' in call_number else 'AA'
                
                # Update library box_inventory
                if box_id in self.library.box_inventory:
                    for box_card in self.library.box_inventory[box_id]:
                        if box_card.get('call_number') == call_number:
                            box_card['acquired_from'] = vendor
                            box_card['acquired_date'] = acquired_date
                            box_card['purchase_price'] = cost
                            matched_count += 1
                            break
                
                # Save changes
                self.library._save_library()
        
        return matched_count
    
    def add_customer_mapping(self, qb_name: str, library_name: str):
        """
        Add manual mapping between QuickBooks customer name and library customer name
        Useful when names don't match exactly
        
        Args:
            qb_name: Customer name as it appears in QuickBooks
            library_name: Customer name as it appears in library system
        """
        self.customer_map[qb_name] = library_name
    
    def add_vendor_mapping(self, qb_name: str, library_name: str):
        """Add manual mapping between QuickBooks vendor name and library supplier name"""
        self.vendor_map[qb_name] = library_name
    
    def export_unmatched_report(self, output_path: str) -> bool:
        """
        Export report of unmatched items from all imports
        Helps identify what needs manual reconciliation
        
        Args:
            output_path: Path to save CSV report
            
        Returns:
            Success status
        """
        try:
            all_unmatched = []
            for import_record in self.import_history:
                if 'unmatched_items' in import_record:
                    all_unmatched.extend(import_record['unmatched_items'])
            
            if not all_unmatched:
                return True
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['customer', 'vendor', 'item', 'quantity', 'amount']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for item in all_unmatched:
                    row = {
                        'customer': item.get('customer', ''),
                        'vendor': item.get('vendor', ''),
                        'item': item.get('item', ''),
                        'quantity': item.get('quantity', 0),
                        'amount': item.get('amount', 0.0)
                    }
                    writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"Error exporting unmatched report: {e}")
            return False
    
    def get_import_summary(self) -> Dict:
        """
        Get summary of all imports performed
        
        Returns:
            Dict with total statistics
        """
        total_revenue = sum(r.get('total_revenue', 0) for r in self.import_history)
        total_cost = sum(r.get('total_cost', 0) for r in self.import_history)
        total_matched = sum(r.get('matched_cards', 0) for r in self.import_history)
        total_rows = sum(r.get('total_rows', 0) for r in self.import_history)
        
        all_customers = set()
        all_vendors = set()
        for record in self.import_history:
            all_customers.update(record.get('customers_processed', []))
            all_vendors.update(record.get('vendors_processed', []))
        
        return {
            "total_imports": len(self.import_history),
            "total_rows_processed": total_rows,
            "total_cards_matched": total_matched,
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "gross_profit": total_revenue - total_cost,
            "unique_customers": len(all_customers),
            "unique_vendors": len(all_vendors),
            "match_rate": (total_matched / total_rows * 100) if total_rows > 0 else 0
        }
