#!/usr/bin/env python3
"""
TCGPlayer Price Data — via Scryfall API (attributed)

TCGPlayer price data is sourced through the Scryfall public API
(api.scryfall.com), which licenses and attributes TCGPlayer pricing.
This module does NOT scrape tcgplayer.com.

Data attribution: Prices displayed as "TCGPlayer Market" sourced from
Scryfall's licensed TCGPlayer feed. All prices must be displayed with
source attribution per the no-pricing mandate.

Official TCGPlayer Partner API:
  When a TCGPlayer API key is obtained (developer.tcgplayer.com),
  set TCGPLAYER_API_KEY in the environment and this module will
  switch to the direct authenticated endpoint automatically.
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from urllib.parse import quote

logger = logging.getLogger(__name__)

SCRYFALL_API = "https://api.scryfall.com"
SCRYFALL_HEADERS = {
    'User-Agent': 'NEXUS-Universal-Collectibles/2.0 (contact: nexus@nexus-cards.com)',
    'Accept': 'application/json',
}
# Scryfall asks for 50–100ms between requests
SCRYFALL_DELAY = 0.1

TCGPLAYER_API_KEY = os.environ.get('TCGPLAYER_API_KEY', '')
TCGPLAYER_API_BASE = "https://api.tcgplayer.com/v1.39.0"

CACHE_TTL_HOURS = 6


class TCGPlayerScraper:
    """
    Retrieves attributed TCGPlayer price listings via Scryfall's licensed feed.

    Returns externally sourced price data only. NEXUS does not generate,
    calculate, or determine prices. All returned values must be displayed
    with source attribution (e.g. "TCGPlayer Market via Scryfall").
    """

    def __init__(self, cache_file: str = None):
        self.cache_file = cache_file or os.path.join(
            os.path.dirname(__file__), "tcg_price_cache.json"
        )
        self.price_cache: dict = self._load_cache()
        self._last_request = 0.0

    # -------------------------------------------------------------------------
    # Cache
    # -------------------------------------------------------------------------

    def _load_cache(self) -> dict:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                cutoff = datetime.now() - timedelta(hours=CACHE_TTL_HOURS)
                return {
                    k: v for k, v in raw.items()
                    if datetime.fromisoformat(v.get('timestamp', '1970-01-01')) > cutoff
                }
        except Exception as e:
            logger.warning(f"Price cache load failed: {e}")
        return {}

    def _save_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.price_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Price cache save failed: {e}")

    # -------------------------------------------------------------------------
    # Rate limiter
    # -------------------------------------------------------------------------

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < SCRYFALL_DELAY:
            time.sleep(SCRYFALL_DELAY - elapsed)
        self._last_request = time.monotonic()

    # -------------------------------------------------------------------------
    # Public interface — same signature as the old scraper
    # -------------------------------------------------------------------------

    def get_card_price(self, card_name: str, set_name: str = None) -> dict | None:
        """
        Return attributed TCGPlayer price data for a card.

        Data source: Scryfall API (licensed TCGPlayer feed).
        All values are externally sourced; NEXUS does not generate prices.

        Returns dict with keys:
            market_price   (float, USD)   — TCGPlayer market price
            low_price      (float, USD)   — TCGPlayer low
            foil_price     (float, USD)   — TCGPlayer foil market
            source         (str)          — attribution string
            set_code       (str)
            set_name       (str)
            card_name      (str)
            timestamp      (str, ISO)
        or None if the card is not found.
        """
        if TCGPLAYER_API_KEY:
            return self._fetch_direct_api(card_name, set_name)
        return self._fetch_via_scryfall(card_name, set_name)

    # -------------------------------------------------------------------------
    # Scryfall path (default — no API key required)
    # -------------------------------------------------------------------------

    def _fetch_via_scryfall(self, card_name: str, set_name: str = None) -> dict | None:
        cache_key = f"{card_name.lower()}_{(set_name or '').lower()}"
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]['price_data']

        try:
            self._wait()
            params = {'fuzzy': card_name}
            if set_name:
                params['set'] = set_name[:3].lower()

            resp = requests.get(
                f"{SCRYFALL_API}/cards/named",
                params=params,
                headers=SCRYFALL_HEADERS,
                timeout=10,
            )

            if resp.status_code == 404:
                logger.info(f"Card not found on Scryfall: {card_name!r}")
                return None
            resp.raise_for_status()
            data = resp.json()

            prices = data.get('prices', {})
            usd = prices.get('usd')
            usd_foil = prices.get('usd_foil')

            if not usd and not usd_foil:
                logger.info(f"No TCGPlayer price data for {card_name!r}")
                return None

            result = {
                'market_price': float(usd) if usd else None,
                'low_price':    float(prices.get('usd', usd) or usd or 0),
                'foil_price':   float(usd_foil) if usd_foil else None,
                'source':       'TCGPlayer Market via Scryfall API',
                'set_code':     data.get('set', ''),
                'set_name':     data.get('set_name', ''),
                'card_name':    data.get('name', card_name),
                'scryfall_id':  data.get('id', ''),
                'timestamp':    datetime.now().isoformat(),
            }

            self.price_cache[cache_key] = {
                'price_data': result,
                'timestamp':  result['timestamp'],
            }
            self._save_cache()
            return result

        except requests.RequestException as e:
            logger.error(f"Scryfall request failed for {card_name!r}: {e}")
            return None

    # -------------------------------------------------------------------------
    # Direct TCGPlayer API path (requires TCGPLAYER_API_KEY env var)
    # -------------------------------------------------------------------------

    def _fetch_direct_api(self, card_name: str, set_name: str = None) -> dict | None:
        """
        Use the official TCGPlayer Partner API when a key is configured.
        Apply for access at: https://developer.tcgplayer.com
        """
        cache_key = f"direct_{card_name.lower()}_{(set_name or '').lower()}"
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]['price_data']

        try:
            self._wait()
            headers = {
                'Authorization': f'Bearer {TCGPLAYER_API_KEY}',
                'Accept': 'application/json',
                'User-Agent': 'NEXUS-Universal-Collectibles/2.0',
            }
            search_resp = requests.get(
                f"{TCGPLAYER_API_BASE}/catalog/products/search",
                params={'productName': card_name, 'limit': 5},
                headers=headers,
                timeout=10,
            )
            search_resp.raise_for_status()
            results = search_resp.json().get('results', [])
            if not results:
                return None

            product_id = results[0]['productId']

            self._wait()
            price_resp = requests.get(
                f"{TCGPLAYER_API_BASE}/pricing/product/{product_id}",
                headers=headers,
                timeout=10,
            )
            price_resp.raise_for_status()
            prices = price_resp.json().get('results', [])
            if not prices:
                return None

            normal = next((p for p in prices if p.get('subTypeName') == 'Normal'), None)
            foil   = next((p for p in prices if p.get('subTypeName') == 'Foil'), None)

            result = {
                'market_price': normal.get('marketPrice') if normal else None,
                'low_price':    normal.get('lowPrice') if normal else None,
                'foil_price':   foil.get('marketPrice') if foil else None,
                'source':       'TCGPlayer Official API',
                'product_id':   product_id,
                'card_name':    results[0].get('name', card_name),
                'set_name':     results[0].get('groupName', ''),
                'timestamp':    datetime.now().isoformat(),
            }

            self.price_cache[cache_key] = {
                'price_data': result,
                'timestamp':  result['timestamp'],
            }
            self._save_cache()
            return result

        except requests.RequestException as e:
            logger.error(f"TCGPlayer API request failed for {card_name!r}: {e}")
            # Fallback to Scryfall
            logger.info("Falling back to Scryfall price feed")
            return self._fetch_via_scryfall(card_name, set_name)
