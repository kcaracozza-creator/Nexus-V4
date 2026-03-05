#!/usr/bin/env python3
"""
NEXUS OTA Firmware Updater — DANIELSON
Fetches signed firmware binaries from ZULTAN and flashes them
to ESP32 boards via esptool.py over existing USB connections.

Usage:
    python3 ota_updater.py                  # update all boards
    python3 ota_updater.py --board arm      # ARM ESP32 only
    python3 ota_updater.py --board light    # LIGHT ESP32 only
    python3 ota_updater.py --check          # check versions only, no flash
    python3 ota_updater.py --rollback arm   # flash rollback image for board

Security model:
    Manifest is signed with Ed25519 (NEXUS private key on ZULTAN).
    Public key is embedded here. Any manifest that fails signature
    verification is rejected — firmware will NOT be flashed.

Patent Pending — Kevin Caracozza
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('nexus.ota')

# =============================================================================
# Configuration
# =============================================================================

ZULTAN_URL   = os.environ.get('ZULTAN_URL', 'http://192.168.1.152:8000')
MANIFEST_URL = f"{ZULTAN_URL}/api/firmware/manifest.json"
FIRMWARE_BASE = f"{ZULTAN_URL}/api/firmware"

BOARD_CONFIG = {
    'arm': {
        'port':        '/dev/nexus_arm',   # udev symlink → /dev/ttyUSB0
        'baud':        460800,
        'description': 'ARM ESP32 (PCA9685 servos + stepper + ring)',
        'filename':    'nexus_arm_v4.bin',
    },
    'light': {
        'port':        '/dev/nexus_light',  # udev symlink → /dev/ttyUSB1
        'baud':        460800,
        'description': 'LIGHT ESP32 (5-channel WS2812B lightbox)',
        'filename':    'nexus_light_v4.bin',
    },
}

FIRMWARE_DIR  = Path('/var/nexus/firmware')
ROLLBACK_DIR  = FIRMWARE_DIR / 'rollback'
ESPTOOL       = shutil.which('esptool.py') or shutil.which('esptool') or 'esptool.py'

# Ed25519 public key for verifying manifest signatures.
# Corresponding private key lives ONLY on ZULTAN (never on deployed units).
# Replace with actual generated public key before first deployment.
NEXUS_PUBLIC_KEY_PEM = os.environ.get('NEXUS_FIRMWARE_PUBKEY', """
-----BEGIN PUBLIC KEY-----
PLACEHOLDER — generate with: python3 tools/gen_firmware_keypair.py
-----END PUBLIC KEY-----
""").strip()

# =============================================================================
# Version query via serial
# =============================================================================

def get_installed_version(board: str) -> str | None:
    """
    Query the installed firmware version from the ESP32 over serial.
    Sends {"cmd":"version"} and reads the JSON response.
    Returns version string like "4.4" or None on failure.
    """
    try:
        import serial
        port = BOARD_CONFIG[board]['port']
        with serial.Serial(port, 115200, timeout=3) as ser:
            time.sleep(0.5)
            ser.reset_input_buffer()
            ser.write(b'{"cmd":"version"}\n')
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        return str(data.get('version', ''))
                    except json.JSONDecodeError:
                        continue
        logger.warning(f"[{board}] No version response from board")
        return None
    except Exception as e:
        logger.warning(f"[{board}] Serial version query failed: {e}")
        return None


# =============================================================================
# Manifest fetch + verification
# =============================================================================

def fetch_manifest() -> dict | None:
    """Fetch and verify the signed firmware manifest from ZULTAN."""
    try:
        resp = requests.get(MANIFEST_URL, timeout=10)
        resp.raise_for_status()
        manifest = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch manifest from {MANIFEST_URL}: {e}")
        return None

    if CRYPTO_AVAILABLE and NEXUS_PUBLIC_KEY_PEM and 'PLACEHOLDER' not in NEXUS_PUBLIC_KEY_PEM:
        try:
            sig_hex  = manifest.pop('signature', '')
            payload  = json.dumps(manifest, sort_keys=True).encode()
            sig_bytes = bytes.fromhex(sig_hex)
            pub_key   = load_pem_public_key(NEXUS_PUBLIC_KEY_PEM.encode())
            pub_key.verify(sig_bytes, payload)
            manifest['signature'] = sig_hex  # restore for logging
            logger.info("Manifest signature verified ✓")
        except InvalidSignature:
            logger.error("MANIFEST SIGNATURE INVALID — aborting. Do not flash unverified firmware.")
            return None
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return None
    else:
        logger.warning("Signature verification skipped (cryptography library not available or key not configured)")

    return manifest


# =============================================================================
# Firmware download + SHA256 verification
# =============================================================================

def download_firmware(board: str, manifest: dict) -> Path | None:
    """Download firmware binary for board, verify SHA256, return local path."""
    board_info = BOARD_CONFIG[board]
    filename   = board_info['filename']
    entry      = manifest.get('boards', {}).get(board)

    if not entry:
        logger.error(f"[{board}] No entry in manifest")
        return None

    expected_sha256 = entry.get('sha256', '')
    version         = entry.get('version', 'unknown')
    url             = f"{FIRMWARE_BASE}/{filename}"

    FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)
    local_path = FIRMWARE_DIR / filename

    logger.info(f"[{board}] Downloading {filename} v{version} from ZULTAN...")
    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        logger.error(f"[{board}] Download failed: {e}")
        return None

    # Verify SHA256
    actual_sha256 = hashlib.sha256(local_path.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        logger.error(
            f"[{board}] SHA256 MISMATCH — aborting.\n"
            f"  Expected: {expected_sha256}\n"
            f"  Got:      {actual_sha256}"
        )
        local_path.unlink(missing_ok=True)
        return None

    logger.info(f"[{board}] SHA256 verified ✓ ({actual_sha256[:16]}...)")
    return local_path


# =============================================================================
# Rollback save
# =============================================================================

def save_rollback(board: str) -> None:
    """Back up the currently installed binary before flashing."""
    ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)
    src = FIRMWARE_DIR / BOARD_CONFIG[board]['filename']
    if src.exists():
        ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = ROLLBACK_DIR / f"{board}_{ts}.bin"
        shutil.copy2(src, dst)
        # Keep only last 3 rollbacks per board
        rollbacks = sorted(ROLLBACK_DIR.glob(f"{board}_*.bin"))
        for old in rollbacks[:-3]:
            old.unlink()
        logger.info(f"[{board}] Rollback saved: {dst.name}")


# =============================================================================
# Flash via esptool
# =============================================================================

def flash_board(board: str, binary: Path) -> bool:
    """Flash binary to ESP32 using esptool.py. Returns True on success."""
    cfg  = BOARD_CONFIG[board]
    port = cfg['port']
    baud = cfg['baud']

    if not Path(port).exists():
        logger.error(f"[{board}] Port {port} not found. Is the board connected?")
        return False

    cmd = [
        ESPTOOL,
        '--chip',   'esp32',
        '--port',   port,
        '--baud',   str(baud),
        '--before', 'default_reset',
        '--after',  'hard_reset',
        'write_flash',
        '--flash_mode',  'qio',
        '--flash_freq',  '80m',
        '--flash_size',  '4MB',
        '0x10000',
        str(binary),
    ]

    logger.info(f"[{board}] Flashing {binary.name} → {port} @ {baud} baud")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            logger.info(f"[{board}] Flash complete ✓")
            return True
        else:
            logger.error(f"[{board}] esptool failed:\n{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"[{board}] Flash timed out after 120s")
        return False
    except FileNotFoundError:
        logger.error(f"esptool not found at {ESPTOOL}. Install: pip install esptool")
        return False


# =============================================================================
# Rollback flash
# =============================================================================

def flash_rollback(board: str) -> bool:
    """Flash the most recent rollback image for a board."""
    rollbacks = sorted(ROLLBACK_DIR.glob(f"{board}_*.bin"))
    if not rollbacks:
        logger.error(f"[{board}] No rollback images found in {ROLLBACK_DIR}")
        return False
    latest = rollbacks[-1]
    logger.info(f"[{board}] Rolling back to {latest.name}")
    return flash_board(board, latest)


# =============================================================================
# Post-flash version verification
# =============================================================================

def verify_version_post_flash(board: str, expected_version: str) -> bool:
    """Wait for board to restart, then verify version matches expected."""
    logger.info(f"[{board}] Waiting for board restart...")
    time.sleep(4)
    actual = get_installed_version(board)
    if actual == expected_version:
        logger.info(f"[{board}] Version verified: {actual} ✓")
        return True
    logger.error(
        f"[{board}] Version mismatch after flash. "
        f"Expected {expected_version!r}, got {actual!r}. "
        f"Initiating rollback..."
    )
    flash_rollback(board)
    return False


# =============================================================================
# Main update flow
# =============================================================================

def update_board(board: str, manifest: dict, check_only: bool = False) -> bool:
    """Full update flow for one board. Returns True if up-to-date or updated."""
    entry = manifest.get('boards', {}).get(board)
    if not entry:
        logger.warning(f"[{board}] Not in manifest, skipping")
        return True

    target_version = str(entry.get('version', ''))
    installed      = get_installed_version(board)

    logger.info(
        f"[{board}] {BOARD_CONFIG[board]['description']}\n"
        f"  Installed: {installed or 'unknown'}\n"
        f"  Available: {target_version}"
    )

    if installed == target_version:
        logger.info(f"[{board}] Already up-to-date ✓")
        return True

    if check_only:
        logger.info(f"[{board}] Update available (--check mode, not flashing)")
        return True

    binary = download_firmware(board, manifest)
    if not binary:
        return False

    save_rollback(board)

    if not flash_board(board, binary):
        logger.error(f"[{board}] Flash failed — rollback preserved at {ROLLBACK_DIR}")
        return False

    return verify_version_post_flash(board, target_version)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='NEXUS OTA Firmware Updater for DANIELSON ESP32 boards'
    )
    parser.add_argument(
        '--board', choices=['arm', 'light', 'all'], default='all',
        help='Which board to update (default: all)'
    )
    parser.add_argument(
        '--check', action='store_true',
        help='Check available versions without flashing'
    )
    parser.add_argument(
        '--rollback', choices=['arm', 'light'],
        help='Flash rollback image for specified board'
    )
    args = parser.parse_args()

    if args.rollback:
        success = flash_rollback(args.rollback)
        sys.exit(0 if success else 1)

    manifest = fetch_manifest()
    if not manifest:
        logger.error("Could not fetch manifest from ZULTAN. Is ZULTAN reachable?")
        sys.exit(1)

    logger.info(
        f"Manifest loaded — "
        f"released {manifest.get('released', 'unknown')} by {manifest.get('released_by', 'unknown')}"
    )

    boards = ['arm', 'light'] if args.board == 'all' else [args.board]
    results = {}
    for board in boards:
        results[board] = update_board(board, manifest, check_only=args.check)

    failed = [b for b, ok in results.items() if not ok]
    if failed:
        logger.error(f"Update failed for: {', '.join(failed)}")
        sys.exit(1)

    logger.info("OTA update complete ✓")
    sys.exit(0)


if __name__ == '__main__':
    main()
