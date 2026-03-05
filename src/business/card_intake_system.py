#!/usr/bin/env python3
"""
Nexus Card Intake System
Handles incoming cards: bulk purchases, trades, donations, etc.
Tracks source, condition, pricing, and library cataloging
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict


class CardIntakeSystem:
    """
    Manages card intake/acquisition workflow
    
    Tracks:
    - Source (purchase, trade, donation, etc.)
    - Condition (NM, LP, MP, HP, DMG)
    - Purchase price & market value
    - Intake date/time
    - Batch information
    - Library assignment
    """
    
    CONDITION_GRADES = {
        'NM': 'Near Mint',
        'LP': 'Lightly Played',
        'MP': 'Moderately Played',
        'HP': 'Heavily Played',
        'DMG': 'Damaged'
    }
    
    CONDITION_MULTIPLIERS = {
        'NM': 1.0,      # 100% market value
        'LP': 0.85,     # 85% market value
        'MP': 0.65,     # 65% market value
        'HP': 0.40,     # 40% market value
        'DMG': 0.25     # 25% market value
    }
    
    INTAKE_SOURCES = [
        'Bulk Purchase',
        'Customer Trade-in',
        'Donation',
        'Estate Sale',
        'Online Purchase',
        'Collection Buy',
        'Store Credit Trade',
        'Consignment'
    ]
    
    def __init__(self, intake_file: str = "E:/MTTGG/card_intake_log.json"):
        """
        Initialize intake system
        
        Args:
            intake_file: Path to intake log JSON
        """
        self.intake_file = intake_file
        self.intake_log = []
        self.current_batch = None
        self.batch_counter = 0
        
        self._load_intake_log()
        print(f"[INTAKE] Card Intake System initialized")
        print(f"[INTAKE] Total intake records: {len(self.intake_log)}")
    
    def _load_intake_log(self):
        """Load intake log from JSON"""
        if os.path.exists(self.intake_file):
            try:
                with open(self.intake_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.intake_log = data.get('intake_log', [])
                    self.batch_counter = data.get('batch_counter', 0)
                
                print(f"[INTAKE] Loaded from {self.intake_file}")
            except Exception as e:
                print(f"[WARNING] Could not load intake log: {e}")
                self.intake_log = []
                self.batch_counter = 0
        else:
            print(f"[INTAKE] Creating new intake log")
            self._save_intake_log()
    
    def _save_intake_log(self):
        """Save intake log to JSON"""
        try:
            data = {
                'intake_log': self.intake_log,
                'batch_counter': self.batch_counter,
                'last_updated': datetime.now().isoformat(),
                'total_cards_processed': len(self.intake_log),
            }
            
            with open(self.intake_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"[INTAKE] Saved to {self.intake_file}")
        except Exception as e:
            print(f"[ERROR] Failed to save intake log: {e}")
    
    def start_batch(self, source: str, supplier: str = "", 
                   total_cost: float = 0.0, notes: str = "") -> str:
        """
        Start new intake batch
        
        Args:
            source: Intake source (e.g., "Bulk Purchase")
            supplier: Supplier name/info
            total_cost: Total amount paid for batch
            notes: Additional notes
        
        Returns:
            Batch ID
        """
        self.batch_counter += 1
        batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{self.batch_counter:04d}"
        
        self.current_batch = {
            'batch_id': batch_id,
            'source': source,
            'supplier': supplier,
            'total_cost': total_cost,
            'notes': notes,
            'start_time': datetime.now().isoformat(),
            'cards': [],
            'status': 'in_progress'
        }
        
        print(f"[INTAKE] Started batch: {batch_id}")
        print(f"[INTAKE] Source: {source}")
        if supplier:
            print(f"[INTAKE] Supplier: {supplier}")
        if total_cost > 0:
            print(f"[INTAKE] Total cost: ${total_cost:.2f}")
        
        return batch_id
    
    def add_card_to_batch(self, card_data: Dict) -> Dict:
        """
        Add card to current batch
        
        Args:
            card_data: Dict with card info
                Required: 'name'
                Optional: 'condition', 'foil', 'quantity', 'purchase_price', 
                         'market_value', 'set', 'language', 'signed', 'altered'
        
        Returns:
            Complete intake record
        """
        if not self.current_batch:
            raise ValueError("No active batch. Call start_batch() first.")
        
        card_name = card_data.get('name', 'Unknown')
        condition = card_data.get('condition', 'NM')
        quantity = card_data.get('quantity', 1)
        foil = card_data.get('foil', False)
        
        # Calculate pricing
        market_value = card_data.get('market_value', 0.0)
        purchase_price = card_data.get('purchase_price', 0.0)
        
        # Apply condition multiplier to market value
        condition_multiplier = self.CONDITION_MULTIPLIERS.get(condition, 1.0)
        adjusted_value = market_value * condition_multiplier
        
        # Calculate profit potential
        profit_potential = (adjusted_value - purchase_price) if purchase_price > 0 else 0.0
        profit_margin = ((profit_potential / purchase_price) * 100) if purchase_price > 0 else 0.0
        
        intake_record = {
            'name': card_name,
            'condition': condition,
            'condition_grade': self.CONDITION_GRADES.get(condition, 'Unknown'),
            'quantity': quantity,
            'foil': foil,
            'set': card_data.get('set', ''),
            'language': card_data.get('language', 'English'),
            'signed': card_data.get('signed', False),
            'altered': card_data.get('altered', False),
            'purchase_price': purchase_price,
            'market_value': market_value,
            'adjusted_value': adjusted_value,
            'condition_multiplier': condition_multiplier,
            'profit_potential': profit_potential,
            'profit_margin': profit_margin,
            'intake_timestamp': datetime.now().isoformat(),
            'batch_id': self.current_batch['batch_id'],
            'call_number': card_data.get('call_number'),  # From library system
            'notes': card_data.get('notes', '')
        }
        
        self.current_batch['cards'].append(intake_record)
        
        print(f"[INTAKE] Added: {card_name} ({condition}) x{quantity}")
        if purchase_price > 0:
            print(f"[INTAKE]   Cost: ${purchase_price:.2f} | Value: ${adjusted_value:.2f} | Profit: ${profit_potential:.2f} ({profit_margin:.1f}%)")
        
        return intake_record
    
    def complete_batch(self) -> Dict:
        """
        Complete current batch and save to log
        
        Returns:
            Batch summary
        """
        if not self.current_batch:
            raise ValueError("No active batch to complete.")
        
        # Calculate batch totals
        total_cards = sum(card['quantity'] for card in self.current_batch['cards'])
        total_purchase = sum(card['purchase_price'] * card['quantity'] 
                           for card in self.current_batch['cards'])
        total_market_value = sum(card['market_value'] * card['quantity'] 
                                for card in self.current_batch['cards'])
        total_adjusted_value = sum(card['adjusted_value'] * card['quantity'] 
                                  for card in self.current_batch['cards'])
        total_profit_potential = total_adjusted_value - total_purchase
        
        # Update batch
        self.current_batch['end_time'] = datetime.now().isoformat()
        self.current_batch['status'] = 'completed'
        self.current_batch['summary'] = {
            'total_cards': total_cards,
            'unique_cards': len(self.current_batch['cards']),
            'total_purchase_cost': total_purchase,
            'total_market_value': total_market_value,
            'total_adjusted_value': total_adjusted_value,
            'total_profit_potential': total_profit_potential,
            'profit_margin': ((total_profit_potential / total_purchase) * 100) if total_purchase > 0 else 0.0
        }
        
        # Condition breakdown
        condition_counts = defaultdict(int)
        for card in self.current_batch['cards']:
            condition_counts[card['condition']] += card['quantity']
        self.current_batch['summary']['by_condition'] = dict(condition_counts)
        
        # Add to log
        self.intake_log.append(self.current_batch)
        
        # Save
        self._save_intake_log()
        
        summary = self.current_batch['summary']
        
        print(f"\n[INTAKE] ✅ Batch completed: {self.current_batch['batch_id']}")
        print(f"[INTAKE] Total cards: {summary['total_cards']} ({summary['unique_cards']} unique)")
        print(f"[INTAKE] Purchase cost: ${summary['total_purchase_cost']:.2f}")
        print(f"[INTAKE] Adjusted value: ${summary['total_adjusted_value']:.2f}")
        print(f"[INTAKE] Profit potential: ${summary['total_profit_potential']:.2f} ({summary['profit_margin']:.1f}%)")
        
        # Clear current batch
        completed_batch = self.current_batch
        self.current_batch = None
        
        return completed_batch
    
    def cancel_batch(self):
        """Cancel current batch without saving"""
        if self.current_batch:
            print(f"[INTAKE] Cancelled batch: {self.current_batch['batch_id']}")
            self.current_batch = None
        else:
            print("[INTAKE] No active batch to cancel")
    
    def get_batch_summary(self, batch_id: str) -> Optional[Dict]:
        """Get summary for specific batch"""
        for batch in self.intake_log:
            if batch['batch_id'] == batch_id:
                return batch
        return None
    
    def get_recent_batches(self, limit: int = 10) -> List[Dict]:
        """Get most recent batches"""
        return sorted(self.intake_log, 
                     key=lambda x: x.get('start_time', ''), 
                     reverse=True)[:limit]
    
    def get_intake_statistics(self, days: int = 30) -> Dict:
        """Get intake statistics for last N days"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_batches = [
            b for b in self.intake_log 
            if datetime.fromisoformat(b.get('start_time', '')) > cutoff_date
        ]
        
        if not recent_batches:
            return {
                'days': days,
                'total_batches': 0,
                'total_cards': 0,
                'total_spent': 0.0,
                'total_value': 0.0
            }
        
        total_cards = sum(b['summary']['total_cards'] for b in recent_batches)
        total_spent = sum(b['summary']['total_purchase_cost'] for b in recent_batches)
        total_value = sum(b['summary']['total_adjusted_value'] for b in recent_batches)
        
        # Source breakdown
        by_source = defaultdict(lambda: {'batches': 0, 'cards': 0, 'spent': 0.0})
        for batch in recent_batches:
            source = batch['source']
            by_source[source]['batches'] += 1
            by_source[source]['cards'] += batch['summary']['total_cards']
            by_source[source]['spent'] += batch['summary']['total_purchase_cost']
        
        return {
            'days': days,
            'total_batches': len(recent_batches),
            'total_cards': total_cards,
            'total_spent': total_spent,
            'total_value': total_value,
            'total_profit_potential': total_value - total_spent,
            'avg_profit_margin': ((total_value - total_spent) / total_spent * 100) if total_spent > 0 else 0.0,
            'by_source': dict(by_source)
        }
    
    def export_batch_receipt(self, batch_id: str, output_file: str):
        """Export batch as printable receipt"""
        batch = self.get_batch_summary(batch_id)
        if not batch:
            print(f"[ERROR] Batch not found: {batch_id}")
            return
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(" " * 25 + "NEXUS CARD INTAKE RECEIPT\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Batch ID: {batch['batch_id']}\n")
            f.write(f"Source: {batch['source']}\n")
            if batch.get('supplier'):
                f.write(f"Supplier: {batch['supplier']}\n")
            f.write(f"Date: {batch['start_time'][:10]}\n")
            f.write(f"Time: {batch['start_time'][11:19]}\n\n")
            
            f.write("-" * 80 + "\n")
            f.write(f"{'Card Name':<40} {'Qty':>4} {'Cond':>4} {'Cost':>10} {'Value':>10}\n")
            f.write("-" * 80 + "\n")
            
            for card in batch['cards']:
                name = card['name'][:39]
                qty = card['quantity']
                cond = card['condition']
                cost = card['purchase_price'] * qty
                value = card['adjusted_value'] * qty
                
                f.write(f"{name:<40} {qty:>4} {cond:>4} ${cost:>9.2f} ${value:>9.2f}\n")
            
            f.write("-" * 80 + "\n")
            
            summary = batch['summary']
            f.write(f"{'TOTAL:':<40} {summary['total_cards']:>4}      ${summary['total_purchase_cost']:>9.2f} ${summary['total_adjusted_value']:>9.2f}\n")
            f.write("\n")
            f.write(f"Profit Potential: ${summary['total_profit_potential']:.2f} ({summary['profit_margin']:.1f}%)\n")
            
            f.write("\n" + "=" * 80 + "\n")
        
        print(f"[INTAKE] Receipt saved to: {output_file}")


