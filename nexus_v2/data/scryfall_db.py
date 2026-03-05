"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SCRYFALL DATABASE - NEXUS V2                               ║
║                                                                               ║
║   Bulk JSON loader with SQLite indexing for instant card lookups             ║
║   Handles foil vs non-foil pricing, image URIs for hover display             ║
║                                                                               ║
║   Usage:                                                                      ║
║     db = ScryfallDatabase("E:/MTTGG/cards.json")                             ║
║     card = db.get_card("Lightning Bolt", "M15", "144")                        ║
║     price = card['prices']['usd']  # or 'usd_foil'                           ║
║     image = card['image_uris']['normal']                                      ║
║                                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
import threading


@dataclass
class ScryfallCard:
    """Represents a card from Scryfall database"""
    scryfall_id: str
    name: str
    set_code: str
    set_name: str
    collector_number: str
    rarity: str
    colors: List[str]
    color_identity: List[str]
    mana_cost: str
    cmc: float
    type_line: str
    oracle_text: str
    keywords: List[str]
    
    # Prices - separate for foil/non-foil
    price_usd: Optional[float] = None
    price_usd_foil: Optional[float] = None
    price_eur: Optional[float] = None
    price_eur_foil: Optional[float] = None
    price_tix: Optional[float] = None
    
    # Images
    image_uri_small: Optional[str] = None
    image_uri_normal: Optional[str] = None
    image_uri_large: Optional[str] = None
    image_uri_art_crop: Optional[str] = None
    image_uri_border_crop: Optional[str] = None
    image_uri_png: Optional[str] = None
    
    # Additional metadata
    layout: str = "normal"
    released_at: Optional[str] = None
    foil: bool = True  # Can this card exist as foil?
    nonfoil: bool = True  # Can this card exist as non-foil?
    
    # Full JSON for any fields we didn't extract
    raw_json: Optional[str] = None
    
    def get_price(self, foil: bool = False) -> Optional[float]:
        """Get price for foil or non-foil version"""
        if foil:
            return self.price_usd_foil
        return self.price_usd
    
    def get_image_uri(self, size: str = "normal") -> Optional[str]:
        """Get image URI by size (small, normal, large, art_crop, border_crop, png)"""
        size_map = {
            'small': self.image_uri_small,
            'normal': self.image_uri_normal,
            'large': self.image_uri_large,
            'art_crop': self.image_uri_art_crop,
            'border_crop': self.image_uri_border_crop,
            'png': self.image_uri_png
        }
        return size_map.get(size, self.image_uri_normal)


