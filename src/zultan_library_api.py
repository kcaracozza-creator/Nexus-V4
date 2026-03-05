#!/usr/bin/env python3
"""
ZULTAN Library API Extension
=============================
Adds inventory management to ZULTAN:8000 unified API.

This establishes ZULTAN as the SINGLE SOURCE OF TRUTH for inventory.
- Desktop reads from here
- BROK syncs to here
- All sales/additions go through here

Patent Pending - Kevin Caracozza
Version: 3.0 (Feb 2026)
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# ZULTAN library database path
LIBRARY_DB = Path.home() / "training" / "data" / "nexus_library.db"


class LibraryManager:
    """Single source of truth for NEXUS inventory"""

    def __init__(self, db_path: Path = LIBRARY_DB):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"Library database not found: {db_path}")

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(str(self.db_path))

    def get_all_cards(self, limit: int = 10000, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all cards in inventory"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cards
            ORDER BY card_name
            LIMIT ? OFFSET ?
        """, (limit, offset))

        cards = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cards

    def get_card_count(self) -> int:
        """Get total card count"""
        conn = self._get_connection()
        cursor = conn.cursor()
        count = cursor.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        conn.close()
        return count

    def search_cards(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search cards by name"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cards
            WHERE card_name LIKE ?
            ORDER BY card_name
            LIMIT ?
        """, (f"%{query}%", limit))

        cards = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cards

    def get_card_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Get card by scryfall_id"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM cards WHERE scryfall_id = ?", (card_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def add_card(self, card_data: Dict[str, Any]) -> bool:
        """Add card to inventory"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if card already exists
            existing = cursor.execute(
                "SELECT id FROM cards WHERE scryfall_id = ?",
                (card_data.get('scryfall_id'),)
            ).fetchone()

            if existing:
                # Update quantity if it exists
                cursor.execute("""
                    UPDATE cards
                    SET quantity = quantity + ?
                    WHERE scryfall_id = ?
                """, (card_data.get('quantity', 1), card_data.get('scryfall_id')))
            else:
                # Insert new card
                cursor.execute("""
                    INSERT INTO cards (
                        scryfall_id, card_name, set_code, set_name,
                        rarity, quantity, price_usd, image_url,
                        oracle_id, collector_number, added_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    card_data.get('scryfall_id'),
                    card_data.get('card_name'),
                    card_data.get('set_code'),
                    card_data.get('set_name'),
                    card_data.get('rarity'),
                    card_data.get('quantity', 1),
                    card_data.get('price_usd'),
                    card_data.get('image_url'),
                    card_data.get('oracle_id'),
                    card_data.get('collector_number'),
                    datetime.now().isoformat()
                ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            conn.close()
            print(f"[LIBRARY] Add card error: {e}")
            return False

    def remove_card(self, scryfall_id: str, quantity: int = 1) -> bool:
        """Remove card from inventory (or reduce quantity)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get current quantity
            row = cursor.execute(
                "SELECT quantity FROM cards WHERE scryfall_id = ?",
                (scryfall_id,)
            ).fetchone()

            if not row:
                conn.close()
                return False

            current_qty = row[0]

            if current_qty <= quantity:
                # Delete card entirely
                cursor.execute("DELETE FROM cards WHERE scryfall_id = ?", (scryfall_id,))
            else:
                # Reduce quantity
                cursor.execute("""
                    UPDATE cards
                    SET quantity = quantity - ?
                    WHERE scryfall_id = ?
                """, (quantity, scryfall_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            conn.close()
            print(f"[LIBRARY] Remove card error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get library statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        total_cards = cursor.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        total_quantity = cursor.execute("SELECT SUM(quantity) FROM cards").fetchone()[0] or 0

        # Get total value (cards with prices)
        total_value = cursor.execute("""
            SELECT SUM(price_usd * quantity) FROM cards
            WHERE price_usd IS NOT NULL
        """).fetchone()[0] or 0.0

        # Get breakdown by rarity
        rarity_counts = {}
        for row in cursor.execute("SELECT rarity, COUNT(*) FROM cards GROUP BY rarity"):
            rarity_counts[row[0]] = row[1]

        conn.close()

        return {
            'total_unique_cards': total_cards,
            'total_quantity': total_quantity,
            'total_value_usd': round(total_value, 2),
            'rarity_breakdown': rarity_counts
        }

    def sync_from_scan(self, scan_data: Dict[str, Any]) -> bool:
        """Sync scanned card from BROK"""
        # Add card from scanner confirmation
        return self.add_card({
            'scryfall_id': scan_data.get('scryfall_id'),
            'card_name': scan_data.get('name'),
            'set_code': scan_data.get('set_code'),
            'set_name': scan_data.get('set_name'),
            'rarity': scan_data.get('rarity'),
            'quantity': scan_data.get('quantity', 1),
            'price_usd': scan_data.get('price_usd'),
            'image_url': scan_data.get('image_url'),
            'oracle_id': scan_data.get('oracle_id'),
            'collector_number': scan_data.get('collector_number')
        })


# =============================================================================
# Flask API Routes (add to nexus_unified_api.py)
# =============================================================================

def create_library_routes(app, library_manager: LibraryManager):
    """Create Flask routes for library management"""

    @app.route('/api/library/stats', methods=['GET'])
    def library_stats():
        """Get library statistics"""
        stats = library_manager.get_stats()
        return json.dumps(stats), 200, {'Content-Type': 'application/json'}

    @app.route('/api/library/search', methods=['GET'])
    def library_search():
        """Search library inventory"""
        from flask import request
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 100))

        if not query:
            return json.dumps({'error': 'No query provided'}), 400

        results = library_manager.search_cards(query, limit)
        return json.dumps({
            'count': len(results),
            'results': results
        }), 200, {'Content-Type': 'application/json'}

    @app.route('/api/library/all', methods=['GET'])
    def library_all():
        """Get all inventory cards (paginated)"""
        from flask import request
        limit = int(request.args.get('limit', 1000))
        offset = int(request.args.get('offset', 0))

        cards = library_manager.get_all_cards(limit, offset)
        total = library_manager.get_card_count()

        return json.dumps({
            'total': total,
            'count': len(cards),
            'offset': offset,
            'limit': limit,
            'results': cards
        }), 200, {'Content-Type': 'application/json'}

    @app.route('/api/library/card/<scryfall_id>', methods=['GET'])
    def library_get_card(scryfall_id):
        """Get specific card by ID"""
        card = library_manager.get_card_by_id(scryfall_id)
        if card:
            return json.dumps(card), 200, {'Content-Type': 'application/json'}
        else:
            return json.dumps({'error': 'Card not found'}), 404

    @app.route('/api/library/add', methods=['POST'])
    def library_add():
        """Add card to inventory"""
        from flask import request
        card_data = request.get_json()

        if not card_data or 'scryfall_id' not in card_data:
            return json.dumps({'error': 'Invalid card data'}), 400

        success = library_manager.add_card(card_data)
        if success:
            return json.dumps({'success': True}), 200
        else:
            return json.dumps({'error': 'Failed to add card'}), 500

    @app.route('/api/library/remove', methods=['POST'])
    def library_remove():
        """Remove card from inventory"""
        from flask import request
        data = request.get_json()

        scryfall_id = data.get('scryfall_id')
        quantity = data.get('quantity', 1)

        if not scryfall_id:
            return json.dumps({'error': 'No scryfall_id provided'}), 400

        success = library_manager.remove_card(scryfall_id, quantity)
        if success:
            return json.dumps({'success': True}), 200
        else:
            return json.dumps({'error': 'Card not found or removal failed'}), 404

    @app.route('/api/library/sync_scan', methods=['POST'])
    def library_sync_scan():
        """Sync scanned card from BROK"""
        from flask import request
        scan_data = request.get_json()

        if not scan_data:
            return json.dumps({'error': 'No scan data'}), 400

        success = library_manager.sync_from_scan(scan_data)
        if success:
            return json.dumps({'success': True}), 200
        else:
            return json.dumps({'error': 'Sync failed'}), 500


if __name__ == "__main__":
    # Test library manager
    print("Testing Library Manager...")
    lm = LibraryManager()
    stats = lm.get_stats()
    print(f"Total cards: {stats['total_unique_cards']:,}")
    print(f"Total quantity: {stats['total_quantity']:,}")
    print(f"Total value: ${stats['total_value_usd']:,.2f}")
    print(f"Rarity breakdown: {stats['rarity_breakdown']}")
