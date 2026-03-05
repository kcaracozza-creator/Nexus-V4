#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              NEXUS HARDWARE SCANNER TAB - PRO REDESIGN                       ║
║                                                                               ║
║  BEFORE: Rainbow button soup, inconsistent fonts, cramped spacing            ║
║  AFTER: Clean, professional, enterprise-grade                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

This is a REFERENCE IMPLEMENTATION showing how to rebuild NEXUS tabs
using the NexusProTheme system.

Author: Jaques (The Twat Rocket)
For: Judge Miyagi 🐐
Date: Dec 2, 2025
"""

import tkinter as tk
from tkinter import ttk
from nexus_pro_theme import (
    NexusProTheme, Colors, Typography, Spacing, 
    ButtonStyle, ButtonSize
)


def create_hardware_scanner_tab_pro(self, notebook: ttk.Notebook):
    """
    REDESIGNED Hardware Scanner Tab
    
    This replaces the old create_hardware_scanner_tab() method.
    Copy this pattern for other tabs.
    """
    
    # Get theme reference (assumes self.theme exists)
    theme = self.theme
    
    # ══════════════════════════════════════════════════════════════════════════
    # MAIN TAB FRAME
    # ══════════════════════════════════════════════════════════════════════════
    tab = theme.frame(notebook, bg=Colors.BG_BASE)
    notebook.add(tab, text="  Hardware Scanner  ")
    
    # Main content container with padding
    content = theme.frame(tab, bg=Colors.BG_BASE)
    content.pack(fill='both', expand=True, padx=Spacing.XL, pady=Spacing.LG)
    
    # ══════════════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════════════
    header = theme.header(
        content, 
        "Hardware Scanner",
        "Arduino control, camera integration, and LED management"
    )
    header.pack(fill='x', pady=(0, Spacing.XL))
    
    # ══════════════════════════════════════════════════════════════════════════
    # MAIN LAYOUT - Two columns
    # ══════════════════════════════════════════════════════════════════════════
    columns = theme.frame(content, bg=Colors.BG_BASE)
    columns.pack(fill='both', expand=True)
    
    # Left column (controls)
    left_col = theme.frame(columns, bg=Colors.BG_BASE)
    left_col.pack(side='left', fill='both', expand=True, padx=(0, Spacing.MD))
    
    # Right column (output)
    right_col = theme.frame(columns, bg=Colors.BG_BASE)
    right_col.pack(side='right', fill='both', expand=True, padx=(Spacing.MD, 0))
    
    # ══════════════════════════════════════════════════════════════════════════
    # CONNECTION STATUS SECTION (Left Column)
    # ══════════════════════════════════════════════════════════════════════════
    status_section = theme.section(left_col, "Connection Status")
    status_section.pack(fill='x', pady=(0, Spacing.MD))
    
    # Port selector row
    port_row = theme.frame(status_section, bg=Colors.BG_CARD)
    port_row.pack(fill='x', pady=Spacing.SM)
    
    port_label = theme.label(port_row, "Arduino Port:", style='label')
    port_label.pack(side='left')
    
    # Port dropdown
    self.port_var = tk.StringVar(value="AUTO")
    port_combo = theme.combobox(
        port_row,
        values=["AUTO", "COM1", "COM3", "COM4", "COM5", "COM6", "COM13", "COM14", "COM15"],
        width=10
    )
    port_combo.configure(textvariable=self.port_var)
    port_combo.pack(side='left', padx=Spacing.SM)
    
    # Port action buttons
    port_buttons = theme.button_group(port_row, [
        {'text': 'Scan', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM,
         'command': lambda: self.scan_com_ports() if hasattr(self, 'scan_com_ports') else None},
        {'text': 'Connect', 'style': ButtonStyle.SUCCESS, 'size': ButtonSize.SM,
         'command': lambda: self.connect_arduino() if hasattr(self, 'connect_arduino') else None},
    ])
    port_buttons.pack(side='left', padx=Spacing.SM)
    
    # Status indicators
    theme.status_row(status_section, "Arduino", "Disconnected", "offline").pack(fill='x', pady=2)
    theme.status_row(status_section, "Camera", "Not Found", "offline").pack(fill='x', pady=2)
    theme.status_row(status_section, "NeoPixel LEDs", "Offline", "offline").pack(fill='x', pady=2)
    
    # ══════════════════════════════════════════════════════════════════════════
    # SCANNER CONTROLS SECTION (Left Column)
    # ══════════════════════════════════════════════════════════════════════════
    controls_section = theme.section(left_col, "Scanner Controls")
    controls_section.pack(fill='x', pady=Spacing.MD)
    
    # Intake mode toggle
    intake_row = theme.frame(controls_section, bg=Colors.BG_CARD)
    intake_row.pack(fill='x', pady=Spacing.SM)
    
    self.intake_mode_var = tk.BooleanVar(value=False)
    intake_cb = theme.checkbox(
        intake_row,
        text="INTAKE MODE (Track acquisition details)",
        variable=self.intake_mode_var
    )
    intake_cb.pack(side='left')
    
    # Scan buttons - using semantic colors
    scan_buttons = theme.frame(controls_section, bg=Colors.BG_CARD)
    scan_buttons.pack(fill='x', pady=Spacing.MD)
    
    btn_single = theme.button(
        scan_buttons,
        text="Single Scan",
        style=ButtonStyle.PRIMARY,
        size=ButtonSize.LG,
        command=lambda: self.single_card_scan() if hasattr(self, 'single_card_scan') else None
    )
    btn_single.pack(side='left', padx=(0, Spacing.SM))
    
    btn_batch = theme.button(
        scan_buttons,
        text="Batch Scan",
        style=ButtonStyle.SECONDARY,
        size=ButtonSize.LG,
        command=lambda: self.batch_scan_cards() if hasattr(self, 'batch_scan_cards') else None
    )
    btn_batch.pack(side='left', padx=Spacing.SM)
    
    btn_test = theme.button(
        scan_buttons,
        text="Hardware Test",
        style=ButtonStyle.WARNING,
        size=ButtonSize.LG,
        command=lambda: self.test_hardware() if hasattr(self, 'test_hardware') else None
    )
    btn_test.pack(side='left', padx=Spacing.SM)
    
    btn_calibrate = theme.button(
        scan_buttons,
        text="Calibrate",
        style=ButtonStyle.GHOST,
        size=ButtonSize.LG,
        command=lambda: self.calibrate_hardware() if hasattr(self, 'calibrate_hardware') else None
    )
    btn_calibrate.pack(side='left', padx=Spacing.SM)
    
    # ══════════════════════════════════════════════════════════════════════════
    # RGB LED CONTROL SECTION (Left Column)
    # ══════════════════════════════════════════════════════════════════════════
    rgb_section = theme.section(left_col, "NeoPixel RGB Control")
    rgb_section.pack(fill='x', pady=Spacing.MD)
    
    # RGB Preview
    preview_row = theme.frame(rgb_section, bg=Colors.BG_CARD)
    preview_row.pack(fill='x', pady=Spacing.SM)
    
    preview_label = theme.label(preview_row, "Live Preview:", style='label')
    preview_label.pack(side='left')
    
    self.rgb_preview_canvas = tk.Canvas(
        preview_row,
        width=120,
        height=32,
        bg='#00ff00',
        highlightthickness=1,
        highlightbackground=Colors.BORDER
    )
    self.rgb_preview_canvas.pack(side='left', padx=Spacing.MD)
    
    self.rgb_value_label = theme.label(preview_row, "RGB(0, 255, 0) | 50%", style='secondary')
    self.rgb_value_label.pack(side='left')
    
    # RGB Sliders
    sliders_frame = theme.frame(rgb_section, bg=Colors.BG_CARD)
    sliders_frame.pack(fill='x', pady=Spacing.MD)
    
    # Red slider
    red_row = theme.frame(sliders_frame, bg=Colors.BG_CARD)
    red_row.pack(fill='x', pady=Spacing.XS)
    
    theme.label(red_row, "Red:", style='label').pack(side='left', padx=(0, Spacing.SM))
    self.red_scale = theme.scale(red_row, from_=0, to=255, length=300)
    self.red_scale.pack(side='left', fill='x', expand=True)
    self.red_value = theme.label(red_row, "0", style='mono')
    self.red_value.pack(side='left', padx=Spacing.SM)
    
    # Green slider
    green_row = theme.frame(sliders_frame, bg=Colors.BG_CARD)
    green_row.pack(fill='x', pady=Spacing.XS)
    
    theme.label(green_row, "Green:", style='label').pack(side='left', padx=(0, Spacing.SM))
    self.green_scale = theme.scale(green_row, from_=0, to=255, length=300)
    self.green_scale.set(255)
    self.green_scale.pack(side='left', fill='x', expand=True)
    self.green_value = theme.label(green_row, "255", style='mono')
    self.green_value.pack(side='left', padx=Spacing.SM)
    
    # Blue slider
    blue_row = theme.frame(sliders_frame, bg=Colors.BG_CARD)
    blue_row.pack(fill='x', pady=Spacing.XS)
    
    theme.label(blue_row, "Blue:", style='label').pack(side='left', padx=(0, Spacing.SM))
    self.blue_scale = theme.scale(blue_row, from_=0, to=255, length=300)
    self.blue_scale.pack(side='left', fill='x', expand=True)
    self.blue_value = theme.label(blue_row, "0", style='mono')
    self.blue_value.pack(side='left', padx=Spacing.SM)
    
    # Brightness slider
    bright_row = theme.frame(sliders_frame, bg=Colors.BG_CARD)
    bright_row.pack(fill='x', pady=Spacing.XS)
    
    theme.label(bright_row, "Brightness:", style='label').pack(side='left', padx=(0, Spacing.SM))
    self.brightness_scale = theme.scale(bright_row, from_=0, to=100, length=300)
    self.brightness_scale.set(50)
    self.brightness_scale.pack(side='left', fill='x', expand=True)
    self.brightness_value = theme.label(bright_row, "50%", style='mono')
    self.brightness_value.pack(side='left', padx=Spacing.SM)
    
    # RGB action buttons
    rgb_actions = theme.frame(rgb_section, bg=Colors.BG_CARD)
    rgb_actions.pack(fill='x', pady=Spacing.MD)
    
    theme.button(
        rgb_actions, text="Send to Arduino", style=ButtonStyle.SUCCESS,
        command=lambda: self.send_rgb_to_arduino() if hasattr(self, 'send_rgb_to_arduino') else None
    ).pack(side='left', padx=(0, Spacing.MD))
    
    # Color presets - now using consistent ghost style
    preset_label = theme.label(rgb_actions, "Presets:", style='muted')
    preset_label.pack(side='left', padx=(0, Spacing.SM))
    
    presets = theme.button_group(rgb_actions, [
        {'text': 'Red', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'Green', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'Blue', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'White', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'Off', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
    ])
    presets.pack(side='left')
    
    # Pattern buttons
    pattern_row = theme.frame(rgb_section, bg=Colors.BG_CARD)
    pattern_row.pack(fill='x', pady=Spacing.SM)
    
    pattern_label = theme.label(pattern_row, "Patterns:", style='muted')
    pattern_label.pack(side='left', padx=(0, Spacing.SM))
    
    patterns = theme.button_group(pattern_row, [
        {'text': 'Solid', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'Pulse', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'Rainbow', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'Chase', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
        {'text': 'Sparkle', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
    ])
    patterns.pack(side='left')
    
    # ══════════════════════════════════════════════════════════════════════════
    # SCAN OUTPUT SECTION (Right Column)
    # ══════════════════════════════════════════════════════════════════════════
    output_section = theme.section(right_col, "Scan Output")
    output_section.pack(fill='both', expand=True)
    
    # Console for scan output
    self.scan_console = theme.console(output_section, height=20)
    self.scan_console.pack(fill='both', expand=True)
    
    # Welcome message
    welcome = """HARDWARE SCANNER READY
