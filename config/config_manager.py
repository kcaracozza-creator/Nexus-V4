#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Management System for Nexus Card Platform
Provides portable, environment-based configuration for multi-platform deployment
"""

import os
import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class ConfigManager:
    """
    Centralized configuration management with:
    - JSON-based default configs
    - Environment variable overrides
    - Cross-platform path resolution
    - Multi-deployment support
    """
    
    def __init__(self, config_dir: Optional[str] = None, env_file: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            config_dir: Directory containing config files (default: ./config)
            env_file: Path to .env file (default: ./.env)
        """
        # Determine base directory (where the script is running)
        self.base_dir = Path(__file__).parent.absolute()
        
        # Configuration directory
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = self.base_dir / 'config'
        
        # Load environment variables from .env file
        if env_file:
            load_dotenv(env_file)
        else:
            # Try to find .env in common locations
            for env_path in [self.base_dir / '.env', self.base_dir.parent / '.env']:
                if env_path.exists():
                    load_dotenv(env_path)
                    break
        
        # Load configuration files
        self.config = self._load_config()
        
        # Resolve all paths
        self._resolve_paths()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from default.json and local.json (if exists)"""
        config = {}
        
        # Load default configuration
        default_config_path = self.config_dir / 'default.json'
        if default_config_path.exists():
            with open(default_config_path, 'r') as f:
                config = json.load(f)
        else:
            # Generate default config if it doesn't exist
            config = self._generate_default_config()
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(default_config_path, 'w') as f:
                json.dump(config, f, indent=2)
        
        # Load local overrides (gitignored)
        local_config_path = self.config_dir / 'local.json'
        if local_config_path.exists():
            with open(local_config_path, 'r') as f:
                local_config = json.load(f)
                config = self._merge_configs(config, local_config)
        
        # Override with environment variables
        config = self._apply_env_overrides(config)
        
        return config
    
    def _generate_default_config(self) -> Dict[str, Any]:
        """Generate default configuration structure"""
        return {
            "system": {
                "name": "Nexus Card System",
                "version": "1.0.0",
                "platform": platform.system(),
                "mode": os.getenv("NEXUS_MODE", "desktop")  # desktop, server, kiosk
            },
            "paths": {
                "base_dir": str(self.base_dir),
                "data_dir": "data",
                "inventory_dir": "data/inventory",
                "scans_dir": "data/scans",
                "library_dir": "data/library",
                "decks_dir": "data/decks",
                "templates_dir": "data/Decklist templates",
                "cache_dir": "data/SCRYFALL_CACHE",
                "backup_dir": "data/backups",
                "logs_dir": "data/logs"
            },
            "database": {
                "type": os.getenv("DB_TYPE", "sqlite"),
                "host": os.getenv("DB_HOST", "localhost"),
                "port": int(os.getenv("DB_PORT", "5432")),
                "name": os.getenv("DB_NAME", "nexus_cards"),
                "user": os.getenv("DB_USER", "nexus"),
                "password": os.getenv("DB_PASSWORD", ""),
                "sqlite_path": "data/nexus_cards.db"
            },
            "api": {
                "enabled": os.getenv("API_ENABLED", "false").lower() == "true",
                "host": os.getenv("API_HOST", "0.0.0.0"),
                "port": int(os.getenv("API_PORT", "8000")),
                "base_url": os.getenv("API_BASE_URL", "http://localhost:8000"),
                "nexus_cards_url": os.getenv("NEXUS_CARDS_URL", "https://nexus-cards.com/api")
            },
            "sync": {
                "enabled": os.getenv("SYNC_ENABLED", "false").lower() == "true",
                "interval": int(os.getenv("SYNC_INTERVAL", "300")),  # seconds
                "auto_upload": os.getenv("AUTO_UPLOAD", "false").lower() == "true"
            },
            "quickbooks": {
                "enabled": os.getenv("QB_ENABLED", "false").lower() == "true",
                "company_file": os.getenv("QB_COMPANY_FILE", ""),
                "username": os.getenv("QB_USERNAME", ""),
                "password": os.getenv("QB_PASSWORD", "")
            },
            "hardware": {
                "scanner_enabled": os.getenv("SCANNER_ENABLED", "true").lower() == "true",
                "camera_enabled": os.getenv("CAMERA_ENABLED", "true").lower() == "true",
                "ir_sensor_enabled": os.getenv("IR_SENSOR_ENABLED", "false").lower() == "true",
                "scanner_port": os.getenv("SCANNER_PORT", "COM3"),
                "camera_index": int(os.getenv("CAMERA_INDEX", "0")),
                "gpu_enabled": os.getenv("GPU_ENABLED", "true").lower() == "true",
                "egpu_enabled": os.getenv("EGPU_ENABLED", "false").lower() == "true",
                "gpu_device": os.getenv("GPU_DEVICE", "auto"),  # auto, cuda:0, cuda:1, etc.
                "gpu_memory_fraction": float(os.getenv("GPU_MEMORY_FRACTION", "0.9")),
                "enable_mixed_precision": os.getenv("MIXED_PRECISION", "true").lower() == "true",
                "sd_card_enabled": os.getenv("SD_CARD_ENABLED", "true").lower() == "true",
                "sd_auto_upload": os.getenv("SD_AUTO_UPLOAD", "false").lower() == "true"
            },
            "ui": {
                "theme": os.getenv("UI_THEME", "professional"),
                "fullscreen": os.getenv("UI_FULLSCREEN", "false").lower() == "true",
                "kiosk_mode": os.getenv("UI_KIOSK_MODE", "false").lower() == "true"
            }
        }
    
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge two configuration dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def _apply_env_overrides(self, config: Dict) -> Dict:
        """Apply environment variable overrides to configuration"""
        # Environment variables have already been applied in _generate_default_config
        # This method is for future extensibility
        return config
    
    def _resolve_paths(self):
        """Resolve all relative paths to absolute paths"""
        if 'paths' not in self.config:
            return
        
        base_dir = Path(self.config['paths']['base_dir'])
        
        for key, path in self.config['paths'].items():
            if key == 'base_dir':
                continue
            
            # Convert to Path object
            path_obj = Path(path)
            
            # If relative, make it relative to base_dir
            if not path_obj.is_absolute():
                path_obj = base_dir / path_obj
            
            # Convert back to string and store
            self.config['paths'][key] = str(path_obj.absolute())
            
            # Create directory if it doesn't exist
            path_obj.mkdir(parents=True, exist_ok=True)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key_path: Dot-separated path (e.g., "database.host")
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any):
        """
        Set configuration value using dot notation
        
        Args:
            key_path: Dot-separated path (e.g., "database.host")
            value: Value to set
        """
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def get_path(self, path_key: str) -> Path:
        """
        Get a path from configuration as a Path object
        
        Args:
            path_key: Key in paths section (e.g., "inventory_dir")
        
        Returns:
            Path object
        """
        path_str = self.get(f'paths.{path_key}')
        if path_str:
            return Path(path_str)
        raise KeyError(f"Path '{path_key}' not found in configuration")
    
    def save_local_config(self):
        """Save current configuration to local.json"""
        local_config_path = self.config_dir / 'local.json'
        with open(local_config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_database_url(self) -> str:
        """Get database connection URL"""
        db_type = self.get('database.type')
        
        if db_type == 'sqlite':
            return f"sqlite:///{self.get('database.sqlite_path')}"
        elif db_type == 'postgresql':
            user = self.get('database.user')
            password = self.get('database.password')
            host = self.get('database.host')
            port = self.get('database.port')
            name = self.get('database.name')
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        elif db_type == 'mysql':
            user = self.get('database.user')
            password = self.get('database.password')
            host = self.get('database.host')
            port = self.get('database.port')
            name = self.get('database.name')
            return f"mysql://{user}:{password}@{host}:{port}/{name}"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def is_mode(self, mode: str) -> bool:
        """Check if running in specific mode (desktop, server, kiosk)"""
        return self.get('system.mode') == mode
    
    def __repr__(self):
        return f"ConfigManager(base_dir={self.base_dir}, mode={self.get('system.mode')})"


# Global configuration instance
_config_instance: Optional[ConfigManager] = None

def get_config() -> ConfigManager:
    """Get global configuration instance (singleton pattern)"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance

