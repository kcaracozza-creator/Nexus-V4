"""
YGOProDeck API v7 Integration
Provides access to Yu-Gi-Oh! card database with pricing and images
API Documentation: https://ygoprodeck.com/api-guide/
"""

import requests
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from nexus_v2.data.yugioh_db import YugiohCard


logger = logging.getLogger(__name__)


class YGOProDeckCache:
    """Local caching system for YGOProDeck API responses"""

    def __init__(self, cache_dir: Path = None, cache_days: int = 7):
        """
        Initialize cache system

        Args:
            cache_dir: Directory for cache files (default: nexus_v2/data/cache/yugioh)
            cache_days: Number of days to cache responses
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / 'data' / 'cache' / 'yugioh'

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_duration = timedelta(days=cache_days)

        logger.info(f"YGOProDeck cache initialized at {self.cache_dir}")

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a given key"""
        # Sanitize key for filesystem
        safe_key = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in key)
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response

        Args:
            key: Cache key (card name, ID, or query)

        Returns:
            Cached data or None if not found/expired
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            # Check expiration
            cached_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.now() - cached_time > self.cache_duration:
                logger.debug(f"Cache expired for: {key}")
                cache_path.unlink()  # Delete expired cache
                return None

            logger.debug(f"Cache hit for: {key}")
            return cached['data']

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid cache file for {key}: {e}")
            cache_path.unlink()  # Delete corrupted cache
            return None

    def set(self, key: str, data: Dict[str, Any]):
        """
        Store response in cache

        Args:
            key: Cache key
            data: Data to cache
        """
        cache_path = self._get_cache_path(key)

        cached = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached, f, ensure_ascii=False, indent=2)
            logger.debug(f"Cached: {key}")
        except Exception as e:
            logger.error(f"Failed to cache {key}: {e}")

    def clear(self):
        """Clear all cached data"""
        for cache_file in self.cache_dir.glob('*.json'):
            cache_file.unlink()
        logger.info("YGOProDeck cache cleared")


