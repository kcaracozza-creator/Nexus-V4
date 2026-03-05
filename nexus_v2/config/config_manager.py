"""
NEXUS Configuration Manager
Centralized configuration loading and management
"""

import json
import os
from pathlib import Path

class ConfigManager:
    """Manages application configuration from nexus_config.json"""
    
    def __init__(self, config_file="config/nexus_config.json"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"Warning: Config file {self.config_file} not found. Using defaults.")
                return self.get_default_config()
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return self.get_default_config()
    
    def get_default_config(self):
        """Return default configuration if file is missing"""
        return {
            "scanner": {
                "snarf_ip": "192.168.1.219",
                "snarf_port": 5001,
                "snarf_url": "http://192.168.1.219:5001",
                "brok_ip": "192.168.1.219",
                "brok_port": 5002,
                "brok_url": "http://192.168.1.219:5001",
                "scanner_ip": "192.168.1.219",
                "scanner_port": 5001,
                "scanner_url": "http://192.168.1.219:5001",
                "timeout_seconds": 2,
                "retry_attempts": 3,
                "device_type": "DANIELSON Laptop"
            },
            "database": {
                "path": "./data/nexus_local.db",
                "backup_count": 5
            },
            "logging": {
                "level": "INFO",
                "file_path": "./logs/nexus.log",
                "max_file_size_mb": 10,
                "backup_count": 5
            },
            "card_types": {
                "enabled": ["mtg", "pokemon", "yugioh"],
                "default": "mtg"
            },
            "yugioh": {
                "api_url": "https://db.ygoprodeck.com/api/v7",
                "cache_enabled": True,
                "cache_days": 7,
                "default_language": "en"
            },
            "marketplace": {
                "server_url": "https://nexus-marketplace-api.kcaracozza.workers.dev",
                "api_prefix": "/v1",
                "store_name": "NEXUS Shop",
                "email": "",  # Set in nexus_config.json
                "password": ""  # Set in nexus_config.json - NEVER commit credentials
            },
            "zultan": {
                "url": "http://192.168.1.152:8000",
                "market_data_enabled": True,
                "price_scrape_interval_hours": 6,
                "world_cup_mode": False,
                "world_cup_scrape_interval_hours": 1
            }
        }
    
    def get(self, key_path, default=None):
        """Get configuration value using dot notation (e.g., 'scanner.snarf_ip')"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_scanner_config(self):
        """Get scanner configuration"""
        return self.get('scanner', {})
    
    def get_scanner_ip(self):
        """Get scanner IP address"""
        return self.get('scanner.snarf_ip', '192.168.1.219')
    
    def get_scanner_port(self):
        """Get scanner port"""
        return self.get('scanner.snarf_port', 5001)
    
    def get_database_path(self):
        """Get database file path"""
        return self.get('database.path', './data/nexus_local.db')
    
    def get_logging_config(self):
        """Get logging configuration"""
        return self.get('logging', {})

    def get_enabled_card_types(self):
        """Get list of enabled card types"""
        return self.get('card_types.enabled', ['mtg'])

    def get_default_card_type(self):
        """Get default card type"""
        return self.get('card_types.default', 'mtg')

    def get_yugioh_config(self):
        """Get Yu-Gi-Oh! configuration"""
        return self.get('yugioh', {})

    def get_yugioh_api_url(self):
        """Get YGOProDeck API URL"""
        return self.get('yugioh.api_url', 'https://db.ygoprodeck.com/api/v7')

    def get_marketplace_config(self):
        """Get marketplace configuration"""
        return self.get('marketplace', {
            'server_url': 'https://nexus-marketplace-api.kcaracozza.workers.dev',
            'api_prefix': '/v1',
            'store_name': 'NEXUS Shop',
            'email': '',
            'password': ''
        })

    def get_marketplace_url(self):
        """Get marketplace server URL (Cloudflare Workers)"""
        return self.get(
            'marketplace.server_url',
            'https://nexus-marketplace-api.kcaracozza.workers.dev'
        )

    def get_zultan_url(self):
        """Get ZULTAN server URL (card data + market data gateway)"""
        return self.get('zultan.url', 'http://192.168.1.152:8000')

    def is_market_data_enabled(self):
        """Check if anonymous market data reporting is enabled"""
        return self.get('zultan.market_data_enabled', True)

    def is_world_cup_mode(self):
        """Check if World Cup high-frequency mode is active"""
        return self.get('zultan.world_cup_mode', False)

    def get_library_config(self):
        """Get library configuration"""
        return self.get('library', {
            'master': 'brock',
            'brock_url': 'http://192.168.1.219:5001',
            'local_cache': True,
            'sync_on_startup': True
        })

    def get_library_master(self):
        """Get library master server (brock or local)"""
        return self.get('library.master', 'brock')

    def get_brock_url(self):
        """Get Brock server URL for library"""
        return self.get('library.brock_url', 'http://192.168.1.219:5001')

    def use_brock_library(self) -> bool:
        """Check if Brock should be used as library master"""
        return self.get('library.master', 'brock') == 'brock'

    def save_config(self):
        """Save current configuration to file"""
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

# Global configuration instance
config = ConfigManager()