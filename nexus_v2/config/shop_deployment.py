#!/usr/bin/env python3
"""
NEXUS V2 Shop Deployment Configuration
=======================================
Patent Pending - Kevin Caracozza 2025-2026

Manages shop-specific configuration for distributed deployment.
Enforces data isolation: customer data stays LOCAL, metadata syncs to cloud.

Data Classification:
  LOCAL ONLY (never leaves shop):
    - Customer information (names, emails, addresses)
    - Sales transactions
    - Payment data
    - Inventory locations (box positions)
    - Employee data

  CLOUD SYNC (metadata only):
    - Card identification requests (image hash, not image)
    - Price lookups (card name only)
    - AI learning patterns (anonymized)
    - License validation
    - Software updates
"""

import os
import json
import uuid
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


class DataClassification(Enum):
    """Data sensitivity classification"""
    LOCAL_ONLY = "local"      # Never leaves shop
    CLOUD_SYNC = "cloud"      # Can sync to central server
    ANONYMIZED = "anonymized" # Sync with PII stripped


@dataclass
class ShopConfig:
    """Configuration for a single shop deployment"""

    # Shop Identity
    shop_id: str                    # Unique shop identifier (UUID)
    shop_name: str                  # Display name
    shop_code: str                  # Short code (e.g., "SHOP1")

    # Network Configuration
    scanner_ip: str = "192.168.1.219"   # Local Pi scanner IP
    scanner_port: int = 5001

    # Central Server (for metadata/pricing only)
    central_api_url: str = "https://api.nexus-tcg.com"
    central_api_key: str = ""           # Shop-specific API key

    # Data Paths (all LOCAL)
    data_dir: str = ""                  # Local data directory
    customer_db: str = ""               # Customer database (LOCAL ONLY)
    inventory_db: str = ""              # Inventory database (LOCAL ONLY)
    sales_db: str = ""                  # Sales database (LOCAL ONLY)

    # Sync Settings
    sync_prices: bool = True            # Fetch prices from central
    sync_metadata: bool = True          # Fetch card metadata from central
    sync_ai_patterns: bool = True       # Send anonymized AI patterns
    sync_customer_data: bool = False    # ALWAYS FALSE - enforced

    # License
    license_key: str = ""
    license_tier: str = "starter"       # free/starter/professional/enterprise

    # Hardware
    has_scanner: bool = True
    has_arm: bool = False
    camera_type: str = "owleye"         # owleye/czur/webcam

    def __post_init__(self):
        """Enforce security: customer sync always disabled"""
        self.sync_customer_data = False  # ENFORCED - never sync customer data

        # Set default paths if not provided
        if not self.data_dir:
            self.data_dir = str(Path.home() / "NEXUS_Data" / self.shop_code)
        if not self.customer_db:
            self.customer_db = str(Path(self.data_dir) / "customers.db")
        if not self.inventory_db:
            self.inventory_db = str(Path(self.data_dir) / "inventory.db")
        if not self.sales_db:
            self.sales_db = str(Path(self.data_dir) / "sales.db")