══════════════════════════════════════════════════════════════

STATUS: Waiting for hardware connection

AVAILABLE ACTIONS:
  • Connect Arduino via USB port
  • Run hardware diagnostics
  • Calibrate scanner settings
  • Control NeoPixel RGB LEDs

Connect your hardware to begin scanning.
"""
    self.scan_console.insert('1.0', welcome)
    
    # ══════════════════════════════════════════════════════════════════════════
    # CAMERA PREVIEW SECTION (Right Column)
    # ══════════════════════════════════════════════════════════════════════════
    camera_section = theme.section(right_col, "Camera Preview")
    camera_section.pack(fill='x', pady=Spacing.MD)
    
    # Camera placeholder
    camera_frame = theme.frame(camera_section, bg=Colors.BG_ELEVATED)
    camera_frame.pack(fill='x', pady=Spacing.SM)
    
    camera_placeholder = tk.Label(
        camera_frame,
        text="Camera feed will appear here",
        font=Typography.BODY_MD,
        fg=Colors.TEXT_MUTED,
        bg=Colors.BG_ELEVATED,
        height=8
    )
    camera_placeholder.pack(fill='both', expand=True, pady=Spacing.XL)
    
    # Camera controls
    cam_controls = theme.frame(camera_section, bg=Colors.BG_CARD)
    cam_controls.pack(fill='x', pady=Spacing.SM)
    
    cam_buttons = theme.button_group(cam_controls, [
        {'text': 'Start Preview', 'style': ButtonStyle.PRIMARY, 'size': ButtonSize.SM},
        {'text': 'Capture', 'style': ButtonStyle.SECONDARY, 'size': ButtonSize.SM},
        {'text': 'Settings', 'style': ButtonStyle.GHOST, 'size': ButtonSize.SM},
    ])
    cam_buttons.pack(side='left')
    
    return tab


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION INSTRUCTIONS
# ══════════════════════════════════════════════════════════════════════════════
"""
HOW TO INTEGRATE INTO nexus.py:
═══════════════════════════════════════════════════════════════════════════════

