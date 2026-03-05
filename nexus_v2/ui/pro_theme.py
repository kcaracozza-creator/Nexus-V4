#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         NEXUS PRO THEME SYSTEM                               ║
║                    Enterprise-Grade UI Components                             ║
║                                                                               ║
║  Transforms NEXUS from "kindergarten project" to "$600B market platform"     ║
╚══════════════════════════════════════════════════════════════════════════════╝

DESIGN PHILOSOPHY:
- Dark theme with gold accents (luxury trading platform aesthetic)
- Consistent spacing, typography, and color usage
- Clear visual hierarchy
- Professional button groupings with semantic colors
- No more rainbow button soup

Author: Jaques (The Twat Rocket)
For: Judge Miyagi 🐐
Date: Dec 2, 2025
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional, Callable, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import colorsys


# ══════════════════════════════════════════════════════════════════════════════
# COLOR SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class Colors:
    """
    NEXUS Professional Color Palette
    
    Inspired by Bloomberg Terminal, TradingView, and high-end fintech platforms.
    Dark theme with gold accents for that luxury feel.
    """
    
    # ══════════════════════════════════════════════════════════════════════════
    # BACKGROUND HIERARCHY (darkest to lightest)
    # ══════════════════════════════════════════════════════════════════════════
    BG_DEEPEST = '#08080a'       # App background - almost pure black
    BG_BASE = '#0d0e11'          # Main content area
    BG_CARD = '#14151a'          # Cards, panels
    BG_ELEVATED = '#1a1b22'      # Elevated surfaces, inputs
    BG_HOVER = '#22242d'         # Hover states
    BG_ACTIVE = '#2a2d38'        # Active/pressed states
    
    # ══════════════════════════════════════════════════════════════════════════
    # PRIMARY ACCENT - GOLD (Luxury/Premium feel)
    # ══════════════════════════════════════════════════════════════════════════
    GOLD = '#d4a537'             # Primary gold
    GOLD_LIGHT = '#e8c468'       # Light gold (hover)
    GOLD_DARK = '#b8912e'        # Dark gold (pressed)
    GOLD_MUTED = '#8a7535'       # Muted gold (disabled)
    GOLD_GLOW = '#d4a53730'      # Gold with transparency for glows
    
    # ══════════════════════════════════════════════════════════════════════════
    # SECONDARY ACCENT - PURPLE (Tech/AI feel)
    # ══════════════════════════════════════════════════════════════════════════
    PURPLE = '#7c5cff'           # Primary purple
    PURPLE_LIGHT = '#9d84ff'     # Light purple
    PURPLE_DARK = '#5c3fd4'      # Dark purple
    PURPLE_MUTED = '#4a3a7a'     # Muted purple
    
    # ══════════════════════════════════════════════════════════════════════════
    # SEMANTIC COLORS
    # ══════════════════════════════════════════════════════════════════════════
    SUCCESS = '#10b981'          # Green - success, connected, profit
    SUCCESS_DARK = '#059669'
    SUCCESS_BG = '#10b98115'
    
    WARNING = '#f59e0b'          # Amber - warning, pending
    WARNING_DARK = '#d97706'
    WARNING_BG = '#f59e0b15'
    
    DANGER = '#ef4444'           # Red - error, disconnected, loss
    DANGER_DARK = '#dc2626'
    DANGER_BG = '#ef444415'
    
    INFO = '#3b82f6'             # Blue - info, neutral action
    INFO_DARK = '#2563eb'
    INFO_BG = '#3b82f615'
    
    # ══════════════════════════════════════════════════════════════════════════
    # TEXT HIERARCHY
    # ══════════════════════════════════════════════════════════════════════════
    TEXT_PRIMARY = '#f0f0f5'     # Primary text - high contrast
    TEXT_SECONDARY = '#a0a3b1'   # Secondary text
    TEXT_MUTED = '#6b6f80'       # Muted/disabled text
    TEXT_INVERSE = '#08080a'     # Text on light backgrounds
    
    # ══════════════════════════════════════════════════════════════════════════
    # BORDERS & DIVIDERS
    # ══════════════════════════════════════════════════════════════════════════
    BORDER = '#2a2d38'           # Default border
    BORDER_LIGHT = '#3a3e4a'     # Lighter border
    BORDER_FOCUS = '#7c5cff'     # Focus ring
    DIVIDER = '#1e2028'          # Section dividers
    
    # ══════════════════════════════════════════════════════════════════════════
    # SPECIAL
    # ══════════════════════════════════════════════════════════════════════════
    TRANSPARENT = 'transparent'
    OVERLAY = '#00000080'        # Modal overlay
    
    @classmethod
    def with_alpha(cls, hex_color: str, alpha: float) -> str:
        """Convert hex color to rgba-like hex with alpha"""
        alpha_hex = format(int(alpha * 255), '02x')
        return f"{hex_color}{alpha_hex}"


