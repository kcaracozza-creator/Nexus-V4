#!/usr/bin/env python3
"""
NEXUS V2 Shop Hardware Bundle Configuration
=============================================
Patent Pending - Kevin Caracozza 2025-2026

Each shop deployment includes a complete hardware stack:
  - Pi "Brock" - Main processor, OCR, AI, display
  - Pi "Snarf" - Hardware controller, cameras, LEDs, arm
  - Surface Tablet - Windows client UI

All processing happens LOCALLY at the shop.
Central server is ONLY for metadata/pricing lookups.

Shop Network Topology:
┌─────────────────────────────────────────────────────────────┐
│                    SHOP LOCAL NETWORK                        │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   BROCK     │◀──▶│   SNARF     │    │  SURFACE    │     │
│  │ 192.168.1.x │    │ 192.168.1.y │    │  TABLET     │     │
│  │             │    │             │    │             │     │
│  │ - OCR/AI    │    │ - Cameras   │    │ - UI        │     │
│  │ - Database  │    │ - LEDs      │    │ - Reports   │     │
│  │ - Display   │    │ - Arm       │    │ - Inventory │     │
│  │ - Coral TPU │    │ - ESP32     │    │             │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        ▲                                      │             │
│        │              LOCAL ONLY              │             │
│        └──────────────────────────────────────┘             │
│                                                             │
│                    │ HTTPS (metadata only)                  │
└────────────────────┼────────────────────────────────────────┘
                     ▼
           ┌─────────────────┐
           │  NEXUS CENTRAL  │
           │  (Prices/Meta)  │
           └─────────────────┘
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List
from datetime import datetime


@dataclass
class PiConfig:
    """Configuration for a single Raspberry Pi"""
    hostname: str
    role: str  # 'brock' or 'snarf'
    ip_address: str
    port: int
    services: List[str] = field(default_factory=list)
    hardware: Dict = field(default_factory=dict)


@dataclass
class ShopHardwareBundle:
    """
    Complete hardware configuration for a shop deployment.

    Each shop gets:
    - Brock Pi (main processor)
    - Snarf Pi (hardware controller)
    - Surface tablet (client UI)
    """

    # Shop Identity
    shop_id: str
    shop_name: str
    shop_code: str

    # Network base (x.x.x.BASE)
    network_base: str = "192.168.1"

    # Brock Configuration (Main Processor)
    brock: PiConfig = field(default_factory=lambda: PiConfig(
        hostname="brock",
        role="processor",
        ip_address="192.168.1.219",
        port=5000,
        services=[
            "ocr_server",      # Coral TPU OCR
            "ai_engine",       # Learning engine
            "database",        # SQLite databases
            "display_server",  # Scan feedback display
            "api_gateway"      # Main API for Surface
        ],
        hardware={
            'coral_tpu': True,
            'owleye_back': True,  # Card back detection camera
            'storage_hdd': '160GB'
        }
    ))

    # Snarf Configuration (Hardware Controller)
    snarf: PiConfig = field(default_factory=lambda: PiConfig(
        hostname="snarf",
        role="hardware",
        ip_address="192.168.1.219",
        port=5001,
        services=[
            "camera_server",   # All camera capture
            "led_controller",  # ESP32 + Arduino LEDs
            "arm_controller",  # Robotic arm
            "motion_detect",   # Auto-scan trigger
        ],
        hardware={
            'owleye_main': True,    # 64MP grading camera
            'czur_scanner': True,   # Bulk scanning
            'webcam': True,         # Motion detection
            'esp32': '/dev/ttyUSB0',
            'arduino': '/dev/ttyACM0',
            'led_rings': 3,
            'arm_servos': 8
        }
    ))

    # Surface Tablet Configuration
    surface: Dict = field(default_factory=lambda: {
        'os': 'Windows 11',
        'app': 'NEXUS V2 Client',
        'connects_to': 'brock',
        'features': [
            'inventory_management',
            'customer_lookup',
            'sales_processing',
            'reports',
            'deck_builder'
        ]
    })

    # Central Server (metadata only)
    central_api: str = "https://api.nexus-tcg.com"
    api_key: str = ""

    # Data directories (on Brock's HDD)
    data_mount: str = "/mnt/nexus_data"

    def __post_init__(self):
        """Update IPs based on network base"""
        if self.network_base != "192.168.1":
            # Update Brock IP
            brock_suffix = self.brock.ip_address.split('.')[-1]
            self.brock.ip_address = f"{self.network_base}.{brock_suffix}"

            # Update Snarf IP
            snarf_suffix = self.snarf.ip_address.split('.')[-1]
            self.snarf.ip_address = f"{self.network_base}.{snarf_suffix}"


class ShopBundleManager:
    """
    Manages shop hardware bundle deployment.

    Creates configuration files for:
    - Brock Pi (brok_server.py config)
    - Snarf Pi (snarf_server.py config)
    - Surface tablet (nexus_v2 config)
    """

    def __init__(self, bundle: ShopHardwareBundle):
        self.bundle = bundle

    def generate_brock_config(self) -> Dict:
        """Generate configuration for Brock Pi"""
        return {
            'hostname': self.bundle.brock.hostname,
            'shop_id': self.bundle.shop_id,
            'shop_code': self.bundle.shop_code,

            # Network
            'bind_address': '0.0.0.0',
            'port': self.bundle.brock.port,
            'snarf_url': f"http://{self.bundle.snarf.ip_address}:{self.bundle.snarf.port}",

            # Coral TPU
            'coral_enabled': True,
            'coral_model': f"{self.bundle.data_mount}/models/ocr_edgetpu.tflite",

            # Databases (LOCAL - never synced)
            'database_dir': f"{self.bundle.data_mount}/databases",
            'customer_db': f"{self.bundle.data_mount}/databases/customers.db",
            'inventory_db': f"{self.bundle.data_mount}/databases/inventory.db",
            'sales_db': f"{self.bundle.data_mount}/databases/sales.db",
            'ai_brain_db': f"{self.bundle.data_mount}/databases/nexus_ai_brain.db",

            # External API (metadata only)
            'central_api_url': self.bundle.central_api,
            'central_api_key': self.bundle.api_key,

            # Data policy
            'sync_customer_data': False,  # ENFORCED
            'sync_sales_data': False,     # ENFORCED
            'sync_metadata': True,        # Prices, card info
            'sync_ai_patterns': True,     # Anonymized only
        }

    def generate_snarf_config(self) -> Dict:
        """Generate configuration for Snarf Pi"""
        return {
            'hostname': self.bundle.snarf.hostname,
            'shop_id': self.bundle.shop_id,
            'shop_code': self.bundle.shop_code,

            # Network
            'bind_address': '0.0.0.0',
            'port': self.bundle.snarf.port,
            'brok_url': f"http://{self.bundle.brock.ip_address}:{self.bundle.brock.port}",

            # Serial ports
            'esp32_port': self.bundle.snarf.hardware.get('esp32', '/dev/ttyUSB0'),
            'arduino_port': self.bundle.snarf.hardware.get('arduino', '/dev/ttyACM0'),

            # Cameras
            'cameras': {
                'owleye': {'type': 'csi', 'index': 0, 'resolution': [4624, 3472]},
                'czur': {'type': 'usb', 'device': '/dev/video10', 'resolution': [1920, 1080]},
                'webcam': {'type': 'usb', 'device': '/dev/video8', 'resolution': [1920, 1080]},
            },

            # Scan directory (temporary, cleaned up)
            'scan_dir': '/home/nexus1/scans',

            # Features
            'multi_pass_scan': True,
            'motion_detect': True,
            'foil_detection': True,
            'arm_enabled': self.bundle.snarf.hardware.get('arm_servos', 0) > 0,
        }

    def generate_surface_config(self) -> Dict:
        """Generate configuration for Surface tablet"""
        return {
            'shop_id': self.bundle.shop_id,
            'shop_name': self.bundle.shop_name,
            'shop_code': self.bundle.shop_code,

            # Connect to local Brock (NOT central server)
            'api_url': f"http://{self.bundle.brock.ip_address}:{self.bundle.brock.port}",
            'scanner_url': f"http://{self.bundle.snarf.ip_address}:{self.bundle.snarf.port}",

            # Central server (metadata only)
            'central_api_url': self.bundle.central_api,
            'central_api_key': self.bundle.api_key,

            # Local data (on Surface)
            'local_cache_dir': '%USERPROFILE%\\NEXUS_Data\\cache',

            # Data policy (enforced)
            'data_policy': {
                'customer_data_location': 'local_brock',  # Stays on Brock
                'sales_data_location': 'local_brock',     # Stays on Brock
                'inventory_location': 'local_brock',      # Stays on Brock
                'metadata_source': 'central_via_brock',   # Brock fetches from central
                'pricing_source': 'central_via_brock',    # Brock fetches from central
            },

            # Features
            'features': self.bundle.surface.get('features', []),
        }

    def generate_all_configs(self, output_dir: str) -> Dict[str, str]:
        """Generate all configuration files for shop deployment"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        files_created = {}

        # Brock config
        brock_file = output_path / "brock_config.json"
        with open(brock_file, 'w') as f:
            json.dump(self.generate_brock_config(), f, indent=2)
        files_created['brock'] = str(brock_file)

        # Snarf config
        snarf_file = output_path / "snarf_config.json"
        with open(snarf_file, 'w') as f:
            json.dump(self.generate_snarf_config(), f, indent=2)
        files_created['snarf'] = str(snarf_file)

        # Surface config
        surface_file = output_path / "nexus_config.json"
        with open(surface_file, 'w') as f:
            json.dump(self.generate_surface_config(), f, indent=2)
        files_created['surface'] = str(surface_file)

        # Master bundle info
        bundle_file = output_path / "shop_bundle.json"
        with open(bundle_file, 'w') as f:
            json.dump({
                'shop_id': self.bundle.shop_id,
                'shop_name': self.bundle.shop_name,
                'shop_code': self.bundle.shop_code,
                'created': datetime.now().isoformat(),
                'brock_ip': self.bundle.brock.ip_address,
                'snarf_ip': self.bundle.snarf.ip_address,
            }, f, indent=2)
        files_created['bundle'] = str(bundle_file)

        return files_created

    def generate_deployment_script(self, output_dir: str) -> str:
        """Generate deployment scripts for Pi setup"""
        output_path = Path(output_dir)

        # Brock deployment script
        brock_script = output_path / "deploy_brock.sh"
        brock_content = f'''#!/bin/bash
# NEXUS V2 Brock Deployment Script
# Shop: {self.bundle.shop_name} ({self.bundle.shop_code})

echo "========================================"
echo "NEXUS Brock Deployment - {self.bundle.shop_code}"
echo "========================================"

# Set hostname
sudo hostnamectl set-hostname {self.bundle.shop_code.lower()}-brock

# Create directories
sudo mkdir -p {self.bundle.data_mount}/databases
sudo mkdir -p {self.bundle.data_mount}/models
sudo mkdir -p {self.bundle.data_mount}/backups

# Set permissions
sudo chown -R nexus1:nexus1 {self.bundle.data_mount}

# Copy configuration
cp brock_config.json /home/nexus1/brok_server_config.json

# Install service
sudo cp brok.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable brok.service
sudo systemctl start brok.service

echo ""
echo "Brock deployed! IP: {self.bundle.brock.ip_address}:{self.bundle.brock.port}"
echo "Data stored at: {self.bundle.data_mount}"
'''
        with open(brock_script, 'w', newline='\n') as f:
            f.write(brock_content)

        # Snarf deployment script
        snarf_script = output_path / "deploy_snarf.sh"
        snarf_content = f'''#!/bin/bash
# NEXUS V2 Snarf Deployment Script
# Shop: {self.bundle.shop_name} ({self.bundle.shop_code})

echo "========================================"
echo "NEXUS Snarf Deployment - {self.bundle.shop_code}"
echo "========================================"

# Set hostname
sudo hostnamectl set-hostname {self.bundle.shop_code.lower()}-snarf

# Create scan directory
mkdir -p /home/nexus1/scans

# Copy configuration
cp snarf_config.json /home/nexus1/snarf_server_config.json

# Install service
sudo cp snarf.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable snarf.service
sudo systemctl start snarf.service

echo ""
echo "Snarf deployed! IP: {self.bundle.snarf.ip_address}:{self.bundle.snarf.port}"
echo "Brock connection: http://{self.bundle.brock.ip_address}:{self.bundle.brock.port}"
'''
        with open(snarf_script, 'w', newline='\n') as f:
            f.write(snarf_content)

        return str(output_path)


