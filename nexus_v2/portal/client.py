#!/usr/bin/env python3
"""
NEXUS Portal Client
===================
Handles authentication, licensing, and updates for NEXUS clients.

Patent Pending - Kevin Caracozza
"""

import os
import json
import uuid
import hashlib
import platform
import requests
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

# Configuration
# Zultan GPU server hosts the portal
DEFAULT_PORTAL_URL = "http://192.168.1.152:8000"
CONFIG_FILE = "nexus_license.json"
VERSION = "2.1.4"

class NexusPortalClient:
    """Client for NEXUS Portal communication"""

    def __init__(self, portal_url: str = None, config_dir: str = None):
        self.portal_url = portal_url or os.environ.get("NEXUS_PORTAL_URL", DEFAULT_PORTAL_URL)
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".nexus"
        self.config_file = self.config_dir / CONFIG_FILE
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.license_key: Optional[str] = None
        self.user_info: Dict[str, Any] = {}
        self.client_id: Optional[int] = None

        self._load_config()

    def _load_config(self):
        """Load saved configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.license_key = data.get('license_key')
                    self.user_info = data.get('user_info', {})
                    self.client_id = data.get('client_id')
            except Exception:
                pass

    def _save_config(self):
        """Save configuration"""
        data = {
            'license_key': self.license_key,
            'user_info': self.user_info,
            'client_id': self.client_id
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _get_machine_id(self) -> str:
        """Generate unique machine identifier"""
        components = [
            platform.node(),
            platform.machine(),
            platform.processor(),
        ]
        return hashlib.md5(''.join(components).encode()).hexdigest()[:16]

    def _get_machine_name(self) -> str:
        """Get friendly machine name"""
        return f"{platform.node()} ({platform.system()} {platform.release()})"

    def _api_request(self, method: str, endpoint: str, data: dict = None,
                     require_license: bool = False) -> Dict[str, Any]:
        """Make API request to portal"""
        url = f"{self.portal_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}

        if require_license and self.license_key:
            headers['X-License-Key'] = self.license_key

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=data, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=10)

            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'data': response.json() if response.content else {}
            }
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Cannot connect to portal server'}
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Portal server timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # AUTH METHODS
    # =========================================================================

    def register(self, email: str, password: str, shop_name: str = "") -> Dict[str, Any]:
        """Register new user account"""
        result = self._api_request('POST', '/api/auth/register', {
            'email': email,
            'password': password,
            'shop_name': shop_name
        })

        if result['success'] and result['data'].get('license_key'):
            self.license_key = result['data']['license_key']
            self.user_info = {
                'email': email,
                'shop_name': shop_name,
                'user_id': result['data'].get('user_id'),
                'station_api_key': result['data'].get('station_api_key')
            }
            self._save_config()

        return result

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login to existing account"""
        result = self._api_request('POST', '/api/auth/login', {
            'email': email,
            'password': password
        })

        if result['success'] and result['data'].get('license_key'):
            self.license_key = result['data']['license_key']
            self.user_info = result['data']
            self._save_config()

        return result

    def validate_license(self) -> Dict[str, Any]:
        """Validate license and register this client"""
        if not self.license_key:
            return {'success': False, 'error': 'No license key'}

        result = self._api_request('POST', '/api/auth/validate', {
            'machine_id': self._get_machine_id(),
            'machine_name': self._get_machine_name(),
            'version': VERSION
        }, require_license=True)

        if result['success'] and result['data'].get('client_id'):
            self.client_id = result['data']['client_id']
            self._save_config()

        return result

    def is_licensed(self) -> bool:
        """Check if client has valid license"""
        return self.license_key is not None

    def logout(self):
        """Clear saved credentials"""
        self.license_key = None
        self.user_info = {}
        self.client_id = None
        if self.config_file.exists():
            self.config_file.unlink()

    def get_station_api_key(self) -> Optional[str]:
        """Get station API key for marketplace integration"""
        # Try from cached user_info first
        if self.user_info.get('station_api_key'):
            return self.user_info['station_api_key']

        # Fetch from server if not cached
        if not self.license_key:
            return None

        result = self._api_request('GET', '/api/auth/station_key', require_license=True)
        if result['success']:
            self.user_info['station_api_key'] = result['data'].get('station_api_key')
            self._save_config()
            return self.user_info['station_api_key']

        return None

    # =========================================================================
    # WALLET METHODS
    # =========================================================================

    def get_wallet(self) -> Dict[str, Any]:
        """Get seller wallet info"""
        return self._api_request('GET', '/api/wallet', require_license=True)

    def update_payout_settings(self, payout_email: str, payout_method: str = 'paypal') -> Dict[str, Any]:
        """Update payout settings"""
        return self._api_request('POST', '/api/wallet/payout', {
            'payout_email': payout_email,
            'payout_method': payout_method
        }, require_license=True)

    def request_withdrawal(self, amount: float) -> Dict[str, Any]:
        """Request withdrawal from wallet"""
        return self._api_request('POST', '/api/wallet/withdraw', {
            'amount': amount
        }, require_license=True)

    # =========================================================================
    # UPDATE METHODS
    # =========================================================================

    def check_for_updates(self) -> Dict[str, Any]:
        """Check if updates are available"""
        result = self._api_request('GET', '/api/updates/check', {
            'version': VERSION
        }, require_license=True)

        return result

    def download_update(self, version: str, target_dir: str) -> Dict[str, Any]:
        """Download and extract update"""
        url = f"{self.portal_url}/api/updates/download/{version}"
        headers = {}
        if self.license_key:
            headers['X-License-Key'] = self.license_key

        try:
            response = requests.get(url, headers=headers, stream=True, timeout=300)

            if response.status_code != 200:
                return {'success': False, 'error': 'Download failed'}

            # Save to temp file
            temp_zip = Path(target_dir) / f"nexus_update_{version}.zip"
            with open(temp_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract
            extract_dir = Path(target_dir) / f"nexus_{version}"
            with zipfile.ZipFile(temp_zip, 'r') as z:
                z.extractall(extract_dir)

            # Cleanup temp file
            temp_zip.unlink()

            return {
                'success': True,
                'extract_path': str(extract_dir),
                'version': version
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_changelog(self) -> Dict[str, Any]:
        """Get version changelog"""
        return self._api_request('GET', '/api/updates/changelog')

    # =========================================================================
    # INFO METHODS
    # =========================================================================

    def get_portal_status(self) -> Dict[str, Any]:
        """Check portal server health"""
        return self._api_request('GET', '/api/health')

    def get_current_version(self) -> str:
        """Get current client version"""
        return VERSION

    def get_user_info(self) -> Dict[str, Any]:
        """Get stored user info"""
        return self.user_info.copy()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_client: Optional[NexusPortalClient] = None

def get_client() -> NexusPortalClient:
    """Get singleton portal client"""
    global _client
    if _client is None:
        _client = NexusPortalClient()
    return _client

def is_licensed() -> bool:
    """Quick check if licensed"""
    return get_client().is_licensed()

def check_updates() -> Dict[str, Any]:
    """Quick update check"""
    return get_client().check_for_updates()


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == '__main__':
    import sys

    client = NexusPortalClient()
    print(f"NEXUS Portal Client v{VERSION}")
    print(f"Portal URL: {client.portal_url}")
    print(f"Machine ID: {client._get_machine_id()}")
    print(f"Machine Name: {client._get_machine_name()}")
    print()

    # Check portal status
    status = client.get_portal_status()
    if status['success']:
        print(f"Portal Status: OK")
        print(f"  Server Version: {status['data'].get('version')}")
    else:
        print(f"Portal Status: OFFLINE - {status.get('error')}")
        sys.exit(1)

    # Check license
    if client.is_licensed():
        print(f"\nLicense Key: {client.license_key}")
        validation = client.validate_license()
        if validation['success']:
            print(f"License Valid: Yes")
            print(f"  Client ID: {client.client_id}")
        else:
            print(f"License Valid: No - {validation['data'].get('error')}")
    else:
        print("\nNo license configured.")
        print("Use client.register() or client.login() to authenticate.")

    # Check for updates
    if client.is_licensed():
        updates = client.check_for_updates()
        if updates['success']:
            if updates['data'].get('update_available'):
                print(f"\nUpdate Available: {updates['data']['latest_version']}")
                print(f"  Mandatory: {updates['data'].get('is_mandatory', False)}")
            else:
                print(f"\nNo updates available. Running latest version.")
