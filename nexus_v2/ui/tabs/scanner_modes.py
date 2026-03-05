#!/usr/bin/env python3
"""
NEXUS V2 - Universal Scanner Tab
Professional 3-column layout - NO SCROLLING TO MORDOR
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import logging
from datetime import datetime
import requests
from urllib.parse import quote
import time

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from nexus_v2.config import get_config
    _config = get_config()
except ImportError:
    _config = None

logger = logging.getLogger(__name__)


class UniversalScannerTab:
    """Universal Scanner - Professional 3-Column Layout"""

    def __init__(self, parent_notebook, config=None, library=None):
        self.notebook = parent_notebook
        self.config = config or {}
        self.library = library

        # DANIELSON URL
        if _config:
            self.danielson_url = getattr(_config.scanner, 'danielson_url', "http://192.168.1.219:5001")
        else:
            self.danielson_url = "http://192.168.1.219:5001"

        # State
        self.connected = False
        self.scanning = False
        self.scan_count = 0
        self.success_count = 0
        self.scan_times = []

        # Mode and type
        self.scan_mode = 'single'  # single, bulk, pregrading
        # Default card_type from config game mode
        _game_to_type = {"magic": "mtg", "pokemon": "pokemon", "sports": "sports",
                         "yugioh": "yugioh", "onepiece": "onepiece", "lorcana": "lorcana"}
        active_game = getattr(getattr(_config, 'game', None), 'active_game', 'magic') if _config else 'magic'
        self.card_type = _game_to_type.get(active_game, 'mtg')

        # 5-step status
        self.step_status = {
            'edge': 'pending',
            'type': 'pending',
            'art': 'pending',
            'ocr': 'pending',
            'match': 'pending'
        }

        # Review queue
        self.review_queue = []
        self.review_index = 0
        self.current_scan = None
        self.current_image_path = None
        self.possible_matches = []

        # Colors - NEXUS theme
        self.colors = {
            'bg': '#0d1117',
            'surface': '#161b22',
            'surface2': '#21262d',
            'border': '#30363d',
            'accent': '#58a6ff',
            'success': '#3fb950',
            'warning': '#d29922',
            'error': '#f85149',
            'text': '#e6edf3',
            'text_dim': '#7d8590',
            'gold': '#ffd700',
            'mtg': '#8b4513',
            'pokemon': '#ffcb05',
            'yugioh': '#4169e1',
            'sports': '#228b22',
            'onepiece': '#dc143c',
            'lorcana': '#9932cc',
            'fab': '#ff6347'
        }

        # Thread-safe UI queue
        self._ui_queue = queue.Queue()
        self._queue_polling = False
        self._after_ids = []
        self._temp_files = []

        self._create_tab()
        self._start_ui_queue_processor()
        self._after_ids.append(self.frame.after(500, self._check_connections))

    def _start_ui_queue_processor(self):
        if self._queue_polling:
            return
        self._queue_polling = True
        self._process_ui_queue()

    def _process_ui_queue(self):
        if not self._queue_polling:
            return
        try:
            for _ in range(10):
                try:
                    callback = self._ui_queue.get_nowait()
                    if callable(callback):
                        callback()
                except queue.Empty:
                    break
        except Exception:
            pass
        try:
            if self._queue_polling and self.frame.winfo_exists():
                after_id = self.frame.after(50, self._process_ui_queue)
                self._after_ids.append(after_id)
        except tk.TclError:
            self._queue_polling = False

    def _schedule_ui(self, callback):
        self._ui_queue.put(callback)

    def _create_tab(self):
        """Create the scanner tab - 3 column layout"""
        self.frame = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.notebook.add(self.frame, text="Scanner")

        # ═══════════════════════════════════════════════════════════════
        # HEADER BAR
        # ═══════════════════════════════════════════════════════════════
        header = tk.Frame(self.frame, bg=self.colors['surface'], height=60)
        header.pack(fill='x', padx=0, pady=0)
        header.pack_propagate(False)

        # Left: Title
        tk.Label(
            header, text="⚡ UNIVERSAL SCANNER",
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors['gold'],
            bg=self.colors['surface']
        ).pack(side='left', padx=20, pady=15)

        # Center: Mode buttons
        mode_frame = tk.Frame(header, bg=self.colors['surface'])
        mode_frame.pack(side='left', padx=50)

        tk.Label(
            mode_frame, text="MODE:",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(side='left', padx=(0, 10))

        self.mode_buttons = {}
        modes = [
            ('single', '⚡ SINGLE TCG', '(Fastest)', self.colors['success']),
            ('bulk', '📦 BULK', '(Any TCG)', self.colors['warning']),
            ('pregrading', '🔍 PREGRADING', '(Grade Est.)', self.colors['accent'])
        ]

        for mode_id, mode_name, mode_sub, color in modes:
            btn_frame = tk.Frame(mode_frame, bg=self.colors['surface'])
            btn_frame.pack(side='left', padx=3)

            btn = tk.Button(
                btn_frame,
                text=f"{mode_name}\n{mode_sub}",
                font=('Segoe UI', 9, 'bold'),
                bg=color if mode_id == 'single' else self.colors['surface2'],
                fg='white' if mode_id == 'single' else self.colors['text'],
                activebackground=color,
                relief='flat',
                width=14, height=2,
                cursor='hand2',
                command=lambda m=mode_id: self._select_mode(m)
            )
            btn.pack()
            self.mode_buttons[mode_id] = btn

        # Right: 5-Step indicators + Connection status
        right_header = tk.Frame(header, bg=self.colors['surface'])
        right_header.pack(side='right', padx=20)

        # 5-Step mini indicators
        step_frame = tk.Frame(right_header, bg=self.colors['surface'])
        step_frame.pack(side='left', padx=(0, 30))

        tk.Label(
            step_frame, text="5-STEP:",
            font=('Segoe UI', 8),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(side='left', padx=(0, 5))

        self.step_mini_labels = {}
        steps = ['edge', 'type', 'art', 'ocr', 'match']
        step_names = ['Edge', 'Type', 'Art', 'OCR', 'Match']

        for i, (step_id, step_name) in enumerate(zip(steps, step_names)):
            lbl = tk.Label(
                step_frame, text=f"{i+1}:{step_name}",
                font=('Consolas', 8),
                fg=self.colors['text_dim'],
                bg=self.colors['surface']
            )
            lbl.pack(side='left', padx=3)
            self.step_mini_labels[step_id] = lbl

        # Connection status
        self.status_indicator = tk.Label(
            right_header, text="DANIELSON: --",
            font=('Consolas', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        )
        self.status_indicator.pack(side='left', padx=5)

        # ═══════════════════════════════════════════════════════════════
        # MAIN CONTENT - 3 COLUMNS
        # ═══════════════════════════════════════════════════════════════
        content = tk.Frame(self.frame, bg=self.colors['bg'])
        content.pack(fill='both', expand=True, padx=10, pady=10)

        # Configure grid weights
        content.grid_columnconfigure(0, weight=1, minsize=280)   # Left column
        content.grid_columnconfigure(1, weight=2, minsize=450)   # Center column
        content.grid_columnconfigure(2, weight=1, minsize=320)   # Right column
        content.grid_rowconfigure(0, weight=1)

        # ─────────────────────────────────────────────────────────────
        # LEFT COLUMN: Controls
        # ─────────────────────────────────────────────────────────────
        left_col = tk.Frame(content, bg=self.colors['surface'])
        left_col.grid(row=0, column=0, sticky='nsew', padx=(0, 5))

        self._create_card_type_panel(left_col)
        self._create_scan_button(left_col)
        self._create_5step_panel(left_col)
        self._create_session_stats(left_col)

        # ─────────────────────────────────────────────────────────────
        # CENTER COLUMN: Preview + Log
        # ─────────────────────────────────────────────────────────────
        center_col = tk.Frame(content, bg=self.colors['surface'])
        center_col.grid(row=0, column=1, sticky='nsew', padx=5)

        self._create_preview_panel(center_col)
        self._create_scan_log(center_col)

        # ─────────────────────────────────────────────────────────────
        # RIGHT COLUMN: Review & Match
        # ─────────────────────────────────────────────────────────────
        right_col = tk.Frame(content, bg=self.colors['surface'])
        right_col.grid(row=0, column=2, sticky='nsew', padx=(5, 0))

        self._create_match_panel(right_col)
        self._create_validation_panel(right_col)
        self._create_review_form(right_col)
        self._create_action_buttons(right_col)

    # ═══════════════════════════════════════════════════════════════════
    # LEFT COLUMN PANELS
    # ═══════════════════════════════════════════════════════════════════

    def _create_card_type_panel(self, parent):
        """Card type selection grid"""
        frame = tk.LabelFrame(
            parent, text="Card Type (Single TCG Mode)",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='x', padx=10, pady=(10, 5))

        self.type_buttons = {}
        types = [
            ('mtg', '🎴 MTG', self.colors['mtg']),
            ('pokemon', '⚡ Pokemon', self.colors['pokemon']),
            ('yugioh', '👁 Yu-Gi-Oh', self.colors['yugioh']),
            ('sports', '⚾ Sports', self.colors['sports']),
            ('onepiece', '🏴‍☠️ One Piece', self.colors['onepiece']),
            ('lorcana', '✨ Lorcana', self.colors['lorcana']),
            ('fab', '⚔ FaB', self.colors['fab'])
        ]

        # 2 columns, 4 rows
        for i, (type_id, type_name, color) in enumerate(types):
            row = i // 2
            col = i % 2

            btn = tk.Button(
                frame, text=type_name,
                font=('Segoe UI', 9, 'bold'),
                bg=color if type_id == 'mtg' else self.colors['surface2'],
                fg='white',
                activebackground=color,
                relief='flat',
                width=12, height=1,
                cursor='hand2',
                command=lambda t=type_id, c=color: self._select_card_type(t, c)
            )
            btn.grid(row=row, column=col, padx=5, pady=3, sticky='ew')
            self.type_buttons[type_id] = (btn, color)

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

    def _create_scan_button(self, parent):
        """Big scan button"""
        frame = tk.Frame(parent, bg=self.colors['surface'])
        frame.pack(fill='x', padx=10, pady=10)

        self.scan_btn = tk.Button(
            frame, text="🔍 SCAN CARD",
            font=('Segoe UI', 16, 'bold'),
            bg=self.colors['success'],
            fg='white',
            activebackground='#2ea043',
            relief='flat',
            height=2,
            cursor='hand2',
            command=self._scan_card
        )
        self.scan_btn.pack(fill='x')

        # Stats line
        self.stats_label = tk.Label(
            frame,
            text="Scans: 0 | Success: 0 | Avg: --ms",
            font=('Consolas', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        )
        self.stats_label.pack(pady=(5, 0))

    def _create_5step_panel(self, parent):
        """5-Step process panel with status indicators"""
        frame = tk.LabelFrame(
            parent, text="5-Step Process",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='x', padx=10, pady=5)

        self.step_labels = {}
        steps = [
            ('edge', '1: Edge Detection', 'Crop card from background'),
            ('type', '2: Type ID', 'Card type identification'),
            ('art', '3: Art Validation', 'Embedding (bulletproof)'),
            ('ocr', '4: OCR', 'Text extraction'),
            ('match', '5: Cross-Reference', '99%+ accuracy match')
        ]

        for step_id, step_name, step_desc in steps:
            row = tk.Frame(frame, bg=self.colors['surface'])
            row.pack(fill='x', padx=8, pady=2)

            # Status indicator
            status_lbl = tk.Label(
                row, text="○",
                font=('Segoe UI', 11),
                fg=self.colors['text_dim'],
                bg=self.colors['surface'],
                width=2
            )
            status_lbl.pack(side='left')

            # Step name
            name_lbl = tk.Label(
                row, text=f"Step {step_name}",
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors['text'],
                bg=self.colors['surface']
            )
            name_lbl.pack(side='left')

            # Description
            desc_lbl = tk.Label(
                row, text=f"  {step_desc}",
                font=('Segoe UI', 8),
                fg=self.colors['text_dim'],
                bg=self.colors['surface']
            )
            desc_lbl.pack(side='left')

            self.step_labels[step_id] = status_lbl

    def _create_session_stats(self, parent):
        """Session statistics"""
        frame = tk.LabelFrame(
            parent, text="Session Stats",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))

        self.session_text = tk.Text(
            frame,
            font=('Consolas', 9),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            height=6,
            state='disabled',
            relief='flat'
        )
        self.session_text.pack(fill='both', expand=True, padx=5, pady=5)

        self._update_session_stats()

    # ═══════════════════════════════════════════════════════════════════
    # CENTER COLUMN PANELS
    # ═══════════════════════════════════════════════════════════════════

    def _create_preview_panel(self, parent):
        """Card preview image"""
        frame = tk.LabelFrame(
            parent, text="Card Preview",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))

        self.preview_canvas = tk.Canvas(
            frame,
            bg=self.colors['bg'],
            highlightthickness=0,
            cursor='hand2'
        )
        self.preview_canvas.pack(fill='both', expand=True, padx=5, pady=5)

        # Placeholder text
        self.preview_canvas.create_text(
            225, 200,
            text="Card preview\nwill appear here",
            fill=self.colors['text_dim'],
            font=('Segoe UI', 12),
            justify='center'
        )

        self.preview_image = None
        self.preview_canvas.bind('<Button-1>', lambda e: self._open_zoom_window())

    def _create_scan_log(self, parent):
        """Scan log output"""
        frame = tk.LabelFrame(
            parent, text="Scan Log",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='x', padx=10, pady=(5, 10))

        # Header with clear button
        header = tk.Frame(frame, bg=self.colors['surface'])
        header.pack(fill='x', padx=5, pady=(5, 0))

        tk.Button(
            header, text="Clear",
            font=('Segoe UI', 8),
            bg=self.colors['surface2'],
            fg=self.colors['text_dim'],
            relief='flat',
            cursor='hand2',
            command=self._clear_log
        ).pack(side='right')

        self.log_text = tk.Text(
            frame,
            font=('Consolas', 9),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            height=8,
            state='disabled',
            relief='flat'
        )
        self.log_text.pack(fill='x', padx=5, pady=5)

        # Configure tags
        self.log_text.tag_configure('success', foreground=self.colors['success'])
        self.log_text.tag_configure('error', foreground=self.colors['error'])
        self.log_text.tag_configure('warning', foreground=self.colors['warning'])
        self.log_text.tag_configure('info', foreground=self.colors['accent'])
        self.log_text.tag_configure('dim', foreground=self.colors['text_dim'])

    # ═══════════════════════════════════════════════════════════════════
    # RIGHT COLUMN PANELS
    # ═══════════════════════════════════════════════════════════════════

    def _create_match_panel(self, parent):
        """Possible matches listbox"""
        frame = tk.LabelFrame(
            parent, text="Match Result",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='x', padx=10, pady=(10, 5))

        # Best match display
        self.match_name_label = tk.Label(
            frame, text="--",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface']
        )
        self.match_name_label.pack(pady=(10, 5))

        # Confidence bar
        conf_frame = tk.Frame(frame, bg=self.colors['surface'])
        conf_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(
            conf_frame, text="Confidence:",
            font=('Segoe UI', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(side='left')

        self.confidence_bar = ttk.Progressbar(
            conf_frame, length=150, mode='determinate'
        )
        self.confidence_bar.pack(side='left', padx=10)

        self.confidence_label = tk.Label(
            conf_frame, text="0%",
            font=('Segoe UI', 9, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface']
        )
        self.confidence_label.pack(side='left')

        # Set and collector number
        info_frame = tk.Frame(frame, bg=self.colors['surface'])
        info_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(info_frame, text="Set:", font=('Segoe UI', 9),
                 fg=self.colors['text_dim'], bg=self.colors['surface']).pack(side='left')
        self.match_set_label = tk.Label(info_frame, text="--", font=('Segoe UI', 9, 'bold'),
                                        fg=self.colors['text'], bg=self.colors['surface'])
        self.match_set_label.pack(side='left', padx=(5, 20))

        tk.Label(info_frame, text="Collector #:", font=('Segoe UI', 9),
                 fg=self.colors['text_dim'], bg=self.colors['surface']).pack(side='left')
        self.match_num_label = tk.Label(info_frame, text="--", font=('Segoe UI', 9, 'bold'),
                                        fg=self.colors['text'], bg=self.colors['surface'])
        self.match_num_label.pack(side='left', padx=5)

        # Possible matches dropdown
        tk.Label(
            frame, text="Other matches:",
            font=('Segoe UI', 8),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(anchor='w', padx=10, pady=(10, 2))

        self.match_listbox = tk.Listbox(
            frame,
            font=('Consolas', 9),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            selectbackground=self.colors['accent'],
            height=3,
            relief='flat'
        )
        self.match_listbox.pack(fill='x', padx=10, pady=(0, 10))
        self.match_listbox.bind('<<ListboxSelect>>', self._on_match_select)

    def _create_validation_panel(self, parent):
        """Cross-validation report"""
        frame = tk.LabelFrame(
            parent, text="Cross-Validation Report",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='x', padx=10, pady=5)

        self.validation_text = tk.Text(
            frame,
            font=('Consolas', 9),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            height=5,
            state='disabled',
            relief='flat'
        )
        self.validation_text.pack(fill='x', padx=5, pady=5)

        self.validation_text.tag_configure('valid', foreground=self.colors['success'])
        self.validation_text.tag_configure('invalid', foreground=self.colors['error'])
        self.validation_text.tag_configure('null', foreground=self.colors['text_dim'])

    def _create_review_form(self, parent):
        """Manual data entry form"""
        frame = tk.LabelFrame(
            parent, text="Manual Entry",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface'],
            bd=1, relief='solid'
        )
        frame.pack(fill='x', padx=10, pady=5)

        # Name
        row1 = tk.Frame(frame, bg=self.colors['surface'])
        row1.pack(fill='x', padx=10, pady=3)
        tk.Label(row1, text="Name:", font=('Segoe UI', 9),
                 fg=self.colors['text'], bg=self.colors['surface'],
                 width=10, anchor='w').pack(side='left')
        self.name_var = tk.StringVar()
        tk.Entry(row1, textvariable=self.name_var, font=('Segoe UI', 9),
                 bg=self.colors['bg'], fg=self.colors['text'],
                 insertbackground=self.colors['text'], relief='flat').pack(side='left', fill='x', expand=True)

        # Set + Number
        row2 = tk.Frame(frame, bg=self.colors['surface'])
        row2.pack(fill='x', padx=10, pady=3)
        tk.Label(row2, text="Set:", font=('Segoe UI', 9),
                 fg=self.colors['text'], bg=self.colors['surface'],
                 width=10, anchor='w').pack(side='left')
        self.set_var = tk.StringVar()
        tk.Entry(row2, textvariable=self.set_var, font=('Segoe UI', 9),
                 bg=self.colors['bg'], fg=self.colors['text'],
                 insertbackground=self.colors['text'], relief='flat', width=8).pack(side='left')
        tk.Label(row2, text="  #:", font=('Segoe UI', 9),
                 fg=self.colors['text'], bg=self.colors['surface']).pack(side='left')
        self.num_var = tk.StringVar()
        tk.Entry(row2, textvariable=self.num_var, font=('Segoe UI', 9),
                 bg=self.colors['bg'], fg=self.colors['text'],
                 insertbackground=self.colors['text'], relief='flat', width=8).pack(side='left')

        # Condition
        row3 = tk.Frame(frame, bg=self.colors['surface'])
        row3.pack(fill='x', padx=10, pady=3)
        tk.Label(row3, text="Condition:", font=('Segoe UI', 9),
                 fg=self.colors['text'], bg=self.colors['surface'],
                 width=10, anchor='w').pack(side='left')
        self.condition_var = tk.StringVar(value="NM")
        for cond in ["M", "NM", "LP", "MP", "HP", "DMG"]:
            tk.Radiobutton(
                row3, text=cond, variable=self.condition_var, value=cond,
                font=('Segoe UI', 8), bg=self.colors['surface'], fg=self.colors['text'],
                selectcolor=self.colors['bg'], activebackground=self.colors['surface']
            ).pack(side='left')

        # Foil + Lang
        row4 = tk.Frame(frame, bg=self.colors['surface'])
        row4.pack(fill='x', padx=10, pady=3)
        self.foil_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row4, text="Foil", variable=self.foil_var,
            font=('Segoe UI', 9), bg=self.colors['surface'], fg=self.colors['text'],
            selectcolor=self.colors['bg']
        ).pack(side='left')
        tk.Label(row4, text="  Lang:", font=('Segoe UI', 9),
                 fg=self.colors['text'], bg=self.colors['surface']).pack(side='left')
        self.lang_var = tk.StringVar(value="EN")
        lang_menu = tk.OptionMenu(row4, self.lang_var, "EN", "JP", "DE", "FR", "IT", "ES", "PT", "KO", "ZH")
        lang_menu.config(font=('Segoe UI', 8), bg=self.colors['bg'], fg=self.colors['text'], relief='flat')
        lang_menu.pack(side='left')

    def _create_action_buttons(self, parent):
        """Accept / Skip / Reject buttons + queue navigation"""
        frame = tk.Frame(parent, bg=self.colors['surface'])
        frame.pack(fill='x', padx=10, pady=(5, 10))

        # Queue navigation
        nav_frame = tk.Frame(frame, bg=self.colors['surface'])
        nav_frame.pack(fill='x', pady=(0, 10))

        tk.Button(
            nav_frame, text="Load Queue",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['accent'], fg='white',
            relief='flat', cursor='hand2',
            command=self._load_review_queue
        ).pack(side='left', padx=2)

        tk.Button(
            nav_frame, text="<",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['surface2'], fg=self.colors['text'],
            relief='flat', cursor='hand2', width=3,
            command=self._prev_review
        ).pack(side='left', padx=2)

        self.queue_label = tk.Label(
            nav_frame, text="0 / 0",
            font=('Consolas', 10),
            fg=self.colors['text'],
            bg=self.colors['surface']
        )
        self.queue_label.pack(side='left', padx=10)

        tk.Button(
            nav_frame, text=">",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['surface2'], fg=self.colors['text'],
            relief='flat', cursor='hand2', width=3,
            command=self._next_review
        ).pack(side='left', padx=2)

        # Action buttons
        btn_frame = tk.Frame(frame, bg=self.colors['surface'])
        btn_frame.pack(fill='x')

        tk.Button(
            btn_frame, text="✓ ACCEPT",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['success'], fg='white',
            relief='flat', cursor='hand2',
            width=10,
            command=self._accept_card
        ).pack(side='left', padx=2, expand=True, fill='x')

        tk.Button(
            btn_frame, text="» SKIP",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['warning'], fg='black',
            relief='flat', cursor='hand2',
            width=8,
            command=self._skip_card
        ).pack(side='left', padx=2, expand=True, fill='x')

        tk.Button(
            btn_frame, text="✗ REJECT",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['error'], fg='white',
            relief='flat', cursor='hand2',
            width=10,
            command=self._reject_card
        ).pack(side='left', padx=2, expand=True, fill='x')

    # ═══════════════════════════════════════════════════════════════════
    # FUNCTIONALITY
    # ═══════════════════════════════════════════════════════════════════

    def _select_mode(self, mode):
        """Switch scan mode"""
        self.scan_mode = mode

        # Update button colors
        for m, btn in self.mode_buttons.items():
            if m == mode:
                if m == 'single':
                    btn.config(bg=self.colors['success'], fg='white')
                elif m == 'bulk':
                    btn.config(bg=self.colors['warning'], fg='black')
                else:
                    btn.config(bg=self.colors['accent'], fg='white')
            else:
                btn.config(bg=self.colors['surface2'], fg=self.colors['text'])

        # Enable/disable card type buttons
        for type_id, (btn, color) in self.type_buttons.items():
            if mode == 'single':
                btn.config(state='normal')
            else:
                btn.config(state='disabled', bg=self.colors['surface2'])

        # Update step 2 indicator
        if mode == 'single':
            self.step_labels['type'].config(text="--", fg=self.colors['text_dim'])
        else:
            self.step_labels['type'].config(text="○", fg=self.colors['text_dim'])

        self._log(f"Mode: {mode.upper()}", 'info')

    def _select_card_type(self, type_id, color):
        """Select card type for Single TCG mode"""
        self.card_type = type_id

        # Update button colors
        for t, (btn, c) in self.type_buttons.items():
            if t == type_id:
                btn.config(bg=c)
            else:
                btn.config(bg=self.colors['surface2'])

        self._log(f"Card type: {type_id.upper()}", 'dim')

    def _update_step(self, step_id, status):
        """Update step indicator: pending, running, success, failed, skipped"""
        icons = {
            'pending': ('○', self.colors['text_dim']),
            'running': ('◉', self.colors['warning']),
            'success': ('✓', self.colors['success']),
            'failed': ('✗', self.colors['error']),
            'skipped': ('--', self.colors['text_dim'])
        }

        icon, color = icons.get(status, ('○', self.colors['text_dim']))

        def update():
            if step_id in self.step_labels:
                self.step_labels[step_id].config(text=icon, fg=color)
            if step_id in self.step_mini_labels:
                self.step_mini_labels[step_id].config(fg=color)

        self._schedule_ui(update)
        self.step_status[step_id] = status

    def _reset_steps(self):
        """Reset all steps to pending"""
        for step_id in self.step_status:
            if step_id == 'type' and self.scan_mode == 'single':
                self._update_step(step_id, 'skipped')
            else:
                self._update_step(step_id, 'pending')

    def _update_session_stats(self):
        """Update session statistics display"""
        avg_time = sum(self.scan_times) / len(self.scan_times) if self.scan_times else 0
        success_rate = (self.success_count / self.scan_count * 100) if self.scan_count > 0 else 0

        stats = f"Session Statistics\n"
        stats += f"─────────────────\n"
        stats += f"Total Scans:    {self.scan_count}\n"
        stats += f"Success:        {self.success_count} ({success_rate:.0f}%)\n"
        stats += f"Avg Time:       {avg_time:.0f}ms\n"
        stats += f"Mode:           {self.scan_mode.upper()}\n"
        stats += f"Card Type:      {self.card_type.upper()}"

        def update():
            self.session_text.config(state='normal')
            self.session_text.delete('1.0', 'end')
            self.session_text.insert('end', stats)
            self.session_text.config(state='disabled')

            self.stats_label.config(
                text=f"Scans: {self.scan_count} | Success: {self.success_count} | Avg: {avg_time:.0f}ms"
            )

        self._schedule_ui(update)

    def _log(self, message, tag=''):
        """Log message to scan log"""
        def do_log():
            try:
                timestamp = datetime.now().strftime('%H:%M:%S')
                self.log_text.config(state='normal')
                self.log_text.insert('end', f"[{timestamp}] ", 'dim')
                self.log_text.insert('end', f"{message}\n", tag)
                self.log_text.see('end')
                self.log_text.config(state='disabled')
            except Exception:
                pass

        self._schedule_ui(do_log)

    def _clear_log(self):
        """Clear scan log"""
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')

    def _check_connections(self):
        """Check DANIELSON connection"""
        self._log("Checking connection...", 'info')

        def check():
            try:
                r = requests.get(f"{self.danielson_url}/status", timeout=3)
                if r.status_code == 200:
                    self.connected = True
                    data = r.json()
                    coral = 'TPU' if data.get('coral_loaded') else 'CPU'
                    status_text = f"DANIELSON: ONLINE ({coral})"
                    self._schedule_ui(lambda: self.status_indicator.config(
                        text=status_text, fg=self.colors['success']))
                    self._log("DANIELSON: ONLINE", 'success')
                else:
                    raise Exception(f"HTTP {r.status_code}")
            except Exception as e:
                self.connected = False
                self._schedule_ui(lambda: self.status_indicator.config(
                    text="DANIELSON: OFFLINE", fg=self.colors['error']))
                self._log(f"DANIELSON: OFFLINE ({e})", 'error')

        threading.Thread(target=check, daemon=True).start()

    def _scan_card(self):
        """Perform card scan"""
        if self.scanning:
            return

        if not self.connected:
            self._log("DANIELSON not connected!", 'error')
            messagebox.showerror("Error", "DANIELSON not connected")
            return

        self.scanning = True
        self.scan_btn.config(state='disabled', text="Scanning...", bg=self.colors['warning'])
        self._reset_steps()
        self._log("Starting scan...", 'info')

        start_time = time.time()

        def do_scan():
            try:
                # Step 1: Edge detection
                self._update_step('edge', 'running')

                r = requests.post(
                    f"{self.danielson_url}/api/scan",
                    json={
                        "camera": "czur",
                        "process": True,
                        "card_type": self.card_type,
                        "mode": self.scan_mode,
                        "skip_back_scan": self.scan_mode == 'single'
                    },
                    timeout=60
                )

                elapsed = int((time.time() - start_time) * 1000)
                self.scan_times.append(elapsed)
                if len(self.scan_times) > 100:
                    self.scan_times.pop(0)

                if r.status_code == 200:
                    result = r.json()
                    self.current_scan = result

                    # Map DANIELSON stages_run/stages to 5-step display
                    stages_run = result.get('stages_run', [])
                    stages = result.get('stages', {})
                    # Edge = capture succeeded
                    self._update_step('edge', 'success' if 'capture' in stages_run and stages.get('capture', {}).get('success') else 'failed')
                    # Type = skipped in single mode
                    if self.scan_mode == 'single':
                        self._update_step('type', 'skipped')
                    else:
                        self._update_step('type', 'success' if result.get('card_type') else 'pending')
                    # Art = FAISS art match
                    art_stage = stages.get('art_match', {})
                    self._update_step('art', 'success' if art_stage.get('success') else ('failed' if 'art_match' in stages_run else 'pending'))
                    # OCR
                    ocr_stage = stages.get('ocr', {})
                    self._update_step('ocr', 'success' if ocr_stage.get('success') and ocr_stage.get('overall_confidence', 0) > 50 else ('failed' if 'ocr' in stages_run else 'pending'))
                    # Match = final result
                    self._update_step('match', 'success' if result.get('success') else ('failed' if result.get('confidence', 0) > 0 else 'pending'))

                    # Always show preview (even on failed scans)
                    image_path = result.get('image_path', '')
                    if image_path:
                        self._update_preview(image_path)

                    if result.get('success'):
                        self.scan_count += 1

                        # Get card data
                        card = result.get('card') or {}
                        name = card.get('name', result.get('card_name', 'Unknown'))
                        set_code = card.get('set', card.get('set_code', result.get('set_code', '???')))
                        confidence = result.get('confidence', 0)
                        image_path = result.get('image_path', '')

                        # Determine status from confidence
                        if confidence >= 95:
                            status = 'identified'
                        elif confidence >= 80:
                            status = 'likely'
                        else:
                            status = 'review'

                        # Update UI
                        def update_ui():
                            self.match_name_label.config(text=name)
                            self.match_set_label.config(text=set_code)
                            self.match_num_label.config(text=card.get('collector_number', '--'))
                            self.confidence_bar['value'] = confidence
                            self.confidence_label.config(text=f"{confidence}%")

                            # Color confidence
                            if confidence >= 85:
                                self.confidence_label.config(fg=self.colors['success'])
                            elif confidence >= 60:
                                self.confidence_label.config(fg=self.colors['warning'])
                            else:
                                self.confidence_label.config(fg=self.colors['error'])

                            # Fill form
                            self.name_var.set(name)
                            self.set_var.set(set_code)
                            self.num_var.set(card.get('collector_number', ''))
                            self.foil_var.set(card.get('foil', False))

                        self._schedule_ui(update_ui)

                        # Populate matches
                        matches = result.get('possible_matches', [])
                        if card.get('name'):
                            main_match = {'card': card, 'confidence': confidence}
                            if not matches:
                                matches = [main_match]
                        self._populate_matches(matches)

                        # Display validation
                        validation = result.get('validation', {})
                        if validation:
                            self._display_validation(validation)

                        # ============================================================
                        # ZERO-SORT: Every card gets a call number immediately.
                        # >=95% = auto-accept (full data into collection)
                        # <95%  = placeholder (call number assigned, awaits manual ID)
                        # ============================================================
                        if status == 'identified':
                            self.success_count += 1
                            self._log(f"✓ {name} ({set_code}) - {confidence}%", 'success')
                            # Auto-accept: send to DANIELSON with full data
                            self._auto_catalog(card, name, set_code, confidence, image_path, needs_review=False)
                        elif status == 'likely':
                            self._log(f"? {name} ({set_code}) - {confidence}%", 'warning')
                            # Placeholder: call number assigned, needs human review
                            self._auto_catalog(card, name, set_code, confidence, image_path, needs_review=True)
                        else:
                            self._log(f"✗ NEEDS REVIEW: {name} ({confidence}%)", 'error')
                            # Placeholder: call number assigned, needs human review
                            self._auto_catalog(card, name, set_code, confidence, image_path, needs_review=True)

                    else:
                        # Failed scan — still gets a call number (zero-sort)
                        confidence = result.get('confidence', 0)
                        card_name = result.get('card_name', '')
                        card = result.get('card') or {}
                        error = result.get('error', 'Unknown error')

                        # Auto-fill form with best candidate
                        best_name = card.get('name', card_name) or 'UNKNOWN'
                        best_set = card.get('set', card.get('set_code', result.get('set_code', '')))
                        best_num = card.get('collector_number', result.get('collector_number', ''))

                        if best_name != 'UNKNOWN':
                            def update_failed_ui():
                                self.match_name_label.config(text=best_name)
                                self.match_set_label.config(text=best_set or '???')
                                self.match_num_label.config(text=best_num or '--')
                                self.confidence_bar['value'] = confidence
                                self.confidence_label.config(text=f"{confidence:.1f}%")
                                self.confidence_label.config(fg=self.colors['warning'] if confidence >= 60 else self.colors['error'])
                                self.name_var.set(best_name)
                                self.set_var.set(best_set or '')
                                self.num_var.set(best_num or '')
                            self._schedule_ui(update_failed_ui)

                        # Populate match candidates list
                        matches = result.get('possible_matches', [])
                        if matches:
                            self._populate_matches(matches)
                            self._log(f"? PICK A MATCH: {card_name or '?'} ({confidence:.1f}%) - {len(matches)} candidates", 'warning')
                        elif card_name:
                            self._log(f"✗ NEEDS REVIEW: {card_name} ({confidence:.1f}%)", 'error')
                        else:
                            self._log(f"✗ NEEDS REVIEW: {confidence:.1f}% - {error}", 'error')

                        # Zero-sort: placeholder call number even on failed scans
                        self._auto_catalog(card, best_name, best_set or '', confidence, result.get('image_path', ''), needs_review=True)
                else:
                    self._log(f"HTTP error: {r.status_code}", 'error')

            except requests.Timeout:
                self._log("Scan timeout", 'error')
            except Exception as e:
                self._log(f"Scan error: {e}", 'error')
            finally:
                self.scanning = False
                self._update_session_stats()
                self._schedule_ui(lambda: self.scan_btn.config(
                    state='normal',
                    text="🔍 SCAN CARD",
                    bg=self.colors['success']
                ))

        threading.Thread(target=do_scan, daemon=True).start()

    def _update_preview(self, image_path):
        """Update card preview image"""
        if not PIL_AVAILABLE:
            return

        def fetch():
            try:
                if image_path.startswith('/'):
                    encoded_path = quote(image_path)
                    url = f"{self.danielson_url}/api/scan_image?path={encoded_path}"
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        from io import BytesIO
                        img = Image.open(BytesIO(r.content))
                    else:
                        return
                else:
                    img = Image.open(image_path)

                # Resize to fit canvas
                canvas_w = self.preview_canvas.winfo_width() or 450
                canvas_h = self.preview_canvas.winfo_height() or 400

                img_w, img_h = img.size
                ratio = min(canvas_w / img_w, canvas_h / img_h)
                new_w = int(img_w * ratio * 0.95)
                new_h = int(img_h * ratio * 0.95)

                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = Image.LANCZOS

                img = img.resize((new_w, new_h), resample)
                photo = ImageTk.PhotoImage(img)

                def update():
                    self.preview_image = photo
                    self.preview_canvas.delete('all')
                    self.preview_canvas.create_image(
                        canvas_w // 2, canvas_h // 2,
                        image=photo, anchor='center'
                    )
                    self.current_image_path = image_path

                self._schedule_ui(update)

            except Exception as e:
                self._log(f"Preview error: {e}", 'error')

        threading.Thread(target=fetch, daemon=True).start()

    def _populate_matches(self, matches):
        """Populate possible matches listbox"""
        def update():
            self.match_listbox.delete(0, tk.END)
            self.possible_matches = matches

            for match in matches:
                card = match.get('card', {})
                name = card.get('name', 'Unknown')
                set_code = card.get('set', card.get('set_code', '???'))
                conf = match.get('confidence', 0)
                self.match_listbox.insert(tk.END, f"{conf:5.1f}% | {name} ({set_code})")

        self._schedule_ui(update)

    def _on_match_select(self, event):
        """Handle match selection"""
        selection = self.match_listbox.curselection()
        if not selection or selection[0] >= len(self.possible_matches):
            return

        match = self.possible_matches[selection[0]]
        card = match.get('card', {})

        name = card.get('name', '')
        set_code = card.get('set', card.get('set_code', ''))
        col_num = card.get('collector_number', card.get('number', ''))

        self.name_var.set(name)
        self.set_var.set(set_code)
        self.num_var.set(col_num)

        # Update the main display too
        def update_display():
            self.match_name_label.config(text=name)
            self.match_set_label.config(text=set_code or '???')
            self.match_num_label.config(text=col_num or '--')
            conf = match.get('confidence', 0)
            self.confidence_bar['value'] = conf
            self.confidence_label.config(text=f"{conf:.1f}%")
        self._schedule_ui(update_display)

        self._log(f"Selected: {name} ({set_code})", 'info')

    def _display_validation(self, validation):
        """Display cross-validation report"""
        def update():
            self.validation_text.config(state='normal')
            self.validation_text.delete('1.0', 'end')

            sources = [
                ('ocr', 'OCR', validation.get('ocr', {})),
                ('zultan', 'ZULTAN', validation.get('zultan', {})),
                ('scryfall', 'Scryfall', validation.get('scryfall', {})),
                ('set', 'Set Code', validation.get('set', {}))
            ]

            valid_count = 0
            total_count = 0

            for key, label, data in sources:
                if isinstance(data, dict) and data:
                    total_count += 1
                    is_valid = data.get('valid', False)
                    if is_valid:
                        valid_count += 1

                    check = '✓' if is_valid else '✗'
                    tag = 'valid' if is_valid else 'invalid'
                    text = data.get('text', data.get('match', 'N/A'))

                    self.validation_text.insert('end', f"{check} {label}: ", tag)
                    self.validation_text.insert('end', f"{text}\n")

            # Summary
            self.validation_text.insert('end', f"\nScore: {valid_count}/{total_count}")

            self.validation_text.config(state='disabled')

        self._schedule_ui(update)

    def _open_zoom_window(self):
        """Open zoomed image in new window"""
        if not self.current_image_path or not PIL_AVAILABLE:
            return
        # Similar to hardware_scanner.py implementation
        self._log("Opening zoom view...", 'dim')

    def _load_review_queue(self):
        """Load review queue from DANIELSON"""
        self._log("Loading review queue...", 'info')

        def fetch():
            try:
                r = requests.get(f"{self.danielson_url}/api/review", timeout=15)
                if r.status_code == 200:
                    result = r.json()
                    queue = result.get('items', [])
                    self.review_queue = queue
                    self.review_index = 0

                    def update():
                        total = len(queue)
                        self.queue_label.config(text=f"{'1' if total > 0 else '0'} / {total}")
                        if queue:
                            self._log(f"Loaded {total} items in queue", 'success')
                            self._show_review_item(0)
                        else:
                            self._log("Queue is empty", 'info')

                    self._schedule_ui(update)
                else:
                    self._log(f"Failed to load queue: {r.status_code}", 'error')
            except Exception as e:
                self._log(f"Queue error: {e}", 'error')

        threading.Thread(target=fetch, daemon=True).start()

    def _show_review_item(self, index):
        """Display review queue item"""
        if not self.review_queue or index < 0 or index >= len(self.review_queue):
            return

        item = self.review_queue[index]
        self.current_scan = item

        card = item.get('suggested_card') or item.get('card') or {}

        def update():
            self.match_name_label.config(text=card.get('name', 'Unknown'))
            self.match_set_label.config(text=card.get('set', '???'))
            self.match_num_label.config(text=card.get('collector_number', '--'))
            self.confidence_bar['value'] = item.get('confidence', 0)
            self.confidence_label.config(text=f"{item.get('confidence', 0)}%")

            self.name_var.set(card.get('name', ''))
            self.set_var.set(card.get('set', ''))
            self.num_var.set(card.get('collector_number', ''))

            self.queue_label.config(text=f"{index + 1} / {len(self.review_queue)}")

        self._schedule_ui(update)

        image_path = item.get('image_path', '')
        if image_path:
            self._update_preview(image_path)

        self._log(f"Showing item {index + 1}: {card.get('name', 'Unknown')}", 'info')

    def _prev_review(self):
        """Previous review item"""
        if self.review_index > 0:
            self.review_index -= 1
            self._show_review_item(self.review_index)

    def _next_review(self):
        """Next review item"""
        if self.review_index < len(self.review_queue) - 1:
            self.review_index += 1
            self._show_review_item(self.review_index)

    def _auto_catalog(self, card, name, set_code, confidence, image_path, needs_review=False):
        """Zero-sort: Every scanned card gets a call number immediately.
        >=95% confidence: auto-accepted with full data.
        <95% confidence: placeholder call number, flagged for manual review.
        """
        payload = {
            'card_name': name,
            'card_type': self.card_type,
            'set_code': set_code,
            'collector_number': card.get('collector_number', '') if card else '',
            'condition': 'NM',
            'foil': card.get('foil', False) if card else False,
            'lang': 'EN',
            'confidence': confidence,
            'image_path': image_path,
            'card': card or {},
            'needs_review': needs_review,
        }

        def send():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/review/confirm",
                    json=payload,
                    timeout=10
                )
                if r.status_code == 200:
                    resp = r.json()
                    cn = resp.get('call_number', '')
                    # Store call number on current scan so _accept_card can UPDATE not INSERT
                    if self.current_scan:
                        self.current_scan['call_number'] = cn
                    if needs_review:
                        self._log(f"  -> {cn} (PENDING REVIEW)", 'warning')
                    else:
                        self._log(f"  -> {cn} cataloged", 'dim')
                    self._refresh_card_count()
                else:
                    self._log(f"  -> Catalog failed: HTTP {r.status_code}", 'error')
            except Exception as e:
                self._log(f"  -> Catalog failed: {e}", 'error')
        threading.Thread(target=send, daemon=True).start()

    def _accept_card(self):
        """Accept current card (manual override for review queue items)"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing Data", "Card name required")
            return

        self._log(f"ACCEPTED: {name} ({self.set_var.get()})", 'success')
        self.success_count += 1
        self._update_session_stats()

        # Send correction to DANIELSON
        scan = self.current_scan or {}
        card = scan.get('card') or {}
        existing_cn = scan.get('call_number', '')

        payload = {
            'card_name': name,
            'card_type': self.card_type,
            'set_code': self.set_var.get().strip(),
            'collector_number': self.num_var.get().strip(),
            'condition': self.condition_var.get() if hasattr(self, 'condition_var') else 'NM',
            'foil': self.foil_var.get() if hasattr(self, 'foil_var') else False,
            'lang': self.lang_var.get() if hasattr(self, 'lang_var') else 'EN',
            'confidence': scan.get('confidence', 0),
            'image_path': scan.get('image_path', ''),
            'card': card,
        }

        def send():
            try:
                if existing_cn:
                    # Card already has a call number from auto-catalog — UPDATE, don't create duplicate
                    payload['call_number'] = existing_cn
                    r = requests.post(
                        f"{self.danielson_url}/api/library/update",
                        json=payload,
                        timeout=10
                    )
                else:
                    # No call number yet — create new entry
                    r = requests.post(
                        f"{self.danielson_url}/api/review/confirm",
                        json=payload,
                        timeout=10
                    )
                if r.status_code == 200:
                    resp = r.json()
                    cn = resp.get('call_number', existing_cn)
                    self._log(f"  -> {cn} confirmed", 'dim')
                    self._refresh_card_count()
                else:
                    self._log(f"  -> API error: {r.status_code}", 'error')
            except Exception as e:
                self._log(f"  -> Failed to save: {e}", 'error')
        threading.Thread(target=send, daemon=True).start()

        # Advance queue
        if self.review_queue:
            self.review_queue.pop(self.review_index)
            if self.review_index >= len(self.review_queue) and self.review_index > 0:
                self.review_index -= 1
            if self.review_queue:
                self._show_review_item(self.review_index)
            self.queue_label.config(
                text=f"{self.review_index + 1 if self.review_queue else 0} / {len(self.review_queue)}")

    def _skip_card(self):
        """Skip current card"""
        self._log("SKIPPED", 'warning')

        if self.review_index < len(self.review_queue) - 1:
            self.review_index += 1
            self._show_review_item(self.review_index)
        else:
            self._log("End of queue", 'dim')

    def _reject_card(self):
        """Reject current card"""
        self._log("REJECTED", 'error')

        if self.current_scan:
            scan = self.current_scan
            def send():
                try:
                    requests.post(
                        f"{self.danielson_url}/api/review/skip",
                        json={'card_name': scan.get('card_name', '')},
                        timeout=5
                    )
                except Exception:
                    pass
            threading.Thread(target=send, daemon=True).start()

        if self.review_queue:
            self.review_queue.pop(self.review_index)
            if self.review_index >= len(self.review_queue) and self.review_index > 0:
                self.review_index -= 1
            if self.review_queue:
                self._show_review_item(self.review_index)
            self.queue_label.config(
                text=f"{self.review_index + 1 if self.review_queue else 0} / {len(self.review_queue)}")

    def _refresh_card_count(self):
        """Fetch updated card count from DANIELSON and update header."""
        try:
            r = requests.get(f"{self.danielson_url}/api/library/stats?type=all", timeout=5)
            if r.status_code == 200:
                total = r.json().get('total_cards', 0)
                # Update the app's header card count label (thread-safe)
                app = self.frame.winfo_toplevel()
                if hasattr(app, 'card_count_label'):
                    self.frame.after(0, lambda: app.card_count_label.config(text=f"{total:,}"))
        except Exception:
            pass

    def cleanup(self):
        """Cleanup on close"""
        self._queue_polling = False
        for after_id in self._after_ids:
            try:
                self.frame.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()
        for temp_file in self._temp_files:
            try:
                os.remove(temp_file)
            except Exception:
                pass
        self._temp_files.clear()


# Backwards compatibility alias
ScannerModesTab = UniversalScannerTab


def create_scanner_modes_tab(notebook, config=None, library=None):
    """Factory function to create the Scanner Modes tab."""
    return UniversalScannerTab(notebook, config, library)
