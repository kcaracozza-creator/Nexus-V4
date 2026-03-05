"""
NEXUS Unified Card Lookup API
Runs on ZULTAN (192.168.1.152:8000)
Provides card search/lookup for ALL TCGs: MTG, Pokemon, Sports
+ Flow 9 Market Data Pipeline (pricing authority)

Endpoints:
  GET  /api/health                  - Health check
  GET  /api/mtg/card/<scryfall_id>  - MTG lookup by Scryfall UUID
  GET  /api/mtg/search?q=<name>    - MTG search by name
  GET  /api/pokemon/card/<card_id>  - Pokemon lookup by ID
  GET  /api/pokemon/search?q=<name>- Pokemon search by name
  GET  /api/sports/search?q=<name> - Sports card search
  GET  /api/sports/search?q=<name>&sport=baseball  - Filter by sport
  GET  /api/stats                   - Database statistics across all TCGs

  # Flow 9: Market Data (Data Moat)
  POST /api/market/scan-event      - Receive anonymous scan event
  POST /api/market/sale-event      - Receive anonymous sale event
  POST /api/market/batch           - Receive batch of events
  GET  /api/market/price           - Query aggregated market price
"""

import json
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from flask import Flask, request, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ===========================================================================
# MTG DATA (card_lookup.json - 521K cards)
# ===========================================================================
MTG_LOOKUP = {}
MTG_NAME_INDEX = {}
MTG_SET_INDEX = {}
MTG_ORACLE_INDEX = {}

MTG_DATA_DIR = os.path.expanduser("~/training")
MTG_LOOKUP_PATH = os.path.join(MTG_DATA_DIR, "metadata", "card_lookup.json")

# ===========================================================================
# POKEMON DATA (pokemon_lookup.json - 19.8K cards)
# ===========================================================================
POKEMON_LOOKUP = {}
POKEMON_NAME_INDEX = {}
POKEMON_SET_INDEX = {}

POKEMON_LOOKUP_PATH = "/opt/nexus/training/data/pokemon/metadata/pokemon_lookup.json"

# ===========================================================================
# SPORTS DATA (SQLite - 250K+ cards)
# ===========================================================================
SPORTS_DB_PATH = "/opt/nexus/sports_cards/tcdb_cache.db"

# Timing
LOAD_TIME = 0
QUERY_COUNT = 0


