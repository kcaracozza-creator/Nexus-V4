"""
NEXUS Market Data Router — Flow 9: The Data Moat
=================================================
Receives anonymous scan and sale events from all NEXUS clients.
Aggregates into pricing authority dataset.

Endpoints:
  POST /api/market/scan-event   — Supply signal (card exists in the wild)
  POST /api/market/sale-event   — Price signal (card sold for $X)
  GET  /api/market/price        — Query aggregated market price
  POST /api/market/batch        — Bulk event submission
  GET  /api/market/stats        — Market data statistics

Storage: SQLite on ZULTAN (market_data.db)
NO customer data. NO order IDs. NO PII. Pure market intelligence.

This is the moat. Every scan across every shop feeds the oracle.
"""

import os
import sqlite3
import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market-data"])

# ================================================================
# DATABASE
# ================================================================
DB_PATH = os.getenv("NEXUS_MARKET_DB", "/home/zultan/nexus_market_data/market_data.db")
# Fallback for Windows dev
if not os.path.exists(os.path.dirname(DB_PATH)) and os.name == "nt":
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "market_data.db")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db() -> sqlite3.Connection:
    """Get SQLite connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """Create market data tables if they don't exist."""
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scan_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_code TEXT,
                card_type TEXT DEFAULT 'mtg',
                condition_estimate TEXT,
                foil INTEGER DEFAULT 0,
                language TEXT DEFAULT 'English',
                surface_score REAL,
                centering TEXT,
                edge_wear REAL,
                surface_defects INTEGER,
                shop_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sale_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                set_code TEXT,
                card_type TEXT DEFAULT 'mtg',
                condition TEXT DEFAULT 'NM',
                foil INTEGER DEFAULT 0,
                sale_price REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                channel TEXT DEFAULT 'marketplace',
                shop_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Aggregated price cache (rebuilt periodically)
            CREATE TABLE IF NOT EXISTS price_cache (
                card_key TEXT PRIMARY KEY,
                card_name TEXT NOT NULL,
                set_code TEXT,
                condition TEXT DEFAULT 'NM',
                foil INTEGER DEFAULT 0,
                market_price REAL,
                price_low REAL,
                price_high REAL,
                median_price REAL,
                sale_count INTEGER DEFAULT 0,
                scan_count INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                source TEXT DEFAULT 'nexus_aggregate',
                last_sale_at TEXT,
                last_scan_at TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Indexes for fast lookups
            CREATE INDEX IF NOT EXISTS idx_scan_card ON scan_events(card_name, set_code);
            CREATE INDEX IF NOT EXISTS idx_scan_time ON scan_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_scan_shop ON scan_events(shop_id);
            CREATE INDEX IF NOT EXISTS idx_sale_card ON sale_events(card_name, set_code);
            CREATE INDEX IF NOT EXISTS idx_sale_time ON sale_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_sale_price ON sale_events(card_name, sale_price);
            CREATE INDEX IF NOT EXISTS idx_price_name ON price_cache(card_name);
        """)
        conn.commit()
        logger.info(f"Market data DB initialized: {DB_PATH}")
    finally:
        conn.close()


# Initialize on import
init_db()


# ================================================================
# MODELS
# ================================================================
class ScanEvent(BaseModel):
    card_name: str
    set_code: Optional[str] = None
    card_type: Optional[str] = "mtg"
    condition_estimate: Optional[str] = None
    foil: bool = False
    language: str = "English"
    surface_score: Optional[float] = None
    centering: Optional[str] = None
    edge_wear: Optional[float] = None
    surface_defects: Optional[int] = None
    shop_id: str = "default"
    timestamp: Optional[str] = None


class SaleEvent(BaseModel):
    card_name: str
    sale_price: float = Field(gt=0)
    set_code: Optional[str] = None
    card_type: Optional[str] = "mtg"
    condition: Optional[str] = "NM"
    foil: bool = False
    currency: str = "USD"
    channel: str = "marketplace"
    shop_id: str = "default"
    timestamp: Optional[str] = None


class BatchPayload(BaseModel):
    events: List[dict]
    shop_id: str = "default"
    batch_timestamp: Optional[str] = None


# ================================================================
# HELPERS
# ================================================================
def _make_card_key(card_name: str, set_code: str = None,
                   condition: str = "NM", foil: bool = False) -> str:
    """Unique key for price cache lookups."""
    parts = [
        card_name.lower().strip(),
        (set_code or "any").lower(),
        (condition or "NM").upper(),
        "foil" if foil else "reg"
    ]
    return "|".join(parts)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_price_cache(conn: sqlite3.Connection, card_name: str,
                        set_code: str = None, condition: str = "NM",
                        foil: bool = False):
    """
    Rebuild price cache entry for a card from raw sale events.
    Called after each sale event — keeps cache hot.
    """
    card_key = _make_card_key(card_name, set_code, condition, foil)

    # Get recent sales (last 90 days)
    ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    query = """
        SELECT sale_price, timestamp FROM sale_events
        WHERE card_name = ? AND foil = ?
    """
    params = [card_name, int(foil)]

    if set_code:
        query += " AND set_code = ?"
        params.append(set_code)
    if condition:
        query += " AND condition = ?"
        params.append(condition)

    query += " AND timestamp >= ? ORDER BY timestamp DESC"
    params.append(ninety_days_ago)

    rows = conn.execute(query, params).fetchall()
    prices = [r["sale_price"] for r in rows]

    # Get scan count
    scan_query = "SELECT COUNT(*) as cnt FROM scan_events WHERE card_name = ?"
    scan_params = [card_name]
    if set_code:
        scan_query += " AND set_code = ?"
        scan_params.append(set_code)
    scan_count = conn.execute(scan_query, scan_params).fetchone()["cnt"]

    if not prices:
        # No sales data — just update scan count
        conn.execute("""
            INSERT INTO price_cache (card_key, card_name, set_code, condition, foil,
                                     scan_count, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'scan_only', ?)
            ON CONFLICT(card_key) DO UPDATE SET
                scan_count = ?, updated_at = ?
        """, (card_key, card_name, set_code, condition, int(foil),
              scan_count, _now_iso(), scan_count, _now_iso()))
        return

    # Calculate aggregated pricing
    sale_count = len(prices)
    market_price = round(statistics.median(prices), 2)
    price_low = round(min(prices), 2)
    price_high = round(max(prices), 2)
    median_price = market_price

    # Confidence scoring:
    # - 1-2 sales: 0.3 (low)
    # - 3-5 sales: 0.5 (moderate)
    # - 6-10 sales: 0.7 (good)
    # - 11-25 sales: 0.85 (high)
    # - 26+: 0.95 (authority)
    if sale_count >= 26:
        confidence = 0.95
    elif sale_count >= 11:
        confidence = 0.85
    elif sale_count >= 6:
        confidence = 0.7
    elif sale_count >= 3:
        confidence = 0.5
    else:
        confidence = 0.3

    # Reduce confidence if price spread is wide (>50% of median)
    if market_price > 0:
        spread = (price_high - price_low) / market_price
        if spread > 0.5:
            confidence *= 0.8

    confidence = round(confidence, 2)
    last_sale = rows[0]["timestamp"] if rows else None

    conn.execute("""
        INSERT INTO price_cache
            (card_key, card_name, set_code, condition, foil,
             market_price, price_low, price_high, median_price,
             sale_count, scan_count, confidence, source,
             last_sale_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nexus_aggregate', ?, ?)
        ON CONFLICT(card_key) DO UPDATE SET
            market_price = ?, price_low = ?, price_high = ?,
            median_price = ?, sale_count = ?, scan_count = ?,
            confidence = ?, last_sale_at = ?, updated_at = ?
    """, (
        card_key, card_name, set_code, condition, int(foil),
        market_price, price_low, price_high, median_price,
        sale_count, scan_count, confidence, last_sale, _now_iso(),
        # UPDATE values:
        market_price, price_low, price_high,
        median_price, sale_count, scan_count,
        confidence, last_sale, _now_iso()
    ))


# ================================================================
# ENDPOINTS
# ================================================================

@router.post("/scan-event")
async def receive_scan_event(event: ScanEvent):
    """
    Receive a scan event (supply signal).
    Every card scanned across every NEXUS station feeds this endpoint.
    """
    ts = event.timestamp or _now_iso()

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO scan_events
                (card_name, set_code, card_type, condition_estimate,
                 foil, language, surface_score, centering, edge_wear,
                 surface_defects, shop_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.card_name, event.set_code, event.card_type,
            event.condition_estimate, int(event.foil), event.language,
            event.surface_score, event.centering, event.edge_wear,
            event.surface_defects, event.shop_id, ts
        ))
        conn.commit()

        # Update scan count in price cache
        _update_price_cache(
            conn, event.card_name, event.set_code,
            event.condition_estimate or "NM", event.foil
        )
        conn.commit()

        return {"status": "recorded", "event": "scan", "card": event.card_name}
    except Exception as e:
        logger.error(f"Scan event failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/sale-event")
async def receive_sale_event(event: SaleEvent):
    """
    Receive a sale event (price signal).
    Every card sold on any channel — marketplace, local POS, card show.
    This is the money data. This builds the moat.
    """
    ts = event.timestamp or _now_iso()

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO sale_events
                (card_name, set_code, card_type, condition,
                 foil, sale_price, currency, channel,
                 shop_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.card_name, event.set_code, event.card_type,
            event.condition, int(event.foil), event.sale_price,
            event.currency, event.channel, event.shop_id, ts
        ))
        conn.commit()

        # Rebuild price cache for this card
        _update_price_cache(
            conn, event.card_name, event.set_code,
            event.condition, event.foil
        )
        conn.commit()

        return {
            "status": "recorded",
            "event": "sale",
            "card": event.card_name,
            "price": event.sale_price
        }
    except Exception as e:
        logger.error(f"Sale event failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/price")
async def get_price(
    card_name: str = Query(..., min_length=1),
    set_code: Optional[str] = None,
    condition: str = "NM",
    foil: bool = False
):
    """
    Query NEXUS aggregated market price for a card.
    Returns median sale price, range, confidence, and sale count.

    Falls back to external sources (Scryfall, TCGPlayer) if no NEXUS data.
    """
    card_key = _make_card_key(card_name, set_code, condition, foil)

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM price_cache WHERE card_key = ?",
            (card_key,)
        ).fetchone()

        if row and row["market_price"]:
            return {
                "card_name": row["card_name"],
                "set_code": row["set_code"],
                "condition": row["condition"],
                "foil": bool(row["foil"]),
                "market_price": row["market_price"],
                "low": row["price_low"],
                "high": row["price_high"],
                "median": row["median_price"],
                "sale_count": row["sale_count"],
                "scan_count": row["scan_count"],
                "confidence": row["confidence"],
                "source": row["source"],
                "last_sale": row["last_sale_at"],
                "updated_at": row["updated_at"]
            }

        # No NEXUS data — try fuzzy match (same card, any set/condition)
        fuzzy = conn.execute("""
            SELECT * FROM price_cache
            WHERE card_name = ? AND market_price IS NOT NULL
            ORDER BY sale_count DESC LIMIT 1
        """, (card_name,)).fetchone()

        if fuzzy:
            return {
                "card_name": fuzzy["card_name"],
                "set_code": fuzzy["set_code"],
                "condition": fuzzy["condition"],
                "foil": bool(fuzzy["foil"]),
                "market_price": fuzzy["market_price"],
                "low": fuzzy["price_low"],
                "high": fuzzy["price_high"],
                "median": fuzzy["median_price"],
                "sale_count": fuzzy["sale_count"],
                "scan_count": fuzzy["scan_count"],
                "confidence": round(fuzzy["confidence"] * 0.7, 2),
                "source": "nexus_fuzzy",
                "note": f"Exact match not found for {set_code}/{condition}. Showing best available.",
                "last_sale": fuzzy["last_sale_at"],
                "updated_at": fuzzy["updated_at"]
            }

        # No data at all
        return {
            "card_name": card_name,
            "set_code": set_code,
            "condition": condition,
            "foil": foil,
            "market_price": None,
            "source": "no_data",
            "message": "No NEXUS pricing data yet. Use external source (Scryfall/TCGPlayer)."
        }
    finally:
        conn.close()


@router.post("/batch")
async def receive_batch(payload: BatchPayload):
    """
    Receive a batch of scan/sale events at once.
    Used for syncing after offline periods or bulk imports.
    """
    recorded = 0
    errors = 0

    conn = get_db()
    try:
        for event_data in payload.events:
            event_type = event_data.get("event_type", "scan")
            # Override shop_id from batch wrapper if not in individual event
            if "shop_id" not in event_data:
                event_data["shop_id"] = payload.shop_id

            try:
                if event_type == "sale":
                    conn.execute("""
                        INSERT INTO sale_events
                            (card_name, set_code, card_type, condition,
                             foil, sale_price, currency, channel,
                             shop_id, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_data.get("card_name", ""),
                        event_data.get("set_code"),
                        event_data.get("card_type", "mtg"),
                        event_data.get("condition", "NM"),
                        int(event_data.get("foil", False)),
                        event_data.get("sale_price", 0),
                        event_data.get("currency", "USD"),
                        event_data.get("channel", "batch_sync"),
                        event_data.get("shop_id", payload.shop_id),
                        event_data.get("timestamp", _now_iso())
                    ))
                else:
                    conn.execute("""
                        INSERT INTO scan_events
                            (card_name, set_code, card_type, condition_estimate,
                             foil, language, surface_score, centering, edge_wear,
                             surface_defects, shop_id, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_data.get("card_name", ""),
                        event_data.get("set_code"),
                        event_data.get("card_type", "mtg"),
                        event_data.get("condition_estimate"),
                        int(event_data.get("foil", False)),
                        event_data.get("language", "English"),
                        event_data.get("surface_score"),
                        event_data.get("centering"),
                        event_data.get("edge_wear"),
                        event_data.get("surface_defects"),
                        event_data.get("shop_id", payload.shop_id),
                        event_data.get("timestamp", _now_iso())
                    ))
                recorded += 1
            except Exception as e:
                logger.warning(f"Batch event failed: {e}")
                errors += 1

        conn.commit()
        return {
            "status": "processed",
            "recorded": recorded,
            "errors": errors,
            "total": len(payload.events)
        }
    finally:
        conn.close()


@router.get("/stats")
async def market_stats():
    """
    Market data dashboard stats.
    How much data is in the moat.
    """
    conn = get_db()
    try:
        scans = conn.execute("SELECT COUNT(*) as cnt FROM scan_events").fetchone()["cnt"]
        sales = conn.execute("SELECT COUNT(*) as cnt FROM sale_events").fetchone()["cnt"]
        unique_cards_scanned = conn.execute(
            "SELECT COUNT(DISTINCT card_name) as cnt FROM scan_events"
        ).fetchone()["cnt"]
        unique_cards_sold = conn.execute(
            "SELECT COUNT(DISTINCT card_name) as cnt FROM sale_events"
        ).fetchone()["cnt"]
        unique_shops = conn.execute(
            "SELECT COUNT(DISTINCT shop_id) as cnt FROM scan_events"
        ).fetchone()["cnt"]
        cached_prices = conn.execute(
            "SELECT COUNT(*) as cnt FROM price_cache WHERE market_price IS NOT NULL"
        ).fetchone()["cnt"]

        # Revenue tracked
        total_volume = conn.execute(
            "SELECT COALESCE(SUM(sale_price), 0) as total FROM sale_events"
        ).fetchone()["total"]

        # Recent activity (last 24h)
        yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        recent_scans = conn.execute(
            "SELECT COUNT(*) as cnt FROM scan_events WHERE received_at >= ?",
            (yesterday,)
        ).fetchone()["cnt"]
        recent_sales = conn.execute(
            "SELECT COUNT(*) as cnt FROM sale_events WHERE received_at >= ?",
            (yesterday,)
        ).fetchone()["cnt"]

        return {
            "total_scan_events": scans,
            "total_sale_events": sales,
            "unique_cards_scanned": unique_cards_scanned,
            "unique_cards_sold": unique_cards_sold,
            "unique_shops": unique_shops,
            "cached_prices": cached_prices,
            "total_sales_volume_usd": round(total_volume, 2),
            "last_24h": {
                "scans": recent_scans,
                "sales": recent_sales
            },
            "moat_status": "growing" if scans > 0 else "empty"
        }
    finally:
        conn.close()
