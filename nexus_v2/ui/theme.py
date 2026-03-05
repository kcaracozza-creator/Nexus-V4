#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS PROFESSIONAL THEME
========================
Clean, modern component-based theme system with enum-based styling.
Drop-in upgrade for nexus_theme.py

Usage:
    from nexus_pro_theme import NexusProTheme, ButtonStyle
    
    theme = NexusProTheme(root)
    theme.button(parent, "Scan", command=scan_cards, style=ButtonStyle.PRIMARY)
    theme.section(parent, "Controls")
    theme.status_row(parent, "Arduino", "Connected", "online")
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from enum import Enum


class ButtonStyle(Enum):
    """Button style presets"""
    PRIMARY = "primary"      # Indigo - main actions
    SUCCESS = "success"      # Green - confirm/save
    DANGER = "danger"        # Red - delete/cancel
    INFO = "info"            # Blue - information
    WARNING = "warning"      # Orange - caution
    GOLD = "gold"            # Gold - special/premium
    NEUTRAL = "neutral"      # Gray - secondary


class NexusProTheme:
    """
    Professional theme system for NEXUS.
    Component-based with consistent styling.
    """
    
    # ============================================
    # COLOR PALETTE
    # ============================================
    BG_MAIN = '#0d0d0d'       # Darkest - main background
    BG_PANEL = '#1a1a1a'      # Panels, frames
    BG_INPUT = '#252525'      # Input fields
    BG_HOVER = '#333333'      # Hover states
    BG_DARK = '#0a0a0a'       # Darker than main
    
    TEXT_PRIMARY = '#10b981'   # NEXUS Emerald - headers
    TEXT_NORMAL = '#cccccc'    # Light gray - normal text
    TEXT_DIM = '#888888'       # Dim - hints
    TEXT_WHITE = '#ffffff'     # White
    TEXT_BLACK = '#000000'     # Black
    
    # Button colors
    BTN_PRIMARY = '#4b0082'    # Indigo
    BTN_SUCCESS = '#2d5016'    # Dark green
    BTN_DANGER = '#8b0000'     # Dark red
    BTN_INFO = '#1a4a6e'       # Dark blue
    BTN_WARNING = '#8b4500'    # Dark orange
    BTN_GOLD = '#b8860b'       # Dark gold
    BTN_NEUTRAL = '#3a3a3a'    # Gray
    
    # Status colors
    STATUS_ONLINE = '#3fb950'
    STATUS_OFFLINE = '#f85149'
    STATUS_WARNING = '#d29922'
    STATUS_INFO = '#58a6ff'
    
    BORDER = '#3a3a3a'
    
    # ============================================
    # FONTS
    # ============================================
    FONT_FAMILY = 'Segoe UI'
    
    FONT_TITLE = (FONT_FAMILY, 18, 'bold')
    FONT_HEADING = (FONT_FAMILY, 13, 'bold')
    FONT_LABEL = (FONT_FAMILY, 12)
    FONT_BUTTON = (FONT_FAMILY, 11, 'bold')
    FONT_TEXT = (FONT_FAMILY, 11)
    FONT_SMALL = (FONT_FAMILY, 10)
    FONT_MONO = ('Consolas', 11)
    
    # ============================================
    # SPACING
    # ============================================
    PAD_SMALL = 3
    PAD_NORMAL = 5
    PAD_LARGE = 10
    
    BTN_PADX = 12
    BTN_PADY = 6
    
    def __init__(self, root):
        """Initialize theme and apply to root window"""
        self.root = root
        self._apply_global_theme()
    
    def apply(self):
        """Apply theme - for API compatibility (already applied in __init__)"""
        pass

    def get_colors(self):
        """Return a ThemeColors object with current theme colors"""
        colors = ThemeColors()
        colors.bg_dark = self.BG_MAIN
        colors.bg_surface = self.BG_PANEL
        colors.bg_input = self.BG_INPUT
        colors.accent = self.TEXT_PRIMARY
        colors.text_primary = self.TEXT_NORMAL
        colors.text_secondary = self.TEXT_DIM
        colors.text_muted = self.TEXT_DIM
        colors.success = self.STATUS_ONLINE
        colors.warning = self.STATUS_WARNING
        colors.error = self.STATUS_OFFLINE
        return colors

    def _apply_global_theme(self):
        """Apply theme globally to root window"""
        self.root.configure(bg=self.BG_MAIN)
        self.root.option_add('*Background', self.BG_PANEL)
        self.root.option_add('*Foreground', self.TEXT_NORMAL)
        self.root.option_add('*Font', self.FONT_TEXT)
        self.root.option_add('*Entry.Background', self.BG_INPUT)
        self.root.option_add('*Entry.Foreground', self.TEXT_NORMAL)
        self.root.option_add('*Text.Background', self.BG_INPUT)
        self.root.option_add('*Text.Foreground', self.TEXT_NORMAL)
        
        # TTK Styles - use 'clam' theme so custom colors actually apply on Windows
        style = ttk.Style(self.root)
        style.theme_use('clam')

        # Notebook tabs
        style.configure('TNotebook',
            background=self.BG_MAIN,
            borderwidth=0)
        
        style.configure('TNotebook.Tab',
            background=self.BG_PANEL,
            foreground=self.TEXT_WHITE,
            padding=[16, 8],
            font=self.FONT_BUTTON)

        style.map('TNotebook.Tab',
            background=[('selected', self.TEXT_PRIMARY), ('active', self.BG_HOVER)],
            foreground=[('selected', self.TEXT_WHITE), ('active', self.TEXT_WHITE)])
        
        # LabelFrame
        style.configure('TLabelframe',
            background=self.BG_PANEL,
            bordercolor=self.BORDER,
            relief='solid',
            borderwidth=1)
        
        style.configure('TLabelframe.Label',
            background=self.BG_PANEL,
            foreground=self.TEXT_PRIMARY,
            font=self.FONT_HEADING)

        # Treeview - make text readable (white on dark)
        style.configure('Treeview',
            background=self.BG_PANEL,
            foreground='#ffffff',  # White text for visibility
            fieldbackground=self.BG_PANEL,
            borderwidth=0,
            rowheight=28,
            font=self.FONT_TEXT)

        style.configure('Treeview.Heading',
            background=self.BG_INPUT,
            foreground='#ffffff',  # White headers
            font=self.FONT_BUTTON)

        style.map('Treeview',
            background=[('selected', '#10b981')],  # Emerald selection
            foreground=[('selected', '#ffffff')])

    # ============================================
    # COMPONENT BUILDERS
    # ============================================
    
    def button(self, parent, text, command=None, style=ButtonStyle.NEUTRAL, **kwargs):
        """
        Create a themed button.
        
        Args:
            parent: Parent widget
            text: Button text
            command: Click handler
            style: ButtonStyle enum
            **kwargs: Additional tk.Button options
        
        Returns:
            tk.Button
        """
        # Get colors for style
        style_colors = {
            ButtonStyle.PRIMARY: (self.BTN_PRIMARY, self.TEXT_WHITE),
            ButtonStyle.SUCCESS: (self.BTN_SUCCESS, self.TEXT_WHITE),
            ButtonStyle.DANGER: (self.BTN_DANGER, self.TEXT_WHITE),
            ButtonStyle.INFO: (self.BTN_INFO, self.TEXT_WHITE),
            ButtonStyle.WARNING: (self.BTN_WARNING, self.TEXT_WHITE),
            ButtonStyle.GOLD: (self.BTN_GOLD, self.TEXT_BLACK),
            ButtonStyle.NEUTRAL: (self.BTN_NEUTRAL, self.TEXT_NORMAL),
        }
        
        bg, fg = style_colors[style]
        
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            font=self.FONT_BUTTON,
            relief='flat',
            cursor='hand2',
            padx=self.BTN_PADX,
            pady=self.BTN_PADY,
            **kwargs
        )
        
        # Hover effect
        def on_enter(e):
            btn.config(bg=self.BG_HOVER)
        
        def on_leave(e):
            btn.config(bg=bg)
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
    
    def frame(self, parent, **kwargs):
        """Create a themed frame"""
        return tk.Frame(
            parent,
            bg=kwargs.pop('bg', self.BG_PANEL),
            **kwargs
        )
    
    def label_frame(self, parent, text, **kwargs):
        """Create a themed LabelFrame"""
        return ttk.LabelFrame(
            parent,
            text=text,
            **kwargs
        )
    
    def label(self, parent, text, style='normal', **kwargs):
        """
        Create a themed label.
        
        Args:
            parent: Parent widget
            text: Label text
            style: 'title', 'heading', 'normal', 'small', 'dim', 'gold'
            **kwargs: Additional tk.Label options
        """
        fonts = {
            'title': self.FONT_TITLE,
            'heading': self.FONT_HEADING,
            'normal': self.FONT_LABEL,
            'small': self.FONT_SMALL,
            'dim': self.FONT_SMALL,
            'gold': self.FONT_HEADING
        }
        
        colors = {
            'title': self.TEXT_PRIMARY,
            'heading': self.TEXT_PRIMARY,
            'normal': self.TEXT_NORMAL,
            'small': self.TEXT_NORMAL,
            'dim': self.TEXT_DIM,
            'gold': self.TEXT_PRIMARY
        }
        
        return tk.Label(
            parent,
            text=text,
            bg=kwargs.pop('bg', self.BG_PANEL),
            fg=kwargs.pop('fg', colors.get(style, self.TEXT_NORMAL)),
            font=kwargs.pop('font', fonts.get(style, self.FONT_LABEL)),
            **kwargs
        )
    
    def entry(self, parent, **kwargs):
        """Create a themed entry field"""
        return tk.Entry(
            parent,
            bg=self.BG_INPUT,
            fg=self.TEXT_NORMAL,
            font=self.FONT_TEXT,
            insertbackground=self.TEXT_PRIMARY,
            relief='flat',
            **kwargs
        )
    
    def text(self, parent, **kwargs):
        """Create a themed text widget"""
        return tk.Text(
            parent,
            bg=self.BG_INPUT,
            fg=self.TEXT_NORMAL,
            font=self.FONT_TEXT,
            insertbackground=self.TEXT_PRIMARY,
            relief='flat',
            **kwargs
        )
    
    def console(self, parent, height=15, **kwargs):
        """Create a themed console/log widget"""
        return scrolledtext.ScrolledText(
            parent,
            bg=self.BG_DARK,
            fg=self.TEXT_NORMAL,
            font=self.FONT_MONO,
            height=height,
            relief='flat',
            insertbackground=self.TEXT_PRIMARY,
            **kwargs
        )
    
    def section(self, parent, title, **kwargs):
        """
        Create a section header.
        
        Args:
            parent: Parent widget
            title: Section title
            **kwargs: Pack options
        
        Returns:
            tk.Label
        """
        lbl = self.label(parent, title, style='heading')
        lbl.pack(anchor='w', pady=(self.PAD_LARGE, self.PAD_SMALL), **kwargs)
        return lbl
    
    def status_row(self, parent, label_text, status_text, status_type='info', **kwargs):
        """
        Create a status indicator row.
        
        Args:
            parent: Parent widget
            label_text: Label text (e.g., "Arduino")
            status_text: Status text (e.g., "Connected")
            status_type: 'online', 'offline', 'warning', 'info'
            **kwargs: Pack options
        
        Returns:
            Tuple[tk.Frame, tk.Label, tk.Label]
        """
        status_colors = {
            'online': self.STATUS_ONLINE,
            'offline': self.STATUS_OFFLINE,
            'warning': self.STATUS_WARNING,
            'info': self.STATUS_INFO
        }
        
        status_icons = {
            'online': '[ON]',
            'offline': '[OFF]',
            'warning': '[!]',
            'info': '[i]'
        }
        
        frame = self.frame(parent)
        frame.pack(fill='x', pady=self.PAD_SMALL, **kwargs)
        
        # Label
        label = self.label(frame, label_text, style='normal')
        label.pack(side='left', padx=(0, self.PAD_NORMAL))
        
        # Status
        icon = status_icons.get(status_type, '[?]')
        color = status_colors.get(status_type, self.TEXT_NORMAL)
        
        status = self.label(
            frame,
            f"{icon} {status_text}",
            style='normal'
        )
        status.config(fg=color)
        status.pack(side='left')
        
        return frame, label, status
    
    def separator(self, parent, **kwargs):
        """Create a horizontal separator"""
        sep = tk.Frame(
            parent,
            height=1,
            bg=self.BORDER
        )
        sep.pack(fill='x', pady=self.PAD_NORMAL, **kwargs)
        return sep
    
    def button_row(self, parent, buttons, **kwargs):
        """
        Create a row of buttons.
        
        Args:
            parent: Parent widget
            buttons: List of (text, command, style) tuples
            **kwargs: Pack options for frame
        
        Returns:
            tk.Frame containing buttons
        """
        frame = self.frame(parent)
        frame.pack(fill='x', pady=self.PAD_SMALL, **kwargs)
        
        for text, command, style in buttons:
            btn = self.button(frame, text, command=command, style=style)
            btn.pack(side='left', padx=(0, self.PAD_SMALL))
        
        return frame
    
    def grid_frame(self, parent, rows, cols, **kwargs):
        """
        Create a grid container with proper spacing.
        
        Args:
            parent: Parent widget
            rows: Number of rows
            cols: Number of columns
            **kwargs: Frame options
        
        Returns:
            tk.Frame configured for grid layout
        """
        frame = self.frame(parent, **kwargs)
        
        # Configure grid weights
        for i in range(rows):
            frame.grid_rowconfigure(i, weight=1)
        for j in range(cols):
            frame.grid_columnconfigure(j, weight=1)
        
        return frame


