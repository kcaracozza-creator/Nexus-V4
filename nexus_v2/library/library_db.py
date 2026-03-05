#!/usr/bin/env python3
"""
NEXUS V2 - SQLite Library Database
Replaces 24MB JSON with indexed SQLite for fast queries
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

class LibraryDB:
    """
    SQLite-backed card library with indexed queries.

    **ARCHITECTURE NOTE:**
    - This class should ONLY be used on BROK server (scanner station)
    - Desktop apps should use BrockLibraryClient to access library via API
    - Default db_path is DEPRECATED - always pass explicit path

    Correct usage:
        # On BROK server:
        db = LibraryDB("/mnt/nexus_data/databases/nexus_library.db")

        # On Desktop (PREFERRED):
        from nexus_v2.library.brock_client import BrockLibraryClient
        brock = BrockLibraryClient("http://192.168.1.219:5001")
    """

    _local = threading.local()

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # DEPRECATED: Default path creates local DB on desktop (violates architecture)
            # TODO: Remove this default and require explicit path
            import warnings
            warnings.warn(
                "LibraryDB without db_path is deprecated. "
                "Desktop should use BrockLibraryClient instead. "
                "Server deployments must provide explicit db_path.",
                DeprecationWarning,
                stacklevel=2
            )
            db_path = Path(__file__).parent.parent / "data" / "nexus_library.db"
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        """Initialize database schema with indexes."""
        conn = self._get_conn()

        # Create base table structure (without display columns for existing DBs)
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS cards (
                call_number TEXT PRIMARY KEY,
                box_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                name TEXT NOT NULL,
                set_code TEXT,
                set_name TEXT,
                collector_number TEXT,
                rarity TEXT,
                colors TEXT,
                color_identity TEXT,
                mana_cost TEXT,
                cmc REAL DEFAULT 0,
                type_line TEXT,
                oracle_text TEXT,
                power TEXT,
                toughness TEXT,
                foil INTEGER DEFAULT 0,
                condition TEXT DEFAULT 'NM',
                language TEXT DEFAULT 'en',
                price REAL DEFAULT 0,
                price_foil REAL DEFAULT 0,
                price_source TEXT,
                price_updated TEXT,
                image_url TEXT,
                image_url_small TEXT,
                art_hash TEXT,
                scryfall_id TEXT,
                uuid TEXT,
                cataloged_at TEXT,
                updated_at TEXT,
                notes TEXT,
                display INTEGER DEFAULT 0,
                display_case INTEGER NULL
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_name ON cards(name);
            CREATE INDEX IF NOT EXISTS idx_box_id ON cards(box_id);
            CREATE INDEX IF NOT EXISTS idx_set_code ON cards(set_code);
            CREATE INDEX IF NOT EXISTS idx_scryfall_id ON cards(scryfall_id);
            CREATE INDEX IF NOT EXISTS idx_price ON cards(price);
            CREATE INDEX IF NOT EXISTS idx_name_set ON cards(name, set_code);

            -- Metadata table
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        ''')
        conn.commit()

        # Migration: Add display columns to existing databases FIRST
        self._migrate_display_columns(conn)

        # Migration: Add Yu-Gi-Oh! support columns
        self._migrate_yugioh_columns(conn)

        # Migration: Add marketplace listing status columns
        self._migrate_listing_columns(conn)

        # Create display indexes AFTER migration ensures columns exist
        try:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_display ON cards(display)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_display_case ON cards(display_case)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_card_type ON cards(card_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_listing_status ON cards(listing_status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_listing_id ON cards(listing_id)')
            conn.commit()
        except Exception as e:
            print(f"[WARN] Index creation: {e}")

    def _migrate_display_columns(self, conn):
        """Add display columns if they don't exist (for existing databases)."""
        try:
            cursor = conn.execute("PRAGMA table_info(cards)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'display' not in columns:
                conn.execute("ALTER TABLE cards ADD COLUMN display INTEGER DEFAULT 0")
                print("[OK] Added 'display' column to cards table")

            if 'display_case' not in columns:
                conn.execute("ALTER TABLE cards ADD COLUMN display_case INTEGER NULL")
                print("[OK] Added 'display_case' column to cards table")

            conn.commit()
        except Exception as e:
            print(f"[WARN] Migration check: {e}")

    def _migrate_yugioh_columns(self, conn):
        """Add Yu-Gi-Oh! support columns if they don't exist (for existing databases)."""
        try:
            cursor = conn.execute("PRAGMA table_info(cards)")
            columns = [row[1] for row in cursor.fetchall()]

            yugioh_columns = {
                'card_type': "ALTER TABLE cards ADD COLUMN card_type TEXT DEFAULT 'mtg'",
                'yugioh_id': "ALTER TABLE cards ADD COLUMN yugioh_id INTEGER",
                'yugioh_type': "ALTER TABLE cards ADD COLUMN yugioh_type TEXT",
                'yugioh_race': "ALTER TABLE cards ADD COLUMN yugioh_race TEXT",
                'yugioh_attribute': "ALTER TABLE cards ADD COLUMN yugioh_attribute TEXT",
                'yugioh_atk': "ALTER TABLE cards ADD COLUMN yugioh_atk INTEGER",
                'yugioh_def': "ALTER TABLE cards ADD COLUMN yugioh_def INTEGER",
                'yugioh_level': "ALTER TABLE cards ADD COLUMN yugioh_level INTEGER",
                'yugioh_archetype': "ALTER TABLE cards ADD COLUMN yugioh_archetype TEXT"
            }

            for col_name, sql in yugioh_columns.items():
                if col_name not in columns:
                    conn.execute(sql)
                    print(f"[OK] Added '{col_name}' column for Yu-Gi-Oh! support")

            conn.commit()
        except Exception as e:
            print(f"[WARN] Yu-Gi-Oh! migration check: {e}")

    def _migrate_listing_columns(self, conn):
        """Add marketplace listing status columns if they don't exist."""
        try:
            cursor = conn.execute("PRAGMA table_info(cards)")
            columns = [row[1] for row in cursor.fetchall()]

            listing_columns = {
                'listing_status': "ALTER TABLE cards ADD COLUMN listing_status TEXT DEFAULT 'available'",
                'listing_id': "ALTER TABLE cards ADD COLUMN listing_id TEXT",
                'listed_at': "ALTER TABLE cards ADD COLUMN listed_at TEXT",
                'sold_at': "ALTER TABLE cards ADD COLUMN sold_at TEXT",
                'sold_price': "ALTER TABLE cards ADD COLUMN sold_price REAL"
            }

            for col_name, sql in listing_columns.items():
                if col_name not in columns:
                    conn.execute(sql)
                    print(f"[OK] Added '{col_name}' column for marketplace tracking")

            conn.commit()
        except Exception as e:
            print(f"[WARN] Listing columns migration: {e}")

    def _card_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to card dictionary."""
        d = dict(row)
        # Convert JSON strings back to lists
        if d.get('colors'):
            try:
                d['colors'] = json.loads(d['colors'])
            except:
                d['colors'] = []
        else:
            d['colors'] = []
        if d.get('color_identity'):
            try:
                d['color_identity'] = json.loads(d['color_identity'])
            except:
                d['color_identity'] = []
        else:
            d['color_identity'] = []
        d['foil'] = bool(d.get('foil', 0))
        d['display'] = bool(d.get('display', 0))
        return d

    def _dict_to_params(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """Convert card dict to database parameters."""
        params = card.copy()
        # Convert lists to JSON strings
        if isinstance(params.get('colors'), list):
            params['colors'] = json.dumps(params['colors'])
        if isinstance(params.get('color_identity'), list):
            params['color_identity'] = json.dumps(params['color_identity'])
        params['foil'] = 1 if params.get('foil') else 0
        params['display'] = 1 if params.get('display') else 0
        return params

    # === CRUD Operations ===

    def get(self, call_number: str) -> Optional[Dict[str, Any]]:
        """Get card by call number."""
        conn = self._get_conn()
        row = conn.execute(
            'SELECT * FROM cards WHERE call_number = ?',
            (call_number,)
        ).fetchone()
        return self._card_to_dict(row) if row else None

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all cards as dictionary (for compatibility)."""
        conn = self._get_conn()
        rows = conn.execute('SELECT * FROM cards').fetchall()
        return {row['call_number']: self._card_to_dict(row) for row in rows}

    def add(self, card: Dict[str, Any]) -> bool:
        """Add or update a card."""
        conn = self._get_conn()
        params = self._dict_to_params(card)

        columns = list(params.keys())
        placeholders = ', '.join(['?' for _ in columns])
        updates = ', '.join([f'{col}=excluded.{col}' for col in columns])

        sql = f'''
            INSERT INTO cards ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(call_number) DO UPDATE SET {updates}
        '''
        try:
            conn.execute(sql, [params.get(col) for col in columns])
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to add card: {e}")
            return False

    def delete(self, call_number: str) -> bool:
        """Delete a card."""
        conn = self._get_conn()
        conn.execute('DELETE FROM cards WHERE call_number = ?', (call_number,))
        conn.commit()
        return True

    def count(self) -> int:
        """Get total card count."""
        conn = self._get_conn()
        return conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]

    # === Search Operations ===

    def search_by_name(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search cards by name (partial match)."""
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT * FROM cards WHERE name LIKE ? LIMIT ?',
            (f'%{name}%', limit)
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def search_by_set(self, set_code: str) -> List[Dict[str, Any]]:
        """Get all cards from a set."""
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT * FROM cards WHERE set_code = ? ORDER BY collector_number',
            (set_code,)
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def search_by_box(self, box_id: str) -> List[Dict[str, Any]]:
        """Get all cards in a box."""
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT * FROM cards WHERE box_id = ? ORDER BY position',
            (box_id,)
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def search_by_price_range(self, min_price: float, max_price: float) -> List[Dict[str, Any]]:
        """Find cards in price range."""
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT * FROM cards WHERE price BETWEEN ? AND ? ORDER BY price DESC',
            (min_price, max_price)
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def get_expensive_cards(self, min_price: float = 1.0, limit: int = 100) -> List[Dict[str, Any]]:
        """Get cards above price threshold."""
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT * FROM cards WHERE price >= ? ORDER BY price DESC LIMIT ?',
            (min_price, limit)
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def get_total_value(self) -> float:
        """Calculate total collection value."""
        conn = self._get_conn()
        result = conn.execute('SELECT SUM(price) FROM cards').fetchone()[0]
        return result or 0.0

    # === Display Case Operations ===

    def get_display_cards(self, case_number: int = None) -> List[Dict[str, Any]]:
        """Get all display cards, optionally filtered by case number."""
        conn = self._get_conn()
        if case_number is not None:
            rows = conn.execute(
                'SELECT * FROM cards WHERE display = 1 AND display_case = ? ORDER BY name',
                (case_number,)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM cards WHERE display = 1 ORDER BY display_case, name'
            ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def set_display(self, call_number: str, display: bool, case_number: int = None) -> bool:
        """Set display status for a card."""
        conn = self._get_conn()
        try:
            conn.execute(
                'UPDATE cards SET display = ?, display_case = ? WHERE call_number = ?',
                (1 if display else 0, case_number if display else None, call_number)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to set display: {e}")
            return False

    def get_display_case_contents(self, case_number: int) -> List[Dict[str, Any]]:
        """Get all cards in a specific display case."""
        return self.get_display_cards(case_number)

    def get_display_case_summary(self) -> Dict[int, int]:
        """Get count of cards per display case."""
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT display_case, COUNT(*) as count FROM cards '
            'WHERE display = 1 AND display_case IS NOT NULL '
            'GROUP BY display_case ORDER BY display_case'
        ).fetchall()
        return {row['display_case']: row['count'] for row in rows}

    # === Marketplace Listing Operations ===

    def mark_pending(self, call_number: str, listing_id: str) -> bool:
        """Mark card as pending sale (listed on marketplace)."""
        conn = self._get_conn()
        try:
            conn.execute(
                '''UPDATE cards SET listing_status = 'pending', listing_id = ?,
                   listed_at = ? WHERE call_number = ?''',
                (listing_id, datetime.now().isoformat(), call_number)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to mark pending: {e}")
            return False

    def mark_sold(self, call_number: str, sold_price: float = None) -> bool:
        """Mark card as sold."""
        conn = self._get_conn()
        try:
            conn.execute(
                '''UPDATE cards SET listing_status = 'sold', sold_at = ?,
                   sold_price = ? WHERE call_number = ?''',
                (datetime.now().isoformat(), sold_price, call_number)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to mark sold: {e}")
            return False

    def mark_available(self, call_number: str) -> bool:
        """Mark card as available (cancel listing or return from pending)."""
        conn = self._get_conn()
        try:
            conn.execute(
                '''UPDATE cards SET listing_status = 'available', listing_id = NULL,
                   listed_at = NULL WHERE call_number = ?''',
                (call_number,)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to mark available: {e}")
            return False

    def get_pending_cards(self) -> List[Dict[str, Any]]:
        """Get all cards currently listed for sale (pending)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM cards WHERE listing_status = 'pending' ORDER BY listed_at DESC"
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def get_sold_cards(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get sold cards history."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM cards WHERE listing_status = 'sold' ORDER BY sold_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def get_available_cards(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get cards available for listing (not pending or sold)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM cards WHERE listing_status = 'available' OR listing_status IS NULL LIMIT ?",
            (limit,)
        ).fetchall()
        return [self._card_to_dict(row) for row in rows]

    def get_listing_by_id(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Find card by marketplace listing ID."""
        conn = self._get_conn()
        row = conn.execute(
            'SELECT * FROM cards WHERE listing_id = ?',
            (listing_id,)
        ).fetchone()
        return self._card_to_dict(row) if row else None

    def get_listing_stats(self) -> Dict[str, Any]:
        """Get summary of listing statuses."""
        conn = self._get_conn()
        rows = conn.execute(
            '''SELECT
                COALESCE(listing_status, 'available') as status,
                COUNT(*) as count,
                SUM(price) as value
               FROM cards
               GROUP BY COALESCE(listing_status, 'available')'''
        ).fetchall()
        return {
            row['status']: {'count': row['count'], 'value': row['value'] or 0}
            for row in rows
        }

    # === Metadata Operations ===

    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value."""
        conn = self._get_conn()
        row = conn.execute(
            'SELECT value FROM metadata WHERE key = ?', (key,)
        ).fetchone()
        return row[0] if row else None

    def set_metadata(self, key: str, value: str):
        """Set metadata value."""
        conn = self._get_conn()
        conn.execute(
            'INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.commit()

    # === Migration ===

    def import_from_json(self, json_path: Path) -> int:
        """Import cards from JSON library file."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        library = data.get('library', {})
        conn = self._get_conn()

        # Batch insert for performance
        count = 0
        for call_number, card in library.items():
            card['call_number'] = call_number
            params = self._dict_to_params(card)

            columns = list(params.keys())
            placeholders = ', '.join(['?' for _ in columns])

            try:
                conn.execute(
                    f'INSERT OR REPLACE INTO cards ({", ".join(columns)}) VALUES ({placeholders})',
                    [params.get(col) for col in columns]
                )
                count += 1
            except Exception as e:
                print(f"[WARN] Skipped {call_number}: {e}")

        # Store metadata
        if 'metadata' in data:
            self.set_metadata('original_metadata', json.dumps(data['metadata']))

        self.set_metadata('imported_at', datetime.now().isoformat())
        self.set_metadata('source_file', str(json_path))

        conn.commit()
        return count

    def export_to_json(self, json_path: Path) -> int:
        """Export library back to JSON format."""
        library = self.get_all()

        # Get original metadata if available
        meta_str = self.get_metadata('original_metadata')
        metadata = json.loads(meta_str) if meta_str else {}

        data = {
            'library': library,
            'metadata': metadata
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return len(library)

    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# === Migration Script ===

def migrate_json_to_sqlite():
    """Migrate existing JSON library to SQLite."""
    data_dir = Path(__file__).parent.parent / "data"
    json_path = data_dir / "nexus_library.json"
    db_path = data_dir / "nexus_library.db"

    if not json_path.exists():
        print(f"[ERROR] JSON library not found: {json_path}")
        return False

    print(f"[INFO] Migrating {json_path} to SQLite...")

    # Create database
    db = LibraryDB(db_path)

    # Import data
    count = db.import_from_json(json_path)

    print(f"[SUCCESS] Migrated {count} cards to {db_path}")
    print(f"[INFO] Database size: {db_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Verify
    total = db.count()
    value = db.get_total_value()
    print(f"[INFO] Verification: {total} cards, ${value:.2f} total value")

    db.close()
    return True


if __name__ == '__main__':
    migrate_json_to_sqlite()
