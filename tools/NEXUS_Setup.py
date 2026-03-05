#!/usr/bin/env python3
"""
NEXUS V2 - Universal Installer
==============================
Downloads and installs NEXUS on Windows tablets/PCs.

Run: python NEXUS_Setup.py
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
import json
from pathlib import Path
import ctypes

# Configuration
NEXUS_VERSION = "2.0.0"
GITHUB_RELEASE_URL = "https://github.com/nexus-cards/nexus-v2/releases/latest/download/nexus_v2.zip"
LOCAL_SOURCE = None  # Set to path if installing from local source

# Shop configurations (select during install)
SHOP_CONFIGS = {
    "SHOP1": {
        "name": "Card Kingdom Boston",
        "brock_ip": "192.168.1.219",
        "snarf_ip": "192.168.1.219"
    },
    "SHOP2": {
        "name": "Game Haven NYC",
        "brock_ip": "192.168.1.170",
        "snarf_ip": "192.168.1.173"
    },
    "CUSTOM": {
        "name": "Custom Configuration",
        "brock_ip": "",
        "snarf_ip": ""
    }
}

REQUIRED_PACKAGES = [
    "pillow",
    "pytesseract",
    "opencv-python",
    "requests",
    "flask",
    "flask-cors",
    "fuzzywuzzy",
    "python-Levenshtein"
]


def is_admin():
    """Check if running as administrator"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def print_banner():
    """Print installer banner"""
    print()
    print("=" * 60)
    print("     NEXUS V2 - Universal Collectibles Scanner")
    print(f"     Version {NEXUS_VERSION}")
    print("=" * 60)
    print()
    print("  Patent Pending - Kevin Caracozza 2025-2026")
    print()


