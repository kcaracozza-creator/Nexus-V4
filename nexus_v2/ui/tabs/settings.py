"""
NEXUS V2 Settings Tab
=====================
Application settings and configuration
"""

import tkinter as tk
from tkinter import ttk

try:
    from nexus_v2.config import get_config
    _config = get_config()
except ImportError:
    _config = None


class SettingsTab:
    """Settings and Configuration Tab"""

    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.library = kwargs.get('library')
        self.theme = kwargs.get('theme')
        self.colors = kwargs.get('colors')
        self.shop_personality = kwargs.get('shop_personality')

        if parent:
            self._create_ui()

    def _create_ui(self):
        """Create the settings UI"""
        # Main container with scroll
        canvas = tk.Canvas(self.parent, bg=self.colors.bg_dark, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=self.colors.bg_dark)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Header
        header = tk.Frame(scrollable, bg=self.colors.bg_surface)
        header.pack(fill='x', padx=20, pady=10)

        tk.Label(
            header,
            text="Settings",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(pady=15, padx=20, anchor='w')

        # Library Settings Section
        lib_frame = tk.LabelFrame(
            scrollable,
            text="Library Settings",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        lib_frame.pack(fill='x', padx=20, pady=10)

        card_count = len(self.library) if self.library else 0
        box_count = len(self.library.box_inventory) if self.library else 0

        tk.Label(
            lib_frame,
            text=f"Cards in Library: {card_count:,}",
            font=('Segoe UI', 10),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        tk.Label(
            lib_frame,
            text=f"Active Boxes: {box_count}",
            font=('Segoe UI', 10),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        # Scanner Settings Section
        scanner_frame = tk.LabelFrame(
            scrollable,
            text="Scanner Settings",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        scanner_frame.pack(fill='x', padx=20, pady=10)

        # Get IPs from config
        scanner_ip = _config.scanner.scanner_ip if _config else "192.168.1.219"
        scanner_port = _config.scanner.scanner_port if _config else 5001
        ocr_ip = _config.scanner.ocr_ip if _config else "192.168.1.219"
        ocr_port = _config.scanner.ocr_port if _config else 5001

        tk.Label(
            scanner_frame,
            text=f"Scanner IP: {scanner_ip}:{scanner_port} (Pi 5 Scarf)",
            font=('Segoe UI', 10),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        tk.Label(
            scanner_frame,
            text=f"OCR Engine: {ocr_ip}:{ocr_port} (Pi 5 Lionelle)",
            font=('Segoe UI', 10),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        # Theme Settings Section
        theme_frame = tk.LabelFrame(
            scrollable,
            text="Theme Settings",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        theme_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(
            theme_frame,
            text="Current Theme: Professional Grey",
            font=('Segoe UI', 10),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        tk.Label(
            theme_frame,
            text=f"Accent Color: {self.colors.accent}",
            font=('Segoe UI', 10),
            fg=self.colors.accent,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        # About Section
        about_frame = tk.LabelFrame(
            scrollable,
            text="About NEXUS",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors.accent,
            bg=self.colors.bg_surface,
            padx=20,
            pady=15
        )
        about_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(
            about_frame,
            text="NEXUS V2 - Universal Collectibles Management System",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors.text_primary,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        tk.Label(
            about_frame,
            text="Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.",
            font=('Segoe UI', 9),
            fg=self.colors.text_secondary,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)

        tk.Label(
            about_frame,
            text="Patent Pending - Filed November 27, 2025",
            font=('Segoe UI', 9),
            fg=self.colors.text_muted,
            bg=self.colors.bg_surface
        ).pack(anchor='w', pady=2)
