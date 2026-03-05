#!/usr/bin/env python3
"""
NEXUS Configuration System
Centralized config for all paths and settings - no more hardcoded values!
"""

import os
import json
from pathlib import Path


class NexusConfig:
    """Centralized configuration management for NEXUS"""
    
    # Default config file location
    CONFIG_FILE = "nexus_config.json"
    
    # Default paths (can be overridden by config file)
    DEFAULTS = {
        # Data paths
        "master_file": "",  # Will auto-detect or prompt
        "collection_folder": "",
        "deck_templates_folder": "",
        "export_folder": "",
        
        # Database
        "database_path": "nexus_data.db",
        
        # API Keys (optional)
        "scryfall_cache_days": 7,
        
        # UI Settings
        "theme": "dark",
        "window_width": 1400,
        "window_height": 900,
        
        # Deck Builder Settings
        "default_format": "Commander",
        "default_strategy": "balanced",
        "prioritize_slow_inventory": True,
        "prioritize_high_inventory": True,
        "high_inventory_threshold": 90,
        
        # Scanner Settings
        "arduino_port": "AUTO",
        "camera_index": 0,
        "led_brightness": 50,
    }
    
    def __init__(self, config_path=None):
        self.config_path = config_path or self.CONFIG_FILE
        self.config = dict(self.DEFAULTS)
        self._load_config()
        self._auto_detect_paths()
    
    def _load_config(self):
        """Load config from JSON file if it exists"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
                print(f"✅ Loaded config from {self.config_path}")
            except Exception as e:
                print(f"⚠️ Could not load config: {e}, using defaults")
    
    def _auto_detect_paths(self):
        """Auto-detect common paths if not set"""
        # Try to find Master File
        if not self.config["master_file"]:
            common_locations = [
                r"E:\MTTGG\MASTER  SHEETS\Master File .csv",
                r"E:\MTTGG\MASTER SHEETS\Master File.csv",
                r"C:\MTTGG\MASTER SHEETS\Master File.csv",
                os.path.expanduser("~/MTTGG/MASTER SHEETS/Master File.csv"),
                "./data/Master File.csv",
                "./Master File.csv",
            ]
            for loc in common_locations:
                if os.path.exists(loc):
                    self.config["master_file"] = loc
                    print(f"✅ Auto-detected Master File: {loc}")
                    break
        
        # Try to find collection folder
        if not self.config["collection_folder"]:
            common_locations = [
                r"E:\MTTGG\Collection",
                r"E:\MTTGG\Inventory",
                os.path.expanduser("~/MTTGG/Collection"),
                "./collection",
                "./inventory",
            ]
            for loc in common_locations:
                if os.path.exists(loc):
                    self.config["collection_folder"] = loc
                    print(f"✅ Auto-detected Collection: {loc}")
                    break
        
        # Try to find deck templates
        if not self.config["deck_templates_folder"]:
            common_locations = [
                r"E:\MTTGG\Deck Templates",
                r"E:\MTTGG\Decklists",
                os.path.expanduser("~/MTTGG/Deck Templates"),
                "./deck_templates",
                "./decklists",
            ]
            for loc in common_locations:
                if os.path.exists(loc):
                    self.config["deck_templates_folder"] = loc
                    print(f"✅ Auto-detected Deck Templates: {loc}")
                    break
    
    def save(self):
        """Save current config to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"✅ Saved config to {self.config_path}")
            return True
        except Exception as e:
            print(f"❌ Could not save config: {e}")
            return False
    
    def get(self, key, default=None):
        """Get a config value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set a config value"""
        self.config[key] = value
    
    def __getitem__(self, key):
        return self.config.get(key)
    
    def __setitem__(self, key, value):
        self.config[key] = value
    
    # Convenience properties
    @property
    def master_file(self):
        return self.config.get("master_file", "")
    
    @property
    def collection_folder(self):
        return self.config.get("collection_folder", "")
    
    @property
    def deck_templates_folder(self):
        return self.config.get("deck_templates_folder", "")
    
    @property
    def database_path(self):
        return self.config.get("database_path", "nexus_data.db")


# Global config instance
_config = None

def get_config():
    """Get the global config instance"""
    global _config
    if _config is None:
        _config = NexusConfig()
    return _config


def init_config(config_path=None):
    """Initialize config with custom path"""
    global _config
    _config = NexusConfig(config_path)
    return _config


# Quick access functions
def get_master_file():
    return get_config().master_file

def get_collection_folder():
    return get_config().collection_folder

def get_deck_templates():
    return get_config().deck_templates_folder


if __name__ == "__main__":
    # Test config system
    config = NexusConfig()
    print("\n📋 Current Configuration:")
    print("-" * 40)
    for key, value in config.config.items():
        print(f"  {key}: {value}")
    
    # Save default config
    config.save()
    print("\n✅ Default config saved to nexus_config.json")
