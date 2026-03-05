"""
NEXUS Marketplace Client
Connects local NEXUS software to the marketplace server
"""

import json
import os
import socket
from pathlib import Path
from typing import List, Optional
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not installed. Install with: pip install requests")
    requests = None

# Flow 9: Market data reporting (sale events)
try:
    from nexus_v2.integrations.market_data_client import report_sale as _report_sale_event
    MARKET_DATA_AVAILABLE = True
except ImportError:
    MARKET_DATA_AVAILABLE = False


# Marketplace API prefix - ZULTAN Flask server uses /api
API_PREFIX = '/api'

def get_default_marketplace_url() -> str:
    """
    Determine marketplace server URL based on environment:
    - Production: https://nexus-marketplace-api.kcaracozza.workers.dev
    - Dev/Local: Set NEXUS_MARKETPLACE_URL=http://localhost:5001
    - Custom: Set NEXUS_MARKETPLACE_URL environment variable

    NOTE: Marketplace is on Cloudflare Workers, NOT on ZULTAN.
    ZULTAN (192.168.1.152:8000) serves card data APIs.
    Marketplace (listings, cart, orders) lives on Cloudflare.
    """
    # Check environment variable first (for dev/testing)
    env_url = os.environ.get('NEXUS_MARKETPLACE_URL')
    if env_url:
        return env_url

    # Production default - ZULTAN marketplace server
    return "http://192.168.1.152:5000"


