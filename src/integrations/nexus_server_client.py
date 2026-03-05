"""
NEXUS SERVER CLIENT
Drop this in with nexus.py - handles all server communication
"""

import requests
import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


class NexusServerClient:
    """
    Client for connecting NEXUS to the server API
    """
    
    def __init__(self, server_url: str = "http://nexus-cards.com:8000"):
        self.server_url = server_url.rstrip('/')
        self.api_key = None
        self.shop_name = None
        self.config_file = Path("nexus_server_config.json")
        self._load_config()
    
    def _load_config(self):
        """Load saved configuration"""
        if self.config_file.exists():
            config = json.loads(self.config_file.read_text())
            self.api_key = config.get('api_key')
            self.shop_name = config.get('shop_name')
            self.server_url = config.get('server_url', self.server_url)
    
    def _save_config(self):
        """Save configuration"""
        config = {
            'api_key': self.api_key,
            'shop_name': self.shop_name,
            'server_url': self.server_url
        }
        self.config_file.write_text(json.dumps(config, indent=2))
    
    def _headers(self) -> dict:
        """Get request headers"""
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request"""
        try:
            r = requests.get(
                f"{self.server_url}{endpoint}",
                headers=self._headers(),
                params=params,
                timeout=10
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def _post(self, endpoint: str, data: dict = None) -> dict:
        """Make POST request"""
        try:
            r = requests.post(
                f"{self.server_url}{endpoint}",
                headers=self._headers(),
                json=data,
                timeout=30
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    # ============================================================
    # CONNECTION & AUTH
    # ============================================================
    def check_health(self) -> dict:
        """Check if server is online"""
        return self._get('/health')
    
    def is_connected(self) -> bool:
        """Check connection status"""
        result = self.check_health()
        return result.get('status') == 'healthy'
    
    def register(self, shop_name: str, owner_name: str, email: str, password: str) -> dict:
        """Register new shop"""
        result = self._post('/shops/register', {
            'shop_name': shop_name,
            'owner_name': owner_name,
            'email': email,
            'password': password
        })
        
        if 'api_key' in result:
            self.api_key = result['api_key']
            self.shop_name = shop_name
            self._save_config()
        
        return result
    
    def login(self, email: str, password: str) -> dict:
        """Login and get API key"""
        result = self._post('/shops/auth', {
            'email': email,
            'password': password
        })
        
        if 'api_key' in result:
            self.api_key = result['api_key']
            self.shop_name = result.get('shop_name')
            self._save_config()
        
        return result
    
    def get_shop_info(self) -> dict:
        """Get current shop info"""
        return self._get('/shops/me')
    
    # ============================================================
    # CARD SEARCH
    # ============================================================
    def search_cards(
        self,
        query: str,
        limit: int = 50,
        set_code: str = None,
        color: str = None,
        rarity: str = None
    ) -> dict:
        """Search for cards"""
        params = {'q': query, 'limit': limit}
        if set_code:
            params['set_code'] = set_code
        if color:
            params['color'] = color
        if rarity:
            params['rarity'] = rarity
        
        return self._get('/cards/search', params)
    
    def get_card(self, card_id: str) -> dict:
        """Get single card by ID"""
        return self._get(f'/cards/{card_id}')
    
    def get_cards_bulk(self, card_ids: List[str]) -> dict:
        """Get multiple cards"""
        return self._post('/cards/bulk', card_ids)
    
    def import_cards(self, cards: List[dict]) -> dict:
        """Import cards to server"""
        return self._post('/cards/import', cards)
    
    # ============================================================
    # PRICE HISTORY
    # ============================================================
    def get_price_history(self, card_id: str, days: int = 30) -> dict:
        """Get price history for card"""
        return self._get(f'/prices/{card_id}', {'days': days})
    
    def record_price(self, card_id: str, price: float, source: str = "nexus") -> dict:
        """Record a price"""
        return self._post(f'/prices/{card_id}', {
            'price': price,
            'source': source
        })
    
    def record_prices_bulk(self, prices: List[dict]) -> dict:
        """Record multiple prices"""
        return self._post('/prices/bulk', prices)
    
    # ============================================================
    # BACKUP & RESTORE
    # ============================================================
    def backup_library(self, library_data: dict) -> dict:
        """Backup library to server"""
        return self._post('/backup', library_data)
    
    def list_backups(self) -> dict:
        """List available backups"""
        return self._get('/backup/list')
    
    def restore_backup(self, filename: str) -> dict:
        """Restore a backup"""
        return self._get(f'/backup/restore/{filename}')
    
    # ============================================================
    # ANALYTICS
    # ============================================================
    def get_analytics_summary(self) -> dict:
        """Get analytics summary"""
        return self._get('/analytics/summary')
    
    def get_top_movers(self, days: int = 7) -> dict:
        """Get top price movers"""
        return self._get('/analytics/top-movers', {'days': days})
    
    # ============================================================
    # DEV CHAT
    # ============================================================
    def get_dev_messages(self) -> list:
        """Get dev chat messages"""
        return self._get('/dev/messages')
    
    def post_dev_message(self, author: str, text: str) -> dict:
        """Post to dev chat"""
        return self._post('/dev/messages', {
            'author': author,
            'text': text
        })


# ============================================================
# INTEGRATION WITH NEXUS
# ============================================================
class NexusServerIntegration:
    """
    Integration layer between NexusLibrarySystem and Server
    """
    
    def __init__(self, library_system, server_url: str = "http://nexus-cards.com:8000"):
        self.library = library_system
        self.client = NexusServerClient(server_url)
    
    def sync_to_server(self) -> dict:
        """Sync local library to server"""
        if not self.client.is_connected():
            return {'error': 'Server not connected'}
        
        # Prepare library data
        library_data = {
            'total_cards': len(self.library.card_locations),
            'total_boxes': len(self.library.box_inventory),
            'library_data': self.library.library_data,
            'card_locations': self.library.card_locations,
            'synced_at': datetime.now().isoformat()
        }
        
        # Backup
        result = self.client.backup_library(library_data)
        
        return result
    
    def restore_from_server(self, filename: str = None) -> dict:
        """Restore library from server backup"""
        if not self.client.is_connected():
            return {'error': 'Server not connected'}
        
        if filename:
            result = self.client.restore_backup(filename)
        else:
            # Get latest backup
            backups = self.client.list_backups()
            if not backups.get('backups'):
                return {'error': 'No backups found'}
            
            latest = backups['backups'][0]['file']
            result = self.client.restore_backup(latest)
        
        if 'library' in result:
            # Restore to local
            library_data = result['library']
            self.library.library_data = library_data.get('library_data', {})
            self.library.card_locations = library_data.get('card_locations', {})
            self.library._save_library()
            
            return {'status': 'restored', 'cards': library_data.get('total_cards', 0)}
        
        return result
    
    def sync_prices(self) -> dict:
        """Sync prices to server"""
        if not self.client.is_connected():
            return {'error': 'Server not connected'}
        
        prices = []
        
        for box_id, cards in self.library.box_inventory.items():
            for card in cards:
                if isinstance(card, dict) and card.get('scryfall_id'):
                    price = card.get('price') or card.get('market_value')
                    if price:
                        prices.append({
                            'card_id': card['scryfall_id'],
                            'price': price,
                            'source': 'nexus_sync'
                        })
        
        if prices:
            return self.client.record_prices_bulk(prices)
        
        return {'status': 'no prices to sync'}


# ============================================================
# EXAMPLE USAGE
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("NEXUS SERVER CLIENT")
    print("=" * 50)
    
    client = NexusServerClient()
    
    # Check connection
    print("\nChecking server connection...")
    health = client.check_health()
    
    if health.get('status') == 'healthy':
        print(f"✅ Server online: {health}")
    else:
        print(f"❌ Server offline: {health}")
    
    print("\nUsage:")
    print("  client = NexusServerClient()")
    print("  client.register('My Shop', 'Kevin', 'kevin@shop.com', 'password')")
    print("  client.search_cards('Black Lotus')")
    print("  client.backup_library(library_data)")
