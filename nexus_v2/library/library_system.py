"""
NEXUS Library System - PRICING INTEGRATION FIXED
================================================
Clouse Fix Date: December 1, 2025

CHANGES MADE:
1. Line 71: Fixed library=self.library → library=self
2. Added proper pricing method wrappers
3. Fixed data structure access (box_inventory not library)
4. Added bulk update support

INTEGRATION INSTRUCTIONS:
1. Replace your nexus_library_system.py with this file
2. Ensure auto_pricing_engine.py is in same directory
3. Restart NEXUS

"""

import json
import os
import requests
from datetime import datetime
from pathlib import Path

# ============================================================
# SQLITE DATABASE IMPORT (PERFORMANCE UPGRADE)
# ============================================================
try:
    from .library_db import LibraryDB
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

# ============================================================
# PRICING ENGINE IMPORT (FIXED)
# ============================================================
try:
    from .auto_pricing_engine import AutoPricingEngine
    PRICING_AVAILABLE = True
    print("[OK] Pricing engine loaded successfully")
except ImportError as e:
    PRICING_AVAILABLE = False
    print(f"[WARN] Pricing engine not available: {e}")
    print("   Price tracking features will be disabled")


class NexusLibrarySystem:
    """
    Main library system for NEXUS card management.
    Handles cataloging, storage, and pricing.
    """

    def __len__(self):
        """Return total card count for len() support."""
        if hasattr(self, 'db') and self.db:
            return self.db.count()
        if hasattr(self, 'box_inventory'):
            return sum(len(cards) for cards in self.box_inventory.values())
        return 0

    def __init__(self, data_dir=None, remote_url=None):
        """Initialize the library system.

        Args:
            data_dir: Local directory containing nexus_library.json
            remote_url: URL to fetch library from (e.g., http://192.168.1.219:5001/api/library)
        """
        self.remote_url = remote_url

        # Set data directory
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # Default to nexus_v2/data/ directory (not library module directory)
            self.data_dir = Path(__file__).parent.parent / "data"

        # Core data structures
        self.box_inventory = {}      # box_name → [list of card dicts]
        self.card_locations = {}     # call_number → card_name
        self.statistics = {}         # various stats
        self.current_box = None
        self.box_counter = {}        # box_name → next card number
        
        # File paths
        self.library_file = self.data_dir / "nexus_library.json"
        self.library_db_file = self.data_dir / "nexus_library.db"
        self.backup_dir = self.data_dir / "backups"

        # SQLite database (if available)
        self.db = None
        if SQLITE_AVAILABLE and self.library_db_file.exists():
            try:
                self.db = LibraryDB(self.library_db_file)
                print(f"[OK] SQLite database loaded: {self.db.count()} cards")
            except Exception as e:
                print(f"[WARN] SQLite load failed, using JSON: {e}")
                self.db = None

        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)
        
        # ============================================================
        # PRICING ENGINE INITIALIZATION (FIXED - Line 71)
        # ============================================================
        # CRITICAL FIX: Pass 'self' not 'self.library'
        # The NexusLibrarySystem IS the library, there's no self.library attribute
        self.pricing_engine = None
        if PRICING_AVAILABLE:
            try:
                self.pricing_engine = AutoPricingEngine(
                    data_dir=str(self.data_dir),
                    library=self  # ← FIXED: Was self.library (undefined)
                )
                print(f"[OK] Pricing engine initialized")
                print(f"   Cache: {len(self.pricing_engine.price_cache)} prices")
                print(f"   History: {len(self.pricing_engine.price_history)} cards tracked")
            except Exception as e:
                print(f"[WARN] Pricing engine init failed: {e}")
                self.pricing_engine = None
        
        # Load existing library
        self._load_library()

        # Update statistics
        self._update_statistics()

        # Start automatic price updates every 3 hours
        if self.pricing_engine:
            try:
                self.pricing_engine.start_background_updates(interval_hours=3)
                print("[OK] Auto price updates enabled (every 3 hours)")
            except Exception as e:
                print(f"[WARN] Could not start auto price updates: {e}")
    
    def _load_library(self):
        """Load library from SQLite, remote URL, or local JSON file."""
        # If SQLite is loaded and has data, it's the source of truth - skip JSON/remote
        if self.db and self.db.count() > 0:
            count = self.db.count()
            print(f"[OK] Library loaded from SQLite: {count} cards")
            return

        data = None

        # Try remote URL (Brock HDD) - only if no SQLite data
        if self.remote_url:
            try:
                print(f"[INFO] Fetching library from {self.remote_url}...")
                response = requests.get(self.remote_url, timeout=5)
                response.raise_for_status()
                data = response.json()
                print(f"[OK] Library fetched from remote ({len(response.content)//1024}KB)")
            except Exception as e:
                print(f"[WARN] Remote fetch failed: {e}, trying local file...")

        # Fall back to local file
        if data is None:
            if not self.library_file.exists():
                print(f"No library file found at {self.library_file}")
                return
            try:
                with open(self.library_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[ERROR] Failed to load local library: {e}")
                return

        try:
            
            self.box_inventory = data.get('box_inventory', {})
            self.card_locations = data.get('card_locations', {})
            self.statistics = data.get('statistics', {})
            self.box_counter = data.get('box_counter', {})
            
            # ============================================================
            # ACTUAL DATA FORMAT: {"library": {"AA-0001": {card}, ...}}
            # Convert to box_inventory format
            # ============================================================
            if not self.box_inventory and 'library' in data:
                print(f"[INFO] Converting library format to box_inventory...")
                library_data = data['library']
                
                for call_number, card_data in library_data.items():
                    if isinstance(card_data, dict):
                        box_id = card_data.get('box_id') or call_number.split('-')[0]
                        if box_id not in self.box_inventory:
                            self.box_inventory[box_id] = []
                        self.box_inventory[box_id].append(card_data)
                
                print(f"[OK] Converted {len(library_data)} cards into {len(self.box_inventory)} boxes")
            
            # ============================================================
            # LINE 64 FIX: Rebuild box_inventory from card_locations
            # ============================================================
            # Use card_locations when it has more data than box_inventory
            box_total = sum(len(c) for c in self.box_inventory.values()) if self.box_inventory else 0
            if self.card_locations and len(self.card_locations) > box_total:
                print(f"[INFO] Rebuilding box_inventory from {len(self.card_locations)} card locations...")
                
                # Check data structure: card_locations can be:
                # 1. OLD FORMAT: {"AA-0001": "Card Name", "AA-0002": "Card Name"}
                # 2. NEW FORMAT: {"Card Name": ["AA-0001", "AA-0002", "AA-0003"]}
                
                first_key = next(iter(self.card_locations))
                first_value = self.card_locations[first_key]
                
                if isinstance(first_value, list):
                    # NEW FORMAT: Card name -> list of call numbers
                    print("[INFO] Detected NEW format (card_name: [locations])")
                    for card_name, locations in self.card_locations.items():
                        for call_number in locations:
                            box_id = call_number.split('-')[0] if '-' in call_number else 'AA'
                            card_dict = {
                                'name': card_name,
                                'call_number': call_number,
                                'set': '???',
                                'foil': False
                            }
                            if box_id not in self.box_inventory:
                                self.box_inventory[box_id] = []
                            self.box_inventory[box_id].append(card_dict)
                else:
                    # OLD FORMAT: Call number -> card name
                    print("[INFO] Detected OLD format (call_number: card_name)")
                    for call_number, card_name in self.card_locations.items():
                        box_id = call_number.split('-')[0] if '-' in call_number else 'AA'
                        card_dict = {
                            'name': card_name,
                            'call_number': call_number,
                            'set': '???',
                            'foil': False
                        }
                        if box_id not in self.box_inventory:
                            self.box_inventory[box_id] = []
                        self.box_inventory[box_id].append(card_dict)
                
                print(f"[OK] Rebuilt {len(self.box_inventory)} boxes from card locations")
            
            # Count what we loaded
            total_cards = sum(len(cards) for cards in self.box_inventory.values())
            print(f"[OK] Library loaded: {total_cards} cards in {len(self.box_inventory)} boxes")
            
        except Exception as e:
            print(f"[ERROR] Error loading library: {e}")
    
    def _save_library(self):
        """Save library to JSON file."""
        try:
            data = {
                'box_inventory': self.box_inventory,
                'card_locations': self.card_locations,
                'statistics': self.statistics,
                'box_counter': self.box_counter,
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.library_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"[ERROR] Error saving library: {e}")
            return False
    
    def _update_statistics(self):
        """Update library statistics."""
        total_cards = sum(len(cards) for cards in self.box_inventory.values())
        total_boxes = len(self.box_inventory)
        
        self.statistics = {
            'total_cards': total_cards,
            'total_boxes': total_boxes,
            'last_updated': datetime.now().isoformat()
        }
    
    def catalog_card(self, card_data, box_name=None):
        """Add a card to the library."""
        if box_name is None:
            box_name = self.current_box or 'AA'
        
        # Ensure box exists
        if box_name not in self.box_inventory:
            self.box_inventory[box_name] = []
            self.box_counter[box_name] = 1
        
        # Generate call number
        card_num = self.box_counter.get(box_name, 1)
        call_number = f"{box_name}-{card_num:04d}"
        
        # Add to card data
        card_data['call_number'] = call_number
        card_data['box'] = box_name
        card_data['cataloged_date'] = datetime.now().isoformat()
        
        # Add to inventory
        self.box_inventory[box_name].append(card_data)
        self.card_locations[call_number] = card_data.get('name', 'Unknown')
        self.box_counter[box_name] = card_num + 1

        # ============================================================
        # FIX: Also add to SQLite database if available
        # Without this, approved cards don't show in collection tab!
        # ============================================================
        if self.db:
            try:
                db_card = {
                    'call_number': call_number,
                    'box_id': box_name,
                    'position': card_num,
                    'name': card_data.get('name', 'Unknown'),
                    'set_code': card_data.get('set_code') or card_data.get('set', ''),
                    'set_name': card_data.get('set_name', ''),
                    'collector_number': card_data.get('collector_number', ''),
                    'rarity': card_data.get('rarity', ''),
                    'colors': card_data.get('colors', []),
                    'color_identity': card_data.get('color_identity', []),
                    'mana_cost': card_data.get('mana_cost', ''),
                    'cmc': card_data.get('cmc', 0),
                    'type_line': card_data.get('type_line', ''),
                    'foil': card_data.get('foil', False),
                    'condition': card_data.get('condition', 'NM'),
                    'price': card_data.get('price_usd') or card_data.get('price', 0),
                    'image_url': card_data.get('image_uris', {}).get('normal') if isinstance(card_data.get('image_uris'), dict) else card_data.get('image_url', ''),
                    'scryfall_id': card_data.get('scryfall_id', ''),
                    'cataloged_at': datetime.now().isoformat(),
                }
                self.db.add(db_card)
            except Exception as e:
                print(f"[WARN] SQLite add failed: {e}")

        # Update stats
        self._update_statistics()

        return call_number

    def get_card(self, call_number):
        """Get a card by call number (indexed lookup with SQLite)."""
        # Use SQLite indexed lookup if available (O(1) vs O(n))
        if self.db:
            return self.db.get(call_number)

        # Fallback to in-memory search
        if '-' in call_number:
            box_name = call_number.split('-')[0]
            if box_name in self.box_inventory:
                for card in self.box_inventory[box_name]:
                    if card.get('call_number') == call_number:
                        return card
        return None

    def update_card(self, call_number, updates):
        """
        Update a card's data by call number.

        Args:
            call_number: Card call number (e.g. 'AA-0001')
            updates: dict of fields to update (e.g. {'price_usd': 1.50, 'name': 'Lightning Bolt'})

        Returns:
            bool: True if updated successfully
        """
        if not call_number or not updates:
            return False

        # Update in box_inventory (in-memory)
        if '-' in call_number:
            box_name = call_number.split('-')[0]
            if box_name in self.box_inventory:
                for card in self.box_inventory[box_name]:
                    if card.get('call_number') == call_number:
                        card.update(updates)
                        break

        # Update in SQLite database
        if self.db:
            try:
                existing = self.db.get(call_number)
                if existing:
                    existing.update(updates)
                    # Map price_usd to price for DB storage
                    if 'price_usd' in updates:
                        existing['price'] = updates['price_usd']
                    self.db.add(existing)
            except Exception as e:
                print(f"[WARN] SQLite update failed for {call_number}: {e}")

        return True

    def search_cards(self, query, limit=100):
        """Search for cards by name (uses indexed SQLite when available)."""
        # Use SQLite indexed search if available (much faster)
        if self.db:
            return self.db.search_by_name(query, limit=limit)

        # Fallback to in-memory search
        results = []
        query_lower = query.lower()

        for box_name, cards in self.box_inventory.items():
            for card in cards:
                if query_lower in card.get('name', '').lower():
                    results.append(card)
                    if len(results) >= limit:
                        return results

        return results
    
    def get_all_cards(self):
        """Get all cards as a flat list."""
        # Use SQLite database if available (faster, more reliable)
        if self.db:
            try:
                all_data = self.db.get_all()
                return list(all_data.values())
            except Exception as e:
                print(f"[WARN] SQLite get_all failed: {e}, falling back to box_inventory")

        # Fallback to box_inventory
        all_cards = []
        for box_name, cards in self.box_inventory.items():
            all_cards.extend(cards)
        return all_cards
    
    def get_box_contents(self, box_name):
        """Get all cards in a box."""
        return self.box_inventory.get(box_name, [])
    
    def get_box_names(self):
        """Get list of all box names."""
        return sorted(self.box_inventory.keys())
    
    # ============================================================
    # PRICING METHOD WRAPPERS (FIXED)
    # ============================================================
    # These methods wrap the pricing engine for easy access
    
    def get_collection_value(self):
        """Get total collection value."""
        if not self.pricing_engine:
            return 0.0
        try:
            return self.pricing_engine.get_collection_value()
        except Exception as e:
            print(f"Error getting collection value: {e}")
            return 0.0
    
    def get_top_value_cards(self, limit=20):
        """Get top cards by value."""
        if not self.pricing_engine:
            return []
        try:
            return self.pricing_engine.get_top_value_cards(limit=limit)
        except Exception as e:
            print(f"Error getting top value cards: {e}")
            return []
    
    def update_all_prices(self, callback=None):
        """
        Update prices for all cards in collection.
        
        Args:
            callback: Optional function(card_name, current, total) for progress
        
        Returns:
            int: Number of cards updated
        """
        if not self.pricing_engine:
            print("Pricing engine not available")
            return 0
        try:
            return self.pricing_engine.update_collection_prices(callback=callback)
        except Exception as e:
            print(f"Error updating prices: {e}")
            return 0
    
    def update_prices_bulk(self, callback=None):
        """
        Update prices using Scryfall bulk data (FAST method).
        
        This downloads the full Scryfall bulk data file and matches
        against your collection. Much faster than individual API calls.
        
        Args:
            callback: Optional function(status_message) for progress
        
        Returns:
            int: Number of cards updated
        """
        if not self.pricing_engine:
            print("Pricing engine not available")
            return 0
        try:
            return self.pricing_engine.fetch_bulk_prices(callback=callback)
        except Exception as e:
            print(f"Error in bulk update: {e}")
            return 0
    
    def get_card_price(self, scryfall_id):
        """Get current price for a card."""
        if not self.pricing_engine:
            return None
        try:
            return self.pricing_engine.get_cached_price(scryfall_id)
        except Exception as e:
            print(f"Error getting price: {e}")
            return None
    
    def get_price_trend(self, scryfall_id, days=30):
        """
        Get price trend for a card.
        
        Args:
            scryfall_id: Scryfall ID of the card
            days: Number of days to analyze
        
        Returns:
            dict: {'direction': 'up'/'down'/'stable', 'percent_change': float, ...}
        """
        if not self.pricing_engine:
            return None
        try:
            return self.pricing_engine.get_price_trend(scryfall_id, days=days)
        except Exception as e:
            print(f"Error getting trend: {e}")
            return None
    
    def get_price_history(self, scryfall_id):
        """Get price history for a card."""
        if not self.pricing_engine:
            return []
        try:
            return self.pricing_engine.price_history.get(scryfall_id, [])
        except Exception as e:
            print(f"Error getting history: {e}")
            return []
    
    def add_price_alert(self, scryfall_id, card_name, alert_type, threshold):
        """
        Add a price alert for a card.
        
        Args:
            scryfall_id: Scryfall ID of the card
            card_name: Name of the card (for display)
            alert_type: 'above' or 'below'
            threshold: Price threshold (float)
        
        Returns:
            bool: Success
        """
        if not self.pricing_engine:
            return False
        try:
            self.pricing_engine.add_price_alert(
                scryfall_id=scryfall_id,
                card_name=card_name,
                alert_type=alert_type,
                threshold=float(threshold)
            )
            return True
        except Exception as e:
            print(f"Error adding alert: {e}")
            return False
    
    def remove_price_alert(self, scryfall_id):
        """Remove a price alert."""
        if not self.pricing_engine:
            return False
        try:
            self.pricing_engine.remove_price_alert(scryfall_id)
            return True
        except Exception as e:
            print(f"Error removing alert: {e}")
            return False
    
    def get_price_alerts(self):
        """Get all price alerts."""
        if not self.pricing_engine:
            return []
        try:
            return self.pricing_engine.get_price_alerts()
        except Exception as e:
            print(f"Error getting alerts: {e}")
            return []
    
    def get_triggered_alerts(self):
        """Get alerts that have been triggered."""
        if not self.pricing_engine:
            return []
        try:
            return self.pricing_engine.get_triggered_alerts()
        except Exception as e:
            print(f"Error getting triggered alerts: {e}")
            return []
    
    def start_background_updates(self, interval_hours=24):
        """Start background price update thread."""
        if not self.pricing_engine:
            return False
        try:
            self.pricing_engine.start_background_updates(interval_hours=interval_hours)
            return True
        except Exception as e:
            print(f"Error starting background updates: {e}")
            return False
    
    def stop_background_updates(self):
        """Stop background price update thread."""
        if not self.pricing_engine:
            return
        try:
            self.pricing_engine.stop_background_updates()
        except Exception as e:
            print(f"Error stopping background updates: {e}")
    
    # ============================================================
    # UTILITY: Find card by name (for alerts dialog)
    # ============================================================
    
    def find_card_by_name(self, card_name):
        """
        Find a card by name and return its data.
        
        Args:
            card_name: Name of card to find
        
        Returns:
            dict: Card data or None
        """
        card_name_lower = card_name.lower().strip()
        
        for box_name, cards in self.box_inventory.items():
            for card in cards:
                if card.get('name', '').lower() == card_name_lower:
                    return card
        
        return None
    
    def get_scryfall_id_by_name(self, card_name):
        """
        Get scryfall_id for a card by name.
        
        Args:
            card_name: Name of card
        
        Returns:
            str: scryfall_id or None
        """
        card = self.find_card_by_name(card_name)
        if card:
            return card.get('scryfall_id')
        return None


# ============================================================
# TEST / MAIN
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("NEXUS Library System - Pricing Integration Test")
    print("="*60 + "\n")
    
    # Initialize
    library = NexusLibrarySystem()
    
    # Test pricing
    print(f"\nCollection Value: ${library.get_collection_value():,.2f}")

    print(f"\nTop 5 Cards:")
    for i, card in enumerate(library.get_top_value_cards(limit=5), 1):
        name = card.get('name', 'Unknown')
        price = card.get('price', 0) or 0
        print(f"   {i}. {name}: ${price:.2f}")

    print(f"\nPrice Alerts: {len(library.get_price_alerts())}")
    
    print("\n[OK] All systems operational!")

# Alias for compatibility
LibrarySystem = NexusLibrarySystem
