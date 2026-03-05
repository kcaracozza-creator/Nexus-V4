"""
NEXUS Auto Pricing Engine - UPDATED
====================================
Clouse - December 1, 2025

This engine handles:
- Scryfall API price fetching (individual cards)
- Scryfall Bulk Data price fetching (FAST, all at once)
- Price history tracking
- Price alerts
- Collection value calculation
- Background price updates

INTEGRATION:
    from auto_pricing_engine import AutoPricingEngine
    engine = AutoPricingEngine(data_dir="path/to/data", library=library_instance)

"""

import json
import time
import threading
import requests
from datetime import datetime, timedelta
from pathlib import Path


class AutoPricingEngine:
    """
    Automatic pricing engine for NEXUS card collections.
    Integrates with Scryfall API for real-time prices.
    """
    
    # Scryfall rate limit: 10 requests per second, we use 100ms for safety
    RATE_LIMIT_MS = 100
    
    # Cache prices for 24 hours
    CACHE_DURATION_HOURS = 24
    
    # Keep price history for 365 days
    HISTORY_DAYS = 365
    
    def __init__(self, data_dir=None, library=None):
        """
        Initialize the pricing engine.
        
        Args:
            data_dir: Directory for storing price data files
            library: NexusLibrarySystem instance (for accessing card data)
        """
        self.library = library
        
        # Set data directory
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).parent
        
        # Data files
        self.cache_file = self.data_dir / "price_cache.json"
        self.history_file = self.data_dir / "price_history.json"
        self.alerts_file = self.data_dir / "price_alerts.json"
        
        # In-memory data
        self.price_cache = {}      # scryfall_id → {'price': float, 'timestamp': str, ...}
        self.price_history = {}    # scryfall_id → [{'price': float, 'date': str}, ...]
        self.price_alerts = {}     # scryfall_id → {'type': str, 'threshold': float, ...}
        self.triggered_alerts = [] # List of triggered alerts
        
        # Background update thread
        self._update_thread = None
        self._stop_updates = False
        
        # Load existing data
        self._load_data()
        
        print(f"💰 Pricing Engine initialized")
        print(f"   Cache: {len(self.price_cache)} prices")
        print(f"   History: {len(self.price_history)} cards tracked")
        print(f"   Alerts: {len(self.price_alerts)} active")
    
    # ============================================================
    # DATA PERSISTENCE
    # ============================================================
    
    def _load_data(self):
        """Load cached data from files."""
        # Load price cache
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.price_cache = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load price cache: {e}")
        
        # Load price history
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    self.price_history = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load price history: {e}")
        
        # Load alerts
        if self.alerts_file.exists():
            try:
                with open(self.alerts_file, 'r') as f:
                    self.price_alerts = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load price alerts: {e}")
    
    def _save_data(self):
        """Save all data to files."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.price_cache, f, indent=2, default=str)
            
            with open(self.history_file, 'w') as f:
                json.dump(self.price_history, f, indent=2, default=str)
            
            with open(self.alerts_file, 'w') as f:
                json.dump(self.price_alerts, f, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Could not save price data: {e}")
    
    # ============================================================
    # SCRYFALL API - INDIVIDUAL CARDS
    # ============================================================
    
    def fetch_card_price(self, scryfall_id):
        """
        Fetch price for a single card from Scryfall API.
        
        Args:
            scryfall_id: Scryfall ID of the card
        
        Returns:
            dict: {'usd': float, 'usd_foil': float, ...} or None
        """
        if not scryfall_id:
            return None
        
        url = f"https://api.scryfall.com/cards/{scryfall_id}"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                prices = data.get('prices', {})
                return {
                    'usd': float(prices.get('usd') or 0),
                    'usd_foil': float(prices.get('usd_foil') or 0),
                    'usd_etched': float(prices.get('usd_etched') or 0),
                    'eur': float(prices.get('eur') or 0),
                    'name': data.get('name', ''),
                    'set': data.get('set', ''),
                    'timestamp': datetime.now().isoformat()
                }
            elif response.status_code == 404:
                return None
            else:
                print(f"Scryfall API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error fetching price for {scryfall_id}: {e}")
            return None
        
        finally:
            # Rate limiting
            time.sleep(self.RATE_LIMIT_MS / 1000)
    
    def update_card_price(self, scryfall_id, force=False):
        """
        Update price for a card (uses cache if recent).
        
        Args:
            scryfall_id: Scryfall ID
            force: If True, bypass cache and fetch fresh
        
        Returns:
            float: USD price or None
        """
        if not scryfall_id:
            return None
        
        # Check cache
        if not force and scryfall_id in self.price_cache:
            cached = self.price_cache[scryfall_id]
            cached_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
            
            if datetime.now() - cached_time < timedelta(hours=self.CACHE_DURATION_HOURS):
                return cached.get('usd', 0)
        
        # Fetch fresh price
        price_data = self.fetch_card_price(scryfall_id)
        
        if price_data:
            # Update cache
            self.price_cache[scryfall_id] = price_data
            
            # Add to history
            self._add_to_history(scryfall_id, price_data.get('usd', 0))
            
            # Check alerts
            self._check_alerts(scryfall_id, price_data.get('usd', 0))
            
            return price_data.get('usd', 0)
        
        return None
    
    def get_cached_price(self, scryfall_id):
        """Get cached price for a card (no API call)."""
        if scryfall_id in self.price_cache:
            return self.price_cache[scryfall_id].get('usd', 0)
        return None
    
    # ============================================================
    # SCRYFALL BULK DATA - FAST UPDATES
    # ============================================================
    
    def fetch_bulk_prices(self, callback=None):
        """
        Fetch prices using Scryfall bulk data.
        MUCH faster than individual API calls.
        
        Args:
            callback: Optional function(status_message) for progress
        
        Returns:
            int: Number of cards updated
        """
        if callback:
            callback("Fetching Scryfall bulk data info...")
        
        # Step 1: Get bulk data URL
        try:
            bulk_info_url = "https://api.scryfall.com/bulk-data"
            response = requests.get(bulk_info_url, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"Failed to get bulk data info: {response.status_code}")
            
            bulk_data = response.json()
            
            # Find the default cards bulk data
            default_cards = None
            for item in bulk_data.get('data', []):
                if item.get('type') == 'default_cards':
                    default_cards = item
                    break
            
            if not default_cards:
                raise Exception("Could not find default_cards bulk data")
            
            download_url = default_cards.get('download_uri')
            
        except Exception as e:
            print(f"Error getting bulk data info: {e}")
            return 0
        
        if callback:
            callback("Downloading bulk price data (~100MB)...")
        
        # Step 2: Download bulk data
        try:
            response = requests.get(download_url, timeout=300, stream=True)
            
            if response.status_code != 200:
                raise Exception(f"Failed to download bulk data: {response.status_code}")
            
            # Parse JSON (this is a large file)
            if callback:
                callback("Parsing bulk data...")
            
            all_cards = response.json()
            
        except Exception as e:
            print(f"Error downloading bulk data: {e}")
            return 0
        
        if callback:
            callback("Matching prices to your collection...")
        
        # Step 3: Build lookup of my scryfall_ids
        my_cards = {}  # scryfall_id → card reference
        
        if self.library:
            for box_name, cards in self.library.box_inventory.items():
                for card in cards:
                    sid = card.get('scryfall_id')
                    if sid:
                        my_cards[sid] = card
        
        if not my_cards:
            if callback:
                callback("No cards with scryfall_id found in collection")
            return 0
        
        if callback:
            callback(f"Matching {len(my_cards):,} cards...")
        
        # Step 4: Match and update prices
        updated_count = 0
        
        for scryfall_card in all_cards:
            sid = scryfall_card.get('id')
            
            if sid in my_cards:
                prices = scryfall_card.get('prices', {})
                usd_price = float(prices.get('usd') or 0)
                usd_foil = float(prices.get('usd_foil') or 0)
                
                # Update cache
                self.price_cache[sid] = {
                    'usd': usd_price,
                    'usd_foil': usd_foil,
                    'name': scryfall_card.get('name', ''),
                    'set': scryfall_card.get('set', ''),
                    'timestamp': datetime.now().isoformat()
                }
                
                # Update card in library
                my_cards[sid]['price'] = usd_price
                my_cards[sid]['price_foil'] = usd_foil
                my_cards[sid]['price_updated'] = datetime.now().isoformat()
                
                # Add to history
                self._add_to_history(sid, usd_price)
                
                # Check alerts
                self._check_alerts(sid, usd_price)
                
                updated_count += 1
        
        # Step 5: Save everything
        if callback:
            callback(f"Saving {updated_count:,} updated prices...")
        
        self._save_data()
        
        # Save library if possible
        if self.library and hasattr(self.library, '_save_library'):
            self.library._save_library()
        
        if callback:
            callback(f"Complete! Updated {updated_count:,} cards.")
        
        return updated_count
    
    # ============================================================
    # COLLECTION UPDATES
    # ============================================================
    
    def update_collection_prices(self, callback=None):
        """
        Update prices for all cards in collection using individual API calls.
        
        Args:
            callback: Optional function(card_name, current, total) for progress
        
        Returns:
            int: Number of cards updated
        """
        if not self.library:
            print("No library connected")
            return 0
        
        # Collect all cards with scryfall_id
        cards_to_update = []
        
        for box_name, cards in self.library.box_inventory.items():
            for card in cards:
                if card.get('scryfall_id'):
                    cards_to_update.append(card)
        
        total = len(cards_to_update)
        updated = 0
        
        print(f"Updating prices for {total} cards...")
        
        for i, card in enumerate(cards_to_update):
            scryfall_id = card['scryfall_id']
            card_name = card.get('name', 'Unknown')
            
            # Callback for progress
            if callback:
                result = callback(card_name, i + 1, total)
                if result is False:  # Allow cancellation
                    break
            
            # Fetch price
            price = self.update_card_price(scryfall_id)
            
            if price is not None:
                # Update card in library
                card['price'] = price
                card['price_updated'] = datetime.now().isoformat()
                updated += 1
        
        # Save data
        self._save_data()
        
        # Save library
        if hasattr(self.library, '_save_library'):
            self.library._save_library()
        
        print(f"Updated {updated} of {total} cards")
        return updated
    
    # ============================================================
    # PRICE HISTORY
    # ============================================================
    
    def _add_to_history(self, scryfall_id, price):
        """Add a price point to history."""
        if scryfall_id not in self.price_history:
            self.price_history[scryfall_id] = []
        
        # Add new point
        self.price_history[scryfall_id].append({
            'price': price,
            'date': datetime.now().strftime('%Y-%m-%d')
        })
        
        # Trim old entries
        cutoff = datetime.now() - timedelta(days=self.HISTORY_DAYS)
        self.price_history[scryfall_id] = [
            p for p in self.price_history[scryfall_id]
            if datetime.strptime(p['date'], '%Y-%m-%d') >= cutoff
        ]
    
    def get_price_trend(self, scryfall_id, days=30):
        """
        Get price trend for a card.
        
        Args:
            scryfall_id: Card's Scryfall ID
            days: Number of days to analyze
        
        Returns:
            dict: {
                'direction': 'up'/'down'/'stable',
                'percent_change': float,
                'start_price': float,
                'end_price': float,
                'data_points': int
            }
        """
        history = self.price_history.get(scryfall_id, [])
        
        if len(history) < 2:
            return {
                'direction': 'stable',
                'percent_change': 0,
                'start_price': 0,
                'end_price': 0,
                'data_points': len(history)
            }
        
        # Get data from last N days
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            p for p in history
            if datetime.strptime(p['date'], '%Y-%m-%d') >= cutoff
        ]
        
        if len(recent) < 2:
            recent = history[-10:] if len(history) >= 10 else history
        
        start_price = recent[0]['price']
        end_price = recent[-1]['price']
        
        if start_price == 0:
            pct_change = 0
        else:
            pct_change = ((end_price - start_price) / start_price) * 100
        
        if pct_change > 5:
            direction = 'up'
        elif pct_change < -5:
            direction = 'down'
        else:
            direction = 'stable'
        
        return {
            'direction': direction,
            'percent_change': abs(pct_change),
            'start_price': start_price,
            'end_price': end_price,
            'data_points': len(recent)
        }
    
    # ============================================================
    # PRICE ALERTS
    # ============================================================
    
    def add_price_alert(self, scryfall_id, card_name, alert_type, threshold):
        """
        Add a price alert.
        
        Args:
            scryfall_id: Card's Scryfall ID
            card_name: Card name (for display)
            alert_type: 'above' or 'below'
            threshold: Price threshold
        """
        self.price_alerts[scryfall_id] = {
            'scryfall_id': scryfall_id,
            'card_name': card_name,
            'type': alert_type,
            'threshold': float(threshold),
            'created': datetime.now().isoformat()
        }
        self._save_data()
    
    def remove_price_alert(self, scryfall_id):
        """Remove a price alert."""
        if scryfall_id in self.price_alerts:
            del self.price_alerts[scryfall_id]
            self._save_data()
    
    def get_price_alerts(self):
        """Get all price alerts as a list."""
        return list(self.price_alerts.values())
    
    def get_triggered_alerts(self):
        """Get list of triggered alerts."""
        return self.triggered_alerts
    
    def _check_alerts(self, scryfall_id, current_price):
        """Check if price triggers an alert."""
        if scryfall_id not in self.price_alerts:
            return
        
        alert = self.price_alerts[scryfall_id]
        threshold = alert['threshold']
        alert_type = alert['type']
        
        triggered = False
        
        if alert_type == 'above' and current_price >= threshold:
            triggered = True
        elif alert_type == 'below' and current_price <= threshold:
            triggered = True
        
        if triggered:
            # Add to triggered list if not already there
            already_triggered = any(
                a.get('scryfall_id') == scryfall_id 
                for a in self.triggered_alerts
            )
            
            if not already_triggered:
                self.triggered_alerts.append({
                    'scryfall_id': scryfall_id,
                    'card_name': alert['card_name'],
                    'type': alert_type,
                    'threshold': threshold,
                    'current_price': current_price,
                    'triggered_at': datetime.now().isoformat()
                })
    
    def clear_triggered_alerts(self):
        """Clear all triggered alerts."""
        self.triggered_alerts = []
    
    # ============================================================
    # COLLECTION VALUE
    # ============================================================
    
    def get_collection_value(self):
        """
        Calculate total collection value.
        
        Returns:
            float: Total USD value
        """
        total = 0.0
        
        if not self.library:
            return total
        
        for box_name, cards in self.library.box_inventory.items():
            for card in cards:
                price = card.get('price', 0)
                if price:
                    total += float(price)
        
        return total
    
    def get_top_value_cards(self, limit=20):
        """
        Get top cards by value.
        
        Args:
            limit: Number of cards to return
        
        Returns:
            list: Cards sorted by price descending
        """
        all_cards = []
        
        if not self.library:
            return all_cards
        
        for box_name, cards in self.library.box_inventory.items():
            for card in cards:
                price = card.get('price', 0)
                if price and price > 0:
                    all_cards.append(card)
        
        # Sort by price descending
        all_cards.sort(key=lambda c: c.get('price', 0), reverse=True)
        
        return all_cards[:limit]
    
    # ============================================================
    # BACKGROUND UPDATES
    # ============================================================
    
    def start_background_updates(self, interval_hours=24):
        """Start background price update thread."""
        if self._update_thread and self._update_thread.is_alive():
            print("Background updates already running")
            return
        
        self._stop_updates = False
        
        def update_loop():
            while not self._stop_updates:
                print(f"[{datetime.now()}] Starting background price update...")
                
                try:
                    self.update_collection_prices()
                except Exception as e:
                    print(f"Background update error: {e}")
                
                # Sleep for interval (check stop flag periodically)
                sleep_seconds = interval_hours * 3600
                for _ in range(int(sleep_seconds / 10)):
                    if self._stop_updates:
                        break
                    time.sleep(10)
        
        self._update_thread = threading.Thread(target=update_loop, daemon=True)
        self._update_thread.start()
        print(f"Background updates started (every {interval_hours} hours)")
    
    def stop_background_updates(self):
        """Stop background update thread."""
        self._stop_updates = True
        print("Background updates stopped")


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Auto Pricing Engine - Test")
    print("="*60 + "\n")
    
    engine = AutoPricingEngine()
    
    # Test single card fetch
    test_id = "bd8fa327-dd41-4737-8f19-2cf5eb1f7571"  # Black Lotus
    print(f"Fetching price for test card...")
    price_data = engine.fetch_card_price(test_id)
    
    if price_data:
        print(f"   Name: {price_data.get('name')}")
        print(f"   Price: ${price_data.get('usd', 0):.2f}")
    else:
        print("   Card not found or API error")
    
    print("\n✅ Pricing engine test complete!")
