#!/usr/bin/env python3
"""
NEXUS Pro Deck Builder Tab
Complete redesign using the Pro Theme system
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from collections import defaultdict

# Import theme system
try:
    from nexus_pro_theme import NexusProTheme, Colors, Typography, Spacing, ButtonStyle, ButtonSize
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False
    print("⚠️ Pro theme not available")

# Import mana curve visualization
try:
    from mana_curve_viz import ManaCurveWidget, ManaCurveAnalyzer, ColorDistributionWidget
    CURVE_VIZ_AVAILABLE = True
except ImportError:
    CURVE_VIZ_AVAILABLE = False
    print("⚠️ Mana curve visualization not available")


class DeckBuilderTabPro:
    """Professional deck builder tab with clean UI"""
    
    FORMATS = ["Commander", "Standard", "Modern", "Pioneer", "Legacy", "Vintage", "Pauper", "Brawl"]
    STRATEGIES = ["balanced", "aggro", "control", "combo", "midrange", "tempo"]
    COLORS = [("White", "W"), ("Blue", "U"), ("Black", "B"), ("Red", "R"), ("Green", "G")]
    
    def __init__(self, notebook: ttk.Notebook, theme: NexusProTheme, nexus_app):
        """
        Args:
            notebook: The main ttk.Notebook widget
            theme: NexusProTheme instance
            nexus_app: Reference to main NEXUS app for accessing deck builder engine
        """
        self.notebook = notebook
        self.theme = theme
        self.app = nexus_app
        
        # State
        self.current_deck = []
        self.collection_loaded = False
        
        # Create the tab
        self._create_tab()
    
    def _create_tab(self):
        """Create the deck builder tab"""
        # Main frame
        self.frame = self.theme.tab_frame(self.notebook)
        self.notebook.add(self.frame, text="Deck Builder")

        # Header (fixed at top)
        header_frame = self.theme.frame(self.frame)
        header_frame.pack(fill="x", padx=Spacing.LG, pady=Spacing.MD)
        self.theme.header(header_frame, "Deck Builder & Testing Suite",
                         "Build optimized decks from your collection")

        # Scrollable content area
        import tkinter as tk
        canvas = tk.Canvas(self.frame, bg='#4a4a4a', highlightthickness=0)
        scrollbar = tk.Scrollbar(self.frame, orient='vertical', command=canvas.yview)
        content = self.theme.frame(canvas)

        content.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=content, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True, padx=Spacing.LG)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Main layout: Left controls, Right output
        main_container = self.theme.frame(content)
        main_container.pack(fill="both", expand=True, pady=Spacing.MD)
        
        # Configure grid
        main_container.columnconfigure(0, weight=1, minsize=380)
        main_container.columnconfigure(1, weight=2)
        main_container.rowconfigure(0, weight=1)
        
        # Left column - Controls
        left_col = self.theme.frame(main_container)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, Spacing.MD))
        self._create_controls(left_col)
        
        # Right column - Output
        right_col = self.theme.frame(main_container)
        right_col.grid(row=0, column=1, sticky="nsew")
        self._create_output(right_col)
    
    def _create_controls(self, parent):
        """Create the control panel"""
        # ═══════════════════════════════════════════════════════════════
        # FORMAT & STRATEGY SECTION
        # ═══════════════════════════════════════════════════════════════
        format_section = self.theme.section(parent, "Format & Strategy")
        format_section.pack(fill="x", pady=(0, Spacing.MD))
        
        format_content = self.theme.frame(format_section)
        format_content.pack(fill="x", padx=Spacing.MD, pady=Spacing.MD)
        
        # Format row
        format_row = self.theme.frame(format_content)
        format_row.pack(fill="x", pady=Spacing.XS)
        
        self.theme.label(format_row, "Format:", width=10).pack(side="left")
        self.format_var = tk.StringVar(value="Commander")
        format_combo = self.theme.combobox(format_row, 
                                           textvariable=self.format_var,
                                           values=self.FORMATS,
                                           width=15)
        format_combo.pack(side="left", padx=Spacing.SM)
        
        # Strategy row
        strategy_row = self.theme.frame(format_content)
        strategy_row.pack(fill="x", pady=Spacing.XS)
        
        self.theme.label(strategy_row, "Strategy:", width=10).pack(side="left")
        self.strategy_var = tk.StringVar(value="balanced")
        strategy_combo = self.theme.combobox(strategy_row,
                                             textvariable=self.strategy_var,
                                             values=self.STRATEGIES,
                                             width=15)
        strategy_combo.pack(side="left", padx=Spacing.SM)
        
        # Test games row
        games_row = self.theme.frame(format_content)
        games_row.pack(fill="x", pady=Spacing.XS)
        
        self.theme.label(games_row, "Test Games:", width=10).pack(side="left")
        self.test_games_var = tk.IntVar(value=1000)
        games_spin = self.theme.spinbox(games_row,
                                        from_=100, to=10000,
                                        textvariable=self.test_games_var,
                                        width=10)
        games_spin.pack(side="left", padx=Spacing.SM)
        
        # ═══════════════════════════════════════════════════════════════
        # COLOR SELECTION SECTION
        # ═══════════════════════════════════════════════════════════════
        color_section = self.theme.section(parent, "Color Identity")
        color_section.pack(fill="x", pady=(0, Spacing.MD))
        
        color_content = self.theme.frame(color_section)
        color_content.pack(fill="x", padx=Spacing.MD, pady=Spacing.MD)
        
        # Color checkboxes
        self.color_vars = {}
        color_row = self.theme.frame(color_content)
        color_row.pack(fill="x")
        
        for color_name, color_code in self.COLORS:
            var = tk.BooleanVar(value=False)
            self.color_vars[color_code] = var
            cb = self.theme.checkbox(color_row, text=color_name, variable=var)
            cb.pack(side="left", padx=Spacing.SM)
        
        # All colors button
        all_btn = self.theme.button(color_row, text="All", 
                                    style=ButtonStyle.GHOST, size=ButtonSize.SM,
                                    command=self._select_all_colors)
        all_btn.pack(side="right")
        
        # ═══════════════════════════════════════════════════════════════
        # BUILD ACTIONS SECTION
        # ═══════════════════════════════════════════════════════════════
        build_section = self.theme.section(parent, "Build Actions")
        build_section.pack(fill="x", pady=(0, Spacing.MD))
        
        build_content = self.theme.frame(build_section)
        build_content.pack(fill="x", padx=Spacing.MD, pady=Spacing.MD)
        
        # Primary actions row
        primary_row = self.theme.frame(build_content)
        primary_row.pack(fill="x", pady=Spacing.XS)
        
        self.theme.button(primary_row, text="Load Collection",
                         style=ButtonStyle.GHOST, size=ButtonSize.MD,
                         command=self._load_collection).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(primary_row, text="Build Deck",
                         style=ButtonStyle.PRIMARY, size=ButtonSize.MD,
                         command=self._build_deck).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(primary_row, text="Batch Build",
                         style=ButtonStyle.SECONDARY, size=ButtonSize.MD,
                         command=self._batch_build).pack(side="left")
        
        # Secondary actions row
        secondary_row = self.theme.frame(build_content)
        secondary_row.pack(fill="x", pady=Spacing.XS)
        
        self.theme.button(secondary_row, text="Import Deck",
                         style=ButtonStyle.GHOST, size=ButtonSize.MD,
                         command=self._import_deck).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(secondary_row, text="AI Optimize",
                         style=ButtonStyle.WARNING, size=ButtonSize.MD,
                         command=self._ai_optimize).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(secondary_row, text="Show Value",
                         style=ButtonStyle.INFO, size=ButtonSize.MD,
                         command=self._show_value).pack(side="left")
        
        # ═══════════════════════════════════════════════════════════════
        # TESTING SECTION
        # ═══════════════════════════════════════════════════════════════
        test_section = self.theme.section(parent, "Deck Testing")
        test_section.pack(fill="x", pady=(0, Spacing.MD))
        
        test_content = self.theme.frame(test_section)
        test_content.pack(fill="x", padx=Spacing.MD, pady=Spacing.MD)
        
        # Mulligan option
        mulligan_row = self.theme.frame(test_content)
        mulligan_row.pack(fill="x", pady=Spacing.XS)
        
        self.mulligan_var = tk.BooleanVar(value=True)
        self.theme.checkbox(mulligan_row, text="Enable Mulligans",
                           variable=self.mulligan_var).pack(side="left")
        
        # Test buttons
        test_row = self.theme.frame(test_content)
        test_row.pack(fill="x", pady=Spacing.XS)
        
        self.theme.button(test_row, text="Goldfish",
                         style=ButtonStyle.SECONDARY, size=ButtonSize.SM,
                         command=self._goldfish_test).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(test_row, text="Combat Sim",
                         style=ButtonStyle.DANGER, size=ButtonSize.SM,
                         command=self._combat_sim).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(test_row, text="Mana Analysis",
                         style=ButtonStyle.SUCCESS, size=ButtonSize.SM,
                         command=self._mana_analysis).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(test_row, text="Meta",
                         style=ButtonStyle.GHOST, size=ButtonSize.SM,
                         command=self._meta_analysis).pack(side="left")
        
        # ═══════════════════════════════════════════════════════════════
        # SAVE/EXPORT SECTION
        # ═══════════════════════════════════════════════════════════════
        save_section = self.theme.section(parent, "Save & Export")
        save_section.pack(fill="x", pady=(0, Spacing.MD))
        
        save_content = self.theme.frame(save_section)
        save_content.pack(fill="x", padx=Spacing.MD, pady=Spacing.MD)
        
        save_row = self.theme.frame(save_content)
        save_row.pack(fill="x")
        
        self.theme.button(save_row, text="Save Deck",
                         style=ButtonStyle.SUCCESS, size=ButtonSize.MD,
                         command=self._save_deck).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(save_row, text="Mark as Built",
                         style=ButtonStyle.PRIMARY, size=ButtonSize.MD,
                         command=self._mark_built).pack(side="left", padx=(0, Spacing.SM))
        
        self.theme.button(save_row, text="Deck Copies",
                         style=ButtonStyle.GHOST, size=ButtonSize.MD,
                         command=self._deck_copies).pack(side="left")
        
        # ═══════════════════════════════════════════════════════════════
        # MANA CURVE VISUALIZATION (if available)
        # ═══════════════════════════════════════════════════════════════
        if CURVE_VIZ_AVAILABLE:
            curve_section = self.theme.section(parent, "Mana Curve")
            curve_section.pack(fill="x", pady=(0, Spacing.MD))
            
            self.curve_widget = ManaCurveWidget(curve_section,
                                                bg=Colors.BG_CARD,
                                                fg=Colors.TEXT_PRIMARY,
                                                accent=Colors.GOLD)
            self.curve_widget.pack(fill="x", padx=Spacing.MD, pady=Spacing.MD)
        else:
            self.curve_widget = None
        
        # ═══════════════════════════════════════════════════════════════
        # STATUS
        # ═══════════════════════════════════════════════════════════════
        status_section = self.theme.section(parent, "Status")
        status_section.pack(fill="x")
        
        status_content = self.theme.frame(status_section)
        status_content.pack(fill="x", padx=Spacing.MD, pady=Spacing.MD)
        
        self.theme.status_row(status_content, "Collection", "Not loaded", "offline")
        self.collection_status = status_content.winfo_children()[-1]  # Get the status row
        
        self.theme.status_row(status_content, "Current Deck", "None", "offline")
        self.deck_status = status_content.winfo_children()[-1]
    
    def _create_output(self, parent):
        """Create the output panel"""
        # Tabbed output
        output_notebook = self.theme.notebook(parent)
        output_notebook.pack(fill="both", expand=True)
        
        # ═══════════════════════════════════════════════════════════════
        # DECK LIST TAB
        # ═══════════════════════════════════════════════════════════════
        deck_tab = self.theme.tab_frame(output_notebook)
        output_notebook.add(deck_tab, text="Deck List")
        
        self.deck_output = self.theme.console(deck_tab, height=30)
        self.deck_output.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)
        
        # Welcome message
        welcome = """╔══════════════════════════════════════════════════════════════╗
