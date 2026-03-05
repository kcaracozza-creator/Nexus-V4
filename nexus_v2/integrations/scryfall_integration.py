#!/usr/bin/env python3
"""
Scryfall Card Data Integration
Fetches real card data (CMC, types, colors, prices) from Scryfall API
With caching to avoid rate limits
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


class ScryfallCache:
    """Local cache for Scryfall data to avoid rate limits"""
    
    CACHE_FILE = "scryfall_cache.json"
    CACHE_DAYS = 7  # How long to keep cached data
    
    def __init__(self, cache_file=None):
        self.cache_file = cache_file or self.CACHE_FILE
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """Load cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Check if cache is too old
                    if 'timestamp' in data:
                        cache_time = datetime.fromisoformat(data['timestamp'])
                        if datetime.now() - cache_time > timedelta(days=self.CACHE_DAYS):
                            print("⚠️ Cache expired, will refresh data")
                            return {'cards': {}, 'timestamp': datetime.now().isoformat()}
                    return data
            except Exception as e:
                print(f"⚠️ Could not load cache: {e}")
        return {'cards': {}, 'timestamp': datetime.now().isoformat()}
    
    def save(self):
        """Save cache to file"""
        self.cache['timestamp'] = datetime.now().isoformat()
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")
    
    def get(self, card_name: str) -> Optional[dict]:
        """Get card from cache"""
        return self.cache.get('cards', {}).get(card_name.lower())
    
    def set(self, card_name: str, data: dict):
        """Store card in cache"""
        if 'cards' not in self.cache:
            self.cache['cards'] = {}
        self.cache['cards'][card_name.lower()] = data
    
    def has(self, card_name: str) -> bool:
        """Check if card is in cache"""
        return card_name.lower() in self.cache.get('cards', {})


