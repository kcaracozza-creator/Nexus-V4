#!/usr/bin/env python3
"""
BROK Library API Server
=======================
Master inventory database API for NEXUS V3.

This runs on BROK (192.168.1.174) and serves as the SINGLE SOURCE OF TRUTH
for the client's physical card inventory.

Deploy to BROK:
    scp brok_library_server.py nexus1@192.168.1.174:~/
    ssh nexus1@192.168.1.174
    python3 brok_library_server.py --port 5002

Patent Pending - Kevin Caracozza
Version: 3.0 (Feb 2026)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
from pathlib import Path
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database path (will be detected or configured)
DEFAULT_DB_PATH = Path.home() / "nexus_library.db"

app = Flask(__name__)
CORS(app)  # Allow desktop to connect


class InventoryDatabase:
    """BROK master inventory database"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_schema()
        logger.info(f"[INVENTORY] Using database: {self.db_path}")

    def _ensure_schema(self):
        """Ensure database schema exists"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create cards table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scryfall_id TEXT UNIQUE NOT NULL,
                card_name TEXT NOT NULL,
                set_code TEXT,
                set_name TEXT,
                rarity TEXT,
                quantity INTEGER DEFAULT 1,
                price_usd REAL,
                image_url TEXT,
                oracle_id TEXT,
                collector_number TEXT,
                added_date TEXT,
                last_updated TEXT
            )
        """)

        # Create sales log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_date TEXT NOT NULL,
                card_name TEXT,
                scryfall_id TEXT,
                quantity INTEGER,
                sale_price REAL,
                buyer_info TEXT,
                notes TEXT
            )
        """)

        # Create scan history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT NOT NULL,
                card_name TEXT,
                scryfall_id TEXT,
                confidence REAL,
                added_to_inventory INTEGER DEFAULT 1
            )
        """)

        conn.commit()
        conn.close()
        logger.info("[INVENTORY] Schema verified")

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_cards(self, limit=10000, offset=0):
        """Get all inventory cards"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cards
            ORDER BY card_name
            LIMIT ? OFFSET ?
        """, (limit, offset))

        cards = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cards

    def get_card_count(self):
        """Get total card count"""
        conn = self.get_connection()
        cursor = conn.cursor()
        count = cursor.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        total_qty = cursor.execute("SELECT SUM(quantity) FROM cards").fetchone()[0] or 0
        conn.close()
        return {'unique_cards': count, 'total_quantity': total_qty}

    def search_cards(self, query, limit=100):
        """Search cards by name"""
        conn = self.get_connection()
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

    def add_card(self, card_data):
        """Add or update card in inventory"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Check if card exists
            existing = cursor.execute(
                "SELECT quantity FROM cards WHERE scryfall_id = ?",
                (card_data['scryfall_id'],)
            ).fetchone()

            if existing:
                # Update quantity
                new_qty = existing[0] + card_data.get('quantity', 1)
                cursor.execute("""
                    UPDATE cards
                    SET quantity = ?,
                        last_updated = ?
                    WHERE scryfall_id = ?
                """, (new_qty, datetime.now().isoformat(), card_data['scryfall_id']))
                logger.info(f"[INVENTORY] Updated {card_data['card_name']} qty: {new_qty}")
            else:
                # Insert new card
                cursor.execute("""
                    INSERT INTO cards (
                        scryfall_id, card_name, set_code, set_name,
                        rarity, quantity, price_usd, image_url,
                        oracle_id, collector_number, added_date, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    card_data['scryfall_id'],
                    card_data['card_name'],
                    card_data.get('set_code'),
                    card_data.get('set_name'),
                    card_data.get('rarity'),
                    card_data.get('quantity', 1),
                    card_data.get('price_usd'),
                    card_data.get('image_url'),
                    card_data.get('oracle_id'),
                    card_data.get('collector_number'),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                logger.info(f"[INVENTORY] Added {card_data['card_name']}")

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"[INVENTORY] Add card error: {e}")
            conn.close()
            return False

    def remove_card(self, scryfall_id, quantity=1):
        """Remove card from inventory"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Get current quantity
            row = cursor.execute(
                "SELECT quantity, card_name FROM cards WHERE scryfall_id = ?",
                (scryfall_id,)
            ).fetchone()

            if not row:
                conn.close()
                return False

            current_qty = row[0]
            card_name = row[1]

            if current_qty <= quantity:
                # Delete card
                cursor.execute("DELETE FROM cards WHERE scryfall_id = ?", (scryfall_id,))
                logger.info(f"[INVENTORY] Removed {card_name} (all)")
            else:
                # Reduce quantity
                new_qty = current_qty - quantity
                cursor.execute("""
                    UPDATE cards
                    SET quantity = ?,
                        last_updated = ?
                    WHERE scryfall_id = ?
                """, (new_qty, datetime.now().isoformat(), scryfall_id))
                logger.info(f"[INVENTORY] Removed {quantity}x {card_name}, {new_qty} remaining")

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"[INVENTORY] Remove card error: {e}")
            conn.close()
            return False

    def log_sale(self, sale_data):
        """Log a sale to history"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sales_log (
                sale_date, card_name, scryfall_id, quantity,
                sale_price, buyer_info, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            sale_data.get('card_name'),
            sale_data.get('scryfall_id'),
            sale_data.get('quantity'),
            sale_data.get('sale_price'),
            sale_data.get('buyer_info'),
            sale_data.get('notes')
        ))

        conn.commit()
        conn.close()
        logger.info(f"[SALES] Logged: {sale_data.get('card_name')}")

    def get_stats(self):
        """Get inventory statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        unique_cards = cursor.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        total_qty = cursor.execute("SELECT SUM(quantity) FROM cards").fetchone()[0] or 0
        total_value = cursor.execute(
            "SELECT SUM(price_usd * quantity) FROM cards WHERE price_usd IS NOT NULL"
        ).fetchone()[0] or 0.0

        # Rarity breakdown
        rarity_counts = {}
        for row in cursor.execute("SELECT rarity, COUNT(*), SUM(quantity) FROM cards GROUP BY rarity"):
            rarity_counts[row[0] or 'unknown'] = {'unique': row[1], 'total': row[2]}

        conn.close()

        return {
            'unique_cards': unique_cards,
            'total_quantity': total_qty,
            'total_value_usd': round(total_value, 2),
            'rarity_breakdown': rarity_counts
        }


# Global database instance
db = None


# =============================================================================
# Flask Routes
# =============================================================================

@app.route('/api/library/health', methods=['GET'])
def health():
    """Health check"""
    count = db.get_card_count()
    return jsonify({
        'status': 'online',
        'service': 'brok-library-api',
        'unique_cards': count['unique_cards'],
        'total_quantity': count['total_quantity']
    })


@app.route('/api/library/all', methods=['GET'])
def get_all():
    """Get all cards (paginated)"""
    limit = int(request.args.get('limit', 1000))
    offset = int(request.args.get('offset', 0))

    cards = db.get_all_cards(limit, offset)
    count = db.get_card_count()

    return jsonify({
        'total': count['unique_cards'],
        'total_quantity': count['total_quantity'],
        'count': len(cards),
        'offset': offset,
        'limit': limit,
        'results': cards
    })


@app.route('/api/library/search', methods=['GET'])
def search():
    """Search cards"""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 100))

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    results = db.search_cards(query, limit)
    return jsonify({
        'count': len(results),
        'results': results
    })


@app.route('/api/library/stats', methods=['GET'])
def stats():
    """Get inventory statistics"""
    stats = db.get_stats()
    return jsonify(stats)


@app.route('/api/library/add', methods=['POST'])
def add_card():
    """Add card to inventory"""
    card_data = request.get_json()

    if not card_data or 'scryfall_id' not in card_data:
        return jsonify({'error': 'Invalid card data'}), 400

    success = db.add_card(card_data)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to add card'}), 500


@app.route('/api/library/remove', methods=['POST'])
def remove_card():
    """Remove card from inventory"""
    data = request.get_json()

    scryfall_id = data.get('scryfall_id')
    quantity = data.get('quantity', 1)

    if not scryfall_id:
        return jsonify({'error': 'No scryfall_id provided'}), 400

    success = db.remove_card(scryfall_id, quantity)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Card not found'}), 404


@app.route('/api/sales/log', methods=['POST'])
def log_sale():
    """Log a sale"""
    sale_data = request.get_json()

    if not sale_data:
        return jsonify({'error': 'No sale data'}), 400

    db.log_sale(sale_data)
    return jsonify({'success': True})


# =============================================================================
# Main
# =============================================================================

def main():
    global db

    parser = argparse.ArgumentParser(description='BROK Library API Server')
    parser.add_argument('--port', type=int, default=5002, help='Port to run on')
    parser.add_argument('--db', type=str, help='Database path (default: ~/nexus_library.db)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    args = parser.parse_args()

    # Determine database path
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    # Initialize database
    db = InventoryDatabase(db_path)

    # Log startup
    count = db.get_card_count()
    logger.info("=" * 60)
    logger.info(f"BROK Library API Server Starting")
    logger.info(f"Database: {db_path}")
    logger.info(f"Inventory: {count['unique_cards']} unique cards, {count['total_quantity']} total")
    logger.info(f"Listening: {args.host}:{args.port}")
    logger.info("=" * 60)

    # Start server
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
