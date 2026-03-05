#!/usr/bin/env python3
"""
BROK Library API - Master Inventory Server
Port: 5002
Database: ~/nexus_library.db (26,850 approved cards)

ACTUAL SCHEMA (verified 2026-02-16):
  call_number TEXT PRIMARY KEY  (e.g. 'AA-0001')
  box_id TEXT, position INTEGER, name TEXT,
  set_code TEXT, set_name TEXT, collector_number TEXT,
  rarity TEXT, colors TEXT, color_identity TEXT,
  mana_cost TEXT, cmc REAL, type_line TEXT, oracle_text TEXT,
  power TEXT, toughness TEXT, foil INTEGER,
  condition TEXT, language TEXT,
  price REAL, price_foil REAL, price_source TEXT, price_updated TEXT,
  image_url TEXT, image_url_small TEXT, art_hash TEXT,
  scryfall_id TEXT, uuid TEXT,
  cataloged_at TEXT, updated_at TEXT, notes TEXT,
  display INTEGER, display_case INTEGER

Each row = 1 physical card. No quantity column.
Quantity derived from COUNT(*) grouped by scryfall_id.
"""

import sqlite3
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.expanduser("~/nexus_library.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_card(row):
    """Convert a DB row to API card dict"""
    return {
        "call_number": row["call_number"],
        "box_id": row["box_id"],
        "position": row["position"],
        "name": row["name"],
        "set_code": row["set_code"],
        "set_name": row["set_name"],
        "collector_number": row["collector_number"],
        "rarity": row["rarity"],
        "colors": row["colors"],
        "color_identity": row["color_identity"],
        "mana_cost": row["mana_cost"],
        "cmc": row["cmc"],
        "type_line": row["type_line"],
        "foil": bool(row["foil"]),
        "condition": row["condition"],
        "price": row["price"],
        "price_foil": row["price_foil"],
        "image_url": row["image_url"],
        "image_url_small": row["image_url_small"],
        "scryfall_id": row["scryfall_id"],
        "cataloged_at": row["cataloged_at"],
    }


def grouped_card(rows):
    """Group multiple physical cards into one entry with quantity"""
    first = rows[0]
    return {
        "scryfall_id": first["scryfall_id"],
        "name": first["name"],
        "set_code": first["set_code"],
        "set_name": first["set_name"],
        "collector_number": first["collector_number"],
        "rarity": first["rarity"],
        "colors": first["colors"],
        "color_identity": first["color_identity"],
        "mana_cost": first["mana_cost"],
        "cmc": first["cmc"],
        "type_line": first["type_line"],
        "foil": bool(first["foil"]),
        "condition": first["condition"],
        "price": first["price"],
        "price_foil": first["price_foil"],
        "image_url": first["image_url"],
        "image_url_small": first["image_url_small"],
        "quantity": len(rows),
        "call_numbers": [r["call_number"] for r in rows],
        "box_ids": list(set(r["box_id"] for r in rows)),
        "date_added": min(r["cataloged_at"] or "" for r in rows),
    }


# ─── HEALTH ────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
@app.route("/api/library/health", methods=["GET"])
def health():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cards")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT scryfall_id) FROM cards WHERE scryfall_id IS NOT NULL")
        unique = cur.fetchone()[0]
        conn.close()
        return jsonify({
            "status": "online",
            "service": "brok-library-api",
            "port": 5002,
            "total_cards": total,
            "unique_cards": unique,
            "database": DB_PATH,
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ─── GET ALL (grouped) ─────────────────────────────────────

@app.route("/api/library/all", methods=["GET"])
def get_all():
    """All inventory cards, grouped by scryfall_id.
    Returns quantity + call_numbers + full metadata.
    ?limit=1000&offset=0&raw=1 for ungrouped individual cards.
    """
    limit = min(int(request.args.get("limit", 50000)), 50000)
    offset = int(request.args.get("offset", 0))
    raw = request.args.get("raw", "0") == "1"

    try:
        conn = get_db()
        cur = conn.cursor()

        if raw:
            # Return every physical card individually
            cur.execute("SELECT * FROM cards ORDER BY call_number LIMIT ? OFFSET ?", (limit, offset))
            results = [row_to_card(r) for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM cards")
            total = cur.fetchone()[0]
            conn.close()
            return jsonify({"total": total, "limit": limit, "offset": offset, "results": results})

        # Grouped mode (default) — group by scryfall_id
        cur.execute("""
            SELECT * FROM cards
            WHERE scryfall_id IS NOT NULL AND scryfall_id != ''
            ORDER BY name, set_code
        """)
        all_rows = cur.fetchall()

        # Group in Python for full metadata access
        groups = {}
        for row in all_rows:
            sid = row["scryfall_id"]
            groups.setdefault(sid, []).append(row)

        results = [grouped_card(rows) for rows in groups.values()]
        results.sort(key=lambda c: c["name"].lower())

        total_unique = len(results)
        page = results[offset:offset + limit]

        conn.close()
        return jsonify({
            "total_unique": total_unique,
            "total_cards": len(all_rows),
            "limit": limit,
            "offset": offset,
            "count": len(page),
            "results": page,
        })
    except Exception as e:
        logger.error(f"get_all failed: {e}")
        return jsonify({"error": str(e)}), 500


# ─── SEARCH ────────────────────────────────────────────────

@app.route("/api/library/search", methods=["GET"])
def search():
    """Search inventory by card name. ?q=lightning+bolt"""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Query param 'q' required"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM cards
            WHERE name LIKE ? AND scryfall_id IS NOT NULL
            ORDER BY name, set_code
        """, (f"%{q}%",))
        all_rows = cur.fetchall()

        groups = {}
        for row in all_rows:
            sid = row["scryfall_id"]
            groups.setdefault(sid, []).append(row)

        results = [grouped_card(rows) for rows in groups.values()]
        results.sort(key=lambda c: c["name"].lower())
        conn.close()

        return jsonify({
            "query": q,
            "unique_matches": len(results),
            "total_cards": len(all_rows),
            "results": results,
        })
    except Exception as e:
        logger.error(f"search failed: {e}")
        return jsonify({"error": str(e)}), 500


# ─── GET SINGLE CARD ───────────────────────────────────────

@app.route("/api/library/card/<scryfall_id>", methods=["GET"])
def get_card(scryfall_id):
    """Get all copies of a specific card by scryfall_id"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM cards WHERE scryfall_id = ?", (scryfall_id,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": "Card not in inventory"}), 404

        return jsonify(grouped_card(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── ADD CARD ──────────────────────────────────────────────

@app.route("/api/library/add", methods=["POST"])
def add_card():
    """Add a card to inventory. Each card = 1 row with unique call_number.

    Required: call_number, box_id, position, name
    Optional: scryfall_id, set_code, set_name, collector_number,
              rarity, colors, price, image_url, foil, condition, etc.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["call_number", "box_id", "position", "name"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        now = datetime.now().isoformat()
        cur.execute("""
            INSERT INTO cards (
                call_number, box_id, position, name,
                set_code, set_name, collector_number,
                rarity, colors, color_identity,
                mana_cost, cmc, type_line, oracle_text,
                power, toughness, foil, condition, language,
                price, price_foil, price_source, price_updated,
                image_url, image_url_small, art_hash,
                scryfall_id, uuid, cataloged_at, updated_at, notes
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?
            )
        """, (
            data["call_number"], data["box_id"], data["position"], data["name"],
            data.get("set_code", ""), data.get("set_name", ""), data.get("collector_number", ""),
            data.get("rarity", ""), data.get("colors", "[]"), data.get("color_identity", "[]"),
            data.get("mana_cost", ""), data.get("cmc", 0), data.get("type_line", ""), data.get("oracle_text", ""),
            data.get("power", ""), data.get("toughness", ""), data.get("foil", 0), data.get("condition", "NM"), data.get("language", "en"),
            data.get("price", 0), data.get("price_foil", 0), data.get("price_source", ""), data.get("price_updated", ""),
            data.get("image_url", ""), data.get("image_url_small", ""), data.get("art_hash", ""),
            data.get("scryfall_id", ""), data.get("uuid", ""), now, now, data.get("notes", ""),
        ))

        conn.commit()
        conn.close()
        return jsonify({"status": "added", "call_number": data["call_number"]})
    except sqlite3.IntegrityError:
        return jsonify({"error": f"call_number '{data['call_number']}' already exists"}), 409
    except Exception as e:
        logger.error(f"add_card failed: {e}")
        return jsonify({"error": str(e)}), 500


# ─── REMOVE CARD ───────────────────────────────────────────

@app.route("/api/library/remove", methods=["POST"])
def remove_card():
    """Remove a card by call_number (physical card removal).
    Or remove by scryfall_id + quantity (removes oldest first).

    Body: {"call_number": "AA-0001"}
      OR: {"scryfall_id": "abc-123", "quantity": 1}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        if "call_number" in data:
            # Remove specific physical card
            cn = data["call_number"]
            cur.execute("SELECT name FROM cards WHERE call_number = ?", (cn,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return jsonify({"error": f"call_number '{cn}' not found"}), 404
            cur.execute("DELETE FROM cards WHERE call_number = ?", (cn,))
            conn.commit()
            conn.close()
            return jsonify({"status": "removed", "call_number": cn, "name": row["name"]})

        elif "scryfall_id" in data:
            # Remove N copies (oldest cataloged first)
            sid = data["scryfall_id"]
            qty = data.get("quantity", 1)
            cur.execute("""
                SELECT call_number FROM cards
                WHERE scryfall_id = ?
                ORDER BY cataloged_at ASC
                LIMIT ?
            """, (sid, qty))
            targets = [r["call_number"] for r in cur.fetchall()]
            if not targets:
                conn.close()
                return jsonify({"error": f"scryfall_id '{sid}' not in inventory"}), 404

            placeholders = ",".join("?" * len(targets))
            cur.execute(f"DELETE FROM cards WHERE call_number IN ({placeholders})", targets)
            conn.commit()
            conn.close()
            return jsonify({"status": "removed", "scryfall_id": sid, "removed": len(targets), "call_numbers": targets})

        else:
            return jsonify({"error": "Provide 'call_number' or 'scryfall_id'"}), 400

    except Exception as e:
        logger.error(f"remove_card failed: {e}")
        return jsonify({"error": str(e)}), 500


# ─── STATS ─────────────────────────────────────────────────

@app.route("/api/library/stats", methods=["GET"])
def stats():
    """Inventory statistics"""
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM cards")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT scryfall_id) FROM cards WHERE scryfall_id IS NOT NULL AND scryfall_id != ''")
        unique = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT box_id) FROM cards")
        boxes = cur.fetchone()[0]

        cur.execute("SELECT SUM(price) FROM cards WHERE foil = 0")
        value_reg = cur.fetchone()[0] or 0

        cur.execute("SELECT SUM(price_foil) FROM cards WHERE foil = 1")
        value_foil = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM cards WHERE foil = 1")
        foil_count = cur.fetchone()[0]

        cur.execute("""
            SELECT rarity, COUNT(*) as cnt FROM cards
            WHERE rarity IS NOT NULL AND rarity != ''
            GROUP BY rarity ORDER BY cnt DESC
        """)
        rarity_breakdown = {r["rarity"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("""
            SELECT set_code, COUNT(*) as cnt FROM cards
            WHERE set_code IS NOT NULL AND set_code != ''
            GROUP BY set_code ORDER BY cnt DESC LIMIT 20
        """)
        top_sets = {r["set_code"]: r["cnt"] for r in cur.fetchall()}

        conn.close()

        return jsonify({
            "total_cards": total,
            "unique_cards": unique,
            "total_boxes": boxes,
            "foil_count": foil_count,
            "estimated_value": round(value_reg + value_foil, 2),
            "value_regular": round(value_reg, 2),
            "value_foil": round(value_foil, 2),
            "rarity_breakdown": rarity_breakdown,
            "top_sets": top_sets,
        })
    except Exception as e:
        logger.error(f"stats failed: {e}")
        return jsonify({"error": str(e)}), 500


# ─── INFO (legacy compat) ─────────────────────────────────

@app.route("/api/library/info", methods=["GET"])
def info():
    """Legacy endpoint - redirects to stats"""
    return stats()


# ─── BOX LOOKUP ────────────────────────────────────────────

@app.route("/api/library/box/<box_id>", methods=["GET"])
def get_box(box_id):
    """Get all cards in a specific box"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM cards WHERE box_id = ? ORDER BY position", (box_id,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": f"Box '{box_id}' not found or empty"}), 404

        return jsonify({
            "box_id": box_id,
            "count": len(rows),
            "cards": [row_to_card(r) for r in rows],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found: {DB_PATH}")
        exit(1)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cards")
    total = cur.fetchone()[0]
    conn.close()

    logger.info(f"BROK Library API starting on port 5002")
    logger.info(f"Database: {DB_PATH} ({total:,} cards)")
    app.run(host="0.0.0.0", port=5002, debug=False)