def load_all_data():
    """Load all card data at startup."""
    global MTG_LOOKUP, MTG_NAME_INDEX, MTG_SET_INDEX, MTG_ORACLE_INDEX
    global POKEMON_LOOKUP, POKEMON_NAME_INDEX, POKEMON_SET_INDEX
    global LOAD_TIME

    start = time.time()

    # --- MTG ---
    print("[NEXUS API] Loading MTG data...")
    try:
        with open(MTG_LOOKUP_PATH, "r") as f:
            MTG_LOOKUP = json.load(f)
        for sid, card in MTG_LOOKUP.items():
            name = card.get("n", "").lower()
            set_code = card.get("s", "").lower()
            oracle_id = card.get("o", "")
            if name not in MTG_NAME_INDEX:
                MTG_NAME_INDEX[name] = []
            MTG_NAME_INDEX[name].append(sid)
            if set_code not in MTG_SET_INDEX:
                MTG_SET_INDEX[set_code] = []
            MTG_SET_INDEX[set_code].append(sid)
            if oracle_id:
                if oracle_id not in MTG_ORACLE_INDEX:
                    MTG_ORACLE_INDEX[oracle_id] = []
                MTG_ORACLE_INDEX[oracle_id].append(sid)
        print(f"[NEXUS API] MTG: {len(MTG_LOOKUP):,} cards, {len(MTG_NAME_INDEX):,} unique names")
    except Exception as e:
        print(f"[NEXUS API] MTG load error: {e}")

    # --- Pokemon ---
    print("[NEXUS API] Loading Pokemon data...")
    try:
        with open(POKEMON_LOOKUP_PATH, "r") as f:
            POKEMON_LOOKUP = json.load(f)
        for card_id, card in POKEMON_LOOKUP.items():
            name = card.get("name", "").lower()
            set_id = card.get("set_id", "").lower()
            if name not in POKEMON_NAME_INDEX:
                POKEMON_NAME_INDEX[name] = []
            POKEMON_NAME_INDEX[name].append(card_id)
            if set_id not in POKEMON_SET_INDEX:
                POKEMON_SET_INDEX[set_id] = []
            POKEMON_SET_INDEX[set_id].append(card_id)
        print(f"[NEXUS API] Pokemon: {len(POKEMON_LOOKUP):,} cards, {len(POKEMON_NAME_INDEX):,} unique names")
    except Exception as e:
        print(f"[NEXUS API] Pokemon load error: {e}")

    # --- Sports (SQLite - don't load into memory, just verify) ---
    try:
        conn = sqlite3.connect(SPORTS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM cards")
        sports_count = c.fetchone()[0]
        conn.close()
        print(f"[NEXUS API] Sports: {sports_count:,} cards (SQLite)")
    except Exception as e:
        print(f"[NEXUS API] Sports DB not available: {e}")

    LOAD_TIME = time.time() - start
    print(f"[NEXUS API] All data loaded in {LOAD_TIME:.1f}s")


# ===========================================================================
# FORMAT HELPERS
# ===========================================================================
def format_mtg_card(scryfall_id, card):
    return {
        "scryfall_id": scryfall_id,
        "name": card.get("n", ""),
        "oracle_id": card.get("o", ""),
        "set_code": card.get("s", ""),
        "set_name": card.get("sn", ""),
        "collector_number": card.get("cn", ""),
        "rarity": card.get("r", ""),
        "price_usd": card.get("p", 0),
        "image_url": f"https://api.scryfall.com/cards/{scryfall_id}?format=image",
        "scryfall_url": f"https://scryfall.com/card/{card.get('s', '')}/{card.get('cn', '')}",
        "tcg": "mtg"
    }


def format_pokemon_card(card_id, card):
    return {
        "card_id": card_id,
        "name": card.get("name", ""),
        "set_id": card.get("set_id", ""),
        "set_name": card.get("set_name", ""),
        "number": card.get("number", ""),
        "rarity": card.get("rarity", ""),
        "image_url": card.get("image_large", ""),
        "tcg": "pokemon"
    }


# ===========================================================================
# HEALTH / STATS
# ===========================================================================
@app.route("/api/health", methods=["GET"])
def health():
    global QUERY_COUNT
    sports_count = 0
    try:
        conn = sqlite3.connect(SPORTS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM cards")
        sports_count = c.fetchone()[0]
        conn.close()
    except:
        pass

    return jsonify({
        "status": "online",
        "service": "nexus-unified-api",
        "host": "ZULTAN",
        "mtg_cards": len(MTG_LOOKUP),
        "pokemon_cards": len(POKEMON_LOOKUP),
        "sports_cards": sports_count,
        "load_time_seconds": round(LOAD_TIME, 1),
        "queries_served": QUERY_COUNT
    })


@app.route("/api/stats", methods=["GET"])
def stats():
    # MTG stats
    mtg_prices = [c.get("p", 0) for c in MTG_LOOKUP.values() if c.get("p", 0) > 0]
    mtg_prices.sort(reverse=True)

    # Sports stats
    sports_stats = {}
    try:
        conn = sqlite3.connect(SPORTS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT sport, COUNT(*) FROM cards GROUP BY sport")
        sports_stats = dict(c.fetchall())
        conn.close()
    except:
        pass

    # Pokemon stats
    pokemon_sets = {}
    for card in POKEMON_LOOKUP.values():
        sn = card.get("set_name", "unknown")
        pokemon_sets[sn] = pokemon_sets.get(sn, 0) + 1

    return jsonify({
        "mtg": {
            "total_cards": len(MTG_LOOKUP),
            "unique_names": len(MTG_NAME_INDEX),
            "total_sets": len(MTG_SET_INDEX),
            "priced_cards": len(mtg_prices),
            "top_10_prices": mtg_prices[:10]
        },
        "pokemon": {
            "total_cards": len(POKEMON_LOOKUP),
            "unique_names": len(POKEMON_NAME_INDEX),
            "total_sets": len(POKEMON_SET_INDEX),
        },
        "sports": sports_stats
    })


# ===========================================================================
# MTG ENDPOINTS
# ===========================================================================
@app.route("/api/mtg/card/<scryfall_id>", methods=["GET"])
@app.route("/api/card/<scryfall_id>", methods=["GET"])  # backward compat
def get_mtg_card(scryfall_id):
    global QUERY_COUNT
    QUERY_COUNT += 1
    card = MTG_LOOKUP.get(scryfall_id)
    if not card:
        return jsonify({"error": "Card not found", "scryfall_id": scryfall_id}), 404
    return jsonify(format_mtg_card(scryfall_id, card))


@app.route("/api/mtg/search", methods=["GET"])
@app.route("/api/search", methods=["GET"])  # backward compat
def search_mtg():
    global QUERY_COUNT
    QUERY_COUNT += 1

    q = request.args.get("q", "").lower().strip()
    set_code = request.args.get("set", "").lower().strip()
    oracle_id = request.args.get("oracle_id", "").strip()
    limit = min(int(request.args.get("limit", 25)), 100)

    results = []

    if oracle_id:
        ids = MTG_ORACLE_INDEX.get(oracle_id, [])
        for sid in ids[:limit]:
            results.append(format_mtg_card(sid, MTG_LOOKUP[sid]))
    elif q:
        if q in MTG_NAME_INDEX:
            ids = MTG_NAME_INDEX[q]
            if set_code:
                ids = [sid for sid in ids if MTG_LOOKUP[sid].get("s", "").lower() == set_code]
            for sid in ids[:limit]:
                results.append(format_mtg_card(sid, MTG_LOOKUP[sid]))
        else:
            matching_names = [n for n in MTG_NAME_INDEX.keys() if q in n]
            matching_names.sort(key=lambda n: (not n.startswith(q), len(n)))
            for name in matching_names[:limit]:
                ids = MTG_NAME_INDEX[name]
                if set_code:
                    ids = [sid for sid in ids if MTG_LOOKUP[sid].get("s", "").lower() == set_code]
                for sid in ids[:3]:
                    results.append(format_mtg_card(sid, MTG_LOOKUP[sid]))
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
    elif set_code:
        ids = MTG_SET_INDEX.get(set_code, [])
        for sid in ids[:limit]:
            results.append(format_mtg_card(sid, MTG_LOOKUP[sid]))

    return jsonify({"query": {"q": q, "set": set_code, "oracle_id": oracle_id},
                     "count": len(results), "results": results})


# ===========================================================================
# POKEMON ENDPOINTS
# ===========================================================================
@app.route("/api/pokemon/card/<card_id>", methods=["GET"])
def get_pokemon_card(card_id):
    global QUERY_COUNT
    QUERY_COUNT += 1
    card = POKEMON_LOOKUP.get(card_id)
    if not card:
        return jsonify({"error": "Card not found", "card_id": card_id}), 404
    return jsonify(format_pokemon_card(card_id, card))


@app.route("/api/pokemon/search", methods=["GET"])
def search_pokemon():
    global QUERY_COUNT
    QUERY_COUNT += 1

    q = request.args.get("q", "").lower().strip()
    set_id = request.args.get("set", "").lower().strip()
    limit = min(int(request.args.get("limit", 25)), 100)

    results = []

    if q:
        # Exact match first
        if q in POKEMON_NAME_INDEX:
            ids = POKEMON_NAME_INDEX[q]
            if set_id:
                ids = [cid for cid in ids if POKEMON_LOOKUP[cid].get("set_id", "").lower() == set_id]
            for cid in ids[:limit]:
                results.append(format_pokemon_card(cid, POKEMON_LOOKUP[cid]))
        else:
            # Fuzzy
            matching = [n for n in POKEMON_NAME_INDEX.keys() if q in n]
            matching.sort(key=lambda n: (not n.startswith(q), len(n)))
            for name in matching[:limit]:
                ids = POKEMON_NAME_INDEX[name]
                if set_id:
                    ids = [cid for cid in ids if POKEMON_LOOKUP[cid].get("set_id", "").lower() == set_id]
                for cid in ids[:3]:
                    results.append(format_pokemon_card(cid, POKEMON_LOOKUP[cid]))
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
    elif set_id:
        ids = POKEMON_SET_INDEX.get(set_id, [])
        for cid in ids[:limit]:
            results.append(format_pokemon_card(cid, POKEMON_LOOKUP[cid]))

    return jsonify({"query": {"q": q, "set": set_id},
                     "count": len(results), "results": results})


# ===========================================================================
# SPORTS ENDPOINTS
# ===========================================================================
@app.route("/api/sports/search", methods=["GET"])
def search_sports():
    global QUERY_COUNT
    QUERY_COUNT += 1

    q = request.args.get("q", "").strip()
    sport = request.args.get("sport", "").strip()
    year = request.args.get("year", type=int)
    limit = min(int(request.args.get("limit", 25)), 100)

    try:
        conn = sqlite3.connect(SPORTS_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = "SELECT * FROM cards WHERE (name LIKE ? OR card_number LIKE ?)"
        params = [f'%{q}%', f'%{q}%']

        if sport:
            sql += ' AND sport = ?'
            params.append(sport)
        if year:
            sql += ' AND year = ?'
            params.append(year)

        sql += f' LIMIT {limit}'
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["tcg"] = "sports"
            results.append(d)

        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"query": {"q": q, "sport": sport, "year": year},
                     "count": len(results), "results": results})


@app.route("/api/sports/card/<card_id>", methods=["GET"])
def get_sports_card(card_id):
    global QUERY_COUNT
    QUERY_COUNT += 1

    try:
        conn = sqlite3.connect(SPORTS_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Card not found", "card_id": card_id}), 404

        d = dict(row)
        d["tcg"] = "sports"
        return jsonify(d)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===========================================================================
# BULK LOOKUP
# ===========================================================================
@app.route("/api/bulk/lookup", methods=["POST"])
def bulk_lookup():
    global QUERY_COUNT
    QUERY_COUNT += 1

    data = request.get_json()
    if not data or "ids" not in data:
        return jsonify({"error": "POST body must include 'ids' array"}), 400

    ids = data["ids"]
    results = {}
    for sid in ids[:1000]:
        card = MTG_LOOKUP.get(sid)
        if card:
            results[sid] = format_mtg_card(sid, card)

    return jsonify({"requested": len(ids), "found": len(results), "results": results})


# ===========================================================================
# FLOW 9: MARKET DATA ENDPOINTS (Data Moat Pipeline)
# ===========================================================================
# These endpoints receive anonymous scan/sale events from all shops
# NO customer data, NO PII - pure market intelligence
# After 90 days → NEXUS becomes the pricing authority

# Import market data manager (SQLite persistence)
try:
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from zultan_market_data_manager import get_market_manager
    market_manager = get_market_manager()
    MARKET_DATA_ENABLED = True
except Exception as e:
    logger.warning(f"Market data manager failed to load: {e}")
    market_manager = None
    MARKET_DATA_ENABLED = False

@app.route("/api/market/scan-event", methods=["POST"])
def market_scan_event():
    """Receive anonymous scan event (supply signal)"""
    global QUERY_COUNT
    QUERY_COUNT += 1

    if not MARKET_DATA_ENABLED:
        return jsonify({"error": "Market data not enabled"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate required fields
    if 'card_name' not in data:
        return jsonify({"error": "card_name required"}), 400

    # Persist to SQLite
    try:
        event_id = market_manager.record_scan(data)
        return jsonify({"status": "ok", "event_id": event_id})
    except Exception as e:
        logger.error(f"Failed to record scan event: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/api/market/sale-event", methods=["POST"])
def market_sale_event():
    """Receive anonymous sale event (price signal)"""
    global QUERY_COUNT
    QUERY_COUNT += 1

    if not MARKET_DATA_ENABLED:
        return jsonify({"error": "Market data not enabled"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate required fields
    if 'card_name' not in data or 'sale_price' not in data:
        return jsonify({"error": "card_name and sale_price required"}), 400

    # Persist to SQLite
    try:
        event_id = market_manager.record_sale(data)
        return jsonify({"status": "ok", "event_id": event_id})
    except Exception as e:
        logger.error(f"Failed to record sale event: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/api/market/batch", methods=["POST"])
def market_batch():
    """Receive batch of scan/sale events"""
    global QUERY_COUNT
    QUERY_COUNT += 1

    if not MARKET_DATA_ENABLED:
        return jsonify({"error": "Market data not enabled"}), 503

    data = request.get_json()
    if not data or 'events' not in data:
        return jsonify({"error": "events array required"}), 400

    # Persist batch to SQLite
    try:
        count = market_manager.record_batch(data['events'])
        return jsonify({"status": "ok", "events_recorded": count})
    except Exception as e:
        logger.error(f"Failed to record batch: {e}")
        return jsonify({"error": "Database error"}), 500


@app.route("/api/market/price", methods=["GET"])
def market_price():
    """Query aggregated market price (pricing authority with Scryfall fallback)"""
    global QUERY_COUNT
    QUERY_COUNT += 1

    if not MARKET_DATA_ENABLED:
        return jsonify({"error": "Market data not enabled"}), 503

    card_name = request.args.get('card_name')
    set_code = request.args.get('set_code')
    condition = request.args.get('condition', 'NM')
    foil = request.args.get('foil', 'false').lower() == 'true'

    if not card_name:
        return jsonify({"error": "card_name required"}), 400

    # Query with Scryfall fallback
    try:
        price_data = market_manager.get_market_price(
            card_name, set_code, condition, foil
        )
        return jsonify(price_data)
    except Exception as e:
        logger.error(f"Price query failed: {e}")
        return jsonify({"error": "Price query failed"}), 500


# ===========================================================================
# MAIN
# ===========================================================================
if __name__ == "__main__":
    load_all_data()
    port = int(os.environ.get("NEXUS_API_PORT", 8000))
    print(f"[NEXUS API] Starting unified API on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
