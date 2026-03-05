"""
NEXUS Card Lookup API
Runs on ZULTAN (192.168.1.152:8000)
Provides card search/lookup for BROCK scanner and all clients.

Endpoints:
  GET  /api/health              - Health check
  GET  /api/card/<scryfall_id>  - Lookup by Scryfall UUID
  GET  /api/search?q=<name>     - Search by card name (fuzzy)
  GET  /api/search?set=<code>   - Filter by set code
  GET  /api/stats               - Database statistics
  POST /api/identify            - FAISS image match (future)
"""

import json
import os
import sys
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# Global data stores
CARD_LOOKUP = {}      # scryfall_id -> card data
NAME_INDEX = {}       # lowercase name -> list of scryfall_ids
SET_INDEX = {}        # set_code -> list of scryfall_ids
ORACLE_INDEX = {}     # oracle_id -> list of scryfall_ids

DATA_DIR = os.path.expanduser("~/training")
CARD_LOOKUP_PATH = os.path.join(DATA_DIR, "metadata", "card_lookup.json")
SCRYFALL_PATH = os.path.join(DATA_DIR, "data", "scryfall_cards.json")

LOAD_TIME = 0
QUERY_COUNT = 0


def load_card_data():
    """Load card_lookup.json and build search indexes."""
    global CARD_LOOKUP, NAME_INDEX, SET_INDEX, ORACLE_INDEX, LOAD_TIME

    start = time.time()
    print(f"[NEXUS API] Loading card data from {CARD_LOOKUP_PATH}...")

    with open(CARD_LOOKUP_PATH, "r") as f:
        CARD_LOOKUP = json.load(f)

    # Build indexes
    for scryfall_id, card in CARD_LOOKUP.items():
        name = card.get("n", "").lower()
        set_code = card.get("s", "").lower()
        oracle_id = card.get("o", "")

        # Name index (group by name for printings)
        if name not in NAME_INDEX:
            NAME_INDEX[name] = []
        NAME_INDEX[name].append(scryfall_id)

        # Set index
        if set_code not in SET_INDEX:
            SET_INDEX[set_code] = []
        SET_INDEX[set_code].append(scryfall_id)

        # Oracle index
        if oracle_id and oracle_id not in ORACLE_INDEX:
            ORACLE_INDEX[oracle_id] = []
        if oracle_id:
            ORACLE_INDEX[oracle_id].append(scryfall_id)

    LOAD_TIME = time.time() - start
    print(f"[NEXUS API] Loaded {len(CARD_LOOKUP):,} cards in {LOAD_TIME:.1f}s")
    print(f"[NEXUS API] Unique names: {len(NAME_INDEX):,}")
    print(f"[NEXUS API] Sets: {len(SET_INDEX):,}")
    print(f"[NEXUS API] Oracle IDs: {len(ORACLE_INDEX):,}")


def format_card(scryfall_id, card):
    """Format compact card data into full response."""
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
        "scryfall_url": f"https://scryfall.com/card/{card.get('s', '')}/{card.get('cn', '')}"
    }


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "nexus-card-api",
        "host": "ZULTAN",
        "cards_loaded": len(CARD_LOOKUP),
        "unique_names": len(NAME_INDEX),
        "sets": len(SET_INDEX),
        "load_time_seconds": round(LOAD_TIME, 1),
        "queries_served": QUERY_COUNT
    })


@app.route("/api/card/<scryfall_id>", methods=["GET"])
def get_card(scryfall_id):
    """Lookup a card by Scryfall UUID."""
    global QUERY_COUNT
    QUERY_COUNT += 1

    card = CARD_LOOKUP.get(scryfall_id)
    if not card:
        return jsonify({"error": "Card not found", "scryfall_id": scryfall_id}), 404

    return jsonify(format_card(scryfall_id, card))


@app.route("/api/search", methods=["GET"])
def search_cards():
    """Search cards by name, set, or oracle_id."""
    global QUERY_COUNT
    QUERY_COUNT += 1

    q = request.args.get("q", "").lower().strip()
    set_code = request.args.get("set", "").lower().strip()
    oracle_id = request.args.get("oracle_id", "").strip()
    limit = min(int(request.args.get("limit", 25)), 100)

    results = []

    if oracle_id:
        # Exact oracle ID lookup - all printings
        ids = ORACLE_INDEX.get(oracle_id, [])
        for sid in ids[:limit]:
            results.append(format_card(sid, CARD_LOOKUP[sid]))

    elif q:
        # Name search - exact first, then fuzzy
        # Exact match
        if q in NAME_INDEX:
            ids = NAME_INDEX[q]
            if set_code:
                ids = [sid for sid in ids if CARD_LOOKUP[sid].get("s", "").lower() == set_code]
            for sid in ids[:limit]:
                results.append(format_card(sid, CARD_LOOKUP[sid]))
        else:
            # Fuzzy: find names containing the query
            matching_names = [n for n in NAME_INDEX.keys() if q in n]
            matching_names.sort(key=lambda n: (not n.startswith(q), len(n)))
            for name in matching_names[:limit]:
                ids = NAME_INDEX[name]
                if set_code:
                    ids = [sid for sid in ids if CARD_LOOKUP[sid].get("s", "").lower() == set_code]
                for sid in ids[:3]:  # Max 3 printings per name in fuzzy
                    results.append(format_card(sid, CARD_LOOKUP[sid]))
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

    elif set_code:
        # Set listing
        ids = SET_INDEX.get(set_code, [])
        for sid in ids[:limit]:
            results.append(format_card(sid, CARD_LOOKUP[sid]))

    return jsonify({
        "query": {"q": q, "set": set_code, "oracle_id": oracle_id},
        "count": len(results),
        "results": results
    })


@app.route("/api/stats", methods=["GET"])
def stats():
    """Database statistics."""
    # Top sets by card count
    top_sets = sorted(SET_INDEX.items(), key=lambda x: -len(x[1]))[:20]

    # Price distribution
    prices = [c.get("p", 0) for c in CARD_LOOKUP.values() if c.get("p", 0) > 0]
    prices.sort(reverse=True)

    return jsonify({
        "total_cards": len(CARD_LOOKUP),
        "unique_names": len(NAME_INDEX),
        "total_sets": len(SET_INDEX),
        "oracle_ids": len(ORACLE_INDEX),
        "priced_cards": len(prices),
        "top_10_expensive": prices[:10] if prices else [],
        "top_sets": [{"set": s, "count": len(ids)} for s, ids in top_sets]
    })


@app.route("/api/bulk/lookup", methods=["POST"])
def bulk_lookup():
    """Bulk lookup by list of scryfall_ids. For inventory backfill."""
    global QUERY_COUNT
    QUERY_COUNT += 1

    data = request.get_json()
    if not data or "ids" not in data:
        return jsonify({"error": "POST body must include 'ids' array"}), 400

    ids = data["ids"]
    results = {}
    for sid in ids[:1000]:  # Max 1000 per request
        card = CARD_LOOKUP.get(sid)
        if card:
            results[sid] = format_card(sid, card)

    return jsonify({
        "requested": len(ids),
        "found": len(results),
        "results": results
    })


if __name__ == "__main__":
    load_card_data()
    port = int(os.environ.get("NEXUS_API_PORT", 8000))
    print(f"[NEXUS API] Starting on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
