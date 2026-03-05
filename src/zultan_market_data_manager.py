#!/usr/bin/env python3
"""
ZULTAN Market Data Manager
==========================
SQLite persistence for Flow 9 market events.

Database: ~/training/data/market_data.db
- scan_events table (supply signals)
- sale_events table (price signals)
- price_snapshots table (aggregated pricing)

Author: NEXUS Project
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class MarketDataManager:
    """
    Manages market event storage and pricing aggregation.

    Flow 9 Pipeline:
    - Scan events → supply signal (what exists in shops)
    - Sale events → price signal (what cards actually sell for)
    - Price queries → aggregated NEXUS data + Scryfall fallback
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path.home() / "training" / "data" / "market_data.db")

        self.db_path = db_path
        self._init_database()
        logger.info(f"Market data manager initialized: {db_path}")

    def _init_database(self):
        """Create database schema if not exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")  # Concurrent writes

        # Scan events (supply signal)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                card_name TEXT NOT NULL,
                set_code TEXT,
                card_type TEXT,
                condition_estimate TEXT,
                foil INTEGER DEFAULT 0,
                language TEXT DEFAULT 'English',
                shop_id TEXT,
                surface_score REAL,
                centering TEXT,
                edge_wear REAL,
                surface_defects INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sale events (price signal)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sale_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                card_name TEXT NOT NULL,
                set_code TEXT,
                card_type TEXT,
                condition TEXT,
                foil INTEGER DEFAULT 0,
                sale_price REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                channel TEXT,
                shop_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Price snapshots (hourly aggregation for fast queries)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_hour TEXT NOT NULL,
                card_name TEXT NOT NULL,
                set_code TEXT,
                condition TEXT,
                foil INTEGER DEFAULT 0,
                avg_price REAL,
                min_price REAL,
                max_price REAL,
                sale_count INTEGER,
                scan_count INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_hour, card_name, set_code, condition, foil)
            )
        """)

        # Indexes for fast queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scan_card ON scan_events(card_name, set_code, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sale_card ON sale_events(card_name, set_code, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshot ON price_snapshots(card_name, set_code, condition, foil)")

        conn.commit()
        conn.close()

    # ================================================================
    # INSERT EVENTS
    # ================================================================

    def record_scan(self, event: Dict) -> int:
        """
        Record a scan event (supply signal).

        Returns:
            Event ID
        """
        conn = sqlite3.connect(self.db_path)

        grading = event.get('grading', {})

        cursor = conn.execute("""
            INSERT INTO scan_events (
                timestamp, card_name, set_code, card_type,
                condition_estimate, foil, language, shop_id,
                surface_score, centering, edge_wear, surface_defects
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get('timestamp'),
            event.get('card_name'),
            event.get('set_code'),
            event.get('card_type'),
            event.get('condition_estimate'),
            1 if event.get('foil') else 0,
            event.get('language', 'English'),
            event.get('shop_id'),
            grading.get('surface_score'),
            grading.get('centering'),
            grading.get('edge_wear'),
            grading.get('surface_defects')
        ))

        event_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"Recorded scan: {event.get('card_name')} (ID {event_id})")
        return event_id

    def record_sale(self, event: Dict) -> int:
        """
        Record a sale event (price signal).

        Returns:
            Event ID
        """
        conn = sqlite3.connect(self.db_path)

        cursor = conn.execute("""
            INSERT INTO sale_events (
                timestamp, card_name, set_code, card_type,
                condition, foil, sale_price, currency, channel, shop_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get('timestamp'),
            event.get('card_name'),
            event.get('set_code'),
            event.get('card_type'),
            event.get('condition'),
            1 if event.get('foil') else 0,
            event.get('sale_price'),
            event.get('currency', 'USD'),
            event.get('channel'),
            event.get('shop_id')
        ))

        event_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Recorded sale: {event.get('card_name')} @ ${event.get('sale_price')} (ID {event_id})")
        return event_id

    def record_batch(self, events: List[Dict]) -> int:
        """
        Record a batch of events.

        Returns:
            Number of events recorded
        """
        count = 0
        for event in events:
            event_type = event.get('event_type')
            if event_type == 'scan':
                self.record_scan(event)
                count += 1
            elif event_type == 'sale':
                self.record_sale(event)
                count += 1

        logger.info(f"Recorded batch: {count} events")
        return count

    # ================================================================
    # QUERY EVENTS
    # ================================================================

    def get_scan_count(self, card_name: str, set_code: str = None,
                       days_back: int = 30) -> int:
        """Get scan count for a card (supply indicator)"""
        conn = sqlite3.connect(self.db_path)

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

        if set_code:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM scan_events
                WHERE card_name = ? AND set_code = ? AND timestamp >= ?
            """, (card_name, set_code, cutoff))
        else:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM scan_events
                WHERE card_name = ? AND timestamp >= ?
            """, (card_name, cutoff))

        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_price_stats(self, card_name: str, set_code: str = None,
                        condition: str = 'NM', foil: bool = False,
                        days_back: int = 30) -> Dict:
        """
        Get aggregated price statistics from sale events.

        Returns:
            {
                'market_price': avg sale price,
                'low': min sale price,
                'high': max sale price,
                'sale_count': number of sales,
                'scan_count': number of scans,
                'confidence': 0-1 based on sample size,
                'source': 'nexus_aggregate'
            }
        """
        conn = sqlite3.connect(self.db_path)

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

        # Query sales
        if set_code:
            cursor = conn.execute("""
                SELECT AVG(sale_price), MIN(sale_price), MAX(sale_price), COUNT(*)
                FROM sale_events
                WHERE card_name = ? AND set_code = ?
                  AND condition = ? AND foil = ?
                  AND timestamp >= ?
                  AND currency = 'USD'
            """, (card_name, set_code, condition, 1 if foil else 0, cutoff))
        else:
            cursor = conn.execute("""
                SELECT AVG(sale_price), MIN(sale_price), MAX(sale_price), COUNT(*)
                FROM sale_events
                WHERE card_name = ?
                  AND condition = ? AND foil = ?
                  AND timestamp >= ?
                  AND currency = 'USD'
            """, (card_name, condition, 1 if foil else 0, cutoff))

        result = cursor.fetchone()
        avg_price, min_price, max_price, sale_count = result

        # Get scan count
        scan_count = self.get_scan_count(card_name, set_code, days_back)

        conn.close()

        if sale_count == 0:
            return None

        # Confidence based on sample size
        # 1-4 sales: 0.3, 5-9: 0.5, 10-19: 0.7, 20+: 0.9
        if sale_count >= 20:
            confidence = 0.9
        elif sale_count >= 10:
            confidence = 0.7
        elif sale_count >= 5:
            confidence = 0.5
        else:
            confidence = 0.3

        return {
            'market_price': round(avg_price, 2) if avg_price else 0,
            'low': round(min_price, 2) if min_price else 0,
            'high': round(max_price, 2) if max_price else 0,
            'sale_count': sale_count,
            'scan_count': scan_count,
            'confidence': confidence,
            'source': 'nexus_aggregate',
            'last_updated': datetime.now(timezone.utc).isoformat()
        }

    # ================================================================
    # PRICE QUERY WITH SCRYFALL FALLBACK
    # ================================================================

    def get_market_price(self, card_name: str, set_code: str = None,
                        condition: str = 'NM', foil: bool = False,
                        days_back: int = 30) -> Dict:
        """
        Get market price with Scryfall fallback.

        Order of precedence:
        1. NEXUS aggregated data (if confidence >= 0.5)
        2. Scryfall API (for MTG)
        3. Best effort from NEXUS data (even low confidence)
        """
        # Try NEXUS data first
        nexus_data = self.get_price_stats(card_name, set_code, condition, foil, days_back)

        if nexus_data and nexus_data['confidence'] >= 0.5:
            return nexus_data

        # Fallback to Scryfall for MTG
        scryfall_data = self._get_scryfall_price(card_name, set_code, foil)
        if scryfall_data:
            return scryfall_data

        # Return low-confidence NEXUS data if available
        if nexus_data:
            return nexus_data

        # No data at all
        return {
            'market_price': 0,
            'low': 0,
            'high': 0,
            'sale_count': 0,
            'scan_count': 0,
            'confidence': 0,
            'source': 'no_data',
            'last_updated': datetime.now(timezone.utc).isoformat()
        }

    def _get_scryfall_price(self, card_name: str, set_code: str = None,
                           foil: bool = False) -> Optional[Dict]:
        """Fallback to Scryfall API for MTG pricing"""
        try:
            import requests

            # Try exact printing first
            if set_code:
                url = f"https://api.scryfall.com/cards/named"
                params = {'exact': card_name, 'set': set_code.lower()}
            else:
                url = f"https://api.scryfall.com/cards/named"
                params = {'fuzzy': card_name}

            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200:
                return None

            card = r.json()
            prices = card.get('prices', {})

            # Get appropriate price
            if foil:
                price = prices.get('usd_foil')
            else:
                price = prices.get('usd')

            if not price:
                return None

            price_float = float(price)

            return {
                'market_price': price_float,
                'low': price_float,
                'high': price_float,
                'sale_count': 0,
                'scan_count': 0,
                'confidence': 0.8,  # Scryfall is reliable
                'source': 'scryfall',
                'last_updated': datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.debug(f"Scryfall fallback failed: {e}")
            return None

    # ================================================================
    # STATS
    # ================================================================

    def get_stats(self) -> Dict:
        """Get overall market data statistics"""
        conn = sqlite3.connect(self.db_path)

        # Total events
        cursor = conn.execute("SELECT COUNT(*) FROM scan_events")
        total_scans = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM sale_events")
        total_sales = cursor.fetchone()[0]

        # Recent events (last 24 hours)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        cursor = conn.execute("SELECT COUNT(*) FROM scan_events WHERE timestamp >= ?", (cutoff,))
        recent_scans = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM sale_events WHERE timestamp >= ?", (cutoff,))
        recent_sales = cursor.fetchone()[0]

        # Total GMV (Gross Merchandise Value)
        cursor = conn.execute("SELECT SUM(sale_price) FROM sale_events WHERE currency = 'USD'")
        total_gmv = cursor.fetchone()[0] or 0

        conn.close()

        return {
            'total_scans': total_scans,
            'total_sales': total_sales,
            'recent_scans_24h': recent_scans,
            'recent_sales_24h': recent_sales,
            'total_gmv_usd': round(total_gmv, 2),
            'database': self.db_path
        }


# Singleton instance
_manager = None

def get_market_manager() -> MarketDataManager:
    """Get or create singleton market data manager"""
    global _manager
    if _manager is None:
        _manager = MarketDataManager()
    return _manager