# ══════════════════════════════════════════════════════════════════════════════
# TYPOGRAPHY SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class Typography:
    """
    Consistent typography across NEXUS.
    
    Using Segoe UI as primary (Windows native, clean, professional)
    with Consolas for monospace (logs, code, data).
    """
    
    # Font families with fallbacks
    FAMILY_DISPLAY = 'Segoe UI'
    FAMILY_BODY = 'Segoe UI'
    FAMILY_MONO = 'Consolas'
    
    # Font sizes (following 1.25 scale)
    SIZE_XS = 10
    SIZE_SM = 11
    SIZE_BASE = 12
    SIZE_MD = 13
    SIZE_LG = 15
    SIZE_XL = 18
    SIZE_2XL = 22
    SIZE_3XL = 28
    SIZE_4XL = 36
    
    # Font weights
    WEIGHT_NORMAL = 'normal'
    WEIGHT_MEDIUM = 'normal'  # Tk doesn't have medium
    WEIGHT_BOLD = 'bold'
    
    @classmethod
    def get(cls, size: str = 'base', weight: str = 'normal', mono: bool = False) -> tuple:
        """Get a font tuple for Tkinter"""
        sizes = {
            'xs': cls.SIZE_XS, 'sm': cls.SIZE_SM, 'base': cls.SIZE_BASE,
            'md': cls.SIZE_MD, 'lg': cls.SIZE_LG, 'xl': cls.SIZE_XL,
            '2xl': cls.SIZE_2XL, '3xl': cls.SIZE_3XL, '4xl': cls.SIZE_4XL
        }
        
        family = cls.FAMILY_MONO if mono else cls.FAMILY_BODY
        font_size = sizes.get(size, cls.SIZE_BASE)
        font_weight = cls.WEIGHT_BOLD if weight == 'bold' else cls.WEIGHT_NORMAL
        
        return (family, font_size, font_weight)
    
    # Preset fonts
    DISPLAY_HERO = (FAMILY_DISPLAY, SIZE_4XL, WEIGHT_BOLD)
    DISPLAY_TITLE = (FAMILY_DISPLAY, SIZE_3XL, WEIGHT_BOLD)
    DISPLAY_HEADING = (FAMILY_DISPLAY, SIZE_2XL, WEIGHT_BOLD)
    DISPLAY_SUBHEADING = (FAMILY_DISPLAY, SIZE_XL, WEIGHT_BOLD)
    
    BODY_LG = (FAMILY_BODY, SIZE_LG, WEIGHT_NORMAL)
    BODY_MD = (FAMILY_BODY, SIZE_MD, WEIGHT_NORMAL)
    BODY_BASE = (FAMILY_BODY, SIZE_BASE, WEIGHT_NORMAL)
    BODY_SM = (FAMILY_BODY, SIZE_SM, WEIGHT_NORMAL)
    
    LABEL = (FAMILY_BODY, SIZE_SM, WEIGHT_BOLD)
    BUTTON = (FAMILY_BODY, SIZE_MD, WEIGHT_BOLD)
    
    MONO_LG = (FAMILY_MONO, SIZE_LG, WEIGHT_NORMAL)
    MONO_MD = (FAMILY_MONO, SIZE_MD, WEIGHT_NORMAL)
    MONO_BASE = (FAMILY_MONO, SIZE_BASE, WEIGHT_NORMAL)
    MONO_SM = (FAMILY_MONO, SIZE_SM, WEIGHT_NORMAL)


# ══════════════════════════════════════════════════════════════════════════════
# SPACING SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class Spacing:
    """Consistent spacing values using 4px base unit"""
    
    NONE = 0
    XS = 4
    SM = 8
    MD = 12
    BASE = 16
    LG = 20
    XL = 24
    XXL = 32
    XXXL = 40
    SECTION = 48


# ══════════════════════════════════════════════════════════════════════════════
# BORDER RADIUS
# ══════════════════════════════════════════════════════════════════════════════

