#!/usr/bin/env python3
"""
Scryfall Card Data & Pricing Scraper
Official Scryfall API integration for comprehensive card information
"""

import requests
import time
import json
import os
from urllib.parse import quote_plus
from datetime import datetime, timedelta
import threading


class ScryfallScraper:
    def __init__(self):
        self.base_url = "https://api.scryfall.com"
        self.cards_endpoint = "/cards"
        
        # Headers for API requests - Scryfall Member
        self.headers = {
            'User-Agent': 'MTTGG Card Collection System/2.0 (Scryfall Member)',
            'Accept': 'application/json',
            'X-Scryfall-Member': 'true'
        }
        
        # Rate limiting - Scryfall Member: 100 req/sec, respectful delay
        self.last_request_time = 0
        self.min_delay = 0.05  # 50ms between requests (member privilege)
        
        # Data cache
        self.cache_file = os.path.join(os.path.dirname(__file__), 
                                     "scryfall_data_cache.json")
        self.data_cache = self.load_cache()
        
        # Bulk data storage
        self.bulk_data = {}
        self.bulk_data_loaded = False
        
    def load_cache(self):
        """Load data cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # Filter out old entries (older than 24 hours)
                    current_time = datetime.now()
                    filtered_cache = {}
                    for card_name, data in cache_data.items():
                        try:
                            cache_time = datetime.fromisoformat(
                                data.get('timestamp', '1970-01-01')
                            )
                            if current_time - cache_time < timedelta(hours=24):
                                filtered_cache[card_name] = data
                        except:
                            continue
                    return filtered_cache
        except Exception as e:
            print(f"Error loading cache: {e}")
        return {}
    
    def save_cache(self):
        """Save data cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.data_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_delay:
            time.sleep(self.min_delay - time_since_last)
        self.last_request_time = time.time()
    
    def get_card_data(self, card_name, set_code=None):
        """Get comprehensive card data from Scryfall API"""
        # Check cache first
        cache_key = f"{card_name}_{set_code if set_code else 'any'}"
        if cache_key in self.data_cache:
            cached_data = self.data_cache[cache_key]
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            if datetime.now() - cache_time < timedelta(hours=12):
                return cached_data['card_data']
        
        try:
            self.rate_limit()
            
            # Use named search endpoint
            if set_code:
                url = f"{self.base_url}{self.cards_endpoint}/named"
                params = {
                    'fuzzy': card_name,
                    'set': set_code
                }
            else:
                url = f"{self.base_url}{self.cards_endpoint}/named"
                params = {
                    'fuzzy': card_name
                }
            
            response = requests.get(url, headers=self.headers,
                                  params=params, timeout=30)# Reduced timeout
            
            if response.status_code == 200:
                card_data = response.json()
                
                # Extract key information
                processed_data = self.process_card_data(card_data)
                
                # Cache the result
                self.data_cache[cache_key] = {
                    'card_data': processed_data,
                    'timestamp': datetime.now().isoformat()
                }
                self.save_cache()
                
                return processed_data
            
            elif response.status_code == 404:
                # Try fuzzy search if exact match fails
                return self.fuzzy_search_card(card_name, set_code)
            
            else:
                print(f"API error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"Timeout fetching card data for {card_name}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"Connection error fetching card data for {card_name}")
            return None
        except Exception as e:
            print(f"Error fetching card data for {card_name}: {e}")
            return None
    
    def fuzzy_search_card(self, card_name, set_code=None):
        """Perform fuzzy search for card"""
        try:
            self.rate_limit()
            
            url = f"{self.base_url}{self.cards_endpoint}/search"
            params = {
                'q': f'name:"{card_name}"'
            }
            
            if set_code:
                params['q'] += f' set:{set_code}'
            
            response = requests.get(url, headers=self.headers, 
                                  params=params, timeout=10)
            
            if response.status_code == 200:
                search_data = response.json()
                
                if search_data.get('total_cards', 0) > 0:
                    # Take the first result
                    card_data = search_data['data'][0]
                    return self.process_card_data(card_data)
            
            return None
            
        except Exception as e:
            print(f"Error in fuzzy search for {card_name}: {e}")
            return None
    
    def process_card_data(self, raw_data):
        """Process raw Scryfall data into useful format"""
        try:
            # Determine foil availability
            finishes = raw_data.get('finishes', [])
            has_nonfoil = 'nonfoil' in finishes
            has_foil = 'foil' in finishes
            has_etched = 'etched' in finishes
            
            # Get pricing to determine foil availability
            prices = raw_data.get('prices', {})
            foil_price = self.safe_float(prices.get('usd_foil'))
            etched_price = self.safe_float(prices.get('usd_etched'))
            
            processed = {
                # Basic info
                'name': raw_data.get('name', 'Unknown'),
                'mana_cost': raw_data.get('mana_cost', ''),
                'cmc': raw_data.get('cmc', 0),
                'type_line': raw_data.get('type_line', ''),
                'oracle_text': raw_data.get('oracle_text', ''),
                
                # Set info
                'set_code': raw_data.get('set', ''),
                'set_name': raw_data.get('set_name', ''),
                'collector_number': raw_data.get('collector_number', ''),
                'rarity': raw_data.get('rarity', 'common'),
                
                # Colors
                'colors': raw_data.get('colors', []),
                'color_identity': raw_data.get('color_identity', []),
                
                # Power/Toughness
                'power': raw_data.get('power'),
                'toughness': raw_data.get('toughness'),
                'loyalty': raw_data.get('loyalty'),
                
                # Foil/Finish availability
                'finishes': finishes,
                'has_nonfoil': has_nonfoil,
                'has_foil': has_foil,
                'has_etched': has_etched,
                'foil_available': has_foil or has_etched,
                
                # Pricing (USD)
                'prices': self.extract_pricing(raw_data),
                
                # Images
                'image_uris': raw_data.get('image_uris', {}),
                
                # Legalities
                'legalities': raw_data.get('legalities', {}),
                
                # Keywords
                'keywords': raw_data.get('keywords', []),
                
                # Metadata
                'scryfall_id': raw_data.get('id', ''),
                'uri': raw_data.get('uri', ''),
                'released_at': raw_data.get('released_at', ''),
                
                # Timestamp
                'fetched_at': datetime.now().isoformat()
            }
            
            return processed
            
        except Exception as e:
            print(f"Error processing card data: {e}")
            return None
    
    def extract_pricing(self, card_data):
        """Extract pricing information from Scryfall data"""
        prices = card_data.get('prices', {})
        
        pricing_data = {
            'usd': self.safe_float(prices.get('usd')),
            'usd_foil': self.safe_float(prices.get('usd_foil')),
            'usd_etched': self.safe_float(prices.get('usd_etched')),
            'eur': self.safe_float(prices.get('eur')),
            'eur_foil': self.safe_float(prices.get('eur_foil')),
            'tix': self.safe_float(prices.get('tix'))  # MTGO tickets
        }
        
        # Calculate primary market price
        primary_price = (pricing_data['usd'] or 
                        pricing_data['eur'] or 
                        pricing_data['tix'] or 0.0)
        
        pricing_data['primary_market_price'] = primary_price
        
        return pricing_data
    
    def safe_float(self, value):
        """Safely convert price string to float"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def get_card_price(self, card_name, set_code=None):
        """Get just the price for a card"""
        card_data = self.get_card_data(card_name, set_code)
        if card_data:
            return card_data.get('prices', {}).get('primary_market_price', 0.0)
        return 0.0
    
    def get_foil_availability(self, card_name, set_code=None):
        """Check if a card is available in foil/hologram format"""
        card_data = self.get_card_data(card_name, set_code)
        if card_data:
            return {
                'card_name': card_name,
                'foil_available': card_data.get('foil_available', False),
                'has_foil': card_data.get('has_foil', False),
                'has_etched': card_data.get('has_etched', False),
                'finishes': card_data.get('finishes', []),
                'foil_price': card_data.get('prices', {}).get('usd_foil', 0.0),
                'etched_price': card_data.get('prices', {}).get('usd_etched', 0.0),
                'normal_price': card_data.get('prices', {}).get('usd', 0.0)
            }
        return None
    
    def get_bulk_card_data(self, card_names, set_codes=None):
        """Get data for multiple cards efficiently"""
        results = {}
        total_cards = len(card_names)
        
        print(f"🔍 Fetching Scryfall data for {total_cards} cards...")
        
        for i, card_name in enumerate(card_names, 1):
            print(f"  [{i}/{total_cards}] {card_name}")
            
            set_code = None
            if set_codes and i <= len(set_codes):
                set_code = set_codes[i-1]
            
            try:
                card_data = self.get_card_data(card_name, set_code)
                if card_data:
                    results[card_name] = card_data
                else:
                    results[card_name] = None
                    
            except Exception as e:
                print(f"    ❌ Error: {e}")
                results[card_name] = None
        
        found_count = sum(1 for data in results.values() if data is not None)
        print(f"✅ Completed! Found data for {found_count}/{total_cards} cards")
        
        return results
    
    def get_bulk_foil_availability(self, card_names, set_codes=None):
        """Get foil availability for multiple cards"""
        foil_data = {}
        total_cards = len(card_names)
        
        print(f"✨ Checking foil availability for {total_cards} cards...")
        
        for i, card_name in enumerate(card_names, 1):
            if i % 10 == 0:  # Progress update every 10 cards
                print(f"  Progress: {i}/{total_cards} cards checked")
            
            set_code = None
            if set_codes and i <= len(set_codes):
                set_code = set_codes[i-1]
            
            try:
                foil_info = self.get_foil_availability(card_name, set_code)
                if foil_info:
                    foil_data[card_name] = foil_info
                    
            except Exception as e:
                print(f"    ❌ Error checking {card_name}: {e}")
        
        foil_count = sum(1 for data in foil_data.values() 
                        if data and data.get('foil_available', False))
        print(f"✅ Completed! {foil_count}/{total_cards} cards available in foil")
        
        return foil_data
    
    def save_foil_availability_to_file(self, foil_data, filename="foil_availability.json"):
        """Save foil availability data to JSON file"""
        try:
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(foil_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Saved foil availability data to {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Error saving foil data: {e}")
            return None
    
    def search_cards(self, query, unique=True, order='name'):
        """Search for cards using Scryfall query syntax"""
        try:
            self.rate_limit()
            
            url = f"{self.base_url}{self.cards_endpoint}/search"
            params = {
                'q': query,
                'unique': 'cards' if unique else 'prints',
                'order': order
            }
            
            response = requests.get(url, headers=self.headers, 
                                  params=params, timeout=15)
            
            if response.status_code == 200:
                search_data = response.json()
                
                results = []
                for card in search_data.get('data', []):
                    processed = self.process_card_data(card)
                    if processed:
                        results.append(processed)
                
                # Handle pagination if needed
                if search_data.get('has_more', False):
                    print(f"⚠️ More results available. Showing first "
                          f"{len(results)} cards.")
                
                return results
            
            else:
                print(f"Search error {response.status_code}: {response.text}")
                return []
                
        except Exception as e:
            print(f"Error searching for '{query}': {e}")
            return []
    
    def get_random_card(self):
        """Get a random card from Scryfall"""
        try:
            self.rate_limit()
            
            url = f"{self.base_url}{self.cards_endpoint}/random"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                card_data = response.json()
                return self.process_card_data(card_data)
            
            return None
            
        except Exception as e:
            print(f"Error getting random card: {e}")
            return None
    
    def update_collection_with_scryfall_data(self, collection_dict):
        """Update a collection dictionary with Scryfall data"""
        enhanced_collection = {}
        
        for card_name, quantity in collection_dict.items():
            card_data = self.get_card_data(card_name)
            
            if card_data:
                enhanced_collection[card_name] = {
                    'quantity': quantity,
                    'card_data': card_data,
                    'market_value': card_data.get('prices', {}).get(
                        'primary_market_price', 0.0
                    ),
                    'total_value': quantity * card_data.get('prices', {}).get(
                        'primary_market_price', 0.0
                    ),
                    'foil_available': card_data.get('foil_available', False),
                    'foil_price': card_data.get('prices', {}).get('usd_foil', 0.0)
                }
            else:
                enhanced_collection[card_name] = {
                    'quantity': quantity,
                    'card_data': None,
                    'market_value': 0.0,
                    'total_value': 0.0,
                    'foil_available': False,
                    'foil_price': 0.0
                }
        
        return enhanced_collection
    
    def build_advanced_query(self, **filters):
        """Build advanced Scryfall search query from filters
        
        Supported filters:
        - colors: color filter (e.g., 'w', 'ub', 'rg')
        - color_identity: color identity filter
        - type_line: card type (e.g., 'creature', 'instant')
        - oracle_text: text in Oracle text
        - keywords: specific keywords (e.g., 'flying', 'trample')
        - mana_cost: specific mana cost
        - cmc: mana value filter (e.g., '<=3', '=5')
        - power: power filter
        - toughness: toughness filter
        - rarity: rarity (common, uncommon, rare, mythic)
        - set_code: set code
        - format: format legality
        - price_usd: USD price filter (e.g., '>=10', '<5')
        - is_foil: foil availability (True/False)
        - is_commander: can be commander (True/False)
        - artist: artist name
        - flavor_text: flavor text search
        """
        query_parts = []
        
        # Colors
        if 'colors' in filters:
            query_parts.append(f"c:{filters['colors']}")
        
        if 'color_identity' in filters:
            query_parts.append(f"id:{filters['color_identity']}")
        
        # Card type
        if 'type_line' in filters:
            query_parts.append(f"t:{filters['type_line']}")
        
        # Oracle text
        if 'oracle_text' in filters:
            query_parts.append(f'o:"{filters["oracle_text"]}"')
        
        # Keywords
        if 'keywords' in filters:
            query_parts.append(f"kw:{filters['keywords']}")
        
        # Mana cost
        if 'mana_cost' in filters:
            query_parts.append(f"m:{filters['mana_cost']}")
        
        # CMC/Mana Value
        if 'cmc' in filters:
            query_parts.append(f"mv{filters['cmc']}")
        
        # Power/Toughness
        if 'power' in filters:
            query_parts.append(f"pow{filters['power']}")
        
        if 'toughness' in filters:
            query_parts.append(f"tou{filters['toughness']}")
        
        # Rarity
        if 'rarity' in filters:
            query_parts.append(f"r:{filters['rarity']}")
        
        # Set
        if 'set_code' in filters:
            query_parts.append(f"e:{filters['set_code']}")
        
        # Format
        if 'format' in filters:
            query_parts.append(f"f:{filters['format']}")
        
        # Price
        if 'price_usd' in filters:
            query_parts.append(f"usd{filters['price_usd']}")
        
        # Foil
        if 'is_foil' in filters:
            if filters['is_foil']:
                query_parts.append("is:foil")
            else:
                query_parts.append("is:nonfoil")
        
        # Commander
        if 'is_commander' in filters and filters['is_commander']:
            query_parts.append("is:commander")
        
        # Artist
        if 'artist' in filters:
            query_parts.append(f'a:"{filters["artist"]}"')
        
        # Flavor text
        if 'flavor_text' in filters:
            query_parts.append(f'ft:"{filters["flavor_text"]}"')
        
        return ' '.join(query_parts)
    
    def search_by_color_and_type(self, colors, card_type, format_legal=None):
        """Search for cards by color and type"""
        query = f"c:{colors} t:{card_type}"
        if format_legal:
            query += f" f:{format_legal}"
        return self.search_cards(query)
    
    def search_foil_cards_in_set(self, set_code, min_price=None):
        """Search for foil cards in a specific set"""
        query = f"e:{set_code} is:foil"
        if min_price:
            query += f" usd>={min_price}"
        return self.search_cards(query)
    
    def search_commander_options(self, colors=None, min_power=None):
        """Search for commander options"""
        query = "is:commander"
        if colors:
            query += f" id<={colors}"  # Color identity
        if min_power:
            query += f" pow>={min_power}"
        return self.search_cards(query)
    
    def search_budget_cards(self, card_type, max_price, format_legal):
        """Search for budget cards in a format"""
        query = f"t:{card_type} f:{format_legal} usd<={max_price}"
        return self.search_cards(query)
    
    def search_high_value_foils(self, min_price=50.0, rarity='rare'):
        """Search for high-value foil cards"""
        query = f"is:foil usd>={min_price} r>={rarity}"
        return self.search_cards(query)
    
    def search_collection_upgrades(self, color_identity, format_name, 
                                   card_type='creature', min_value=5.0):
        """Search for potential collection upgrades"""
        query = f"id<={color_identity} f:{format_name} t:{card_type} usd>={min_value}"
        return self.search_cards(query)


def main():
    """Test the Scryfall scraper"""
    scraper = ScryfallScraper()
    
    # Test individual card lookup
    print("🔍 Testing Scryfall Card Data Scraper")
    print("=" * 50)
    print("✨ Scryfall Member - Thank you for supporting Scryfall!")
    print("=" * 50)
    
    test_cards = [
        "Lightning Bolt",
        "Black Lotus",
        "Counterspell", 
        "Tarmogoyf",
        "Snapcaster Mage"
    ]
    
    for card in test_cards:
        print(f"\n📋 {card}")
        data = scraper.get_card_data(card)
        
        if data:
            print(f"  Set: {data['set_name']} ({data['set_code']})")
            print(f"  Type: {data['type_line']}")
            print(f"  Rarity: {data['rarity'].title()}")
            print(f"  Price: ${data['prices']['primary_market_price']:.2f}")
            if data['mana_cost']:
                print(f"  Mana Cost: {data['mana_cost']}")
            
            # Show foil availability
            if data.get('foil_available', False):
                print(f"  ✨ FOIL AVAILABLE")
                finishes = data.get('finishes', [])
                print(f"  Finishes: {', '.join(finishes)}")
                foil_price = data['prices'].get('usd_foil', 0.0)
                if foil_price > 0:
                    print(f"  Foil Price: ${foil_price:.2f}")
            else:
                print(f"  ❌ Not available in foil")
        else:
            print("  ❌ No data found")
    
    # Test foil availability checking
    print(f"\n\n✨ Testing Foil Availability Check")
    print("=" * 50)
    foil_test = ["Lightning Bolt", "Sol Ring", "Counterspell"]
    foil_data = scraper.get_bulk_foil_availability(foil_test)
    
    for card, info in foil_data.items():
        if info and info.get('foil_available'):
            print(f"✅ {card}: Foil available (${info.get('foil_price', 0):.2f})")
        else:
            print(f"❌ {card}: No foil version")
    
    # Test search functionality
    print(f"\n🔎 Testing search: 'lightning'")
    search_results = scraper.search_cards('lightning', unique=True)
    print(f"Found {len(search_results)} cards")
    for card in search_results[:3]:  # Show first 3
        price = card['prices']['primary_market_price']
        foil_status = "✨" if card.get('foil_available') else "❌"
        print(f"  {foil_status} {card['name']} - ${price:.2f}")
    
    # Test advanced search builder
    print(f"\n\n🔍 Testing Advanced Search Builder")
    print("=" * 50)
    
    # Example 1: Red creatures in Standard
    print("\n1. Red creatures in Standard:")
    query1 = scraper.build_advanced_query(colors='r', type_line='creature', format='standard')
    print(f"   Query: {query1}")
    
    # Example 2: Budget commander options
    print("\n2. Budget Commanders (<=10 USD):")
    query2 = scraper.build_advanced_query(is_commander=True, price_usd='<=10')
    print(f"   Query: {query2}")
    
    # Example 3: High-value foils
    print("\n3. High-value foil cards:")
    query3 = scraper.build_advanced_query(is_foil=True, price_usd='>=50', rarity='mythic')
    print(f"   Query: {query3}")
    
    # Example 4: Cards with flying keyword
    print("\n4. Cards with flying in Modern:")
    query4 = scraper.build_advanced_query(keywords='flying', format='modern', cmc='<=3')
    print(f"   Query: {query4}")
    
    print("\n✅ Advanced search syntax ready!")
    print("   Supports: colors, types, text, mana costs, power/toughness,")
    print("   rarity, sets, formats, prices, foil, artist, and more!")


if __name__ == "__main__":
    main()