class MarketplaceClient:
    """
    Client for connecting NEXUS to the marketplace server

    Server Location:
    - Production: https://nexus-marketplace-api.kcaracozza.workers.dev
    - Website: https://nexus-cards.com
    - Development: Set NEXUS_MARKETPLACE_URL=http://localhost:5001

    All endpoints use /v1 prefix (Cloudflare Worker convention)
    """

    def __init__(self, server_url: str = None):
        if requests is None:
            raise ImportError("requests library is required. Install with: pip install requests")
        
        # Auto-detect server URL if not provided
        if server_url is None:
            server_url = get_default_marketplace_url()

        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        self.user = None
        # Look for config in project root (parent of nexus_v2)
        project_root = Path(__file__).parent.parent.parent
        self.config_file = project_root / "nexus_marketplace_config.json"
        self._load_config()

    def _load_config(self):
        """Load saved configuration"""
        if self.config_file.exists():
            try:
                config = json.loads(self.config_file.read_text())
                self.server_url = config.get('server_url', self.server_url)
                self.user = config.get('user')
                token = config.get('token')
                if token:
                    self.session.headers['Authorization'] = f'Bearer {token}'
            except Exception:
                pass

    def _save_config(self):
        """Save configuration"""
        config = {
            'server_url': self.server_url,
            'user': self.user,
            'token': self.session.headers.get('Authorization', '').replace('Bearer ', '')
        }
        self.config_file.write_text(json.dumps(config, indent=2))

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request to marketplace API"""
        try:
            r = self.session.get(
                f"{self.server_url}{API_PREFIX}{endpoint}",
                params=params,
                timeout=15
            )
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
        except json.JSONDecodeError:
            return {'error': 'Invalid response from server'}

    def _post(self, endpoint: str, data: dict = None) -> dict:
        """Make POST request to marketplace API"""
        try:
            r = self.session.post(
                f"{self.server_url}{API_PREFIX}{endpoint}",
                json=data,
                timeout=30
            )
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
        except json.JSONDecodeError:
            return {'error': 'Invalid response from server'}

    def _put(self, endpoint: str, data: dict = None) -> dict:
        """Make PUT request to marketplace API"""
        try:
            r = self.session.put(
                f"{self.server_url}{API_PREFIX}{endpoint}",
                json=data,
                timeout=30
            )
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
        except json.JSONDecodeError:
            return {'error': 'Invalid response from server'}

    def _delete(self, endpoint: str) -> dict:
        """Make DELETE request to marketplace API"""
        try:
            r = self.session.delete(
                f"{self.server_url}{API_PREFIX}{endpoint}",
                timeout=15
            )
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
        except json.JSONDecodeError:
            return {'error': 'Invalid response from server'}

    # ============================================================
    # CONNECTION & AUTH
    # ============================================================
    def check_health(self) -> dict:
        """Check if server is online"""
        try:
            r = self.session.get(f"{self.server_url}/health", timeout=10)
            return r.json()
        except Exception as e:
            return {'error': str(e), 'status': 'offline'}

    def is_connected(self) -> bool:
        """Check connection status"""
        result = self.check_health()
        status = result.get('status', '')
        return status in ('online', 'healthy') and 'error' not in result

    def register(self, username: str, email: str, password: str,
                 role: str = 'buyer', shop_name: str = None) -> dict:
        """Register new account"""
        data = {
            'username': username,
            'email': email,
            'password': password,
            'role': role
        }
        if shop_name and role == 'seller':
            data['shop_name'] = shop_name

        result = self._post('/auth/register', data)

        if result.get('user'):
            self.user = result['user']
            token = result.get('token')
            if token:
                self.session.headers['Authorization'] = f'Bearer {token}'
            self._save_config()

        return result

    def login(self, email: str, password: str) -> dict:
        """Login to marketplace"""
        result = self._post('/auth/login', {
            'email': email,
            'password': password
        })

        if result.get('user'):
            self.user = result['user']
            token = result.get('token')
            if token:
                self.session.headers['Authorization'] = f'Bearer {token}'
            self._save_config()

        return result

    def logout(self) -> dict:
        """Logout from marketplace"""
        result = self._post('/auth/logout')
        self.user = None
        self.session.headers.pop('Authorization', None)
        self._save_config()
        return result

    def get_current_user(self) -> dict:
        """Get current logged-in user"""
        result = self._get('/auth/me')
        if result.get('user'):
            self.user = result['user']
        return result

    # ============================================================
    # LISTINGS (Browse Marketplace)
    # ============================================================
    def browse_listings(self, page: int = 1, per_page: int = 48,
                        search: str = None, min_price: float = None,
                        max_price: float = None, condition: str = None,
                        rarity: str = None, foil: bool = None,
                        sort: str = 'newest') -> dict:
        """Browse marketplace listings"""
        params = {
            'page': page,
            'per_page': per_page,
            'sort': sort
        }
        if search:
            params['search'] = search
        if min_price is not None:
            params['min_price'] = min_price
        if max_price is not None:
            params['max_price'] = max_price
        if condition:
            params['condition'] = condition
        if rarity:
            params['rarity'] = rarity
        if foil is not None:
            params['foil'] = 'true' if foil else 'false'

        return self._get('/listings', params)

    def get_listing(self, listing_id: str) -> dict:
        """Get single listing details"""
        return self._get(f'/listings/{listing_id}')

    def create_listing(self, card_name: str, price: float, quantity: int = 1,
                       condition: str = 'NM', set_name: str = None,
                       set_code: str = None, rarity: str = None,
                       foil: bool = False, language: str = 'English',
                       collector_number: str = None, image_url: str = None,
                       scryfall_id: str = None) -> dict:
        """Create a new listing (requires seller account)"""
        data = {
            'card_name': card_name,
            'price': price,
            'quantity': quantity,
            'condition': condition,
            'foil': foil,
            'language': language
        }
        if set_name:
            data['set_name'] = set_name
        if set_code:
            data['set_code'] = set_code
        if rarity:
            data['rarity'] = rarity
        if collector_number:
            data['collector_number'] = collector_number
        if image_url:
            data['image_url'] = image_url
        if scryfall_id:
            data['scryfall_id'] = scryfall_id

        return self._post('/listings', data)

    def delete_listing(self, listing_id: str) -> dict:
        """Delete a listing"""
        return self._delete(f'/listings/{listing_id}')

    # ============================================================
    # CART
    # ============================================================
    def get_cart(self) -> dict:
        """Get current cart (requires logged-in user)"""
        if not self.user:
            return {'error': 'Not logged in'}
        user_id = self.user.get('id', self.user.get('user_id', ''))
        return self._get(f'/cart/{user_id}')

    def add_to_cart(self, listing_id: str, quantity: int = 1) -> dict:
        """Add item to cart"""
        return self._post('/cart', {
            'listing_id': listing_id,
            'quantity': quantity
        })

    def update_cart_item(self, item_id: str, quantity: int) -> dict:
        """Update cart item quantity"""
        return self._put(f'/cart/{item_id}', {'quantity': quantity})

    def remove_from_cart(self, item_id: str) -> dict:
        """Remove item from cart"""
        return self._delete(f'/cart/item/{item_id}')

    def clear_cart(self) -> dict:
        """Clear entire cart"""
        if not self.user:
            return {'error': 'Not logged in'}
        user_id = self.user.get('id', self.user.get('user_id', ''))
        return self._post('/cart/clear', {'user_id': user_id})

    # ============================================================
    # ORDERS & PAYMENT
    # ============================================================
    def get_orders(self, role: str = 'buyer') -> dict:
        """Get user's orders (buyer or seller)"""
        return self._get(f'/orders?role={role}')

    def get_order(self, order_id: str) -> dict:
        """Get single order details"""
        return self._get(f'/orders/{order_id}')

    def create_order(self, shipping_address: str) -> dict:
        """Create order from cart (checkout)"""
        return self._post('/orders', {
            'shipping_address': shipping_address
        })

    def process_payment(self, order_id: str, source_id: str) -> dict:
        """Process Square payment for order"""
        return self._post('/payment/create', {
            'order_id': order_id,
            'source_id': source_id
        })

    def get_payment_status(self, order_id: str) -> dict:
        """Check payment status for order"""
        return self._get(f'/payment/status/{order_id}')

    def update_order_status(self, order_id: str, status: str, 
                           tracking_number: str = None) -> dict:
        """Update order status (seller only)"""
        data = {'status': status}
        if tracking_number:
            data['tracking_number'] = tracking_number
        return self._put(f'/orders/{order_id}/status', data)

    # ============================================================
    # SELLER DASHBOARD
    # ============================================================
    def get_seller_stats(self) -> dict:
        """Get seller dashboard stats"""
        return self._get('/seller/stats')

    def get_my_listings(self, status: str = None) -> dict:
        """Get my listings (seller only)"""
        endpoint = '/listings/mine'
        if status:
            endpoint += f'?status={status}'
        return self._get(endpoint)

    def update_seller_profile(self, **kwargs) -> dict:
        """Update seller profile"""
        return self._put('/seller/profile', kwargs)

    # ============================================================
    # SUBSCRIPTION
    # ============================================================
    def get_subscription(self) -> dict:
        """Get current subscription status"""
        return self._get('/payments/subscription')

    def get_payment_config(self) -> dict:
        """Get payment configuration"""
        return self._get('/payments/config')

    # ============================================================
    # BULK OPERATIONS (for NEXUS integration)
    # ============================================================
    def bulk_create_listings(self, cards: List[dict], library_db=None) -> dict:
        """
        Create multiple listings at once from NEXUS scanned cards.

        Each card dict should have:
        - card_name (required)
        - price (required)
        - quantity (default 1)
        - condition (default NM)
        - set_name, set_code, rarity, foil, image_url, scryfall_id (optional)
        - call_number (optional, for library tracking)

        If library_db is provided, cards will be marked as 'pending' with their listing_id.
        """
        results = {'success': [], 'failed': [], 'pending_marked': []}

        for card in cards:
            result = self.create_listing(
                card_name=card.get('card_name') or card.get('name'),
                price=card.get('price') or card.get('market_value', 0.99),
                quantity=card.get('quantity', 1),
                condition=card.get('condition', 'NM'),
                set_name=card.get('set_name'),
                set_code=card.get('set_code') or card.get('set'),
                rarity=card.get('rarity'),
                foil=card.get('foil', False),
                language=card.get('language', 'English'),
                collector_number=card.get('collector_number'),
                image_url=card.get('image_url') or card.get('image'),
                scryfall_id=card.get('scryfall_id')
            )

            if result.get('error'):
                results['failed'].append({
                    'card': card.get('card_name') or card.get('name'),
                    'call_number': card.get('call_number'),
                    'error': result['error']
                })
            else:
                listing_id = result.get('listing', {}).get('id')
                results['success'].append(listing_id)

                # Mark card as pending in library if we have call_number
                call_number = card.get('call_number')
                if library_db and call_number and listing_id:
                    try:
                        library_db.mark_pending(call_number, listing_id)
                        results['pending_marked'].append(call_number)
                    except Exception as e:
                        print(f"[WARN] Failed to mark {call_number} pending: {e}")

        results['total'] = len(cards)
        results['success_count'] = len(results['success'])
        results['failed_count'] = len(results['failed'])
        results['pending_count'] = len(results['pending_marked'])

        return results