# ============================================
# BACKWARDS COMPATIBILITY
# ============================================

def apply_theme(root):
    """Legacy function - creates NexusProTheme instance"""
    return NexusProTheme(root)


def create_themed_label(parent, text, style='normal'):
    """Legacy function"""
    theme = NexusProTheme(parent.winfo_toplevel())
    return theme.label(parent, text, style=style)


def create_themed_button(parent, text, command=None, style='neutral'):
    """Legacy function"""
    theme = NexusProTheme(parent.winfo_toplevel())
    style_map = {
        'primary': ButtonStyle.PRIMARY,
        'success': ButtonStyle.SUCCESS,
        'danger': ButtonStyle.DANGER,
        'neutral': ButtonStyle.NEUTRAL
    }
    return theme.button(parent, text, command=command, style=style_map.get(style, ButtonStyle.NEUTRAL))


def create_themed_frame(parent):
    """Legacy function"""
    theme = NexusProTheme(parent.winfo_toplevel())
    return theme.frame(parent)

# Aliases for compatibility
ProTheme = NexusProTheme

class ThemeColors:
    '''Theme color constants'''
    BG_DARK = '#1a1a2e'
    BG_MEDIUM = '#16213e'
    BG_LIGHT = '#0f3460'
    ACCENT = '#e94560'
    TEXT = '#ffffff'
    SUCCESS = '#00ff00'
    WARNING = '#ffff00'
    ERROR = '#ff0000'