class YGOProDeckAPI:
    """
    YGOProDeck API v7 client with rate limiting and caching

    API Endpoint: https://db.ygoprodeck.com/api/v7/cardinfo.php
    Rate Limit: 20 requests/second
    """

    BASE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    RATE_LIMIT_MS = 50  # 20 req/sec = 50ms between requests
    MAX_RETRIES = 3

    def __init__(self, cache_enabled: bool = True, cache_days: int = 7):
        """
        Initialize API client

        Args:
            cache_enabled: Enable local caching
            cache_days: Number of days to cache responses
        """
        self.cache_enabled = cache_enabled
        self.cache = YGOProDeckCache(cache_days=cache_days) if cache_enabled else None
        self.last_request_time = 0

        logger.info("YGOProDeck API client initialized")

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        if self.last_request_time > 0:
            elapsed = (time.time() - self.last_request_time) * 1000  # ms
            if elapsed < self.RATE_LIMIT_MS:
                sleep_time = (self.RATE_LIMIT_MS - elapsed) / 1000
                time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, params: Dict[str, Any], use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Make API request with rate limiting and caching

        Args:
            params: Query parameters
            use_cache: Whether to use cache

        Returns:
            API response data or None on failure
        """
        # Generate cache key from params
        cache_key = json.dumps(params, sort_keys=True)

        # Check cache first
        if use_cache and self.cache_enabled:
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                return cached_data

        # Make request with retry logic
        for attempt in range(self.MAX_RETRIES):
            try:
                self._rate_limit()

                response = requests.get(
                    self.BASE_URL,
                    params=params,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()

                    # Cache successful response
                    if use_cache and self.cache_enabled:
                        self.cache.set(cache_key, data)

                    return data

                elif response.status_code == 429:  # Rate limit exceeded
                    logger.warning("Rate limit exceeded, waiting...")
                    time.sleep(1)
                    continue

                else:
                    logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(0.5)
                    continue
                return None

        return None

    def get_card_by_id(self, card_id: int, use_cache: bool = True) -> Optional[YugiohCard]:
        """
        Get card by YGOProDeck ID

        Args:
            card_id: Card ID
            use_cache: Whether to use cache

        Returns:
            YugiohCard or None if not found
        """
        logger.info(f"Fetching card by ID: {card_id}")

        params = {'id': card_id}
        data = self._make_request(params, use_cache)

        if data and 'data' in data and len(data['data']) > 0:
            return YugiohCard.from_api_response(data['data'][0])

        logger.warning(f"Card not found: ID {card_id}")
        return None

    def get_card_by_name(self, name: str, fuzzy: bool = False, use_cache: bool = True) -> Optional[YugiohCard]:
        """
        Get card by exact or fuzzy name match

        Args:
            name: Card name
            fuzzy: Use fuzzy matching (fname parameter)
            use_cache: Whether to use cache

        Returns:
            YugiohCard or None if not found
        """
        logger.info(f"Fetching card by name: {name} (fuzzy={fuzzy})")

        params = {'fname' if fuzzy else 'name': name}
        data = self._make_request(params, use_cache)

        if data and 'data' in data and len(data['data']) > 0:
            return YugiohCard.from_api_response(data['data'][0])

        logger.warning(f"Card not found: {name}")
        return None

    def search_cards(self, query: str = None, **filters) -> List[YugiohCard]:
        """
        Search for cards with filters

        Args:
            query: Fuzzy name search
            **filters: Additional filters:
                - type: Card type (e.g., "Normal Monster", "Spell Card")
                - atk: Attack value
                - def_: Defense value
                - level: Level/Rank
                - race: Monster type (e.g., "Spellcaster", "Dragon")
                - attribute: DARK, LIGHT, etc.
                - archetype: Archetype name
                - sort: Sort field (atk, def, name, level, id)
                - misc: yes/no for TCG legality

        Returns:
            List of YugiohCards matching search
        """
        logger.info(f"Searching cards: query={query}, filters={filters}")

        params = {}

        if query:
            params['fname'] = query

        # Map filter parameters
        filter_map = {
            'type': 'type',
            'atk': 'atk',
            'def_': 'def',  # Convert def_ to def for API
            'level': 'level',
            'race': 'race',
            'attribute': 'attribute',
            'archetype': 'archetype',
            'sort': 'sort',
            'misc': 'misc'
        }

        for key, api_param in filter_map.items():
            if key in filters:
                params[api_param] = filters[key]

        data = self._make_request(params, use_cache=True)

        if data and 'data' in data:
            cards = [YugiohCard.from_api_response(card_data) for card_data in data['data']]
            logger.info(f"Found {len(cards)} cards")
            return cards

        logger.info("No cards found")
        return []

    def get_cards_batch(self, card_ids: List[int], use_cache: bool = True) -> Dict[int, YugiohCard]:
        """
        Get multiple cards by ID in a single request

        Args:
            card_ids: List of card IDs
            use_cache: Whether to use cache

        Returns:
            Dictionary mapping card ID to YugiohCard
        """
        logger.info(f"Fetching {len(card_ids)} cards in batch")

        if not card_ids:
            return {}

        # API accepts comma-separated IDs
        params = {'id': ','.join(map(str, card_ids))}
        data = self._make_request(params, use_cache)

        result = {}
        if data and 'data' in data:
            for card_data in data['data']:
                card = YugiohCard.from_api_response(card_data)
                result[card.id] = card

        logger.info(f"Retrieved {len(result)} cards")
        return result

    def get_all_cards(self, use_cache: bool = True) -> List[YugiohCard]:
        """
        Get all Yu-Gi-Oh! cards in the database

        Warning: This returns 10,000+ cards and takes time. Use sparingly.

        Args:
            use_cache: Whether to use cache

        Returns:
            List of all YugiohCards
        """
        logger.info("Fetching all cards (this may take a while...)")

        data = self._make_request({}, use_cache)

        if data and 'data' in data:
            cards = [YugiohCard.from_api_response(card_data) for card_data in data['data']]
            logger.info(f"Retrieved {len(cards)} total cards")
            return cards

        logger.warning("Failed to retrieve cards")
        return []

    def get_archetypes(self) -> List[str]:
        """
        Get list of all archetype names

        Returns:
            List of archetype names
        """
        logger.info("Fetching archetype list")

        try:
            response = requests.get(
                "https://db.ygoprodeck.com/api/v7/archetypes.php",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    archetypes = [item['archetype_name'] for item in data['data']]
                    logger.info(f"Retrieved {len(archetypes)} archetypes")
                    return archetypes

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch archetypes: {e}")

        return []

    def clear_cache(self):
        """Clear all cached data"""
        if self.cache:
            self.cache.clear()


# Convenience function for quick lookups
def quick_lookup(card_name: str, fuzzy: bool = True) -> Optional[YugiohCard]:
    """
    Quick card lookup helper function

    Args:
        card_name: Card name to search
        fuzzy: Use fuzzy matching

    Returns:
        YugiohCard or None
    """
    api = YGOProDeckAPI()
    return api.get_card_by_name(card_name, fuzzy=fuzzy)


if __name__ == "__main__":
    # Test the API
    logging.basicConfig(level=logging.INFO)

    api = YGOProDeckAPI()

    print("\n=== Testing YGOProDeck API ===\n")

    # Test 1: Get card by ID
    print("Test 1: Get Dark Magician by ID")
    dark_magician = api.get_card_by_id(46986414)
    if dark_magician:
        print(f"  Name: {dark_magician.name}")
        print(f"  Type: {dark_magician.type}")
        print(f"  ATK/DEF: {dark_magician.get_display_stats()}")
        print(f"  Attribute: {dark_magician.attribute}")
        print(f"  Level: {dark_magician.get_level_stars()}")
        print(f"  Price: ${dark_magician.get_best_price():.2f} (Confidence: {dark_magician.get_price_confidence()})")
    print()

    # Test 2: Fuzzy name search
    print("Test 2: Fuzzy search for 'Blue-Eyes'")
    blue_eyes = api.get_card_by_name("Blue-Eyes White Dragon", fuzzy=True)
    if blue_eyes:
        print(f"  Name: {blue_eyes.name}")
        print(f"  Type: {blue_eyes.type}")
        print(f"  Stats: {blue_eyes.get_display_stats()}")
        print(f"  Price: ${blue_eyes.get_best_price():.2f}")
    print()

    # Test 3: Search with filters
    print("Test 3: Search for DARK Spellcaster monsters")
    results = api.search_cards(
        attribute="DARK",
        race="Spellcaster",
        type="Normal Monster"
    )
    print(f"  Found {len(results)} cards")
    for card in results[:3]:
        print(f"    - {card.name} ({card.get_display_stats()})")
    print()

    # Test 4: Batch lookup
    print("Test 4: Batch lookup of 3 cards")
    batch = api.get_cards_batch([46986414, 89631139, 55144522])
    for card_id, card in batch.items():
        print(f"  {card.name} (ID: {card_id})")
    print()

    print("=== All tests complete ===")