def create_shop_bundle(shop_name: str, shop_code: str,
                       network_base: str = "192.168.1",
                       brock_suffix: str = "169",
                       snarf_suffix: str = "172") -> ShopHardwareBundle:
    """
    Create a new shop hardware bundle configuration.

    Args:
        shop_name: Human-readable shop name
        shop_code: Short identifier (e.g., "SHOP1")
        network_base: Network prefix (e.g., "192.168.1")
        brock_suffix: Last octet for Brock IP
        snarf_suffix: Last octet for Snarf IP

    Returns:
        Configured ShopHardwareBundle
    """
    import uuid

    bundle = ShopHardwareBundle(
        shop_id=str(uuid.uuid4()),
        shop_name=shop_name,
        shop_code=shop_code,
        network_base=network_base,
    )

    # Update IPs
    bundle.brock.ip_address = f"{network_base}.{brock_suffix}"
    bundle.snarf.ip_address = f"{network_base}.{snarf_suffix}"

    return bundle


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("NEXUS V2 Shop Hardware Bundle Generator")
    print("=" * 60)

    if len(sys.argv) < 3:
        print("\nUsage:")
        print("  python shop_hardware_bundle.py <shop_name> <shop_code> [output_dir]")
        print("\nExample:")
        print('  python shop_hardware_bundle.py "Card Kingdom Boston" SHOP1 ./shop1_deploy')
        print("\nThis generates:")
        print("  - brock_config.json  (for Brock Pi)")
        print("  - snarf_config.json  (for Snarf Pi)")
        print("  - nexus_config.json  (for Surface tablet)")
        print("  - deploy_brock.sh    (Pi deployment script)")
        print("  - deploy_snarf.sh    (Pi deployment script)")
        sys.exit(1)

    shop_name = sys.argv[1]
    shop_code = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else f"./{shop_code.lower()}_deploy"

    # Create bundle
    bundle = create_shop_bundle(shop_name, shop_code)
    manager = ShopBundleManager(bundle)

    # Generate configs
    files = manager.generate_all_configs(output_dir)
    manager.generate_deployment_script(output_dir)

    print(f"\nShop Bundle Created: {shop_name} ({shop_code})")
    print(f"Shop ID: {bundle.shop_id}")
    print(f"\nNetwork Configuration:")
    print(f"  Brock: {bundle.brock.ip_address}:{bundle.brock.port}")
    print(f"  Snarf: {bundle.snarf.ip_address}:{bundle.snarf.port}")
    print(f"\nFiles generated in: {output_dir}")
    for name, path in files.items():
        print(f"  - {name}: {Path(path).name}")
    print(f"  - deploy_brock.sh")
    print(f"  - deploy_snarf.sh")
    print(f"\nData Flow:")
    print(f"  Surface → Brock → Snarf (cameras)")
    print(f"  Brock → Central API (metadata/prices only)")
    print(f"  Customer/Sales data: LOCAL ONLY (never leaves shop)")
    print("\n" + "=" * 60)
