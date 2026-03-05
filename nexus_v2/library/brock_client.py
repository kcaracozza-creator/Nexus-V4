#!/usr/bin/env python3
"""
NEXUS V2 - Brock Library Client
Connects to Brock (192.168.1.219) as the master library database.
Local SQLite is read cache only - writes go to Brock.
"""

import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class BrockLibraryClient:
    """
    Client for Brock's master library database.

    Architecture:
    - Brock (192.168.1.219:5001) = Master database on 160GB HDD
    - Desktop/Zultan = Use this client, local cache for offline
    """

    def __init__(self, brock_url: str = "http://192.168.1.219:5001", timeout: int = 5):
        self.brock_url = brock_url.rstrip('/')
        self.timeout = timeout
        self._online = None

    def _request(self, method: str, endpoint: str, data: Any = None) -> Dict:
        """Make request to Brock API."""
        url = f"{self.brock_url}/api/library{endpoint}"
        try:
            if method == 'GET':
                resp = requests.get(url, timeout=self.timeout)
            elif method == 'POST':
                resp = requests.post(url, json=data, timeout=self.timeout)
            elif method == 'DELETE':
                resp = requests.delete(url, timeout=self.timeout)
            else:
                return {'success': False, 'error': f'Unknown method: {method}'}

            self._online = True
            return resp.json()
        except requests.exceptions.Timeout:
            self._online = False
            return {'success': False, 'error': 'Brock timeout', 'offline': True}
        except requests.exceptions.ConnectionError:
            self._online = False
            return {'success': False, 'error': 'Brock offline', 'offline': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def is_online(self) -> bool:
        """Check if Brock is reachable."""
        if self._online is not None:
            return self._online
        result = self.stats()
        return result.get('success', False)

    # === Read Operations ===

    def stats(self) -> Dict:
        """Get library statistics."""
        return self._request('GET', '/stats')

    def get(self, call_number: str) -> Optional[Dict]:
        """Get card by call number."""
        result = self._request('GET', f'/card/{call_number}')
        return result.get('card') if result.get('success') else None

    def get_all(self, limit: int = 1000, offset: int = 0) -> Dict:
        """Get all cards (paginated)."""
        return self._request('GET', f'/all?limit={limit}&offset={offset}')

    def search(self, name: str = None, set_code: str = None, box_id: str = None,
               min_price: float = None, max_price: float = None,
               listing_status: str = None, limit: int = 100) -> List[Dict]:
        """Search library with filters."""
        filters = {'limit': limit}
        if name:
            filters['name'] = name
        if set_code:
            filters['set_code'] = set_code
        if box_id:
            filters['box_id'] = box_id
        if min_price is not None:
            filters['min_price'] = min_price
        if max_price is not None:
            filters['max_price'] = max_price
        if listing_status:
            filters['listing_status'] = listing_status

        result = self._request('POST', '/search', filters)
        return result.get('cards', []) if result.get('success') else []

    # === Write Operations (all go to Brock) ===

    def add(self, card: Dict) -> bool:
        """Add or update a card on Brock."""
        result = self._request('POST', '/card', card)
        return result.get('success', False)

    def delete(self, call_number: str) -> bool:
        """Delete a card from Brock."""
        result = self._request('DELETE', f'/card/{call_number}')
        return result.get('success', False)

    def bulk_add(self, cards: List[Dict]) -> Dict:
        """Add multiple cards at once."""
        return self._request('POST', '/bulk', cards)

    # === Listing Operations ===

    def mark_pending(self, call_number: str, listing_id: str) -> bool:
        """Mark card as pending sale."""
        result = self._request('POST', '/listing/pending', {
            'call_number': call_number,
            'listing_id': listing_id
        })
        return result.get('success', False)

    def mark_sold(self, call_number: str, sold_price: float = None) -> bool:
        """Mark card as sold."""
        result = self._request('POST', '/listing/sold', {
            'call_number': call_number,
            'sold_price': sold_price
        })
        return result.get('success', False)

    def mark_available(self, call_number: str) -> bool:
        """Mark card as available (cancel listing)."""
        result = self._request('POST', '/listing/available', {
            'call_number': call_number
        })
        return result.get('success', False)

    # === Sync Operations ===

    def sync_from_local(self, local_db) -> Dict:
        """
        Push all local cards to Brock (initial sync or recovery).

        Args:
            local_db: LocalLibraryDB instance with cards to push

        Returns:
            Dict with sync results
        """
        if not self.is_online():
            return {'success': False, 'error': 'Brock offline'}

        all_cards = local_db.get_all()
        cards_list = list(all_cards.values())

        if not cards_list:
            return {'success': True, 'synced': 0, 'message': 'No cards to sync'}

        # Bulk upload in batches
        batch_size = 100
        total_synced = 0
        errors = []

        for i in range(0, len(cards_list), batch_size):
            batch = cards_list[i:i + batch_size]
            result = self.bulk_add(batch)
            if result.get('success'):
                total_synced += result.get('added', 0)
                if result.get('errors'):
                    errors.extend(result['errors'])
            else:
                errors.append(result.get('error', 'Unknown error'))

        return {
            'success': True,
            'synced': total_synced,
            'total': len(cards_list),
            'errors': errors
        }

    def sync_to_local(self, local_db, full: bool = False) -> Dict:
        """
        Pull cards from Brock to local cache.

        Args:
            local_db: LocalLibraryDB instance to update
            full: If True, replace all local data. If False, merge.

        Returns:
            Dict with sync results
        """
        if not self.is_online():
            return {'success': False, 'error': 'Brock offline'}

        # Get all cards from Brock (paginated)
        all_cards = []
        offset = 0
        limit = 1000

        while True:
            result = self.get_all(limit=limit, offset=offset)
            if not result.get('success'):
                return {'success': False, 'error': result.get('error')}

            cards = result.get('cards', [])
            all_cards.extend(cards)

            if len(cards) < limit:
                break
            offset += limit

        # Update local database
        synced = 0
        for card in all_cards:
            if local_db.add(card):
                synced += 1

        return {
            'success': True,
            'synced': synced,
            'total': len(all_cards)
        }