class ShopDeployment:
    """
    Manages shop deployment configuration and data isolation.

    CRITICAL: This class enforces that customer data NEVER leaves the shop.
    All cloud sync operations are filtered through classification checks.
    """

    # Data fields that are NEVER synced to cloud
    LOCAL_ONLY_FIELDS = {
        'customer_name', 'customer_email', 'customer_phone', 'customer_address',
        'payment_method', 'credit_card', 'bank_account', 'ssn', 'tax_id',
        'employee_name', 'employee_id', 'salary', 'schedule',
        'sale_total', 'sale_items', 'receipt', 'transaction_id',
        'box_location', 'shelf_position', 'storage_notes'
    }

    # Data fields safe to sync (anonymized metadata)
    CLOUD_SYNC_FIELDS = {
        'card_name', 'set_code', 'collector_number', 'condition', 'language',
        'price_timestamp', 'ocr_confidence', 'scan_quality',
        'ai_pattern_hash', 'recognition_accuracy'
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize shop deployment manager"""
        self.config_path = config_path or self._default_config_path()
        self.config: Optional[ShopConfig] = None

        # Load existing config or create new
        if Path(self.config_path).exists():
            self.load_config()

    def _default_config_path(self) -> str:
        """Get default config path"""
        return str(Path.home() / "NEXUS_Data" / "shop_config.json")

    def create_shop(self, shop_name: str, shop_code: str, **kwargs) -> ShopConfig:
        """
        Create a new shop configuration.

        Args:
            shop_name: Human-readable shop name
            shop_code: Short identifier (e.g., "SHOP1")
            **kwargs: Additional config options

        Returns:
            ShopConfig instance
        """
        # Generate unique shop ID
        shop_id = str(uuid.uuid4())

        # Create config
        self.config = ShopConfig(
            shop_id=shop_id,
            shop_name=shop_name,
            shop_code=shop_code,
            **kwargs
        )

        # Create data directories
        data_path = Path(self.config.data_dir)
        data_path.mkdir(parents=True, exist_ok=True)
        (data_path / "backups").mkdir(exist_ok=True)
        (data_path / "scans").mkdir(exist_ok=True)
        (data_path / "exports").mkdir(exist_ok=True)

        # Save config
        self.save_config()

        return self.config

    def save_config(self):
        """Save shop configuration to file"""
        if not self.config:
            raise ValueError("No configuration to save")

        config_path = Path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump(asdict(self.config), f, indent=2)

    def load_config(self) -> ShopConfig:
        """Load shop configuration from file"""
        with open(self.config_path, 'r') as f:
            data = json.load(f)

        self.config = ShopConfig(**data)
        return self.config

    def classify_data(self, data: Dict) -> Dict[DataClassification, Dict]:
        """
        Classify data fields by sensitivity.

        Args:
            data: Dictionary of data to classify

        Returns:
            Dict with LOCAL_ONLY, CLOUD_SYNC, and ANONYMIZED categories
        """
        classified = {
            DataClassification.LOCAL_ONLY: {},
            DataClassification.CLOUD_SYNC: {},
            DataClassification.ANONYMIZED: {}
        }

        for key, value in data.items():
            key_lower = key.lower()

            # Check if field contains sensitive patterns
            is_sensitive = any(
                sensitive in key_lower
                for sensitive in ['customer', 'payment', 'employee', 'sale', 'credit', 'bank', 'ssn', 'address', 'phone', 'email']
            )

            if is_sensitive or key in self.LOCAL_ONLY_FIELDS:
                classified[DataClassification.LOCAL_ONLY][key] = value
            elif key in self.CLOUD_SYNC_FIELDS:
                classified[DataClassification.CLOUD_SYNC][key] = value
            else:
                # Default: anonymize and allow sync
                classified[DataClassification.ANONYMIZED][key] = value

        return classified

    def prepare_for_sync(self, data: Dict) -> Dict:
        """
        Prepare data for cloud sync by removing all sensitive fields.

        CRITICAL: This is the gatekeeper - no PII passes through.

        Args:
            data: Raw data dictionary

        Returns:
            Sanitized data safe for cloud sync
        """
        classified = self.classify_data(data)

        # Only return CLOUD_SYNC data
        safe_data = classified[DataClassification.CLOUD_SYNC].copy()

        # Add shop identifier (not sensitive)
        if self.config:
            safe_data['shop_id'] = self.config.shop_id
            safe_data['shop_code'] = self.config.shop_code

        # Add timestamp
        safe_data['sync_timestamp'] = datetime.now().isoformat()

        return safe_data

    def anonymize_for_ai(self, scan_result: Dict) -> Dict:
        """
        Anonymize scan result for AI learning sync.

        Keeps: card recognition patterns, OCR accuracy, timing
        Removes: customer context, transaction details

        Args:
            scan_result: Raw scan result

        Returns:
            Anonymized data for AI learning
        """
        # Hash any identifying information
        anonymized = {
            'pattern_hash': hashlib.sha256(
                json.dumps(scan_result, sort_keys=True).encode()
            ).hexdigest()[:16],
            'card_name': scan_result.get('card_name'),
            'set_code': scan_result.get('set_code'),
            'confidence': scan_result.get('confidence'),
            'ocr_method': scan_result.get('method'),
            'processing_time': scan_result.get('processing_time'),
            'recognition_success': scan_result.get('success', False),
        }

        # Remove any customer/transaction context
        for sensitive in ['customer', 'sale', 'transaction', 'payment', 'employee']:
            anonymized.pop(sensitive, None)

        return anonymized

    def get_scanner_url(self) -> str:
        """Get full scanner API URL"""
        if not self.config:
            return "http://192.168.1.219:5001"
        return f"http://{self.config.scanner_ip}:{self.config.scanner_port}"

    def get_central_api_url(self) -> str:
        """Get central API URL for metadata/pricing"""
        if not self.config:
            return "https://api.nexus-tcg.com"
        return self.config.central_api_url


# =============================================================================
# DEPLOYMENT HELPERS
# =============================================================================

def generate_shop_installer(shop_config: ShopConfig, output_dir: str) -> str:
    """
    Generate shop-specific installer package.

    Creates:
    - shop_config.json (pre-configured)
    - install.bat (Windows installer script)
    - README.txt (setup instructions)

    Args:
        shop_config: Shop configuration
        output_dir: Output directory for installer

    Returns:
        Path to installer package
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save shop config
    config_file = output_path / "shop_config.json"
    with open(config_file, 'w') as f:
        json.dump(asdict(shop_config), f, indent=2)

    # Create Windows installer script
    installer_script = output_path / "install.bat"
    installer_content = f'''@echo off
echo ================================================
echo NEXUS V2 Shop Installer - {shop_config.shop_name}
echo ================================================
echo.

REM Create data directories
mkdir "%USERPROFILE%\\NEXUS_Data\\{shop_config.shop_code}"
mkdir "%USERPROFILE%\\NEXUS_Data\\{shop_config.shop_code}\\backups"
mkdir "%USERPROFILE%\\NEXUS_Data\\{shop_config.shop_code}\\scans"

REM Copy configuration
copy shop_config.json "%USERPROFILE%\\NEXUS_Data\\shop_config.json"

REM Install Python dependencies
pip install pillow pytesseract opencv-python requests flask

echo.
echo Installation complete!
echo.
echo Shop ID: {shop_config.shop_id}
echo Scanner IP: {shop_config.scanner_ip}:{shop_config.scanner_port}
echo Data Directory: %USERPROFILE%\\NEXUS_Data\\{shop_config.shop_code}
echo.
echo IMPORTANT: Customer data stays LOCAL - never synced to cloud.
echo.
pause
'''
    with open(installer_script, 'w') as f:
        f.write(installer_content)

    # Create README
    readme_file = output_path / "README.txt"
    readme_content = f'''NEXUS V2 Shop Deployment Package
=================================
Shop: {shop_config.shop_name} ({shop_config.shop_code})
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

INSTALLATION:
1. Run install.bat as Administrator
2. Configure scanner IP in shop_config.json if different from {shop_config.scanner_ip}
3. Enter license key in NEXUS application

DATA PRIVACY:
- Customer information stays LOCAL on this device
- Only card metadata (names, prices) syncs with central server
- Sales and inventory data never leaves this shop

SCANNER SETUP:
- Scanner IP: {shop_config.scanner_ip}:{shop_config.scanner_port}
- Ensure Surface tablet and Pi scanner are on same network

SUPPORT:
- License Tier: {shop_config.license_tier}
- Shop ID: {shop_config.shop_id}
'''
    with open(readme_file, 'w') as f:
        f.write(readme_content)

    return str(output_path)


def configure_pi_scanner(shop_config: ShopConfig) -> Dict:
    """
    Generate Pi scanner configuration for shop deployment.

    Returns configuration to be deployed to Pi.
    """
    return {
        'shop_id': shop_config.shop_id,
        'shop_code': shop_config.shop_code,
        'brok_url': f'http://{shop_config.scanner_ip}:5002',  # Local Brok on same Pi
        'server_port': shop_config.scanner_port,
        'camera_type': shop_config.camera_type,
        'features': {
            'multi_pass_scan': True,
            'motion_detect': True,
            'foil_scan': True,
            'arm_control': shop_config.has_arm,
        },
        'data_policy': {
            'send_images_to_cloud': False,  # NEVER
            'send_customer_data': False,    # NEVER
            'send_anonymized_patterns': shop_config.sync_ai_patterns,
        }
    }


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("NEXUS V2 Shop Deployment Tool")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python shop_deployment.py create <shop_name> <shop_code>")
        print("  python shop_deployment.py package <config_path> <output_dir>")
        print("  python shop_deployment.py info <config_path>")
        print("\nExample:")
        print("  python shop_deployment.py create \"Card Kingdom Boston\" SHOP1")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) < 4:
            print("Error: Need shop_name and shop_code")
            sys.exit(1)

        shop_name = sys.argv[2]
        shop_code = sys.argv[3]

        deployment = ShopDeployment()
        config = deployment.create_shop(shop_name, shop_code)

        print(f"\n[OK] Shop created: {shop_name}")
        print(f"     Shop ID: {config.shop_id}")
        print(f"     Shop Code: {config.shop_code}")
        print(f"     Data Dir: {config.data_dir}")
        print(f"     Config saved to: {deployment.config_path}")

    elif command == "package":
        if len(sys.argv) < 4:
            print("Error: Need config_path and output_dir")
            sys.exit(1)

        config_path = sys.argv[2]
        output_dir = sys.argv[3]

        deployment = ShopDeployment(config_path)
        config = deployment.load_config()

        package_path = generate_shop_installer(config, output_dir)
        print(f"\n[OK] Installer package created: {package_path}")

    elif command == "info":
        config_path = sys.argv[2] if len(sys.argv) > 2 else None
        deployment = ShopDeployment(config_path)

        if deployment.config:
            config = deployment.config
            print(f"\nShop Configuration:")
            print(f"  Name: {config.shop_name}")
            print(f"  Code: {config.shop_code}")
            print(f"  ID: {config.shop_id}")
            print(f"  Scanner: {config.scanner_ip}:{config.scanner_port}")
            print(f"  License: {config.license_tier}")
            print(f"\nData Policy:")
            print(f"  Sync Prices: {config.sync_prices}")
            print(f"  Sync Metadata: {config.sync_metadata}")
            print(f"  Sync AI Patterns: {config.sync_ai_patterns}")
            print(f"  Sync Customer Data: {config.sync_customer_data} (ENFORCED)")
        else:
            print("No configuration found")

    print("\n" + "=" * 60)
