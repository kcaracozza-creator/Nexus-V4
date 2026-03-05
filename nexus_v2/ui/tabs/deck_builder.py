#!/usr/bin/env python3
"""
NEXUS V2 Deck Builder Tab
Simple, functional deck builder
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

# NEXUS library imports
from nexus_v2.library.brock_client import BrockLibraryClient
from nexus_v2.config import get_config


class DeckBuilderTab:
    """Deck Builder Tab - AI-powered deck construction"""

    FORMATS = {
        "Commander": {"deck_size": 100, "max_copies": 1},
        "Standard": {"deck_size": 60, "max_copies": 4},
        "Modern": {"deck_size": 60, "max_copies": 4},
        "Pioneer": {"deck_size": 60, "max_copies": 4},
        "Legacy": {"deck_size": 60, "max_copies": 4},
    }
    STRATEGIES = ["Balanced", "Aggro", "Control", "Combo", "Midrange"]

    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.library = kwargs.get("library")
        self.scryfall_db = kwargs.get("scryfall_db")
        self.theme = kwargs.get("theme")
        self.colors = kwargs.get("colors")
        self.shop_personality = kwargs.get("shop_personality")

        self.current_deck = []
        self.commander = None  # Commander card for EDH format
        self.deck_name = tk.StringVar(value="New Deck")
        self.format_var = tk.StringVar(value="Commander")
        self.strategy_var = tk.StringVar(value="Balanced")
        self.color_vars = {c: tk.BooleanVar() for c in "WUBRG"}

        # Theme colors
        self.bg_dark = "#1a1a1a"
        self.bg_surface = "#2d2d2d"
        self.accent = "#d4af37"

        if parent:
            self._create_ui()

    def _create_ui(self):
        """Create the deck builder UI"""
        main = tk.Frame(self.parent, bg=self.bg_dark)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # Left panel - controls
        left = tk.Frame(main, bg=self.bg_dark, width=350)
        left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left.grid_propagate(False)
        self._create_controls(left)

        # Right panel - deck list
        right = tk.Frame(main, bg=self.bg_dark)
        right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self._create_deck_panel(right)

    def _create_controls(self, parent):
        """Create control panel"""
        # Header
        tk.Label(
            parent,
            text="DECK BUILDER",
            font=("Segoe UI", 14, "bold"),
            fg=self.accent,
            bg=self.bg_dark
        ).pack(pady=10)

        # Deck Info section
        info = tk.LabelFrame(parent, text="Deck Info", fg=self.accent, bg=self.bg_surface)
        info.pack(fill="x", padx=10, pady=5)

        # Name
        row = tk.Frame(info, bg=self.bg_surface)
        row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text="Name:", fg="#b0b0b0", bg=self.bg_surface, width=10, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self.deck_name, width=22).pack(side="left")

        # Format
        row = tk.Frame(info, bg=self.bg_surface)
        row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text="Format:", fg="#b0b0b0", bg=self.bg_surface, width=10, anchor="w").pack(side="left")
        ttk.Combobox(row, textvariable=self.format_var, values=list(self.FORMATS.keys()), width=20, state="readonly").pack(side="left")

        # Strategy
        row = tk.Frame(info, bg=self.bg_surface)
        row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text="Strategy:", fg="#b0b0b0", bg=self.bg_surface, width=10, anchor="w").pack(side="left")
        ttk.Combobox(row, textvariable=self.strategy_var, values=self.STRATEGIES, width=20, state="readonly").pack(side="left")

        # Colors section
        colors_frame = tk.LabelFrame(parent, text="Colors", fg=self.accent, bg=self.bg_surface)
        colors_frame.pack(fill="x", padx=10, pady=5)

        color_row = tk.Frame(colors_frame, bg=self.bg_surface)
        color_row.pack(pady=8)

        color_display = [
            ("W", "#f8f6d8", "black"),
            ("U", "#0e68ab", "white"),
            ("B", "#333333", "white"),
            ("R", "#d3202a", "white"),
            ("G", "#00733e", "white"),
        ]

        for c, bg, fg in color_display:
            tk.Checkbutton(
                color_row,
                text=c,
                variable=self.color_vars[c],
                bg=bg,
                fg=fg,
                selectcolor=bg,
                font=("Segoe UI", 10, "bold"),
                width=3
            ).pack(side="left", padx=2)

        # Commander section (for EDH format)
        cmd_frame = tk.LabelFrame(parent, text="Commander", fg=self.accent, bg=self.bg_surface)
        cmd_frame.pack(fill="x", padx=10, pady=5)

        self.commander_label = tk.Label(
            cmd_frame,
            text="None selected",
            fg="#b0b0b0",
            bg=self.bg_surface,
            font=("Segoe UI", 9)
        )
        self.commander_label.pack(side="left", padx=10, pady=5)

        tk.Button(
            cmd_frame,
            text="Set Commander",
            command=self._set_commander,
            bg="#6b21a8",
            fg="white",
            width=14
        ).pack(side="right", padx=10, pady=5)

        # Actions section
        actions = tk.LabelFrame(parent, text="Actions", fg=self.accent, bg=self.bg_surface)
        actions.pack(fill="x", padx=10, pady=5)

        btn_frame = tk.Frame(actions, bg=self.bg_surface)
        btn_frame.pack(pady=8)

        buttons = [
            ("AI Build", self._ai_build, "#4b0082", 0, 0),
            ("Add Cards", self._add_cards, "#2d5016", 0, 1),
            ("Clear", self._clear_deck, "#8b0000", 1, 0),
            ("Export", self._export_deck, "#555555", 1, 1),
            ("🛒 Sell Deck", self._sell_deck, "#d4af37", 2, 0),
        ]

        for text, cmd, color, row, col in buttons:
            tk.Button(
                btn_frame,
                text=text,
                command=cmd,
                bg=color,
                fg="white",
                width=12
            ).grid(row=row, column=col, padx=3, pady=3)

        # Status
        self.status_label = tk.Label(
            parent,
            text="Select colors and build!",
            fg="#b0b0b0",
            bg=self.bg_dark
        )
        self.status_label.pack(pady=10)

    def _create_deck_panel(self, parent):
        """Create deck list panel with card preview"""
        # Header
        header = tk.Frame(parent, bg=self.bg_dark)
        header.pack(fill="x", pady=5)

        tk.Label(
            header,
            text="DECK LIST",
            font=("Segoe UI", 14, "bold"),
            fg=self.accent,
            bg=self.bg_dark
        ).pack(side="left")

        self.deck_stats = tk.Label(
            header,
            text="0 cards",
            fg="#b0b0b0",
            bg=self.bg_dark
        )
        self.deck_stats.pack(side="right")

        # Main container - tree + preview
        container = tk.Frame(parent, bg=self.bg_dark)
        container.pack(fill="both", expand=True)

        # Left - Treeview
        tree_frame = tk.Frame(container, bg=self.bg_dark)
        tree_frame.pack(side="left", fill="both", expand=True)

        self.deck_tree = ttk.Treeview(
            tree_frame,
            columns=("qty", "name", "set_code", "box", "call_num", "price"),
            show="headings",
            height=18
        )

        self.deck_tree.heading("qty", text="Qty")
        self.deck_tree.heading("name", text="Card Name")
        self.deck_tree.heading("set_code", text="Set")
        self.deck_tree.heading("box", text="Box")
        self.deck_tree.heading("call_num", text="Call #")
        self.deck_tree.heading("price", text="Price")

        self.deck_tree.column("qty", width=35)
        self.deck_tree.column("name", width=180)
        self.deck_tree.column("set_code", width=50)
        self.deck_tree.column("box", width=50)
        self.deck_tree.column("call_num", width=70)
        self.deck_tree.column("price", width=55)

        self.deck_tree.pack(side="left", fill="both", expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.deck_tree.yview)
        self.deck_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self.deck_tree.yview_scroll(int(-1*(event.delta/120)), "units")
        self.deck_tree.bind("<MouseWheel>", _on_mousewheel)

        # Right - Card Preview
        preview_frame = tk.Frame(container, bg=self.bg_surface, width=200)
        preview_frame.pack(side="right", fill="y", padx=(5, 0))
        preview_frame.pack_propagate(False)

        tk.Label(
            preview_frame,
            text="Card Preview",
            fg=self.accent,
            bg=self.bg_surface,
            font=("Segoe UI", 9, "bold")
        ).pack(pady=3)

        self.deck_preview_img = tk.Label(preview_frame, bg=self.bg_surface, text="Click card")
        self.deck_preview_img.pack(pady=5)

        self.deck_preview_info = tk.Label(
            preview_frame,
            text="",
            fg="#b0b0b0",
            bg=self.bg_surface,
            justify="left",
            wraplength=190,
            font=("Segoe UI", 8)
        )
        self.deck_preview_info.pack(pady=3, padx=5)

        # Store image ref
        self._deck_preview_photo = None

        def on_tree_select(event):
            sel = self.deck_tree.selection()
            if not sel:
                return
            item = self.deck_tree.item(sel[0])
            values = item.get("values", [])
            if len(values) < 3:
                return
            name = values[1]
            set_code = values[2]

            # Get card data from Scryfall
            sf = None
            if self.scryfall_db:
                sf = self.scryfall_db.get_card(name, set_code)

            if sf:
                # Update info
                colors = sf.get("color_identity", [])
                type_line = sf.get("type_line", "")
                oracle = sf.get("oracle_text", "")[:150]
                self.deck_preview_info.config(
                    text=f"{name}\n{type_line}\n\n{oracle}{'...' if len(sf.get('oracle_text', '')) > 150 else ''}"
                )

                # Load image
                image_url = sf.get("image_uri", "")
                if image_url:
                    try:
                        import urllib.request
                        from PIL import Image, ImageTk
                        import io

                        with urllib.request.urlopen(image_url, timeout=5) as resp:
                            img_data = resp.read()
                        img = Image.open(io.BytesIO(img_data))
                        img = img.resize((175, 244), Image.Resampling.LANCZOS)
                        self._deck_preview_photo = ImageTk.PhotoImage(img)
                        self.deck_preview_img.config(image=self._deck_preview_photo, text="")
                    except Exception:
                        self.deck_preview_img.config(image="", text="[No image]")
            else:
                self.deck_preview_info.config(text=name)
                self.deck_preview_img.config(image="", text="[Not found]")

        self.deck_tree.bind("<<TreeviewSelect>>", on_tree_select)

    def _ai_build(self):
        """AI-powered deck building using Einstein (Claude AI)"""
        import sys
        import os
        import threading

        # Add AI module path (nexus_v2/ai)
        ai_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ai")
        if ai_path not in sys.path:
            sys.path.insert(0, ai_path)
        
        # Get selected colors
        if self.format_var.get() == "Commander":
            if not self.commander:
                messagebox.showinfo(
                    "Select Commander First",
                    "Commander defines your deck's colors.\n\n"
                    "Click 'Set Commander' to pick from your legendary creatures."
                )
                return
            selected_colors = (
                self.commander.get('color_identity', []) or
                self.commander.get('colors', []) or
                []
            )
            commander_name = self.commander.get('name')
        else:
            if not any(v.get() for v in self.color_vars.values()):
                messagebox.showinfo("Select Colors", "Please select at least one color")
                return
            selected_colors = [c for c, v in self.color_vars.items() if v.get()]
            commander_name = None
        
        # Update status
        self.status_label.config(text="Einstein is thinking... (10-25 seconds)")
        self.parent.update()
        
        def build_in_background():
            try:
                from einstein_integration import build_deck_with_einstein

                # Get all cards from library for inventory prioritization
                all_cards = []
                if hasattr(self.library, 'get_all_cards'):
                    all_cards = self.library.get_all_cards()
                elif hasattr(self.library, 'box_inventory'):
                    for box in self.library.box_inventory.values():
                        all_cards.extend(box)

                # API key from environment variable ANTHROPIC_API_KEY
                result = build_deck_with_einstein(
                    format=self.format_var.get(),
                    strategy=self.strategy_var.get().lower(),
                    colors=selected_colors,
                    commander=commander_name,
                    budget=50.00,
                    api_key=os.getenv('ANTHROPIC_API_KEY'),
                    inventory=all_cards
                )
                
                # Update UI from main thread
                self.parent.after(0, lambda: self._apply_einstein_result(result))
                
            except Exception as e:
                self.parent.after(0, lambda: self._einstein_error(str(e)))
        
        # Run in background thread
        thread = threading.Thread(target=build_in_background, daemon=True)
        thread.start()
    
    def _apply_einstein_result(self, result):
        """Apply Einstein's deck build result to the UI"""
        if not result['success']:
            messagebox.showerror("Einstein Error", result['error'])
            self.status_label.config(text="Build failed - see error")
            return
        
        # Clear current deck
        self.current_deck = []
        
        # Convert Einstein's deck list to our format
        # Build a lookup of inventory cards by name
        inventory_lookup = {}
        all_cards = []
        if hasattr(self.library, 'get_all_cards'):
            all_cards = self.library.get_all_cards()
        elif hasattr(self.library, 'box_inventory'):
            for box in self.library.box_inventory.values():
                all_cards.extend(box)
        
        for inv_card in all_cards:
            name = inv_card.get('name', '').lower()
            if name not in inventory_lookup:
                inventory_lookup[name] = []
            inventory_lookup[name].append(inv_card)
        
        for card in result['deck_list']:
            card_name = card['name']
            for _ in range(card['quantity']):
                # Try to find this card in inventory
                inv_cards = inventory_lookup.get(card_name.lower(), [])
                if inv_cards:
                    # Use the actual inventory card (has box, call_number)
                    inv_card = inv_cards.pop(0)  # Take one from inventory
                    card_data = inv_card.copy()  # Copy to not modify original
                    card_data['quantity'] = 1
                    self.current_deck.append(card_data)
                # Skip cards not in inventory - Einstein should only suggest owned cards
        
        # Update commander if provided
        if result.get('commander') and hasattr(self, 'commander_label'):
            self.commander_label.config(text=f"{result['commander']}", fg=self.accent)
        
        # Refresh the deck list display
        self._refresh_deck_list()
        
        # Store report for export
        self.last_ai_report = {
            'deck_name': result.get('deck_name', ''),
            'strategy_notes': result.get('strategy_notes', ''),
            'mana_analysis': result.get('mana_analysis', ''),
            'viability_report': result.get('viability_report', ''),
            'total_cards': result.get('total_cards', 0),
            'total_price': result.get('total_price', 0),
            'build_time': result.get('build_time', 0)
        }
        
        # Update status with results
        self.status_label.config(
            text=f"Einstein: '{result['deck_name']}' - {result['total_cards']} cards, ${result['total_price']:.2f} ({result['build_time']:.1f}s)"
        )
        
        # Show viability report in a popup
        if result.get('viability_report'):
            self._show_viability_report(result)
    
    def _show_viability_report(self, result):
        """Show Einstein's viability report in a popup"""
        report_window = tk.Toplevel(self.parent)
        report_window.title(f"Deck Analysis: {result['deck_name']}")
        report_window.geometry("600x500")
        report_window.configure(bg=self.bg_dark)
        
        # Header
        tk.Label(
            report_window,
            text=result['deck_name'],
            font=("Segoe UI", 16, "bold"),
            fg=self.accent,
            bg=self.bg_dark
        ).pack(pady=10)
        
        # Stats row
        stats_frame = tk.Frame(report_window, bg=self.bg_surface)
        stats_frame.pack(fill="x", padx=20, pady=5)
        
        tk.Label(stats_frame, text=f"Cards: {result['total_cards']}", fg="white", bg=self.bg_surface, font=("Segoe UI", 11)).pack(side="left", padx=20)
        tk.Label(stats_frame, text=f"Value: ${result['total_price']:.2f}", fg="#4CAF50", bg=self.bg_surface, font=("Segoe UI", 11)).pack(side="left", padx=20)
        tk.Label(stats_frame, text=f"Built in: {result['build_time']:.1f}s", fg="#2196F3", bg=self.bg_surface, font=("Segoe UI", 11)).pack(side="left", padx=20)
        
        # Strategy notes
        if result.get('strategy_notes'):
            tk.Label(report_window, text="Strategy:", fg=self.accent, bg=self.bg_dark, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=20, pady=(15,5))
            strategy_text = tk.Text(report_window, height=3, wrap="word", bg=self.bg_surface, fg="white", font=("Segoe UI", 10))
            strategy_text.pack(fill="x", padx=20)
            strategy_text.insert("1.0", result['strategy_notes'].strip())
            strategy_text.config(state="disabled")
        
        # Mana analysis
        if result.get('mana_analysis'):
            tk.Label(report_window, text="Mana Base:", fg=self.accent, bg=self.bg_dark, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=20, pady=(15,5))
            mana_text = tk.Text(report_window, height=4, wrap="word", bg=self.bg_surface, fg="white", font=("Segoe UI", 10))
            mana_text.pack(fill="x", padx=20)
            mana_text.insert("1.0", result['mana_analysis'].strip())
            mana_text.config(state="disabled")
        
        # Viability report
        if result.get('viability_report'):
            tk.Label(report_window, text="Competitive Viability:", fg=self.accent, bg=self.bg_dark, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=20, pady=(15,5))
            viability_text = tk.Text(report_window, height=10, wrap="word", bg=self.bg_surface, fg="white", font=("Segoe UI", 10))
            viability_text.pack(fill="both", expand=True, padx=20, pady=(0,10))
            viability_text.insert("1.0", result['viability_report'].strip())
            viability_text.config(state="disabled")
        
        # Close button
        tk.Button(
            report_window,
            text="Close",
            command=report_window.destroy,
            bg="#555555",
            fg="white",
            font=("Segoe UI", 11)
        ).pack(pady=10)
    
    def _einstein_error(self, error_msg):
        """Handle Einstein build error"""
        messagebox.showerror("Einstein Error", f"AI deck build failed:\n\n{error_msg}")
        self.status_label.config(text="Build failed - check API key")

    def _add_cards(self):
        """Open dialog to add cards"""
        if not self.library:
            messagebox.showwarning("No Library", "No card library available")
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title("Add Cards")
        dialog.geometry("400x350")
        dialog.configure(bg=self.bg_dark)

        # Search entry
        search_var = tk.StringVar()
        tk.Entry(dialog, textvariable=search_var, width=40).pack(pady=10)

        # Results listbox
        listbox = tk.Listbox(dialog, width=50, height=12)
        listbox.pack(fill="both", expand=True, padx=10)

        card_data = []

        def search(*args):
            query = search_var.get().lower()
            listbox.delete(0, tk.END)
            card_data.clear()

            if len(query) < 2:
                return

            # Use SQLite search if available (faster), else fallback to box_inventory
            if hasattr(self.library, 'db') and self.library.db:
                results = self.library.db.search_by_name(query, limit=50)
                for card in results:
                    listbox.insert(tk.END, f"{card.get('name')} [{card.get('set_code', 'N/A')}]")
                    card_data.append(card)
            elif hasattr(self.library, 'box_inventory'):
                for cards in self.library.box_inventory.values():
                    for card in cards:
                        if query in card.get("name", "").lower():
                            listbox.insert(tk.END, f"{card.get('name')} [{card.get('set', 'N/A')}]")
                            card_data.append(card)
                            if len(card_data) >= 50:
                                return

        search_var.trace("w", search)

        def add_selected():
            sel = listbox.curselection()
            if sel and card_data:
                self.current_deck.append(card_data[sel[0]])
                self._refresh_deck_list()

        tk.Button(dialog, text="Add to Deck", command=add_selected, bg="#2d5016", fg="white").pack(pady=5)

    def _set_commander(self):
        """Select a commander from your ENTIRE collection (not just deck)"""
        if not self.library:
            messagebox.showwarning("No Library", "No card library available")
            return

        if not self.scryfall_db:
            messagebox.showwarning("No Scryfall", "Scryfall database not loaded")
            return

        # Show loading message
        self.status_label.config(text="Loading commanders... please wait")
        self.parent.update()
        
        import threading
        
        def load_mythics():
            # Get ALL legendary creatures from Scryfall DB in one query
            all_legends = []
            if self.scryfall_db:
                try:
                    all_legends = self.scryfall_db.get_legendary_creatures(limit=50000)
                except:
                    pass
            
            # Build set of legendary creature names (lowercase for matching)
            legend_names = {c.get("name", "").lower() for c in all_legends}
            
            # Get user's cards
            all_cards = []
            if hasattr(self.library, 'get_all_cards'):
                all_cards = self.library.get_all_cards()
            elif hasattr(self.library, 'box_inventory'):
                for box in self.library.box_inventory.values():
                    all_cards.extend(box)

            # Filter to legendary creatures user owns
            mythics = []
            seen = set()
            for card in all_cards:
                name = card.get("name", "")
                # Dedupe by NAME only
                if name.lower() in seen:
                    continue
                
                # Check if it's a legendary creature
                if name.lower() in legend_names:
                    seen.add(name.lower())
                    mythics.append(card)
            
            # Update UI from main thread
            self.parent.after(0, lambda: self._show_commander_dialog(mythics))
        
        threading.Thread(target=load_mythics, daemon=True).start()
    
    def _show_commander_dialog(self, mythics):
        """Show commander selection dialog (called from main thread)"""
        self.status_label.config(text="Select colors and build!")
        
        if not mythics:
            messagebox.showinfo("No Commanders", "No legendary creatures found in your collection")
            return

        # Selection dialog with search and card preview
        dialog = tk.Toplevel(self.parent)
        dialog.title("Select Commander")
        dialog.geometry("750x500")
        dialog.configure(bg=self.bg_dark)

        # Main container - two columns
        main_frame = tk.Frame(dialog, bg=self.bg_dark)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left side - search and list
        left_frame = tk.Frame(main_frame, bg=self.bg_dark)
        left_frame.pack(side="left", fill="both", expand=True)

        tk.Label(
            left_frame,
            text="Search Your Legendary Creatures:",
            fg=self.accent,
            bg=self.bg_dark,
            font=("Segoe UI", 11, "bold")
        ).pack(pady=5)

        # Search box
        search_var = tk.StringVar()
        tk.Entry(left_frame, textvariable=search_var, width=40).pack(pady=5)

        # Results listbox
        listbox = tk.Listbox(left_frame, width=45, height=15)
        listbox.pack(fill="both", expand=True, pady=5)

        # Right side - card preview
        right_frame = tk.Frame(main_frame, bg=self.bg_surface, width=250)
        right_frame.pack(side="right", fill="y", padx=(10, 0))
        right_frame.pack_propagate(False)

        tk.Label(
            right_frame,
            text="Card Preview",
            fg=self.accent,
            bg=self.bg_surface,
            font=("Segoe UI", 10, "bold")
        ).pack(pady=5)

        # Image label
        preview_label = tk.Label(right_frame, bg=self.bg_surface, text="Select a card")
        preview_label.pack(pady=10)

        # Card info
        info_label = tk.Label(
            right_frame,
            text="",
            fg="#b0b0b0",
            bg=self.bg_surface,
            justify="left",
            wraplength=230
        )
        info_label.pack(pady=5, padx=5)

        # Store image reference to prevent garbage collection
        dialog._preview_image = None

        def show_preview(event=None):
            sel = listbox.curselection()
            if not sel or not filtered_mythics:
                return
            card = filtered_mythics[sel[0]]
            name = card.get("name", "")
            set_code = card.get("set_code", "")

            # Get full card data from Scryfall (fast local DB lookup)
            sf = self.scryfall_db.get_card(name, set_code) if self.scryfall_db else None
            
            # Store color identity on card for later use
            if sf and not card.get("color_identity"):
                card["color_identity"] = sf.get("color_identity", [])

            # Update info immediately
            colors = card.get("color_identity", []) or []
            price = card.get("price") or card.get("price_usd") or 0
            type_line = sf.get("type_line", "") if sf else ""
            oracle = sf.get("oracle_text", "")[:200] if sf else ""
            info_label.config(
                text=f"{name}\n{set_code.upper()}\n\n"
                     f"Colors: {''.join(colors) or 'Colorless'}\n"
                     f"Price: ${price:.2f}\n\n"
                     f"{type_line}\n\n"
                     f"{oracle}{'...' if sf and len(sf.get('oracle_text', '')) > 200 else ''}"
            )
            preview_label.config(image="", text="Loading...")

            # Load image in background thread
            if sf:
                image_url = sf.get("image_uri") or ""
                if image_url:
                    def load_image():
                        try:
                            import urllib.request
                            from PIL import Image, ImageTk
                            import io
                            with urllib.request.urlopen(image_url, timeout=5) as response:
                                img_data = response.read()
                            img = Image.open(io.BytesIO(img_data))
                            img = img.resize((220, 307), Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(img)
                            # Update UI from main thread
                            dialog.after(0, lambda p=photo: _update_preview_image(p))
                        except Exception:
                            dialog.after(0, lambda: preview_label.config(image="", text="[Image unavailable]"))
                    
                    import threading
                    threading.Thread(target=load_image, daemon=True).start()
                else:
                    preview_label.config(image="", text="[No image]")

        listbox.bind("<<ListboxSelect>>", show_preview)
        
        def _update_preview_image(photo):
            """Helper to update preview from main thread"""
            try:
                dialog._preview_image = photo
                preview_label.config(image=photo, text="")
            except tk.TclError:
                pass  # Dialog closed

        filtered_mythics = []

        def update_list(*args):
            query = search_var.get().lower()
            listbox.delete(0, tk.END)
            filtered_mythics.clear()

            for card in mythics:
                name = card.get("name", "")
                if query in name.lower() or not query:
                    set_code = card.get("set_code") or card.get("set", "")
                    colors = card.get("color_identity", []) or card.get("colors", [])
                    color_str = "".join(colors) if colors else "C"
                    price = card.get("price") or card.get("price_usd") or 0
                    box = card.get("box", "?")
                    call_num = card.get("call_number", "")
                    listbox.insert(
                        tk.END,
                        f"{name} [{set_code.upper()}] ({color_str}) ${price:.2f} | Box: {box} {call_num}"
                    )
                    filtered_mythics.append(card)
                    if len(filtered_mythics) >= 100:
                        break

        search_var.trace("w", update_list)
        update_list()  # Initial population

        def select():
            sel = listbox.curselection()
            if sel and filtered_mythics:
                self.commander = filtered_mythics[sel[0]]
                name = self.commander.get("name", "Unknown")
                colors = self.commander.get("color_identity", []) or []
                color_str = "".join(colors) if colors else "Colorless"
                self.commander_label.config(text=f"{name} ({color_str})", fg=self.accent)
                self.status_label.config(text=f"Commander set! Click AI Build for 99.")
                # Auto-set color checkboxes to match commander
                for c in "WUBRG":
                    self.color_vars[c].set(c in colors)
                dialog.destroy()

        tk.Button(
            dialog, text="Set as Commander", command=select, bg="#6b21a8", fg="white"
        ).pack(pady=10)

    def _clear_deck(self):
        """Clear the current deck"""
        if self.current_deck:
            self.current_deck = []
            self.commander = None
            self.commander_label.config(text="None selected", fg="#b0b0b0")
            self._refresh_deck_list()
            self.status_label.config(text="Deck cleared")

    def _export_deck(self):
        """Export deck to file with set codes"""
        if not self.current_deck:
            messagebox.showwarning("Empty Deck", "No cards in deck to export")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"// {self.deck_name.get()}\n")
                f.write(f"// Format: {self.format_var.get()}\n")

                # Commander section for EDH format
                if self.format_var.get() == "Commander":
                    if self.commander:
                        cmd = self.commander
                        cmd_set = cmd.get("set_code") or cmd.get("set", "")
                        cmd_num = cmd.get("collector_number", "")
                        cmd_name = cmd.get("name", "Unknown")
                        if cmd_set and cmd_num:
                            f.write(f"\n// Commander\n")
                            f.write(f"1 {cmd_name} ({cmd_set.upper()}) {cmd_num}\n")
                        elif cmd_set:
                            f.write(f"\n// Commander\n")
                            f.write(f"1 {cmd_name} ({cmd_set.upper()})\n")
                        else:
                            f.write(f"\n// Commander\n")
                            f.write(f"1 {cmd_name}\n")
                    else:
                        f.write(f"\n// Commander: NOT SET\n")

                f.write(f"\n// Deck\n")

                # Group by name + set (different printings separate)
                groups = defaultdict(list)
                for card in self.current_deck:
                    # Skip commander from main list
                    if self.commander and card.get("name") == self.commander.get("name"):
                        continue
                    set_code = card.get("set_code") or card.get("set", "")
                    col_num = card.get("collector_number", "")
                    key = (card.get("name", "Unknown"), set_code, col_num)
                    groups[key].append(card)

                # Export format: 4 Lightning Bolt (LEA) 161
                for (name, set_code, col_num), cards in sorted(groups.items()):
                    count = len(cards)
                    if set_code and col_num:
                        f.write(f"{count} {name} ({set_code.upper()}) {col_num}\n")
                    elif set_code:
                        f.write(f"{count} {name} ({set_code.upper()})\n")
                    else:
                        f.write(f"{count} {name}\n")

            messagebox.showinfo("Exported", f"Deck saved to {filename}")

    def _sell_deck(self):
        """Sell the current deck - removes cards from inventory and creates sale record"""
        import sqlite3
        from datetime import datetime
        
        if not self.current_deck:
            messagebox.showwarning("Empty Deck", "No cards in deck to sell")
            return
        
        # Calculate total value
        total_value = 0.0
        card_counts = defaultdict(int)
        for card in self.current_deck:
            price = card.get('price') or card.get('price_usd') or 0
            total_value += float(price) if price else 0
            card_counts[card.get('name', 'Unknown')] += 1
        
        # Confirmation dialog
        deck_name = self.deck_name.get()
        card_count = len(self.current_deck)
        unique_cards = len(card_counts)
        
        confirm = messagebox.askyesno(
            "Confirm Sale",
            f"SELL THIS DECK?\n\n"
            f"Deck: {deck_name}\n"
            f"Cards: {card_count} ({unique_cards} unique)\n"
            f"Total Value: ${total_value:.2f}\n\n"
            f"This will REMOVE cards from inventory.\n"
            f"This action cannot be undone."
        )
        
        if not confirm:
            return

        # Connect to DANIELSON library API
        try:
            # Get DANIELSON URL from config
            try:
                config = get_config()
                danielson_url = config.get('library.danielson_url', 'http://192.168.1.219:5001')
            except:
                danielson_url = 'http://192.168.1.219:5001'

            brock = BrockLibraryClient(danielson_url)

            # Check if DANIELSON is online
            if not brock.is_online():
                messagebox.showerror(
                    "DANIELSON Offline",
                    f"Cannot connect to DANIELSON library server at {danielson_url}\n\n"
                    "Make sure DANIELSON is running and try again."
                )
                return

            removed_count = 0
            failed_cards = []

            # Remove cards from DANIELSON inventory via API
            for card in self.current_deck:
                card_name = card.get('name', '')
                set_code = card.get('set_code') or card.get('set', '')

                # Search for card in DANIELSON inventory
                search_results = brock.search(name=card_name, set_code=set_code, limit=1)

                if search_results and len(search_results) > 0:
                    # Found card - get call number and delete it
                    call_number = search_results[0].get('call_number')
                    if call_number and brock.delete(call_number):
                        removed_count += 1
                    else:
                        failed_cards.append(card_name)
                else:
                    # Try searching by name only
                    search_results = brock.search(name=card_name, limit=1)
                    if search_results and len(search_results) > 0:
                        call_number = search_results[0].get('call_number')
                        if call_number and brock.delete(call_number):
                            removed_count += 1
                        else:
                            failed_cards.append(card_name)
                    else:
                        failed_cards.append(card_name)

            # Log the sale to local file
            try:
                # Use config-based path or default to project data dir
                try:
                    config = get_config()
                    data_dir = Path(config.get('data_dir', Path.home() / '.nexus' / 'data'))
                except:
                    data_dir = Path.home() / '.nexus' / 'data'

                sale_log_path = data_dir / 'sales_log.txt'
                sale_log_path.parent.mkdir(parents=True, exist_ok=True)

                with open(sale_log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*50}\n")
                    f.write(f"SALE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Deck: {deck_name}\n")
                    f.write(f"Format: {self.format_var.get()}\n")
                    f.write(f"Cards: {card_count}\n")
                    f.write(f"Value: ${total_value:.2f}\n")
                    f.write(f"Removed from inventory: {removed_count}\n")
                    if failed_cards:
                        f.write(f"Not found in inventory: {', '.join(failed_cards[:10])}\n")
                    f.write(f"{'='*50}\n")
            except Exception as log_err:
                print(f"Could not write sale log: {log_err}")
            
            # ==========================================
            # PHONE HOME TO NEXUS HQ
            # ==========================================
            hq_result = None
            try:
                from phone_home import report_deck_sale
                
                # Build card list for HQ
                cards_list = []
                for name, count in card_counts.items():
                    cards_list.append({'name': name, 'qty': count})
                
                hq_result = report_deck_sale(
                    deck_name=deck_name,
                    format=self.format_var.get(),
                    card_count=card_count,
                    sale_value=total_value,
                    cards=cards_list
                )
                
                if hq_result.get('success'):
                    print(f"📡 Phoned home: ${total_value:.2f} → NEXUS fee: ${hq_result.get('nexus_fee', 0):.2f}")
                else:
                    print(f"⚠️ Phone home failed: {hq_result.get('error', 'Unknown')}")
                    
            except Exception as hq_err:
                print(f"⚠️ Could not phone home: {hq_err}")
            
            # Show result
            result_msg = f"SALE COMPLETE!\n\n"
            result_msg += f"Deck: {deck_name}\n"
            result_msg += f"Value: ${total_value:.2f}\n"
            result_msg += f"Removed {removed_count} cards from inventory\n"
            
            if failed_cards:
                result_msg += f"\n⚠️ {len(failed_cards)} cards not found in inventory"
            
            messagebox.showinfo("Sale Complete", result_msg)
            
            # Clear the deck
            self._clear_deck()
            self.status_label.config(text=f"SOLD: {deck_name} for ${total_value:.2f}")
            
        except Exception as e:
            messagebox.showerror("Sale Error", f"Failed to process sale:\n\n{str(e)}")

    def _refresh_deck_list(self):
        """Refresh the deck list display"""
        self.deck_tree.delete(*self.deck_tree.get_children())

        # Group by card name + set (different printings are separate)
        groups = defaultdict(list)
        for card in self.current_deck:
            set_code = card.get("set_code") or card.get("set", "")
            key = (card.get("name", "Unknown"), set_code)
            groups[key].append(card)

        # Calculate total value
        total_value = 0.0

        # Add to treeview
        for (name, set_code), cards in sorted(groups.items()):
            card = cards[0]
            set_name = card.get("set_name", "")
            price = card.get("price") or card.get("price_usd") or 0
            box = card.get("box", "?")
            call_num = card.get("call_number", "")
            total_value += price * len(cards)

            self.deck_tree.insert("", "end", values=(
                len(cards),
                name,
                set_code.upper() if set_code else "N/A",
                box,
                call_num,
                f"${price:.2f}" if price else "—"
            ))

        self.deck_stats.config(text=f"{len(self.current_deck)} cards | ${total_value:.2f}")


# Alias for compatibility
DeckBuilderTabPro = DeckBuilderTab
