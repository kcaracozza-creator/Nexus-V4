# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# NEXUS: Universal Collectibles Recognition and Management System
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# 
# Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.
# 
# PATENT PENDING - U.S. Provisional Application Filed November 27, 2025
# Application: 35 U.S.C. \u00a7 111(b)
# Classification: G06V 10/00, G06V 30/19, G06N 3/08, G06Q 30/02, H04N 23/00
# 
# This software is proprietary and confidential. Unauthorized copying,
# modification, distribution, or use is strictly prohibited.
# 
# See LICENSE file for full terms.
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

"""
NEXUS V2 Customer Meta Analytics
=================================
Customer profitability tracking with QuickBooks integration
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import csv
import json
from collections import defaultdict


@dataclass
class CustomerProfile:
    """Customer profile with purchase history"""
    customer_id: str
    name: str
    email: str = ""
    phone: str = ""
    total_purchases: int = 0
    total_spent: Decimal = Decimal('0.00')
    total_profit: Decimal = Decimal('0.00')
    roi_percent: float = 0.0
    first_purchase: Optional[datetime] = None
    last_purchase: Optional[datetime] = None
    favorite_formats: List[str] = field(default_factory=list)
    favorite_colors: List[str] = field(default_factory=list)
    avg_purchase_value: Decimal = Decimal('0.00')
    lifetime_value: Decimal = Decimal('0.00')
    purchase_frequency: float = 0.0  # purchases per month
    
    @property
    def customer_tier(self) -> str:
        """Calculate customer tier based on spending"""
        if self.total_spent >= 1000:
            return "Platinum"
        elif self.total_spent >= 500:
            return "Gold"
        elif self.total_spent >= 200:
            return "Silver"
        else:
            return "Bronze"
    
    @property
    def months_active(self) -> int:
        """Calculate months as active customer"""
        if not self.first_purchase or not self.last_purchase:
            return 0
        delta = self.last_purchase - self.first_purchase
        return max(1, delta.days // 30)


@dataclass
class Transaction:
    """Individual transaction record"""
    transaction_id: str
    customer_id: str
    date: datetime
    items: List[Dict]  # [{'card_name': str, 'quantity': int, 'price': Decimal}]
    total_amount: Decimal
    cost_basis: Decimal
    profit: Decimal
    payment_method: str = "cash"
    invoice_number: str = ""
    notes: str = ""


@dataclass
class QuickBooksExport:
    """QuickBooks export file metadata"""
    file_path: Path
    export_date: datetime
    export_type: str  # 'sales' or 'purchases'
    rows_imported: int = 0
    matched_transactions: int = 0
    unmatched_items: List[Dict] = field(default_factory=list)


class CustomerMetaAnalytics:
    """
    Customer analytics dashboard with QuickBooks integration
    Tracks profitability, ROI, customer tiers, and lifetime value
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize customer analytics
        
        Args:
            data_dir: Directory for storing customer data
        """
        self.data_dir = data_dir or Path("data/customers")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.customers: Dict[str, CustomerProfile] = {}
        self.transactions: List[Transaction] = []
        self.qb_imports: List[QuickBooksExport] = []
        
        # Load existing data
        self._load_customer_data()
    
    def _load_customer_data(self):
        """Load customer profiles and transactions from disk"""
        customer_file = self.data_dir / "customers.json"
        transactions_file = self.data_dir / "transactions.json"
        
        if customer_file.exists():
            try:
                with open(customer_file, 'r') as f:
                    data = json.load(f)
                    for cid, cdata in data.items():
                        self.customers[cid] = self._dict_to_customer(cdata)
            except Exception as e:
                print(f"Error loading customers: {e}")
        
        if transactions_file.exists():
            try:
                with open(transactions_file, 'r') as f:
                    data = json.load(f)
                    for tdata in data:
                        self.transactions.append(self._dict_to_transaction(tdata))
            except Exception as e:
                print(f"Error loading transactions: {e}")
    
    def _save_customer_data(self):
        """Save customer profiles and transactions to disk"""
        customer_file = self.data_dir / "customers.json"
        transactions_file = self.data_dir / "transactions.json"
        
        # Save customers