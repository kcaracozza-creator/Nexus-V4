"""
Scryfall Cache Manager - Download and maintain local cache of Scryfall data
Eliminates slow API calls by storing all card data locally

Features:
- Download complete Scryfall bulk data
- Cache card images locally
- Fast local lookups
- Automatic updates
- Price data caching
"""

import requests
import json
import os
import time
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path


class ScryfallCacheManager:
    """Manage local cache of Scryfall data for fast offline access"""
    
    def __init__(self, cache_dir="E:/MTTGG/SCRYFALL_CACHE"):
        """
        Initialize cache manager
        
        Args:
            cache_dir: Directory to store cached data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache subdirectories
        self.bulk_data_dir = self.cache_dir / "bulk_data"
        self.images_dir = self.cache_dir / "images"
        self.prices_dir = self.cache_dir / "prices"
        
        for directory in [self.bulk_data_dir, self.images_dir, self.prices_dir]:
            directory.mkdir(exist_ok=True)
        
        # Database for fast lookups
        self.db_path = self.cache_dir / "scryfall_cache.db"
        self._init_database()
        
        print(f"✅ Scryfall Cache Manager initialized at {self.cache_dir}")
    
    def _init_database(self):
        """Initialize SQLite database for fast card lookups"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Cards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                set_code TEXT,
                collector_number TEXT,
                mana_cost TEXT,
                cmc REAL,
                type_line TEXT,
                oracle_text TEXT,
                colors TEXT,
                color_identity TEXT,
                keywords TEXT,
                rarity TEXT,
                prices_usd REAL,
                prices_usd_foil REAL,
                image_uri TEXT,
                data_json TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        # Create indexes for fast searches
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON cards(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_set ON cards(set_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_colors ON cards(colors)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON cards(type_line)')
        
        # Metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def download_bulk_data(self, bulk_type='default_cards'):
        """
        Download Scryfall bulk data file
        
        Args:
            bulk_type: Type of bulk data (default_cards, oracle_cards, unique_artwork, etc.)
            
        Returns:
            Path to downloaded file
        """
        print(f"\n📥 Downloading Scryfall bulk data: {bulk_type}")
        
        # Get bulk data download URL
        print("Fetching bulk data info...")
        response = requests.get('https://api.scryfall.com/bulk-data')
        if response.status_code != 200:
            raise Exception(f"Failed to fetch bulk data info: {response.status_code}")
        
        bulk_data_info = response.json()
        
        # Find the requested bulk type
        download_url = None
        file_size = 0
        for item in bulk_data_info['data']:
            if item['type'] == bulk_type:
                download_url = item['download_uri']
                file_size = item['size']
                break
        
        if not download_url:
            raise Exception(f"Bulk type '{bulk_type}' not found")
        
        # Download file
        output_file = self.bulk_data_dir / f"{bulk_type}.json"
        
        print(f"Downloading {file_size / 1024 / 1024:.1f} MB...")
        print(f"This may take several minutes...")
        
        response = requests.get(download_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_file, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Progress indicator
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\rProgress: {percent:.1f}%", end='')
        
        print(f"\n✅ Downloaded to {output_file}")
        
        # Update metadata
        self._update_metadata('last_bulk_download', datetime.now().isoformat())
        self._update_metadata('bulk_type', bulk_type)
        
        return output_file
    
    def load_bulk_data_to_database(self, bulk_file=None):
        """
        Load bulk data into SQLite database for fast lookups
        
        Args:
            bulk_file: Path to bulk data file (if None, uses most recent)
        """
        if bulk_file is None:
            bulk_file = self.bulk_data_dir / "default_cards.json"
        
        if not os.path.exists(bulk_file):
            print("⚠️ Bulk data file not found. Downloading...")
            bulk_file = self.download_bulk_data()
        
        print(f"\n📊 Loading bulk data into database...")
        print(f"Source: {bulk_file}")
        
        with open(bulk_file, 'r', encoding='utf-8') as f:
            cards_data = json.load(f)
        
        print(f"Processing {len(cards_data)} cards...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        batch_size = 1000
        for i, card in enumerate(cards_data):
            try:
                # Extract relevant fields
                card_id = card.get('id', '')
                name = card.get('name', '')
                set_code = card.get('set', '')
                collector_number = card.get('collector_number', '')
                mana_cost = card.get('mana_cost', '')
                cmc = card.get('cmc', 0)
                type_line = card.get('type_line', '')
                oracle_text = card.get('oracle_text', '')
                colors = ','.join(card.get('colors', []))
                color_identity = ','.join(card.get('color_identity', []))
                keywords = ','.join(card.get('keywords', []))
                rarity = card.get('rarity', '')
                
                # Prices
                prices = card.get('prices', {})
                price_usd = float(prices.get('usd', 0) or 0)
                price_usd_foil = float(prices.get('usd_foil', 0) or 0)
                
                # Image URI
                image_uris = card.get('image_uris', {})
                image_uri = image_uris.get('normal', '')
                
                # Full JSON data
                data_json = json.dumps(card)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    card_id, name, set_code, collector_number, mana_cost, cmc,
                    type_line, oracle_text, colors, color_identity, keywords,
                    rarity, price_usd, price_usd_foil, image_uri, data_json,
                    datetime.now().isoformat()
                ))
                
                # Commit in batches
                if (i + 1) % batch_size == 0:
                    conn.commit()
                    print(f"\rProcessed {i + 1}/{len(cards_data)} cards...", end='')
            
            except Exception as e:
                print(f"\n⚠️ Error processing card {name}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ Loaded {len(cards_data)} cards into database")
        self._update_metadata('last_db_update', datetime.now().isoformat())
        self._update_metadata('total_cards', str(len(cards_data)))
    
    def search_cards(self, name=None, colors=None, type_line=None, set_code=None, limit=100):
        """
        Search cards in local database (FAST!)
        
        Args:
            name: Card name (partial match)
            colors: Color filter (e.g., 'W,U' for white/blue)
            type_line: Type filter (e.g., 'Creature')
            set_code: Set code filter
            limit: Max results
            
        Returns:
            List of matching cards
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = "SELECT * FROM cards WHERE 1=1"
        params = []
        
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        
        if colors:
            query += " AND colors LIKE ?"
            params.append(f"%{colors}%")
        
        if type_line:
            query += " AND type_line LIKE ?"
            params.append(f"%{type_line}%")
        
        if set_code:
            query += " AND set_code = ?"
            params.append(set_code)
        
        query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        # Convert to dictionaries
        cards = []
        for row in results:
            cards.append({
                'id': row[0],
                'name': row[1],
                'set_code': row[2],
                'collector_number': row[3],
                'mana_cost': row[4],
                'cmc': row[5],
                'type_line': row[6],
                'oracle_text': row[7],
                'colors': row[8],
                'color_identity': row[9],
                'keywords': row[10],
                'rarity': row[11],
                'prices_usd': row[12],
                'prices_usd_foil': row[13],
                'image_uri': row[14]
            })
        
        return cards
    
    def get_card_by_name(self, name, exact=True):
        """
        Get card by exact name (INSTANT lookup)
        
        Args:
            name: Card name
            exact: If True, exact match only
            
        Returns:
            Card data or None
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if exact:
            cursor.execute("SELECT * FROM cards WHERE name = ? LIMIT 1", (name,))
        else:
            cursor.execute("SELECT * FROM cards WHERE name LIKE ? LIMIT 1", (f"%{name}%",))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'set_code': result[2],
                'collector_number': result[3],
                'mana_cost': result[4],
                'cmc': result[5],
                'type_line': result[6],
                'oracle_text': result[7],
                'colors': result[8].split(',') if result[8] else [],
                'color_identity': result[9].split(',') if result[9] else [],
                'keywords': result[10].split(',') if result[10] else [],
                'rarity': result[11],
                'prices': {
                    'usd': result[12],
                    'usd_foil': result[13]
                },
                'image_uri': result[14],
                'data_json': result[15]
            }
        return None
    
    def download_card_image(self, card_name, image_url=None):
        """
        Download and cache card image locally
        
        Args:
            card_name: Name of card
            image_url: Image URL (if None, looks up from database)
            
        Returns:
            Path to local image file
        """
        # Sanitize filename
        safe_name = "".join(c for c in card_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        image_file = self.images_dir / f"{safe_name}.jpg"
        
        # Check if already cached
        if image_file.exists():
            return image_file
        
        # Get image URL if not provided
        if not image_url:
            card = self.get_card_by_name(card_name)
            if card:
                image_url = card.get('image_uri')
        
        if not image_url:
            return None
        
        # Download image
        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                with open(image_file, 'wb') as f:
                    f.write(response.content)
                return image_file
        except Exception as e:
            print(f"⚠️ Failed to download image for {card_name}: {e}")
        
        return None
    
    def get_cache_stats(self):
        """Get statistics about the cache"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cards")
        total_cards = cursor.fetchone()[0]
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_bulk_download'")
        last_download = cursor.fetchone()
        last_download = last_download[0] if last_download else "Never"
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_db_update'")
        last_update = cursor.fetchone()
        last_update = last_update[0] if last_update else "Never"
        
        conn.close()
        
        # Count cached images
        image_count = len(list(self.images_dir.glob("*.jpg")))
        
        return {
            'total_cards': total_cards,
            'last_download': last_download,
            'last_update': last_update,
            'cached_images': image_count,
            'cache_dir': str(self.cache_dir),
            'db_size_mb': os.path.getsize(self.db_path) / 1024 / 1024 if os.path.exists(self.db_path) else 0
        }
    
    def _update_metadata(self, key, value):
        """Update metadata table"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO metadata VALUES (?, ?, ?)
        ''', (key, value, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def update_cache(self):
        """Download latest data and update cache"""
        print("\n🔄 Updating Scryfall cache...")
        self.download_bulk_data()
        self.load_bulk_data_to_database()
        print("✅ Cache update complete!")
    
    def needs_update(self, max_age_days=7):
        """Check if cache needs updating"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_db_update'")
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True
        
        last_update = datetime.fromisoformat(result[0])
        age = datetime.now() - last_update
        
        return age.days >= max_age_days


if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("SCRYFALL CACHE MANAGER - SETUP")
    print("=" * 60)
    
    cache = ScryfallCacheManager()
    
    # Check if needs initial setup
    stats = cache.get_cache_stats()
    
    if stats['total_cards'] == 0:
        print("\n⚠️ No cached data found. Running initial setup...")
        print("This will download ~200MB of data.")
        
        response = input("\nProceed with download? (yes/no): ")
        if response.lower() == 'yes':
            cache.update_cache()
        else:
            print("Setup cancelled.")
    else:
        print(f"\n✅ Cache already initialized!")
        print(f"   Total cards: {stats['total_cards']:,}")
        print(f"   Last updated: {stats['last_update']}")
        print(f"   Database size: {stats['db_size_mb']:.1f} MB")
        print(f"   Cached images: {stats['cached_images']}")
        
        if cache.needs_update():
            print("\n⚠️ Cache is outdated (>7 days old)")
            response = input("Update now? (yes/no): ")
            if response.lower() == 'yes':
                cache.update_cache()
    
    print("\n✅ Scryfall Cache Manager ready!")
