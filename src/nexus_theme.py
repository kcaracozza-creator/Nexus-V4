#!/usr/bin/env python3
"""
NEXUS Unified Theme System
Consistent colors, fonts, and styles across all GUI components
"""

import tkinter as tk
from tkinter import ttk


class NexusTheme:
    """
    Centralized theme configuration for all NEXUS interfaces
    Gothic/dark theme with gold accents
    """
    
    # ============================================
    # COLOR PALETTE
    # ============================================
    
    # Background colors
    BG_DARKEST = '#0d0d0d'      # Main background (near black)
    BG_DARK = '#1a1a1a'          # Panels and frames
    BG_MEDIUM = '#2a2a2a'        # Input fields, disabled state
    BG_LIGHT = '#3a3a3a'         # Hover states
    
    # Text colors
    TEXT_GOLD = '#e8dcc4'        # Primary text (warm gold)
    TEXT_WHITE = '#ffffff'       # Secondary text
    TEXT_GRAY = '#888888'        # Disabled/hint text
    TEXT_BLACK = '#000000'       # For light backgrounds
    
    # Accent colors
    ACCENT_PURPLE = '#4b0082'    # Primary actions (indigo)
    ACCENT_GREEN = '#00cc00'     # Success/confirm
    ACCENT_RED = '#cc0000'       # Danger/delete
    ACCENT_BLUE = '#0066cc'      # Info/secondary
    ACCENT_ORANGE = '#ff8800'    # Warning
    ACCENT_CYAN = '#00ffff'      # Highlight
    
    # Status colors
    STATUS_SUCCESS = '#38a169'   # Green
    STATUS_WARNING = '#d97706'   # Orange
    STATUS_ERROR = '#dc2626'     # Red
    STATUS_INFO = '#3b82f6'      # Blue
    
    # MTG Colors
    MTG_WHITE = '#f0f0f0'
    MTG_BLUE = '#0066cc'
    MTG_BLACK = '#333333'
    MTG_RED = '#cc0000'
    MTG_GREEN = '#00aa00'
    
    # ============================================
    # FONTS
    # ============================================
    
    FONT_FAMILY = 'Segoe UI'    # Modern, clean, readable
    FONT_MONO = 'Consolas'       # For code/numbers
    FONT_GOTHIC = 'Perpetua'     # For titles (fallback to Segoe UI if not available)
    
    FONT_TITLE = (FONT_GOTHIC, 24, 'bold')
    FONT_SUBTITLE = (FONT_GOTHIC, 16)
    FONT_HEADING = (FONT_FAMILY, 14, 'bold')
    FONT_LABEL = (FONT_FAMILY, 11)
    FONT_BUTTON = (FONT_FAMILY, 11, 'bold')
    FONT_TEXT = (FONT_FAMILY, 10)
    FONT_SMALL = (FONT_FAMILY, 9)
    FONT_CODE = (FONT_MONO, 10)
    
    # ============================================
    # BUTTON STYLES
    # ============================================
    
    @classmethod
    def button_primary(cls, **kwargs):
        """Primary action button (purple)"""
        defaults = {
            'bg': cls.ACCENT_PURPLE,
            'fg': cls.TEXT_WHITE,
            'font': cls.FONT_BUTTON,
            'relief': 'flat',
            'padx': 15,
            'pady': 8,
            'cursor': 'hand2',
            'activebackground': '#6a00b4',
            'activeforeground': cls.TEXT_WHITE
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def button_success(cls, **kwargs):
        """Success/confirm button (green)"""
        defaults = {
            'bg': cls.ACCENT_GREEN,
            'fg': cls.TEXT_WHITE,
            'font': cls.FONT_BUTTON,
            'relief': 'flat',
            'padx': 15,
            'pady': 8,
            'cursor': 'hand2',
            'activebackground': '#00ff00',
            'activeforeground': cls.TEXT_WHITE
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def button_danger(cls, **kwargs):
        """Danger/delete button (red)"""
        defaults = {
            'bg': cls.ACCENT_RED,
            'fg': cls.TEXT_WHITE,
            'font': cls.FONT_BUTTON,
            'relief': 'flat',
            'padx': 15,
            'pady': 8,
            'cursor': 'hand2',
            'activebackground': '#ff0000',
            'activeforeground': cls.TEXT_WHITE
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def button_info(cls, **kwargs):
        """Info/secondary button (blue)"""
        defaults = {
            'bg': cls.ACCENT_BLUE,
            'fg': cls.TEXT_WHITE,
            'font': cls.FONT_BUTTON,
            'relief': 'flat',
            'padx': 15,
            'pady': 8,
            'cursor': 'hand2',
            'activebackground': '#0088ff',
            'activeforeground': cls.TEXT_WHITE
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def button_default(cls, **kwargs):
        """Default/neutral button (gray)"""
        defaults = {
            'bg': '#666666',
            'fg': cls.TEXT_WHITE,
            'font': cls.FONT_BUTTON,
            'relief': 'flat',
            'padx': 15,
            'pady': 8,
            'cursor': 'hand2',
            'activebackground': '#888888',
            'activeforeground': cls.TEXT_WHITE
        }
        defaults.update(kwargs)
        return defaults
    
    # ============================================
    # FRAME STYLES
    # ============================================
    
    @classmethod
    def frame_main(cls, **kwargs):
        """Main container frame"""
        defaults = {
            'bg': cls.BG_DARKEST
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def frame_panel(cls, **kwargs):
        """Panel/section frame"""
        defaults = {
            'bg': cls.BG_DARK,
            'relief': 'flat',
            'bd': 0
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def frame_control(cls, **kwargs):
        """Control/button container frame"""
        defaults = {
            'bg': cls.BG_DARK
        }
        defaults.update(kwargs)
        return defaults
    
    # ============================================
    # LABEL STYLES
    # ============================================
    
    @classmethod
    def label_title(cls, **kwargs):
        """Page title label"""
        defaults = {
            'font': cls.FONT_TITLE,
            'fg': cls.TEXT_GOLD,
            'bg': cls.BG_DARKEST
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def label_heading(cls, **kwargs):
        """Section heading label"""
        defaults = {
            'font': cls.FONT_HEADING,
            'fg': cls.TEXT_GOLD,
            'bg': cls.BG_DARK
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def label_text(cls, **kwargs):
        """Normal text label"""
        defaults = {
            'font': cls.FONT_LABEL,
            'fg': cls.TEXT_WHITE,
            'bg': cls.BG_DARK
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def label_status(cls, status='info', **kwargs):
        """Status label with color coding"""
        color_map = {
            'success': cls.STATUS_SUCCESS,
            'warning': cls.STATUS_WARNING,
            'error': cls.STATUS_ERROR,
            'info': cls.STATUS_INFO
        }
        defaults = {
            'font': cls.FONT_LABEL,
            'fg': color_map.get(status, cls.TEXT_GOLD),
            'bg': cls.BG_DARK
        }
        defaults.update(kwargs)
        return defaults
    
    # ============================================
    # ENTRY/INPUT STYLES
    # ============================================
    
    @classmethod
    def entry_standard(cls, **kwargs):
        """Standard text entry field"""
        defaults = {
            'font': cls.FONT_TEXT,
            'bg': cls.BG_MEDIUM,
            'fg': cls.TEXT_WHITE,
            'insertbackground': cls.TEXT_WHITE,
            'relief': 'sunken',
            'bd': 2
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def text_standard(cls, **kwargs):
        """Standard text widget (multiline)"""
        defaults = {
            'font': cls.FONT_TEXT,
            'bg': cls.BG_MEDIUM,
            'fg': cls.TEXT_GOLD,
            'insertbackground': cls.TEXT_GOLD,
            'relief': 'sunken',
            'bd': 2,
            'wrap': 'word'
        }
        defaults.update(kwargs)
        return defaults
    
    @classmethod
    def text_code(cls, **kwargs):
        """Code/monospace text widget"""
        defaults = {
            'font': cls.FONT_CODE,
            'bg': cls.BG_DARKEST,
            'fg': cls.ACCENT_GREEN,
            'insertbackground': cls.ACCENT_GREEN,
            'relief': 'sunken',
            'bd': 2,
            'wrap': 'none'
        }
        defaults.update(kwargs)
        return defaults
    
    # ============================================
    # TTK STYLE CONFIGURATION
    # ============================================
    
    @classmethod
    def configure_ttk_styles(cls, root):
        """Configure TTK widget styles to match NEXUS theme"""
        style = ttk.Style(root)
        
        # Notebook (tabs)
        style.configure('TNotebook',
                       background=cls.BG_DARKEST,
                       borderwidth=0,
                       tabmargins=[2, 5, 2, 0])
        
        style.configure('TNotebook.Tab',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_GOLD,
                       padding=[20, 10],
                       borderwidth=1)
        
        style.map('TNotebook.Tab',
                 background=[('selected', cls.BG_MEDIUM), ('active', cls.BG_LIGHT)],
                 foreground=[('selected', cls.TEXT_WHITE), ('active', cls.TEXT_WHITE)])
        
        # LabelFrame
        style.configure('TLabelframe',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_GOLD,
                       borderwidth=1,
                       relief='solid')
        
        style.configure('TLabelframe.Label',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_GOLD,
                       font=cls.FONT_HEADING)
        
        # Treeview (for tables)
        style.configure('Treeview',
                       background=cls.BG_MEDIUM,
                       foreground=cls.TEXT_WHITE,
                       fieldbackground=cls.BG_MEDIUM,
                       font=cls.FONT_TEXT)
        
        style.configure('Treeview.Heading',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_GOLD,
                       font=cls.FONT_HEADING)
        
        style.map('Treeview',
                 background=[('selected', cls.ACCENT_PURPLE)],
                 foreground=[('selected', cls.TEXT_WHITE)])
        
        # Scrollbar
        style.configure('Vertical.TScrollbar',
                       background=cls.BG_DARK,
                       troughcolor=cls.BG_DARKEST,
                       borderwidth=0,
                       arrowcolor=cls.TEXT_GOLD)


# ============================================
# UTILITY FUNCTIONS
# ============================================

def apply_theme_to_widget(widget, widget_type='frame', **custom):
    """
    Apply NEXUS theme to any widget
    
    Args:
        widget: tkinter widget instance
        widget_type: 'frame', 'button_primary', 'label_text', etc.
        **custom: Override specific attributes
    """
    theme = NexusTheme()
    
    # Get style method
    style_method = getattr(theme, widget_type, None)
    if not style_method:
        print(f"Warning: Unknown widget type '{widget_type}'")
        return
    
    # Apply style
    style = style_method(**custom)
    try:
        widget.configure(**style)
    except tk.TclError as e:
        print(f"Warning: Could not apply all theme attributes: {e}")


def create_themed_button(parent, text, command=None, style='primary', **custom):
    """
    Create a button with NEXUS theme
    
    Args:
        parent: Parent widget
        text: Button text
        command: Button command callback
        style: 'primary', 'success', 'danger', 'info', 'default'
        **custom: Override attributes
    
    Returns:
        Themed tk.Button
    """
    theme = NexusTheme()
    style_method = getattr(theme, f'button_{style}', theme.button_default)
    style_attrs = style_method(**custom)
    
    return tk.Button(parent, text=text, command=command, **style_attrs)


def create_themed_label(parent, text, style='text', **custom):
    """
    Create a label with NEXUS theme
    
    Args:
        parent: Parent widget
        text: Label text
        style: 'title', 'heading', 'text', 'status'
        **custom: Override attributes
    
    Returns:
        Themed tk.Label
    """
    theme = NexusTheme()
    style_method = getattr(theme, f'label_{style}', theme.label_text)
    style_attrs = style_method(**custom)
    
    return tk.Label(parent, text=text, **style_attrs)


def create_themed_entry(parent, **custom):
    """
    Create an entry widget with NEXUS theme
    
    Returns:
        Themed tk.Entry
    """
    theme = NexusTheme()
    style_attrs = theme.entry_standard(**custom)
    
    return tk.Entry(parent, **style_attrs)


def create_themed_frame(parent, style='panel', **custom):
    """
    Create a frame with NEXUS theme
    
    Args:
        parent: Parent widget
        style: 'main', 'panel', 'control'
        **custom: Override attributes
    
    Returns:
        Themed tk.Frame
    """
    theme = NexusTheme()
    style_method = getattr(theme, f'frame_{style}', theme.frame_panel)
    style_attrs = style_method(**custom)
    
    return tk.Frame(parent, **style_attrs)


# ============================================
# DEMO
# ============================================

if __name__ == '__main__':
    root = tk.Tk()
    root.title("NEXUS Theme Demo")
    root.geometry("800x600")
    root.configure(bg=NexusTheme.BG_DARKEST)
    
    # Configure TTK styles
    NexusTheme.configure_ttk_styles(root)
    
    # Title
    create_themed_label(root, "🎨 NEXUS UNIFIED THEME", style='title').pack(pady=20)
    
    # Button examples
    button_frame = create_themed_frame(root, style='control')
    button_frame.pack(pady=10, padx=20, fill='x')
    
    create_themed_button(button_frame, "Primary Action", style='primary').pack(side='left', padx=5)
    create_themed_button(button_frame, "Success", style='success').pack(side='left', padx=5)
    create_themed_button(button_frame, "Danger", style='danger').pack(side='left', padx=5)
    create_themed_button(button_frame, "Info", style='info').pack(side='left', padx=5)
    create_themed_button(button_frame, "Default", style='default').pack(side='left', padx=5)
    
    # Label examples
    label_frame = create_themed_frame(root, style='panel')
    label_frame.pack(pady=10, padx=20, fill='x')
    
    create_themed_label(label_frame, "Section Heading", style='heading').pack(anchor='w', pady=5)
    create_themed_label(label_frame, "Normal text label with theme applied", style='text').pack(anchor='w', pady=5)
    create_themed_label(label_frame, "✅ Success status", style='status', status='success').pack(anchor='w', pady=5)
    create_themed_label(label_frame, "⚠️ Warning status", style='status', status='warning').pack(anchor='w', pady=5)
    create_themed_label(label_frame, "❌ Error status", style='status', status='error').pack(anchor='w', pady=5)
    
    # Entry example
    entry_frame = create_themed_frame(root, style='panel')
    entry_frame.pack(pady=10, padx=20, fill='x')
    
    create_themed_label(entry_frame, "Text Input:", style='text').pack(side='left', padx=5)
    entry = create_themed_entry(entry_frame, width=30)
    entry.pack(side='left', padx=5)
    entry.insert(0, "Themed text entry")
    
    # Text widget example
    text_frame = create_themed_frame(root, style='panel')
    text_frame.pack(pady=10, padx=20, fill='both', expand=True)
    
    create_themed_label(text_frame, "Text Widget:", style='heading').pack(anchor='w', pady=5)
    
    theme = NexusTheme()
    text_widget = tk.Text(text_frame, height=10, **theme.text_standard())
    text_widget.pack(fill='both', expand=True, padx=5, pady=5)
    text_widget.insert('1.0', "This is a themed text widget\nWith multiple lines\nAnd consistent styling!")
    
    root.mainloop()