║           UNIFIED DECK BUILDER & TESTING SUITE               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  DECK BUILDING                                               ║
║  ─────────────                                               ║
║  • Multi-format: Commander, Standard, Modern, Pioneer,       ║
║    Legacy, Vintage, Pauper, Brawl                           ║
║  • 6 strategies: balanced, aggro, control, combo,           ║
║    midrange, tempo                                          ║
║  • Smart color filtering                                     ║
║  • AI-powered optimization                                   ║
║  • Real-time Scryfall pricing                               ║
║                                                              ║
║  DECK TESTING                                                ║
║  ────────────                                                ║
║  • Goldfish testing for speed/consistency                   ║
║  • Combat simulation vs meta archetypes                     ║
║  • Mana curve analysis                                       ║
║  • Meta comparison                                           ║
║                                                              ║
║  WORKFLOW                                                    ║
║  ────────                                                    ║
║  1. Load your collection                                     ║
║  2. Select format, strategy, colors                         ║
║  3. Build deck or import existing                           ║
║  4. Run tests and optimize                                  ║
║  5. Save your final deck                                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Load your collection to get started!
"""
        self.deck_output.insert("1.0", welcome)
        
        # ═══════════════════════════════════════════════════════════════
        # TEST RESULTS TAB
        # ═══════════════════════════════════════════════════════════════
        test_tab = self.theme.tab_frame(output_notebook)
        output_notebook.add(test_tab, text="Test Results")
        
        self.test_output = self.theme.console(test_tab, height=30)
        self.test_output.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)
        
        test_welcome = """╔══════════════════════════════════════════════════════════════╗
