#!/usr/bin/env python3
"""
NEXUS Phone Home Module
=======================
Universal module for NEXUS clients to report ALL activity to HQ

Drop this into any NEXUS installation and call:
    from phone_home import report_sale, report_scan

Every sale, every scan - HQ sees it all.
"""

import requests
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

# Configuration
HQ_URL = os.getenv('NEXUS_HQ_URL', 'http://localhost:5050')
API_KEY = os.getenv('NEXUS_API_KEY', '')  # Set this per-client

# Config file path (for clients that store their key locally)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'nexus_client_config.json')


def load_config():
    """Load client config from file"""
    global API_KEY, HQ_URL
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                API_KEY = config.get('api_key', API_KEY)
                HQ_URL = config.get('hq_url', HQ_URL)
    except Exception as e:
        print(f"⚠️ Could not load phone_home config: {e}")


def save_config(api_key: str, hq_url: str = None):
    """Save client config"""
    global API_KEY, HQ_URL
    API_KEY = api_key
    if hq_url:
        HQ_URL = hq_url
    
    config = {'api_key': API_KEY, 'hq_url': HQ_URL}
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Could not save phone_home config: {e}")
        return False


def _post_to_hq(endpoint: str, data: dict) -> dict:
    """Internal: POST to HQ"""
    if not API_KEY:
        return {'success': False, 'error': 'No API key configured', 'offline': True}
    
    try:
        response = requests.post(
            f'{HQ_URL}{endpoint}',
            headers={
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json'
            },
            json=data,
            timeout=5  # Quick timeout so sales aren't blocked
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        # Don't fail sales just because HQ is unreachable
        # Queue for later? For now just log
        print(f"⚠️ HQ unreachable: {e}")
        return {'success': False, 'error': str(e), 'offline': True}


# ============================================
# SALE REPORTING
# ============================================

def report_sale(
    sale_type: str,           # 'deck', 'card', 'bulk', 'order'
    item_name: str,           # Deck name or card name
    total_value: float,       # Sale price
    item_count: int = 1,      # Number of items (cards in deck, or qty)
    format: str = '',         # MTG format if applicable
    cards: List[dict] = None, # Optional card list
    customer_info: str = '',  # Optional customer note
    **kwargs                  # Any extra data
) -> dict:
    """
    Report ANY sale to NEXUS HQ
    
    Examples:
        # Deck sale
        report_sale('deck', 'Gruul Aggro', 45.67, item_count=100, format='Commander')
        
        # Single card sale
        report_sale('card', 'Black Lotus', 50000.00)
        
        # Bulk sale
        report_sale('bulk', 'Bulk Commons Box', 25.00, item_count=1000)
        
        # Order (multiple items)
        report_sale('order', 'Order #1234', 156.78, item_count=15)
    """
    data = {
        'sale_type': sale_type,
        'deck_name': item_name,  # HQ expects deck_name for now
        'format': format or sale_type,
        'card_count': item_count,
        'sale_value': total_value,
        'cards': cards or [],
        'customer_info': customer_info,
        'local_timestamp': datetime.now().isoformat(),
        **kwargs
    }
    
    result = _post_to_hq('/api/phone-home/sale', data)
    
    # Log locally regardless
    _log_sale(sale_type, item_name, total_value, result)
    
    return result


def report_deck_sale(deck_name: str, format: str, card_count: int, 
                     sale_value: float, cards: List[dict] = None) -> dict:
    """Convenience: Report a deck sale"""
    return report_sale(
        sale_type='deck',
        item_name=deck_name,
        total_value=sale_value,
        item_count=card_count,
        format=format,
        cards=cards
    )


def report_card_sale(card_name: str, price: float, quantity: int = 1,
                     set_code: str = '', condition: str = 'NM') -> dict:
    """Convenience: Report a single card sale"""
    return report_sale(
        sale_type='card',
        item_name=card_name,
        total_value=price * quantity,
        item_count=quantity,
        cards=[{
            'name': card_name,
            'qty': quantity,
            'price': price,
            'set': set_code,
            'condition': condition
        }]
    )


def report_bulk_sale(description: str, total_value: float, card_count: int) -> dict:
    """Convenience: Report a bulk sale"""
    return report_sale(
        sale_type='bulk',
        item_name=description,
        total_value=total_value,
        item_count=card_count
    )


def report_order_sale(order_id: str, total_value: float, item_count: int,
                      items: List[dict] = None) -> dict:
    """Convenience: Report a multi-item order"""
    return report_sale(
        sale_type='order',
        item_name=f'Order {order_id}',
        total_value=total_value,
        item_count=item_count,
        cards=items
    )


# ============================================
# SCAN REPORTING
# ============================================

def report_scan(card_name: str, set_code: str = '', rarity: str = '',
                price: float = 0, confidence: float = 0) -> dict:
    """Report a card scan to HQ"""
    return _post_to_hq('/api/phone-home/scan', {
        'card_name': card_name,
        'set_code': set_code,
        'rarity': rarity,
        'price': price,
        'confidence': confidence
    })


def report_batch_scans(scans: List[dict]) -> dict:
    """Report multiple scans at once (more efficient)"""
    return _post_to_hq('/api/phone-home/batch-scans', {'scans': scans})


# ============================================
# LOCAL LOGGING (BACKUP)
# ============================================

SALES_LOG_PATH = os.path.join(os.path.dirname(__file__), 'local_sales_log.json')

def _log_sale(sale_type: str, item_name: str, value: float, hq_result: dict):
    """Log sale locally (backup if HQ offline)"""
    try:
        # Load existing
        sales = []
        if os.path.exists(SALES_LOG_PATH):
            with open(SALES_LOG_PATH, 'r') as f:
                sales = json.load(f)
        
        # Append
        sales.append({
            'timestamp': datetime.now().isoformat(),
            'type': sale_type,
            'item': item_name,
            'value': value,
            'hq_synced': hq_result.get('success', False),
            'hq_sale_id': hq_result.get('sale_id'),
            'nexus_fee': hq_result.get('nexus_fee', 0)
        })
        
        # Keep last 1000
        sales = sales[-1000:]
        
        with open(SALES_LOG_PATH, 'w') as f:
            json.dump(sales, f, indent=2)
            
    except Exception as e:
        print(f"⚠️ Could not log sale locally: {e}")


def get_unsynced_sales() -> List[dict]:
    """Get sales that failed to sync to HQ"""
    try:
        if os.path.exists(SALES_LOG_PATH):
            with open(SALES_LOG_PATH, 'r') as f:
                sales = json.load(f)
                return [s for s in sales if not s.get('hq_synced')]
    except:
        pass
    return []


def retry_unsynced_sales() -> int:
    """Retry syncing failed sales"""
    unsynced = get_unsynced_sales()
    synced_count = 0
    
    for sale in unsynced:
        result = report_sale(
            sale_type=sale.get('type', 'unknown'),
            item_name=sale.get('item', 'Unknown'),
            total_value=sale.get('value', 0)
        )
        if result.get('success'):
            synced_count += 1
    
    return synced_count


# ============================================
# STATUS CHECK
# ============================================

def check_hq_status() -> dict:
    """Check if HQ is reachable"""
    try:
        response = requests.get(f'{HQ_URL}/api/status', timeout=3)
        return response.json()
    except:
        return {'status': 'offline', 'error': 'HQ unreachable'}


def is_hq_online() -> bool:
    """Quick check if HQ is online"""
    status = check_hq_status()
    return status.get('status') == 'online'


# Load config on import
load_config()


# ============================================
# TEST
# ============================================

if __name__ == '__main__':
    print("=" * 50)
    print("  NEXUS Phone Home Module Test")
    print("=" * 50)
    
    print(f"\nHQ URL: {HQ_URL}")
    print(f"API Key: {API_KEY[:20] + '...' if API_KEY else 'NOT SET'}")
    print(f"HQ Online: {is_hq_online()}")
    
    # Test sale
    print("\nTesting sale report...")
    result = report_sale(
        sale_type='test',
        item_name='Test Sale',
        total_value=9.99,
        item_count=1
    )
    print(f"Result: {json.dumps(result, indent=2)}")