1. Import the theme at the top of nexus.py:
   
   from nexus_pro_theme import NexusProTheme, Colors, ButtonStyle, ButtonSize

2. In your __init__ method, create the theme:
   
   def __init__(self):
       self.root = tk.Tk()
       self.theme = NexusProTheme(self.root)
       # ... rest of init

3. Replace your old create_hardware_scanner_tab() with:
   
   def create_hardware_scanner_tab(self):
       create_hardware_scanner_tab_pro(self, self.notebook)

4. Or copy the code directly into your class method.

5. Repeat this pattern for ALL tabs:
   - Use theme.section() for grouped controls
   - Use theme.button() with ButtonStyle enum
   - Use theme.status_row() for status displays
   - Use theme.console() for output areas
   - Use consistent spacing with Spacing.* constants

BEFORE/AFTER COMPARISON:
═══════════════════════════════════════════════════════════════════════════════

BEFORE (old code):
   tk.Label(hardware_frame, text="HARDWARE SCANNER SYSTEM", 
            font=("Arial", 18, "bold"), fg="green", bg="white")
   
   tk.Button(buttons_frame, text="Single Scan", 
            command=self.single_card_scan, bg="#4b0082", fg="white",
            font=("Arial", 13))
   
   tk.Button(buttons_frame, text="Batch Scan", 
            command=self.batch_scan_cards, bg="#2d5016", fg="white",
            font=("Arial", 13))

AFTER (new code):
   theme.header(content, "Hardware Scanner", "Arduino control and LED management")
   
   theme.button(scan_buttons, text="Single Scan", 
               style=ButtonStyle.PRIMARY, size=ButtonSize.LG)
   
   theme.button(scan_buttons, text="Batch Scan",
               style=ButtonStyle.SECONDARY, size=ButtonSize.LG)

The new code is:
✓ More readable
✓ Consistent styling
✓ Semantic button colors
✓ Professional appearance
✓ No hardcoded colors/fonts scattered everywhere
"""


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE DEMO
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Demo the redesigned tab
    root = tk.Tk()
    root.title("NEXUS Hardware Scanner - Pro Redesign")
    root.geometry("1400x900")
    root.configure(bg=Colors.BG_DEEPEST)
    
    # Create theme
    theme = NexusProTheme(root)
    
    # Create a mock self object
    class MockSelf:
        def __init__(self):
            self.theme = theme
    
    mock_self = MockSelf()
    
    # Create notebook
    notebook = theme.notebook(root)
    notebook.pack(fill='both', expand=True, padx=2, pady=2)
    
    # Create the redesigned tab
    create_hardware_scanner_tab_pro(mock_self, notebook)
    
    root.mainloop()
