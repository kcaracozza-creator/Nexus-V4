"""
MTTGG Marketplace API Client
Handles communication between desktop app and web marketplace
"""

import requests
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib
import time


class MarketplaceAPI:
    """API client for MTTGG Marketplace integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        # API endpoints (will be actual URLs when deployed)
        self.base_url = os.getenv('MTTGG_API_URL', 'https://api.mttgg.com')
        self.api_version = 'v1'
        self.api_key = api_key or os.getenv('MTTGG_API_KEY')
        
        # Session management
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MTTGG Desktop/2.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}'
        
        # Rate limiting
        self.last_request_time = 0
        self.min_delay = 0.1  # 100ms between requests
        
        # Offline queue
        self.offline_queue = []
        self.offline_mode = False
        
    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, method: str, endpoint: str, 
                      data: Optional[Dict] = None) -> Dict:
        """Make HTTP request with error handling"""
        self._rate_limit()
        
        url = f"{self.base_url}/{self.api_version}/{endpoint}"
        
        try:
            if method == 'GET':
                response = self.session.get(url, params=data, timeout=10)
            elif method == 'POST':
                response = self.session.post(url, json=data, timeout=10)
            elif method == 'PUT':
                response = self.session.put(url, json=data, timeout=10)
            elif method == 'DELETE':
                response = self.session.delete(url, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError:
            self.offline_mode = True
            print("⚠️ Connection error - entering offline mode")
            if data and method in ['POST', 'PUT']:
                self._queue_offline_request(method, endpoint, data)
            return {'error': 'offline', 'queued': True}
            
        except requests.exceptions.Timeout:
            return {'error': 'timeout'}
            
        except requests.exceptions.HTTPError as e:
            return {'error': str(e), 'status_code': e.response.status_code}
            
        except Exception as e:
            return {'error': str(e)}
    
    def _queue_offline_request(self, method: str, endpoint: str, data: Dict):
        """Queue request for when connection is restored"""
        self.offline_queue.append({
            'method': method,
            'endpoint': endpoint,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
    
    def process_offline_queue(self) -> int:
        """Process queued requests when connection is restored"""
        if not self.offline_queue:
            return 0
        
        processed = 0
        failed = []
        
        for request in self.offline_queue:
            result = self._make_request(
                request['method'],
                request['endpoint'],
                request['data']
            )
            
            if 'error' not in result:
                processed += 1
            else:
                failed.append(request)
        
        self.offline_queue = failed
        self.offline_mode = len(failed) > 0
        
        return processed
    
    # ==================== VENDOR MANAGEMENT ====================
    
    def register_vendor(self, vendor_data: Dict) -> Dict:
        """Register new vendor account"""
        return self._make_request('POST', 'vendors/register', vendor_data)
    
    def get_vendor_profile(self, vendor_id: str) -> Dict:
        """Get vendor profile information"""
        return self._make_request('GET', f'vendors/{vendor_id}')
    
    def update_vendor_profile(self, vendor_id: str, updates: Dict) -> Dict:
        """Update vendor profile"""
        return self._make_request('PUT', f'vendors/{vendor_id}', updates)
    
    def get_vendor_stats(self, vendor_id: str) -> Dict:
        """Get vendor statistics and analytics"""
        return self._make_request('GET', f'vendors/{vendor_id}/stats')
    
    # ==================== PRODUCT LISTINGS ====================
    
    def create_listing(self, product_data: Dict) -> Dict:
        """Create new product listing"""
        return self._make_request('POST', 'products', product_data)
    
    def update_listing(self, product_id: str, updates: Dict) -> Dict:
        """Update existing product listing"""
        return self._make_request('PUT', f'products/{product_id}', updates)
    
    def delete_listing(self, product_id: str) -> Dict:
        """Delete product listing"""
        return self._make_request('DELETE', f'products/{product_id}')
    
    def bulk_create_listings(self, products: List[Dict]) -> Dict:
        """Create multiple listings at once"""
        return self._make_request('POST', 'products/bulk', {'products': products})
    
    def bulk_update_prices(self, price_updates: List[Dict]) -> Dict:
        """Update prices for multiple products"""
        return self._make_request('PUT', 'products/bulk/prices', {'updates': price_updates})
    
    def get_vendor_listings(self, vendor_id: str, filters: Optional[Dict] = None) -> Dict:
        """Get all listings for a vendor"""
        return self._make_request('GET', f'vendors/{vendor_id}/products', filters)
    
    # ==================== INVENTORY SYNC ====================
    
    def sync_inventory(self, vendor_id: str, inventory: List[Dict]) -> Dict:
        """Sync entire inventory with marketplace"""
        return self._make_request('POST', f'vendors/{vendor_id}/sync', {'inventory': inventory})
    
    def update_inventory_quantities(self, vendor_id: str, quantities: List[Dict]) -> Dict:
        """Update quantities for multiple products"""
        return self._make_request('PUT', f'vendors/{vendor_id}/quantities', {'quantities': quantities})
    
    def get_sync_status(self, vendor_id: str) -> Dict:
        """Check sync status and conflicts"""
        return self._make_request('GET', f'vendors/{vendor_id}/sync/status')
    
    # ==================== ORDER MANAGEMENT ====================
    
    def get_pending_orders(self, vendor_id: str) -> Dict:
        """Get all pending orders for vendor"""
        return self._make_request('GET', f'vendors/{vendor_id}/orders', {'status': 'pending'})
    
    def get_order_details(self, order_id: str) -> Dict:
        """Get detailed order information"""
        return self._make_request('GET', f'orders/{order_id}')
    
    def update_order_status(self, order_id: str, status: str, tracking: Optional[str] = None) -> Dict:
        """Update order status (pending, shipped, delivered, cancelled)"""
        data = {'status': status}
        if tracking:
            data['tracking_number'] = tracking
        return self._make_request('PUT', f'orders/{order_id}/status', data)
    
    def bulk_ship_orders(self, shipments: List[Dict]) -> Dict:
        """Mark multiple orders as shipped with tracking"""
        return self._make_request('POST', 'orders/bulk/ship', {'shipments': shipments})
    
    # ==================== PRICING & ANALYTICS ====================
    
    def get_market_prices(self, card_name: str, game_type: str = 'mtg', 
                          set_code: Optional[str] = None) -> Dict:
        """Get current market prices across all vendors"""
        params = {'card_name': card_name, 'game_type': game_type}
        if set_code:
            params['set_code'] = set_code
        return self._make_request('GET', 'market/prices', params)
    
    def get_price_history(self, card_name: str, game_type: str = 'mtg', 
                          days: int = 30) -> Dict:
        """Get historical price data"""
        return self._make_request('GET', 'market/history', {
            'card_name': card_name,
            'game_type': game_type,
            'days': days
        })
    
    def get_suggested_prices(self, vendor_id: str, card_name: str, 
                            condition: str, foil: bool = False) -> Dict:
        """Get AI-suggested pricing based on market data"""
        return self._make_request('GET', 'pricing/suggest', {
            'vendor_id': vendor_id,
            'card_name': card_name,
            'condition': condition,
            'foil': foil
        })
    
    def get_sales_analytics(self, vendor_id: str, period: str = '30d') -> Dict:
        """Get sales analytics for time period"""
        return self._make_request('GET', f'vendors/{vendor_id}/analytics', {'period': period})
    
    # ==================== SEARCH & DISCOVERY ====================
    
    def search_products(self, query: str, filters: Optional[Dict] = None) -> Dict:
        """Search marketplace for products"""
        params = {'q': query}
        if filters:
            params.update(filters)
        return self._make_request('GET', 'products/search', params)
    
    def get_trending_cards(self, game_type: str = 'mtg', limit: int = 50) -> Dict:
        """Get trending cards on marketplace"""
        return self._make_request('GET', 'market/trending', {
            'game_type': game_type,
            'limit': limit
        })
    
    def get_new_releases(self, game_type: str = 'mtg', days: int = 7) -> Dict:
        """Get recently listed cards"""
        return self._make_request('GET', 'market/new', {
            'game_type': game_type,
            'days': days
        })
    
    # ==================== REVIEWS & RATINGS ====================
    
    def get_vendor_reviews(self, vendor_id: str, limit: int = 50) -> Dict:
        """Get reviews for vendor"""
        return self._make_request('GET', f'vendors/{vendor_id}/reviews', {'limit': limit})
    
    def respond_to_review(self, review_id: str, response: str) -> Dict:
        """Vendor response to customer review"""
        return self._make_request('POST', f'reviews/{review_id}/respond', {'response': response})
    
    # ==================== MESSAGES & SUPPORT ====================
    
    def get_messages(self, vendor_id: str, unread_only: bool = False) -> Dict:
        """Get customer messages"""
        return self._make_request('GET', f'vendors/{vendor_id}/messages', {
            'unread_only': unread_only
        })
    
    def send_message(self, vendor_id: str, customer_id: str, message: str) -> Dict:
        """Send message to customer"""
        return self._make_request('POST', 'messages', {
            'vendor_id': vendor_id,
            'customer_id': customer_id,
            'message': message
        })
    
    def create_support_ticket(self, vendor_id: str, subject: str, 
                             description: str, priority: str = 'normal') -> Dict:
        """Create support ticket"""
        return self._make_request('POST', 'support/tickets', {
            'vendor_id': vendor_id,
            'subject': subject,
            'description': description,
            'priority': priority
        })
    
    # ==================== PROMOTIONS & MARKETING ====================
    
    def create_promotion(self, vendor_id: str, promotion_data: Dict) -> Dict:
        """Create promotional campaign"""
        return self._make_request('POST', f'vendors/{vendor_id}/promotions', promotion_data)
    
    def get_active_promotions(self, vendor_id: str) -> Dict:
        """Get active promotions"""
        return self._make_request('GET', f'vendors/{vendor_id}/promotions')
    
    def feature_product(self, product_id: str, duration_days: int = 7) -> Dict:
        """Pay to feature product"""
        return self._make_request('POST', f'products/{product_id}/feature', {
            'duration_days': duration_days
        })
    
    # ==================== MULTI-GAME SUPPORT ====================
    
    def get_supported_games(self) -> Dict:
        """Get list of supported game types"""
        return self._make_request('GET', 'games')
    
    def get_game_sets(self, game_type: str) -> Dict:
        """Get all sets for a game type"""
        return self._make_request('GET', f'games/{game_type}/sets')
    
    def get_card_data(self, game_type: str, card_name: str, 
                     set_code: Optional[str] = None) -> Dict:
        """Get comprehensive card data for any game"""
        params = {'card_name': card_name}
        if set_code:
            params['set_code'] = set_code
        return self._make_request('GET', f'games/{game_type}/cards', params)


class InventorySyncManager:
    """Manages bi-directional sync between desktop and marketplace"""
    
    def __init__(self, api: MarketplaceAPI, vendor_id: str):
        self.api = api
        self.vendor_id = vendor_id
        self.sync_interval = 300  # 5 minutes
        self.last_sync = 0
        self.sync_enabled = False
        
    def enable_auto_sync(self, interval: int = 300):
        """Enable automatic syncing"""
        self.sync_enabled = True
        self.sync_interval = interval
        print(f"✅ Auto-sync enabled (every {interval}s)")
    
    def disable_auto_sync(self):
        """Disable automatic syncing"""
        self.sync_enabled = False
        print("❌ Auto-sync disabled")
    
    def should_sync(self) -> bool:
        """Check if it's time to sync"""
        if not self.sync_enabled:
            return False
        return (time.time() - self.last_sync) >= self.sync_interval
    
    def sync_to_marketplace(self, inventory_data: Dict) -> Dict:
        """Push local inventory to marketplace"""
        print("📤 Syncing inventory to marketplace...")
        
        # Convert inventory to marketplace format
        products = []
        for card_name, card_data in inventory_data.items():
            product = {
                'vendor_id': self.vendor_id,
                'game_type': card_data.get('game_type', 'mtg'),
                'card_name': card_name,
                'set_code': card_data.get('set'),
                'set_name': card_data.get('set_name'),
                'condition': card_data.get('condition', 'NM'),
                'language': card_data.get('language', 'EN'),
                'foil': card_data.get('foil', False),
                'signed': card_data.get('signed', False),
                'quantity': card_data.get('quantity', 1),
                'price': card_data.get('value', 0.0),
                'image_url': card_data.get('image_url'),
                'last_updated': datetime.now().isoformat()
            }
            products.append(product)
        
        # Bulk sync
        result = self.api.sync_inventory(self.vendor_id, products)
        
        if 'error' not in result:
            self.last_sync = time.time()
            print(f"✅ Synced {len(products)} products to marketplace")
        else:
            print(f"❌ Sync failed: {result.get('error')}")
        
        return result
    
    def pull_marketplace_orders(self) -> List[Dict]:
        """Pull new orders from marketplace"""
        print("📥 Checking for new marketplace orders...")
        
        result = self.api.get_pending_orders(self.vendor_id)
        
        if 'error' not in result and 'orders' in result:
            orders = result['orders']
            print(f"📦 Found {len(orders)} pending orders")
            return orders
        else:
            print("✅ No new orders")
            return []
    
    def update_marketplace_quantities(self, quantity_changes: List[Dict]) -> Dict:
        """Update quantities after local sales"""
        return self.api.update_inventory_quantities(self.vendor_id, quantity_changes)