║                    DECK TESTING RESULTS                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Run tests using the buttons on the left to see results.    ║
║                                                              ║
║  AVAILABLE TESTS                                             ║
║  ───────────────                                             ║
║  • Goldfish    - Simulate games without opponent            ║
║  • Combat Sim  - Test against meta decks                    ║
║  • Mana Curve  - Analyze mana distribution                  ║
║  • Meta        - Compare against current meta               ║
║                                                              ║
║  Build or import a deck first, then run tests!              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        self.test_output.insert("1.0", test_welcome)
    
    # ═══════════════════════════════════════════════════════════════════════
    # ACTION HANDLERS
    # ═══════════════════════════════════════════════════════════════════════
    
    def _select_all_colors(self):
        """Select all colors"""
        for var in self.color_vars.values():
            var.set(True)
    
    def _get_selected_colors(self):
        """Get list of selected color codes"""
        return [code for code, var in self.color_vars.items() if var.get()]
    
    def _load_collection(self):
        """Load collection - delegates to main app"""
        if hasattr(self.app, 'unified_load_collection'):
            self.app.unified_load_collection()
            self._update_collection_status()
    
    def _build_deck(self):
        """Build deck - delegates to main app"""
        if hasattr(self.app, 'unified_build_deck'):
            # Update app's variables from our UI
            self.app.unified_format_var.set(self.format_var.get())
            self.app.unified_strategy_var.set(self.strategy_var.get())
            
            # Update color vars
            for code, var in self.color_vars.items():
                if code in self.app.unified_colors_vars:
                    self.app.unified_colors_vars[code].set(var.get())
            
            self.app.unified_build_deck()
            self._update_deck_status()
            self._update_curve()
    
    def _batch_build(self):
        """Batch build - delegates to main app"""
        if hasattr(self.app, 'unified_batch_build_deck'):
            self.app.unified_batch_build_deck()
    
    def _import_deck(self):
        """Import deck - delegates to main app"""
        if hasattr(self.app, 'unified_import_deck'):
            self.app.unified_import_deck()
            self._update_deck_status()
            self._update_curve()
    
    def _ai_optimize(self):
        """AI optimize - delegates to main app"""
        if hasattr(self.app, 'unified_ai_optimize'):
            self.app.unified_ai_optimize()
            self._update_curve()
    
    def _show_value(self):
        """Show value - delegates to main app"""
        if hasattr(self.app, 'unified_show_value'):
            self.app.unified_show_value()
    
    def _goldfish_test(self):
        """Run goldfish test - delegates to main app"""
        if hasattr(self.app, 'run_goldfish_test'):
            self.app.run_goldfish_test()
    
    def _combat_sim(self):
        """Run combat simulation - delegates to main app"""
        if hasattr(self.app, 'run_combat_sim'):
            self.app.run_combat_sim()
    
    def _mana_analysis(self):
        """Run mana analysis - delegates to main app"""
        if hasattr(self.app, 'analyze_mana_base'):
            self.app.analyze_mana_base()
    
    def _meta_analysis(self):
        """Run meta analysis - delegates to main app"""
        if hasattr(self.app, 'meta_analysis'):
            self.app.meta_analysis()
    
    def _save_deck(self):
        """Save deck - delegates to main app"""
        if hasattr(self.app, 'unified_save_deck'):
            self.app.unified_save_deck()
    
    def _mark_built(self):
        """Mark deck as built - delegates to main app"""
        if hasattr(self.app, 'mark_deck_as_built'):
            self.app.mark_deck_as_built()
    
    def _deck_copies(self):
        """Show deck copies - delegates to main app"""
        if hasattr(self.app, 'unified_deck_copies'):
            self.app.unified_deck_copies()
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATUS UPDATES
    # ═══════════════════════════════════════════════════════════════════════
    
    def _update_collection_status(self):
        """Update collection status display"""
        if hasattr(self.app, 'enhanced_deck_builder') and self.app.enhanced_deck_builder:
            collection = self.app.enhanced_deck_builder.collection
            if collection:
                count = len(collection)
                total = sum(collection.values())
                # Note: Would need to update the status row widget
                self.collection_loaded = True
    
    def _update_deck_status(self):
        """Update deck status display"""
        if hasattr(self.app, 'unified_current_deck') and self.app.unified_current_deck:
            deck = self.app.unified_current_deck
            self.current_deck = deck
    
    def _update_curve(self):
        """Update mana curve visualization"""
        if self.curve_widget and self.current_deck:
            self.curve_widget.update_curve(self.current_deck)
    
    def write_to_deck_output(self, text: str):
        """Write text to deck output console"""
        self.deck_output.insert("end", text)
        self.deck_output.see("end")
    
    def write_to_test_output(self, text: str):
        """Write text to test output console"""
        self.test_output.insert("end", text)
        self.test_output.see("end")
    
    def clear_deck_output(self):
        """Clear deck output console"""
        self.deck_output.delete("1.0", "end")
    
    def clear_test_output(self):
        """Clear test output console"""
        self.test_output.delete("1.0", "end")


# ═══════════════════════════════════════════════════════════════════════════
# STANDALONE DEMO
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Demo the deck builder tab
    root = tk.Tk()
    root.title("NEXUS - Deck Builder (Pro Theme Demo)")
    root.geometry("1400x900")
    root.configure(bg=Colors.BG_BASE)
    
    # Create theme
    if THEME_AVAILABLE:
        theme = NexusProTheme(root)
    else:
        print("❌ Pro theme required for demo")
        exit(1)
    
    # Create notebook
    notebook = theme.notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create mock app object
    class MockApp:
        def __init__(self):
            self.unified_format_var = tk.StringVar(value="Commander")
            self.unified_strategy_var = tk.StringVar(value="balanced")
            self.unified_colors_vars = {c: tk.BooleanVar() for c in "WUBRG"}
            self.enhanced_deck_builder = None
            self.unified_current_deck = []
        
        def unified_load_collection(self):
            print("Load collection clicked")
        
        def unified_build_deck(self):
            print("Build deck clicked")
            self.unified_current_deck = ["Lightning Bolt"] * 4 + ["Counterspell"] * 4
    
    mock_app = MockApp()
    
    # Create tab
    deck_tab = DeckBuilderTabPro(notebook, theme, mock_app)
    
    root.mainloop()