class NexusMarketplaceIntegration:
    """
    Integration layer between NexusLibrarySystem and Marketplace.
    Tracks listing status in library database.
    """

    def __init__(self, library_system, server_url: str = None,
                 library_db=None):
        self.library = library_system
        self.client = MarketplaceClient(server_url)  # Uses get_default_marketplace_url() if None
        self.library_db = library_db  # LibraryDB instance for status tracking

    def list_box_on_marketplace(self, box_id: str, pricing_strategy: str = 'market') -> dict:
        """
        List all cards from a box on the marketplace.
        Cards are marked as 'pending' in library_db when successfully listed.

        pricing_strategy: 'market' (use market prices), 'fixed' (use stored prices),
                         or a multiplier like '0.9' for 90% of market
        """
        if not self.client.user:
            return {'error': 'Not logged in to marketplace'}

        if box_id not in self.library.box_inventory:
            return {'error': f'Box {box_id} not found'}

        cards = self.library.box_inventory[box_id]
        listings = []

        for card in cards:
            if not isinstance(card, dict):
                continue

            # Calculate price
            market_price = card.get('market_value') or card.get('price', 0)
            if pricing_strategy == 'market':
                price = market_price
            elif pricing_strategy == 'fixed':
                price = card.get('price', market_price)
            else:
                try:
                    multiplier = float(pricing_strategy)
                    price = market_price * multiplier
                except ValueError:
                    price = market_price

            # Round to 2 decimal places, minimum $0.25
            price = max(0.25, round(price, 2))

            listings.append({
                'card_name': card.get('name'),
                'price': price,
                'quantity': card.get('quantity', 1),
                'condition': card.get('condition', 'NM'),
                'set_name': card.get('set_name'),
                'set_code': card.get('set'),
                'rarity': card.get('rarity'),
                'foil': card.get('foil', False),
                'image_url': card.get('image'),
                'scryfall_id': card.get('scryfall_id'),
                'call_number': card.get('call_number')  # For library tracking
            })

        return self.client.bulk_create_listings(listings, library_db=self.library_db)

    def sync_inventory_to_marketplace(self, min_value: float = 1.0) -> dict:
        """
        Sync entire inventory to marketplace (cards above min_value).
        Cards are marked as 'pending' in library_db when successfully listed.
        """
        if not self.client.user:
            return {'error': 'Not logged in to marketplace'}

        all_cards = []

        for box_id, cards in self.library.box_inventory.items():
            for card in cards:
                if isinstance(card, dict):
                    value = card.get('market_value') or card.get('price', 0)
                    if value >= min_value:
                        # Include call_number for tracking
                        card_copy = card.copy()
                        if 'call_number' not in card_copy:
                            card_copy['call_number'] = card.get('call_number')
                        all_cards.append(card_copy)

        if not all_cards:
            return {'error': 'No cards above minimum value'}

        return self.client.bulk_create_listings(all_cards, library_db=self.library_db)

    def mark_listing_sold(self, listing_id: str, sold_price: float = None) -> bool:
        """Mark a card as sold when order completes."""
        if not self.library_db:
            return False
        card = self.library_db.get_listing_by_id(listing_id)
        if card:
            success = self.library_db.mark_sold(card['call_number'], sold_price)
            
            # ============================================================
            # FLOW 9: Report sale event to ZULTAN (anonymous price signal)
            # Fire-and-forget — never blocks order completion
            # ============================================================
            if success and MARKET_DATA_AVAILABLE and sold_price:
                try:
                    _report_sale_event(
                        card_name=card.get('name', card.get('card_name', '')),
                        sale_price=sold_price,
                        set_code=card.get('set_code', card.get('set', '')),
                        condition=card.get('condition', 'NM'),
                        card_type=card.get('card_type', 'mtg'),
                        channel='marketplace'
                    )
                except Exception:
                    pass  # Never block sales on market data
            
            return success
        return False

    def cancel_listing(self, listing_id: str) -> bool:
        """Mark a card as available when listing is cancelled."""
        if not self.library_db:
            return False
        card = self.library_db.get_listing_by_id(listing_id)
        if card:
            return self.library_db.mark_available(card['call_number'])
        return False


# ============================================================
# EXAMPLE USAGE
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("NEXUS MARKETPLACE CLIENT")
    print("=" * 50)

    client = MarketplaceClient()

    # Check connection
    print("\nChecking marketplace connection...")
    health = client.check_health()

    if health.get('status') == 'online':
        print(f"Connected: {health}")

        # Check if logged in
        user = client.get_current_user()
        if user.get('user'):
            print(f"Logged in as: {user['user']['username']}")
        else:
            print("Not logged in")

        # Browse listings
        print("\nBrowsing listings...")
        listings = client.browse_listings(per_page=5)
        print(f"Found {listings.get('total', 0)} listings")
    else:
        print(f"Marketplace offline: {health}")

    print("\nUsage:")
    print("  client = MarketplaceClient()")
    print("  client.login('email@example.com', 'password')")
    print("  client.browse_listings(search='Black Lotus')")
    print("  client.create_listing('Black Lotus', price=50000.00)")
