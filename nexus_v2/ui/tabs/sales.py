"""
NEXUS V2 Sales Tab
==================
Marketplace and sales management with listing workflow
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from datetime import datetime
from typing import Dict, List, Optional
import threading


class ListingDialog:
    """Dialog for creating new marketplace listings"""

    CONDITIONS = ['Near Mint', 'Lightly Played', 'Moderately Played', 'Heavily Played', 'Damaged']
    CONDITION_MULTIPLIERS = {
        'Near Mint': 1.0,
        'Lightly Played': 0.85,
        'Moderately Played': 0.70,
        'Heavily Played': 0.50,
        'Damaged': 0.30
    }
    PLATFORMS = ['TCGPlayer', 'eBay', 'CardMarket', 'Manual']

    def __init__(self, parent, library, colors, callback):
        self.parent = parent
        self.library = library
        self.colors = colors
        self.callback = callback
        self.selected_card = None
        self.all_cards = []

        self._create_dialog()

    def _create_dialog(self):
        """Create the listing dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("List New Item")
        self.dialog.geometry("900x600")
        self.dialog.configure(bg=self.colors.bg_dark)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Main layout: left (search/list) | right (details/pricing)
        main_frame = tk.Frame(self.dialog, bg=self.colors.bg_dark)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Left panel - Card Search
        left_panel = tk.Frame(main_frame, bg=self.colors.bg_surface, width=450)
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 5))
        left_panel.pack_propagate(False)

        tk.Label(
            left_panel,
            text="Select Card from Library",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(pady=10, padx=10, anchor='w')

        # Search bar
        search_frame = tk.Frame(left_panel, bg=self.colors.bg_surface)
        search_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(search_frame, text="Search:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self._on_search)
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side='left', padx=5)

        # Card list
        list_frame = tk.Frame(left_panel, bg=self.colors.bg_surface)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('Name', 'Set', 'Foil', 'Call #')
        self.card_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self.card_tree.heading(col, text=col)
            self.card_tree.column(col, width=100 if col != 'Name' else 150)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.card_tree.yview)
        self.card_tree.configure(yscrollcommand=scrollbar.set)

        self.card_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.card_tree.bind('<<TreeviewSelect>>', self._on_card_select)

        # Right panel - Listing Details
        right_panel = tk.Frame(main_frame, bg=self.colors.bg_surface, width=400)
        right_panel.pack(side='right', fill='both', padx=(5, 0))
        right_panel.pack_propagate(False)

        tk.Label(
            right_panel,
            text="Listing Details",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(pady=10, padx=10, anchor='w')

        # Card info display
        self.card_info_frame = tk.Frame(right_panel, bg=self.colors.bg_surface)
        self.card_info_frame.pack(fill='x', padx=10, pady=5)

        self.card_name_label = tk.Label(
            self.card_info_frame,
            text="No card selected",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        )
        self.card_name_label.pack(anchor='w')

        self.card_set_label = tk.Label(
            self.card_info_frame,
            text="",
            font=('Segoe UI', 10),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        )
        self.card_set_label.pack(anchor='w')

        # Pricing section
        pricing_frame = tk.LabelFrame(right_panel, text="Pricing", bg=self.colors.bg_surface,
                                      fg=self.colors.text_primary)
        pricing_frame.pack(fill='x', padx=10, pady=10)

        # Market price display (third-party reference data only)
        self.market_price_label = tk.Label(
            pricing_frame,
            text="TCGPlayer Mid (Scryfall): --",
            font=('Segoe UI', 10),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        )
        self.market_price_label.pack(anchor='w', padx=10, pady=5)

        tk.Label(
            pricing_frame,
            text="Market data provided by Scryfall/TCGPlayer. NEXUS does not determine prices.",
            font=('Segoe UI', 8),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface,
            wraplength=340,
            justify='left'
        ).pack(anchor='w', padx=10)

        # Your price entry
        price_row = tk.Frame(pricing_frame, bg=self.colors.bg_surface)
        price_row.pack(fill='x', padx=10, pady=5)

        tk.Label(price_row, text="Your Price: $", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).pack(side='left')
        self.price_var = tk.StringVar(value="0.00")
        self.price_entry = tk.Entry(price_row, textvariable=self.price_var, width=10)
        self.price_entry.pack(side='left')

        tk.Button(price_row, text="Copy Reference", command=self._use_market_price).pack(side='left', padx=10)

        # Condition dropdown
        condition_frame = tk.Frame(right_panel, bg=self.colors.bg_surface)
        condition_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(condition_frame, text="Condition:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).pack(side='left')
        self.condition_var = tk.StringVar(value='Near Mint')
        self.condition_combo = ttk.Combobox(
            condition_frame,
            textvariable=self.condition_var,
            values=self.CONDITIONS,
            state='readonly',
            width=18
        )
        self.condition_combo.pack(side='left', padx=5)
        self.condition_combo.bind('<<ComboboxSelected>>', self._on_condition_change)

        # Quantity
        qty_frame = tk.Frame(right_panel, bg=self.colors.bg_surface)
        qty_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(qty_frame, text="Quantity:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).pack(side='left')
        self.qty_var = tk.StringVar(value="1")
        self.qty_spin = tk.Spinbox(qty_frame, from_=1, to=100, textvariable=self.qty_var, width=5)
        self.qty_spin.pack(side='left', padx=5)

        # Platform
        platform_frame = tk.Frame(right_panel, bg=self.colors.bg_surface)
        platform_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(platform_frame, text="Platform:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).pack(side='left')
        self.platform_var = tk.StringVar(value='TCGPlayer')
        self.platform_combo = ttk.Combobox(
            platform_frame,
            textvariable=self.platform_var,
            values=self.PLATFORMS,
            state='readonly',
            width=15
        )
        self.platform_combo.pack(side='left', padx=5)

        # Buttons
        button_frame = tk.Frame(right_panel, bg=self.colors.bg_surface)
        button_frame.pack(fill='x', padx=10, pady=20)

        tk.Button(
            button_frame,
            text="Add Listing",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors.accent,
            fg='white',
            command=self._add_listing
        ).pack(side='left', padx=5)

        tk.Button(
            button_frame,
            text="Cancel",
            font=('Segoe UI', 10),
            command=self.dialog.destroy
        ).pack(side='left', padx=5)

        # Load cards
        self._load_cards()

    def _load_cards(self):
        """Load cards from library"""
        if self.library:
            self.all_cards = self.library.get_all_cards()
            self._populate_tree(self.all_cards[:500])  # Show first 500

    def _populate_tree(self, cards):
        """Populate the card tree"""
        self.card_tree.delete(*self.card_tree.get_children())
        for card in cards:
            foil = "✓" if card.get('foil') else ""
            self.card_tree.insert('', 'end', values=(
                card.get('name', 'Unknown'),
                card.get('set', 'N/A'),
                foil,
                card.get('call_number', '')
            ), tags=(str(id(card)),))
            # Store card data
            self.card_tree.set(self.card_tree.get_children()[-1], 'data', str(cards.index(card)))

    def _on_search(self, *args):
        """Filter cards by search text"""
        search_text = self.search_var.get().lower()
        if not search_text:
            self._populate_tree(self.all_cards[:500])
            return

        filtered = [c for c in self.all_cards if search_text in c.get('name', '').lower()]
        self._populate_tree(filtered[:200])

    def _on_card_select(self, event):
        """Handle card selection"""
        selection = self.card_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.card_tree.item(item, 'values')
        name, set_code, foil, call_num = values

        # Find card in all_cards
        for card in self.all_cards:
            if card.get('call_number') == call_num:
                self.selected_card = card
                break

        if self.selected_card:
            self.card_name_label.config(text=self.selected_card.get('name', 'Unknown'))
            self.card_set_label.config(
                text=f"Set: {self.selected_card.get('set', 'N/A')} | "
                     f"#{self.selected_card.get('collector_number', '')} | "
                     f"{'FOIL' if self.selected_card.get('foil') else 'Non-foil'}"
            )
            self._fetch_market_price()

    def _fetch_market_price(self):
        """Fetch third-party market reference price for selected card (display only)"""
        if not self.selected_card:
            return

        self.market_price_label.config(text="TCGPlayer Mid (Scryfall): Loading...")

        # Use Scryfall price if available in card data (sourced from TCGPlayer)
        price = self.selected_card.get('price_usd') or self.selected_card.get('prices', {}).get('usd')
        if price:
            self.market_price = float(price)
            self.market_price_label.config(
                text=f"TCGPlayer Mid (Scryfall): ${self.market_price:.2f}"
            )
        else:
            self.market_price = 0
            self.market_price_label.config(text="TCGPlayer Mid (Scryfall): Not available")

    def _use_market_price(self):
        """Copy the raw third-party reference price into the price field (no calculation)"""
        if hasattr(self, 'market_price') and self.market_price > 0:
            self.price_var.set(f"{self.market_price:.2f}")

    def _on_condition_change(self, event=None):
        """Condition changed — user sets their own price"""
        pass  # NEXUS does not calculate condition-adjusted prices

    def _add_listing(self):
        """Add the listing"""
        if not self.selected_card:
            messagebox.showwarning("No Card", "Please select a card first.")
            return

        try:
            price = float(self.price_var.get())
        except ValueError:
            messagebox.showerror("Invalid Price", "Please enter a valid price.")
            return

        listing = {
            'name': self.selected_card.get('name'),
            'set': self.selected_card.get('set'),
            'collector_number': self.selected_card.get('collector_number', ''),
            'foil': self.selected_card.get('foil', False),
            'condition': self.condition_var.get(),
            'price': price,
            'quantity': int(self.qty_var.get()),
            'platform': self.platform_var.get(),
            'call_number': self.selected_card.get('call_number', ''),
            'status': 'Draft',
            'created_at': datetime.now().isoformat()
        }

        self.callback(listing)
        messagebox.showinfo("Success", f"Added {listing['name']} to listings!")
        self.dialog.destroy()


class SalesTab:
    """Sales and Marketplace Management Tab"""

    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.library = kwargs.get('library')
        self.theme = kwargs.get('theme')
        self.colors = kwargs.get('colors')
        self.shop_personality = kwargs.get('shop_personality')
        self.listed_items = []
        self.purchases = []  # Track purchased cards

        if parent:
            self._create_ui()

    def _create_ui(self):
        """Create the sales UI"""
        # Main container
        container = tk.Frame(self.parent, bg=self.colors.bg_dark)
        container.pack(fill='both', expand=True)

        # Header (fixed at top)
        header = tk.Frame(container, bg=self.colors.bg_surface)
        header.pack(fill='x', padx=10, pady=10)

        tk.Label(
            header,
            text="Sales & Marketplace",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(pady=15, padx=20, anchor='w')

        # Scrollable content area
        canvas = tk.Canvas(container, bg=self.colors.bg_dark, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
        main_frame = tk.Frame(canvas, bg=self.colors.bg_dark)

        main_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=main_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True, padx=10)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Stats row
        stats_frame = tk.Frame(main_frame, bg=self.colors.bg_surface)
        stats_frame.pack(fill='x', pady=5)

        stats = [
            ("Listed Items", "0"),
            ("Total Sales", "$0.00"),
            ("Purchases", "0"),
            ("Pending", "0"),
            ("Active Platforms", "0"),
        ]

        stats_inner = tk.Frame(stats_frame, bg=self.colors.bg_surface)
        stats_inner.pack(pady=15, padx=20)

        self._stat_labels = {}
        for label, value in stats:
            col = tk.Frame(stats_inner, bg=self.colors.bg_surface)
            col.pack(side='left', padx=30)

            val_label = tk.Label(
                col,
                text=value,
                font=('Segoe UI', 20, 'bold'),
                fg=self.colors.accent,
                bg=self.colors.bg_surface
            )
            val_label.pack()
            self._stat_labels[label] = val_label

            tk.Label(
                col,
                text=label,
                font=('Segoe UI', 10),
                fg=self.colors.text_secondary,
                bg=self.colors.bg_surface
            ).pack()

        # Listings table
        listings_frame = tk.Frame(main_frame, bg=self.colors.bg_surface)
        listings_frame.pack(fill='both', expand=True, pady=10)

        tk.Label(
            listings_frame,
            text="Active Listings",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(pady=10, padx=20, anchor='w')

        # Treeview for listings
        columns = ('Card Name', 'Set', 'Price', 'Quantity', 'Platform', 'Status')
        self.listings_tree = ttk.Treeview(listings_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.listings_tree.heading(col, text=col)
            self.listings_tree.column(col, width=120)

        self.listings_tree.pack(fill='both', expand=True, padx=20, pady=10)

        # Action buttons
        button_frame = tk.Frame(listings_frame, bg=self.colors.bg_surface)
        button_frame.pack(fill='x', padx=20, pady=10)

        tk.Button(
            button_frame,
            text="List New Item",
            font=('Segoe UI', 10),
            bg=self.colors.accent,
            fg='white',
            command=self._list_new_item
        ).pack(side='left', padx=5)

        tk.Button(
            button_frame,
            text="Sync with TCGPlayer",
            font=('Segoe UI', 10),
            command=self._sync_tcgplayer
        ).pack(side='left', padx=5)

        tk.Button(
            button_frame,
            text="Export CSV",
            font=('Segoe UI', 10),
            command=self._export_csv
        ).pack(side='left', padx=5)

        # NEXUS Marketplace button
        tk.Button(
            button_frame,
            text="Sync to NEXUS Marketplace",
            font=('Segoe UI', 10),
            bg='#2ecc71',
            fg='white',
            command=self._sync_nexus_marketplace
        ).pack(side='left', padx=5)

        # ═══════════════════════════════════════════════════════════════
        # PURCHASES SECTION
        # ═══════════════════════════════════════════════════════════════
        purchases_frame = tk.Frame(main_frame, bg=self.colors.bg_surface)
        purchases_frame.pack(fill='both', expand=True, pady=10)

        tk.Label(
            purchases_frame,
            text="Recent Purchases",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(pady=10, padx=20, anchor='w')

        # Treeview for purchases
        purchase_columns = ('Card Name', 'Set', 'Price', 'Qty', 'Seller', 'Status', 'Date')
        self.purchases_tree = ttk.Treeview(purchases_frame, columns=purchase_columns, show='headings', height=8)

        for col in purchase_columns:
            self.purchases_tree.heading(col, text=col)
            width = 80 if col in ('Qty', 'Price') else 100 if col != 'Card Name' else 150
            self.purchases_tree.column(col, width=width)

        self.purchases_tree.pack(fill='both', expand=True, padx=20, pady=10)

        # Purchase action buttons
        purchase_btn_frame = tk.Frame(purchases_frame, bg=self.colors.bg_surface)
        purchase_btn_frame.pack(fill='x', padx=20, pady=10)

        tk.Button(
            purchase_btn_frame,
            text="Add Purchase",
            font=('Segoe UI', 10),
            bg='#3498db',
            fg='white',
            command=self._add_purchase
        ).pack(side='left', padx=5)

        tk.Button(
            purchase_btn_frame,
            text="Mark Received",
            font=('Segoe UI', 10),
            command=self._mark_received
        ).pack(side='left', padx=5)

        tk.Button(
            purchase_btn_frame,
            text="Add to Library",
            font=('Segoe UI', 10),
            bg='#27ae60',
            fg='white',
            command=self._add_purchase_to_library
        ).pack(side='left', padx=5)

        tk.Button(
            purchase_btn_frame,
            text="Sync Purchases",
            font=('Segoe UI', 10),
            command=self._sync_purchases
        ).pack(side='left', padx=5)

    def _list_new_item(self):
        """Open dialog to list a new item"""
        ListingDialog(
            self.parent,
            self.library,
            self.colors,
            callback=self._on_listing_added
        )

    def open_listing_for_card(self, card_group):
        """
        Open listing dialog for a specific card from Collection tab.

        Args:
            card_group: GroupedCard object from collection tab
        """
        import tkinter as tk
        from tkinter import messagebox, ttk

        # Create listing dialog with standard ttk widgets
        popup = tk.Toplevel(self.parent)
        popup.title(f"List for Sale - {card_group.name}")
        popup.geometry("450x500")
        popup.transient(self.parent)
        popup.grab_set()

        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill="both", expand=True)

        # Card info header
        ttk.Label(frame, text=card_group.name, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{card_group.set_name} ({card_group.set_code}) #{getattr(card_group, 'collector_number', '')}",
                  foreground="gray").pack(anchor="w")
        if card_group.foil:
            ttk.Label(frame, text="FOIL", foreground="#FFD700").pack(anchor="w")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=15)

        # Price section
        price_frame = ttk.Frame(frame)
        price_frame.pack(fill="x", pady=5)

        ttk.Label(price_frame, text="Listing Price ($):").pack(side="left")
        price_var = tk.StringVar()

        # Default to market value if available
        default_price = getattr(card_group, 'market_value', None) or getattr(card_group, 'db_price', None) or 0.99
        price_var.set(f"{default_price:.2f}")

        price_entry = ttk.Entry(price_frame, textvariable=price_var, width=12)
        price_entry.pack(side="left", padx=10)

        if hasattr(card_group, 'market_value') and card_group.market_value:
            ttk.Label(price_frame, text=f"(Market: ${card_group.market_value:.2f})",
                      foreground="gray").pack(side="left")

        # Quantity section
        qty_frame = ttk.Frame(frame)
        qty_frame.pack(fill="x", pady=5)

        ttk.Label(qty_frame, text="Quantity to List:").pack(side="left")
        qty_var = tk.StringVar(value="1")
        qty_spin = ttk.Spinbox(qty_frame, from_=1, to=card_group.quantity, textvariable=qty_var, width=5)
        qty_spin.pack(side="left", padx=10)
        ttk.Label(qty_frame, text=f"(Have: {card_group.quantity})", foreground="gray").pack(side="left")

        # Condition dropdown
        cond_frame = ttk.Frame(frame)
        cond_frame.pack(fill="x", pady=5)

        ttk.Label(cond_frame, text="Condition:").pack(side="left")
        cond_var = tk.StringVar(value="NM")
        cond_combo = ttk.Combobox(cond_frame, textvariable=cond_var, width=15,
                                   values=["NM", "LP", "MP", "HP", "DMG"], state="readonly")
        cond_combo.pack(side="left", padx=10)

        # Platform dropdown
        platform_frame = ttk.Frame(frame)
        platform_frame.pack(fill="x", pady=5)

        ttk.Label(platform_frame, text="Platform:").pack(side="left")
        platform_var = tk.StringVar(value="NEXUS Marketplace")
        platform_combo = ttk.Combobox(platform_frame, textvariable=platform_var, width=20,
                                     values=["NEXUS Marketplace", "TCGPlayer", "eBay", "Local Shop"], state="readonly")
        platform_combo.pack(side="left", padx=10)

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
                platform = platform_var.get()

                if price <= 0:
                    messagebox.showerror("Invalid Price", "Price must be greater than $0")
                    return
                if qty < 1 or qty > card_group.quantity:
                    messagebox.showerror("Invalid Quantity", f"Quantity must be between 1 and {card_group.quantity}")
                    return

                # Create listing data
                listing_data = {
                    'name': card_group.name,
                    'set': f"{card_group.set_name} ({card_group.set_code})",
                    'set_code': card_group.set_code,
                    'collector_number': getattr(card_group, 'collector_number', ''),
                    'price': price,
                    'quantity': qty,
                    'condition': condition,
                    'platform': platform,
                    'foil': card_group.foil,
                    'rarity': getattr(card_group, 'rarity', 'Unknown'),
                    'scryfall_id': getattr(card_group, 'scryfall_id', ''),
                    'image_url': getattr(card_group, 'image_uri', ''),
                    'status': 'Active'
                }

                # If NEXUS Marketplace, try API sync
                if platform == "NEXUS Marketplace":
                    try:
                        from nexus_v2.integrations.marketplace_client import MarketplaceClient
                        client = MarketplaceClient()

                        if client.is_connected():
                            status_var.set("Creating listing on marketplace...")
                            popup.update()

                            # Auto-login if needed
                            user = client.get_current_user()
                            if not user.get('user'):
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
                                    status_var.set("Creating seller account...")
                                    popup.update()
                                    client.register(username="NEXUS Shop", email=email, password=password, role='seller', shop_name="NEXUS Shop")

                            # Create listing via API
                            result = client.create_listing(
                                card_name=card_group.name,
                                price=price,
                                quantity=qty,
                                condition=condition,
                                set_name=card_group.set_name,
                                set_code=card_group.set_code,
                                rarity=getattr(card_group, 'rarity', 'Unknown'),
                                foil=card_group.foil,
                                collector_number=getattr(card_group, 'collector_number', ''),
                                image_url=getattr(card_group, 'image_uri', ''),
                                scryfall_id=getattr(card_group, 'scryfall_id', '')
                            )

                            if result.get('error'):
                                status_var.set(f"API Error: {result['error']}")
                                # Still add locally as draft
                                listing_data['status'] = 'Draft - API Failed'
                            else:
                                listing_data['listing_id'] = result.get('listing_id')
                                listing_data['status'] = 'Synced to Marketplace'
                    except ImportError:
                        status_var.set("Marketplace client not available - saving locally")
                        listing_data['status'] = 'Local Only'
                    except Exception as e:
                        status_var.set(f"Sync error: {e}")
                        listing_data['status'] = 'Local Only'

                # Add to sales tab listings
                self._on_listing_added(listing_data)

                messagebox.showinfo("Listed!",
                                  f"Successfully listed:\n\n{card_group.name} x{qty}\n${price:.2f} each\n\nPlatform: {platform}")
                popup.destroy()

            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter valid price and quantity")

        ttk.Button(btn_frame, text="List for Sale", command=do_list).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side="left", padx=5)

    def _on_listing_added(self, listing_data):
        """Callback when listing is added from dialog"""
        self.listed_items.append(listing_data)
        self._stat_labels['Listed Items'].config(text=str(len(self.listed_items)))

        # Add to treeview
        self.listings_tree.insert('', 'end', values=(
            listing_data.get('name', 'Unknown'),
            listing_data.get('set', 'N/A'),
            f"${listing_data.get('price', 0):.2f}",
            listing_data.get('quantity', 1),
            listing_data.get('platform', 'Manual'),
            listing_data.get('status', 'Draft')
        ))

        # Update total value
        total = sum(item.get('price', 0) * item.get('quantity', 1) for item in self.listed_items)
        self._stat_labels['Total Sales'].config(text=f"${total:.2f}")

    def _sync_tcgplayer(self):
        """Sync with TCGPlayer"""
        if not self.listed_items:
            messagebox.showinfo("No Listings", "Add some listings first before syncing.")
            return

        # Filter TCGPlayer listings
        tcg_listings = [l for l in self.listed_items if l.get('platform') == 'TCGPlayer']
        if not tcg_listings:
            messagebox.showinfo("No TCGPlayer Listings",
                               "No listings marked for TCGPlayer. Change platform to TCGPlayer first.")
            return

        messagebox.showinfo("TCGPlayer Sync",
                           f"Ready to sync {len(tcg_listings)} listings to TCGPlayer.\n\n"
                           "Use 'Export CSV' to generate a TCGPlayer-compatible file for mass upload.")

    def _sync_nexus_marketplace(self):
        """Sync listings to NEXUS Marketplace (nexus-cards.com)"""
        if not self.listed_items:
            messagebox.showinfo("No Listings", "Add some listings first before syncing.")
            return

        try:
            from nexus_v2.integrations.marketplace_client import MarketplaceClient
            client = MarketplaceClient()

            # Check connection
            status = client._get('/status')
            if 'error' in status:
                messagebox.showerror("Connection Error",
                                    f"Could not connect to NEXUS Marketplace:\n{status['error']}\n\n"
                                    "Make sure you have an internet connection.")
                return

            # Sync each listing
            synced = 0
            errors = []

            for listing in self.listed_items:
                result = client.create_listing(
                    card_name=listing.get('name'),
                    price=listing.get('price', 0),
                    quantity=listing.get('quantity', 1),
                    condition=listing.get('condition', 'NM'),
                    set_code=listing.get('set_code', ''),
                    set_name=listing.get('set', ''),
                    collector_number=listing.get('collector_number', ''),
                    foil=listing.get('foil', False),
                    rarity=listing.get('rarity', ''),
                    scryfall_id=listing.get('scryfall_id', ''),
                    image_url=listing.get('image_url', '')
                )

                if result.get('success'):
                    synced += 1
                    listing['marketplace_id'] = result.get('listing_id')
                    listing['status'] = 'Listed'
                else:
                    errors.append(f"{listing.get('name')}: {result.get('error', 'Unknown error')}")

            # Update UI
            self._refresh_listings_tree()

            if synced > 0:
                self._stat_labels['Active Platforms'].config(text="1")

            msg = f"Successfully synced {synced}/{len(self.listed_items)} listings to NEXUS Marketplace!"
            if errors:
                msg += f"\n\nErrors:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += f"\n... and {len(errors) - 5} more"

            messagebox.showinfo("Sync Complete", msg)

        except ImportError:
            messagebox.showerror("Module Not Found",
                               "Marketplace client not available.\n"
                               "Check that integrations/marketplace_client.py exists.")
        except Exception as e:
            messagebox.showerror("Sync Error", f"Failed to sync: {e}")

    def _refresh_listings_tree(self):
        """Refresh the listings treeview"""
        self.listings_tree.delete(*self.listings_tree.get_children())
        for listing in self.listed_items:
            self.listings_tree.insert('', 'end', values=(
                listing.get('name', 'Unknown'),
                listing.get('set', 'N/A'),
                f"${listing.get('price', 0):.2f}",
                listing.get('quantity', 1),
                listing.get('platform', 'Manual'),
                listing.get('status', 'Draft')
            ))

    def _export_csv(self):
        """Export listings to CSV (TCGPlayer compatible format)"""
        if not self.listed_items:
            messagebox.showinfo("No Listings", "No listings to export.")
            return

        # Ask for save location
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            initialfilename=f'nexus_listings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )

        if not filepath:
            return

        try:
            # TCGPlayer CSV format
            tcg_headers = [
                'TCGplayer Id', 'Product Line', 'Set Name', 'Product Name',
                'Title', 'Number', 'Rarity', 'Condition', 'TCG Market Price',
                'TCG Direct Low', 'TCG Low Price', 'TCG Low Price Shipping',
                'Total Quantity', 'Add to Quantity', 'TCG Marketplace Price',
                'Photo URL'
            ]

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(tcg_headers)

                for listing in self.listed_items:
                    # Map condition to TCGPlayer format
                    condition_map = {
                        'Near Mint': 'Near Mint',
                        'Lightly Played': 'Lightly Played',
                        'Moderately Played': 'Moderately Played',
                        'Heavily Played': 'Heavily Played',
                        'Damaged': 'Damaged'
                    }
                    tcg_condition = condition_map.get(listing.get('condition', 'Near Mint'), 'Near Mint')
                    if listing.get('foil'):
                        tcg_condition += ' Foil'

                    writer.writerow([
                        '',  # TCGplayer Id (blank for new)
                        'Magic',  # Product Line
                        listing.get('set', ''),  # Set Name
                        listing.get('name', ''),  # Product Name
                        '',  # Title
                        listing.get('collector_number', ''),  # Number
                        '',  # Rarity
                        tcg_condition,  # Condition
                        '',  # TCG Market Price
                        '',  # TCG Direct Low
                        '',  # TCG Low Price
                        '',  # TCG Low Price Shipping
                        listing.get('quantity', 1),  # Total Quantity
                        listing.get('quantity', 1),  # Add to Quantity
                        f"{listing.get('price', 0):.2f}",  # TCG Marketplace Price
                        ''  # Photo URL
                    ])

            messagebox.showinfo("Export Complete",
                               f"Exported {len(self.listed_items)} listings to:\n{filepath}\n\n"
                               "Upload this file to TCGPlayer's mass upload tool.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV:\n{e}")

    def add_listing(self, card_data):
        """Add a card to listings from Collection tab"""
        self.listed_items.append(card_data)
        self._stat_labels['Listed Items'].config(text=str(len(self.listed_items)))

        # Add to treeview
        self.listings_tree.insert('', 'end', values=(
            card_data.get('name', 'Unknown'),
            card_data.get('set', 'N/A'),
            f"${card_data.get('price', 0):.2f}",
            card_data.get('quantity', 1),
            'Manual',
            'Draft'
        ))

    # ═══════════════════════════════════════════════════════════════════
    # PURCHASE TRACKING METHODS
    # ═══════════════════════════════════════════════════════════════════

    def _add_purchase(self):
        """Open dialog to manually add a purchase"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Add Purchase")
        dialog.geometry("450x400")
        dialog.configure(bg=self.colors.bg_surface)
        dialog.transient(self.parent)
        dialog.grab_set()

        tk.Label(
            dialog, text="Add Card Purchase",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(pady=15)

        form_frame = tk.Frame(dialog, bg=self.colors.bg_surface)
        form_frame.pack(fill='x', padx=20, pady=10)

        # Card name
        tk.Label(form_frame, text="Card Name:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).grid(row=0, column=0, sticky='w', pady=5)
        name_var = tk.StringVar()
        tk.Entry(form_frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

        # Set
        tk.Label(form_frame, text="Set Code:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).grid(row=1, column=0, sticky='w', pady=5)
        set_var = tk.StringVar()
        tk.Entry(form_frame, textvariable=set_var, width=10).grid(row=1, column=1, sticky='w', pady=5)

        # Price
        tk.Label(form_frame, text="Price Paid: $", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).grid(row=2, column=0, sticky='w', pady=5)
        price_var = tk.StringVar(value="0.00")
        tk.Entry(form_frame, textvariable=price_var, width=10).grid(row=2, column=1, sticky='w', pady=5)

        # Quantity
        tk.Label(form_frame, text="Quantity:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).grid(row=3, column=0, sticky='w', pady=5)
        qty_var = tk.StringVar(value="1")
        tk.Spinbox(form_frame, from_=1, to=100, textvariable=qty_var, width=5).grid(row=3, column=1, sticky='w', pady=5)

        # Seller
        tk.Label(form_frame, text="Seller/Source:", bg=self.colors.bg_surface,
                 fg=self.colors.text_primary).grid(row=4, column=0, sticky='w', pady=5)
        seller_var = tk.StringVar()
        seller_combo = ttk.Combobox(form_frame, textvariable=seller_var, width=20,
                                    values=['TCGPlayer', 'eBay', 'CardKingdom', 'Local Shop', 'Trade', 'Other'])
        seller_combo.grid(row=4, column=1, sticky='w', pady=5)

        # Foil checkbox
        foil_var = tk.BooleanVar(value=False)
        tk.Checkbutton(form_frame, text="Foil", variable=foil_var,
                       bg=self.colors.bg_surface, fg=self.colors.text_primary,
                       selectcolor=self.colors.bg_dark).grid(row=5, column=1, sticky='w', pady=5)

        def save_purchase():
            try:
                price = float(price_var.get())
            except ValueError:
                messagebox.showerror("Invalid Price", "Please enter a valid price.")
                return

            if not name_var.get().strip():
                messagebox.showerror("Missing Name", "Please enter a card name.")
                return

            purchase = {
                'name': name_var.get().strip(),
                'set': set_var.get().strip().upper(),
                'price': price,
                'quantity': int(qty_var.get()),
                'seller': seller_var.get() or 'Unknown',
                'foil': foil_var.get(),
                'status': 'Ordered',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'received': False
            }

            self.purchases.append(purchase)
            self._refresh_purchases_tree()
            self._update_purchase_stats()
            messagebox.showinfo("Success", f"Added purchase: {purchase['name']}")
            dialog.destroy()

        tk.Button(
            dialog, text="Save Purchase",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors.accent, fg='white',
            command=save_purchase
        ).pack(pady=20)

    def _mark_received(self):
        """Mark selected purchase as received"""
        selection = self.purchases_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a purchase to mark as received.")
            return

        for item in selection:
            values = self.purchases_tree.item(item, 'values')
            # Find matching purchase
            for purchase in self.purchases:
                if (purchase['name'] == values[0] and
                    purchase['date'] == values[6] and
                    purchase['status'] != 'Received'):
                    purchase['status'] = 'Received'
                    purchase['received'] = True
                    break

        self._refresh_purchases_tree()
        self._update_purchase_stats()
        messagebox.showinfo("Updated", "Selected purchases marked as received!")

    def _add_purchase_to_library(self):
        """Add received purchase to library"""
        selection = self.purchases_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a purchase to add to library.")
            return

        if not self.library:
            messagebox.showerror("No Library", "Library not available.")
            return

        added = 0
        for item in selection:
            values = self.purchases_tree.item(item, 'values')
            # Find matching purchase
            for purchase in self.purchases:
                if (purchase['name'] == values[0] and
                    purchase['date'] == values[6] and
                    purchase.get('received', False)):

                    # Add to library
                    try:
                        for _ in range(purchase.get('quantity', 1)):
                            self.library.add_card({
                                'name': purchase['name'],
                                'set': purchase.get('set', '???'),
                                'foil': purchase.get('foil', False),
                                'condition': 'NM',
                                'price_paid': purchase.get('price', 0)
                            })
                        purchase['status'] = 'In Library'
                        added += 1
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to add {purchase['name']}: {e}")
                    break

        if added > 0:
            self._refresh_purchases_tree()
            messagebox.showinfo("Added to Library", f"Added {added} purchase(s) to your library!")
        else:
            messagebox.showinfo("Not Received", "Only received purchases can be added to library.")

    def _sync_purchases(self):
        """Sync purchases from NEXUS Marketplace"""
        try:
            from nexus_v2.integrations.marketplace_client import MarketplaceClient
            client = MarketplaceClient()

            # Get user's purchases
            result = client._get('/user/purchases')
            if 'error' in result:
                messagebox.showerror("Sync Error", f"Could not fetch purchases:\n{result['error']}")
                return

            purchases = result.get('purchases', [])
            if not purchases:
                messagebox.showinfo("No Purchases", "No purchases found on NEXUS Marketplace.")
                return

            # Add new purchases
            new_count = 0
            for p in purchases:
                # Check if already exists
                exists = any(
                    purchase.get('marketplace_id') == p.get('id')
                    for purchase in self.purchases
                )
                if not exists:
                    self.purchases.append({
                        'name': p.get('card_name', 'Unknown'),
                        'set': p.get('set_code', ''),
                        'price': p.get('price', 0),
                        'quantity': p.get('quantity', 1),
                        'seller': p.get('seller_name', 'NEXUS'),
                        'foil': p.get('foil', False),
                        'status': p.get('status', 'Ordered'),
                        'date': p.get('purchase_date', datetime.now().strftime('%Y-%m-%d')),
                        'received': p.get('status') == 'Delivered',
                        'marketplace_id': p.get('id')
                    })
                    new_count += 1

            self._refresh_purchases_tree()
            self._update_purchase_stats()
            messagebox.showinfo("Sync Complete", f"Synced {new_count} new purchase(s) from NEXUS Marketplace!")

        except ImportError:
            messagebox.showerror("Module Not Found", "Marketplace client not available.")
        except Exception as e:
            messagebox.showerror("Sync Error", f"Failed to sync: {e}")

    def _refresh_purchases_tree(self):
        """Refresh the purchases treeview"""
        self.purchases_tree.delete(*self.purchases_tree.get_children())
        for purchase in self.purchases:
            self.purchases_tree.insert('', 'end', values=(
                purchase.get('name', 'Unknown'),
                purchase.get('set', 'N/A'),
                f"${purchase.get('price', 0):.2f}",
                purchase.get('quantity', 1),
                purchase.get('seller', 'Unknown'),
                purchase.get('status', 'Ordered'),
                purchase.get('date', '')
            ))

    def _update_purchase_stats(self):
        """Update purchase statistics"""
        self._stat_labels['Purchases'].config(text=str(len(self.purchases)))

        pending = sum(1 for p in self.purchases if p.get('status') not in ('Received', 'In Library'))
        self._stat_labels['Pending'].config(text=str(pending))
