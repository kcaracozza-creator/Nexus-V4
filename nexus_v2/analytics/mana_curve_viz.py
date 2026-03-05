#!/usr/bin/env python3
"""
Mana Curve Visualization
Generates ASCII and graphical mana curve charts for decks
"""

import tkinter as tk
from tkinter import ttk
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Try to import Scryfall integration
try:
    from scryfall_integration import get_scryfall_api, CardDataEnricher
    SCRYFALL_AVAILABLE = True
except ImportError:
    SCRYFALL_AVAILABLE = False
    print("[WARN] Scryfall integration not available - using estimated CMC")


class ManaCurveAnalyzer:
    """Analyzes and visualizes mana curves"""
    
    # Color mapping for MTG
    COLOR_MAP = {
        'W': ('#F9FAF4', 'White'),
        'U': ('#0E68AB', 'Blue'),
        'B': ('#150B00', 'Black'),
        'R': ('#D3202A', 'Red'),
        'G': ('#00733E', 'Green'),
        'C': ('#CAC5C0', 'Colorless'),
    }
    
    # Type icons (using ASCII text)
    TYPE_ICONS = {
        'Creature': '[C]',
        'Instant': '[I]',
        'Sorcery': '[S]',
        'Artifact': '[A]',
        'Enchantment': '[E]',
        'Planeswalker': '[PW]',
        'Land': '[L]',
    }
    
    def __init__(self):
        if SCRYFALL_AVAILABLE:
            self.enricher = CardDataEnricher()
        else:
            self.enricher = None
        
        # Fallback CMC estimation
        self.cmc_cache = {}
    
    def _estimate_cmc(self, card_name: str) -> int:
        """Estimate CMC when Scryfall is unavailable"""
        if card_name in self.cmc_cache:
            return self.cmc_cache[card_name]
        
        # Pattern-based estimation
        name_lower = card_name.lower()
        
        # Known cards
        known = {
            'lightning bolt': 1, 'shock': 1, 'opt': 1, 'ponder': 1,
            'counterspell': 2, 'doom blade': 2, 'terminate': 2,
            'murder': 3, 'cultivate': 3, 'kodama\'s reach': 3,
            'wrath of god': 4, 'damnation': 4, 'explosive vegetation': 4,
            'force of will': 5, 'mulldrifter': 5,
            'sol ring': 1, 'arcane signet': 2, 'commander\'s sphere': 3,
        }
        
        if name_lower in known:
            return known[name_lower]
        
        # Pattern matching
        if 'bolt' in name_lower or 'shock' in name_lower:
            return 1
        elif 'signet' in name_lower or 'talisman' in name_lower:
            return 2
        elif 'wrath' in name_lower or 'verdict' in name_lower:
            return 4
        elif 'dragon' in name_lower or 'angel' in name_lower:
            return 5
        elif 'titan' in name_lower or 'eldrazi' in name_lower:
            return 6
        
        # Default mid-range
        return 3
    
    def get_cmc(self, card_name: str) -> int:
        """Get CMC for a card (Scryfall or estimated)"""
        if SCRYFALL_AVAILABLE and self.enricher:
            return self.enricher.api.get_cmc(card_name)
        return self._estimate_cmc(card_name)
    
    def analyze_deck(self, deck: List[str]) -> Dict:
        """
        Full analysis of a deck
        
        Returns dict with:
        - mana_curve: {cmc: count}
        - color_distribution: {color: count}
        - type_distribution: {type: count}
        - average_cmc: float
        - curve_rating: str
        """
        # Mana curve
        curve = defaultdict(int)
        for card in deck:
            cmc = self.get_cmc(card)
            # Lands don't count toward curve
            if cmc >= 0:
                display_cmc = min(cmc, 7)  # 7+ bucket
                curve[display_cmc] += 1
        
        # Calculate average CMC (excluding lands)
        total_cmc = sum(cmc * count for cmc, count in curve.items())
        non_land_count = sum(curve.values())
        avg_cmc = total_cmc / non_land_count if non_land_count > 0 else 0
        
        # Rate the curve
        curve_rating = self._rate_curve(curve, avg_cmc)
        
        return {
            'mana_curve': dict(curve),
            'average_cmc': avg_cmc,
            'curve_rating': curve_rating,
            'total_nonland': non_land_count,
        }
    
    def _rate_curve(self, curve: Dict[int, int], avg_cmc: float) -> str:
        """Rate the mana curve quality"""
        if avg_cmc < 2.0:
            return "[FAST] Very Aggressive (avg {:.2f})".format(avg_cmc)
        elif avg_cmc < 2.5:
            return "[AGGRO] Aggressive (avg {:.2f})".format(avg_cmc)
        elif avg_cmc < 3.0:
            return "[BAL] Balanced (avg {:.2f})".format(avg_cmc)
        elif avg_cmc < 3.5:
            return "[MID] Midrange (avg {:.2f})".format(avg_cmc)
        elif avg_cmc < 4.0:
            return "[CTRL] Control (avg {:.2f})".format(avg_cmc)
        else:
            return "[HEAVY] Very Heavy (avg {:.2f})".format(avg_cmc)
    
    def generate_ascii_curve(self, deck: List[str], width: int = 60) -> str:
        """Generate ASCII art mana curve"""
        analysis = self.analyze_deck(deck)
        curve = analysis['mana_curve']
        
        if not curve:
            return "No cards to analyze"
        
        # Find max for scaling
        max_count = max(curve.values()) if curve else 1
        bar_width = width - 15  # Leave room for labels
        
        lines = []
        lines.append("=" * width)
        lines.append("MANA CURVE ANALYSIS")
        lines.append("=" * width)
        lines.append("")
        
        # Draw bars for each CMC
        for cmc in range(8):  # 0-7+
            count = curve.get(cmc, 0)
            bar_length = int((count / max_count) * bar_width) if max_count > 0 else 0
            bar = "█" * bar_length
            
            if cmc == 7:
                label = f"7+  "
            else:
                label = f"{cmc}   "
            
            lines.append(f"{label}│{bar} ({count})")
        
        lines.append("")
        lines.append(f"Average CMC: {analysis['average_cmc']:.2f}")
        lines.append(f"Rating: {analysis['curve_rating']}")
        lines.append(f"Non-land cards: {analysis['total_nonland']}")
        lines.append("=" * width)
        
        return "\n".join(lines)
    
    def generate_detailed_report(self, deck: List[str]) -> str:
        """Generate detailed deck analysis report"""
        analysis = self.analyze_deck(deck)
        curve = analysis['mana_curve']
        
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════╗")
        lines.append("║              DECK ANALYSIS REPORT                         ║")
        lines.append("╠══════════════════════════════════════════════════════════╣")
        lines.append("")
        
        # Mana Curve Section
        lines.append("┌─────────────────────────────────────────────────────────┐")
        lines.append("│ MANA CURVE                                              │")
        lines.append("└─────────────────────────────────────────────────────────┘")
        
        max_count = max(curve.values()) if curve else 1
        
        for cmc in range(8):
            count = curve.get(cmc, 0)
            bar_length = int((count / max_count) * 40) if max_count > 0 else 0
            bar = "▓" * bar_length + "░" * (40 - bar_length)
            
            if cmc == 7:
                label = "7+"
            else:
                label = f"{cmc} "
            
            pct = (count / analysis['total_nonland'] * 100) if analysis['total_nonland'] > 0 else 0
            lines.append(f"  {label} │{bar}│ {count:3d} ({pct:5.1f}%)")
        
        lines.append("")
        lines.append(f"  [AVG] Average CMC: {analysis['average_cmc']:.2f}")
        lines.append(f"  [RATE] Curve Rating: {analysis['curve_rating']}")
        lines.append(f"  [COUNT] Total Non-Land Cards: {analysis['total_nonland']}")
        
        # Distribution by CMC
        lines.append("")
        lines.append("┌─────────────────────────────────────────────────────────┐")
        lines.append("│ CMC BREAKDOWN                                           │")
        lines.append("└─────────────────────────────────────────────────────────┘")
        
        low_end = sum(curve.get(i, 0) for i in range(3))  # 0-2
        mid_range = sum(curve.get(i, 0) for i in range(3, 5))  # 3-4
        high_end = sum(curve.get(i, 0) for i in range(5, 8))  # 5+
        
        total = analysis['total_nonland'] or 1
        lines.append(f"  [LOW] Low (0-2 CMC):    {low_end:3d} cards ({low_end/total*100:5.1f}%)")
        lines.append(f"  [MID] Mid (3-4 CMC):    {mid_range:3d} cards ({mid_range/total*100:5.1f}%)")
        lines.append(f"  [HIGH] High (5+ CMC):   {high_end:3d} cards ({high_end/total*100:5.1f}%)")
        
        lines.append("")
        lines.append("╚══════════════════════════════════════════════════════════╝")
        
        return "\n".join(lines)