# Example usage and testing
if __name__ == "__main__":
    print("🏪 MTTGG Marketplace API Client")
    print("=" * 50)
    
    # Initialize API (will use environment variables or config)
    api = MarketplaceAPI()
    
    # Test connection
    print("\n📡 Testing API connection...")
    games = api.get_supported_games()
    if 'error' not in games:
        print(f"✅ Connected! Supported games: {games}")
    else:
        print(f"⚠️ Connection failed: {games}")
    
    # Example: Register vendor
    print("\n📝 Example: Vendor Registration")
    vendor_data = {
        'store_name': 'Magic Card Emporium',
        'email': 'contact@cardshop.com',
        'subscription_tier': 'professional',
        'business_address': '123 Main St, City, State',
        'tax_id': 'XX-XXXXXXX'
    }
    # result = api.register_vendor(vendor_data)
    # print(f"Registration result: {result}")
    
    # Example: Create product listing
    print("\n📦 Example: Product Listing")
    product = {
        'game_type': 'mtg',
        'card_name': 'Black Lotus',
        'set_code': 'LEA',
        'condition': 'NM',
        'foil': False,
        'quantity': 1,
        'price': 25000.00,
        'graded': True,
        'grade_company': 'PSA',
        'grade_score': 9.5
    }
    # result = api.create_listing(product)
    # print(f"Listing created: {result}")
    
    # Example: Get market prices
    print("\n💰 Example: Market Price Check")
    # prices = api.get_market_prices('Lightning Bolt', 'mtg')
    # print(f"Market prices: {prices}")
    
    # Example: Search products
    print("\n🔍 Example: Product Search")
    # results = api.search_products('bolt', {
    #     'game_type': 'mtg',
    #     'min_price': 0.50,
    #     'max_price': 5.00,
    #     'condition': 'NM'
    # })
    # print(f"Search results: {results}")
    
    print("\n✨ API client ready for integration!")
