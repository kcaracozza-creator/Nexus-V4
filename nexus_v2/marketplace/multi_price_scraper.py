"""
NEXUS Multi-Site Price Scraper
==============================
Aggregates pricing data from 5 sources:
1. Scryfall (API) - Already integrated
2. TCGPlayer (API/scrape)
3. Card Kingdom (scrape)
4. CoolStuffInc (scrape)
5. ChannelFireball (scrape)

Usage:
    from marketplace.multi_price_scraper import MultiPriceScraper
    scraper = MultiPriceScraper()
    prices = scraper.get_prices("Black Lotus", "LEA", "232")
"""

import requests
import re
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse

# Optional: BeautifulSoup for HTML parsing
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("[WARN] BeautifulSoup not installed. Install with: pip install beautifulsoup4")


@dataclass
class PriceResult:
    """Price from a single source"""
    source: str
    price: float
    price_foil: Optional[float] = None
    url: str = ""
    condition: str = "NM"
    in_stock: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AggregatedPrice:
    """Aggregated price from all sources"""
    card_name: str
    set_code: str
    collector_number: str

    prices: List[PriceResult] = field(default_factory=list)

    @property
    def lowest_price(self) -> float:
        """Get lowest available price"""
        available = [p.price for p in self.prices if p.price > 0 and p.in_stock]
        return min(available) if available else 0

    @property
    def highest_price(self) -> float:
        """Get highest price"""
        available = [p.price for p in self.prices if p.price > 0]
        return max(available) if available else 0

    @property
    def average_price(self) -> float:
        """Get average price across sources"""
        available = [p.price for p in self.prices if p.price > 0]
        return sum(available) / len(available) if available else 0

    @property
    def price_spread(self) -> float:
        """Price difference between highest and lowest"""
        return self.highest_price - self.lowest_price

    @property
    def best_deal(self) -> Optional[PriceResult]:
        """Get best deal (lowest in-stock price)"""
        available = [p for p in self.prices if p.price > 0 and p.in_stock]
        if not available:
            return None
        return min(available, key=lambda x: x.price)


