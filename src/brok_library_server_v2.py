#!/usr/bin/env python3
"""
BROK Library API Server V2
===========================
Works with the ACTUAL library schema (call_number, box_id, position, name, etc.)

Schema from ZULTAN/Scanner:
- call_number: Physical location identifier
- box_id: Storage box ID
- position: Position within box
- name: Card name
- set_code, set_name, collector_number, rarity
- MTG-specific: colors, color_identity, mana_cost, cmc, type_line, oracle_text

This version serves the REAL client inventory with call numbers intact.

Deploy to BROK:
    scp brok_library_server_v2.py nexus1@192.168.1.174:~/
    ssh nexus1@192.168.1.174
    python3 brok_library_server_v2.py --port 5002 --db ~/nexus_library.db

Patent Pending - Kevin Caracozza
Version: 3.0 (Feb 2026)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from pathlib import Path
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
DEFAULT_DB_PATH = Path.home() / "nexus_library.db"

app = Flask(__name__)
CORS(app)


class InventoryDatabase:
    """BROK master inventory database (READ-ONLY schema)"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._check_schema()
        logger.info(f"[INVENTORY] Using database: {self.db_path}")

    def _check_schema(self):
        """Check database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get schema
        columns = cursor.execute("PRAGMA table_info(cards)").fetchall()
        col_names = [c[1] for c in columns]

        logger.info(f"[SCHEMA] Columns: {', '.join(col_names[:10])}...")

        # Check for required columns
        if 'name' not in col_names and 'card_name' not in col_names:
            raise ValueError("Database missing card name column!")

        conn.close()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_cards(self, limit=1000, offset=0):
        """Get all inventory cards"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cards
            ORDER BY call_number
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
        conn.close()
        return count

    def search_cards(self, query, limit=100):
        """Search cards by name"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Try 'name' column first, fallback to 'card_name'
        try:
            cursor.execute("""
                SELECT * FROM cards
                WHERE name LIKE ?
                ORDER BY name
                LIMIT ?
            """, (f"%{query}%", limit))
        except sqlite3.OperationalError:
            cursor.execute("""
                SELECT * FROM cards
                WHERE card_name LIKE ?
                ORDER BY card_name
                LIMIT ?
            """, (f"%{query}%", limit))

        cards = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return cards

    def get_by_call_number(self, call_number):
        """Get card by call number (physical location)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM cards WHERE call_number = ?", (call_number,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_stats(self):
        """Get inventory statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        total_cards = cursor.execute("SELECT COUNT(*) FROM cards").fetchone()[0]

        # Get breakdown by rarity
        rarity_counts = {}
        try:
            for row in cursor.execute("SELECT rarity, COUNT(*) FROM cards GROUP BY rarity"):
                rarity_counts[row[0] or 'unknown'] = row[1]
        except:
            pass

        # Get breakdown by set
        set_counts = {}
        try:
            for row in cursor.execute("SELECT set_code, COUNT(*) FROM cards GROUP BY set_code ORDER BY COUNT(*) DESC LIMIT 10"):
                set_counts[row[0] or 'unknown'] = row[1]
        except:
            pass

        conn.close()

        return {
            'total_cards': total_cards,
            'rarity_breakdown': rarity_counts,
            'top_10_sets': set_counts
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
        'service': 'brok-library-api-v2',
        'unique_cards': count,
        'total_quantity': count  # No quantity column, so total = unique
    })


@app.route('/api/library/all', methods=['GET'])
def get_all():
    """Get all cards (paginated)"""
    limit = int(request.args.get('limit', 1000))
    offset = int(request.args.get('offset', 0))

    cards = db.get_all_cards(limit, offset)
    total = db.get_card_count()

    return jsonify({
        'total': total,
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


@app.route('/api/library/call/<call_number>', methods=['GET'])
def get_by_call(call_number):
    """Get card by call number"""
    card = db.get_by_call_number(call_number)
    if card:
        return jsonify(card)
    else:
        return jsonify({'error': 'Card not found'}), 404


# =============================================================================
# Main
# =============================================================================

def main():
    global db

    parser = argparse.ArgumentParser(description='BROK Library API Server V2')
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
    logger.info(f"BROK Library API Server V2 Starting")
    logger.info(f"Database: {db_path}")
    logger.info(f"Inventory: {count} cards")
    logger.info(f"Listening: {args.host}:{args.port}")
    logger.info("=" * 60)

    # Start server
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
