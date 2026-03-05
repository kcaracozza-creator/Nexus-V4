"""
Enhanced Theme Manager for NEXUS V2
Centralized theme management with consistent styling across all components
"""

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Dict, Any, Optional
import sys
import os

# Add parent path for config import
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from config import get_config
except ImportError:
    get_config = None

@dataclass 
class EnhancedThemeColors:
    """Enhanced color palette with comprehensive theme support"""
    
    # Primary Background Colors
    bg_primary: str = "#0a0a0f"      # Deep black (from audit spec)
    bg_secondary: str = "#12121a"     # Card background (from audit spec) 
    bg_surface: str = "#1a1a24"      # Elevated surfaces
    bg_elevated: str = "#232334"     # Modal/popup backgrounds
    
    # Border and Divider Colors
    border_primary: str = "#2a2a3a"
    border_secondary: str = "#3a3a4a"
    border_focus: str = "#6366f1"    # Indigo (from audit spec)
    
    # Text Colors
    text_primary: str = "#f8fafc"    # White (from audit spec)
    text_secondary: str = "#e2e8f0"
    text_muted: str = "#64748b"      # Gray (from audit spec)
    text_disabled: str = "#475569"
    
    # Accent Colors (from audit design specs)
    primary: str = "#6366f1"         # Indigo - main actions
    primary_hover: str = "#5855f1"
    primary_pressed: str = "#4f46e5"
    
    # Status Colors (from audit design specs)
    success: str = "#22c55e"         # Green - positive
    success_hover: str = "#16a34a"
    warning: str = "#f59e0b"         # Amber - caution  
    warning_hover: str = "#d97706"
    error: str = "#ef4444"           # Red - critical
    error_hover: str = "#dc2626"
    info: str = "#3b82f6"           # Blue - informational
    info_hover: str = "#2563eb"
    
    # Input Field Colors
    input_bg: str = "#1a1a24"
    input_border: str = "#2a2a3a"
    input_border_focus: str = "#6366f1"
    input_placeholder: str = "#64748b"
    
    # Button Colors
    button_primary_bg: str = "#6366f1"
    button_primary_text: str = "#ffffff"
    button_secondary_bg: str = "#374151"
    button_secondary_text: str = "#f8fafc"
    button_danger_bg: str = "#ef4444"
    button_danger_text: str = "#ffffff"
    
    # Table/List Colors
    table_header_bg: str = "#232334"
    table_row_even: str = "#1a1a24"
    table_row_odd: str = "#12121a"
    table_row_hover: str = "#2a2a3a"
    table_row_selected: str = "#3730a3"
    
    # Card Rarity Colors (MTG specific)
    rarity_common: str = "#64748b"
    rarity_uncommon: str = "#71717a"
    rarity_rare: str = "#eab308"
    rarity_mythic: str = "#dc2626"
    rarity_special: str = "#a855f7"
    
    # Mana Colors (MTG specific)
    mana_white: str = "#fefce8"
    mana_blue: str = "#1e40af"
    mana_black: str = "#18181b"
    mana_red: str = "#dc2626"
    mana_green: str = "#166534"
    mana_colorless: str = "#64748b"

