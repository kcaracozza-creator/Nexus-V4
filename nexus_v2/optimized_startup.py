#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS OPTIMIZED STARTUP MODULE
==============================
Fixes the lag issues in nexus.py with:
1. Lazy loading - don't load until needed
2. Pickle caching - 10x faster than CSV
3. Threaded initialization - GUI shows immediately
4. Progress feedback - user knows what's happening

Drop this file in your NEXUS directory and import it.

Usage:
    from nexus_optimized_startup import OptimizedDataLoader, LazyModule
    
    # In your __init__:
    self.data_loader = OptimizedDataLoader(self.update_status)
    self.data_loader.start_background_load()
    
    # When you need the data:
    master_cards = self.data_loader.get_master_cards()  # Lazy loads if needed

Author: Jaques (The Twat Rocket)
For: Judge Miyagi
Date: Dec 2, 2025
"""

import os
import sys
import time
import pickle
import csv
import threading
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from functools import lru_cache


# ============================================
# CONFIGURATION
# ============================================

@dataclass
class LoaderConfig:
    """Configuration for the data loader"""
    # Data paths (update these for your system)
    master_csv_path: str = r"E:\MTTGG\MASTER  SHEETS\cards.csv"
    nexus_library_path: str = r"E:\MTTGG\data\nexus_library.json"
    price_cache_path: str = r"E:\MTTGG\data\price_cache.json"
    
    # Cache settings
    cache_dir: str = r"E:\MTTGG\cache"
    use_pickle_cache: bool = True
    cache_expiry_hours: int = 24
    
    # Performance settings
    lazy_load: bool = True
    threaded_load: bool = True
    show_progress: bool = True


# ============================================
# PICKLE CACHE MANAGER
# ============================================

class PickleCache:
    """
    Manages pickle caches for fast data loading.
    
    CSV loading: ~5-10 seconds for 89MB
    Pickle loading: ~0.5-1 second for same data
    
    That's 10x faster startup!
    """
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_path(self, source_path: str) -> Path:
        """Generate cache filename based on source file"""
        # Use hash of path + file modification time for cache key
        source = Path(source_path)
        if source.exists():
            mtime = source.stat().st_mtime
            key = f"{source_path}_{mtime}"
        else:
            key = source_path
        
        hash_name = hashlib.md5(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{source.stem}_{hash_name}.pkl"
    
    def is_cache_valid(self, source_path: str, max_age_hours: int = 24) -> bool:
        """Check if cache exists and is fresh"""
        cache_path = self._get_cache_path(source_path)
        
        if not cache_path.exists():
            return False
        
        # Check if source file was modified after cache
        source = Path(source_path)
        if source.exists():
            if source.stat().st_mtime > cache_path.stat().st_mtime:
                return False
        
        # Check cache age
        cache_age = time.time() - cache_path.stat().st_mtime
        max_age_seconds = max_age_hours * 3600
        
        return cache_age < max_age_seconds
    
    def load(self, source_path: str) -> Optional[Any]:
        """Load data from pickle cache"""
        cache_path = self._get_cache_path(source_path)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Cache load error: {e}")
            return None
    
    def save(self, source_path: str, data: Any) -> bool:
        """Save data to pickle cache"""
        cache_path = self._get_cache_path(source_path)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception as e:
            print(f"Cache save error: {e}")
            return False


# ============================================
# LAZY MODULE LOADER
# ============================================

class LazyModule:
    """
    Delays module import until first use.
    
    Usage:
        tcg_scraper = LazyModule('modules.scrapers.tcgplayer_scraper', 'TCGPlayerScraper')
        
        # Module not loaded yet...
        
        scraper = tcg_scraper.get()  # NOW it loads
    """
    
    def __init__(self, module_path: str, class_name: str = None, 
                 init_args: tuple = None, init_kwargs: dict = None):
        self.module_path = module_path
        self.class_name = class_name
        self.init_args = init_args or ()
        self.init_kwargs = init_kwargs or {}
        self._instance = None
        self._loaded = False
        self._available = None
        self._load_error = None
    
    def is_available(self) -> bool:
        """Check if module can be imported without loading it"""
        if self._available is not None:
            return self._available
        
        try:
            import importlib.util
            spec = importlib.util.find_spec(self.module_path)
            self._available = spec is not None
        except Exception:
            self._available = False
        
        return self._available
    
    def get(self) -> Optional[Any]:
        """Get the module/class instance, loading if needed"""
        if self._loaded:
            return self._instance
        
        try:
            import importlib
            module = importlib.import_module(self.module_path)
            
            if self.class_name:
                cls = getattr(module, self.class_name)
                self._instance = cls(*self.init_args, **self.init_kwargs)
            else:
                self._instance = module
            
            self._loaded = True
            self._available = True
            
        except Exception as e:
            self._load_error = str(e)
            self._available = False
            self._instance = None
        
        return self._instance
    
    def get_error(self) -> Optional[str]:
        """Get load error if any"""
        return self._load_error


# ============================================
# OPTIMIZED DATA LOADER
# ============================================

class OptimizedDataLoader:
    """
    Handles all data loading with optimization.
    
    Features:
    - Pickle caching (10x faster than CSV)
    - Background threading (GUI shows immediately)
    - Lazy loading (load only when needed)
    - Progress callbacks (user sees what's happening)
    """
    
    def __init__(self, status_callback: Callable[[str], None] = None, 
                 config: LoaderConfig = None):
        self.config = config or LoaderConfig()
        self.status_callback = status_callback or print
        
        # Initialize pickle cache
        self.cache = PickleCache(self.config.cache_dir)
        
        # Data storage
        self._master_cards: Dict = {}
        self._master_cards_by_name: Dict = {}
        self._nexus_library: Dict = {}
        self._price_cache: Dict = {}
        
        # Loading state
        self._loading = False
        self._loaded = {
            'master_cards': False,
            'nexus_library': False,
            'price_cache': False
        }
        self._load_thread: Optional[threading.Thread] = None
        self._load_errors: List[str] = []
    
    def _update_status(self, message: str):
        """Thread-safe status update"""
        if self.status_callback:
            try:
                self.status_callback(message)
            except Exception:
                print(f"Status: {message}")
    
    # ------------------------------------------
    # MASTER CARDS DATABASE
    # ------------------------------------------
    
    def _load_master_cards_from_csv(self) -> tuple:
        """Load master cards from CSV (slow but works first time)"""
        master_cards = {}
        master_cards_by_name = {}
        
        csv_path = self.config.master_csv_path
        if not os.path.exists(csv_path):
            self._load_errors.append(f"Master CSV not found: {csv_path}")
            return master_cards, master_cards_by_name
        
        self._update_status("Loading master cards from CSV...")
        start = time.time()
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                uuid = row.get('uuid', '')
                name = row.get('name', '')
                
                if uuid:
                    master_cards[uuid] = row
                    
                    if name:
                        if name not in master_cards_by_name:
                            master_cards_by_name[name] = []
                        master_cards_by_name[name].append(uuid)
                
                count += 1
                if count % 25000 == 0:
                    self._update_status(f"Loading cards... {count:,}")
        
        elapsed = time.time() - start
        self._update_status(f"Loaded {len(master_cards):,} cards in {elapsed:.1f}s")
        
        return master_cards, master_cards_by_name
    
    def _load_master_cards(self) -> bool:
        """Load master cards with pickle caching"""
        csv_path = self.config.master_csv_path
        
        # Try pickle cache first
        if self.config.use_pickle_cache:
            if self.cache.is_cache_valid(csv_path, self.config.cache_expiry_hours):
                self._update_status("Loading master cards from cache...")
                start = time.time()
                
                cached = self.cache.load(csv_path)
                if cached:
                    self._master_cards, self._master_cards_by_name = cached
                    elapsed = time.time() - start
                    self._update_status(f"Cache loaded: {len(self._master_cards):,} cards in {elapsed:.2f}s")
                    self._loaded['master_cards'] = True
                    return True
        
        # Load from CSV
        self._master_cards, self._master_cards_by_name = self._load_master_cards_from_csv()
        
        # Save to pickle cache for next time
        if self.config.use_pickle_cache and self._master_cards:
            self._update_status("Saving to cache for faster startup next time...")
            self.cache.save(csv_path, (self._master_cards, self._master_cards_by_name))
        
        self._loaded['master_cards'] = True
        return bool(self._master_cards)
    
    def get_master_cards(self) -> Dict:
        """Get master cards, loading if needed (lazy load)"""
        if not self._loaded['master_cards']:
            self._load_master_cards()
        return self._master_cards
    
    def get_master_cards_by_name(self) -> Dict:
        """Get master cards by name lookup"""
        if not self._loaded['master_cards']:
            self._load_master_cards()
        return self._master_cards_by_name
    
    # ------------------------------------------
    # BACKGROUND LOADING
    # ------------------------------------------
    
    def _background_load_all(self):
        """Load all data in background thread"""
        self._loading = True
        
        try:
            # Load master cards (biggest file)
            self._load_master_cards()
            
            # Add other data loads here as needed
            # self._load_nexus_library()
            # self._load_price_cache()
            
        except Exception as e:
            self._load_errors.append(f"Background load error: {e}")
        
        self._loading = False
        self._update_status("Background loading complete!")
    
    def start_background_load(self):
        """Start loading data in background thread"""
        if self._loading:
            return
        
        if self.config.threaded_load:
            self._load_thread = threading.Thread(
                target=self._background_load_all,
                daemon=True
            )
            self._load_thread.start()
            self._update_status("Starting background data load...")
        else:
            self._background_load_all()
    
    def wait_for_load(self, timeout: float = None):
        """Wait for background load to complete"""
        if self._load_thread and self._load_thread.is_alive():
            self._load_thread.join(timeout)
    
    def is_loading(self) -> bool:
        """Check if still loading"""
        return self._loading
    
    def is_loaded(self, data_name: str = None) -> bool:
        """Check if data is loaded"""
        if data_name:
            return self._loaded.get(data_name, False)
        return all(self._loaded.values())
    
    def get_load_errors(self) -> List[str]:
        """Get any errors from loading"""
        return self._load_errors


# ============================================
# OPTIMIZED IMPORTS MANAGER
# ============================================

class OptimizedImports:
    """
    Manages lazy loading of all NEXUS module imports.
    
    Instead of 198 imports at startup, modules load on demand.
    """
    
    def __init__(self, status_callback: Callable[[str], None] = None):
        self.status = status_callback or print
        
        # Define all lazy modules
        self._modules = {
            # Scrapers
            'tcg_scraper': LazyModule(
                'modules.scrapers.tcgplayer_scraper', 
                'TCGPlayerScraper'
            ),
            'scryfall_scraper': LazyModule(
                'modules.scrapers.scryfall_scraper',
                'ScryfallScraper'
            ),
            
            # AI Components
            'deck_optimizer': LazyModule(
                'ai_deck_optimizer',
                'AdvancedDeckOptimizer'
            ),
            'trading_bot': LazyModule(
                'ai_trading_bot',
                'AITradingBot'
            ),
            'meta_analyzer': LazyModule(
                'ai_deck_optimizer',
                'AIMetaAnalyzer'
            ),
            
            # Recognition
            'card_recognizer': LazyModule(
                'modules.scanner.ai_card_recognition_v2',
                'MTGCardRecognizer'
            ),
            
            # Library System
            'library_system': LazyModule(
                'nexus_library_system',
                'NexusLibrarySystem'
            ),
            
            # Theme
            'nexus_theme': LazyModule('nexus_theme'),
            
            # Business
            'quickbooks': LazyModule(
                'quickbooks_integration',
                'QuickBooksExporter'
            ),
            'marketplace': LazyModule(
                'modules.marketplace.nexus_marketplace',
                'NEXUSMarketplace'
            ),
        }
        
        self._instances = {}
    
    def get(self, name: str) -> Optional[Any]:
        """Get a module by name, loading if needed"""
        if name in self._instances:
            return self._instances[name]
        
        if name not in self._modules:
            return None
        
        module = self._modules[name]
        instance = module.get()
        
        if instance:
            self._instances[name] = instance
            self.status(f"Loaded: {name}")
        else:
            error = module.get_error()
            if error:
                self.status(f"Could not load {name}: {error}")
        
        return instance
    
    def is_available(self, name: str) -> bool:
        """Check if a module is available"""
        if name not in self._modules:
            return False
        return self._modules[name].is_available()
    
    def preload(self, names: List[str]):
        """Preload specific modules in background"""
        def _preload():
            for name in names:
                self.get(name)
        
        thread = threading.Thread(target=_preload, daemon=True)
        thread.start()


# ============================================
# INTEGRATION EXAMPLE
# ============================================

def integrate_with_nexus():
    """
    Example of how to integrate this with your existing nexus.py
    
    Replace your current __init__ startup sequence with this pattern.
    """
    
    example_code = '''
# In your NexusGUI class __init__:

def __init__(self):
    self.root = tk.Tk()
    self.root.title("NEXUS - Loading...")
    self.root.geometry("1600x1000")
    
    # Show loading screen immediately
    self._show_loading_screen()
    
    # Initialize optimized loaders
    from nexus_optimized_startup import OptimizedDataLoader, OptimizedImports
    
    self.data_loader = OptimizedDataLoader(
        status_callback=self._update_loading_status
    )
    self.imports = OptimizedImports(
        status_callback=self._update_loading_status
    )
    
    # Start background loading
    self.data_loader.start_background_load()
    
    # Build GUI while data loads
    self._build_gui()
    
    # Preload critical modules
    self.imports.preload(['scryfall_scraper', 'nexus_theme'])
    
    # Update title when ready
    self.root.after(100, self._check_load_complete)

def _show_loading_screen(self):
    """Show a loading indicator"""
    self.loading_label = tk.Label(
        self.root, 
        text="Loading NEXUS...",
        font=('Perpetua', 24),
        bg='#0d0d0d',
        fg='#ffd700'
    )
    self.loading_label.place(relx=0.5, rely=0.5, anchor='center')

def _update_loading_status(self, message):
    """Update loading screen"""
    if hasattr(self, 'loading_label'):
        self.loading_label.config(text=message)
        self.root.update_idletasks()  # Don't use update() - just idletasks

def _check_load_complete(self):
    """Check if background load is done"""
    if self.data_loader.is_loading():
        self.root.after(100, self._check_load_complete)
    else:
        self.loading_label.destroy()
        self.root.title("NEXUS - Complete Card Management System")
        
# When you need master cards (lazy load):
def get_card_data(self, card_name):
    master = self.data_loader.get_master_cards_by_name()
    return master.get(card_name, [])

# When you need a module (lazy load):
def run_price_check(self):
    scraper = self.imports.get('tcg_scraper')
    if scraper:
        return scraper.get_price(...)
'''
    
    return example_code


# ============================================
# STANDALONE TEST
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("NEXUS OPTIMIZED STARTUP - TEST")
    print("=" * 60)
    
    # Test the loader
    def status(msg):
        print(f"[STATUS] {msg}")
    
    loader = OptimizedDataLoader(status_callback=status)
    
    print("\n1. Testing background load...")
    loader.start_background_load()
    
    print("\n2. Doing other stuff while loading...")
    for i in range(5):
        print(f"   Working... {i+1}")
        time.sleep(0.5)
    
    print("\n3. Waiting for load to complete...")
    loader.wait_for_load(timeout=30)
    
    print("\n4. Checking results...")
    cards = loader.get_master_cards()
    print(f"   Master cards loaded: {len(cards):,}")
    
    by_name = loader.get_master_cards_by_name()
    print(f"   Unique names: {len(by_name):,}")
    
    errors = loader.get_load_errors()
    if errors:
        print(f"\n   Errors: {errors}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
