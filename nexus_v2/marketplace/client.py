# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# NEXUS: Universal Collectibles Recognition and Management System
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# 
# Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.
# 
# PATENT PENDING - U.S. Provisional Application Filed November 27, 2025
# Application: 35 U.S.C. \u00a7 111(b)
# Classification: G06V 10/00, G06V 30/19, G06N 3/08, G06Q 30/02, H04N 23/00
# 
# This software is proprietary and confidential. Unauthorized copying,
# modification, distribution, or use is strictly prohibited.
# 
# See LICENSE file for full terms.
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

"""
NEXUS V2 Marketplace Client v3.0
================================
Connects NEXUS V2 to the marketplace server for:
- Multi-seller marketplace integration
- Real-time listing sync
- Order management
- Cart & checkout support
"""

import requests
import logging
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Marketplace server URLs
MARKETPLACE_URLS = [
    "https://nexus-cards.com",
    "https://nexus-marketplace-1.onrender.com",
    "http://localhost:5001"
]


@dataclass
class MarketplaceListing:
    """Card listing for marketplace sync"""
    card_name: str
    set_code: str
    condition: str
    price: float
    quantity: int = 1
    foil: bool = False
    notes: str = ""
    image_url: str = ""
    rarity: str = ""
    set_name: str = ""
    type_line: str = ""
    mana_cost: str = ""
    id: str = ""
    status: str = "Active"
    
    def to_dict(self) -> Dict:
        return asdict(self)