def demonstrate_intake_system():
    """Demonstrate intake system"""
    print("\n=== NEXUS CARD INTAKE SYSTEM DEMO ===\n")
    
    intake = CardIntakeSystem()
    
    # Start a batch
    batch_id = intake.start_batch(
        source="Bulk Purchase",
        supplier="Local Game Store Buyout",
        total_cost=250.00,
        notes="Store closing sale - good mix of modern staples"
    )
    
    print("\nAdding cards to batch:\n")
    
    # Add some cards
    test_cards = [
        {
            'name': 'Lightning Bolt',
            'condition': 'NM',
            'quantity': 4,
            'purchase_price': 2.00,
            'market_value': 3.50,
            'set': 'M11'
        },
        {
            'name': 'Counterspell',
            'condition': 'LP',
            'quantity': 3,
            'purchase_price': 1.50,
            'market_value': 2.25,
            'set': '7ED'
        },
        {
            'name': 'Black Lotus',
            'condition': 'MP',
            'quantity': 1,
            'purchase_price': 15000.00,
            'market_value': 30000.00,
            'set': 'LEA',
            'notes': 'Graded, certified authentic'
        }
    ]
    
    for card in test_cards:
        intake.add_card_to_batch(card)
    
    print("\n" + "=" * 80 + "\n")
    
    # Complete batch
    completed = intake.complete_batch()
    
    print("\n" + "=" * 80 + "\n")
    
    # Get statistics
    stats = intake.get_intake_statistics(days=30)
    print("\n30-Day Intake Statistics:")
    print(f"  Batches: {stats['total_batches']}")
    print(f"  Cards: {stats['total_cards']}")
    print(f"  Spent: ${stats['total_spent']:.2f}")
    print(f"  Value: ${stats['total_value']:.2f}")
    print(f"  Profit Potential: ${stats['total_profit_potential']:.2f} ({stats['avg_profit_margin']:.1f}%)")
    
    print("\n✅ Intake system demonstration complete!")


if __name__ == "__main__":
    demonstrate_intake_system()
