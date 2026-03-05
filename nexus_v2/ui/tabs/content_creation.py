#!/usr/bin/env python3
"""NEXUS V2 - Content Creation Tab"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging

logger = logging.getLogger(__name__)


class ContentCreationTab:
    """
    AI Content Creation Interface.
    
    Features:
    - Custom card generation
    - Deck theme creation
    - Marketing materials
    - Social media content
    """
    
    def __init__(self, notebook: ttk.Notebook, config):
        self.notebook = notebook
        self.config = config
        self.colors = self._get_colors()
        
        # Create tab
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="🎨 Content Creator")
        
        self._build_ui()
        
    def _get_colors(self):
        """Get theme colors."""
        class Colors:
            bg_dark = "#4a4a4a"
            bg_surface = "#555555"
            bg_elevated = "#606060"
            accent = "#5c6bc0"
            text_primary = "#ffffff"
            text_secondary = "#e0e0e0"
            success = "#43a047"
        return Colors()
        
    def _build_ui(self):
        """Build the content creation interface."""
        container = tk.Frame(self.frame, bg=self.colors.bg_dark)
        container.pack(fill='both', expand=True)

        # Header (fixed at top)
        header = tk.Frame(container, bg=self.colors.bg_surface)
        header.pack(fill='x', padx=10, pady=10)

        tk.Label(
            header, text="🎨 AI Content Creator",
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors.accent, bg=self.colors.bg_surface
        ).pack(side='left', padx=15, pady=10)

        # Scrollable content area
        canvas = tk.Canvas(container, bg=self.colors.bg_dark, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
        main = tk.Frame(canvas, bg=self.colors.bg_dark)

        main.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=main, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True, padx=10)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Content sections
        content = tk.Frame(main, bg=self.colors.bg_dark)
        content.pack(fill='both', expand=True)
        
        # Left - Content Types
        left = tk.Frame(content, bg=self.colors.bg_surface)
        left.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        tk.Label(
            left, text="Content Type",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        ).pack(pady=10)
        
        # Content type buttons
        types = [
            ("📝 Deck Description", self._create_deck_desc),
            ("📊 Price Report", self._create_price_report),
            ("📱 Social Post", self._create_social_post),
            ("📧 Newsletter", self._create_newsletter),
            ("🏷️ Listing Description", self._create_listing),
        ]
        
        for text, cmd in types:
            tk.Button(
                left, text=text,
                font=('Segoe UI', 11),
                fg='white', bg=self.colors.bg_elevated,
                activebackground=self.colors.accent,
                width=25, height=2,
                command=cmd
            ).pack(pady=5, padx=10)
            
        # Right - Output area
        right = tk.Frame(content, bg=self.colors.bg_surface)
        right.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        tk.Label(
            right, text="Generated Content",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        ).pack(pady=10)
        
        # Text output
        self.output = tk.Text(
            right, height=20, width=50,
            bg=self.colors.bg_elevated, fg='white',
            font=('Consolas', 10),
            wrap='word'
        )
        self.output.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Action buttons
        btn_frame = tk.Frame(right, bg=self.colors.bg_surface)
        btn_frame.pack(pady=10)
        
        tk.Button(
            btn_frame, text="📋 Copy",
            font=('Segoe UI', 10),
            fg='white', bg=self.colors.accent,
            command=self._copy_content
        ).pack(side='left', padx=5)
        
        tk.Button(
            btn_frame, text="💾 Save",
            font=('Segoe UI', 10),
            fg='white', bg=self.colors.success,
            command=self._save_content
        ).pack(side='left', padx=5)

    def _create_deck_desc(self):
        """Generate deck description."""
        self.output.delete('1.0', 'end')
        desc = """🎴 DECK DESCRIPTION GENERATOR

Enter your deck details to generate a compelling description:

DECK NAME: [Your Deck Name]
FORMAT: [Standard/Modern/Commander/etc.]
COLORS: [W/U/B/R/G]
STRATEGY: [Aggro/Control/Combo/Midrange]

---
GENERATED DESCRIPTION:

This competitive deck leverages powerful synergies 
to dominate the battlefield. With a carefully curated
selection of cards, it offers both consistency and
explosive potential.

Key Features:
• Strong early game presence
• Multiple win conditions
• Resilient to disruption
• Budget-friendly alternatives available

Perfect for players who enjoy strategic depth
with explosive finish potential.
"""
        self.output.insert('1.0', desc)
        
    def _create_price_report(self):
        """Generate price report."""
        self.output.delete('1.0', 'end')
        report = """📊 MARKET PRICE REPORT
Generated: [Current Date]

TOP MOVERS THIS WEEK:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 GAINERS:
1. Card Name - $XX.XX (+15.2%)
2. Card Name - $XX.XX (+12.8%)
3. Card Name - $XX.XX (+10.5%)

📉 DECLINERS:
1. Card Name - $XX.XX (-8.3%)
2. Card Name - $XX.XX (-6.1%)
3. Card Name - $XX.XX (-4.9%)

MARKET SUMMARY:
• Overall trend: Bullish
• Volume: High
• Volatility: Moderate

RECOMMENDATIONS:
• Consider buying undervalued staples
• Watch for rotation impacts
• Monitor tournament results
"""
        self.output.insert('1.0', report)
        
    def _create_social_post(self):
        """Generate social media post."""
        self.output.delete('1.0', 'end')
        post = """📱 SOCIAL MEDIA POST

TWITTER/X (280 chars):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 Just pulled an INSANE card! Check out 
our latest inventory additions at [Shop Name]! 

New arrivals include chase cards from the 
latest set. Stop by before they're gone! 

#MTG #TradingCards #TCG #CardShop

INSTAGRAM CAPTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Fresh inventory alert! ✨

We've got some amazing new additions 
to our collection. From competitive 
staples to collector's items, there's 
something for everyone!

📍 Visit us at [Address]
🕐 Open [Hours]
📞 [Phone]

#MagicTheGathering #CardShop #TCG 
#Pokemon #SportsCards #Collectibles
"""
        self.output.insert('1.0', post)
        
    def _create_newsletter(self):
        """Generate newsletter content."""
        self.output.delete('1.0', 'end')
        newsletter = """📧 WEEKLY NEWSLETTER

Subject: This Week at [Shop Name] - Hot New Arrivals!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hey [Customer Name]!

Hope you're having a great week! We've got 
some exciting updates to share with you.

🆕 NEW ARRIVALS:
• [Card/Product 1]
• [Card/Product 2]  
• [Card/Product 3]

🎮 UPCOMING EVENTS:
• Friday Night Magic - This Friday 7PM
• Commander Night - Saturday 6PM
• Draft Weekend - Next Sunday

💰 SPECIAL OFFERS:
Use code NEXUS10 for 10% off your next 
purchase over $50!

See you at the shop!
- The [Shop Name] Team
"""
        self.output.insert('1.0', newsletter)
        
    def _create_listing(self):
        """Generate listing description."""
        self.output.delete('1.0', 'end')
        listing = """🏷️ MARKETPLACE LISTING

TITLE: [Card Name] - [Set] - [Condition]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DESCRIPTION:

[Card Name] from [Set Name]

Condition: Near Mint (NM)
Language: English
Edition: First Print

This card is in excellent condition with 
no visible wear. Perfect for collectors 
or competitive play.

SHIPPING:
• Free shipping on orders over $25
• Tracked shipping available
• Ships within 24 hours

RETURNS:
30-day return policy. Full refund if 
item doesn't match description.

Questions? Message us anytime!
"""
        self.output.insert('1.0', listing)
        
    def _copy_content(self):
        """Copy content to clipboard."""
        content = self.output.get('1.0', 'end')
        self.frame.clipboard_clear()
        self.frame.clipboard_append(content)
        messagebox.showinfo("Copied", "Content copied to clipboard!")
        
    def _save_content(self):
        """Save content to file."""
        content = self.output.get('1.0', 'end')
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            with open(file_path, 'w') as f:
                f.write(content)
            messagebox.showinfo("Saved", f"Content saved to {file_path}")