class EnhancedThemeManager:
    """Enhanced theme management with comprehensive styling"""
    
    def __init__(self):
        self.colors = EnhancedThemeColors()
        self.fonts = self._setup_fonts()
        self.styles = {}
        
    def _setup_fonts(self) -> Dict[str, Dict[str, Any]]:
        """Setup font configurations from audit specifications"""
        return {
            'primary': {
                'family': 'Inter',
                'fallback': 'Segoe UI',
                'sizes': {
                    'small': 11,
                    'normal': 14,
                    'medium': 16,
                    'large': 18,
                    'xlarge': 24,
                    'xxlarge': 32
                }
            },
            'monospace': {
                'family': 'JetBrains Mono',
                'fallback': 'Consolas',
                'sizes': {
                    'small': 10,
                    'normal': 12,
                    'medium': 14,
                    'large': 16
                }
            },
            'heading': {
                'family': 'Inter',
                'fallback': 'Segoe UI',
                'weight': 'semibold',
                'tracking': 'tight'
            }
        }
    
    def apply_theme(self, root: tk.Tk):
        """Apply comprehensive theme to the application"""
        # Configure root window
        root.configure(bg=self.colors.bg_primary)
        
        # Setup TTK style
        self._setup_ttk_styles(root)
        
        # Apply global styles
        self._apply_global_styles(root)
        
    def _setup_ttk_styles(self, root: tk.Tk):
        """Setup TTK styles with enhanced theme"""
        style = ttk.Style()
        
        # Configure theme
        style.theme_use('clam')  # Use clam as base for customization
        
        # Frame styles
        style.configure('Card.TFrame',
                       background=self.colors.bg_secondary,
                       relief='flat',
                       borderwidth=1)
        
        style.configure('Elevated.TFrame', 
                       background=self.colors.bg_elevated,
                       relief='raised',
                       borderwidth=1)
        
        # Button styles
        style.configure('Primary.TButton',
                       background=self.colors.button_primary_bg,
                       foreground=self.colors.button_primary_text,
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat')
        
        style.map('Primary.TButton',
                 background=[('active', self.colors.primary_hover),
                           ('pressed', self.colors.primary_pressed)])
        
        style.configure('Secondary.TButton',
                       background=self.colors.button_secondary_bg,
                       foreground=self.colors.button_secondary_text,
                       focuscolor='none',
                       borderwidth=1,
                       relief='flat')
        
        style.configure('Danger.TButton',
                       background=self.colors.button_danger_bg,
                       foreground=self.colors.button_danger_text,
                       focuscolor='none',
                       borderwidth=0,
                       relief='flat')
        
        # Entry styles
        style.configure('Enhanced.TEntry',
                       fieldbackground=self.colors.input_bg,
                       foreground=self.colors.text_primary,
                       bordercolor=self.colors.input_border,
                       insertcolor=self.colors.text_primary,
                       selectbackground=self.colors.primary,
                       selectforeground=self.colors.text_primary)
        
        style.map('Enhanced.TEntry',
                 bordercolor=[('focus', self.colors.input_border_focus)])
        
        # Label styles
        style.configure('Heading.TLabel',
                       background=self.colors.bg_primary,
                       foreground=self.colors.text_primary,
                       font=(self.fonts['heading']['fallback'], 16, 'bold'))
        
        style.configure('Body.TLabel',
                       background=self.colors.bg_primary,
                       foreground=self.colors.text_secondary,
                       font=(self.fonts['primary']['fallback'], 12))
        
        style.configure('Muted.TLabel',
                       background=self.colors.bg_primary,
                       foreground=self.colors.text_muted,
                       font=(self.fonts['primary']['fallback'], 10))
        
        # Notebook (tab) styles
        style.configure('Enhanced.TNotebook',
                       background=self.colors.bg_primary,
                       borderwidth=0)
        
        style.configure('Enhanced.TNotebook.Tab',
                       background=self.colors.bg_secondary,
                       foreground=self.colors.text_muted,
                       padding=[20, 12],
                       borderwidth=0)
        
        style.map('Enhanced.TNotebook.Tab',
                 background=[('selected', self.colors.bg_elevated),
                           ('active', self.colors.bg_surface)],
                 foreground=[('selected', self.colors.text_primary),
                           ('active', self.colors.text_secondary)])
        
        # Treeview styles
        style.configure('Enhanced.Treeview',
                       background=self.colors.table_row_even,
                       foreground=self.colors.text_primary,
                       fieldbackground=self.colors.table_row_even,
                       borderwidth=0)
        
        style.configure('Enhanced.Treeview.Heading',
                       background=self.colors.table_header_bg,
                       foreground=self.colors.text_primary,
                       relief='flat',
                       borderwidth=1)
        
        style.map('Enhanced.Treeview',
                 background=[('selected', self.colors.table_row_selected)],
                 foreground=[('selected', self.colors.text_primary)])
        
        # Scrollbar styles
        style.configure('Enhanced.Vertical.TScrollbar',
                       background=self.colors.bg_secondary,
                       troughcolor=self.colors.bg_primary,
                       borderwidth=0,
                       arrowcolor=self.colors.text_muted,
                       darkcolor=self.colors.bg_secondary,
                       lightcolor=self.colors.bg_secondary)
        
    def _apply_global_styles(self, root: tk.Tk):
        """Apply global styling preferences"""
        # Set default colors for standard tkinter widgets
        root.option_add('*Background', self.colors.bg_primary)
        root.option_add('*Foreground', self.colors.text_primary)
        root.option_add('*selectBackground', self.colors.primary)
        root.option_add('*selectForeground', self.colors.text_primary)
        root.option_add('*insertBackground', self.colors.text_primary)
        root.option_add('*highlightBackground', self.colors.bg_primary)
        root.option_add('*highlightColor', self.colors.border_focus)
        
    def create_styled_widget(self, widget_type: str, parent, **kwargs) -> tk.Widget:
        """Create a widget with enhanced theming applied"""
        
        base_config = {
            'bg': self.colors.bg_secondary,
            'fg': self.colors.text_primary,
            'relief': 'flat',
            'borderwidth': 0
        }
        
        # Widget-specific configurations
        widget_configs = {
            'Frame': {
                'bg': self.colors.bg_secondary,
                'relief': 'flat'
            },
            'Label': {
                'bg': self.colors.bg_primary,
                'fg': self.colors.text_primary,
                'font': (self.fonts['primary']['fallback'], 12)
            },
            'Button': {
                'bg': self.colors.button_primary_bg,
                'fg': self.colors.button_primary_text,
                'activebackground': self.colors.primary_hover,
                'activeforeground': self.colors.text_primary,
                'relief': 'flat',
                'borderwidth': 0,
                'cursor': 'hand2'
            },
            'Entry': {
                'bg': self.colors.input_bg,
                'fg': self.colors.text_primary,
                'insertbackground': self.colors.text_primary,
                'selectbackground': self.colors.primary,
                'relief': 'solid',
                'borderwidth': 1,
                'highlightthickness': 2,
                'highlightcolor': self.colors.border_focus,
                'highlightbackground': self.colors.input_border
            },
            'Text': {
                'bg': self.colors.input_bg,
                'fg': self.colors.text_primary,
                'insertbackground': self.colors.text_primary,
                'selectbackground': self.colors.primary,
                'relief': 'solid',
                'borderwidth': 1,
                'highlightthickness': 2,
                'highlightcolor': self.colors.border_focus,
                'highlightbackground': self.colors.input_border
            },
            'Listbox': {
                'bg': self.colors.bg_secondary,
                'fg': self.colors.text_primary,
                'selectbackground': self.colors.table_row_selected,
                'selectforeground': self.colors.text_primary,
                'relief': 'solid',
                'borderwidth': 1,
                'highlightthickness': 0
            }
        }
        
        # Merge base config with widget-specific config and user kwargs
        config = {**base_config}
        if widget_type in widget_configs:
            config.update(widget_configs[widget_type])
        config.update(kwargs)
        
        # Create the widget
        widget_class = getattr(tk, widget_type)
        widget = widget_class(parent, **config)
        
        return widget
    
    def get_color(self, color_name: str) -> str:
        """Get color value by name"""
        return getattr(self.colors, color_name, self.colors.text_primary)
    
    def get_font(self, font_type: str = 'primary', size: str = 'normal') -> tuple:
        """Get font configuration"""
        font_config = self.fonts.get(font_type, self.fonts['primary'])
        family = font_config.get('fallback', 'Segoe UI')
        font_size = font_config['sizes'].get(size, 12)
        weight = font_config.get('weight', 'normal')
        
        return (family, font_size, weight)

# Global theme manager instance
theme_manager = EnhancedThemeManager()

# Convenience functions
def apply_theme(root: tk.Tk):
    """Apply enhanced theme to application"""
    theme_manager.apply_theme(root)

def create_styled_widget(widget_type: str, parent, **kwargs):
    """Create a styled widget"""
    return theme_manager.create_styled_widget(widget_type, parent, **kwargs)

def get_color(color_name: str) -> str:
    """Get color value"""
    return theme_manager.get_color(color_name)

def get_font(font_type: str = 'primary', size: str = 'normal') -> tuple:
    """Get font configuration"""
    return theme_manager.get_font(font_type, size)