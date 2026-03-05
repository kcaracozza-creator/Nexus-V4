#!/usr/bin/env python3
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# NEXUS: Universal Collectibles Recognition and Management System
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# 
# Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.
# 
# PATENT PENDING - U.S. Provisional Application Filed November 27, 2025
# Application: 35 U.S.C. \u00a7 111(b)
# Classification: G06V 10/00, G06V 30/19, G06N 3/08, G06Q 30/02, H04N 23/00
# 
# This software is proprietary and confidential. Unauthorized copying,
# modification, distribution, or use is strictly prohibited.
# 
# See LICENSE file for full terms.
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

# -*- coding: utf-8 -*-
"""
NEXUS V3 Main Application
=========================

The main application window with tabbed interface.
Clean, modular design with crash protection.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..config import get_config, PROJECT_ROOT
from ..library.library_system import LibrarySystem
from ..ai.shop_personality import AdaptiveShopPersonality
from ..ai.shop_intelligence import ShopIntelligenceAI
from ..ai.universal_collectibles import (
    UniversalShopAI, CollectibleIndustry,
    MTGSystem, PokemonSystem, SportsCardSystem, ComicBookSystem, CoinSystem
)
from .theme import ProTheme, ThemeColors
from ..data.scryfall_db import ScryfallDatabase
from .tabs.collection import CollectionTab
from .tabs.deck_builder import DeckBuilderTab
from .tabs.analytics import AnalyticsTab
from .tabs.sales import SalesTab
from .tabs.settings import SettingsTab
from .tabs.scanner_modes import ScannerModesTab  # Universal Scanner (kept)
from .tabs.hardware_controls import HardwareControlsTab

# Merchandise Authentication
try:
    from nexus_v2.merchandise.merchandise_ui import MerchandiseAuthUI
    _HAS_MERCH_AUTH = True
except ImportError:
    _HAS_MERCH_AUTH = False

# Optional imports - graceful fallback
try:
    from .tabs.ai_training import AITrainingTab
    AI_TRAINING_AVAILABLE = True
except ImportError as e:
    AI_TRAINING_AVAILABLE = False
    AITrainingTab = None

logger = logging.getLogger(__name__)


class NexusApp:
    """
    Main NEXUS V3 Application.
    
    Clean, modular design implementing:
    - Professional dark theme
    - Tabbed interface
    - Crash protection
    - Modular tab loading
    """
    
    APP_TITLE = "NEXUS V3 - Universal Collectibles Management"
    
    def __init__(self):
        """Initialize the application"""
        logger.info("=" * 60)
        logger.info("  NEXUS V3 Starting...")
        logger.info("=" * 60)
        
        # Configuration
        self.config = get_config()
        
        # Create root window
        self.root = tk.Tk()
        self.root.title(self.APP_TITLE)
        self.root.geometry(f"{self.config.ui.window_width}x{self.config.ui.window_height}")
        
        # Set application icon
        self._set_app_icon()
        
        # Apply theme
        self.theme = ProTheme(self.root)
        self.theme.apply()
        self.colors = self.theme.get_colors()
        
        # Initialize core systems
        self._init_systems()
        
        # Build UI
        self._build_ui()
        
        # Finalize
        self._finalize()
        
        logger.info("NEXUS V3 initialized successfully")
    
    def _set_app_icon(self):
        """Set the application window icon"""
        try:
            # Try to load the brand icon from assets folder
            icon_paths = [
                Path(__file__).parent.parent / "assets" / "brand_icon.jpg",
                Path("E:/MTTGG/PYTHON SOURCE FILES/nexus_v2/assets/brand_icon.jpg"),
                Path("E:/MTTGG/BRAND ICON.jpg"),
            ]
            
            icon_path = None
            for p in icon_paths:
                if p.exists():
                    icon_path = p
                    break
            
            if icon_path:
                # Use PIL to convert JPG to PhotoImage for window icon
                try:
                    from PIL import Image, ImageTk
                    
                    # Load and resize icon
                    img = Image.open(icon_path)
                    # Create multiple sizes for better display
                    img_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
                    img_64 = img.resize((64, 64), Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage
                    self._icon_32 = ImageTk.PhotoImage(img_32)
                    self._icon_64 = ImageTk.PhotoImage(img_64)
                    
                    # Set window icon (use wm_iconphoto for better cross-platform support)
                    self.root.wm_iconphoto(True, self._icon_64, self._icon_32)
                    logger.info(f"[OK] Brand icon loaded: {icon_path}")
                    
                except ImportError:
                    logger.debug("PIL not available for icon loading")
                except Exception as e:
                    logger.debug(f"Failed to load icon with PIL: {e}")
            else:
                logger.debug("Brand icon not found")
                
        except Exception as e:
            logger.debug(f"Icon setup failed (non-critical): {e}")
    
    def _init_systems(self):
        """Initialize core systems"""
        logger.info("Initializing core systems...")
        
        # Library system
        try:
            # Uses local SQLite database at nexus_v2/data/nexus_library.db
            # Can optionally sync with Brock (192.168.1.219) for OCR updates
            self.library = LibrarySystem(
                remote_url="http://192.168.1.219:5001/api/library/all"
            )
            logger.info(f"Library loaded: {len(self.library)} cards")
        except Exception as e:
            logger.error(f"Failed to load library: {e}")
            self.library = None

        # Scryfall Database for pricing and images
        try:
            self.scryfall_db = ScryfallDatabase(
                bulk_json_path=r"E:\MTTGG\cards.json",
                auto_load=True
            )
            stats = self.scryfall_db.get_stats()
            logger.info(f"Scryfall DB loaded: {stats['total_cards']:,} cards, {stats['cards_with_prices']:,} priced")
        except FileNotFoundError:
            logger.warning("Scryfall cards.json not found at E:\\MTTGG\\cards.json - prices unavailable")
            self.scryfall_db = None
        except Exception as e:
            logger.error(f"Failed to load Scryfall database: {e}")
            self.scryfall_db = None
        
        # Shop Personality System (Patent Claim 4)
        try:
            self.shop_personality = AdaptiveShopPersonality("MTTGG")
            self.ui_recommendations = self.shop_personality.get_ui_recommendations()
            logger.info(f"[PERSONALITY] Shop Personality: {self.shop_personality.get_adaptation_level()}")
        except Exception as e:
            logger.error(f"Failed to load shop personality: {e}")
            self.shop_personality = None
            self.ui_recommendations = None
        
        # Cross-Industry AI System (Patent Claim 3)
        try:
            self.universal_ai = UniversalShopAI()
            # Register supported industries
            self.universal_ai.register_industry(MTGSystem())
            self.universal_ai.register_industry(PokemonSystem())
            self.universal_ai.register_industry(SportsCardSystem('Baseball'))
            self.universal_ai.register_industry(ComicBookSystem())
            self.universal_ai.register_industry(CoinSystem())
            self.universal_ai.seed_universal_insights()
            
            # Track active industry (default MTG)
            self.active_industry = CollectibleIndustry.MTG
            logger.info(f"[MULTI] Cross-Industry AI: {len(self.universal_ai.get_registered_industries())} industries registered")
        except Exception as e:
            logger.error(f"Failed to load Cross-Industry AI: {e}")
            self.universal_ai = None
            self.active_industry = CollectibleIndustry.MTG
        
        # Shop Intelligence AI System (Patent Claim 9)
        try:
            self.shop_intelligence = ShopIntelligenceAI("MTTGG")
            logger.info("[SHOP] Shop Intelligence AI initialized")
        except Exception as e:
            logger.error(f"Failed to load Shop Intelligence AI: {e}")
            self.shop_intelligence = None
            
        # Scanner (lazy loaded)
        self._scanner = None
        
    def _build_ui(self):
        """Build the main UI"""
        logger.info("Building UI...")
        
        # Main container
        self.main_frame = ttk.Frame(self.root, style='TFrame')
        self.main_frame.pack(fill='both', expand=True)
        
        # Header
        self._create_header()
        
        # Status bar (create BEFORE notebook so _update_status works)
        self._create_status_bar()
        
        # Tab notebook
        self._create_notebook()
        
    def _create_header(self):
        """Create application header with logo"""
        header = tk.Frame(self.main_frame, bg=self.colors.bg_surface, height=70)
        header.pack(fill='x')
        header.pack_propagate(False)

        # Logo/Title
        title_frame = tk.Frame(header, bg=self.colors.bg_surface)
        title_frame.pack(side='left', padx=20, pady=8)

        # Load and display logo
        self._header_logo = None
        try:
            from PIL import Image, ImageTk
            logo_paths = [
                Path(__file__).parent.parent / "assets" / "brand_icon.jpg",
                PROJECT_ROOT / "nexus_v2" / "assets" / "brand_icon.jpg",
                PROJECT_ROOT / "archive" / "temp_images" / "brand_icon_original.jpg",
            ]
            for lp in logo_paths:
                if lp.exists():
                    img = Image.open(lp)
                    img = img.resize((50, 50), Image.Resampling.LANCZOS)
                    self._header_logo = ImageTk.PhotoImage(img)
                    tk.Label(
                        title_frame,
                        image=self._header_logo,
                        bg=self.colors.bg_surface
                    ).pack(side='left', padx=(0, 10))
                    break
        except Exception as e:
            logger.debug(f"Header logo load failed: {e}")

        tk.Label(
            title_frame,
            text="NEXUS",
            font=('Segoe UI', 28, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(side='left')

        tk.Label(
            title_frame,
            text="V3",
            font=('Segoe UI', 14),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        ).pack(side='left', padx=(5, 0), pady=(12, 0))

        # Stats display
        stats_frame = tk.Frame(header, bg=self.colors.bg_surface)
        stats_frame.pack(side='right', padx=20, pady=10)

        card_count = len(self.library) if self.library else 0

        tk.Label(
            stats_frame,
            text=f"{card_count:,}",
            font=('Segoe UI', 22, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(side='left')

        tk.Label(
            stats_frame,
            text=" cards",
            font=('Segoe UI', 14),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        ).pack(side='left')
        
    def _create_notebook(self):
        """Create tabbed interface"""
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Track tab switch times for personality learning
        self._tab_switch_time = {}
        self._current_tab = None
        
        # Bind tab change event for UI usage tracking (Patent Claim 4)
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
        
        # Create tabs
        self._create_collection_tab()
        self._create_scanner_modes_tab()  # Universal Scanner
        self._create_merchandise_auth_tab()  # FIFA Merchandise Authentication
        self._create_hardware_controls_tab()
        self._create_ai_training_tab()
        self._create_deck_builder_tab()
        self._create_sales_tab()
        self._create_analytics_tab()
        self._create_settings_tab()
        
        # Connect collection tab to sales tab for "List for Sale" functionality
        if hasattr(self, 'collection_tab') and hasattr(self, 'sales_tab'):
            if hasattr(self.collection_tab, 'set_sales_tab'):
                self.collection_tab.set_sales_tab(self.sales_tab)
            if hasattr(self.collection_tab, 'set_notebook'):
                self.collection_tab.set_notebook(self.notebook)

        # Apply Adaptive UI based on Shop Personality (Patent Claim 4)
        self._apply_adaptive_ui()

    def _apply_adaptive_ui(self):
        """
        Patent Claim 4: Dynamically adapt UI based on shop personality.
        Asks user before hiding unused tabs.
        """
        if not self.ui_recommendations:
            return

        try:
            from tkinter import messagebox

            tab_priority = getattr(self.ui_recommendations, 'tab_priority', [])

            # Find tabs to hide
            tabs_to_hide = []
            for rec in tab_priority:
                if isinstance(rec, dict) and not rec.get('visible', True):
                    tabs_to_hide.append(rec.get('tab', ''))

            if not tabs_to_hide:
                return

            # Ask user before applying changes
            msg = "Based on your shop's usage patterns, NEXUS recommends hiding:\n\n"
            msg += "\n".join(f"  - {tab}" for tab in tabs_to_hide)
            msg += "\n\nApply these UI optimizations?"

            if messagebox.askyesno("Adaptive UI", msg):
                tab_map = {
                    'Collection': 0, 'Scanner': 1, 'Hardware Scanner': 1,
                    'Deck Builder': 2, 'Sales': 3, 'Online Marketplace': 3,
                    'Analytics': 4, 'Business Intelligence': 4, 'Settings': 5
                }
                for tab_name in tabs_to_hide:
                    if tab_name in tab_map:
                        try:
                            self.notebook.tab(tab_map[tab_name], state='hidden')
                            logger.info(f"[ADAPTIVE] Hidden tab: {tab_name}")
                        except Exception:
                            pass
                logger.info("[ADAPTIVE] UI adapted with user approval")
            else:
                logger.info("[ADAPTIVE] User declined UI adaptation")
        except Exception as e:
            logger.debug(f"Adaptive UI skipped: {e}")

    def _on_tab_changed(self, event):
        """Track tab usage for shop personality learning (Patent Claim 4)"""
        import time
        
        # Calculate time spent on previous tab
        if self._current_tab and self._current_tab in self._tab_switch_time:
            time_spent = time.time() - self._tab_switch_time[self._current_tab]
            
            # Record to shop personality
            if self.shop_personality and time_spent > 2:  # Only if > 2 seconds
                try:
                    tab_name = self._current_tab
                    feature_name = f"{tab_name} Tab"
                    self.shop_personality.record_ui_usage(feature_name, tab_name, time_spent)
                except Exception as e:
                    logger.debug(f"Failed to record UI usage: {e}")
        
        # Update current tab
        try:
            current_idx = self.notebook.index(self.notebook.select())
            tab_names = ['Collection', 'Scanner', 'Deck Builder', 'Sales', 'Analytics', 'Settings']
            self._current_tab = tab_names[current_idx] if current_idx < len(tab_names) else 'Unknown'
            self._tab_switch_time[self._current_tab] = time.time()
        except:
            pass
        
    def _create_collection_tab(self):
        """Create Collection Management tab - Enhanced with filters and call signs"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="\ud83d\udce6 Collection")
        
        # Use the modular CollectionTab component
        self.collection_tab = CollectionTab(
            parent=tab,
            library=self.library,
            scryfall_db=self.scryfall_db
        )
        
    def _create_scanner_modes_tab(self):
        """Create Scanner Modes tab (3-mode universal scanner)"""
        self.scanner_modes_tab = ScannerModesTab(
            parent_notebook=self.notebook,
            config=self.config,
            library=self.library
        )

    def _create_merchandise_auth_tab(self):
        """Create Merchandise Authentication tab (FIFA workflow)"""
        if _HAS_MERCH_AUTH:
            try:
                self.merch_auth_tab = MerchandiseAuthUI(
                    parent=None,
                    notebook=self.notebook,
                    config=self.config,
                )
            except Exception as e:
                logger.warning(f"Merchandise Auth tab failed to load: {e}")

    def _create_hardware_controls_tab(self):
        """Create Hardware Controls tab for LEDs, arm, vacuum, etc."""
        # Use the modular HardwareControlsTab component
        self.hardware_controls_tab = HardwareControlsTab(
            notebook=self.notebook,
            config=self.config
        )

    def _create_ai_training_tab(self):
        """Create AI Training tab - Monitor and control RL training"""
        if not AI_TRAINING_AVAILABLE:
            # Create placeholder tab
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text="🤖 AI Training")
            
            tk.Label(
                tab,
                text="🤖 AI Training (Requires matplotlib)\n\n"
                     "Install matplotlib to enable AI training visualization:\n"
                     "pip install matplotlib",
                font=('Segoe UI', 12),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_dark,
                justify='center'
            ).pack(expand=True)
            return

        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🤖 AI Training")
        
        # Use the modular AITrainingTab component
        self.ai_training_tab = AITrainingTab(parent=tab)

    def _create_deck_builder_tab(self):
        """Create Deck Builder tab - AI-powered deck construction"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="\ud83c\udccf Deck Builder")
        
        # Use the modular DeckBuilderTab component with Shop Personality
        self.deck_builder_tab = DeckBuilderTab(
            parent=tab,
            library=self.library,
            scryfall_db=self.scryfall_db,
            theme=self.theme,
            colors=self.colors,
            shop_personality=self.shop_personality  # Patent Claim 4
        )
    
    def _create_sales_tab(self):
        """Create Sales tab - Vendor store management"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="\ud83c\udfea Sales")
        
        # Use the modular SalesTab component with Shop Personality
        self.sales_tab = SalesTab(
            parent=tab,
            library=self.library,
            theme=self.theme,
            colors=self.colors,
            shop_personality=self.shop_personality  # Patent Claim 4
        )
        
    def _create_analytics_tab(self):
        """Create Analytics tab - AI insights and meta analysis"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="\ud83d\udcca Analytics")
        
        # Use the modular AnalyticsTab component with shop personality
        self.analytics_tab = AnalyticsTab(
            parent=tab,
            library=self.library,
            theme=self.theme,
            colors=self.colors,
            shop_personality=self.shop_personality
        )
        
    def _create_settings_tab(self):
        """Create Settings tab with Shop Personality"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="\u2699\ufe0f Settings")
        
        # Create scrollable frame
        canvas = tk.Canvas(tab, bg=self.colors.bg_dark, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=self.colors.bg_dark)
        
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling - bind/unbind on enter/leave
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _bind_wheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_wheel(event):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # ========================================
        # GAME MODE SECTION - Magic/Pokemon Toggle
        # ========================================
        game_frame = tk.LabelFrame(
            scrollable,
            text="\ud83c\udfb4 Trading Card Game Mode",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        game_frame.pack(fill='x', padx=20, pady=10)
        
        # Current game mode
        current_game = self.config.game.active_game if hasattr(self.config, 'game') else "magic"
        self.game_mode_var = tk.StringVar(value=current_game)
        
        game_info = tk.Frame(game_frame, bg=self.colors.bg_surface)
        game_info.pack(fill='x', pady=5)
        
        tk.Label(
            game_info,
            text="Active Game Mode:",
            font=('Segoe UI', 10),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        ).pack(side='left')
        
        # Radio buttons for game mode
        mode_frame = tk.Frame(game_frame, bg=self.colors.bg_surface)
        mode_frame.pack(fill='x', pady=10)
        
        # Magic option
        magic_rb = tk.Radiobutton(
            mode_frame,
            text="\ud83e\uddd9 Magic: The Gathering (Scryfall)",
            variable=self.game_mode_var,
            value="magic",
            font=('Segoe UI', 11),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface,
            activebackground=self.colors.bg_surface,
            selectcolor=self.colors.bg_dark,
            command=lambda: self._switch_game_mode("magic")
        )
        magic_rb.pack(anchor='w', pady=5)
        
        # Pokemon option
        pokemon_rb = tk.Radiobutton(
            mode_frame,
            text="\u26a1 Pokemon TCG (Pokemon TCG API)",
            variable=self.game_mode_var,
            value="pokemon",
            font=('Segoe UI', 11),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface,
            activebackground=self.colors.bg_surface,
            selectcolor=self.colors.bg_dark,
            command=lambda: self._switch_game_mode("pokemon")
        )
        pokemon_rb.pack(anchor='w', pady=5)
        
        # Note about separate libraries
        note_frame = tk.Frame(game_frame, bg=self.colors.bg_dark, padx=10, pady=8)
        note_frame.pack(fill='x', pady=(10, 0))
        
        tk.Label(
            note_frame,
            text="\u2139\ufe0f Each game has its own library. Cards can share physical box locations.",
            font=('Segoe UI', 9),
            fg=self.colors.text_muted,
            bg=self.colors.bg_dark,
            wraplength=450
        ).pack(anchor='w')
        
        # Shop Personality Section (Patent Claim 4)
        personality_frame = tk.LabelFrame(
            scrollable,
            text="\ud83e\uddec Adaptive Shop Personality (Patent Claim 4)",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        personality_frame.pack(fill='x', padx=20, pady=10)
        
        if self.shop_personality:
            profile = self.shop_personality.personality

            # Adaptation status
            status_frame = tk.Frame(personality_frame, bg=self.colors.bg_surface)
            status_frame.pack(fill='x', pady=5)

            tk.Label(
                status_frame,
                text=f"Shop: {self.shop_personality.shop_name}",
                font=('Segoe UI', 11, 'bold'),
                fg=self.colors.text_primary,
                bg=self.colors.bg_surface
            ).pack(anchor='w')

            tk.Label(
                status_frame,
                text=f"Status: {self.shop_personality.get_adaptation_level()}",
                font=('Segoe UI', 10),
                fg=self.colors.success if profile.get('days_active', 0) >= 30 else self.colors.warning,
                bg=self.colors.bg_surface
            ).pack(anchor='w')

            tk.Label(
                status_frame,
                text=f"Days Active: {profile.get('days_active', 0)} | Confidence: {profile.get('confidence_score', 0)*100:.0f}%",
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface
            ).pack(anchor='w')

            # Shop profile details
            details_frame = tk.Frame(personality_frame, bg=self.colors.bg_surface)
            details_frame.pack(fill='x', pady=10)

            details = [
                ("Top Format", profile.get('top_format', 'N/A')),
                ("Customer Type", profile.get('customer_type', 'mixed').title()),
                ("Price Positioning", profile.get('price_positioning', 'competitive').title()),
                ("Target Margin", f"{profile.get('target_margin', 0.3)*100:.0f}%"),
                ("Primary Revenue", profile.get('primary_revenue_source', 'singles').title()),
                ("Online Sales", f"{profile.get('online_sales_ratio', 0.2)*100:.0f}%"),
            ]
            
            for i, (label, value) in enumerate(details):
                row = tk.Frame(details_frame, bg=self.colors.bg_surface)
                row.pack(fill='x', pady=2)
                
                tk.Label(
                    row,
                    text=f"{label}:",
                    font=('Segoe UI', 10),
                    fg=self.colors.text_secondary,
                    bg=self.colors.bg_surface,
                    width=15,
                    anchor='w'
                ).pack(side='left')
                
                tk.Label(
                    row,
                    text=value,
                    font=('Segoe UI', 10, 'bold'),
                    fg=self.colors.text_primary,
                    bg=self.colors.bg_surface
                ).pack(side='left')
            
            # UI Recommendations
            if self.ui_recommendations:
                recs_frame = tk.LabelFrame(
                    personality_frame,
                    text="UI Recommendations",
                    font=('Segoe UI', 10),
                    fg=self.colors.text_secondary,
                    bg=self.colors.bg_surface,
                    padx=10,
                    pady=10
                )
                recs_frame.pack(fill='x', pady=10)
                
                # Analytics focus
                analytics_focus = self.ui_recommendations.get('analytics_focus', [])
                if analytics_focus:
                    tk.Label(
                        recs_frame,
                        text=f"Focus: {', '.join(analytics_focus[:3])}",
                        font=('Segoe UI', 9),
                        fg=self.colors.text_primary,
                        bg=self.colors.bg_surface,
                        wraplength=400
                    ).pack(anchor='w')

                # Hidden features
                hidden_features = self.ui_recommendations.get('hidden_features', [])
                if hidden_features:
                    tk.Label(
                        recs_frame,
                        text=f"Hidden: {', '.join(hidden_features[:3])}",
                        font=('Segoe UI', 9),
                        fg=self.colors.text_muted,
                        bg=self.colors.bg_surface
                    ).pack(anchor='w')
        else:
            tk.Label(
                personality_frame,
                text="Shop Personality not initialized",
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface
            ).pack()
        
        # Cross-Industry AI Section (Patent Claim 3)
        industry_frame = tk.LabelFrame(
            scrollable,
            text="\ud83c\udf10 Cross-Industry AI (Patent Claim 3)",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        industry_frame.pack(fill='x', padx=20, pady=10)
        
        if self.universal_ai:
            # Industry selector
            selector_frame = tk.Frame(industry_frame, bg=self.colors.bg_surface)
            selector_frame.pack(fill='x', pady=5)
            
            tk.Label(
                selector_frame,
                text="Active Industry:",
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface
            ).pack(side='left')
            
            # Industry dropdown
            self.industry_var = tk.StringVar(value=self.active_industry.value)
            industries = self.universal_ai.get_registered_industries()
            
            industry_dropdown = ttk.Combobox(
                selector_frame,
                textvariable=self.industry_var,
                values=industries,
                state='readonly',
                width=30
            )
            industry_dropdown.pack(side='left', padx=10)
            industry_dropdown.bind('<<ComboboxSelected>>', self._on_industry_change)
            
            # Status display
            status_row = tk.Frame(industry_frame, bg=self.colors.bg_surface)
            status_row.pack(fill='x', pady=10)
            
            tk.Label(
                status_row,
                text=f"Registered Industries: {len(industries)}",
                font=('Segoe UI', 10, 'bold'),
                fg=self.colors.success,
                bg=self.colors.bg_surface
            ).pack(anchor='w')
            
            # List industries
            for ind in industries[:5]:
                tk.Label(
                    status_row,
                    text=f"  \u2705 {ind}",
                    font=('Segoe UI', 9),
                    fg=self.colors.text_primary,
                    bg=self.colors.bg_surface
                ).pack(anchor='w')
            
            if len(industries) > 5:
                tk.Label(
                    status_row,
                    text=f"  ... and {len(industries) - 5} more",
                    font=('Segoe UI', 9),
                    fg=self.colors.text_muted,
                    bg=self.colors.bg_surface
                ).pack(anchor='w')
            
            # Cross-Industry Insights
            insights_frame = tk.LabelFrame(
                industry_frame,
                text="\ud83e\udde0 Universal Insights",
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface,
                padx=10,
                pady=10
            )
            insights_frame.pack(fill='x', pady=10)
            
            # Get insights for active industry
            insights = self.universal_ai.get_applicable_insights(self.active_industry)
            
            tk.Label(
                insights_frame,
                text=f"Insights applicable to {self.active_industry.value}: {len(insights)}",
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors.text_primary,
                bg=self.colors.bg_surface
            ).pack(anchor='w')
            
            for insight in insights[:3]:
                desc = insight.get('description', '')[:60]
                tk.Label(
                    insights_frame,
                    text=f"  \ud83d\udca1 {desc}...",
                    font=('Segoe UI', 9),
                    fg=self.colors.text_secondary,
                    bg=self.colors.bg_surface
                ).pack(anchor='w')
        else:
            tk.Label(
                industry_frame,
                text="Cross-Industry AI not initialized",
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface
            ).pack()
        
        # Shop Intelligence Section (Patent Claim 9)
        intelligence_frame = tk.LabelFrame(
            scrollable,
            text="\ud83c\udfea Shop Intelligence AI (Patent Claim 9)",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        intelligence_frame.pack(fill='x', padx=20, pady=10)
        
        if self.shop_intelligence:
            # Profitability Overview
            report = self.shop_intelligence.get_profitability_report()
            
            profit_frame = tk.Frame(intelligence_frame, bg=self.colors.bg_surface)
            profit_frame.pack(fill='x', pady=5)
            
            tk.Label(
                profit_frame,
                text="\ud83d\udcbc Financial Overview",
                font=('Segoe UI', 11, 'bold'),
                fg=self.colors.text_primary,
                bg=self.colors.bg_surface
            ).pack(anchor='w')
            
            metrics = [
                ("Inventory Value", f"${report['inventory_value']:,.2f}"),
                ("Total Revenue", f"${report['total_revenue']:,.2f}"),
                ("Profit Margin", f"{report['profit_margin']:.1f}%"),
                ("Customers", f"{report['customer_count']:,}"),
                ("VIP/Whale", f"{report['vip_count']:,}"),
            ]
            
            for label, value in metrics:
                row = tk.Frame(profit_frame, bg=self.colors.bg_surface)
                row.pack(fill='x', pady=2)
                
                tk.Label(
                    row,
                    text=f"  {label}:",
                    font=('Segoe UI', 9),
                    fg=self.colors.text_secondary,
                    bg=self.colors.bg_surface,
                    width=15,
                    anchor='w'
                ).pack(side='left')
                
                tk.Label(
                    row,
                    text=value,
                    font=('Segoe UI', 9, 'bold'),
                    fg=self.colors.success if 'Profit' in label else self.colors.text_primary,
                    bg=self.colors.bg_surface
                ).pack(side='left')
            
            # Hot Sellers
            insights = self.shop_intelligence.get_inventory_insights()
            
            if insights.hot_sellers:
                hot_frame = tk.LabelFrame(
                    intelligence_frame,
                    text="\ud83d\udd25 Hot Sellers",
                    font=('Segoe UI', 10),
                    fg=self.colors.text_secondary,
                    bg=self.colors.bg_surface,
                    padx=10,
                    pady=10
                )
                hot_frame.pack(fill='x', pady=10)
                
                for card in insights.hot_sellers[:3]:
                    margin_pct = card.profit_margin * 100 if card.profit_margin else 0
                    tk.Label(
                        hot_frame,
                        text=f"  \ud83c\udfc6 {card.card_name} - Margin: {margin_pct:.0f}%",
                        font=('Segoe UI', 9),
                        fg=self.colors.text_primary,
                        bg=self.colors.bg_surface
                    ).pack(anchor='w')
            
            # Restock Needed
            if insights.restock_needed:
                restock_frame = tk.LabelFrame(
                    intelligence_frame,
                    text="\ud83d\udce6 Restock Needed",
                    font=('Segoe UI', 10),
                    fg=self.colors.warning,
                    bg=self.colors.bg_surface,
                    padx=10,
                    pady=10
                )
                restock_frame.pack(fill='x', pady=10)
                
                for card in insights.restock_needed[:3]:
                    tk.Label(
                        restock_frame,
                        text=f"  \u26a0\ufe0f {card.card_name} - {card.quantity_on_hand}/{card.optimal_stock_level}",
                        font=('Segoe UI', 9),
                        fg=self.colors.warning,
                        bg=self.colors.bg_surface
                    ).pack(anchor='w')
        else:
            tk.Label(
                intelligence_frame,
                text="Shop Intelligence AI not initialized",
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface
            ).pack()
        
        # Other Settings
        other_frame = tk.LabelFrame(
            scrollable,
            text="General Settings",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        other_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(
            other_frame,
            text="Additional configuration options coming soon...",
            font=('Segoe UI', 10),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        ).pack(anchor='w')
    
    def _on_industry_change(self, event=None):
        """Handle industry selection change"""
        selected = self.industry_var.get()
        
        # Map display name back to enum
        for industry in CollectibleIndustry:
            if industry.value == selected:
                self.active_industry = industry
                logger.info(f"\ud83c\udf10 Active industry changed to: {selected}")
                self._update_status(f"Active Industry: {selected}")
                
                # Could refresh UI elements specific to the industry here
                break
    
    def _switch_game_mode(self, game: str):
        """Switch between Magic and Pokemon game modes"""
        from tkinter import messagebox
        
        current = self.config.game.active_game if hasattr(self.config, 'game') else "magic"
        if game == current:
            return  # Already on this mode
        
        game_names = {"magic": "Magic: The Gathering", "pokemon": "Pokemon TCG"}
        
        # Confirm switch
        if not messagebox.askyesno(
            "Switch Game Mode",
            f"Switch to {game_names[game]}?\
\
"
            f"This will load your {game_names[game]} collection.\
"
            f"Your {game_names[current]} collection will be preserved."
        ):
            # Reset the radio button to current value
            self.game_mode_var.set(current)
            return
        
        # Save to config
        self.config.game.active_game = game
        self.config.save()
        logger.info(f"\ud83c\udfb4 Game mode switched to: {game}")
        
        # Update status
        self._update_status(f"Game Mode: {game_names[game]}")
        
        # Notify user - full reload needed for library switch
        messagebox.showinfo(
            "Game Mode Changed",
            f"Now using {game_names[game]} mode.\
\
"
            f"Please restart NEXUS to load your {game_names[game]} library.\
\
"
            f"(Hot-reload coming in future update)"
        )
        
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = tk.Frame(self.main_frame, bg=self.colors.bg_surface, height=30)
        self.status_bar.pack(fill='x', side='bottom')
        self.status_bar.pack_propagate(False)
        
        self.status_label = tk.Label(
            self.status_bar,
            text="Ready",
            font=('Segoe UI', 9),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        )
        self.status_label.pack(side='left', padx=10, pady=5)
        
        # Version
        tk.Label(
            self.status_bar,
            text=f"NEXUS V{self.config.version}",
            font=('Segoe UI', 9),
            fg=self.colors.text_muted,
            bg=self.colors.bg_surface
        ).pack(side='right', padx=10, pady=5)
        
    # NOTE: _load_collection_data and _search_collection removed - now handled by CollectionTab
        
    def _update_status(self, message: str):
        """Update status bar"""
        self.status_label.config(text=message)
        
    def _finalize(self):
        """Finalize app setup"""
        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        # Register window close handler to properly cleanup resources
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        """Handle window close - cleanup all resources before exiting"""
        logger.info("Closing NEXUS V3...")

        # Call cleanup on all tabs that have the method
        tabs_to_cleanup = [
            'scanner_tab',
            'hardware_controls_tab',
            'collection_tab',
            'ai_training_tab'
        ]

        for tab_name in tabs_to_cleanup:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'cleanup'):
                    try:
                        logger.info(f"Cleaning up {tab_name}...")
                        tab.cleanup()
                    except Exception as e:
                        logger.error(f"Error cleaning up {tab_name}: {e}")

        # Destroy window
        self.root.destroy()

    def run(self):
        """Start the application main loop"""
        # Check license and show login if needed
        try:
            from ..portal import is_licensed
            from ..portal.login_dialog import show_login_dialog, check_and_prompt_updates

            if not is_licensed():
                # Show login dialog on first run
                logger.info("No license found - showing login dialog")
                show_login_dialog(self.root)
            else:
                # Check for updates if licensed
                logger.info("License valid - checking for updates")
                check_and_prompt_updates(self.root)
        except ImportError as e:
            logger.warning(f"Portal not available: {e}")
        except Exception as e:
            logger.error(f"Portal error: {e}")

        self.root.mainloop()
        