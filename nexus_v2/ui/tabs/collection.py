"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    COLLECTION TAB - NEXUS V2                                  ║
║                                                                               ║
║   Enhanced collection manager with:                                           ║
║   - Grouped inventory display (batched by name/set/number/foil)              ║
║   - Hover-to-show-image tooltip                                              ║
║   - Foil cards separated (different prices)                                  ║
║   - Call sign ranges display                                                  ║
║   - Scryfall price integration                                               ║
║   - Filter/sort dropdowns                                                     ║
║   - Pagination for performance                                               ║
║                                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading
import urllib.request
import re
from io import BytesIO
from PIL import Image, ImageTk
import os
import csv

# Import price consensus engine for BFT pricing
try:
    from nexus_v2.library.price_consensus import PriceConsensus
    PRICE_CONSENSUS_AVAILABLE = True
except ImportError:
    PRICE_CONSENSUS_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS AND DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

class SortColumn(Enum):
    NAME = "name"
    SET = "set"
    RARITY = "rarity"
    PRICE = "price"
    BOX = "box"
    QTY = "qty"
    FOIL = "foil"
    DATE_ADDED = "date_added"


class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass
class FilterState:
    """Current filter/sort state"""
    search: str = ""
    card_type: str = ""  # "All" = no filter, "mtg", "pokemon", "yugioh"
    set_code: str = ""  # "All" = no filter
    rarity: str = ""    # "All" = no filter
    color: str = ""     # "All" = no filter
    box: str = ""       # "All" = no filter
    foil_filter: str = ""  # "All", "Foil Only", "Non-Foil Only"
    show_listed_only: bool = False  # Show only cards listed for sale
    sort_column: SortColumn = SortColumn.NAME
    sort_order: SortOrder = SortOrder.ASC
    page: int = 1
    per_page: int = 100


@dataclass
class GroupedCard:
    """Represents a group of identical physical cards for display"""
    name: str
    set_code: str
    set_name: str
    collector_number: str
    rarity: str
    colors: List[str]
    mana_cost: str
    type_line: str
    foil: bool  # KEY CHANGE: Foil is part of grouping key

    quantity: int
    call_signs: List[str]
    purchase_prices: List[float]
    boxes: List[str]

    # From Scryfall
    market_value: Optional[float] = None  # Per-card market value
    image_uri: Optional[str] = None
    scryfall_id: Optional[str] = None

    # From database
    db_price: Optional[float] = None  # Price stored in DB

    # Card type identification (mtg, pokemon, yugioh)
    card_type: str = "mtg"

    # Yu-Gi-Oh! specific fields (Optional)
    yugioh_type: Optional[str] = None      # Normal Monster, Effect Monster, Spell Card, Trap Card
    yugioh_race: Optional[str] = None      # Spellcaster, Dragon, Warrior, etc.
    yugioh_attribute: Optional[str] = None  # DARK, LIGHT, EARTH, FIRE, WATER, WIND
    yugioh_atk: Optional[int] = None       # Attack points
    yugioh_def: Optional[int] = None       # Defense points
    yugioh_level: Optional[int] = None     # Level/Rank

    # Pokemon TCG specific fields (Optional)
    pokemon_hp: Optional[int] = None           # Hit points
    pokemon_types: Optional[List[str]] = None  # Fire, Water, Grass, etc.
    pokemon_weakness: Optional[str] = None     # Weakness type
    pokemon_resistance: Optional[str] = None   # Resistance type
    pokemon_retreat_cost: Optional[int] = None # Retreat cost (energy count)
    pokemon_stage: Optional[str] = None        # Basic, Stage 1, Stage 2, etc.

    @property
    def price_confidence(self) -> str:
        """
        Byzantine Fault Tolerance style price confidence.
        Multiple sources must agree for high confidence.

        Sources: Scryfall (market_value), DB (db_price)
        - HIGH: 2+ sources agree within 15%
        - MED: 1 source available
        - LOW: No price data or sources disagree >30%
        """
        sources = []
        if self.market_value and self.market_value > 0:
            sources.append(self.market_value)
        if self.db_price and self.db_price > 0:
            sources.append(self.db_price)

        if len(sources) == 0:
            return "LOW"
        elif len(sources) == 1:
            return "MED"  # Single source - medium confidence
        else:
            # BFT: Check if sources agree (within 15%)
            avg = sum(sources) / len(sources)
            max_diff = max(abs(p - avg) / avg for p in sources) if avg > 0 else 1

            if max_diff <= 0.15:
                return "HIGH"  # Sources agree within 15%
            elif max_diff <= 0.30:
                return "MED"   # Sources within 30%
            else:
                return "LOW"   # Sources disagree >30%

    @property
    def price_confidence_symbol(self) -> str:
        """Symbol for BFT price confidence display"""
        conf = self.price_confidence
        if conf == "HIGH":
            return "[H]"  # High - sources agree
        elif conf == "MED":
            return "[M]"  # Medium - single source or slight diff
        else:
            return "[L]"  # Low - no data or sources disagree

    @property
    def avg_purchase_price(self) -> float:
        if not self.purchase_prices:
            return 0.0
        return sum(self.purchase_prices) / len(self.purchase_prices)
    
    @property
    def total_value(self) -> float:
        if self.market_value:
            return self.market_value * self.quantity
        elif self.db_price:
            return self.db_price * self.quantity
        return 0.0
    
    @property
    def call_sign_display(self) -> str:
        """Format call signs as ranges: AA0001-AA0004, AA0087-AA0088"""
        if not self.call_signs:
            return ""
        
        if len(self.call_signs) == 1:
            return self.call_signs[0]
        
        # Sort call signs
        sorted_signs = sorted(self.call_signs)
        
        ranges = []
        range_start = sorted_signs[0]
        range_end = sorted_signs[0]
        
        for i in range(1, len(sorted_signs)):
            if self._is_consecutive(range_end, sorted_signs[i]):
                range_end = sorted_signs[i]
            else:
                if range_start == range_end:
                    ranges.append(range_start)
                else:
                    ranges.append(f"{range_start}-{range_end}")
                range_start = sorted_signs[i]
                range_end = sorted_signs[i]
        
        # Don't forget last range
        if range_start == range_end:
            ranges.append(range_start)
        else:
            ranges.append(f"{range_start}-{range_end}")
        
        return ", ".join(ranges)
    
    @staticmethod
    def _is_consecutive(sign1: str, sign2: str) -> bool:
        """Check if two call signs are consecutive (AA0001, AA0002)"""
        if len(sign1) != 6 or len(sign2) != 6:
            return False
        
        prefix1, num1 = sign1[:2], int(sign1[2:])
        prefix2, num2 = sign2[:2], int(sign2[2:])
        
        # Same prefix, consecutive numbers
        if prefix1 == prefix2 and num2 == num1 + 1:
            return True
        
        # Handle rollover: AA9999 → AB0001
        if num1 == 9999 and num2 == 1:
            if prefix1[1] == 'Z':
                # AZ9999 → BA0001
                expected_prefix = chr(ord(prefix1[0]) + 1) + 'A'
            else:
                # AA9999 → AB0001
                expected_prefix = prefix1[0] + chr(ord(prefix1[1]) + 1)
            return prefix2 == expected_prefix
        
        return False
    
    @property
    def box_display(self) -> str:
        """Format boxes list"""
        unique_boxes = list(set(self.boxes))
        if len(unique_boxes) == 1:
            return unique_boxes[0] or "—"
        return f"{len(unique_boxes)} boxes"
    
    @property
    def foil_display(self) -> str:
        """Display foil indicator"""
        return "✨ Foil" if self.foil else ""

    @property
    def best_price(self) -> float:
        """
        Get best available price using BFT preference.
        Prefers Scryfall (live market) over DB cache.
        """
        if self.market_value and self.market_value > 0:
            return self.market_value
        elif self.db_price and self.db_price > 0:
            return self.db_price
        return 0.0

    @property
    def reference_price(self) -> float:
        """Third-party market reference price (TCGPlayer Mid via Scryfall). NEXUS does not determine prices."""
        return self.best_price


# ═══════════════════════════════════════════════════════════════════════════
# HOVER IMAGE TOOLTIP
# ═══════════════════════════════════════════════════════════════════════════

def _fix_scryfall_url(url: str) -> str:
    """Convert broken Scryfall API image URLs to working CDN URLs.

    Old format (400 error): https://api.scryfall.com/cards/{uuid}?format=image&version=normal
    New format (works):     https://cards.scryfall.io/normal/front/{c1}/{c2}/{uuid}.jpg
    """
    if not url:
        return url
    m = re.match(r'https?://api\.scryfall\.com/cards/([0-9a-f-]+)\?format=image&version=(\w+)', url)
    if m:
        uuid, version = m.group(1), m.group(2)
        return f"https://cards.scryfall.io/{version}/front/{uuid[0]}/{uuid[1]}/{uuid}.jpg"
    return url