def check_python():
    """Check Python version"""
    version = sys.version_info
    print(f"[CHECK] Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("[ERROR] Python 3.10 or higher required!")
        print("        Download from: https://python.org")
        return False

    print("[OK] Python version is compatible")
    return True


def create_directories():
    """Create NEXUS data directories"""
    print("\n[STEP 1] Creating directories...")

    base_dir = Path.home() / "NEXUS_Data"
    dirs = [
        base_dir,
        base_dir / "cache",
        base_dir / "logs",
        base_dir / "exports",
        base_dir / "scans"
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {d}")

    return base_dir


def select_shop():
    """Let user select shop configuration"""
    print("\n[STEP 2] Select Shop Configuration")
    print("-" * 40)

    for i, (code, config) in enumerate(SHOP_CONFIGS.items(), 1):
        print(f"  {i}. {code}: {config['name']}")

    print()
    while True:
        try:
            choice = input("Enter choice (1-3): ").strip()
            idx = int(choice) - 1
            shop_code = list(SHOP_CONFIGS.keys())[idx]
            break
        except (ValueError, IndexError):
            print("  Invalid choice, try again.")

    config = SHOP_CONFIGS[shop_code].copy()

    # Custom configuration
    if shop_code == "CUSTOM":
        print("\n  Enter custom network settings:")
        config["name"] = input("  Shop Name: ").strip() or "My Shop"
        config["brock_ip"] = input("  Scanner IP (e.g., 192.168.1.219): ").strip()
        config["snarf_ip"] = input("  Scanner IP (e.g., 192.168.1.219): ").strip()

    print(f"\n[OK] Selected: {config['name']}")
    print(f"     Brock: {config['brock_ip']}")
    print(f"     Snarf: {config['snarf_ip']}")

    return shop_code, config


def save_config(base_dir, shop_code, config):
    """Save shop configuration"""
    print("\n[STEP 3] Saving configuration...")

    nexus_config = {
        "shop_code": shop_code,
        "shop_name": config["name"],
        "brock_url": f"http://{config['brock_ip']}:5000",
        "snarf_url": f"http://{config['snarf_ip']}:5001",
        "central_url": "https://nexus-cards.com",
        "data_policy": {
            "customer_data": "local_only",
            "sales_data": "local_only",
            "inventory": "local_only"
        }
    }

    config_path = base_dir / "nexus_config.json"
    with open(config_path, 'w') as f:
        json.dump(nexus_config, f, indent=2)

    print(f"  Saved: {config_path}")
    return config_path


def install_packages():
    """Install required Python packages"""
    print("\n[STEP 4] Installing Python packages...")
    print("  This may take a few minutes...")
    print()

    # Upgrade pip first
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                   capture_output=True)

    for pkg in REQUIRED_PACKAGES:
        print(f"  Installing {pkg}...", end=" ", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("OK")
        else:
            print("FAILED")
            print(f"    Error: {result.stderr[:100]}")

    print("\n[OK] Package installation complete")


def download_nexus(install_dir):
    """Download NEXUS from GitHub or copy from local"""
    print("\n[STEP 5] Installing NEXUS application...")

    # Check if we're running from the source directory
    script_dir = Path(__file__).parent.parent
    nexus_src = script_dir / "nexus_v2"

    if nexus_src.exists():
        print(f"  Found local source: {nexus_src}")
        print("  Copying to installation directory...")

        dest = install_dir / "nexus_v2"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(nexus_src, dest)

        # Also copy pi_servers for reference
        pi_src = script_dir / "pi_servers"
        if pi_src.exists():
            shutil.copytree(pi_src, install_dir / "pi_servers")

        print(f"  Installed to: {dest}")
        return dest
    else:
        print("  [ERROR] Source not found. Please run from NEXUS directory.")
        return None


def create_shortcut(nexus_dir):
    """Create desktop shortcut"""
    print("\n[STEP 6] Creating desktop shortcut...")

    desktop = Path.home() / "Desktop"
    shortcut_path = desktop / "NEXUS V2.lnk"

    main_py = nexus_dir / "main.py"

    # Use PowerShell to create shortcut
    ps_cmd = f'''
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut("{shortcut_path}")
    $s.TargetPath = "python"
    $s.Arguments = '"{main_py}"'
    $s.WorkingDirectory = "{nexus_dir.parent}"
    $s.Description = "NEXUS V2 - Card Scanner"
    $s.Save()
    '''

    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)

    if shortcut_path.exists():
        print(f"  Created: {shortcut_path}")
    else:
        print("  [WARN] Could not create shortcut")
        print(f"  Manual launch: python {main_py}")


def test_connection(config):
    """Test connection to Brock and Snarf"""
    print("\n[STEP 7] Testing network connections...")

    import socket

    # Test Brock
    brock_ip = config["brock_ip"]
    print(f"  Testing Brock ({brock_ip}:5000)...", end=" ", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((brock_ip, 5000))
        sock.close()
        if result == 0:
            print("ONLINE")
        else:
            print("OFFLINE")
    except:
        print("OFFLINE")

    # Test Snarf
    snarf_ip = config["snarf_ip"]
    print(f"  Testing Snarf ({snarf_ip}:5001)...", end=" ", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((snarf_ip, 5001))
        sock.close()
        if result == 0:
            print("ONLINE")
        else:
            print("OFFLINE")
    except:
        print("OFFLINE")


def print_complete(config):
    """Print completion message"""
    print()
    print("=" * 60)
    print("     INSTALLATION COMPLETE!")
    print("=" * 60)
    print()
    print(f"  Shop:    {config['name']}")
    print(f"  Brock:   {config['brock_ip']}:5000 (OCR/Database)")
    print(f"  Snarf:   {config['snarf_ip']}:5001 (Scanner/Hardware)")
    print()
    print("  DATA POLICY:")
    print("    Customer data: LOCAL ONLY (never leaves shop)")
    print("    Sales data:    LOCAL ONLY (stored on Brock)")
    print("    Card prices:   Fetched from central server")
    print()
    print("  Launch NEXUS from desktop shortcut or run:")
    print("    python nexus_v2\\main.py")
    print()
    print("=" * 60)


def main():
    """Main installer function"""
    print_banner()

    # Check admin (optional warning)
    if not is_admin():
        print("[WARN] Not running as Administrator")
        print("       Some features may not work correctly.")
        print()

    # Check Python
    if not check_python():
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Create directories
    base_dir = create_directories()

    # Select shop
    shop_code, config = select_shop()

    # Save config
    save_config(base_dir, shop_code, config)

    # Install packages
    install_packages()

    # Install NEXUS
    install_dir = Path("C:/NEXUS")
    install_dir.mkdir(parents=True, exist_ok=True)
    nexus_dir = download_nexus(install_dir)

    if nexus_dir:
        # Create shortcut
        create_shortcut(nexus_dir)

        # Test connections
        test_connection(config)

        # Complete
        print_complete(config)
    else:
        print("\n[ERROR] Installation failed!")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