class MultiPriceScraper:
    """
    Multi-site price aggregator for MTG cards.
    Scrapes 5 sources for price comparison.
    """

    # Rate limiting (requests per second)
    RATE_LIMIT = 0.5  # 2 requests per second max

    # User agent for requests
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __init__(self, data_dir: str = None):
        """Initialize the scraper"""
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)

        # Price cache
        self.cache_file = self.data_dir / "multi_price_cache.json"
        self.cache = self._load_cache()

        # Session for requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/json",
            "Accept-Language": "en-US,en;q=0.9"
        })

        # Track last request times per source
        self._last_request = {}

        print("[OK] Multi-site price scraper initialized")
        print(f"     BeautifulSoup: {'Available' if BS4_AVAILABLE else 'Not available'}")

    def _load_cache(self) -> dict:
        """Load price cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_cache(self):
        """Save price cache to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"[WARN] Cache save failed: {e}")

    def _rate_limit(self, source: str):
        """Apply rate limiting per source"""
        if source in self._last_request:
            elapsed = time.time() - self._last_request[source]
            if elapsed < self.RATE_LIMIT:
                time.sleep(self.RATE_LIMIT - elapsed)
        self._last_request[source] = time.time()

    def _get_cache_key(self, name: str, set_code: str, number: str) -> str:
        """Generate cache key"""
        return f"{name}|{set_code}|{number}".lower()

    # ================================================================
    # SOURCE 1: SCRYFALL (API)
    # ================================================================

    def _fetch_scryfall(self, name: str, set_code: str, number: str) -> Optional[PriceResult]:
        """Fetch price from Scryfall API"""
        self._rate_limit("scryfall")

        try:
            # Try exact match first
            url = f"https://api.scryfall.com/cards/{set_code.lower()}/{number}"
            resp = self.session.get(url, timeout=10)

            if resp.status_code == 404:
                # Fallback to fuzzy search
                search_url = f"https://api.scryfall.com/cards/named?fuzzy={urllib.parse.quote(name)}&set={set_code}"
                resp = self.session.get(search_url, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                prices = data.get('prices', {})

                return PriceResult(
                    source="Scryfall",
                    price=float(prices.get('usd') or 0),
                    price_foil=float(prices.get('usd_foil') or 0) if prices.get('usd_foil') else None,
                    url=data.get('purchase_uris', {}).get('tcgplayer', ''),
                    in_stock=True
                )
        except Exception as e:
            print(f"[WARN] Scryfall error: {e}")

        return None

    # ================================================================
    # SOURCE 2: TCGPLAYER (scrape search results)
    # ================================================================

    def _fetch_tcgplayer(self, name: str, set_code: str, number: str) -> Optional[PriceResult]:
        """Fetch price from TCGPlayer"""
        if not BS4_AVAILABLE:
            return None

        self._rate_limit("tcgplayer")

        try:
            # Search URL
            search_term = urllib.parse.quote(f"{name} {set_code}")
            url = f"https://www.tcgplayer.com/search/magic/product?productLineName=magic&q={search_term}"

            resp = self.session.get(url, timeout=15)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find price listing
                price_elem = soup.select_one('.inventory__price-with-shipping')
                if not price_elem:
                    price_elem = soup.select_one('[class*="price"]')

                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Extract number from price text
                    match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if match:
                        return PriceResult(
                            source="TCGPlayer",
                            price=float(match.group(1)),
                            url=url,
                            in_stock=True
                        )
        except Exception as e:
            print(f"[WARN] TCGPlayer error: {e}")

        return None

    # ================================================================
    # SOURCE 3: CARD KINGDOM (scrape)
    # ================================================================

    def _fetch_cardkingdom(self, name: str, set_code: str, number: str) -> Optional[PriceResult]:
        """Fetch price from Card Kingdom"""
        if not BS4_AVAILABLE:
            return None

        self._rate_limit("cardkingdom")

        try:
            # Card Kingdom URL format
            card_slug = name.lower().replace(' ', '-').replace(',', '').replace("'", '')
            url = f"https://www.cardkingdom.com/mtg/{set_code.lower()}/{card_slug}"

            resp = self.session.get(url, timeout=15)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find NM price
                price_elem = soup.select_one('.stylePrice')
                if not price_elem:
                    price_elem = soup.select_one('.itemAddPrice')

                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if match:
                        # Check stock
                        out_of_stock = soup.select_one('.outOfStock') is not None

                        return PriceResult(
                            source="Card Kingdom",
                            price=float(match.group(1)),
                            url=url,
                            in_stock=not out_of_stock
                        )
        except Exception as e:
            print(f"[WARN] Card Kingdom error: {e}")

        return None

    # ================================================================
    # SOURCE 4: COOLSTUFFINC (scrape)
    # ================================================================

    def _fetch_coolstuffinc(self, name: str, set_code: str, number: str) -> Optional[PriceResult]:
        """Fetch price from CoolStuffInc"""
        if not BS4_AVAILABLE:
            return None

        self._rate_limit("coolstuffinc")

        try:
            # Search URL
            search_term = urllib.parse.quote(name)
            url = f"https://www.coolstuffinc.com/main_search.php?pa=searchOnName&page=1&resultsPerPage=25&q={search_term}"

            resp = self.session.get(url, timeout=15)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find product with matching set
                products = soup.select('.product')
                for product in products:
                    set_elem = product.select_one('.setName')
                    if set_elem and set_code.upper() in set_elem.get_text().upper():
                        price_elem = product.select_one('.price')
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            match = re.search(r'\$?(\d+\.?\d*)', price_text)
                            if match:
                                return PriceResult(
                                    source="CoolStuffInc",
                                    price=float(match.group(1)),
                                    url="https://www.coolstuffinc.com",
                                    in_stock=True
                                )
        except Exception as e:
            print(f"[WARN] CoolStuffInc error: {e}")

        return None

    # ================================================================
    # SOURCE 5: CHANNELFIREBALL (scrape)
    # ================================================================

    def _fetch_channelfireball(self, name: str, set_code: str, number: str) -> Optional[PriceResult]:
        """Fetch price from ChannelFireball"""
        if not BS4_AVAILABLE:
            return None

        self._rate_limit("channelfireball")

        try:
            # Search URL
            search_term = urllib.parse.quote(name)
            url = f"https://www.channelfireball.com/search?q={search_term}"

            resp = self.session.get(url, timeout=15)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find price
                price_elem = soup.select_one('.product-price')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if match:
                        return PriceResult(
                            source="ChannelFireball",
                            price=float(match.group(1)),
                            url=url,
                            in_stock=True
                        )
        except Exception as e:
            print(f"[WARN] ChannelFireball error: {e}")

        return None

    # ================================================================
    # MAIN AGGREGATION
    # ================================================================

    def get_prices(
        self,
        name: str,
        set_code: str,
        collector_number: str = "",
        use_cache: bool = True,
        parallel: bool = True
    ) -> AggregatedPrice:
        """
        Get prices from all 5 sources for a card.

        Args:
            name: Card name
            set_code: Set code (e.g., "LEA", "MH2")
            collector_number: Collector number
            use_cache: Whether to use cached prices (1 hour cache)
            parallel: Fetch from sources in parallel

        Returns:
            AggregatedPrice with prices from all sources
        """
        cache_key = self._get_cache_key(name, set_code, collector_number)

        # Check cache
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
            # Cache for 1 hour
            if (datetime.now() - cache_time).total_seconds() < 3600:
                result = AggregatedPrice(
                    card_name=name,
                    set_code=set_code,
                    collector_number=collector_number
                )
                for p in cached.get('prices', []):
                    result.prices.append(PriceResult(**p))
                return result

        # Fetch from all sources
        result = AggregatedPrice(
            card_name=name,
            set_code=set_code,
            collector_number=collector_number
        )

        fetch_methods = [
            ("Scryfall", self._fetch_scryfall),
            ("TCGPlayer", self._fetch_tcgplayer),
            ("Card Kingdom", self._fetch_cardkingdom),
            ("CoolStuffInc", self._fetch_coolstuffinc),
            ("ChannelFireball", self._fetch_channelfireball),
        ]

        if parallel:
            # Parallel fetching
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(method, name, set_code, collector_number): source
                    for source, method in fetch_methods
                }

                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        price_result = future.result()
                        if price_result:
                            result.prices.append(price_result)
                    except Exception as e:
                        print(f"[WARN] {source} failed: {e}")
        else:
            # Sequential fetching
            for source, method in fetch_methods:
                try:
                    price_result = method(name, set_code, collector_number)
                    if price_result:
                        result.prices.append(price_result)
                except Exception as e:
                    print(f"[WARN] {source} failed: {e}")

        # Cache result
        self.cache[cache_key] = {
            'timestamp': datetime.now().isoformat(),
            'prices': [
                {
                    'source': p.source,
                    'price': p.price,
                    'price_foil': p.price_foil,
                    'url': p.url,
                    'condition': p.condition,
                    'in_stock': p.in_stock,
                    'timestamp': p.timestamp
                }
                for p in result.prices
            ]
        }
        self._save_cache()

        return result

    def get_bulk_prices(
        self,
        cards: List[Dict[str, str]],
        callback=None
    ) -> Dict[str, AggregatedPrice]:
        """
        Get prices for multiple cards.

        Args:
            cards: List of dicts with 'name', 'set_code', 'collector_number'
            callback: Optional progress callback(current, total, card_name)

        Returns:
            Dict mapping card key to AggregatedPrice
        """
        results = {}
        total = len(cards)

        for i, card in enumerate(cards):
            name = card.get('name', '')
            set_code = card.get('set_code', '')
            number = card.get('collector_number', '')

            if callback:
                callback(i + 1, total, name)

            key = self._get_cache_key(name, set_code, number)
            results[key] = self.get_prices(name, set_code, number)

        return results

    def format_price_comparison(self, agg_price: AggregatedPrice) -> str:
        """Format price comparison as readable string"""
        lines = [
            f"Price Comparison: {agg_price.card_name} ({agg_price.set_code})",
            "=" * 50
        ]

        for p in sorted(agg_price.prices, key=lambda x: x.price if x.price > 0 else 999):
            stock = "In Stock" if p.in_stock else "Out of Stock"
            price_str = f"${p.price:.2f}" if p.price > 0 else "N/A"
            lines.append(f"  {p.source:15} {price_str:>10}  [{stock}]")

        lines.append("-" * 50)
        lines.append(f"  Lowest:  ${agg_price.lowest_price:.2f}")
        lines.append(f"  Average: ${agg_price.average_price:.2f}")
        lines.append(f"  Spread:  ${agg_price.price_spread:.2f}")

        if agg_price.best_deal:
            lines.append(f"\n  Best Deal: {agg_price.best_deal.source} @ ${agg_price.best_deal.price:.2f}")

        return "\n".join(lines)


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Multi-Site Price Scraper - Test")
    print("=" * 60 + "\n")

    scraper = MultiPriceScraper()

    # Test card
    print("Fetching prices for: Lightning Bolt (2ED)")
    result = scraper.get_prices("Lightning Bolt", "2ED", "157")

    print(scraper.format_price_comparison(result))