def init_config(config_dir: Optional[str] = None, env_file: Optional[str] = None):
    """Initialize global configuration with custom parameters"""
    global _config_instance
    _config_instance = ConfigManager(config_dir=config_dir, env_file=env_file)
    return _config_instance


if __name__ == "__main__":
    # Demo usage
    config = ConfigManager()
    
    print("=" * 60)
    print("NEXUS CARD SYSTEM - CONFIGURATION")
    print("=" * 60)
    print(f"\nSystem Name: {config.get('system.name')}")
    print(f"Version: {config.get('system.version')}")
    print(f"Platform: {config.get('system.platform')}")
    print(f"Mode: {config.get('system.mode')}")
    
    print(f"\nBase Directory: {config.get('paths.base_dir')}")
    print(f"Data Directory: {config.get('paths.data_dir')}")
    print(f"Inventory Directory: {config.get('paths.inventory_dir')}")
    
    print(f"\nDatabase Type: {config.get('database.type')}")
    print(f"Database URL: {config.get_database_url()}")
    
    print(f"\nAPI Enabled: {config.get('api.enabled')}")
    if config.get('api.enabled'):
        print(f"API Host: {config.get('api.host')}:{config.get('api.port')}")
    
    print(f"\nSync Enabled: {config.get('sync.enabled')}")
    print(f"Nexus Cards URL: {config.get('api.nexus_cards_url')}")
    
    print("\n" + "=" * 60)
