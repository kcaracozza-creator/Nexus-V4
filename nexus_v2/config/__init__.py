#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# NEXUS: Universal Collectibles Recognition and Management System
# Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.
# PATENT PENDING - U.S. Provisional Application Filed November 27, 2025
# ═══════════════════════════════════════════════════════════════════════════════

"""NEXUS V2 Configuration System - Centralized configuration management."""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any

# Project root - everything is relative to this
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Core directories
DATA_DIR = PROJECT_ROOT / 'data'
ASSETS_DIR = PROJECT_ROOT / 'assets'
CACHE_DIR = PROJECT_ROOT / 'cache'
CONFIG_DIR = PROJECT_ROOT / 'config'
BACKUP_DIR = PROJECT_ROOT / 'backups'
LOGS_DIR = PROJECT_ROOT / 'logs'
LIBRARY_DIR = DATA_DIR / 'library'
DECKS_DIR = DATA_DIR / 'decks'
SCANS_DIR = DATA_DIR / 'scans'
SCRYFALL_CACHE_DIR = DATA_DIR / 'SCRYFALL_CACHE'

# Ensure directories exist
for directory in [DATA_DIR, ASSETS_DIR, CACHE_DIR, CONFIG_DIR, BACKUP_DIR,
                  LOGS_DIR, LIBRARY_DIR, DECKS_DIR, SCANS_DIR,
                  SCRYFALL_CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


@dataclass
class DatabaseConfig:
    path: str = str(DATA_DIR / 'nexus_local.db')
    backup_count: int = 5


@dataclass
class ScannerConfig:
    # Snarf Pi - Mechanical (Arm + Lights via ESP32s)
    snarf_ip: str = os.environ.get("NEXUS_SNARF_IP", "192.168.1.219")
    snarf_port: int = int(os.environ.get("NEXUS_SNARF_PORT", "5001"))
    # Brok Pi - Camera + OCR + HDD Storage
    brok_ip: str = os.environ.get("NEXUS_BROK_IP", "192.168.1.219")
    brok_port: int = int(os.environ.get("NEXUS_BROK_PORT", "5001"))
    # Brok HDD Storage (160GB) - All scans, cache, inventory
    brok_hdd_path: str = "/mnt/nexus_data"
    brok_ssh_user: str = "nexus1"
    # Legacy aliases (for backwards compat)
    scanner_ip: str = field(default="")
    scanner_port: int = 5001
    ocr_ip: str = field(default="")
    ocr_port: int = 5000
    # Settings
    timeout_seconds: int = 2
    retry_attempts: int = 3
    device_type: str = "DANIELSON Laptop"
    ocr_confidence_threshold: float = 70.0
    camera_index: int = 0
    camera_width: int = 1920
    camera_height: int = 1080

    def __post_init__(self):
        # Sync legacy fields
        if not self.scanner_ip:
            self.scanner_ip = self.snarf_ip
        if not self.ocr_ip:
            self.ocr_ip = self.brok_ip

    @property
    def snarf_url(self) -> str:
        """Mechanical control (arm + lights)"""
        return f"http://{self.snarf_ip}:{self.snarf_port}"

    @property
    def brok_url(self) -> str:
        """Camera capture + OCR"""
        return f"http://{self.brok_ip}:{self.brok_port}"

    # Legacy aliases
    @property
    def scanner_url(self) -> str:
        return self.snarf_url

    @property
    def ocr_url(self) -> str:
        return self.brok_url


@dataclass
class AIConfig:
    learning_enabled: bool = True
    grading_confidence_threshold: float = 0.85


@dataclass
class UIConfig:
    theme: str = "pro"
    font_family: str = "Segoe UI"
    font_size: int = 11
    window_width: int = 1400
    window_height: int = 900
    color_accent: str = "#c9a227"


@dataclass
class MarketplaceConfig:
    enabled: bool = True
    api_url: str = "https://nexus-cards.com"


@dataclass
class GameConfig:
    active_game: str = "magic"
    magic_library: str = "nexus_library.json"
    pokemon_library: str = "pokemon_library.json"


@dataclass
class NexusConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    marketplace: MarketplaceConfig = field(default_factory=MarketplaceConfig)
    game: GameConfig = field(default_factory=GameConfig)
    version: str = "2.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NexusConfig':
        config = cls()
        for key, val in data.items():
            if hasattr(config, key) and isinstance(val, dict):
                # Handle scanner config migration from old field names
                if key == 'scanner' and val:
                    # Migrate old default_ip/default_port to new field names
                    if 'default_ip' in val:
                        val['snarf_ip'] = val.pop('default_ip')
                        # Also set legacy field
                        val['scanner_ip'] = val['snarf_ip']
                    if 'default_port' in val:
                        val['snarf_port'] = val.pop('default_port')
                        # Also set legacy field
                        val['scanner_port'] = val['snarf_port']
                setattr(config, key, type(getattr(config, key))(**val))
            elif hasattr(config, key):
                setattr(config, key, val)
        return config


class ConfigManager:
    CONFIG_FILE = CONFIG_DIR / 'nexus_config.json'
    
    def __init__(self):
        self._config = NexusConfig()
        self._load()
        
    def _load(self):
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._config = NexusConfig.from_dict(json.load(f))
            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                logging.warning("Config load failed: %s", str(e))
        else:
            self.save()
            
    def save(self):
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._config.to_dict(), f, indent=2)
            
    @property
    def database(self): return self._config.database
    @property
    def scanner(self): return self._config.scanner
    @property
    def ai(self): return self._config.ai
    @property
    def ui(self): return self._config.ui
    @property
    def marketplace(self): return self._config.marketplace
    @property
    def game(self): return self._config.game
    @property
    def version(self): return self._config.version


_config_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    global _config_instance  # Need global for singleton pattern
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


__all__ = ['PROJECT_ROOT', 'DATA_DIR', 'ASSETS_DIR', 'CACHE_DIR', 'CONFIG_DIR',
           'NexusConfig', 'ConfigManager', 'get_config', 'get_env']