class ManaCurveWidget(tk.Frame):
    """Tkinter widget for displaying mana curve"""
    
    # Colors for the bars
    BAR_COLORS = {
        0: '#9ca3af',  # Gray for 0
        1: '#fbbf24',  # Amber for 1
        2: '#f59e0b',  # Orange for 2
        3: '#ef4444',  # Red for 3
        4: '#dc2626',  # Dark red for 4
        5: '#7c3aed',  # Purple for 5
        6: '#6d28d9',  # Dark purple for 6
        7: '#4c1d95',  # Very dark purple for 7+
    }
    
    def __init__(self, parent, bg='#0d0e11', fg='#f0f0f5', accent='#d4a537', **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        
        self.bg = bg
        self.fg = fg
        self.accent = accent
        
        self.analyzer = ManaCurveAnalyzer()
        self.current_deck = []
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the widget UI"""
        # Title
        title = tk.Label(self, text="MANA CURVE", 
                        font=("Segoe UI", 12, "bold"),
                        fg=self.accent, bg=self.bg)
        title.pack(pady=(8, 4))
        
        # Canvas for drawing the curve
        self.canvas = tk.Canvas(self, 
                               width=300, height=180,
                               bg=self.bg, 
                               highlightthickness=0)
        self.canvas.pack(padx=8, pady=4)
        
        # Stats label
        self.stats_label = tk.Label(self, text="Load a deck to see curve",
                                   font=("Segoe UI", 10),
                                   fg='#a0a3b1', bg=self.bg)
        self.stats_label.pack(pady=(4, 8))
    
    def update_curve(self, deck: List[str]):
        """Update the curve display with a new deck"""
        self.current_deck = deck
        analysis = self.analyzer.analyze_deck(deck)
        
        self._draw_curve(analysis['mana_curve'])
        self.stats_label.config(
            text=f"Avg CMC: {analysis['average_cmc']:.2f} | {analysis['curve_rating']}"
        )
    
    def _draw_curve(self, curve: Dict[int, int]):
        """Draw the mana curve bars"""
        self.canvas.delete("all")
        
        if not curve:
            self.canvas.create_text(150, 90, text="No data",
                                   fill='#6b6f80', font=("Segoe UI", 11))
            return
        
        # Dimensions
        width = 300
        height = 180
        padding = 30
        bar_area_width = width - 2 * padding
        bar_area_height = height - 2 * padding
        
        # Calculate bar dimensions
        num_bars = 8  # 0-7+
        bar_width = bar_area_width / num_bars - 4
        max_count = max(curve.values()) if curve else 1
        
        # Draw bars
        for cmc in range(8):
            count = curve.get(cmc, 0)
            bar_height = (count / max_count) * bar_area_height if max_count > 0 else 0
            
            x1 = padding + cmc * (bar_width + 4)
            y1 = height - padding - bar_height
            x2 = x1 + bar_width
            y2 = height - padding
            
            # Draw bar
            color = self.BAR_COLORS.get(cmc, '#4c1d95')
            if bar_height > 0:
                self.canvas.create_rectangle(x1, y1, x2, y2,
                                            fill=color, outline='')
            
            # Draw CMC label
            label = "7+" if cmc == 7 else str(cmc)
            self.canvas.create_text(x1 + bar_width/2, height - padding + 12,
                                   text=label, fill='#6b6f80',
                                   font=("Segoe UI", 9))
            
            # Draw count on top of bar
            if count > 0:
                self.canvas.create_text(x1 + bar_width/2, y1 - 8,
                                       text=str(count), fill=self.fg,
                                       font=("Segoe UI", 9, "bold"))
        
        # Draw axis line
        self.canvas.create_line(padding, height - padding,
                               width - padding, height - padding,
                               fill='#2a2d38', width=1)
    
    def clear(self):
        """Clear the curve display"""
        self.canvas.delete("all")
        self.stats_label.config(text="Load a deck to see curve")
        self.current_deck = []


class ColorDistributionWidget(tk.Frame):
    """Widget showing color distribution pie/bar"""
    
    COLOR_HEX = {
        'W': '#F9FAF4',
        'U': '#0E68AB', 
        'B': '#2D2D2D',
        'R': '#D3202A',
        'G': '#00733E',
        'C': '#CAC5C0',
    }
    
    COLOR_NAMES = {
        'W': 'White',
        'U': 'Blue',
        'B': 'Black',
        'R': 'Red',
        'G': 'Green',
        'C': 'Colorless',
    }
    
    def __init__(self, parent, bg='#0d0e11', fg='#f0f0f5', accent='#d4a537', **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        
        self.bg = bg
        self.fg = fg
        self.accent = accent
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the widget UI"""
        # Title
        title = tk.Label(self, text="COLOR DISTRIBUTION",
                        font=("Segoe UI", 12, "bold"),
                        fg=self.accent, bg=self.bg)
        title.pack(pady=(8, 4))
        
        # Canvas for color bars
        self.canvas = tk.Canvas(self,
                               width=200, height=120,
                               bg=self.bg,
                               highlightthickness=0)
        self.canvas.pack(padx=8, pady=4)
    
    def update_distribution(self, color_dist: Dict[str, int]):
        """Update the color distribution display"""
        self.canvas.delete("all")
        
        if not color_dist:
            self.canvas.create_text(100, 60, text="No data",
                                   fill='#6b6f80', font=("Segoe UI", 11))
            return
        
        total = sum(color_dist.values())
        if total == 0:
            return
        
        # Draw horizontal stacked bar
        x = 10
        bar_height = 30
        bar_y = 40
        total_width = 180
        
        for color in ['W', 'U', 'B', 'R', 'G', 'C']:
            count = color_dist.get(color, 0)
            if count > 0:
                width = (count / total) * total_width
                self.canvas.create_rectangle(x, bar_y, x + width, bar_y + bar_height,
                                            fill=self.COLOR_HEX[color], outline='')
                x += width
        
        # Legend
        y = 90
        x = 10
        for color in ['W', 'U', 'B', 'R', 'G', 'C']:
            count = color_dist.get(color, 0)
            if count > 0:
                # Color square
                self.canvas.create_rectangle(x, y, x + 12, y + 12,
                                            fill=self.COLOR_HEX[color], outline='#2a2d38')
                # Label
                self.canvas.create_text(x + 16, y + 6, text=f"{count}",
                                       anchor='w', fill='#a0a3b1',
                                       font=("Segoe UI", 9))
                x += 35


# Standalone test
if __name__ == "__main__":
    # Test with sample deck
    sample_deck = [
        "Lightning Bolt", "Lightning Bolt", "Lightning Bolt", "Lightning Bolt",
        "Counterspell", "Counterspell", "Counterspell",
        "Tarmogoyf", "Tarmogoyf", "Tarmogoyf", "Tarmogoyf",
        "Snapcaster Mage", "Snapcaster Mage", "Snapcaster Mage",
        "Force of Will", "Force of Will",
        "Jace, the Mind Sculptor",
        "Cryptic Command", "Cryptic Command",
        "Wrath of God", "Wrath of God",
        "Sol Ring",
        "Mana Crypt",
    ]
    
    analyzer = ManaCurveAnalyzer()
    
    print(analyzer.generate_ascii_curve(sample_deck))
    print()
    print(analyzer.generate_detailed_report(sample_deck))
    
    # Test GUI
    root = tk.Tk()
    root.title("Mana Curve Test")
    root.configure(bg='#0d0e11')
    
    curve_widget = ManaCurveWidget(root)
    curve_widget.pack(padx=20, pady=20)
    curve_widget.update_curve(sample_deck)
    
    root.mainloop()
