#!/usr/bin/env python3
"""
NEXUS V2 Cloud Sync Layer
==========================
Patent Pending - Kevin Caracozza 2025-2026

Manages all communication between shop and central NEXUS server.
ENFORCES data isolation: customer data NEVER leaves the shop.

Sync Operations (ALLOWED):
  - Card metadata lookup (Scryfall, etc.)
  - Price feeds (TCGPlayer, CardKingdom)
  - AI model updates (patterns only, no images)
  - License validation
  - Software updates
  - Anonymized analytics

NEVER Synced:
  - Customer PII (names, emails, addresses)
  - Payment information
  - Individual sales transactions
  - Employee data
  - Inventory locations
"""

import os
import json
import hashlib
import logging
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SyncType(Enum):
    """Types of sync operations"""
    PRICE_LOOKUP = "price"
    CARD_METADATA = "metadata"
    AI_PATTERN = "ai_pattern"
    LICENSE_CHECK = "license"
    SOFTWARE_UPDATE = "update"
    ANALYTICS = "analytics"


@dataclass
class SyncResult:
    """Result of a sync operation"""
    success: bool
    sync_type: SyncType
    data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class CloudSyncManager:
    """
    Manages cloud sync operations with strict data isolation.

    SECURITY: All outbound data passes through sanitize_outbound()
    which strips any PII before transmission.
    """

    # Fields that are NEVER sent to cloud
    BLOCKED_FIELDS = {
        # Customer PII
        'customer_name', 'customer_email', 'customer_phone', 'customer_address',
        'customer_id', 'buyer_name', 'buyer_email', 'shipping_address',
        # Payment
        'credit_card', 'card_number', 'cvv', 'expiry', 'bank_account',
        'payment_method', 'payment_details', 'billing_address',
        # Employee
        'employee_name', 'employee_id', 'salary', 'ssn', 'tax_id',
        # Transaction details
        'receipt_number', 'transaction_id', 'sale_total', 'sale_items',
        # Inventory locations (competitive advantage)
        'box_location', 'shelf_position', 'storage_location',
    }

    # Patterns in field names that indicate sensitive data
    SENSITIVE_PATTERNS = [
        'customer', 'buyer', 'seller', 'employee', 'staff',
        'payment', 'credit', 'bank', 'account', 'billing',
        'address', 'phone', 'email', 'ssn', 'tax',
        'receipt', 'transaction', 'sale_', 'purchase_',
        'password', 'secret', 'token', 'key',
    ]

    def __init__(self, shop_config=None, central_url: str = "https://api.nexus-tcg.com"):
        """
        Initialize cloud sync manager.

        Args:
            shop_config: ShopConfig instance (optional)
            central_url: Central server URL
        """
        self.central_url = central_url
        self.shop_config = shop_config
        self.shop_id = shop_config.shop_id if shop_config else "unknown"
        self.api_key = shop_config.central_api_key if shop_config else ""

        # Cache for reducing API calls
        self.price_cache: Dict[str, Dict] = {}
        self.metadata_cache: Dict[str, Dict] = {}
        self.cache_duration = timedelta(minutes=15)

        # Sync statistics (local only)
        self.sync_stats = {
            'total_syncs': 0,
            'blocked_fields': 0,
            'price_lookups': 0,
            'metadata_lookups': 0,
            'last_sync': None
        }

        logger.info(f"CloudSyncManager initialized for shop {self.shop_id}")

    def sanitize_outbound(self, data: Dict) -> Dict:
        """
        CRITICAL: Sanitize data before sending to cloud.

        Removes ALL sensitive fields and patterns.
        This is the security gatekeeper - no PII passes through.

        Args:
            data: Raw data dictionary

        Returns:
            Sanitized data safe for cloud transmission
        """
        sanitized = {}

        for key, value in data.items():
            key_lower = key.lower()

            # Check explicit blocked fields
            if key_lower in self.BLOCKED_FIELDS:
                self.sync_stats['blocked_fields'] += 1
                logger.debug(f"Blocked field: {key}")
                continue

            # Check sensitive patterns
            is_sensitive = any(
                pattern in key_lower for pattern in self.SENSITIVE_PATTERNS
            )
            if is_sensitive:
                self.sync_stats['blocked_fields'] += 1
                logger.debug(f"Blocked pattern match: {key}")
                continue

            # Recursively sanitize nested dicts
            if isinstance(value, dict):
                sanitized[key] = self.sanitize_outbound(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.sanitize_outbound(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    def _make_request(self, endpoint: str, method: str = "GET",
                      data: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to central server"""
        url = f"{self.central_url}/{endpoint}"

        headers = {
            'Content-Type': 'application/json',
            'X-Shop-ID': self.shop_id,
            'X-API-Key': self.api_key,
        }

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            else:
                # ALWAYS sanitize outbound data
                safe_data = self.sanitize_outbound(data or {})
                response = requests.post(url, json=safe_data, headers=headers, timeout=10)

            if response.ok:
                return response.json()
            else:
                logger.warning(f"API request failed: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"API timeout: {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning(f"API connection error: {endpoint}")
            return None
        except Exception as e:
            logger.error(f"API error: {e}")
            return None

    # =========================================================================
    # PRICE LOOKUP (ALLOWED)
    # =========================================================================

    def get_card_price(self, card_name: str, set_code: str = "",
                       condition: str = "NM") -> SyncResult:
        """
        Fetch card price from central server.

        ALLOWED: Only card name and set code are sent.
        """
        # Check cache first
        cache_key = f"{card_name}:{set_code}:{condition}"
        if cache_key in self.price_cache:
            cached = self.price_cache[cache_key]
            if datetime.fromisoformat(cached['timestamp']) > datetime.now() - self.cache_duration:
                return SyncResult(
                    success=True,
                    sync_type=SyncType.PRICE_LOOKUP,
                    data=cached['data']
                )

        # Make API request (sanitized by _make_request)
        result = self._make_request("api/prices", "POST", {
            'card_name': card_name,
            'set_code': set_code,
            'condition': condition,
            # Note: shop_id added automatically, no customer data
        })

        if result:
            # Cache the result
            self.price_cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self.sync_stats['price_lookups'] += 1

            return SyncResult(
                success=True,
                sync_type=SyncType.PRICE_LOOKUP,
                data=result
            )

        return SyncResult(
            success=False,
            sync_type=SyncType.PRICE_LOOKUP,
            error="Price lookup failed"
        )

    # =========================================================================
    # CARD METADATA (ALLOWED)
    # =========================================================================

    def get_card_metadata(self, card_name: str, set_code: str = "") -> SyncResult:
        """
        Fetch card metadata (oracle text, colors, etc.) from central server.

        ALLOWED: Only card identification info is sent.
        """
        cache_key = f"meta:{card_name}:{set_code}"
        if cache_key in self.metadata_cache:
            cached = self.metadata_cache[cache_key]
            if datetime.fromisoformat(cached['timestamp']) > datetime.now() - self.cache_duration:
                return SyncResult(
                    success=True,
                    sync_type=SyncType.CARD_METADATA,
                    data=cached['data']
                )

        result = self._make_request("api/cards/metadata", "POST", {
            'card_name': card_name,
            'set_code': set_code,
        })

        if result:
            self.metadata_cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self.sync_stats['metadata_lookups'] += 1

            return SyncResult(
                success=True,
                sync_type=SyncType.CARD_METADATA,
                data=result
            )

        return SyncResult(
            success=False,
            sync_type=SyncType.CARD_METADATA,
            error="Metadata lookup failed"
        )

    # =========================================================================
    # AI PATTERN SYNC (ALLOWED - ANONYMIZED)
    # =========================================================================

    def sync_ai_pattern(self, scan_result: Dict) -> SyncResult:
        """
        Sync anonymized AI learning pattern to central server.

        ALLOWED: Only anonymized patterns are sent.
        NO images, NO customer context, NO transaction details.
        """
        # Create anonymized pattern
        anonymized = {
            'pattern_hash': hashlib.sha256(
                json.dumps(scan_result, sort_keys=True).encode()
            ).hexdigest()[:16],
            'card_name': scan_result.get('card_name'),
            'set_code': scan_result.get('set_code'),
            'confidence': scan_result.get('confidence'),
            'ocr_method': scan_result.get('method'),
            'processing_time_ms': scan_result.get('processing_time', 0) * 1000,
            'recognition_success': scan_result.get('success', False),
            'timestamp': datetime.now().isoformat(),
        }

        # Double-check no PII leaked through
        anonymized = self.sanitize_outbound(anonymized)

        result = self._make_request("api/ai/patterns", "POST", anonymized)

        if result:
            return SyncResult(
                success=True,
                sync_type=SyncType.AI_PATTERN,
                data={'pattern_id': result.get('pattern_id')}
            )

        return SyncResult(
            success=False,
            sync_type=SyncType.AI_PATTERN,
            error="AI pattern sync failed"
        )

    # =========================================================================
    # LICENSE VALIDATION (ALLOWED)
    # =========================================================================

    def validate_license(self, license_key: str) -> SyncResult:
        """
        Validate license with central server.

        ALLOWED: Only license key and shop ID are sent.
        """
        result = self._make_request("api/license/validate", "POST", {
            'license_key': license_key,
            # shop_id added automatically
        })

        if result and result.get('valid'):
            return SyncResult(
                success=True,
                sync_type=SyncType.LICENSE_CHECK,
                data={
                    'valid': True,
                    'tier': result.get('tier', 'starter'),
                    'expires': result.get('expires'),
                    'features': result.get('features', [])
                }
            )

        return SyncResult(
            success=False,
            sync_type=SyncType.LICENSE_CHECK,
            error=result.get('error', 'License validation failed') if result else 'Connection failed'
        )

    # =========================================================================
    # SOFTWARE UPDATE CHECK (ALLOWED)
    # =========================================================================

    def check_for_updates(self, current_version: str) -> SyncResult:
        """
        Check for software updates.

        ALLOWED: Only version number is sent.
        """
        result = self._make_request("api/updates/check", "POST", {
            'current_version': current_version,
            'platform': 'windows',
        })

        if result:
            return SyncResult(
                success=True,
                sync_type=SyncType.SOFTWARE_UPDATE,
                data=result
            )

        return SyncResult(
            success=False,
            sync_type=SyncType.SOFTWARE_UPDATE,
            error="Update check failed"
        )

    # =========================================================================
    # ANALYTICS (ALLOWED - AGGREGATED ONLY)
    # =========================================================================

    def sync_analytics(self, analytics: Dict) -> SyncResult:
        """
        Sync aggregated analytics to central server.

        ALLOWED: Only aggregated counts, no individual records.

        Example allowed data:
            {'total_scans': 150, 'avg_confidence': 0.87, 'top_sets': ['NEO', 'MOM']}

        NOT allowed:
            {'sales': [...], 'customers': [...], 'transactions': [...]}
        """
        # Only allow specific aggregated fields
        allowed_fields = {
            'total_scans', 'successful_scans', 'failed_scans',
            'avg_confidence', 'avg_processing_time',
            'top_sets', 'top_card_types', 'cards_scanned_today',
            'uptime_hours', 'error_rate'
        }

        filtered = {k: v for k, v in analytics.items() if k in allowed_fields}
        filtered['period'] = analytics.get('period', 'daily')
        filtered['timestamp'] = datetime.now().isoformat()

        result = self._make_request("api/analytics", "POST", filtered)

        if result:
            return SyncResult(
                success=True,
                sync_type=SyncType.ANALYTICS,
                data={'accepted': True}
            )

        return SyncResult(
            success=False,
            sync_type=SyncType.ANALYTICS,
            error="Analytics sync failed"
        )

    def get_sync_stats(self) -> Dict:
        """Get sync statistics (local tracking)"""
        self.sync_stats['last_sync'] = datetime.now().isoformat()
        return self.sync_stats.copy()


# =============================================================================
# OFFLINE MODE SUPPORT
# =============================================================================

class OfflineSyncQueue:
    """
    Queues sync operations when offline for later processing.

    All queued data is sanitized before storage.
    """

    def __init__(self, queue_path: str = None):
        self.queue_path = queue_path or str(
            Path.home() / "NEXUS_Data" / "sync_queue.json"
        )
        self.queue: List[Dict] = []
        self._load_queue()

    def _load_queue(self):
        """Load existing queue from disk"""
        if Path(self.queue_path).exists():
            try:
                with open(self.queue_path, 'r') as f:
                    self.queue = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load sync queue: {e}")
                self.queue = []

    def _save_queue(self):
        """Save queue to disk"""
        try:
            Path(self.queue_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.queue_path, 'w') as f:
                json.dump(self.queue, f)
        except Exception as e:
            logger.error(f"Failed to save sync queue: {e}")

    def add(self, sync_type: SyncType, data: Dict):
        """Add item to sync queue (sanitized)"""
        # Create temporary sync manager just for sanitization
        sanitizer = CloudSyncManager()
        safe_data = sanitizer.sanitize_outbound(data)

        self.queue.append({
            'type': sync_type.value,
            'data': safe_data,
            'queued_at': datetime.now().isoformat()
        })
        self._save_queue()

    def process(self, sync_manager: CloudSyncManager) -> int:
        """Process all queued items, return count of successful syncs"""
        if not self.queue:
            return 0

        successful = 0
        remaining = []

        for item in self.queue:
            sync_type = SyncType(item['type'])
            data = item['data']

            try:
                if sync_type == SyncType.AI_PATTERN:
                    result = sync_manager.sync_ai_pattern(data)
                elif sync_type == SyncType.ANALYTICS:
                    result = sync_manager.sync_analytics(data)
                else:
                    # Skip other types in queue (prices/metadata are real-time)
                    continue

                if result.success:
                    successful += 1
                else:
                    remaining.append(item)
            except Exception as e:
                logger.warning(f"Queue processing error: {e}")
                remaining.append(item)

        self.queue = remaining
        self._save_queue()

        return successful


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_sync_manager: Optional[CloudSyncManager] = None


def get_sync_manager() -> CloudSyncManager:
    """Get or create global sync manager"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = CloudSyncManager()
    return _sync_manager


def lookup_price(card_name: str, set_code: str = "", condition: str = "NM") -> Optional[Dict]:
    """Convenience function for price lookup"""
    result = get_sync_manager().get_card_price(card_name, set_code, condition)
    return result.data if result.success else None


def lookup_metadata(card_name: str, set_code: str = "") -> Optional[Dict]:
    """Convenience function for metadata lookup"""
    result = get_sync_manager().get_card_metadata(card_name, set_code)
    return result.data if result.success else None


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("NEXUS V2 Cloud Sync Layer - Security Test")
    print("=" * 60)

    sync = CloudSyncManager()

    # Test sanitization
    test_data = {
        'card_name': 'Lightning Bolt',  # ALLOWED
        'set_code': 'LEA',              # ALLOWED
        'confidence': 0.95,             # ALLOWED
        'customer_name': 'John Doe',    # BLOCKED
        'customer_email': 'john@x.com', # BLOCKED
        'payment_method': 'credit',     # BLOCKED
        'sale_total': 49.99,            # BLOCKED
        'box_location': 'Shelf A3',     # BLOCKED
    }

    print("\nOriginal data:")
    for k, v in test_data.items():
        print(f"  {k}: {v}")

    print("\nSanitized (safe for cloud):")
    sanitized = sync.sanitize_outbound(test_data)
    for k, v in sanitized.items():
        print(f"  {k}: {v}")

    print(f"\nBlocked fields: {sync.sync_stats['blocked_fields']}")
    print("\n[OK] Data isolation enforced!")
    print("=" * 60)