class ScryfallAPI:
    """Scryfall API client with rate limiting and caching"""
    
    BASE_URL = "https://api.scryfall.com"
    RATE_LIMIT_MS = 100  # Scryfall asks for 50-100ms between requests
    
    def __init__(self):
        self.cache = ScryfallCache()
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NEXUS-DeckBuilder/1.0',
            'Accept': 'application/json'
        })
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        elapsed = (time.time() * 1000) - self.last_request_time
        if elapsed < self.RATE_LIMIT_MS:
            time.sleep((self.RATE_LIMIT_MS - elapsed) / 1000)
        self.last_request_time = time.time() * 1000
    
    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Make API request with rate limiting"""
        self._rate_limit()
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                print(f"⚠️ Scryfall API error: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ Scryfall request failed: {e}")
            return None
    
    def get_card(self, card_name: str, use_cache: bool = True) -> Optional[dict]:
        """Get card data by name"""
        # Check cache first
        if use_cache and self.cache.has(card_name):
            return self.cache.get(card_name)
        
        # Query Scryfall
        data = self._make_request("cards/named", {"fuzzy": card_name})
        
        if data:
            # Extract relevant fields
            card_data = self._extract_card_data(data)
            self.cache.set(card_name, card_data)
            return card_data
        
        return None
    
    def get_cards_batch(self, card_names: List[str], progress_callback=None) -> Dict[str, dict]:
        """Get multiple cards with progress reporting"""
        results = {}
        uncached = []
        
        # Check cache first
        for name in card_names:
            if self.cache.has(name):
                results[name] = self.cache.get(name)
            else:
                uncached.append(name)
        
        # Fetch uncached cards
        total = len(uncached)
        for i, name in enumerate(uncached):
            if progress_callback:
                progress_callback(i + 1, total, name)
            
            data = self.get_card(name, use_cache=False)
            if data:
                results[name] = data
        
        # Save cache
        self.cache.save()
        
        return results
    
    def _extract_card_data(self, raw_data: dict) -> dict:
        """Extract relevant fields from Scryfall response"""
        # Handle double-faced cards
        if 'card_faces' in raw_data:
            front_face = raw_data['card_faces'][0]
            mana_cost = front_face.get('mana_cost', '')
            type_line = front_face.get('type_line', '')
        else:
            mana_cost = raw_data.get('mana_cost', '')
            type_line = raw_data.get('type_line', '')
        
        # Get prices
        prices = raw_data.get('prices', {})
        
        return {
            'name': raw_data.get('name', ''),
            'mana_cost': mana_cost,
            'cmc': raw_data.get('cmc', 0),
            'type_line': type_line,
            'colors': raw_data.get('colors', []),
            'color_identity': raw_data.get('color_identity', []),
            'rarity': raw_data.get('rarity', ''),
            'set': raw_data.get('set', ''),
            'set_name': raw_data.get('set_name', ''),
            'price_usd': float(prices.get('usd') or 0),
            'price_usd_foil': float(prices.get('usd_foil') or 0),
            'oracle_text': raw_data.get('oracle_text', ''),
            'power': raw_data.get('power'),
            'toughness': raw_data.get('toughness'),
            'keywords': raw_data.get('keywords', []),
            'legalities': raw_data.get('legalities', {}),
        }
    
    def get_cmc(self, card_name: str) -> int:
        """Get converted mana cost for a card"""
        data = self.get_card(card_name)
        if data:
            return int(data.get('cmc', 0))
        return 0
    
    def get_type(self, card_name: str) -> str:
        """Get type line for a card"""
        data = self.get_card(card_name)
        if data:
            return data.get('type_line', '')
        return ''
    
    def get_colors(self, card_name: str) -> List[str]:
        """Get colors for a card"""
        data = self.get_card(card_name)
        if data:
            return data.get('colors', [])
        return []
    
    def get_color_identity(self, card_name: str) -> List[str]:
        """Get color identity for a card (for Commander)"""
        data = self.get_card(card_name)
        if data:
            return data.get('color_identity', [])
        return []
    
    def get_price(self, card_name: str) -> float:
        """Get USD price for a card"""
        data = self.get_card(card_name)
        if data:
            return data.get('price_usd', 0.0)
        return 0.0
    
    def is_legal(self, card_name: str, format_name: str) -> bool:
        """Check if card is legal in a format"""
        data = self.get_card(card_name)
        if data:
            legalities = data.get('legalities', {})
            return legalities.get(format_name.lower(), 'not_legal') == 'legal'
        return False
    
    def search_cards(self, query: str, limit: int = 20) -> List[dict]:
        """Search for cards matching a query"""
        data = self._make_request("cards/search", {"q": query})
        if data and 'data' in data:
            return [self._extract_card_data(card) for card in data['data'][:limit]]
        return []
    
    def get_commanders(self, colors: List[str] = None) -> List[dict]:
        """Get legendary creatures that can be commanders"""
        query = "is:commander"
        if colors:
            color_str = "".join(colors)
            query += f" id<={color_str}"
        
        return self.search_cards(query, limit=50)
    
    def save_cache(self):
        """Explicitly save the cache"""
        self.cache.save()


class CardDataEnricher:
    """Enriches card data with Scryfall information"""
    
    def __init__(self):
        self.api = ScryfallAPI()
    
    def enrich_collection(self, collection: Dict[str, int], 
                         progress_callback=None) -> Dict[str, dict]:
        """
        Enrich a collection with Scryfall data
        
        Args:
            collection: Dict of {card_name: quantity}
            progress_callback: Optional callback(current, total, card_name)
        
        Returns:
            Dict of {card_name: {quantity, ...scryfall_data}}
        """
        enriched = {}
        card_names = list(collection.keys())
        
        # Fetch all card data
        card_data = self.api.get_cards_batch(card_names, progress_callback)
        
        # Combine with quantities
        for name, qty in collection.items():
            if name in card_data:
                enriched[name] = {
                    'quantity': qty,
                    **card_data[name]
                }
            else:
                # Card not found in Scryfall
                enriched[name] = {
                    'quantity': qty,
                    'name': name,
                    'cmc': 0,
                    'type_line': 'Unknown',
                    'colors': [],
                    'price_usd': 0.0,
                }
        
        return enriched
    
    def get_mana_curve(self, deck: List[str]) -> Dict[int, int]:
        """
        Get mana curve distribution for a deck
        
        Returns:
            Dict of {cmc: count}
        """
        curve = defaultdict(int)
        
        for card_name in deck:
            cmc = self.api.get_cmc(card_name)
            # Cap at 7+ for display purposes
            display_cmc = min(cmc, 7)
            curve[display_cmc] += 1
        
        return dict(curve)
    
    def get_color_distribution(self, deck: List[str]) -> Dict[str, int]:
        """
        Get color distribution for a deck
        
        Returns:
            Dict of {color: count}
        """
        colors = defaultdict(int)
        
        for card_name in deck:
            card_colors = self.api.get_colors(card_name)
            for color in card_colors:
                colors[color] += 1
            if not card_colors:
                colors['C'] += 1  # Colorless
        
        return dict(colors)
    
    def get_type_distribution(self, deck: List[str]) -> Dict[str, int]:
        """
        Get card type distribution for a deck
        
        Returns:
            Dict of {type: count}
        """
        types = defaultdict(int)
        
        type_categories = {
            'Creature': 'Creature',
            'Instant': 'Instant',
            'Sorcery': 'Sorcery',
            'Artifact': 'Artifact',
            'Enchantment': 'Enchantment',
            'Planeswalker': 'Planeswalker',
            'Land': 'Land',
        }
        
        for card_name in deck:
            type_line = self.api.get_type(card_name)
            categorized = False
            for key, category in type_categories.items():
                if key in type_line:
                    types[category] += 1
                    categorized = True
                    break
            if not categorized:
                types['Other'] += 1
        
        return dict(types)
    
    def calculate_deck_value(self, deck: List[str]) -> Dict[str, Any]:
        """
        Calculate total value of a deck
        
        Returns:
            Dict with total_value, card_values, most_expensive, etc.
        """
        card_values = {}
        total = 0.0
        
        for card_name in deck:
            price = self.api.get_price(card_name)
            card_values[card_name] = price
            total += price
        
        # Sort by price
        sorted_cards = sorted(card_values.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_value': total,
            'card_values': card_values,
            'most_expensive': sorted_cards[:10] if sorted_cards else [],
            'average_card_value': total / len(deck) if deck else 0,
        }


# Global API instance
_api = None

def get_scryfall_api() -> ScryfallAPI:
    """Get the global Scryfall API instance"""
    global _api
    if _api is None:
        _api = ScryfallAPI()
    return _api


# Convenience functions
def get_card_cmc(card_name: str) -> int:
    return get_scryfall_api().get_cmc(card_name)

def get_card_type(card_name: str) -> str:
    return get_scryfall_api().get_type(card_name)

def get_card_colors(card_name: str) -> List[str]:
    return get_scryfall_api().get_colors(card_name)

def get_card_price(card_name: str) -> float:
    return get_scryfall_api().get_price(card_name)


if __name__ == "__main__":
    # Test the API
    api = ScryfallAPI()
    
    print("🔍 Testing Scryfall API Integration\n")
    
    test_cards = [
        "Lightning Bolt",
        "Counterspell",
        "Tarmogoyf",
        "Sol Ring",
        "Black Lotus",
    ]
    
    for card in test_cards:
        data = api.get_card(card)
        if data:
            print(f"✅ {data['name']}")
            print(f"   CMC: {data['cmc']}")
            print(f"   Type: {data['type_line']}")
            print(f"   Colors: {data['colors']}")
            print(f"   Price: ${data['price_usd']:.2f}")
            print()
        else:
            print(f"❌ {card} - not found")
    
    # Save cache
    api.save_cache()
    print("✅ Cache saved")