class CardImageTooltip:
    """
    Tooltip that displays card image on hover.
    Caches images to avoid re-downloading.
    """

    def __init__(self, parent):
        self.parent = parent
        self.tooltip_window = None
        self.image_cache: Dict[str, ImageTk.PhotoImage] = {}
        self.current_image_uri = None
        self.loading = False

        # Image dimensions for tooltip
        self.max_width = 250
        self.max_height = 350
    
    def show(self, event, image_uri: str, card_name: str = ""):
        """Show tooltip with card image at mouse position"""
        if not image_uri:
            return
        
        # Don't re-show for same image
        if self.tooltip_window and self.current_image_uri == image_uri:
            return
        
        self.hide()
        self.current_image_uri = image_uri
        
        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self.parent)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_attributes("-topmost", True)
        
        # Position near mouse but not under it
        x = event.x_root + 20
        y = event.y_root + 10
        
        # Keep on screen
        screen_width = self.parent.winfo_screenwidth()
        screen_height = self.parent.winfo_screenheight()
        
        if x + self.max_width > screen_width:
            x = event.x_root - self.max_width - 20
        if y + self.max_height > screen_height:
            y = screen_height - self.max_height - 10
        
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Dark background
        frame = tk.Frame(self.tooltip_window, bg="#1a1a2e", relief="solid", bd=2)
        frame.pack(fill="both", expand=True)
        
        # Check cache
        if image_uri in self.image_cache:
            self._display_image(frame, self.image_cache[image_uri], card_name)
        else:
            # Show loading
            loading_label = tk.Label(
                frame, 
                text="Loading...", 
                bg="#1a1a2e", 
                fg="#ffffff",
                font=("Segoe UI", 12)
            )
            loading_label.pack(padx=10, pady=10)
            
            # Load image in background
            threading.Thread(
                target=self._load_image, 
                args=(image_uri, frame, card_name),
                daemon=True
            ).start()
    
    def _load_image(self, uri: str, frame: tk.Frame, card_name: str):
        """Load image from URL in background thread"""
        try:
            # Fix broken Scryfall API URLs → CDN URLs
            uri = _fix_scryfall_url(uri)

            # Download image with User-Agent to avoid blocks
            req = urllib.request.Request(uri, headers={'User-Agent': 'NEXUS-V2/1.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                image_data = response.read()
            
            # Open with PIL
            image = Image.open(BytesIO(image_data))
            
            # Resize to fit tooltip
            image.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage (must be done in main thread)
            def update_display():
                if self.tooltip_window and self.tooltip_window.winfo_exists():
                    photo = ImageTk.PhotoImage(image)
                    self.image_cache[uri] = photo
                    
                    # Clear loading label
                    for widget in frame.winfo_children():
                        widget.destroy()
                    
                    self._display_image(frame, photo, card_name)
            
            self.parent.after(0, update_display)
            
        except Exception as e:
            def show_error():
                if self.tooltip_window and self.tooltip_window.winfo_exists():
                    for widget in frame.winfo_children():
                        widget.destroy()
                    tk.Label(
                        frame,
                        text=f"Image load failed",
                        bg="#1a1a2e",
                        fg="#ff6b6b",
                        font=("Segoe UI", 11)
                    ).pack(padx=10, pady=10)
            
            self.parent.after(0, show_error)
    
    def _display_image(self, frame: tk.Frame, photo: ImageTk.PhotoImage, card_name: str):
        """Display the loaded image in tooltip"""
        # Card name label
        if card_name:
            name_label = tk.Label(
                frame,
                text=card_name,
                bg="#1a1a2e",
                fg="#00d4ff",
                font=("Segoe UI", 12, "bold")
            )
            name_label.pack(padx=5, pady=(5, 2))
        
        # Image label
        img_label = tk.Label(frame, image=photo, bg="#1a1a2e")
        img_label.image = photo  # Keep reference
        img_label.pack(padx=5, pady=5)
    
    def hide(self):
        """Hide the tooltip"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
        self.current_image_uri = None


# ═══════════════════════════════════════════════════════════════════════════
# COLLECTION TAB
# ═══════════════════════════════════════════════════════════════════════════

class CollectionTab:
    """
    Enhanced Collection Manager tab.
    
    Features:
    - Grouped display (name + set + collector_number + FOIL)
    - Hover-to-show-image
    - Foil/Non-foil separation with different prices
    - Filter dropdowns (Set, Rarity, Color, Box, Foil)
    - Sortable columns
    - Pagination
    - Call sign ranges
    """
    
    # Rarity sort order
    RARITY_ORDER = {
        'common': 0,
        'uncommon': 1,
        'rare': 2,
        'mythic': 3,
        'special': 4,
        'bonus': 5
    }
    
    # Color symbols for display (letters + diamond for colorless)
    COLOR_SYMBOLS = {
        'W': 'W',  # White
        'U': 'U',  # Blue
        'B': 'B',  # Black
        'R': 'R',  # Red
        'G': 'G',  # Green
    }
    
    # Rarity colors (bright for dark background)
    RARITY_COLORS = {
        'common': '#d4d4d4',     # Light gray (brighter)
        'uncommon': '#e0e0e0',   # Lighter gray
        'rare': '#ffd700',       # Gold
        'mythic': '#ff6b00',     # Orange
        'special': '#a78bfa',    # Purple (brighter)
        'bonus': '#22d3ee'       # Cyan (brighter)
    }
    
    def __init__(self, parent: ttk.Frame, library=None, scryfall_db=None):
        """
        Initialize Collection tab.
        
        Args:
            parent: Parent frame
            library: LibrarySystem instance for card data
            scryfall_db: ScryfallDatabase instance for prices/images
        """
        self.parent = parent
        self.library = library
        self.scryfall_db = scryfall_db

        # Price consensus engine for BFT pricing
        self.price_consensus = PriceConsensus() if PRICE_CONSENSUS_AVAILABLE else None

        # State
        self.filter_state = FilterState()
        self.all_cards: List[Dict] = []
        self.all_grouped_cards: List[GroupedCard] = []  # Cached groups (prices looked up once)
        self.grouped_cards: List[GroupedCard] = []      # Filtered groups for display
        self.displayed_cards: List[GroupedCard] = []
        self.total_pages = 1
        self.cached_total_value = 0.0
        self.cached_total_qty = 0
        
        # Image tooltip
        self.image_tooltip = CardImageTooltip(parent)
        
        # References to other tabs
        self.sales_tab = None
        self.parent_notebook = None

        # Track which item is hovered
        self.hovered_item = None
        
        # Debounce timer for search
        self.search_timer = None
        
        # Build UI
        self._build_ui()
        
        # Load initial data
        self.parent.after(100, self._load_all_cards)
    
    def _build_ui(self):
        """Build the collection tab UI"""
        
        # Configure parent grid
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(1, weight=1)
        
        # ─────────────────────────────────────────────────────────────
        # HEADER ROW
        # ─────────────────────────────────────────────────────────────
        header_frame = ttk.Frame(self.parent)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        ttk.Label(
            header_frame,
            text="📦 Collection Manager",
            font=("Segoe UI", 18, "bold")
        ).pack(side="left")

        self.stats_label = ttk.Label(
            header_frame,
            text="Loading...",
            font=("Segoe UI", 12)
        )
        self.stats_label.pack(side="right")
        
        # ─────────────────────────────────────────────────────────────
        # FILTER BAR
        # ─────────────────────────────────────────────────────────────
        filter_frame = ttk.LabelFrame(self.parent, text="Filters", padding=10)
        filter_frame.grid(row=0, column=0, sticky="new", padx=10, pady=5)
        
        # Row 1: Search + dropdowns
        row1 = ttk.Frame(filter_frame)
        row1.pack(fill="x", pady=(0, 5))
        
        # Search
        ttk.Label(row1, text="Search:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.search_entry = ttk.Entry(row1, textvariable=self.search_var, width=20)
        self.search_entry.pack(side="left", padx=(0, 10))

        # Card Type dropdown (MTG, Pokemon, Yu-Gi-Oh)
        ttk.Label(row1, text="Type:").pack(side="left", padx=(0, 5))
        self.card_type_var = tk.StringVar(value="All")
        self.card_type_combo = ttk.Combobox(
            row1,
            textvariable=self.card_type_var,
            width=10,
            state="readonly",
            values=["All", "MTG", "Pokemon", "Yu-Gi-Oh", "Sports"]
        )
        self.card_type_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.card_type_combo.pack(side="left", padx=(0, 10))

        # Set dropdown
        ttk.Label(row1, text="Set:").pack(side="left", padx=(0, 5))
        self.set_var = tk.StringVar(value="All")
        self.set_combo = ttk.Combobox(row1, textvariable=self.set_var, width=12, state="readonly")
        self.set_combo['values'] = ["All"]
        self.set_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.set_combo.pack(side="left", padx=(0, 15))
        
        # Rarity dropdown
        ttk.Label(row1, text="Rarity:").pack(side="left", padx=(0, 5))
        self.rarity_var = tk.StringVar(value="All")
        self.rarity_combo = ttk.Combobox(
            row1, 
            textvariable=self.rarity_var, 
            width=10, 
            state="readonly",
            values=["All", "Common", "Uncommon", "Rare", "Mythic"]
        )
        self.rarity_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.rarity_combo.pack(side="left", padx=(0, 15))
        
        # Color dropdown
        ttk.Label(row1, text="Color:").pack(side="left", padx=(0, 5))
        self.color_var = tk.StringVar(value="All")
        self.color_combo = ttk.Combobox(
            row1,
            textvariable=self.color_var,
            width=12,
            state="readonly",
            values=["All", "White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"]
        )
        self.color_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.color_combo.pack(side="left", padx=(0, 15))
        
        # Box dropdown
        ttk.Label(row1, text="Box:").pack(side="left", padx=(0, 5))
        self.box_var = tk.StringVar(value="All")
        self.box_combo = ttk.Combobox(row1, textvariable=self.box_var, width=12, state="readonly")
        self.box_combo['values'] = ["All"]
        self.box_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.box_combo.pack(side="left", padx=(0, 15))
        
        # Foil filter dropdown
        ttk.Label(row1, text="Foil:").pack(side="left", padx=(0, 5))
        self.foil_var = tk.StringVar(value="All")
        self.foil_combo = ttk.Combobox(
            row1,
            textvariable=self.foil_var,
            width=12,
            state="readonly",
            values=["All", "Foil Only", "Non-Foil Only"]
        )
        self.foil_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self.foil_combo.pack(side="left", padx=(0, 15))
        
        # Clear filters button
        ttk.Button(row1, text="Clear Filters", command=self._clear_filters).pack(side="left", padx=(0, 10))

        # Update prices button
        ttk.Button(row1, text="Update Prices", command=self._update_prices).pack(side="right")

        # Sync with Brok HDD button
        ttk.Button(row1, text="Sync DANIELSON", command=self._sync_with_danielson).pack(side="right", padx=(0, 10))

        # Import/Export CSV buttons
        ttk.Button(row1, text="CSV Template", command=self._download_template).pack(side="right", padx=(0, 10))
        ttk.Button(row1, text="Import CSV", command=self._import_csv).pack(side="right", padx=(0, 10))
        ttk.Button(row1, text="Export CSV", command=self._export_csv).pack(side="right", padx=(0, 10))

        # Push to Marketplace button
        ttk.Button(row1, text="Push to Marketplace", command=self._push_to_marketplace).pack(side="right", padx=(0, 10))
        
        # ─────────────────────────────────────────────────────────────
        # CARD LIST (TREEVIEW)
        # ─────────────────────────────────────────────────────────────
        list_frame = ttk.Frame(self.parent)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Columns: Name, Set, Rarity, Colors, Foil, Price, Box, Qty, Status, Call Signs
        columns = ("name", "set", "rarity", "colors", "foil", "price", "box", "qty", "status", "call_signs")
        
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        
        # Column configurations
        self.tree.heading("name", text="Name ▲", command=lambda: self._sort_by("name"))
        self.tree.heading("set", text="Set", command=lambda: self._sort_by("set"))
        self.tree.heading("rarity", text="Rarity", command=lambda: self._sort_by("rarity"))
        self.tree.heading("colors", text="Colors")
        self.tree.heading("foil", text="Foil", command=lambda: self._sort_by("foil"))
        self.tree.heading("price", text="Price", command=lambda: self._sort_by("price"))
        self.tree.heading("box", text="Box", command=lambda: self._sort_by("box"))
        self.tree.heading("qty", text="Qty", command=lambda: self._sort_by("qty"))
        self.tree.heading("status", text="Status")
        self.tree.heading("call_signs", text="Call Signs")
        
        self.tree.column("name", width=250, minwidth=150)
        self.tree.column("set", width=70, minwidth=50)
        self.tree.column("rarity", width=90, minwidth=70)
        self.tree.column("colors", width=80, minwidth=60)
        self.tree.column("foil", width=70, minwidth=50)
        self.tree.column("price", width=80, minwidth=60)
        self.tree.column("box", width=80, minwidth=60)
        self.tree.column("qty", width=50, minwidth=40)
        self.tree.column("status", width=70, minwidth=50)
        self.tree.column("call_signs", width=180, minwidth=100)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self.tree.yview_scroll(int(-1*(event.delta/120)), "units")
        self.tree.bind("<MouseWheel>", _on_mousewheel)
        
        # Rarity color tags
        for rarity, color in self.RARITY_COLORS.items():
            self.tree.tag_configure(rarity, foreground=color)
        
        # Foil tag - use cyan/turquoise for visibility (not gold which conflicts with rare)
        self.tree.tag_configure("foil", foreground="#00d4ff")

        # Price confidence tags
        self.tree.tag_configure("conf_high", foreground="#22c55e")  # Green
        self.tree.tag_configure("conf_med", foreground="#eab308")   # Yellow
        self.tree.tag_configure("conf_low", foreground="#ef4444")   # Red

        # Bind events
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Motion>", self._on_mouse_motion)
        self.tree.bind("<Leave>", self._on_mouse_leave)
        
        # ─────────────────────────────────────────────────────────────
        # PAGINATION BAR
        # ─────────────────────────────────────────────────────────────
        page_frame = ttk.Frame(self.parent)
        page_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        # Page info
        self.page_label = ttk.Label(page_frame, text="Page 1 of 1 (0 groups)")
        self.page_label.pack(side="left")
        
        # Navigation buttons
        nav_frame = ttk.Frame(page_frame)
        nav_frame.pack(side="left", padx=20)
        
        ttk.Button(nav_frame, text="⏮ First", width=8, command=self._first_page).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="◀ Prev", width=8, command=self._prev_page).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="Next ▶", width=8, command=self._next_page).pack(side="left", padx=2)
        ttk.Button(nav_frame, text="Last ⏭", width=8, command=self._last_page).pack(side="left", padx=2)
        
        # Per page selector
        ttk.Label(page_frame, text="Per page:").pack(side="left", padx=(20, 5))
        self.per_page_var = tk.StringVar(value="100")
        per_page_combo = ttk.Combobox(
            page_frame,
            textvariable=self.per_page_var,
            width=6,
            state="readonly",
            values=["50", "100", "250", "500", "1000"]
        )
        per_page_combo.bind("<<ComboboxSelected>>", self._on_per_page_change)
        per_page_combo.pack(side="left")
        
        # Total value display
        self.value_label = ttk.Label(page_frame, text="Total Value: $0.00", font=("Segoe UI", 12, "bold"))
        self.value_label.pack(side="right")
        
        # ─────────────────────────────────────────────────────────────
        # STATUS BAR
        # ─────────────────────────────────────────────────────────────
        status_frame = ttk.Frame(self.parent)
        status_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(side="left")
    
    # ═══════════════════════════════════════════════════════════════════
    # DATA LOADING
    # ═══════════════════════════════════════════════════════════════════

    def _fetch_from_danielson(self) -> list:
        """Fetch full card inventory from DANIELSON library API.
        Returns list of card dicts with all metadata (price, set, rarity, etc.)"""
        import requests
        DANIELSON_LIBRARY_URL = "http://192.168.1.219:5001/api/library/all"

        try:
            print("[DANIELSON] Fetching library from 192.168.1.219:5001...")
            r = requests.get(f"{DANIELSON_LIBRARY_URL}?raw=1", timeout=15)
            if r.status_code != 200:
                print(f"[DANIELSON] HTTP {r.status_code}")
                return []

            data = r.json()
            cards = data.get('cards', data.get('results', []))

            if not cards:
                print("[DANIELSON] No cards in response")
                return []

            # Normalize field names to what collection tab expects
            normalized = []
            for card in cards:
                # Colors come as string from SQLite - parse to list
                raw_colors = card.get('colors', '')
                if isinstance(raw_colors, str):
                    try:
                        import ast
                        colors_list = ast.literal_eval(raw_colors) if raw_colors else []
                    except:
                        colors_list = []
                else:
                    colors_list = raw_colors or []

                # Price - ensure float
                price = card.get('price')
                if price is not None:
                    try:
                        price = float(price)
                        if price == 0:
                            price = None
                    except:
                        price = None

                price_foil = card.get('price_foil')
                if price_foil is not None:
                    try:
                        price_foil = float(price_foil)
                        if price_foil == 0:
                            price_foil = None
                    except:
                        price_foil = None

                normalized.append({
                    'name': card.get('name', ''),
                    'set_code': (card.get('set_code') or card.get('set', '')),
                    'set_name': card.get('set_name', ''),
                    'collector_number': card.get('collector_number', ''),
                    'rarity': card.get('rarity', ''),
                    'colors': colors_list,
                    'mana_cost': card.get('mana_cost', ''),
                    'type_line': card.get('type_line', ''),
                    'foil': bool(card.get('foil', 0)),
                    'condition': card.get('condition', ''),
                    'price': price,
                    'price_foil': price_foil,
                    'image_url': card.get('image_url', ''),
                    'scryfall_id': card.get('scryfall_id', ''),
                    'call_number': card.get('call_number', ''),
                    'box_id': card.get('box_id', ''),
                })

            print(f"[DANIELSON] Loaded {len(normalized)} cards with full metadata")
            return normalized

        except requests.exceptions.ConnectionError:
            print("[DANIELSON] Connection refused - is danielson_server.py running on port 5001?")
            return []
        except Exception as e:
            print(f"[DANIELSON] Fetch error: {e}")
            return []

    def _load_all_cards(self):
        """Load all cards from DANIELSON API (primary) or local library (fallback)"""
        self._set_status("Loading collection from DANIELSON...")
        self.parent.update()

        try:
            # PRIMARY: Fetch from DANIELSON with full metadata
            self.all_cards = self._fetch_from_danielson()

            # FALLBACK: Local library if DANIELSON unreachable
            if not self.all_cards:
                self._set_status("DANIELSON unavailable, loading local data...")
                self.parent.update()
                if self.library:
                    self.all_cards = self.library.get_all_cards()
                else:
                    self.all_cards = []

            total_cards = len(self.all_cards)
            self._set_status(f"Grouping {total_cards} cards and fetching prices...")
            self.parent.update()

            # GROUP CARDS ONCE on load with progress updates
            # This ensures Scryfall lookup happens once per card, giving consistent prices
            self.all_grouped_cards = self._group_cards_with_progress(self.all_cards)

            # Calculate and cache total value ONCE
            self.cached_total_value = sum(g.total_value for g in self.all_grouped_cards)
            self.cached_total_qty = sum(g.quantity for g in self.all_grouped_cards)

            priced = sum(1 for g in self.all_grouped_cards if g.market_value or g.db_price)

            # Populate filter dropdowns
            self._populate_dropdowns()

            # Apply filters (now just filters pre-grouped data)
            self._apply_filters()

            self._set_status(f"Loaded {total_cards} cards | {len(self.all_grouped_cards)} groups | {priced} priced | ${self.cached_total_value:,.2f}")

        except Exception as e:
            self._set_status(f"Error loading: {e}")
            print(f"Collection load error: {e}")

    def _group_cards_with_progress(self, cards: List[Dict]) -> List[GroupedCard]:
        """Group cards with progress updates for large collections"""
        total = len(cards)
        update_interval = max(1, total // 20)  # Update every 5%

        groups: Dict[Tuple, GroupedCard] = {}

        for i, card in enumerate(cards):
            # Progress update
            if i % update_interval == 0:
                pct = int((i / total) * 100) if total > 0 else 0
                self._set_status(f"Processing cards... {pct}% ({i}/{total})")
                self.parent.update()

            # Grouping key now includes foil status
            is_foil = card.get('foil', False)

            # Handle both 'set' and 'set_code' field names (Brock uses 'set')
            set_code = (card.get('set_code') or card.get('set', '')).upper()

            # Normalize name and collector_number for consistent grouping
            card_name = card.get('name', '').strip()
            collector_num = str(card.get('collector_number', '')).strip()

            # Use normalized values for consistent grouping
            key = (
                card_name.lower(),
                set_code,
                collector_num,
                is_foil
            )

            if key not in groups:
                # Get price and missing data from Scryfall
                market_value = None
                image_uri = None
                rarity = card.get('rarity', '')
                colors = card.get('colors', [])
                set_name = card.get('set_name', '')
                type_line = card.get('type_line', '')
                mana_cost = card.get('mana_cost', '')

                # Try Scryfall lookup
                if self.scryfall_db:
                    scryfall_card = self.scryfall_db.get_card(
                        card.get('name', ''),
                        set_code,
                        card.get('collector_number', '')
                    )
                    if scryfall_card:
                        prices = scryfall_card.get('prices', {})
                        if is_foil:
                            market_value = prices.get('usd_foil')
                        else:
                            market_value = prices.get('usd')

                        if market_value and isinstance(market_value, str):
                            try:
                                market_value = float(market_value)
                            except ValueError:
                                market_value = None

                        image_uris = scryfall_card.get('image_uris', {})
                        if image_uris:
                            image_uri = image_uris.get('normal')

                        if not rarity:
                            rarity = scryfall_card.get('rarity', '')
                        if not colors:
                            colors = scryfall_card.get('colors', [])
                        if not set_name:
                            set_name = scryfall_card.get('set_name', '')
                        if not type_line:
                            type_line = scryfall_card.get('type_line', '')
                        if not mana_cost:
                            mana_cost = scryfall_card.get('mana_cost', '')

                if image_uri is None:
                    image_uri = card.get('image_url')

                # Fix broken Scryfall API redirect URLs → CDN
                if image_uri:
                    image_uri = _fix_scryfall_url(image_uri)

                db_price = None
                if is_foil and card.get('price_foil'):
                    db_price = card.get('price_foil')
                elif card.get('price'):
                    db_price = card.get('price')

                groups[key] = GroupedCard(
                    name=card_name,
                    set_code=set_code,
                    set_name=set_name,
                    collector_number=collector_num,
                    rarity=rarity,
                    colors=colors,
                    mana_cost=mana_cost,
                    type_line=type_line,
                    foil=is_foil,
                    quantity=0,
                    call_signs=[],
                    purchase_prices=[],
                    boxes=[],
                    market_value=market_value,
                    image_uri=image_uri,
                    scryfall_id=card.get('scryfall_id'),
                    db_price=db_price
                )

            group = groups[key]
            group.quantity += 1

            call_sign = card.get('call_sign') or card.get('call_number')
            if call_sign:
                group.call_signs.append(call_sign)

            if card.get('purchase_price'):
                group.purchase_prices.append(card['purchase_price'])

            box_id = card.get('box_id', '')
            if box_id and box_id not in group.boxes:
                group.boxes.append(box_id)

        self._set_status(f"Finalizing {len(groups)} groups...")
        self.parent.update()

        return list(groups.values())
    
    def _populate_dropdowns(self):
        """Populate filter dropdowns from data"""
        sets = set()
        boxes = set()

        for card in self.all_cards:
            # Handle both 'set' and 'set_code' field names (Brock uses 'set')
            set_code = card.get('set_code') or card.get('set')
            if set_code:
                sets.add(set_code)
            if card.get('box_id'):
                boxes.add(card['box_id'])

        self.set_combo['values'] = ["All"] + sorted(sets)
        self.box_combo['values'] = ["All"] + sorted(boxes)
    
    # ═══════════════════════════════════════════════════════════════════
    # FILTERING AND GROUPING
    # ═══════════════════════════════════════════════════════════════════
    
    def _on_search_change(self, *args):
        """Handle search text change with debounce"""
        if self.search_timer:
            self.parent.after_cancel(self.search_timer)
        self.search_timer = self.parent.after(300, self._apply_filters)
    
    def _on_filter_change(self, event=None):
        """Handle dropdown filter change"""
        self._apply_filters()
    
    def _on_per_page_change(self, event=None):
        """Handle per-page change"""
        self.filter_state.per_page = int(self.per_page_var.get())
        self.filter_state.page = 1
        self._apply_filters()
    
    def _clear_filters(self):
        """Clear all filters"""
        self.search_var.set("")
        self.card_type_var.set("All")
        self.set_var.set("All")
        self.rarity_var.set("All")
        self.color_var.set("All")
        self.box_var.set("All")
        self.foil_var.set("All")
        self.filter_state = FilterState(per_page=int(self.per_page_var.get()))
        self._apply_filters()
    
    def _apply_filters(self):
        """Apply current filters to PRE-GROUPED cards, then paginate and display.

        FIXED: No longer re-groups cards on every filter/sort - uses cached groups
        from _load_all_cards() to ensure consistent pricing.
        """
        # Update filter state
        self.filter_state.search = self.search_var.get().strip().lower()
        # Map display names to internal card_type values
        card_type_map = {"MTG": "mtg", "Pokemon": "pokemon", "Yu-Gi-Oh": "yugioh", "Sports": "sports"}
        selected_type = self.card_type_var.get()
        self.filter_state.card_type = card_type_map.get(selected_type, "") if selected_type != "All" else ""
        self.filter_state.set_code = self.set_var.get() if self.set_var.get() != "All" else ""
        self.filter_state.rarity = self.rarity_var.get() if self.rarity_var.get() != "All" else ""
        self.filter_state.color = self.color_var.get() if self.color_var.get() != "All" else ""
        self.filter_state.box = self.box_var.get() if self.box_var.get() != "All" else ""
        self.filter_state.foil_filter = self.foil_var.get() if self.foil_var.get() != "All" else ""

        # Filter the PRE-GROUPED cards (not raw cards)
        # This ensures prices stay consistent because Scryfall lookup only happened once
        if not hasattr(self, 'all_grouped_cards'):
            self.all_grouped_cards = []

        filtered_groups = []
        for group in self.all_grouped_cards:
            # Card type filter (MTG, Pokemon, Yu-Gi-Oh, Sports)
            if self.filter_state.card_type:
                if group.card_type.lower() != self.filter_state.card_type.lower():
                    continue

            # Search filter
            if self.filter_state.search:
                if self.filter_state.search not in group.name.lower():
                    continue

            # Set filter
            if self.filter_state.set_code:
                if group.set_code.lower() != self.filter_state.set_code.lower():
                    continue

            # Rarity filter
            if self.filter_state.rarity:
                if group.rarity.lower() != self.filter_state.rarity.lower():
                    continue

            # Color filter
            if self.filter_state.color:
                colors = group.colors
                if self.filter_state.color == "Colorless":
                    if len(colors) > 0:
                        continue
                elif self.filter_state.color == "Multicolor":
                    if len(colors) <= 1:
                        continue
                else:
                    color_map = {'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'}
                    target_color = color_map.get(self.filter_state.color)
                    if target_color and target_color not in colors:
                        continue

            # Box filter (check if any card in group is in this box)
            if self.filter_state.box:
                if self.filter_state.box not in group.boxes:
                    continue

            # Foil filter
            if self.filter_state.foil_filter:
                if self.filter_state.foil_filter == "Foil Only" and not group.foil:
                    continue
                if self.filter_state.foil_filter == "Non-Foil Only" and group.foil:
                    continue

            filtered_groups.append(group)

        self.grouped_cards = filtered_groups
        
        # Sort
        self._sort_displayed_cards()
        
        # Paginate
        total_groups = len(self.grouped_cards)
        self.total_pages = max(1, (total_groups + self.filter_state.per_page - 1) // self.filter_state.per_page)
        
        if self.filter_state.page > self.total_pages:
            self.filter_state.page = self.total_pages
        
        start_idx = (self.filter_state.page - 1) * self.filter_state.per_page
        end_idx = start_idx + self.filter_state.per_page
        self.displayed_cards = self.grouped_cards[start_idx:end_idx]
        
        # Refresh display
        self._refresh_treeview()
        
        # Update labels
        self.page_label.config(
            text=f"Page {self.filter_state.page} of {self.total_pages} ({total_groups} groups)"
        )
        
        # Calculate totals for filtered view
        view_qty = sum(g.quantity for g in self.grouped_cards)
        view_value = sum(g.total_value for g in self.grouped_cards)

        # Use cached total for full collection (no filters)
        is_filtered = bool(self.filter_state.search or self.filter_state.card_type or
                          self.filter_state.set_code or self.filter_state.rarity or
                          self.filter_state.color or self.filter_state.box or
                          self.filter_state.foil_filter)

        # Show filtered value if filtering, else cached total
        display_value = view_value if is_filtered else getattr(self, 'cached_total_value', view_value)

        self.value_label.config(text=f"Total Value: ${display_value:,.2f}")
        self.stats_label.config(text=f"{len(self.all_cards)} cards | {view_qty} in view")
    
    def _group_cards(self, cards: List[Dict]) -> List[GroupedCard]:
        """
        Group cards by (name, set_code, collector_number, FOIL).

        Foil cards are now SEPARATE groups with different prices.
        """
        groups: Dict[Tuple, GroupedCard] = {}

        for card in cards:
            # Grouping key now includes foil status
            is_foil = card.get('foil', False)

            # Handle both 'set' and 'set_code' field names (Brock uses 'set')
            set_code = (card.get('set_code') or card.get('set', '')).upper()

            # Normalize name and collector_number for consistent grouping
            card_name = card.get('name', '').strip()
            collector_num = str(card.get('collector_number', '')).strip()

            # FIXED: Use normalized values for consistent grouping regardless of sort order
            key = (
                card_name.lower(),  # Case-insensitive name matching
                set_code,           # Already uppercased
                collector_num,
                is_foil
            )

            if key not in groups:
                # Get price and missing data from Scryfall (foil vs non-foil)
                market_value = None
                image_uri = None
                rarity = card.get('rarity', '')
                colors = card.get('colors', [])
                set_name = card.get('set_name', '')
                type_line = card.get('type_line', '')
                mana_cost = card.get('mana_cost', '')

                # Try Scryfall lookup to get missing data
                if self.scryfall_db:
                    scryfall_card = self.scryfall_db.get_card(
                        card.get('name', ''),
                        set_code,
                        card.get('collector_number', '')
                    )
                    if scryfall_card:
                        # Get price (foil vs non-foil)
                        prices = scryfall_card.get('prices', {})
                        if is_foil:
                            market_value = prices.get('usd_foil')
                        else:
                            market_value = prices.get('usd')

                        # Convert string price to float
                        if market_value and isinstance(market_value, str):
                            try:
                                market_value = float(market_value)
                            except ValueError:
                                market_value = None

                        # Get image
                        image_uris = scryfall_card.get('image_uris', {})
                        if image_uris:
                            image_uri = image_uris.get('normal')

                        # Fill in missing data from Scryfall
                        if not rarity:
                            rarity = scryfall_card.get('rarity', '')
                        if not colors:
                            colors = scryfall_card.get('colors', [])
                        if not set_name:
                            set_name = scryfall_card.get('set_name', '')
                        if not type_line:
                            type_line = scryfall_card.get('type_line', '')
                        if not mana_cost:
                            mana_cost = scryfall_card.get('mana_cost', '')

                # Fallback image URL from database
                if image_uri is None:
                    image_uri = card.get('image_url')

                # Get DB price (use foil price if foil card)
                db_price = None
                if is_foil and card.get('price_foil'):
                    db_price = card.get('price_foil')
                elif card.get('price'):
                    db_price = card.get('price')

                groups[key] = GroupedCard(
                    name=card_name,  # Use stripped name (original case for display)
                    set_code=set_code,  # Already uppercased
                    set_name=set_name,
                    collector_number=collector_num,  # Use normalized collector number
                    rarity=rarity,
                    colors=colors,
                    mana_cost=mana_cost,
                    type_line=type_line,
                    foil=is_foil,
                    quantity=0,
                    call_signs=[],
                    purchase_prices=[],
                    boxes=[],
                    market_value=market_value,
                    image_uri=image_uri,
                    scryfall_id=card.get('scryfall_id'),
                    db_price=db_price
                )

            group = groups[key]
            group.quantity += 1

            # Support both call_sign and call_number (database uses call_number)
            call_sign = card.get('call_sign') or card.get('call_number')
            if call_sign:
                group.call_signs.append(call_sign)

            if card.get('purchase_price') is not None:
                group.purchase_prices.append(card['purchase_price'])

            if card.get('box_id'):
                group.boxes.append(card['box_id'])

        return list(groups.values())
    
    # ═══════════════════════════════════════════════════════════════════
    # SORTING
    # ═══════════════════════════════════════════════════════════════════
    
    def _sort_by(self, column: str):
        """Sort by column, toggle order if same column"""
        column_map = {
            'name': SortColumn.NAME,
            'set': SortColumn.SET,
            'rarity': SortColumn.RARITY,
            'price': SortColumn.PRICE,
            'box': SortColumn.BOX,
            'qty': SortColumn.QTY,
            'foil': SortColumn.FOIL
        }
        
        new_column = column_map.get(column, SortColumn.NAME)
        
        if self.filter_state.sort_column == new_column:
            # Toggle order
            self.filter_state.sort_order = (
                SortOrder.DESC if self.filter_state.sort_order == SortOrder.ASC 
                else SortOrder.ASC
            )
        else:
            self.filter_state.sort_column = new_column
            self.filter_state.sort_order = SortOrder.ASC
        
        # Update header indicators
        self._update_sort_headers()
        
        # Re-apply filters (includes sort)
        self._apply_filters()
    
    def _update_sort_headers(self):
        """Update column header sort indicators"""
        columns = {
            'name': SortColumn.NAME,
            'set': SortColumn.SET,
            'rarity': SortColumn.RARITY,
            'price': SortColumn.PRICE,
            'box': SortColumn.BOX,
            'qty': SortColumn.QTY,
            'foil': SortColumn.FOIL
        }
        
        labels = {
            'name': 'Name',
            'set': 'Set',
            'rarity': 'Rarity',
            'price': 'Price',
            'box': 'Box',
            'qty': 'Qty',
            'foil': 'Foil'
        }
        
        for col, sort_col in columns.items():
            label = labels[col]
            if self.filter_state.sort_column == sort_col:
                arrow = "▲" if self.filter_state.sort_order == SortOrder.ASC else "▼"
                self.tree.heading(col, text=f"{label} {arrow}")
            else:
                self.tree.heading(col, text=label)
    
    def _sort_displayed_cards(self):
        """Sort grouped cards by current sort column/order"""
        reverse = self.filter_state.sort_order == SortOrder.DESC
        
        def sort_key(group: GroupedCard):
            if self.filter_state.sort_column == SortColumn.NAME:
                return group.name.lower()
            elif self.filter_state.sort_column == SortColumn.SET:
                return group.set_code.lower()
            elif self.filter_state.sort_column == SortColumn.RARITY:
                return self.RARITY_ORDER.get(group.rarity.lower(), 99)
            elif self.filter_state.sort_column == SortColumn.PRICE:
                return group.market_value or 0
            elif self.filter_state.sort_column == SortColumn.BOX:
                return group.box_display.lower()
            elif self.filter_state.sort_column == SortColumn.QTY:
                return group.quantity
            elif self.filter_state.sort_column == SortColumn.FOIL:
                return (0 if group.foil else 1, group.name.lower())
            else:
                return group.name.lower()
        
        self.grouped_cards.sort(key=sort_key, reverse=reverse)
    
    # ═══════════════════════════════════════════════════════════════════
    # DISPLAY
    # ═══════════════════════════════════════════════════════════════════
    
    def _refresh_treeview(self):
        """Refresh treeview with current displayed cards"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add cards
        for group in self.displayed_cards:
            # Format colors (letters: W, U, B, R, G or diamond for colorless)
            color_display = ''.join(self.COLOR_SYMBOLS.get(c, c) for c in group.colors)
            if not color_display:
                color_display = "<>"  # Colorless diamond

            # Format price with confidence indicator
            # [H]=High (Scryfall/TCG), [M]=Medium (DB), [L]=Low (none)
            if group.market_value:
                price_display = f"${group.market_value:.2f} [H]"
            elif group.db_price and group.db_price > 0:
                price_display = f"${group.db_price:.2f} [M]"
            else:
                price_display = "- [L]"

            # Foil display (plain text, color comes from tag)
            foil_display = "Foil" if group.foil else ""
            
            # Determine tags
            tags = []
            if group.rarity:
                tags.append(group.rarity.lower())
            if group.foil:
                tags.append("foil")
            
            # Check if listed for sale
            status_display = ""
            if self.sales_tab and hasattr(self.sales_tab, 'listed_items'):
                for listing in self.sales_tab.listed_items:
                    if listing.get('name') == group.name and listing.get('set_code') == group.set_code:
                        status_display = "📋 Listed"
                        break

            # Insert row
            item_id = self.tree.insert(
                "",
                "end",
                values=(
                    group.name,
                    group.set_code,
                    group.rarity.title() if group.rarity else "",
                    color_display,
                    foil_display,
                    price_display,
                    group.box_display,
                    group.quantity,
                    status_display,
                    group.call_sign_display
                ),
                tags=tuple(tags)
            )
            
            # Store reference for tooltip
            self.tree.set(item_id, "name", group.name)
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGINATION
    # ═══════════════════════════════════════════════════════════════════
    
    def _first_page(self):
        self.filter_state.page = 1
        self._apply_filters()
    
    def _prev_page(self):
        if self.filter_state.page > 1:
            self.filter_state.page -= 1
            self._apply_filters()
    
    def _next_page(self):
        if self.filter_state.page < self.total_pages:
            self.filter_state.page += 1
            self._apply_filters()
    
    def _last_page(self):
        self.filter_state.page = self.total_pages
        self._apply_filters()
    
    # ═══════════════════════════════════════════════════════════════════
    # HOVER / TOOLTIP
    # ═══════════════════════════════════════════════════════════════════
    
    def _on_mouse_motion(self, event):
        """Handle mouse motion for hover tooltip - only show on name column"""
        # Get item and column under cursor
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        # Only show tooltip when hovering over the name column (#1)
        if column != "#1":
            self.image_tooltip.hide()
            self.hovered_item = None
            return

        if item != self.hovered_item:
            self.hovered_item = item

            if item:
                # Get card data for this row
                idx = self.tree.index(item)
                if 0 <= idx < len(self.displayed_cards):
                    group = self.displayed_cards[idx]
                    if group.image_uri:
                        self.image_tooltip.show(event, group.image_uri, group.name)
                    else:
                        self.image_tooltip.hide()
            else:
                self.image_tooltip.hide()
    
    def _on_mouse_leave(self, event):
        """Handle mouse leaving treeview"""
        self.image_tooltip.hide()
        self.hovered_item = None
    
    # ═══════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════
    
    def _on_double_click(self, event):
        """Handle double-click on row"""
        item = self.tree.selection()
        if item:
            idx = self.tree.index(item[0])
            if 0 <= idx < len(self.displayed_cards):
                group = self.displayed_cards[idx]
                self._show_card_details(group)
    
    def _on_right_click(self, event):
        """Handle right-click context menu"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            
            menu = tk.Menu(self.parent, tearoff=0)
            menu.add_command(label="View Details", command=self._view_selected_details)
            menu.add_command(label="Copy Name", command=self._copy_selected_name)
            menu.add_separator()
            menu.add_command(label="Update Price", command=self._update_selected_price)
            menu.add_separator()

            # Display case submenu
            display_menu = tk.Menu(menu, tearoff=0)
            display_menu.add_command(label="Case 1", command=lambda: self._set_display_case(1))
            display_menu.add_command(label="Case 2", command=lambda: self._set_display_case(2))
            display_menu.add_command(label="Case 3", command=lambda: self._set_display_case(3))
            display_menu.add_command(label="Case 4", command=lambda: self._set_display_case(4))
            display_menu.add_command(label="Case 5", command=lambda: self._set_display_case(5))
            display_menu.add_command(label="Case 6", command=lambda: self._set_display_case(6))
            display_menu.add_separator()
            display_menu.add_command(label="Remove from Display", command=lambda: self._set_display_case(None))
            menu.add_cascade(label="Set Display Case", menu=display_menu)

            menu.add_separator()
            menu.add_command(label="List for Sale", command=self._list_for_sale)

            menu.post(event.x_root, event.y_root)
    
    def _view_selected_details(self):
        """View details for selected card"""
        item = self.tree.selection()
        if item:
            idx = self.tree.index(item[0])
            if 0 <= idx < len(self.displayed_cards):
                self._show_card_details(self.displayed_cards[idx])
    
    def _copy_selected_name(self):
        """Copy selected card name to clipboard"""
        item = self.tree.selection()
        if item:
            idx = self.tree.index(item[0])
            if 0 <= idx < len(self.displayed_cards):
                name = self.displayed_cards[idx].name
                self.parent.clipboard_clear()
                self.parent.clipboard_append(name)
    
    def _update_selected_price(self):
        """Update price for selected card"""
        # Placeholder - would fetch fresh price from Scryfall
        messagebox.showinfo("Update Price", "Price update coming soon!")

    def _set_display_case(self, case_number):
        """Set display case for selected card(s)"""
        item = self.tree.selection()
        if not item:
            return

        idx = self.tree.index(item[0])
        if 0 <= idx < len(self.displayed_cards):
            group = self.displayed_cards[idx]

            # Get the library's database
            if hasattr(self.library, 'db') and self.library.db:
                # Update all cards in this group
                updated = 0
                for call_sign in group.call_signs:
                    if self.library.db.set_display(call_sign, case_number is not None, case_number):
                        updated += 1

                if updated > 0:
                    if case_number:
                        messagebox.showinfo("Display Set",
                                          f"Added {group.name} ({updated} card(s)) to Case {case_number}")
                    else:
                        messagebox.showinfo("Display Removed",
                                          f"Removed {group.name} ({updated} card(s)) from display")
                else:
                    messagebox.showwarning("No Update", "Could not update display status")
            else:
                messagebox.showwarning("Database Required",
                                      "SQLite database required for display case tracking")

    def set_sales_tab(self, sales_tab):
        """Set reference to Sales tab for List for Sale functionality"""
        self.sales_tab = sales_tab

    def set_notebook(self, notebook):
        """Set reference to parent notebook for tab switching"""
        self.parent_notebook = notebook

    def _list_for_sale(self):
        """Navigate to Sales & Marketing page with selected card"""
        item = self.tree.selection()
        if not item:
            return

        idx = self.tree.index(item[0])
        if 0 <= idx < len(self.displayed_cards):
            group = self.displayed_cards[idx]

            # If we have references to sales tab and notebook, navigate there
            if self.sales_tab and self.parent_notebook:
                # Switch to Sales tab
                for i in range(self.parent_notebook.index('end')):
                    tab_name = self.parent_notebook.tab(i, 'text')
                    if 'Sales' in tab_name:
                        self.parent_notebook.select(i)
                        break

                # Tell sales tab to open listing for this card
                if hasattr(self.sales_tab, 'open_listing_for_card'):
                    self.sales_tab.open_listing_for_card(group)
            else:
                # Fallback to old dialog behavior
                self._show_listing_dialog(group)

    def _show_listing_dialog(self, group: GroupedCard):
        """Show dialog to create marketplace listing"""
        popup = tk.Toplevel(self.parent)
        popup.title(f"List for Sale - {group.name}")
        popup.geometry("450x500")
        popup.transient(self.parent)
        popup.grab_set()

        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill="both", expand=True)

        # Card info header
        ttk.Label(frame, text=group.name, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{group.set_name} ({group.set_code}) #{group.collector_number}",
                  foreground="gray").pack(anchor="w")
        if group.foil:
            ttk.Label(frame, text="FOIL", foreground="#FFD700").pack(anchor="w")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=15)

        # Price section
        price_frame = ttk.Frame(frame)
        price_frame.pack(fill="x", pady=5)

        ttk.Label(price_frame, text="Listing Price ($):").pack(side="left")
        price_var = tk.StringVar()

        # Default to market value if available
        default_price = group.market_value or group.db_price or 0.99
        price_var.set(f"{default_price:.2f}")

        price_entry = ttk.Entry(price_frame, textvariable=price_var, width=12)
        price_entry.pack(side="left", padx=10)

        if group.market_value:
            ttk.Label(price_frame, text=f"(Market: ${group.market_value:.2f})",
                      foreground="gray").pack(side="left")

        # Quantity section
        qty_frame = ttk.Frame(frame)
        qty_frame.pack(fill="x", pady=5)

        ttk.Label(qty_frame, text="Quantity to List:").pack(side="left")
        qty_var = tk.StringVar(value="1")
        qty_spin = ttk.Spinbox(qty_frame, from_=1, to=group.quantity, textvariable=qty_var, width=5)
        qty_spin.pack(side="left", padx=10)
        ttk.Label(qty_frame, text=f"(Have: {group.quantity})", foreground="gray").pack(side="left")

        # Condition dropdown
        cond_frame = ttk.Frame(frame)
        cond_frame.pack(fill="x", pady=5)

        ttk.Label(cond_frame, text="Condition:").pack(side="left")
        cond_var = tk.StringVar(value="NM")
        cond_combo = ttk.Combobox(cond_frame, textvariable=cond_var, width=15,
                                   values=["NM", "LP", "MP", "HP", "DMG"], state="readonly")
        cond_combo.pack(side="left", padx=10)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=15)

        # Status label
        status_var = tk.StringVar(value="")
        status_label = ttk.Label(frame, textvariable=status_var, foreground="gray")
        status_label.pack(anchor="w")

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=20)

        def do_list():
            try:
                price = float(price_var.get())
                qty = int(qty_var.get())
                condition = cond_var.get()

                if price <= 0:
                    messagebox.showerror("Invalid Price", "Price must be greater than $0")
                    return
                if qty < 1 or qty > group.quantity:
                    messagebox.showerror("Invalid Quantity", f"Quantity must be between 1 and {group.quantity}")
                    return

                status_var.set("Connecting to marketplace...")
                popup.update()

                # Try to use marketplace client
                try:
                    from nexus_v2.integrations.marketplace_client import MarketplaceClient
                    client = MarketplaceClient()

                    # Check if server is reachable
                    if not client.is_connected():
                        status_var.set("Marketplace offline")
                        messagebox.showerror("Marketplace Offline",
                                          f"Cannot connect to marketplace server.\n\n"
                                          f"Make sure server is running on 192.168.1.152:8000")
                        return

                    # Check if logged in
                    user = client.get_current_user()
                    if not user.get('user'):
                        # Try auto-login with config credentials
                        status_var.set("Logging in...")
                        popup.update()

                        try:
                            from nexus_v2.config.config_manager import config
                            mp_config = config.get_marketplace_config()
                            email = mp_config.get('email', 'nexus@local.shop')
                            password = mp_config.get('password', 'nexus2026')
                            shop_name = mp_config.get('shop_name', 'NEXUS Shop')
                        except Exception:
                            email = 'nexus@local.shop'
                            password = 'nexus2026'
                            shop_name = 'NEXUS Shop'

                        login_result = client.login(email, password)
                        if login_result.get('error'):
                            # Try to register as seller
                            status_var.set("Registering seller account...")
                            popup.update()
                            reg_result = client.register(
                                username=shop_name,
                                email=email,
                                password=password,
                                role='seller',
                                shop_name=shop_name
                            )
                            if reg_result.get('error'):
                                status_var.set("Login failed")
                                messagebox.showerror("Login Failed",
                                                  f"Could not login to marketplace.\n\n"
                                                  f"Error: {reg_result.get('error')}")
                                return

                    # Create listing on marketplace
                    status_var.set("Creating listing...")
                    popup.update()

                    result = client.create_listing(
                        card_name=group.name,
                        price=price,
                        quantity=qty,
                        condition=condition,
                        set_name=group.set_name,
                        set_code=group.set_code,
                        rarity=group.rarity,
                        foil=group.foil,
                        collector_number=group.collector_number,
                        image_url=group.image_uri,
                        scryfall_id=group.scryfall_id
                    )

                    if result.get('error'):
                        status_var.set(f"Error: {result['error']}")
                        messagebox.showerror("Listing Failed", result['error'])
                    else:
                        messagebox.showinfo("Listed on Marketplace!",
                                          f"Successfully listed {group.name} x{qty} for ${price:.2f}\n\n"
                                          f"View at: http://192.168.1.152:8000")
                        popup.destroy()

                except ImportError:
                    status_var.set("Missing library")
                    messagebox.showerror("Missing Library",
                                      f"Install 'requests' library:\n\npip install requests")

            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid price and quantity")

        ttk.Button(btn_frame, text="List for Sale", command=do_list).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side="left", padx=5)

    def _save_local_listing(self, group: GroupedCard, price: float, qty: int, condition: str):
        """Save listing locally for later sync"""
        import json
        from pathlib import Path

        listings_file = Path("pending_listings.json")
        listings = []

        if listings_file.exists():
            try:
                listings = json.loads(listings_file.read_text())
            except Exception:
                listings = []

        listings.append({
            'card_name': group.name,
            'price': price,
            'quantity': qty,
            'condition': condition,
            'set_name': group.set_name,
            'set_code': group.set_code,
            'rarity': group.rarity,
            'foil': group.foil,
            'collector_number': group.collector_number,
            'image_url': group.image_uri,
            'scryfall_id': group.scryfall_id,
            'created_at': datetime.now().isoformat()
        })

        listings_file.write_text(json.dumps(listings, indent=2))

    def _push_to_marketplace(self):
        """Push pending listings to Zultan marketplace server (port 5000)"""
        import json
        import threading
        from pathlib import Path

        listings_file = Path("pending_listings.json")

        # Check if we have pending listings
        if not listings_file.exists():
            messagebox.showinfo("No Pending Listings",
                              "No cards queued for marketplace.\n\nRight-click a card → 'List for Sale' to add cards.")
            return

        try:
            listings = json.loads(listings_file.read_text())
        except Exception as e:
            messagebox.showerror("Error", f"Could not read pending listings: {e}")
            return

        if not listings:
            messagebox.showinfo("No Pending Listings",
                              "No cards queued for marketplace.\n\nRight-click a card → 'List for Sale' to add cards.")
            return

        # Show confirmation
        total_value = sum(l.get('price', 0) * l.get('quantity', 1) for l in listings)
        confirm = messagebox.askyesno(
            "Push to Marketplace",
            f"Push {len(listings)} listing(s) to Zultan marketplace?\n\n"
            f"Total value: ${total_value:.2f}\n\n"
            "Server: http://192.168.1.152:8000"
        )

        if not confirm:
            return

        def do_push():
            try:
                from nexus_v2.integrations.marketplace_client import MarketplaceClient

                self._set_status("Connecting to Zultan marketplace...")

                # Use MarketplaceClient (Zultan on port 5000)
                client = MarketplaceClient()

                # Check connection
                if not client.is_connected():
                    self.parent.after(0, lambda: messagebox.showerror(
                        "Server Offline",
                        "Cannot connect to Zultan marketplace (192.168.1.152:8000)\n\n"
                        "Check if server is running."
                    ))
                    self._set_status("Marketplace offline")
                    return

                # Check if logged in
                user = client.get_current_user()
                if not user.get('user'):
                    # Try to login with default credentials
                    self._set_status("Logging in...")
                    try:
                        from nexus_v2.config.config_manager import config
                        mp_config = config.get_marketplace_config()
                        email = mp_config.get('email', 'nexus@local.shop')
                        password = mp_config.get('password', 'nexus2026')
                    except Exception:
                        email = 'nexus@local.shop'
                        password = 'nexus2026'

                    login_result = client.login(email, password)
                    if login_result.get('error'):
                        # Try register
                        self._set_status("Registering...")
                        reg_result = client.register(
                            username='NEXUS Shop',
                            email=email,
                            password=password,
                            role='seller',
                            shop_name='NEXUS Shop'
                        )
                        if reg_result.get('error'):
                            self.parent.after(0, lambda e=reg_result['error']: messagebox.showerror(
                                "Login Failed", f"Could not login or register:\n{e}"
                            ))
                            self._set_status("Login failed")
                            return

                self._set_status(f"Pushing {len(listings)} listings...")

                # Use bulk create
                result = client.bulk_create_listings(listings)

                success_count = result.get('success_count', 0)
                failed_count = result.get('failed_count', 0)

                if success_count > 0:
                    # Clear successful listings
                    if failed_count == 0:
                        listings_file.write_text("[]")
                    else:
                        # Keep failed ones
                        failed_names = [f['card'] for f in result.get('failed', [])]
                        remaining = [l for l in listings if l.get('card_name') in failed_names]
                        listings_file.write_text(json.dumps(remaining, indent=2))

                    self._set_status(f"Pushed {success_count} listings!")
                    msg = f"Successfully pushed {success_count} listings to marketplace!"
                    if failed_count > 0:
                        msg += f"\n\n{failed_count} failed (kept in queue)"
                    self.parent.after(0, lambda m=msg: messagebox.showinfo("Success!", m))
                else:
                    errors = result.get('failed', [])
                    error_msg = '\n'.join([f"{f['card']}: {f['error']}" for f in errors[:5]])
                    self._set_status("Push failed")
                    self.parent.after(0, lambda e=error_msg: messagebox.showerror(
                        "Push Failed", f"Could not create listings:\n{e}"
                    ))

            except ImportError as ie:
                self.parent.after(0, lambda: messagebox.showerror(
                    "Missing Library",
                    f"Install requests library:\npip install requests\n\n{ie}"
                ))
                self._set_status("Missing library")
            except Exception as ex:
                self._set_status(f"Push failed: {ex}")
                self.parent.after(0, lambda e=str(ex): messagebox.showerror(
                    "Push Failed", f"Error:\n{e}"
                ))

        threading.Thread(target=do_push, daemon=True).start()

    def _show_card_details(self, group: GroupedCard):
        """Show detailed card info popup"""
        popup = tk.Toplevel(self.parent)
        popup.title(f"Card Details - {group.name}")
        popup.geometry("500x600")
        popup.transient(self.parent)
        
        # Content
        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill="both", expand=True)
        
        # Card name
        ttk.Label(frame, text=group.name, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        
        # Set info
        ttk.Label(frame, text=f"{group.set_name} ({group.set_code}) #{group.collector_number}").pack(anchor="w")
        
        # Type line
        ttk.Label(frame, text=group.type_line, font=("Segoe UI", 12, "italic")).pack(anchor="w", pady=(5, 0))

        # Yu-Gi-Oh! specific attributes
        if hasattr(group, 'card_type') and group.card_type == "yugioh":
            yugioh_info = []
            if group.yugioh_attribute:
                yugioh_info.append(f"[{group.yugioh_attribute}]")
            if group.yugioh_level:
                yugioh_info.append(f"Level {group.yugioh_level}")
            if group.yugioh_race:
                yugioh_info.append(group.yugioh_race)
            if yugioh_info:
                ttk.Label(frame, text=" ".join(yugioh_info), font=("Segoe UI", 11)).pack(anchor="w")

            # ATK/DEF for monsters
            if group.yugioh_atk is not None:
                stats_text = f"ATK/{group.yugioh_atk}"
                if group.yugioh_def is not None:
                    stats_text += f"  DEF/{group.yugioh_def}"
                ttk.Label(frame, text=stats_text, font=("Segoe UI", 12, "bold")).pack(anchor="w")

        # Pokemon TCG specific attributes
        elif hasattr(group, 'card_type') and group.card_type == "pokemon":
            pokemon_info = []
            if group.pokemon_stage:
                pokemon_info.append(group.pokemon_stage)
            if group.pokemon_types:
                pokemon_info.append("/".join(group.pokemon_types))
            if pokemon_info:
                ttk.Label(frame, text=" - ".join(pokemon_info), font=("Segoe UI", 11)).pack(anchor="w")

            # HP and combat stats
            stats_parts = []
            if group.pokemon_hp is not None:
                stats_parts.append(f"HP {group.pokemon_hp}")
            if group.pokemon_weakness:
                stats_parts.append(f"Weak: {group.pokemon_weakness}")
            if group.pokemon_resistance:
                stats_parts.append(f"Resist: {group.pokemon_resistance}")
            if group.pokemon_retreat_cost is not None:
                stats_parts.append(f"Retreat: {group.pokemon_retreat_cost}")
            if stats_parts:
                ttk.Label(frame, text="  |  ".join(stats_parts), font=("Segoe UI", 12, "bold")).pack(anchor="w")

        # Separator
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        # Details grid
        details = [
            ("Rarity", group.rarity.title() if group.rarity else "—"),
            ("Foil", "Yes ✨" if group.foil else "No"),
            ("Quantity", str(group.quantity)),
            ("Market Value", f"${group.market_value:.2f}" if group.market_value else "—"),
            ("DB Price", f"${group.db_price:.2f}" if group.db_price else "—"),
            ("Best Price", f"${group.best_price:.2f}" if group.best_price > 0 else "—"),
            ("Confidence", f"{group.price_confidence} {group.price_confidence_symbol}"),
            ("Total Value", f"${group.total_value:.2f}" if group.total_value > 0 else "—"),
            ("Avg Purchase", f"${group.avg_purchase_price:.2f}" if group.purchase_prices else "—"),
            ("Call Signs", group.call_sign_display or "—"),
            ("Box(es)", group.box_display),
        ]

        # Add pricing recommendations section if we have price data
        if group.best_price > 0:
            details.append(("", ""))  # Spacer
            details.append(("— PRICING —", ""))

            # Use full consensus engine if available
            if self.price_consensus and group.scryfall_id:
                prices = {}
                if group.market_value and group.market_value > 0:
                    prices['scryfall'] = group.market_value
                if group.db_price and group.db_price > 0:
                    prices['db_cache'] = group.db_price

                if len(prices) >= 1:
                    result = self.price_consensus.calculate_consensus(
                        group.scryfall_id, prices
                    )
                    details.append(("Consensus", f"${result.consensus_price:.2f}"))
                    details.append(("Score", f"{result.confidence_score:.0f}%"))
                    if result.anomaly_detected:
                        details.append(("Alert", f"⚠️ {result.anomaly_type}"))
                    details.append(("Source", result.source_summary.split('.')[0]))
                else:
                    details.append(("TCGPlayer Mid", f"${group.reference_price:.2f}"))
                    details.append(("Source", "Scryfall/TCGPlayer"))
            else:
                details.append(("TCGPlayer Mid", f"${group.reference_price:.2f}"))
                details.append(("Source", "Scryfall/TCGPlayer"))
        
        for label, value in details:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label}:", font=("Segoe UI", 12, "bold"), width=15).pack(side="left")
            ttk.Label(row, text=value).pack(side="left")
        
        # Close button
        ttk.Button(popup, text="Close", command=popup.destroy).pack(pady=20)
    
    def _update_prices(self):
        """Update prices by re-fetching from DANIELSON"""
        self._sync_with_danielson()

    def _sync_with_danielson(self):
        """Sync collection with DANIELSON library API"""
        import threading

        def sync():
            try:
                self._set_status("Syncing with DANIELSON...")
                self.all_cards = self._fetch_from_danielson()

                if self.all_cards:
                    total = len(self.all_cards)
                    self._set_status(f"Synced {total} cards from DANIELSON, regrouping...")
                    self.parent.after(0, self._finish_sync)
                else:
                    self._set_status("Sync failed - DANIELSON unreachable")
            except Exception as e:
                self._set_status(f"Sync error: {e}")

        threading.Thread(target=sync, daemon=True).start()

    def _finish_sync(self):
        """Finish sync on main thread (regroup and refresh display)"""
        self.all_grouped_cards = self._group_cards_with_progress(self.all_cards)
        self.cached_total_value = sum(g.total_value for g in self.all_grouped_cards)
        self.cached_total_qty = sum(g.quantity for g in self.all_grouped_cards)
        priced = sum(1 for g in self.all_grouped_cards if g.market_value or g.db_price)
        self._populate_dropdowns()
        self._apply_filters()
        self._set_status(f"Synced {len(self.all_cards)} cards | {len(self.all_grouped_cards)} groups | {priced} priced | ${self.cached_total_value:,.2f}")

    def _download_template(self):
        """Save CSV import template to user-selected location"""
        import shutil

        # Template location
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'import_template.csv')

        if not os.path.exists(template_path):
            messagebox.showerror("Error", "Template file not found")
            return

        # Ask user where to save
        dest_path = filedialog.asksaveasfilename(
            title="Save CSV Template",
            defaultextension=".csv",
            initialfile="import_template.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not dest_path:
            return

        try:
            shutil.copy(template_path, dest_path)
            self._set_status(f"Template saved to {dest_path}")
            messagebox.showinfo("Success", f"Template saved!\n\nColumns:\n- name (required)\n- set_code\n- collector_number\n- quantity\n- price (leave blank for auto-pricing)\n- foil (true/false)\n- rarity\n- condition\n- language")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")


    def _import_csv(self):
        """Import collection from CSV file with auto-pricing via Scryfall"""
        file_path = filedialog.askopenfilename(
            title="Import CSV Collection",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            self._set_status(f"Importing from {file_path}...")
            imported = 0
            errors = 0
            needs_pricing = []

            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # Detect column mapping (flexible headers)
                headers = reader.fieldnames
                name_col = next((h for h in headers if h.lower() in ['name', 'card_name', 'cardname']), None)
                set_col = next((h for h in headers if h.lower() in ['set', 'set_code', 'edition', 'set_name']), None)
                qty_col = next((h for h in headers if h.lower() in ['qty', 'quantity', 'count', 'amount']), None)
                price_col = next((h for h in headers if h.lower() in ['price', 'price_usd', 'value']), None)
                foil_col = next((h for h in headers if h.lower() in ['foil', 'is_foil', 'finish']), None)
                rarity_col = next((h for h in headers if h.lower() in ['rarity']), None)
                condition_col = next((h for h in headers if h.lower() in ['condition', 'cond', 'grade']), None)
                collector_col = next((h for h in headers if h.lower() in ['collector_number', 'number', 'card_number', 'num', 'collector_num']), None)
                language_col = next((h for h in headers if h.lower() in ['language', 'lang']), None)

                if not name_col:
                    messagebox.showerror("Import Error", f"Could not find name column. Headers: {headers}")
                    return

                for row in reader:
                    try:
                        name = row.get(name_col, '').strip()
                        if not name:
                            continue

                        set_code = row.get(set_col, '') if set_col else ''
                        qty = int(row.get(qty_col, 1)) if qty_col else 1
                        price = float(row.get(price_col, 0)) if price_col and row.get(price_col) else None
                        foil_val = row.get(foil_col, '') if foil_col else ''
                        is_foil = foil_val.lower() in ['true', 'yes', '1', 'foil'] if foil_val else False
                        rarity = row.get(rarity_col, '') if rarity_col else ''
                        condition = row.get(condition_col, 'NM').strip() if condition_col else 'NM'
                        collector_number = row.get(collector_col, '').strip() if collector_col else ''
                        language = row.get(language_col, 'en').strip() if language_col else 'en'

                        # Add to library
                        if self.library:
                            card_data = {
                                'name': name,
                                'set_code': set_code.upper() if set_code else '',
                                'quantity': qty,
                                'is_foil': is_foil,
                                'rarity': rarity,
                                'condition': condition,
                                'collector_number': collector_number,
                                'language': language,
                            }
                            if price and price > 0:
                                card_data['price_usd'] = price

                            call_number = self.library.catalog_card(card_data)
                            imported += 1

                            # Track cards that need auto-pricing
                            if not price or price <= 0:
                                card_data['_call_number'] = call_number
                                needs_pricing.append(card_data)
                    except Exception as e:
                        errors += 1

            # Save library
            if self.library and imported > 0:
                self.library._save_library()

            msg = f"Imported {imported} cards"
            if errors > 0:
                msg += f" ({errors} errors)"

            # Auto-price cards that came in without prices
            pricing_engine = getattr(self.library, 'pricing_engine', None) if self.library else None
            if needs_pricing and pricing_engine:
                msg += f"\n\nFetching prices for {len(needs_pricing)} cards from Scryfall..."
                self._set_status(msg)

                # Ask user if they want auto-pricing
                do_price = messagebox.askyesno(
                    "Auto-Price Cards",
                    f"Imported {imported} cards. {len(needs_pricing)} have no price.\n\n"
                    f"Fetch market prices from Scryfall?\n"
                    f"(~{len(needs_pricing) // 10 + 1} seconds)"
                )

                if do_price:
                    # Run pricing in background thread so UI doesn't freeze
                    import threading
                    def _do_auto_pricing():
                        priced = 0
                        failed = 0
                        for i, card in enumerate(needs_pricing):
                            try:
                                self.parent.after(0, lambda i=i: self._set_status(
                                    f"Pricing card {i+1}/{len(needs_pricing)}: {card.get('name', '?')}..."
                                ))

                                result = pricing_engine.auto_price_card(card)

                                if result and result.get('usd', 0) > 0:
                                    price_usd = result['usd']
                                    card_name = result.get('name', card.get('name', ''))
                                    scryfall_id = result.get('scryfall_id', '')

                                    # Update card in library
                                    call_num = card.get('_call_number')
                                    if call_num and self.library:
                                        self.library.update_card(call_num, {
                                            'price_usd': price_usd,
                                            'name': card_name,
                                            'scryfall_id': scryfall_id,
                                            'rarity': result.get('rarity', card.get('rarity', '')),
                                            'type_line': result.get('type_line', ''),
                                            'image_url': result.get('image_url', ''),
                                        })
                                    priced += 1
                                else:
                                    failed += 1
                            except Exception as e:
                                print(f"[WARN] Auto-price failed for {card.get('name', '?')}: {e}")
                                failed += 1

                        # Save updated prices
                        if self.library and priced > 0:
                            self.library._save_library()
                            pricing_engine._save_data()

                        # Refresh UI
                        def _finish():
                            self._load_all_cards()
                            final_msg = f"Import complete: {imported} cards, {priced} priced"
                            if failed > 0:
                                final_msg += f", {failed} price lookups failed"
                            self._set_status(final_msg)
                            messagebox.showinfo("Import Complete", final_msg)
                        self.parent.after(100, _finish)

                    threading.Thread(target=_do_auto_pricing, daemon=True).start()
                    return  # Don't show the default messagebox — pricing thread handles it

            # No pricing needed or user declined
            self.parent.after(100, self._load_all_cards)
            self._set_status(msg)
            messagebox.showinfo("Import Complete", msg)

        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import CSV: {e}")
            self._set_status(f"Import failed: {e}")

    def _export_csv(self):
        """Export collection to CSV file"""
        file_path = filedialog.asksaveasfilename(
            title="Export CSV Collection",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            self._set_status("Exporting collection...")
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Headers
                writer.writerow(['name', 'set_code', 'set_name', 'rarity', 'colors', 'foil', 'price_usd', 'quantity', 'call_sign'])
                
                # Write all grouped cards
                for group in self.grouped_cards:
                    writer.writerow([
                        group.name,
                        group.set_code,
                        group.set_name,
                        group.rarity,
                        ','.join(group.colors) if group.colors else '',
                        'Yes' if group.is_foil else 'No',
                        group.price if group.price else '',
                        group.quantity,
                        f"{getattr(group, 'first_call_sign', '')}-{getattr(group, 'last_call_sign', '')}" if getattr(group, 'first_call_sign', None) else ''
                    ])

            self._set_status(f"Exported {len(self.grouped_cards)} cards to {file_path}")
            messagebox.showinfo("Export Complete", f"Exported {len(self.grouped_cards)} cards to:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {e}")
            self._set_status(f"Export failed: {e}")

    def _set_status(self, message: str):
        """Update status bar"""
        self.status_label.config(text=message)


# ═══════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def create_collection_tab(parent: ttk.Frame, library=None, scryfall_db=None) -> CollectionTab:
    """Factory function to create collection tab"""
    return CollectionTab(parent, library, scryfall_db)
