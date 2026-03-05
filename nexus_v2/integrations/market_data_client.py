"""
NEXUS Market Data Client — Flow 9
Sends anonymous scan and sale events to ZULTAN for pricing authority.

This is the DATA MOAT pipeline:
- Every scan = supply signal (what exists in the wild)
- Every sale = price signal (what it actually sold for)
- Aggregated across all shops → NEXUS becomes pricing authority

NO customer data. NO order IDs. NO personally identifiable information.
Pure anonymous market intelligence.

Target: ZULTAN (192.168.1.152:8000) — centralized pricing gateway
"""

import os
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

# ZULTAN is the market data gateway — NOT the marketplace
ZULTAN_MARKET_URL = os.getenv(
    'NEXUS_ZULTAN_URL', 'http://192.168.1.152:8000'
)


class MarketDataClient:
    """
    Fires anonymous market events to ZULTAN.
    All calls are fire-and-forget (async in background thread).
    Scanner should NEVER block on market data submission.
    """

    def __init__(self, zultan_url: str = None, shop_id: str = None):
        if requests is None:
            raise ImportError("requests library required")

        self.zultan_url = (zultan_url or ZULTAN_MARKET_URL).rstrip('/')
        self.shop_id = shop_id or os.getenv('NEXUS_SHOP_ID', 'default')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-NEXUS-Source': 'market-data-client'
        })
        # Queue for failed events (retry later)
        self._failed_queue = []
        self._enabled = True

    def disable(self):
        """Disable market data reporting (offline mode)"""
        self._enabled = False

    def enable(self):
        """Enable market data reporting"""
        self._enabled = True

    # ================================================================
    # SCAN EVENT — Supply signal
    # Fires after every successful card identification
    # ================================================================
    def report_scan(
        self,
        card_name: str,
        set_code: str = None,
        condition_estimate: str = None,
        card_type: str = None,
        surface_score: float = None,
        centering: str = None,
        edge_wear: float = None,
        surface_defects: int = None,
        foil: bool = False,
        language: str = 'English'
    ):
        """
        Report a scan event (supply signal).
        Called after card is identified, before inventory add.

        Args:
            card_name: Identified card name
            set_code: Set code (e.g., 'MH2', 'SV4')
            condition_estimate: NM/LP/MP/HP/DMG
            card_type: mtg/pokemon/yugioh/sports
            surface_score: Cross-polarization surface score (0-100)
            centering: Centering measurement (e.g., '98/96')
            edge_wear: Edge wear percentage (0-100)
            surface_defects: Count of detected surface defects
            foil: Whether card is foil
            language: Card language
        """
        event = {
            'event_type': 'scan',
            'card_name': card_name,
            'set_code': set_code,
            'card_type': card_type,
            'condition_estimate': condition_estimate,
            'foil': foil,
            'language': language,
            'shop_id': self.shop_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Cross-polarization grading data (when available)
        if surface_score is not None:
            event['grading'] = {
                'surface_score': surface_score,
                'centering': centering,
                'edge_wear': edge_wear,
                'surface_defects': surface_defects
            }

        self._send_async('/api/market/scan-event', event)

    # ================================================================
    # SALE EVENT — Price signal
    # Fires when a card is sold (marketplace OR local POS)
    # ================================================================
    def report_sale(
        self,
        card_name: str,
        sale_price: float,
        set_code: str = None,
        condition: str = None,
        card_type: str = None,
        foil: bool = False,
        currency: str = 'USD',
        channel: str = 'marketplace'
    ):
        """
        Report a sale event (price signal).
        Called when a card sale completes on ANY channel.

        Args:
            card_name: Card that sold
            sale_price: Actual sale price (after any discounts)
            set_code: Set code
            condition: Card condition at time of sale
            card_type: mtg/pokemon/yugioh/sports
            foil: Whether card is foil
            currency: Currency code (default USD)
            channel: Sale channel — 'marketplace', 'local_pos', 'card_show'
        """
        event = {
            'event_type': 'sale',
            'card_name': card_name,
            'sale_price': sale_price,
            'set_code': set_code,
            'condition': condition,
            'card_type': card_type,
            'foil': foil,
            'currency': currency,
            'channel': channel,
            'shop_id': self.shop_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        self._send_async('/api/market/sale-event', event)

    # ================================================================
    # PRICE CHECK — Query ZULTAN pricing (not a market event)
    # ================================================================
    def get_price(
        self,
        card_name: str,
        set_code: str = None,
        condition: str = 'NM',
        foil: bool = False
    ) -> Optional[dict]:
        """
        Query ZULTAN for current market price.
        Returns dict with price data or None on failure.

        Returns:
            {
                'market_price': 12.50,
                'low': 10.00,
                'high': 15.00,
                'source': 'nexus_aggregate',  # or 'scryfall', 'tcgplayer'
                'last_updated': '2026-02-15T...',
                'confidence': 0.92,
                'sale_count': 47
            }
        """
        try:
            r = self.session.get(
                f"{self.zultan_url}/api/market/price",
                params={
                    'card_name': card_name,
                    'set_code': set_code,
                    'condition': condition,
                    'foil': foil
                },
                timeout=5
            )
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            logger.warning(f"Price check failed: {e}")
            return None

    # ================================================================
    # BATCH — Flush multiple events at once
    # ================================================================
    def flush_batch(self, events: list):
        """
        Send a batch of scan/sale events at once.
        Useful for syncing after offline period.
        """
        if not events:
            return

        payload = {
            'events': events,
            'shop_id': self.shop_id,
            'batch_timestamp': datetime.now(timezone.utc).isoformat()
        }
        self._send_async('/api/market/batch', payload)

    def retry_failed(self):
        """Retry any events that failed to send."""
        if not self._failed_queue:
            return 0

        retrying = self._failed_queue.copy()
        self._failed_queue.clear()
        self.flush_batch(retrying)
        return len(retrying)

    # ================================================================
    # INTERNAL — Fire and forget
    # ================================================================
    def _send_async(self, endpoint: str, data: dict):
        """Send event in background thread. Never blocks scanner."""
        if not self._enabled:
            return

        def _do_send():
            try:
                r = self.session.post(
                    f"{self.zultan_url}{endpoint}",
                    json=data,
                    timeout=5
                )
                if r.status_code >= 400:
                    logger.warning(
                        f"Market event failed ({r.status_code}): {endpoint}"
                    )
                    self._failed_queue.append(data)
            except Exception as e:
                logger.debug(f"Market event send failed: {e}")
                self._failed_queue.append(data)

        t = threading.Thread(target=_do_send, daemon=True)
        t.start()


# Singleton for easy import
_default_client = None


def get_market_client() -> MarketDataClient:
    """Get or create the default market data client."""
    global _default_client
    if _default_client is None:
        _default_client = MarketDataClient()
    return _default_client


# ================================================================
# CONVENIENCE FUNCTIONS — Call from anywhere
# ================================================================
def report_scan(card_name: str, **kwargs):
    """Quick scan event. Import and call: market_data_client.report_scan(...)"""
    get_market_client().report_scan(card_name, **kwargs)


def report_sale(card_name: str, sale_price: float, **kwargs):
    """Quick sale event. Import and call: market_data_client.report_sale(...)"""
    get_market_client().report_sale(card_name, sale_price, **kwargs)
