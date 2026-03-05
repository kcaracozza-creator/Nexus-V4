"""
NEXUS V2 Client
Handles both LOCAL (Brock Pi) and CLOUD (nexus-cards.com) connections
For Surface tablets at shop deployments
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import requests


class NexusClient:
    """
    Unified client for NEXUS V2 Surface tablets
    - LOCAL: Brock Pi for OCR, scanning, customer data
    - CLOUD: nexus-cards.com for card metadata, prices
    """

    def __init__(self, config_path: str = None):
        # Load config
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Default locations
            self.config_path = Path(os.getenv(
                'NEXUS_CONFIG',
                os.path.expanduser('~/NEXUS_Data/nexus_config.json')
            ))

        self.config = self._load_config()

        # Connection endpoints
        self.brock_url = self.config.get('brock_url', 'http://192.168.1.219:5001')
        self.cloud_url = self.config.get('cloud_url', 'https://nexus-cards.com')

        # Auth
        self.api_key = self.config.get('api_key')
        self.shop_code = self.config.get('shop_code')

    def _load_config(self) -> dict:
        """Load configuration from file"""
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        return {}

    def _save_config(self):
        """Save configuration"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.config, indent=2))

    def _headers(self, include_auth: bool = True) -> dict:
        """Get request headers"""
        headers = {'Content-Type': 'application/json'}
        if include_auth and self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        if self.shop_code:
            headers['X-Shop-Code'] = self.shop_code
        return headers

    # ============================================================
    # LOCAL OPERATIONS (Brock Pi)
    # Customer data NEVER leaves here
    # ============================================================

    def _local_get(self, endpoint: str, params: dict = None, timeout: int = 10) -> dict:
        """GET request to local Brock Pi"""
        try:
            r = requests.get(
                f"{self.brock_url}{endpoint}",
                headers=self._headers(include_auth=False),
                params=params,
                timeout=timeout
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e), 'source': 'local'}

    def _local_post(self, endpoint: str, data: dict = None, timeout: int = 30) -> dict:
        """POST request to local Brock Pi"""
        try:
            r = requests.post(
                f"{self.brock_url}{endpoint}",
                headers=self._headers(include_auth=False),
                json=data,
                timeout=timeout
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e), 'source': 'local'}

    def check_brock(self) -> dict:
        """Check if Brock Pi is online"""
        return self._local_get('/status')

    def is_brock_connected(self) -> bool:
        """Quick connection check"""
        result = self.check_brock()
        return 'error' not in result

    def scan_card(self, image_path: str = None, image_data: bytes = None) -> dict:
        """Send image to Brock for OCR"""
        try:
            files = {}
            if image_path:
                files['image'] = open(image_path, 'rb')
            elif image_data:
                files['image'] = ('card.jpg', image_data, 'image/jpeg')
            else:
                return {'error': 'No image provided'}

            r = requests.post(
                f"{self.brock_url}/api/scan",
                files=files,
                timeout=60
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}

    def get_local_inventory(self) -> dict:
        """Get inventory from local database"""
        return self._local_get('/api/inventory')

    def add_to_inventory(self, card_data: dict) -> dict:
        """Add card to local inventory"""
        return self._local_post('/api/inventory/add', card_data)

    def get_shop_info(self) -> dict:
        """Get shop configuration from Brock"""
        return self._local_get('/api/shop/info')

    # Customer operations - LOCAL ONLY
    def save_customer(self, customer_data: dict) -> dict:
        """Save customer to LOCAL database only"""
        return self._local_post('/api/customers/save', customer_data)

    def get_customers(self) -> dict:
        """Get customers from LOCAL database"""
        return self._local_get('/api/customers')

    def record_sale(self, sale_data: dict) -> dict:
        """Record sale to LOCAL database only"""
        return self._local_post('/api/sales/record', sale_data)

    def get_sales(self, days: int = 30) -> dict:
        """Get sales from LOCAL database"""
        return self._local_get('/api/sales', {'days': days})

    # ============================================================
    # CLOUD OPERATIONS (nexus-cards.com)
    # Card metadata, prices, analytics - NO customer data
    # ============================================================

    def _cloud_get(self, endpoint: str, params: dict = None, timeout: int = 15) -> dict:
        """GET request to cloud server"""
        try:
            r = requests.get(
                f"{self.cloud_url}{endpoint}",
                headers=self._headers(),
                params=params,
                timeout=timeout
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e), 'source': 'cloud'}

    def _cloud_post(self, endpoint: str, data: dict = None, timeout: int = 30) -> dict:
        """POST request to cloud server"""
        try:
            r = requests.post(
                f"{self.cloud_url}{endpoint}",
                headers=self._headers(),
                json=data,
                timeout=timeout
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e), 'source': 'cloud'}

    def check_cloud(self) -> dict:
        """Check if cloud server is online"""
        try:
            r = requests.get(f"{self.cloud_url}/health", timeout=10)
            return r.json()
        except Exception as e:
            return {'error': str(e), 'status': 'offline'}

    def is_cloud_connected(self) -> bool:
        """Quick cloud connection check"""
        result = self.check_cloud()
        return result.get('status') == 'online'

    # Auth
    def register_shop(self, shop_name: str, owner_name: str,
                      email: str, password: str) -> dict:
        """Register new shop with cloud"""
        result = self._cloud_post('/shops/register', {
            'shop_name': shop_name,
            'owner_name': owner_name,
            'email': email,
            'password': password
        })

        if 'api_key' in result:
            self.api_key = result['api_key']
            self.config['api_key'] = self.api_key
            self._save_config()

        return result

    def login(self, email: str, password: str) -> dict:
        """Login to cloud server"""
        result = self._cloud_post('/shops/auth', {
            'email': email,
            'password': password
        })

        if 'api_key' in result:
            self.api_key = result['api_key']
            self.shop_code = result.get('shop_code')
            self.config['api_key'] = self.api_key
            self.config['shop_code'] = self.shop_code
            self._save_config()

        return result

    # Card search (cloud database)
    def search_cards(self, query: str, limit: int = 50,
                     set_code: str = None, color: str = None,
                     rarity: str = None) -> dict:
        """Search cards in cloud database"""
        params = {'q': query, 'limit': limit}
        if set_code:
            params['set_code'] = set_code
        if color:
            params['color'] = color
        if rarity:
            params['rarity'] = rarity

        return self._cloud_get('/cards/search', params)

    def get_card(self, card_id: str) -> dict:
        """Get card details from cloud"""
        return self._cloud_get(f'/cards/{card_id}')

    # Price data (cloud)
    def get_price_history(self, card_id: str, days: int = 30) -> dict:
        """Get price history from cloud"""
        return self._cloud_get(f'/prices/{card_id}', {'days': days})

    def get_top_movers(self, days: int = 7) -> dict:
        """Get top price movers"""
        return self._cloud_get('/analytics/top-movers', {'days': days})

    # ============================================================
    # SYNC OPERATIONS
    # Metadata only - NEVER customer data
    # ============================================================

    def sync_inventory_metadata(self) -> dict:
        """
        Sync inventory metadata to cloud (card counts, not customer info)
        This helps with analytics but keeps customer data local
        """
        # Get local inventory
        local_inv = self.get_local_inventory()
        if 'error' in local_inv:
            return local_inv

        # Prepare sanitized metadata (no customer info)
        metadata = {
            'shop_code': self.shop_code,
            'total_cards': local_inv.get('total_cards', 0),
            'total_value': local_inv.get('total_value', 0),
            'card_types': local_inv.get('card_types', {}),
            'last_sync': datetime.now().isoformat()
        }

        return self._cloud_post('/shops/sync-metadata', metadata)

    def backup_to_cloud(self, include_inventory: bool = True) -> dict:
        """
        Backup to cloud - inventory only, NEVER customer data
        """
        backup_data = {
            'shop_code': self.shop_code,
            'timestamp': datetime.now().isoformat()
        }

        if include_inventory:
            inv = self.get_local_inventory()
            if 'error' not in inv:
                # Strip any customer references
                backup_data['inventory'] = self._sanitize_for_cloud(inv)

        return self._cloud_post('/backup', backup_data)

    def _sanitize_for_cloud(self, data: dict) -> dict:
        """Remove any customer-related fields before cloud sync"""
        BLOCKED = {
            'customer_name', 'customer_email', 'customer_phone',
            'customer_address', 'customer_id', 'buyer_name',
            'seller_name', 'payment_method', 'credit_card'
        }

        def clean(obj):
            if isinstance(obj, dict):
                return {k: clean(v) for k, v in obj.items()
                        if k.lower() not in BLOCKED}
            elif isinstance(obj, list):
                return [clean(item) for item in obj]
            return obj

        return clean(data)

    # ============================================================
    # MARKETPLACE INTEGRATION
    # List scanned cards for sale on nexus-cards.com
    # ============================================================

    def get_marketplace_client(self):
        """Get MarketplaceClient for listing cards"""
        try:
            from nexus_v2.integrations.marketplace_client import MarketplaceClient
            return MarketplaceClient(self.cloud_url)
        except ImportError:
            return None

    def list_on_marketplace(self, cards: List[dict]) -> dict:
        """
        List cards on the marketplace

        Args:
            cards: List of card dicts with name, price, condition, etc.
        """
        marketplace = self.get_marketplace_client()
        if not marketplace:
            return {'error': 'Marketplace client not available'}

        if not marketplace.user:
            return {'error': 'Not logged in to marketplace'}

        return marketplace.bulk_create_listings(cards)


# ============================================================
# QUICK STATUS CHECK
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("NEXUS V2 CLIENT - Connection Test")
    print("=" * 50)

    client = NexusClient()

    # Check local Brock
    print(f"\nBrock Pi ({client.brock_url}):")
    brock = client.check_brock()
    if 'error' not in brock:
        print(f"  [OK] Connected - {brock}")
    else:
        print(f"  [OFFLINE] {brock.get('error')}")

    # Check cloud
    print(f"\nCloud ({client.cloud_url}):")
    cloud = client.check_cloud()
    if cloud.get('status') == 'healthy':
        print(f"  [OK] Connected - {cloud}")
    else:
        print(f"  [OFFLINE] {cloud.get('error', cloud)}")

    print("\n" + "=" * 50)
    print("Usage:")
    print("  client = NexusClient()")
    print("  client.scan_card('card.jpg')  # Local OCR")
    print("  client.search_cards('Black Lotus')  # Cloud search")
    print("  client.save_customer({...})  # LOCAL ONLY")
    print("=" * 50)