class ScryfallDatabase:
    """
    High-performance Scryfall bulk data database.
    
    Loads cards.json once, indexes in SQLite for instant lookups.
    Handles foil vs non-foil pricing, provides image URIs.
    """
    
    # Database schema version - increment to force rebuild
    SCHEMA_VERSION = 2
    
    def __init__(self, 
                 bulk_json_path: str = "E:/MTTGG/cards.json",
                 cache_dir: str = None,
                 auto_load: bool = True):
        """
        Initialize Scryfall database.
        
        Args:
            bulk_json_path: Path to Scryfall bulk cards.json
            cache_dir: Directory for SQLite cache (default: same as JSON)
            auto_load: Automatically load/build database on init
        """
        self.bulk_json_path = Path(bulk_json_path)
        
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = self.bulk_json_path.parent
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite database path
        self.db_path = self.cache_dir / "scryfall_indexed.db"
        
        # Thread-local connections
        self._local = threading.local()
        
        # Statistics
        self.total_cards = 0
        self.unique_sets = 0
        self.last_loaded = None
        
        if auto_load:
            self._ensure_database()
    
    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _ensure_database(self):
        """Ensure database exists and is up-to-date"""
        needs_rebuild = False
        
        if not self.db_path.exists():
            print("[SCRYFALL] Scryfall database not found, building...")
            needs_rebuild = True
        else:
            # Check schema version
            try:
                cursor = self._conn.cursor()
                cursor.execute("SELECT value FROM metadata WHERE key = 'schema_version'")
                row = cursor.fetchone()
                if not row or int(row[0]) < self.SCHEMA_VERSION:
                    print("[SCRYFALL] Scryfall database outdated, rebuilding...")
                    needs_rebuild = True
            except sqlite3.OperationalError:
                needs_rebuild = True
        
        if needs_rebuild:
            self._build_database()
        else:
            self._load_stats()
    
    def _build_database(self):
        """Build SQLite database from bulk JSON"""
        print(f"[SCRYFALL] Loading Scryfall bulk data from: {self.bulk_json_path}")
        
        if not self.bulk_json_path.exists():
            raise FileNotFoundError(f"Scryfall bulk data not found: {self.bulk_json_path}")
        
        # Drop existing database
        if self.db_path.exists():
            os.remove(str(self.db_path))
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create tables
        self._create_tables(cursor)
        
        # Load JSON
        print("   Reading JSON file...")
        with open(self.bulk_json_path, 'r', encoding='utf-8') as f:
            cards = json.load(f)
        
        print(f"   Found {len(cards):,} cards")
        
        # Insert cards in batches
        batch_size = 5000
        total = len(cards)
        inserted = 0
        sets_seen = set()
        
        print("   Indexing cards...")
        for i in range(0, total, batch_size):
            batch = cards[i:i + batch_size]
            
            for card in batch:
                self._insert_card(cursor, card)
                sets_seen.add(card.get('set', ''))
            
            inserted += len(batch)
            progress = (inserted / total) * 100
            print(f"   Progress: {progress:.1f}% ({inserted:,}/{total:,})")
            conn.commit()
        
        # Store metadata
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        """, ('schema_version', str(self.SCHEMA_VERSION), datetime.now().isoformat()))
        
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        """, ('total_cards', str(inserted), datetime.now().isoformat()))
        
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        """, ('unique_sets', str(len(sets_seen)), datetime.now().isoformat()))
        
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        """, ('built_from', str(self.bulk_json_path), datetime.now().isoformat()))
        
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        """, ('built_at', datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        self.total_cards = inserted
        self.unique_sets = len(sets_seen)
        self.last_loaded = datetime.now()
        
        print(f"[OK] Scryfall database built: {inserted:,} cards from {len(sets_seen)} sets")
    
    def _create_tables(self, cursor):
        """Create database tables with proper indexes"""
        
        # Main cards table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                scryfall_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                set_code TEXT NOT NULL,
                set_name TEXT,
                collector_number TEXT NOT NULL,
                rarity TEXT,
                colors TEXT,
                color_identity TEXT,
                mana_cost TEXT,
                cmc REAL,
                type_line TEXT,
                oracle_text TEXT,
                keywords TEXT,
                
                -- Prices (NULL if not available)
                price_usd REAL,
                price_usd_foil REAL,
                price_eur REAL,
                price_eur_foil REAL,
                price_tix REAL,
                
                -- Image URIs
                image_small TEXT,
                image_normal TEXT,
                image_large TEXT,
                image_art_crop TEXT,
                image_border_crop TEXT,
                image_png TEXT,
                
                -- Metadata
                layout TEXT,
                released_at TEXT,
                foil INTEGER,
                nonfoil INTEGER,
                
                -- Raw JSON for anything else needed
                raw_json TEXT
            )
        """)
        
        # Indexes for fast lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON cards(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_lower ON cards(LOWER(name))")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_set_code ON cards(set_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_set_collector ON cards(set_code, collector_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rarity ON cards(rarity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON cards(type_line)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmc ON cards(cmc)")
        
        # Metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
    
    def _insert_card(self, cursor, card: dict):
        """Insert a single card into the database"""
        
        # Extract image URIs (handle different layouts)
        image_uris = card.get('image_uris', {})
        if not image_uris and 'card_faces' in card:
            # Double-faced cards - use front face image
            faces = card.get('card_faces', [])
            if faces:
                image_uris = faces[0].get('image_uris', {})
        
        # Extract prices
        prices = card.get('prices', {})
        
        def parse_price(val):
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        
        # Extract colors as comma-separated
        colors = ','.join(card.get('colors', []))
        color_identity = ','.join(card.get('color_identity', []))
        keywords = ','.join(card.get('keywords', []))
        
        cursor.execute("""
            INSERT OR REPLACE INTO cards VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?
            )
        """, (
            card.get('id', ''),
            card.get('name', ''),
            card.get('set', ''),
            card.get('set_name', ''),
            card.get('collector_number', ''),
            card.get('rarity', ''),
            colors,
            color_identity,
            card.get('mana_cost', ''),
            card.get('cmc', 0),
            card.get('type_line', ''),
            card.get('oracle_text', ''),
            keywords,
            
            parse_price(prices.get('usd')),
            parse_price(prices.get('usd_foil')),
            parse_price(prices.get('eur')),
            parse_price(prices.get('eur_foil')),
            parse_price(prices.get('tix')),
            
            image_uris.get('small'),
            image_uris.get('normal'),
            image_uris.get('large'),
            image_uris.get('art_crop'),
            image_uris.get('border_crop'),
            image_uris.get('png'),
            
            card.get('layout', 'normal'),
            card.get('released_at'),
            1 if card.get('foil', True) else 0,
            1 if card.get('nonfoil', True) else 0,
            
            json.dumps(card)  # Store full JSON for anything else
        ))
    
    def _load_stats(self):
        """Load statistics from database"""
        cursor = self._conn.cursor()
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'total_cards'")
        row = cursor.fetchone()
        self.total_cards = int(row[0]) if row else 0
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'unique_sets'")
        row = cursor.fetchone()
        self.unique_sets = int(row[0]) if row else 0
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'built_at'")
        row = cursor.fetchone()
        self.last_loaded = row[0] if row else None
    
    def _row_to_card(self, row: sqlite3.Row) -> ScryfallCard:
        """Convert database row to ScryfallCard object"""
        colors = row['colors'].split(',') if row['colors'] else []
        color_identity = row['color_identity'].split(',') if row['color_identity'] else []
        keywords = row['keywords'].split(',') if row['keywords'] else []
        
        return ScryfallCard(
            scryfall_id=row['scryfall_id'],
            name=row['name'],
            set_code=row['set_code'],
            set_name=row['set_name'],
            collector_number=row['collector_number'],
            rarity=row['rarity'],
            colors=colors,
            color_identity=color_identity,
            mana_cost=row['mana_cost'],
            cmc=row['cmc'],
            type_line=row['type_line'],
            oracle_text=row['oracle_text'],
            keywords=keywords,
            
            price_usd=row['price_usd'],
            price_usd_foil=row['price_usd_foil'],
            price_eur=row['price_eur'],
            price_eur_foil=row['price_eur_foil'],
            price_tix=row['price_tix'],
            
            image_uri_small=row['image_small'],
            image_uri_normal=row['image_normal'],
            image_uri_large=row['image_large'],
            image_uri_art_crop=row['image_art_crop'],
            image_uri_border_crop=row['image_border_crop'],
            image_uri_png=row['image_png'],
            
            layout=row['layout'],
            released_at=row['released_at'],
            foil=bool(row['foil']),
            nonfoil=bool(row['nonfoil']),
            
            raw_json=row['raw_json']
        )
    
    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert database row to dictionary"""
        return {
            'scryfall_id': row['scryfall_id'],
            'name': row['name'],
            'set_code': row['set_code'],
            'set_name': row['set_name'],
            'collector_number': row['collector_number'],
            'rarity': row['rarity'],
            'colors': row['colors'].split(',') if row['colors'] else [],
            'color_identity': row['color_identity'].split(',') if row['color_identity'] else [],
            'mana_cost': row['mana_cost'],
            'cmc': row['cmc'],
            'type_line': row['type_line'],
            'oracle_text': row['oracle_text'],
            'keywords': row['keywords'].split(',') if row['keywords'] else [],
            'prices': {
                'usd': row['price_usd'],
                'usd_foil': row['price_usd_foil'],
                'eur': row['price_eur'],
                'eur_foil': row['price_eur_foil'],
                'tix': row['price_tix']
            },
            'image_uris': {
                'small': row['image_small'],
                'normal': row['image_normal'],
                'large': row['image_large'],
                'art_crop': row['image_art_crop'],
                'border_crop': row['image_border_crop'],
                'png': row['image_png']
            },
            'layout': row['layout'],
            'released_at': row['released_at'],
            'foil': bool(row['foil']),
            'nonfoil': bool(row['nonfoil'])
        }
    
    # ═══════════════════════════════════════════════════════════════════
    # LOOKUP METHODS
    # ═══════════════════════════════════════════════════════════════════
    
    def get_card(self, 
                 name: str, 
                 set_code: str = None, 
                 collector_number: str = None,
                 as_dict: bool = True) -> Optional[Any]:
        """
        Get a card by name, optionally filtered by set and collector number.
        
        This is the PRIMARY lookup method - use this for matching scanned cards.
        
        Args:
            name: Card name (case-insensitive)
            set_code: Optional set code (e.g., "M15", "LEA")
            collector_number: Optional collector number (e.g., "144")
            as_dict: Return as dict (True) or ScryfallCard object (False)
        
        Returns:
            Card data or None if not found
        """
        cursor = self._conn.cursor()
        
        if set_code and collector_number:
            # Exact match by set + collector number
            cursor.execute("""
                SELECT * FROM cards 
                WHERE LOWER(name) = LOWER(?) 
                  AND LOWER(set_code) = LOWER(?)
                  AND collector_number = ?
                LIMIT 1
            """, (name, set_code, collector_number))
        elif set_code:
            # Match by name + set
            cursor.execute("""
                SELECT * FROM cards 
                WHERE LOWER(name) = LOWER(?) 
                  AND LOWER(set_code) = LOWER(?)
                LIMIT 1
            """, (name, set_code))
        else:
            # Match by name only (returns first match)
            cursor.execute("""
                SELECT * FROM cards 
                WHERE LOWER(name) = LOWER(?)
                LIMIT 1
            """, (name,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return self._row_to_dict(row) if as_dict else self._row_to_card(row)
    
    def get_card_by_id(self, scryfall_id: str, as_dict: bool = True) -> Optional[Any]:
        """Get card by Scryfall ID (UUID)"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE scryfall_id = ?", (scryfall_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return self._row_to_dict(row) if as_dict else self._row_to_card(row)
    
    def search_cards(self, 
                     query: str, 
                     limit: int = 50,
                     as_dict: bool = True) -> List[Any]:
        """
        Search cards by name (partial match, case-insensitive).
        
        Args:
            query: Search string
            limit: Maximum results to return
            as_dict: Return as dicts (True) or ScryfallCard objects (False)
        
        Returns:
            List of matching cards
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM cards 
            WHERE name LIKE ?
            ORDER BY name
            LIMIT ?
        """, (f"%{query}%", limit))
        
        rows = cursor.fetchall()
        
        if as_dict:
            return [self._row_to_dict(row) for row in rows]
        else:
            return [self._row_to_card(row) for row in rows]
    
    def get_legendary_creatures(self, limit: int = 10000, as_dict: bool = True) -> List[Any]:
        """
        Get all legendary creatures (valid commanders).
        
        Args:
            limit: Maximum results
            as_dict: Return as dicts (True) or ScryfallCard objects (False)
        
        Returns:
            List of legendary creatures
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM cards 
            WHERE type_line LIKE '%Legendary%Creature%'
            ORDER BY name
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        
        if as_dict:
            return [self._row_to_dict(row) for row in rows]
        else:
            return [self._row_to_card(row) for row in rows]

    def get_all_printings(self, 
                          name: str, 
                          as_dict: bool = True) -> List[Any]:
        """
        Get all printings of a card across all sets.
        
        Useful for finding different versions/prices of the same card.
        
        Args:
            name: Exact card name
            as_dict: Return as dicts (True) or ScryfallCard objects (False)
        
        Returns:
            List of all printings
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM cards 
            WHERE LOWER(name) = LOWER(?)
            ORDER BY released_at DESC
        """, (name,))
        
        rows = cursor.fetchall()
        
        if as_dict:
            return [self._row_to_dict(row) for row in rows]
        else:
            return [self._row_to_card(row) for row in rows]
    
    def get_price(self, 
                  name: str, 
                  set_code: str = None, 
                  collector_number: str = None,
                  foil: bool = False) -> Optional[float]:
        """
        Quick price lookup.
        
        Args:
            name: Card name
            set_code: Optional set code
            collector_number: Optional collector number
            foil: Get foil price (True) or regular price (False)
        
        Returns:
            Price in USD or None
        """
        card = self.get_card(name, set_code, collector_number)
        if not card:
            return None
        
        if foil:
            return card['prices'].get('usd_foil')
        return card['prices'].get('usd')
    
    def get_image_uri(self,
                      name: str,
                      set_code: str = None,
                      collector_number: str = None,
                      size: str = "normal") -> Optional[str]:
        """
        Quick image URI lookup.
        
        Args:
            name: Card name
            set_code: Optional set code
            collector_number: Optional collector number
            size: Image size (small, normal, large, art_crop, border_crop, png)
        
        Returns:
            Image URI or None
        """
        card = self.get_card(name, set_code, collector_number)
        if not card:
            return None
        
        return card['image_uris'].get(size)
    
    # ═══════════════════════════════════════════════════════════════════
    # SET / FILTER METHODS
    # ═══════════════════════════════════════════════════════════════════
    
    def get_all_sets(self) -> List[Tuple[str, str]]:
        """Get all unique sets as (set_code, set_name) tuples"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT DISTINCT set_code, set_name 
            FROM cards 
            ORDER BY set_name
        """)
        return [(row[0], row[1]) for row in cursor.fetchall()]
    
    def get_cards_by_set(self, 
                         set_code: str, 
                         as_dict: bool = True) -> List[Any]:
        """Get all cards in a set"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM cards 
            WHERE LOWER(set_code) = LOWER(?)
            ORDER BY CAST(collector_number AS INTEGER)
        """, (set_code,))
        
        rows = cursor.fetchall()
        
        if as_dict:
            return [self._row_to_dict(row) for row in rows]
        else:
            return [self._row_to_card(row) for row in rows]
    
    def get_cards_by_rarity(self, 
                            rarity: str, 
                            limit: int = 100,
                            as_dict: bool = True) -> List[Any]:
        """Get cards by rarity (common, uncommon, rare, mythic)"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM cards 
            WHERE LOWER(rarity) = LOWER(?)
            ORDER BY name
            LIMIT ?
        """, (rarity, limit))
        
        rows = cursor.fetchall()
        
        if as_dict:
            return [self._row_to_dict(row) for row in rows]
        else:
            return [self._row_to_card(row) for row in rows]
    
    # ═══════════════════════════════════════════════════════════════════
    # PRICE UPDATE METHODS
    # ═══════════════════════════════════════════════════════════════════
    
    def update_prices(self, updates: Dict[str, Dict[str, float]]):
        """
        Bulk update prices from fresh Scryfall data.
        
        Args:
            updates: Dict of scryfall_id -> {usd, usd_foil, eur, eur_foil, tix}
        """
        cursor = self._conn.cursor()
        
        for scryfall_id, prices in updates.items():
            cursor.execute("""
                UPDATE cards SET
                    price_usd = ?,
                    price_usd_foil = ?,
                    price_eur = ?,
                    price_eur_foil = ?,
                    price_tix = ?
                WHERE scryfall_id = ?
            """, (
                prices.get('usd'),
                prices.get('usd_foil'),
                prices.get('eur'),
                prices.get('eur_foil'),
                prices.get('tix'),
                scryfall_id
            ))
        
        self._conn.commit()
        print(f"[PRICE] Updated prices for {len(updates)} cards")
    
    # ═══════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        cursor = self._conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cards")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT set_code) FROM cards")
        sets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM cards WHERE price_usd IS NOT NULL")
        priced = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM cards WHERE image_normal IS NOT NULL")
        with_images = cursor.fetchone()[0]
        
        return {
            'total_cards': total,
            'unique_sets': sets,
            'cards_with_prices': priced,
            'cards_with_images': with_images,
            'database_path': str(self.db_path),
            'database_size_mb': os.path.getsize(str(self.db_path)) / (1024 * 1024) if self.db_path.exists() else 0,
            'last_loaded': self.last_loaded
        }
    
    def rebuild(self):
        """Force rebuild database from JSON"""
        print("[REBUILD] Forcing database rebuild...")
        self._build_database()


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════

_scryfall_db: Optional[ScryfallDatabase] = None


def get_scryfall_db(json_path: str = "E:/MTTGG/cards.json") -> ScryfallDatabase:
    """Get or create the singleton Scryfall database instance"""
    global _scryfall_db
    
    if _scryfall_db is None:
        _scryfall_db = ScryfallDatabase(json_path)
    
    return _scryfall_db


# ═══════════════════════════════════════════════════════════════════════════
# DEMO / TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("  SCRYFALL DATABASE - TEST")
    print("═" * 60)
    
    # Try to load database
    try:
        db = ScryfallDatabase()
        
        stats = db.get_stats()
        print(f"\n[STATS] Database Stats:")
        print(f"   Total cards: {stats['total_cards']:,}")
        print(f"   Unique sets: {stats['unique_sets']}")
        print(f"   Cards with prices: {stats['cards_with_prices']:,}")
        print(f"   Cards with images: {stats['cards_with_images']:,}")
        print(f"   Database size: {stats['database_size_mb']:.1f} MB")
        
        # Test lookup
        card = db.get_card("Lightning Bolt")
        if card:
            print(f"\n[TEST] Test lookup - Lightning Bolt:")
            print(f"   Set: {card['set_code']} ({card['set_name']})")
            print(f"   Rarity: {card['rarity']}")
            print(f"   Price (USD): ${card['prices']['usd'] or 'N/A'}")
            print(f"   Price (Foil): ${card['prices']['usd_foil'] or 'N/A'}")
            print(f"   Image: {card['image_uris']['normal'][:50]}..." if card['image_uris']['normal'] else "   Image: N/A")
        
        print("\n[OK] Scryfall database ready!")
        
    except FileNotFoundError as e:
        print(f"\n[WARNING] {e}")
        print("   Place cards.json in E:/MTTGG/ or specify path")