class Radius:
    """Border radius values"""
    
    NONE = 0
    SM = 4
    MD = 6
    LG = 8
    XL = 12
    FULL = 9999


# ══════════════════════════════════════════════════════════════════════════════
# BUTTON STYLES
# ══════════════════════════════════════════════════════════════════════════════

class ButtonStyle(Enum):
    """Button style variants"""
    PRIMARY = 'primary'       # Gold - main action
    SECONDARY = 'secondary'   # Purple - secondary action
    SUCCESS = 'success'       # Green - positive action
    DANGER = 'danger'         # Red - destructive action
    WARNING = 'warning'       # Amber - caution action
    INFO = 'info'             # Blue - informational action
    GHOST = 'ghost'           # Transparent - subtle action
    OUTLINE = 'outline'       # Border only


class ButtonSize(Enum):
    """Button size variants"""
    SM = 'sm'
    MD = 'md'
    LG = 'lg'
    XL = 'xl'


# ══════════════════════════════════════════════════════════════════════════════
# NEXUS PRO THEME CLASS
# ══════════════════════════════════════════════════════════════════════════════

class NexusProTheme:
    """
    The main theme class that provides styled widget factories.
    
    Usage:
        theme = NexusProTheme(root)
        
        # Create styled widgets
        btn = theme.button(parent, "Click Me", style=ButtonStyle.PRIMARY)
        lbl = theme.header(parent, "Title")
        frame = theme.card(parent)
    """
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.colors = Colors
        self.typography = Typography
        self.spacing = Spacing
        
        # Apply base configuration
        self._configure_root()
        self._configure_ttk_styles()
    
    # ══════════════════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════
    
    def _configure_root(self):
        """Configure the root window"""
        self.root.configure(bg=Colors.BG_DEEPEST)
        self.root.option_add('*Font', Typography.BODY_BASE)
        self.root.option_add('*Background', Colors.BG_BASE)
        self.root.option_add('*Foreground', Colors.TEXT_PRIMARY)
    
    def _configure_ttk_styles(self):
        """Configure ttk widget styles"""
        style = ttk.Style()
        style.theme_use('default')
        
        # ══════════════════════════════════════════════════════════════════════
        # NOTEBOOK (TABS)
        # ══════════════════════════════════════════════════════════════════════
        style.configure('Nexus.TNotebook',
            background=Colors.BG_DEEPEST,
            borderwidth=0,
            padding=0
        )
        
        style.configure('Nexus.TNotebook.Tab',
            background=Colors.BG_CARD,
            foreground=Colors.TEXT_SECONDARY,
            padding=[Spacing.LG, Spacing.SM],
            font=Typography.LABEL
        )
        
        style.map('Nexus.TNotebook.Tab',
            background=[
                ('selected', Colors.BG_ELEVATED),
                ('active', Colors.BG_HOVER)
            ],
            foreground=[
                ('selected', Colors.GOLD),
                ('active', Colors.TEXT_PRIMARY)
            ]
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # FRAMES
        # ══════════════════════════════════════════════════════════════════════
        style.configure('Nexus.TFrame',
            background=Colors.BG_BASE
        )
        
        style.configure('NexusCard.TFrame',
            background=Colors.BG_CARD
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # LABELFRAME (SECTIONS)
        # ══════════════════════════════════════════════════════════════════════
        style.configure('Nexus.TLabelframe',
            background=Colors.BG_CARD,
            borderwidth=1,
            relief='solid',
            bordercolor=Colors.BORDER
        )
        
        style.configure('Nexus.TLabelframe.Label',
            background=Colors.BG_CARD,
            foreground=Colors.GOLD,
            font=Typography.LABEL
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # COMBOBOX
        # ══════════════════════════════════════════════════════════════════════
        style.configure('Nexus.TCombobox',
            fieldbackground=Colors.BG_ELEVATED,
            background=Colors.BG_HOVER,
            foreground=Colors.TEXT_PRIMARY,
            arrowcolor=Colors.TEXT_SECONDARY,
            padding=Spacing.SM,
            font=Typography.BODY_BASE
        )
        
        style.map('Nexus.TCombobox',
            fieldbackground=[('focus', Colors.BG_HOVER)],
            bordercolor=[('focus', Colors.PURPLE)]
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # SCROLLBAR
        # ══════════════════════════════════════════════════════════════════════
        style.configure('Nexus.Vertical.TScrollbar',
            background=Colors.BG_ELEVATED,
            troughcolor=Colors.BG_BASE,
            borderwidth=0,
            arrowcolor=Colors.TEXT_MUTED
        )
        
        style.configure('Nexus.Horizontal.TScrollbar',
            background=Colors.BG_ELEVATED,
            troughcolor=Colors.BG_BASE,
            borderwidth=0,
            arrowcolor=Colors.TEXT_MUTED
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # PROGRESSBAR
        # ══════════════════════════════════════════════════════════════════════
        style.configure('Nexus.Horizontal.TProgressbar',
            background=Colors.GOLD,
            troughcolor=Colors.BG_ELEVATED,
            borderwidth=0,
            lightcolor=Colors.GOLD_LIGHT,
            darkcolor=Colors.GOLD_DARK
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # SCALE (SLIDER)
        # ══════════════════════════════════════════════════════════════════════
        style.configure('Nexus.Horizontal.TScale',
            background=Colors.BG_CARD,
            troughcolor=Colors.BG_ELEVATED,
            sliderthickness=16,
            borderwidth=0
        )
    
    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT WIDGETS
    # ══════════════════════════════════════════════════════════════════════════
    
    def frame(self, parent, bg: str = None, **kwargs) -> tk.Frame:
        """Create a basic frame"""
        return tk.Frame(
            parent,
            bg=bg or Colors.BG_BASE,
            highlightthickness=0,
            **kwargs
        )
    
    def card(self, parent, padding: int = None, **kwargs) -> tk.Frame:
        """Create a card (elevated surface)"""
        pad = padding if padding is not None else Spacing.BASE
        
        outer = tk.Frame(parent, bg=Colors.BG_BASE, highlightthickness=0)
        
        card = tk.Frame(
            outer,
            bg=Colors.BG_CARD,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
            **kwargs
        )
        card.pack(fill='both', expand=True, padx=2, pady=2)
        
        inner = tk.Frame(card, bg=Colors.BG_CARD)
        inner.pack(fill='both', expand=True, padx=pad, pady=pad)
        
        # Store reference to outer for packing
        inner._outer = outer
        return inner
    
    def section(self, parent, title: str, **kwargs) -> tk.Frame:
        """Create a titled section using LabelFrame"""
        lf = ttk.LabelFrame(
            parent,
            text=f"  {title}  ",
            style='Nexus.TLabelframe',
            padding=Spacing.MD,
            **kwargs
        )
        return lf
    
    def divider(self, parent, horizontal: bool = True) -> tk.Frame:
        """Create a divider line"""
        div = tk.Frame(
            parent,
            bg=Colors.DIVIDER,
            height=1 if horizontal else None,
            width=1 if not horizontal else None
        )
        return div
    
    # ══════════════════════════════════════════════════════════════════════════
    # TEXT WIDGETS
    # ══════════════════════════════════════════════════════════════════════════
    
    def label(self, parent, text: str, style: str = 'body', 
              color: str = None, **kwargs) -> tk.Label:
        """Create a styled label"""
        
        presets = {
            'hero': (Typography.DISPLAY_HERO, Colors.GOLD),
            'title': (Typography.DISPLAY_TITLE, Colors.GOLD),
            'heading': (Typography.DISPLAY_HEADING, Colors.TEXT_PRIMARY),
            'subheading': (Typography.DISPLAY_SUBHEADING, Colors.TEXT_PRIMARY),
            'body': (Typography.BODY_BASE, Colors.TEXT_PRIMARY),
            'body-lg': (Typography.BODY_LG, Colors.TEXT_PRIMARY),
            'secondary': (Typography.BODY_BASE, Colors.TEXT_SECONDARY),
            'muted': (Typography.BODY_SM, Colors.TEXT_MUTED),
            'label': (Typography.LABEL, Colors.GOLD),
            'mono': (Typography.MONO_BASE, Colors.TEXT_PRIMARY),
            'success': (Typography.BODY_BASE, Colors.SUCCESS),
            'danger': (Typography.BODY_BASE, Colors.DANGER),
            'warning': (Typography.BODY_BASE, Colors.WARNING),
        }
        
        font, default_color = presets.get(style, presets['body'])
        
        return tk.Label(
            parent,
            text=text,
            font=font,
            fg=color or default_color,
            bg=Colors.BG_CARD,
            **kwargs
        )
    
    def header(self, parent, text: str, subtitle: str = None) -> tk.Frame:
        """Create a page header with optional subtitle"""
        frame = self.frame(parent, bg=Colors.BG_BASE)
        
        title_label = tk.Label(
            frame,
            text=text,
            font=Typography.DISPLAY_HEADING,
            fg=Colors.GOLD,
            bg=Colors.BG_BASE
        )
        title_label.pack(anchor='w')
        
        if subtitle:
            sub_label = tk.Label(
                frame,
                text=subtitle,
                font=Typography.BODY_MD,
                fg=Colors.TEXT_SECONDARY,
                bg=Colors.BG_BASE
            )
            sub_label.pack(anchor='w', pady=(Spacing.XS, 0))
        
        return frame
    
    # ══════════════════════════════════════════════════════════════════════════
    # BUTTON WIDGETS
    # ══════════════════════════════════════════════════════════════════════════
    
    def button(self, parent, text: str, command: Callable = None,
               style: ButtonStyle = ButtonStyle.PRIMARY,
               size: ButtonSize = ButtonSize.MD,
               icon: str = None,
               full_width: bool = False,
               **kwargs) -> tk.Button:
        """Create a styled button"""
        
        # Style configurations
        style_configs = {
            ButtonStyle.PRIMARY: {
                'bg': Colors.GOLD,
                'fg': Colors.TEXT_INVERSE,
                'hover_bg': Colors.GOLD_LIGHT,
                'active_bg': Colors.GOLD_DARK,
            },
            ButtonStyle.SECONDARY: {
                'bg': Colors.PURPLE,
                'fg': Colors.TEXT_PRIMARY,
                'hover_bg': Colors.PURPLE_LIGHT,
                'active_bg': Colors.PURPLE_DARK,
            },
            ButtonStyle.SUCCESS: {
                'bg': Colors.SUCCESS,
                'fg': Colors.TEXT_PRIMARY,
                'hover_bg': Colors.SUCCESS,
                'active_bg': Colors.SUCCESS_DARK,
            },
            ButtonStyle.DANGER: {
                'bg': Colors.DANGER,
                'fg': Colors.TEXT_PRIMARY,
                'hover_bg': Colors.DANGER,
                'active_bg': Colors.DANGER_DARK,
            },
            ButtonStyle.WARNING: {
                'bg': Colors.WARNING,
                'fg': Colors.TEXT_INVERSE,
                'hover_bg': Colors.WARNING,
                'active_bg': Colors.WARNING_DARK,
            },
            ButtonStyle.INFO: {
                'bg': Colors.INFO,
                'fg': Colors.TEXT_PRIMARY,
                'hover_bg': Colors.INFO,
                'active_bg': Colors.INFO_DARK,
            },
            ButtonStyle.GHOST: {
                'bg': Colors.BG_CARD,
                'fg': Colors.TEXT_SECONDARY,
                'hover_bg': Colors.BG_HOVER,
                'active_bg': Colors.BG_ACTIVE,
            },
            ButtonStyle.OUTLINE: {
                'bg': Colors.BG_CARD,
                'fg': Colors.GOLD,
                'hover_bg': Colors.BG_HOVER,
                'active_bg': Colors.BG_ACTIVE,
            },
        }
        
        # Size configurations
        size_configs = {
            ButtonSize.SM: {'padx': 12, 'pady': 4, 'font': Typography.BODY_SM},
            ButtonSize.MD: {'padx': 16, 'pady': 6, 'font': Typography.BUTTON},
            ButtonSize.LG: {'padx': 20, 'pady': 8, 'font': Typography.BODY_LG},
            ButtonSize.XL: {'padx': 24, 'pady': 10, 'font': Typography.DISPLAY_SUBHEADING},
        }
        
        style_cfg = style_configs[style]
        size_cfg = size_configs[size]
        
        display_text = f"{icon} {text}" if icon else text
        
        btn = tk.Button(
            parent,
            text=display_text,
            command=command,
            font=size_cfg['font'],
            bg=style_cfg['bg'],
            fg=style_cfg['fg'],
            activebackground=style_cfg['active_bg'],
            activeforeground=style_cfg['fg'],
            relief='flat',
            bd=0,
            padx=size_cfg['padx'],
            pady=size_cfg['pady'],
            cursor='hand2',
            highlightthickness=0,
            **kwargs
        )
        
        # Add hover effects
        def on_enter(e):
            btn.configure(bg=style_cfg['hover_bg'])
        
        def on_leave(e):
            btn.configure(bg=style_cfg['bg'])
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
    
    def button_group(self, parent, buttons: List[Dict], 
                     spacing: int = None) -> tk.Frame:
        """
        Create a group of buttons with consistent spacing.
        
        Args:
            buttons: List of dicts with keys:
                - text: Button text
                - command: Click handler
                - style: ButtonStyle (default: GHOST)
                - size: ButtonSize (default: MD)
                - icon: Optional icon text
        """
        gap = spacing if spacing is not None else Spacing.SM
        
        frame = self.frame(parent, bg=Colors.BG_CARD)
        
        for i, btn_cfg in enumerate(buttons):
            btn = self.button(
                frame,
                text=btn_cfg.get('text', 'Button'),
                command=btn_cfg.get('command'),
                style=btn_cfg.get('style', ButtonStyle.GHOST),
                size=btn_cfg.get('size', ButtonSize.MD),
                icon=btn_cfg.get('icon')
            )
            
            padx = (0, gap) if i < len(buttons) - 1 else 0
            btn.pack(side='left', padx=padx)
        
        return frame
    
    # ══════════════════════════════════════════════════════════════════════════
    # INPUT WIDGETS
    # ══════════════════════════════════════════════════════════════════════════
    
    def entry(self, parent, width: int = 20, **kwargs) -> tk.Entry:
        """Create a styled text entry"""
        entry = tk.Entry(
            parent,
            font=Typography.BODY_BASE,
            bg=Colors.BG_ELEVATED,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.GOLD,
            selectbackground=Colors.PURPLE,
            selectforeground=Colors.TEXT_PRIMARY,
            relief='flat',
            bd=0,
            width=width,
            highlightthickness=1,
            highlightbackground=Colors.BORDER,
            highlightcolor=Colors.PURPLE,
            **kwargs
        )
        return entry
    
    def combobox(self, parent, values: List[str], width: int = 15, 
                 **kwargs) -> ttk.Combobox:
        """Create a styled combobox"""
        combo = ttk.Combobox(
            parent,
            values=values,
            width=width,
            state='readonly',
            style='Nexus.TCombobox',
            font=Typography.BODY_BASE,
            **kwargs
        )
        return combo
    
    def checkbox(self, parent, text: str, variable: tk.BooleanVar = None,
                 command: Callable = None, **kwargs) -> tk.Checkbutton:
        """Create a styled checkbox"""
        var = variable or tk.BooleanVar()
        
        cb = tk.Checkbutton(
            parent,
            text=text,
            variable=var,
            command=command,
            font=Typography.BODY_BASE,
            bg=Colors.BG_CARD,
            fg=Colors.TEXT_PRIMARY,
            selectcolor=Colors.BG_ELEVATED,
            activebackground=Colors.BG_CARD,
            activeforeground=Colors.TEXT_PRIMARY,
            highlightthickness=0,
            **kwargs
        )
        cb.variable = var
        return cb
    
    def spinbox(self, parent, from_: int = 0, to: int = 100,
                width: int = 8, **kwargs) -> tk.Spinbox:
        """Create a styled spinbox"""
        spin = tk.Spinbox(
            parent,
            from_=from_,
            to=to,
            width=width,
            font=Typography.BODY_BASE,
            bg=Colors.BG_ELEVATED,
            fg=Colors.TEXT_PRIMARY,
            buttonbackground=Colors.BG_HOVER,
            insertbackground=Colors.GOLD,
            selectbackground=Colors.PURPLE,
            relief='flat',
            bd=0,
            highlightthickness=1,
            highlightbackground=Colors.BORDER,
            highlightcolor=Colors.PURPLE,
            **kwargs
        )
        return spin
    
    def scale(self, parent, from_: int = 0, to: int = 255,
              orient: str = 'horizontal', length: int = 200,
              command: Callable = None, **kwargs) -> tk.Scale:
        """Create a styled scale/slider"""
        scale = tk.Scale(
            parent,
            from_=from_,
            to=to,
            orient=orient,
            length=length,
            command=command,
            font=Typography.BODY_SM,
            bg=Colors.BG_CARD,
            fg=Colors.TEXT_SECONDARY,
            troughcolor=Colors.BG_ELEVATED,
            activebackground=Colors.PURPLE,
            highlightthickness=0,
            sliderrelief='flat',
            bd=0,
            **kwargs
        )
        return scale
    
    # ══════════════════════════════════════════════════════════════════════════
    # TEXT AREAS
    # ══════════════════════════════════════════════════════════════════════════
    
    def text_area(self, parent, height: int = 10, width: int = 80,
                  **kwargs) -> scrolledtext.ScrolledText:
        """Create a styled text area with scrollbar"""
        text = scrolledtext.ScrolledText(
            parent,
            height=height,
            width=width,
            font=Typography.MONO_BASE,
            bg=Colors.BG_ELEVATED,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.GOLD,
            selectbackground=Colors.PURPLE,
            selectforeground=Colors.TEXT_PRIMARY,
            relief='flat',
            bd=0,
            padx=Spacing.MD,
            pady=Spacing.MD,
            wrap='word',
            **kwargs
        )
        return text
    
    def console(self, parent, height: int = 15, **kwargs) -> scrolledtext.ScrolledText:
        """Create a console-style text area (green text on black)"""
        console = scrolledtext.ScrolledText(
            parent,
            height=height,
            font=Typography.MONO_BASE,
            bg='#0a0a0a',
            fg=Colors.SUCCESS,
            insertbackground=Colors.SUCCESS,
            selectbackground=Colors.PURPLE,
            relief='flat',
            bd=0,
            padx=Spacing.MD,
            pady=Spacing.MD,
            wrap='word',
            **kwargs
        )
        return console
    
    # ══════════════════════════════════════════════════════════════════════════
    # STATUS INDICATORS
    # ══════════════════════════════════════════════════════════════════════════
    
    def status_dot(self, parent, status: str = 'offline') -> tk.Canvas:
        """Create a status indicator dot"""
        colors = {
            'online': Colors.SUCCESS,
            'connected': Colors.SUCCESS,
            'offline': Colors.DANGER,
            'disconnected': Colors.DANGER,
            'pending': Colors.WARNING,
            'loading': Colors.WARNING,
            'info': Colors.INFO,
        }
        
        canvas = tk.Canvas(
            parent,
            width=12,
            height=12,
            bg=Colors.BG_CARD,
            highlightthickness=0
        )
        
        color = colors.get(status.lower(), Colors.TEXT_MUTED)
        canvas.create_oval(2, 2, 10, 10, fill=color, outline='')
        
        return canvas
    
    def status_badge(self, parent, text: str, status: str = 'info') -> tk.Frame:
        """Create a status badge with text"""
        colors = {
            'success': (Colors.SUCCESS_BG, Colors.SUCCESS),
            'danger': (Colors.DANGER_BG, Colors.DANGER),
            'warning': (Colors.WARNING_BG, Colors.WARNING),
            'info': (Colors.INFO_BG, Colors.INFO),
        }
        
        bg_color, fg_color = colors.get(status, colors['info'])
        
        frame = tk.Frame(parent, bg=bg_color, padx=Spacing.SM, pady=Spacing.XS)
        
        label = tk.Label(
            frame,
            text=text,
            font=Typography.BODY_SM,
            fg=fg_color,
            bg=bg_color
        )
        label.pack()
        
        return frame
    
    def status_row(self, parent, label: str, value: str, 
                   status: str = None) -> tk.Frame:
        """Create a labeled status row"""
        frame = self.frame(parent, bg=Colors.BG_CARD)
        
        lbl = tk.Label(
            frame,
            text=f"{label}:",
            font=Typography.LABEL,
            fg=Colors.GOLD,
            bg=Colors.BG_CARD,
            width=15,
            anchor='w'
        )
        lbl.pack(side='left')
        
        if status:
            dot = self.status_dot(frame, status)
            dot.pack(side='left', padx=(0, Spacing.SM))
        
        val = tk.Label(
            frame,
            text=value,
            font=Typography.BODY_BASE,
            fg=Colors.TEXT_SECONDARY if status in ['offline', 'disconnected'] else Colors.TEXT_PRIMARY,
            bg=Colors.BG_CARD,
            anchor='w'
        )
        val.pack(side='left', fill='x', expand=True)
        
        return frame
    
    # ══════════════════════════════════════════════════════════════════════════
    # DATA DISPLAY
    # ══════════════════════════════════════════════════════════════════════════
    
    def stat_card(self, parent, label: str, value: str, 
                  trend: str = None) -> tk.Frame:
        """Create a stat display card"""
        frame = self.frame(parent, bg=Colors.BG_CARD)
        frame.configure(padx=Spacing.BASE, pady=Spacing.MD)
        
        lbl = tk.Label(
            frame,
            text=label,
            font=Typography.LABEL,
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_CARD
        )
        lbl.pack(anchor='w')
        
        val = tk.Label(
            frame,
            text=value,
            font=Typography.DISPLAY_HEADING,
            fg=Colors.TEXT_PRIMARY,
            bg=Colors.BG_CARD
        )
        val.pack(anchor='w', pady=(Spacing.XS, 0))
        
        if trend:
            trend_color = Colors.SUCCESS if trend.startswith('+') else Colors.DANGER
            trend_lbl = tk.Label(
                frame,
                text=trend,
                font=Typography.BODY_SM,
                fg=trend_color,
                bg=Colors.BG_CARD
            )
            trend_lbl.pack(anchor='w', pady=(Spacing.XS, 0))
        
        return frame
    
    # ══════════════════════════════════════════════════════════════════════════
    # NOTEBOOK (TABS)
    # ══════════════════════════════════════════════════════════════════════════
    
    def notebook(self, parent, **kwargs) -> ttk.Notebook:
        """Create a styled notebook (tabbed interface)"""
        nb = ttk.Notebook(parent, style='Nexus.TNotebook', **kwargs)
        return nb
    
    def tab_frame(self, notebook: ttk.Notebook, title: str, **kwargs) -> tk.Frame:
        """Create a frame to use as a tab and add it to notebook"""
        frame = tk.Frame(notebook, bg=Colors.BG_BASE, **kwargs)
        notebook.add(frame, text=f"  {title}  ")
        return frame


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTION TO APPLY THEME TO EXISTING APP
# ══════════════════════════════════════════════════════════════════════════════

def apply_theme_to_nexus(root: tk.Tk) -> NexusProTheme:
    """
    Apply the NEXUS Pro Theme to an existing root window.
    
    Usage in nexus.py:
        from nexus_pro_theme import apply_theme_to_nexus
        
        def __init__(self):
            self.root = tk.Tk()
            self.theme = apply_theme_to_nexus(self.root)
            # Now use self.theme.button(), self.theme.card(), etc.
    """
    return NexusProTheme(root)


# ══════════════════════════════════════════════════════════════════════════════
# DEMO / TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    root = tk.Tk()
    root.title("NEXUS Pro Theme Demo")
    root.geometry("1200x800")
    
    theme = NexusProTheme(root)
    
    # Main container
    main = theme.frame(root, bg=Colors.BG_DEEPEST)
    main.pack(fill='both', expand=True, padx=Spacing.XL, pady=Spacing.XL)
    
    # Header
    header = theme.header(main, "NEXUS PRO THEME", "Enterprise-grade UI components")
    header.pack(fill='x', pady=(0, Spacing.XL))
    
    # Button demo section
    btn_section = theme.section(main, "Button Styles")
    btn_section.pack(fill='x', pady=Spacing.MD)
    
    buttons = [
        {'text': 'Primary', 'style': ButtonStyle.PRIMARY},
        {'text': 'Secondary', 'style': ButtonStyle.SECONDARY},
        {'text': 'Success', 'style': ButtonStyle.SUCCESS},
        {'text': 'Danger', 'style': ButtonStyle.DANGER},
        {'text': 'Warning', 'style': ButtonStyle.WARNING},
        {'text': 'Ghost', 'style': ButtonStyle.GHOST},
    ]
    
    btn_group = theme.button_group(btn_section, buttons)
    btn_group.pack(pady=Spacing.MD)
    
    # Status demo
    status_section = theme.section(main, "Status Indicators")
    status_section.pack(fill='x', pady=Spacing.MD)
    
    theme.status_row(status_section, "Arduino", "Connected", "online").pack(fill='x', pady=2)
    theme.status_row(status_section, "Camera", "Not Found", "offline").pack(fill='x', pady=2)
    theme.status_row(status_section, "Scanner", "Initializing...", "pending").pack(fill='x', pady=2)
    
    # Console demo
    console_section = theme.section(main, "Console Output")
    console_section.pack(fill='both', expand=True, pady=Spacing.MD)
    
    console = theme.console(console_section, height=10)
    console.pack(fill='both', expand=True)
    console.insert('1.0', "NEXUS PRO THEME LOADED\n" + "=" * 50 + "\n\nReady for enterprise-grade UI.\n")
    
    root.mainloop()
