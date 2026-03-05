"""
NEXUS Update Client - LAN Auto-Update
Checks Zultan (192.168.1.152:8000) for new versions on startup.
Downloads and extracts if newer. That's it.
"""

import os
import sys
import json
import shutil
import zipfile
import logging
import requests
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("NEXUS_UPDATE")

VERSION = "2.1.4"
BUILD_DATE = "2026-02-11"
UPDATE_SERVER = "http://192.168.1.152:8000"


def get_local_version():
    """Return current local version"""
    return VERSION


def check_and_update(app_dir: str = None):
    """Check for updates and apply if newer. Call before app starts."""
    if app_dir is None:
        app_dir = str(Path(__file__).parent.parent)

    try:
        r = requests.get(f"{UPDATE_SERVER}/update/check", timeout=3)
        if r.status_code != 200:
            return False

        data = r.json()
        server_version = data.get('version', '0.0.0')
        available = data.get('available', False)

        if not available:
            logger.info(f"No update available (local: {VERSION})")
            return False

        # Compare versions
        local_parts = [int(x) for x in VERSION.split('.')]
        server_parts = [int(x) for x in server_version.split('.')]

        if server_parts <= local_parts:
            logger.info(f"Already up to date (v{VERSION})")
            return False

        logger.info(f"Update available: v{VERSION} -> v{server_version}")

        # Download
        r = requests.get(f"{UPDATE_SERVER}/update/download", timeout=60, stream=True)
        if r.status_code != 200:
            logger.error("Download failed")
            return False

        zip_path = os.path.join(app_dir, '_update.zip')
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded update ({os.path.getsize(zip_path)} bytes)")

        # Extract over current app dir
        # Zip contains nexus_v2/ prefix - strip it so files land in app_dir
        with zipfile.ZipFile(zip_path, 'r') as z:
            for member in z.namelist():
                # Strip "nexus_v2/" prefix
                if member.startswith('nexus_v2/'):
                    rel_path = member[len('nexus_v2/'):]
                else:
                    rel_path = member
                if not rel_path:
                    continue
                target = os.path.join(app_dir, rel_path)
                if member.endswith('/'):
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(member) as src, open(target, 'wb') as dst:
                        dst.write(src.read())

        os.remove(zip_path)
        logger.info(f"Updated to v{server_version} - restart app to use new version")
        return True

    except requests.exceptions.ConnectionError:
        logger.info("Update server not reachable (offline mode)")
        return False
    except Exception as e:
        logger.error(f"Update check failed: {e}")
        return False