class MarketplaceClient:
    """
    Client for NEXUS Marketplace API v3
    
    Supports multi-seller marketplace with:
    - API key authentication
    - Listing sync from V2 desktop
    - Order management
    """
    
    def __init__(self, base_url: str = None):
        """Initialize marketplace client"""
        self.base_url = base_url
        self._connected = False
        self._server_info = {}
        
        # Seller credentials
        self._seller_id = None
        self._api_key = None
        self._shop_name = None
        
        # Config file path
        self._config_path = Path(__file__).parent.parent / 'data' / 'marketplace_config.json'
        
        # Load saved credentials
        self._load_credentials()
        
        # Auto-connect
        if not base_url:
            self._auto_connect()
        else:
            self._check_connection()
    
    # ============================================
    # CONNECTION MANAGEMENT
    # ============================================
    
    def _auto_connect(self):
        """Auto-detect and connect to marketplace server"""
        for url in MARKETPLACE_URLS:
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    self.base_url = url
                    self._connected = True
                    self._server_info = response.json()
                    logger.info(f"\u2705 Connected to marketplace: {url}")
                    return
            except Exception as e:
                logger.debug(f"Could not connect to {url}: {e}")
                continue
        
        logger.warning("\u26a0\ufe0f Could not connect to any marketplace server")
        self._connected = False
    
    def _check_connection(self):
        """Check connection to marketplace"""
        if not self.base_url:
            self._connected = False
            return
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            self._connected = response.status_code == 200
            if self._connected:
                self._server_info = response.json()
        except Exception:
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def is_registered(self) -> bool:
        return self._api_key is not None
    
    @property
    def shop_name(self) -> str:
        return self._shop_name or "Not Registered"
    
    @property
    def seller_id(self) -> Optional[str]:
        return self._seller_id
    
    def check_server(self) -> bool:
        """Re-check server connection"""
        self._check_connection()
        return self._connected
    
    def get_status(self) -> Dict:
        """Get marketplace server status"""
        if not self._connected:
            return {'status': 'disconnected'}
        
        try:
            response = requests.get(f"{self.base_url}/status", timeout=5)
            return response.json()
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    # ============================================
    # CREDENTIALS MANAGEMENT
    # ============================================
    
    def _load_credentials(self):
        """Load saved seller credentials"""
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r') as f:
                    config = json.load(f)
                    self._seller_id = config.get('seller_id')
                    self._api_key = config.get('api_key')
                    self._shop_name = config.get('shop_name')
                    if self._api_key:
                        logger.info(f"\u2705 Loaded marketplace credentials: {self._shop_name}")
        except Exception as e:
            logger.debug(f"Could not load credentials: {e}")
    
    def _save_credentials(self):
        """Save seller credentials"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, 'w') as f:
                json.dump({
                    'seller_id': self._seller_id,
                    'api_key': self._api_key,
                    'shop_name': self._shop_name
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    def clear_credentials(self):
        """Clear saved credentials (logout)"""
        self._seller_id = None
        self._api_key = None
        self._shop_name = None
        try:
            if self._config_path.exists():
                self._config_path.unlink()
        except Exception:
            pass
    
    def _get_headers(self) -> Dict:
        """Get request headers with API key"""
        headers = {'Content-Type': 'application/json'}
        if self._api_key:
            headers['X-API-Key'] = self._api_key
        return headers
    
    # ============================================
    # SELLER REGISTRATION & AUTH
    # ============================================
    
    def register_seller(self, shop_name: str, email: str, location: str = "") -> Dict:
        """
        Register as a new seller on the marketplace
        
        Args:
            shop_name: Display name for your store
            email: Contact email
            location: Optional location (city, state)
            
        Returns:
            {'success': True, 'seller_id': '...', 'api_key': '...'}
        """
        if not self._connected:
            return {'success': False, 'error': 'Not connected to marketplace'}
        
        try:
            response = requests.post(
                f"{self.base_url}/api/seller/register",
                json={
                    'shop_name': shop_name,
                    'email': email,
                    'location': location
                },
                timeout=10
            )
            
            data = response.json()
            
            if response.status_code == 200 and data.get('success'):
                self._seller_id = data.get('seller_id')
                self._api_key = data.get('api_key')
                self._shop_name = shop_name
                self._save_credentials()
                logger.info(f"\u2705 Registered as seller: {shop_name}")
                return {
                    'success': True,
                    'seller_id': self._seller_id,
                    'api_key': self._api_key,
                    'message': data.get('message', 'Registration successful!')
                }
            
            return {'success': False, 'error': data.get('error', 'Registration failed')}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def set_api_key(self, api_key: str, shop_name: str = None) -> bool:
        """
        Manually set API key (for existing sellers)
        
        Args:
            api_key: Your NEXUS marketplace API key
            shop_name: Optional shop name for display
        """
        self._api_key = api_key
        self._shop_name = shop_name or "My Store"
        self._save_credentials()
        return True
    
    # ============================================
    # LISTING SYNC
    # ============================================
    
    def sync_listings(self, listings: List[Dict], mode: str = "merge") -> Dict:
        """
        Sync listings from V2 to marketplace
        
        This is the main method for pushing your inventory to nexus-cards.com
        
        Args:
            listings: List of listing dicts with card_name, set_code, condition, price, quantity
            mode: 'merge' (add/update) or 'replace' (delete all and replace)
            
        Returns:
            {'success': True, 'added': N, 'updated': N, 'total_listings': N}
        """
        if not self._connected:
            return {'success': False, 'error': 'Not connected to marketplace'}
        
        if not self._api_key:
            return {'success': False, 'error': 'Not registered as seller. Call register_seller() first.'}
        
        try:
            response = requests.post(
                f"{self.base_url}/api/seller/sync",
                headers=self._get_headers(),
                json={
                    'listings': listings,
                    'mode': mode
                },
                timeout=60  # Longer timeout for bulk sync
            )
            
            data = response.json()
            
            if response.status_code == 200 and data.get('success'):
                logger.info(f"\u2705 Synced {data.get('added', 0)} new, {data.get('updated', 0)} updated listings")
                return data
            
            return {'success': False, 'error': data.get('error', 'Sync failed')}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_for_sale(self, cards: List[Dict]) -> Dict:
        """
        List cards for sale on the marketplace.
        Wrapper around sync_listings for the Collection tab's 'List for Sale' feature.
        
        Args:
            cards: List of card dicts with name, set_code, price, quantity, image_url, etc.
            
        Returns:
            {'success': True, 'listing_id': '...', 'count': N} on success
        """
        if not self._connected:
            return {'success': False, 'error': 'Not connected to marketplace'}
        
        if not self._api_key:
            return {'success': False, 'error': 'Not registered as seller. Call register_seller() first.'}
        
        # Convert cards to MarketplaceListing format
        listings = []
        for card in cards:
            listing = {
                'card_name': card.get('name', ''),
                'set_code': card.get('set_code', ''),
                'condition': card.get('condition', 'NM'),
                'price': float(card.get('price', 0)),
                'quantity': int(card.get('quantity', 1)),
                'foil': card.get('is_foil', False),
                'image_url': card.get('image_url', ''),
                'rarity': card.get('rarity', ''),
                'scryfall_id': card.get('scryfall_id', '')
            }
            listings.append(listing)
        
        # Sync to marketplace
        result = self.sync_listings(listings, mode='merge')
        
        if result.get('success'):
            return {
                'success': True,
                'listing_id': f"batch_{len(listings)}",
                'count': len(listings),
                'added': result.get('added', 0),
                'updated': result.get('updated', 0)
            }
        
        return result
    
    def get_my_listings(self) -> Dict:
        """Get your current listings on the marketplace"""
        if not self._connected or not self._api_key:
            return {'success': False, 'listings': [], 'error': 'Not connected or not registered'}
        
        try:
            response = requests.get(
                f"{self.base_url}/api/seller/listings",
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
            return {'success': False, 'listings': [], 'error': response.json().get('error', 'Failed')}
            
        except Exception as e:
            return {'success': False, 'listings': [], 'error': str(e)}
    
    # ============================================
    # ORDER MANAGEMENT
    # ============================================
    
    def get_my_orders(self) -> Dict:
        """Get your incoming orders"""
        if not self._connected or not self._api_key:
            return {'success': False, 'orders': [], 'error': 'Not connected or not registered'}
        
        try:
            response = requests.get(
                f"{self.base_url}/api/seller/orders",
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
            return {'success': False, 'orders': [], 'error': response.json().get('error', 'Failed')}
            
        except Exception as e:
            return {'success': False, 'orders': [], 'error': str(e)}
    
    def update_order(self, order_id: str, status: str = None, tracking: str = None) -> Dict:
        """
        Update an order's status
        
        Args:
            order_id: Order ID
            status: New status (pending, paid, shipped, delivered, completed, cancelled)
            tracking: Tracking number (optional)
        """
        if not self._connected or not self._api_key:
            return {'success': False, 'error': 'Not connected or not registered'}
        
        try:
            data = {}
            if status:
                data['status'] = status
            if tracking:
                data['tracking'] = tracking
            
            response = requests.post(
                f"{self.base_url}/api/seller/order/{order_id}/update",
                headers=self._get_headers(),
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {'success': True, 'order': response.json().get('order')}
            
            return {'success': False, 'error': response.json().get('error', 'Failed')}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ============================================
    # PUBLIC MARKETPLACE BROWSING
    # ============================================
    
    def browse_listings(self, name: str = None, set_code: str = None, 
                        seller: str = None, limit: int = 100) -> Dict:
        """Browse all marketplace listings (public)"""
        if not self._connected:
            return {'listings': [], 'total': 0}
        
        try:
            params = {'limit': limit}
            if name:
                params['name'] = name
            if set_code:
                params['set'] = set_code
            if seller:
                params['seller'] = seller
            
            response = requests.get(
                f"{self.base_url}/api/listings",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            logger.error(f"Browse failed: {e}")
        
        return {'listings': [], 'total': 0}
    
    def get_sellers(self) -> List[Dict]:
        """Get list of all sellers"""
        if not self._connected:
            return []
        
        try:
            response = requests.get(f"{self.base_url}/api/sellers", timeout=10)
            if response.status_code == 200:
                return response.json().get('sellers', [])
        except Exception:
            pass
        
        return []
    
    def get_analytics(self) -> Dict:
        """Get marketplace analytics summary"""
        if not self._connected:
            return {}
        
        try:
            response = requests.get(f"{self.base_url}/analytics/summary", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        
        return {}
    
    # ============================================
    # LEGACY COMPATIBILITY
    # ============================================
    
    def search_cards(self, query: str, limit: int = 20) -> List[Dict]:
        """Legacy method - search cards"""
        result = self.browse_listings(name=query, limit=limit)
        return result.get('listings', [])
    
    def get_price_check(self, card_name: str, set_code: str = None) -> Dict:
        """Get market price for a card"""
        result = self.browse_listings(name=card_name, set_code=set_code, limit=1)
        listings = result.get('listings', [])
        if listings:
            return {
                'name': listings[0].get('card_name'),
                'price': listings[0].get('price'),
                'set': listings[0].get('set_code')
            }
        return {}


# Singleton instance
_marketplace_client: Optional[MarketplaceClient] = None

def get_marketplace() -> MarketplaceClient:
    """Get or create marketplace client singleton"""
    global _marketplace_client
    if _marketplace_client is None:
        _marketplace_client = MarketplaceClient()
    return _marketplace_client


def check_marketplace_status() -> Dict:
    """Quick check of marketplace status"""
    client = get_marketplace()
    return {
        'connected': client.is_connected,
        'registered': client.is_registered,
        'shop_name': client.shop_name,
        'url': client.base_url,
        'status': client.get_status() if client.is_connected else 'disconnected'
    }