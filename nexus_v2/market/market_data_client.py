#!/usr/bin/env python3
"""
NEXUS MARKET DATA CLIENT (Flow 9)
==================================
THE DATA MOAT. Every scan and every sale feeds anonymous market data
to ZULTAN, building the pricing authority that no competitor has.

Two event types:
  1. SCAN EVENT  → Supply signal (what exists in the wild)
  2. SALE EVENT  → Price signal  (what it actually sold for)

Combined over time: condition spreads, velocity, real transaction prices
across MTG/Pokemon/Sports, all channels, all shops.

NO customer data. NO call_numbers. NO order IDs. Just market signals.

Patent Pending - Kevin Caracozza
"""

import os
import logging
import threading
import queue
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger('NEXUS-MarketData')

# ZULTAN is the centralized pricing gateway
ZULTAN_MARKET_URL = os.getenv(
    'NEXUS_ZULTAN_MARKET_URL',
    'http://192.168.1.152:8000'
)


class MarketDataClient:
    """
    Fires anonymous market data events to ZULTAN.
    
    Uses a background queue so scan/sale flows are never blocked
    by network latency to ZULTAN. Events are fire-and-forget with
    local fallback logging if ZULTAN is unreachable.
    
    Usage:
        market = MarketDataClient(shop_id="NEXUS-HQ-001")
        
        # After card identified:
        market.scan_event(
            card_name="Lightning Bolt",
            set_code="2ED",
            card_type="mtg",
            condition_estimate="NM"
        )
        
        # After sale completes:
        market.sale_event(
            card_name="Lightning Bolt",
            set_code="2ED",
            card_type="mtg",
            condition="NM",
            sale_price=245.00
        )
    """

    def __init__(self, shop_id: str = "NEXUS-DEFAULT",
                 zultan_url: str = None,
                 queue_size: int = 1000,
                 retry_attempts: int = 3,
                 retry_delay: float = 1.0,
                 fallback_log: str = None):
        """
        Args:
            shop_id: Anonymous shop identifier (not shop name/location)
            zultan_url: Override ZULTAN URL
            queue_size: Max events to buffer before dropping
            retry_attempts: Retries per event before fallback
            retry_delay: Seconds between retries (with backoff)
            fallback_log: Path to log failed events for later replay
        """
        self.shop_id = shop_id
        self.zultan_url = (zultan_url or ZULTAN_MARKET_URL).rstrip('/')
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.fallback_log = fallback_log

        # Background queue for non-blocking event dispatch
        self._queue = queue.Queue(maxsize=queue_size)
        self._worker = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="MarketData-Worker"
        )
        self._running = True
        self._worker.start()

        # Stats
        self._sent_count = 0
        self._failed_count = 0
        self._dropped_count = 0

        # Session with connection pooling
        if requests:
            self._session = requests.Session()
            self._session.headers.update({
                'Content-Type': 'application/json',
                'X-NEXUS-Source': 'market-data-client',
                'X-NEXUS-Shop': self.shop_id
            })
        else:
            self._session = None
            logger.warning("requests library not available - market data disabled")

        logger.info(f"MarketDataClient initialized → {self.zultan_url} (shop: {self.shop_id})")

    # =========================================================================
    # PUBLIC API - Fire and forget
    # =========================================================================

    def scan_event(self,
                   card_name: str,
                   card_type: str,
                   set_code: Optional[str] = None,
                   condition_estimate: Optional[str] = None,
                   confidence: Optional[int] = None,
                   surface_score: Optional[float] = None,
                   centering: Optional[str] = None,
                   edge_wear: Optional[float] = None,
                   surface_defects: Optional[int] = None,
                   scan_source: str = "scanner") -> bool:
        """
        Record a scan event (supply signal).
        
        Called after BROK inventory write completes.
        No customer data. No call_number. Just market supply signal.
        
        Args:
            card_name: Identified card name
            card_type: mtg, pokemon, yugioh, sports_baseball, etc.
            set_code: Set/product code
            condition_estimate: NM, LP, MP, HP, DMG
            confidence: Identification confidence 0-100
            surface_score: Cross-polarization surface score (if available)
            centering: Centering measurement "98/96" format
            edge_wear: Edge wear percentage
            surface_defects: Count of detected surface defects
            scan_source: "scanner", "manual", "import"
        
        Returns:
            True if queued successfully, False if queue full
        """
        event = {
            'event_type': 'scan',
            'card_name': card_name,
            'card_type': card_type,
            'set_code': set_code,
            'condition_estimate': condition_estimate,
            'confidence': confidence,
            'scan_source': scan_source,
            'shop_id': self.shop_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Grading data (cross-polarization) - only if available
        if surface_score is not None:
            event['grading'] = {
                'surface_score': surface_score,
                'centering': centering,
                'edge_wear': edge_wear,
                'surface_defects': surface_defects
            }

        return self._enqueue(event)

    def sale_event(self,
                   card_name: str,
                   card_type: str,
                   sale_price: float,
                   set_code: Optional[str] = None,
                   condition: Optional[str] = None,
                   currency: str = "USD",
                   sale_channel: str = "local",
                   listed_price: Optional[float] = None,
                   days_listed: Optional[int] = None) -> bool:
        """
        Record a sale event (price signal).
        
        Called when sale completes (marketplace OR local POS).
        No buyer. No seller name. No order ID. Just transaction data.
        
        Args:
            card_name: Card that sold
            card_type: mtg, pokemon, yugioh, sports_baseball, etc.
            sale_price: Actual sale price
            set_code: Set/product code
            condition: Card condition at time of sale
            currency: Currency code (default USD)
            sale_channel: "local", "marketplace", "tcgplayer", "ebay"
            listed_price: Original listing price (shows negotiation spread)
            days_listed: Days between listing and sale (velocity signal)
        
        Returns:
            True if queued successfully, False if queue full
        """
        event = {
            'event_type': 'sale',
            'card_name': card_name,
            'card_type': card_type,
            'set_code': set_code,
            'condition': condition,
            'sale_price': sale_price,
            'currency': currency,
            'sale_channel': sale_channel,
            'shop_id': self.shop_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Velocity data - optional but valuable
        if listed_price is not None:
            event['listed_price'] = listed_price
        if days_listed is not None:
            event['days_listed'] = days_listed

        return self._enqueue(event)

    def get_stats(self) -> Dict[str, int]:
        """Get client-side delivery stats"""
        return {
            'sent': self._sent_count,
            'failed': self._failed_count,
            'dropped': self._dropped_count,
            'queued': self._queue.qsize()
        }

    def shutdown(self):
        """Graceful shutdown - flush remaining events"""
        self._running = False
        # Give worker time to flush
        self._queue.join()
        if self._session:
            self._session.close()
        logger.info(f"MarketDataClient shutdown. Stats: {self.get_stats()}")

    # =========================================================================
    # INTERNAL - Queue processing
    # =========================================================================

    def _enqueue(self, event: Dict) -> bool:
        """Add event to background queue"""
        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            self._dropped_count += 1
            logger.warning(f"Market data queue full - event dropped ({self._dropped_count} total)")
            return False

    def _process_queue(self):
        """Background worker - sends events to ZULTAN"""
        while self._running or not self._queue.empty():
            try:
                event = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._send_event(event)
                self._sent_count += 1
            except Exception as e:
                self._failed_count += 1
                logger.error(f"Market data event failed: {e}")
                self._fallback_log_event(event)
            finally:
                self._queue.task_done()

    def _send_event(self, event: Dict):
        """Send single event to ZULTAN with retry"""
        if not self._session:
            raise RuntimeError("requests library not available")

        endpoint = f"{self.zultan_url}/api/market/{event['event_type']}-event"

        for attempt in range(self.retry_attempts):
            try:
                resp = self._session.post(
                    endpoint,
                    json=event,
                    timeout=5
                )
                if resp.status_code in (200, 201, 202):
                    return  # Success
                elif resp.status_code == 429:
                    # Rate limited - back off harder
                    wait = self.retry_delay * (2 ** attempt) * 2
                    logger.warning(f"ZULTAN rate limited, waiting {wait}s")
                    time.sleep(wait)
                else:
                    logger.warning(
                        f"ZULTAN returned {resp.status_code} for "
                        f"{event['event_type']} event (attempt {attempt + 1})"
                    )
            except requests.exceptions.ConnectionError:
                # ZULTAN unreachable - retry with backoff
                wait = self.retry_delay * (2 ** attempt)
                if attempt < self.retry_attempts - 1:
                    time.sleep(wait)
            except requests.exceptions.Timeout:
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)

        # All retries exhausted
        raise RuntimeError(
            f"Failed to deliver {event['event_type']} event after "
            f"{self.retry_attempts} attempts"
        )

    def _fallback_log_event(self, event: Dict):
        """Log failed event for later replay"""
        if not self.fallback_log:
            return
        try:
            import json
            with open(self.fallback_log, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f"Fallback log write failed: {e}")


# =============================================================================
# ZULTAN SERVER-SIDE ENDPOINTS (deploy to ZULTAN)
# =============================================================================
# These would be added to the ZULTAN Flask/FastAPI server.
# Included here as reference implementation.

ZULTAN_MARKET_SCHEMA = """
-- Market Data Tables (SQLite on ZULTAN)
-- Run once on zultan@192.168.1.152

CREATE TABLE IF NOT EXISTS market_scan_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name TEXT NOT NULL,
    card_type TEXT NOT NULL,
    set_code TEXT,
    condition_estimate TEXT,
    confidence INTEGER,
    scan_source TEXT DEFAULT 'scanner',
    shop_id TEXT NOT NULL,
    -- Grading data (cross-polarization)
    surface_score REAL,
    centering TEXT,
    edge_wear REAL,
    surface_defects INTEGER,
    -- Metadata
    timestamp TEXT NOT NULL,
    received_at TEXT DEFAULT (datetime('now')),
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS market_sale_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name TEXT NOT NULL,
    card_type TEXT NOT NULL,
    set_code TEXT,
    condition TEXT,
    sale_price REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    sale_channel TEXT DEFAULT 'local',
    listed_price REAL,
    days_listed INTEGER,
    shop_id TEXT NOT NULL,
    -- Metadata
    timestamp TEXT NOT NULL,
    received_at TEXT DEFAULT (datetime('now')),
    processed INTEGER DEFAULT 0
);

-- Aggregated pricing index (rebuilt periodically)
CREATE TABLE IF NOT EXISTS market_price_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name TEXT NOT NULL,
    card_type TEXT NOT NULL,
    set_code TEXT,
    condition TEXT DEFAULT 'NM',
    -- Pricing
    avg_price REAL,
    median_price REAL,
    low_price REAL,
    high_price REAL,
    sample_count INTEGER,
    -- Velocity
    avg_days_to_sell REAL,
    scan_count INTEGER,
    sale_count INTEGER,
    -- Time window
    period_start TEXT,
    period_end TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(card_name, set_code, condition, period_end)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_scan_card ON market_scan_events(card_name, card_type);
CREATE INDEX IF NOT EXISTS idx_scan_time ON market_scan_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_sale_card ON market_sale_events(card_name, card_type);
CREATE INDEX IF NOT EXISTS idx_sale_time ON market_sale_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_price_lookup ON market_price_index(card_name, set_code, condition);
"""
