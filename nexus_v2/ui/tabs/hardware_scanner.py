#!/usr/bin/env python3
"""
NEXUS V2 - Hardware Scanner Tab
Clean implementation for Pi 5 scanner integration
"""

import os
import tkinter as tk
from tkinter import messagebox
import threading
import queue
import logging
from datetime import datetime
import requests
from urllib.parse import quote

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

# Grading analyzer (local CV analysis for PREGRADING mode)
try:
    import cv2
    from nexus_v2.scanner.grading_analyzer import CardGradingAnalyzer
    GRADING_AVAILABLE = True
except ImportError:
    GRADING_AVAILABLE = False

# NFT minter (shared with nexus_auth venue pipeline)
try:
    import sys as _sys
    import os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', '..'))
    from nexus_auth.nft_minter import NexusNFTMinter
    _nft_minter = NexusNFTMinter()
    NFT_AVAILABLE = True
except Exception:
    NFT_AVAILABLE = False
    _nft_minter = None

from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# SCANNER MODES - 3 operational modes for universal scanning
# =============================================================================

class ScanMode(Enum):
    """Scanning operation modes"""
    SINGLE_TCG = "single_tcg"   # User specifies type (FASTEST - skip back scan)
    BULK = "bulk"               # Mixed cards, auto-detect type (back scan required)
    PREGRADING = "pregrading"   # Full inspection + defect analysis


class CardType(Enum):
    """Supported card types"""
    MTG = "mtg"
    POKEMON = "pokemon"
    YUGIOH = "yugioh"
    SPORTS = "sports"
    ONE_PIECE = "one_piece"
    LORCANA = "lorcana"
    FLESH_AND_BLOOD = "flesh_and_blood"


# Card type colors for UI
CARD_TYPE_COLORS = {
    CardType.MTG: '#8B4513',           # Brown
    CardType.POKEMON: '#FFD700',        # Gold
    CardType.YUGIOH: '#4169E1',         # Royal Blue
    CardType.SPORTS: '#228B22',         # Forest Green
    CardType.ONE_PIECE: '#DC143C',      # Crimson
    CardType.LORCANA: '#9932CC',        # Purple
    CardType.FLESH_AND_BLOOD: '#FF6347', # Tomato
}


class HardwareScannerTab:
    """Hardware Scanner Tab - Pi 5 Integration"""

    def __init__(self, parent_notebook, config=None, library=None):
        self.notebook = parent_notebook
        self.config = config or {}
        self.library = library  # For adding cards to collection

        # DANIELSON unified scanner server (replaces SNARF + BROK)
        self.danielson_url = "http://192.168.1.219:5001"

        # State
        self.connected = False
        self.scanning = False
        self.scan_count = 0

        # Bulk scan state
        self.bulk_scanning = False
        self.bulk_paused = False
        self.bulk_scan_count = 0
        self.bulk_auto_accepted = 0
        self.bulk_needs_review = 0

        # Scanner mode state (5-step patent process)
        self.current_mode = ScanMode.SINGLE_TCG
        self.selected_card_type = CardType.MTG
        self.step_indicators = []  # 5-step progress indicators

        # Grading state (PREGRADING mode)
        self.current_grade_result = None  # CardGradingAnalyzer output for current scan

        # Colors
        self.colors = {
            'bg': '#1a1a1a',
            'surface': '#2d2d2d',
            'accent': '#4a9eff',
            'success': '#4caf50',
            'error': '#f44336',
            'warning': '#ff9800',
            'text': '#ffffff',
            'text_dim': '#888888'
        }

        # Current image path for zoom
        self.current_image_path = None
        self._temp_files = []  # Track temp files for cleanup

        # Thread-safe UI queue (fixes "main thread is not in main loop" crashes)
        self._ui_queue = queue.Queue()
        self._queue_polling = False
        self._after_ids = []  # Track .after() callback IDs for proper cleanup

        self._create_tab()
        self._start_ui_queue_processor()
        # Delay connection check until UI is fully built (fixes race condition)
        initial_check_id = self.frame.after(500, self._check_connections)
        self._after_ids.append(initial_check_id)

    def _start_ui_queue_processor(self):
        """Start the UI queue processor on the main thread."""
        if self._queue_polling:
            return
        self._queue_polling = True
        self._process_ui_queue()

    def _process_ui_queue(self):
        """Process pending UI updates from background threads."""
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
        # Only schedule next iteration if widget still exists
        try:
            if self._queue_polling and self.frame.winfo_exists():
                after_id = self.frame.after(50, self._process_ui_queue)
                self._after_ids.append(after_id)
        except tk.TclError:
            # Widget destroyed, stop polling
            self._queue_polling = False

    def _schedule_ui(self, callback):
        """Thread-safe way to schedule a UI update from any thread."""
        self._ui_queue.put(callback)

    def _create_tab(self):
        """Create the scanner tab UI"""
        self.frame = tk.Frame(self.notebook, bg=self.colors['bg'])
        self.notebook.add(self.frame, text="Scanner")

        # Header
        header = tk.Frame(self.frame, bg=self.colors['surface'])
        header.pack(fill='x', padx=10, pady=10)

        tk.Label(
            header,
            text="HARDWARE SCANNER",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        ).pack(side='left', padx=15, pady=10)

        # Connection status indicators
        self.status_frame = tk.Frame(header, bg=self.colors['surface'])
        self.status_frame.pack(side='right', padx=15, pady=10)

        # Danielson status (unified scanner)
        self.status_indicator = tk.Label(
            self.status_frame,
            text="Danielson: --",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        )
        self.status_indicator.pack(side='left', padx=10)

        # =====================================================================
        # MODE SELECTION + 5-STEP INDICATOR
        # =====================================================================
        mode_header = tk.Frame(self.frame, bg=self.colors['surface'])
        mode_header.pack(fill='x', padx=10, pady=5)

        # Mode buttons (left side)
        mode_btn_frame = tk.Frame(mode_header, bg=self.colors['surface'])
        mode_btn_frame.pack(side='left', padx=10, pady=5)

        tk.Label(
            mode_btn_frame,
            text="MODE:",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface']
        ).pack(side='left', padx=(0, 10))

        # Single TCG button (default selected)
        self.single_mode_btn = tk.Button(
            mode_btn_frame,
            text="SINGLE TCG",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['success'],
            fg='white',
            width=10,
            command=lambda: self._select_mode(ScanMode.SINGLE_TCG),
            cursor='hand2'
        )
        self.single_mode_btn.pack(side='left', padx=2)

        # Bulk button
        self.bulk_mode_btn = tk.Button(
            mode_btn_frame,
            text="BULK",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['surface'],
            fg='white',
            width=10,
            command=lambda: self._select_mode(ScanMode.BULK),
            cursor='hand2'
        )
        self.bulk_mode_btn.pack(side='left', padx=2)

        # Pregrading button
        self.pregrade_mode_btn = tk.Button(
            mode_btn_frame,
            text="PREGRADING",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['surface'],
            fg='white',
            width=10,
            command=lambda: self._select_mode(ScanMode.PREGRADING),
            cursor='hand2'
        )
        self.pregrade_mode_btn.pack(side='left', padx=2)

        # Mode info label
        self.mode_info_label = tk.Label(
            mode_btn_frame,
            text="Skip back scan - user specifies type",
            font=('Segoe UI', 8, 'italic'),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        )
        self.mode_info_label.pack(side='left', padx=15)

        # 5-Step indicator (right side)
        steps_frame = tk.Frame(mode_header, bg=self.colors['surface'])
        steps_frame.pack(side='right', padx=10, pady=5)

        tk.Label(
            steps_frame,
            text="5-STEP:",
            font=('Segoe UI', 9, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        ).pack(side='left', padx=(0, 5))

        step_names = ['Edge', 'Type', 'Art', 'OCR', 'Match']
        self.step_labels = []
        for i, name in enumerate(step_names):
            lbl = tk.Label(
                steps_frame,
                text=f"{i+1}:{name}",
                font=('Consolas', 9),
                fg=self.colors['text_dim'],
                bg=self.colors['surface'],
                padx=3
            )
            lbl.pack(side='left')
            self.step_labels.append(lbl)

        # Main content - scrollable
        content = tk.Frame(self.frame, bg=self.colors['bg'])
        content.pack(fill='both', expand=True, padx=10, pady=5)

        # Left panel - Controls (scrollable, fixed width)
        left_container = tk.Frame(content, bg=self.colors['surface'], width=320)
        left_container.pack(side='left', fill='both', padx=(0, 10), pady=5)
        left_container.pack_propagate(False)

        # Scrollable controls section (top part)
        controls_container = tk.Frame(left_container, bg=self.colors['surface'])
        controls_container.pack(fill='both', expand=True)

        # Add canvas and scrollbar for controls
        left_canvas = tk.Canvas(controls_container, bg=self.colors['surface'], highlightthickness=0)
        left_scrollbar = tk.Scrollbar(controls_container, orient='vertical', command=left_canvas.yview)
        left = tk.Frame(left_canvas, bg=self.colors['surface'])

        left.bind('<Configure>', lambda e: left_canvas.configure(scrollregion=left_canvas.bbox('all')))
        left_canvas.create_window((0, 0), window=left, anchor='nw')
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_scrollbar.pack(side='right', fill='y')
        left_canvas.pack(side='left', fill='both', expand=True)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._create_connection_panel(left)
        self._create_card_type_panel(left)
        self._create_5step_panel(left)
        self._create_scan_controls(left)
        self._create_bulk_scan_controls(left)

        # Scan log - FIXED at bottom, not scrollable
        self._create_scan_log(left_container)

        # Right panel - Results
        right = tk.Frame(content, bg=self.colors['surface'])
        right.pack(side='left', fill='both', expand=True, pady=5)

        self._create_results_panel(right)

    def _create_connection_panel(self, parent):
        """Connection settings panel"""
        frame = tk.LabelFrame(
            parent,
            text="Connection",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.pack(fill='x', padx=10, pady=10)

        # Danielson IP (unified scanner)
        row1 = tk.Frame(frame, bg=self.colors['surface'])
        row1.pack(fill='x', padx=10, pady=5)

        tk.Label(
            row1, text="Danielson:",
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            width=10, anchor='w'
        ).pack(side='left')

        self.danielson_ip_var = tk.StringVar(value=self.danielson_url)
        self.danielson_entry = tk.Entry(
            row1,
            textvariable=self.danielson_ip_var,
            font=('Consolas', 10),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            width=22
        )
        self.danielson_entry.pack(side='left', padx=5)

        # Connect button
        tk.Button(
            frame,
            text="Test Connection",
            font=('Segoe UI', 10),
            bg=self.colors['accent'],
            fg='white',
            activebackground='#3d8ce0',
            command=self._check_connections,
            cursor='hand2'
        ).pack(pady=5)

        # Sync inventory button
        tk.Button(
            row1,
            text="Sync Inventory",
            font=('Segoe UI', 10),
            bg='#6c5ce7',
            fg='white',
            activebackground='#5b4cdb',
            command=self._sync_inventory,
            cursor='hand2'
        ).pack(side='left', padx=10)

    def _create_card_type_panel(self, parent):
        """Card type selection for Single TCG mode"""
        self.type_frame = tk.LabelFrame(
            parent,
            text="Card Type (Single TCG)",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['success'],
            bg=self.colors['surface']
        )
        self.type_frame.pack(fill='x', padx=10, pady=10)

        # Card type buttons grid
        types_grid = tk.Frame(self.type_frame, bg=self.colors['surface'])
        types_grid.pack(fill='x', padx=5, pady=5)

        self.type_buttons = {}
        types = [
            (CardType.MTG, "MTG", CARD_TYPE_COLORS[CardType.MTG]),
            (CardType.POKEMON, "Pokemon", CARD_TYPE_COLORS[CardType.POKEMON]),
            (CardType.YUGIOH, "Yu-Gi-Oh", CARD_TYPE_COLORS[CardType.YUGIOH]),
            (CardType.SPORTS, "Sports", CARD_TYPE_COLORS[CardType.SPORTS]),
            (CardType.ONE_PIECE, "One Piece", CARD_TYPE_COLORS[CardType.ONE_PIECE]),
            (CardType.LORCANA, "Lorcana", CARD_TYPE_COLORS[CardType.LORCANA]),
            (CardType.FLESH_AND_BLOOD, "FaB", CARD_TYPE_COLORS[CardType.FLESH_AND_BLOOD]),
        ]

        for i, (card_type, label, color) in enumerate(types):
            row = i // 4
            col = i % 4

            # Highlight MTG as default selected
            bg_color = color if card_type == self.selected_card_type else self.colors['bg']

            btn = tk.Button(
                types_grid,
                text=label,
                font=('Segoe UI', 9),
                bg=bg_color,
                fg='white',
                width=8,
                command=lambda ct=card_type: self._select_card_type(ct),
                cursor='hand2'
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky='ew')
            self.type_buttons[card_type] = btn

        for i in range(4):
            types_grid.columnconfigure(i, weight=1)

    def _create_5step_panel(self, parent):
        """5-Step scanning process progress panel"""
        frame = tk.LabelFrame(
            parent,
            text="5-Step Process",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.pack(fill='x', padx=10, pady=10)

        steps = [
            ("1", "Edge Detection", "Crop card"),
            ("2", "Type ID", "Back scan"),
            ("3", "Art Match", "Embedding"),
            ("4", "OCR", "Text extract"),
            ("5", "Cross-Ref", "Final match"),
        ]

        self.step_indicators = []

        for step_num, step_name, step_desc in steps:
            row = tk.Frame(frame, bg=self.colors['surface'])
            row.pack(fill='x', padx=5, pady=2)

            indicator = tk.Label(
                row,
                text="O",
                font=('Consolas', 10),
                fg=self.colors['text_dim'],
                bg=self.colors['surface'],
                width=2
            )
            indicator.pack(side='left')

            tk.Label(
                row,
                text=f"{step_num}: {step_name}",
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors['text'],
                bg=self.colors['surface'],
                width=14,
                anchor='w'
            ).pack(side='left')

            tk.Label(
                row,
                text=step_desc,
                font=('Segoe UI', 8),
                fg=self.colors['text_dim'],
                bg=self.colors['surface']
            ).pack(side='left')

            self.step_indicators.append(indicator)

    def _create_scan_controls(self, parent):
        """Scan control buttons"""
        frame = tk.LabelFrame(
            parent,
            text="Scan Controls",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.pack(fill='x', padx=10, pady=10)

        # Camera selection
        cam_frame = tk.Frame(frame, bg=self.colors['surface'])
        cam_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(
            cam_frame, text="Camera:",
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['surface']
        ).pack(side='left')

        self.camera_var = tk.StringVar(value="owleye")
        tk.Radiobutton(
            cam_frame, text="OwlEye",
            variable=self.camera_var, value="owleye",
            font=('Segoe UI', 9),
            bg=self.colors['surface'], fg=self.colors['text'],
            selectcolor=self.colors['bg'],
            activebackground=self.colors['surface']
        ).pack(side='left', padx=5)

        tk.Radiobutton(
            cam_frame, text="CZUR",
            variable=self.camera_var, value="czur",
            font=('Segoe UI', 9),
            bg=self.colors['surface'], fg=self.colors['text'],
            selectcolor=self.colors['bg'],
            activebackground=self.colors['surface']
        ).pack(side='left', padx=5)

        # Scan button
        self.scan_btn = tk.Button(
            frame,
            text="SCAN CARD",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['success'],
            fg='white',
            activebackground='#45a049',
            command=self._scan_card,
            cursor='hand2',
            height=2
        )
        self.scan_btn.pack(fill='x', padx=10, pady=10)

        # Capture only button
        tk.Button(
            frame,
            text="Capture Image Only",
            font=('Segoe UI', 10),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            command=self._capture_only,
            cursor='hand2'
        ).pack(fill='x', padx=10, pady=5)

        # Scan count
        self.count_label = tk.Label(
            frame,
            text="Scans: 0",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        )
        self.count_label.pack(pady=5)

    def _create_bulk_scan_controls(self, parent):
        """Bulk scan controls for continuous automated scanning"""
        frame = tk.LabelFrame(
            parent,
            text="Bulk Scan",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['warning'],
            bg=self.colors['surface']
        )
        frame.pack(fill='x', padx=10, pady=10)

        # Status indicator
        status_row = tk.Frame(frame, bg=self.colors['surface'])
        status_row.pack(fill='x', padx=10, pady=5)

        tk.Label(
            status_row, text="Status:",
            font=('Segoe UI', 10),
            fg=self.colors['text'],
            bg=self.colors['surface']
        ).pack(side='left')

        self.bulk_status_label = tk.Label(
            status_row, text="STOPPED",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['error'],
            bg=self.colors['surface']
        )
        self.bulk_status_label.pack(side='left', padx=10)

        # Delay setting
        delay_row = tk.Frame(frame, bg=self.colors['surface'])
        delay_row.pack(fill='x', padx=10, pady=3)

        tk.Label(
            delay_row, text="Delay (sec):",
            font=('Segoe UI', 9),
            fg=self.colors['text'],
            bg=self.colors['surface']
        ).pack(side='left')

        self.bulk_delay_var = tk.IntVar(value=2)
        self.bulk_delay_scale = tk.Scale(
            delay_row,
            from_=1, to=10,
            orient='horizontal',
            variable=self.bulk_delay_var,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            highlightthickness=0,
            length=100
        )
        self.bulk_delay_scale.pack(side='left', padx=5)

        # Auto-accept threshold
        thresh_row = tk.Frame(frame, bg=self.colors['surface'])
        thresh_row.pack(fill='x', padx=10, pady=3)

        tk.Label(
            thresh_row, text="Auto-Accept %:",
            font=('Segoe UI', 9),
            fg=self.colors['text'],
            bg=self.colors['surface']
        ).pack(side='left')

        self.bulk_threshold_var = tk.IntVar(value=85)
        self.bulk_threshold_scale = tk.Scale(
            thresh_row,
            from_=50, to=100,
            orient='horizontal',
            variable=self.bulk_threshold_var,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            highlightthickness=0,
            length=100
        )
        self.bulk_threshold_scale.pack(side='left', padx=5)

        # Control buttons
        btn_row = tk.Frame(frame, bg=self.colors['surface'])
        btn_row.pack(fill='x', padx=10, pady=8)

        self.bulk_start_btn = tk.Button(
            btn_row, text="START",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white',
            command=self._start_bulk_scan,
            cursor='hand2', width=8
        )
        self.bulk_start_btn.pack(side='left', padx=2)

        self.bulk_pause_btn = tk.Button(
            btn_row, text="PAUSE",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['warning'], fg='black',
            command=self._pause_bulk_scan,
            cursor='hand2', width=8,
            state='disabled'
        )
        self.bulk_pause_btn.pack(side='left', padx=2)

        self.bulk_stop_btn = tk.Button(
            btn_row, text="STOP",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white',
            command=self._stop_bulk_scan,
            cursor='hand2', width=8,
            state='disabled'
        )
        self.bulk_stop_btn.pack(side='left', padx=2)

        # Stats display
        stats_frame = tk.Frame(frame, bg=self.colors['bg'])
        stats_frame.pack(fill='x', padx=10, pady=5)

        # Scanned count
        stat_row1 = tk.Frame(stats_frame, bg=self.colors['bg'])
        stat_row1.pack(fill='x', pady=1)

        tk.Label(
            stat_row1, text="Scanned:",
            font=('Consolas', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['bg'], width=12, anchor='w'
        ).pack(side='left')

        self.bulk_scanned_label = tk.Label(
            stat_row1, text="0",
            font=('Consolas', 10, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['bg']
        )
        self.bulk_scanned_label.pack(side='left')

        # Auto-accepted count
        stat_row2 = tk.Frame(stats_frame, bg=self.colors['bg'])
        stat_row2.pack(fill='x', pady=1)

        tk.Label(
            stat_row2, text="Auto-Accept:",
            font=('Consolas', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['bg'], width=12, anchor='w'
        ).pack(side='left')

        self.bulk_accepted_label = tk.Label(
            stat_row2, text="0",
            font=('Consolas', 10, 'bold'),
            fg=self.colors['success'],
            bg=self.colors['bg']
        )
        self.bulk_accepted_label.pack(side='left')

        # Needs review count
        stat_row3 = tk.Frame(stats_frame, bg=self.colors['bg'])
        stat_row3.pack(fill='x', pady=1)

        tk.Label(
            stat_row3, text="For Review:",
            font=('Consolas', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['bg'], width=12, anchor='w'
        ).pack(side='left')

        self.bulk_review_label = tk.Label(
            stat_row3, text="0",
            font=('Consolas', 10, 'bold'),
            fg=self.colors['warning'],
            bg=self.colors['bg']
        )
        self.bulk_review_label.pack(side='left')

        # Reset stats button
        tk.Button(
            frame, text="Reset Stats",
            font=('Segoe UI', 8),
            bg=self.colors['bg'], fg=self.colors['text_dim'],
            command=self._reset_bulk_stats,
            cursor='hand2'
        ).pack(pady=5)

    def _start_bulk_scan(self):
        """Start bulk scanning mode"""
        if not self.connected:
            self._log("DANIELSON not connected!", 'error')
            messagebox.showerror("Error", "DANIELSON not connected - cannot start bulk scan")
            return

        if self.bulk_scanning and self.bulk_paused:
            # Resume from pause
            self.bulk_paused = False
            self.bulk_status_label.config(text="RUNNING", fg=self.colors['success'])
            self.bulk_pause_btn.config(text="PAUSE")
            self._log("Bulk scan RESUMED", 'info')
            return

        if self.bulk_scanning:
            return

        self.bulk_scanning = True
        self.bulk_paused = False

        # Update UI
        self.bulk_status_label.config(text="RUNNING", fg=self.colors['success'])
        self.bulk_start_btn.config(state='disabled')
        self.bulk_pause_btn.config(state='normal')
        self.bulk_stop_btn.config(state='normal')
        self.scan_btn.config(state='disabled')  # Disable single scan

        self._log("=== BULK SCAN STARTED ===", 'info')
        self._log(f"Delay: {self.bulk_delay_var.get()}s | Auto-accept threshold: {self.bulk_threshold_var.get()}%", 'dim')

        # Start bulk scan loop
        threading.Thread(target=self._bulk_scan_loop, daemon=True).start()

    def _pause_bulk_scan(self):
        """Pause/Resume bulk scanning"""
        if not self.bulk_scanning:
            return

        if self.bulk_paused:
            # Resume
            self.bulk_paused = False
            self.bulk_status_label.config(text="RUNNING", fg=self.colors['success'])
            self.bulk_pause_btn.config(text="PAUSE")
            self._log("Bulk scan RESUMED", 'info')
        else:
            # Pause
            self.bulk_paused = True
            self.bulk_status_label.config(text="PAUSED", fg=self.colors['warning'])
            self.bulk_pause_btn.config(text="RESUME")
            self._log("Bulk scan PAUSED", 'info')

    def _stop_bulk_scan(self):
        """Stop bulk scanning"""
        self.bulk_scanning = False
        self.bulk_paused = False

        # Update UI
        self.bulk_status_label.config(text="STOPPED", fg=self.colors['error'])
        self.bulk_start_btn.config(state='normal')
        self.bulk_pause_btn.config(state='disabled', text="PAUSE")
        self.bulk_stop_btn.config(state='disabled')
        self.scan_btn.config(state='normal')  # Re-enable single scan

        self._log("=== BULK SCAN STOPPED ===", 'info')
        self._log(f"Total: {self.bulk_scan_count} | Auto: {self.bulk_auto_accepted} | Review: {self.bulk_needs_review}", 'dim')

    def _reset_bulk_stats(self):
        """Reset bulk scan statistics"""
        self.bulk_scan_count = 0
        self.bulk_auto_accepted = 0
        self.bulk_needs_review = 0
        self.bulk_scanned_label.config(text="0")
        self.bulk_accepted_label.config(text="0")
        self.bulk_review_label.config(text="0")
        self._log("Bulk scan stats reset", 'dim')

    def _bulk_scan_loop(self):
        """Main bulk scan loop"""
        import time

        while self.bulk_scanning:
            # Check for pause
            if self.bulk_paused:
                time.sleep(0.5)
                continue

            # Check connection
            if not self.connected:
                self._log("Lost connection to DANIELSON - stopping bulk scan", 'error')
                self._schedule_ui(self._stop_bulk_scan)
                break

            try:
                camera = self.camera_var.get()
                threshold = self.bulk_threshold_var.get()

                # Perform scan
                self._log(f"Bulk scan #{self.bulk_scan_count + 1}...", 'dim')

                r = requests.post(
                    f"{self.danielson_url}/api/acr",
                    json={"camera": camera, "card_type": "mtg"},
                    timeout=60
                )

                if r.status_code == 200:
                    result = r.json()

                    if result.get('success'):
                        card = result.get('card') or {}
                        call_number = result.get('call_number', '???')
                        name = card.get('name', 'Unknown')
                        set_code = card.get('set', '???')
                        confidence = result.get('confidence', 0)
                        status = result.get('status', 'unknown')
                        image_path = result.get('image_path', '')

                        self.bulk_scan_count += 1

                        # Update preview on main thread
                        if image_path:
                            self._schedule_ui(lambda p=image_path: self._update_preview_image(p))

                        # Check if auto-accept
                        if confidence >= threshold or status == 'identified':
                            self.bulk_auto_accepted += 1
                            self._log(f"[{call_number}] {name} ({set_code}) - {confidence}% AUTO", 'success')
                            # Add to local library
                            if self.library and card:
                                try:
                                    lib_card = {
                                        'name': name,
                                        'set_code': set_code,
                                        'collector_number': card.get('collector_number', ''),
                                        'condition': 'NM',
                                        'foil': False,
                                        'language': 'EN',
                                        'price_usd': (card.get('prices') or {}).get('usd'),
                                        'rarity': card.get('rarity'),
                                        'set_name': card.get('set_name'),
                                        'scryfall_id': card.get('scryfall_id'),
                                    }
                                    self.library.catalog_card(lib_card)
                                    self.library._save_library()
                                except Exception as e:
                                    self._log(f"  Library error: {e}", 'error')
                        else:
                            self.bulk_needs_review += 1
                            self._log(f"[{call_number}] {name} ({set_code}) - {confidence}% REVIEW", 'warning')

                        # Store current scan for review
                        self.current_scan = result

                        # Populate matches for current scan
                        matches = result.get('possible_matches', [])
                        if card.get('name'):
                            main_match = {'card': card, 'confidence': confidence}
                            if not matches:
                                matches = [main_match]

                        def update_ui():
                            self.bulk_scanned_label.config(text=str(self.bulk_scan_count))
                            self.bulk_accepted_label.config(text=str(self.bulk_auto_accepted))
                            self.bulk_review_label.config(text=str(self.bulk_needs_review))
                            self.count_label.config(text=f"Scans: {self.scan_count + self.bulk_scan_count}")
                            if matches:
                                self._populate_matches(matches)
                            # Fill form
                            self.card_name_var.set(name)
                            self.card_set_var.set(set_code)
                            self.card_number_var.set(card.get('collector_number', ''))
                            self.card_foil_var.set(card.get('foil', False))

                        self._schedule_ui(update_ui)

                    else:
                        error = result.get('error', 'Unknown error')
                        self._log(f"Scan failed: {error}", 'error')
                else:
                    self._log(f"HTTP error: {r.status_code}", 'error')

            except requests.Timeout:
                self._log("Scan timeout", 'error')
            except Exception as e:
                self._log(f"Scan error: {e}", 'error')

            # Delay before next scan
            if self.bulk_scanning and not self.bulk_paused:
                delay = self.bulk_delay_var.get()
                for _ in range(delay * 10):  # Check every 100ms for stop/pause
                    if not self.bulk_scanning or self.bulk_paused:
                        break
                    time.sleep(0.1)

        # Loop ended
        self._schedule_ui(lambda: self.bulk_status_label.config(text="STOPPED", fg=self.colors['error']))

    def _create_scan_log(self, parent):
        """Scan log display (bottom of left panel)"""
        # Results header
        header = tk.Frame(parent, bg=self.colors['surface'])
        header.pack(fill='x', padx=10, pady=(15, 5))

        tk.Label(
            header,
            text="Scan Log",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        ).pack(side='left')

        tk.Button(
            header,
            text="Clear",
            font=('Segoe UI', 9),
            bg=self.colors['bg'],
            fg=self.colors['text_dim'],
            command=self._clear_results,
            cursor='hand2'
        ).pack(side='right')

        # Results text
        self.results = tk.Text(
            parent,
            font=('Consolas', 9),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            height=10,
            state='disabled'
        )
        self.results.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        # Configure tags for colored output
        self.results.tag_configure('success', foreground=self.colors['success'])
        self.results.tag_configure('error', foreground=self.colors['error'])
        self.results.tag_configure('info', foreground=self.colors['accent'])
        self.results.tag_configure('dim', foreground=self.colors['text_dim'])

    def _create_results_panel(self, parent):
        """Scan results display with image preview and review panel"""
        # Top section: Image preview + Possible matches
        top_frame = tk.Frame(parent, bg=self.colors['surface'])
        top_frame.pack(fill='x', padx=10, pady=10)

        # Left: Image preview
        preview_frame = tk.LabelFrame(
            top_frame,
            text="Card Preview",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        preview_frame.pack(side='left', fill='both', padx=(0, 5))

        self.preview_canvas = tk.Canvas(
            preview_frame,
            width=500, height=700,
            bg=self.colors['bg'],
            highlightthickness=1,
            highlightbackground=self.colors['text_dim']
        )
        self.preview_canvas.pack(padx=5, pady=5)
        self.preview_image = None  # Keep reference to prevent garbage collection

        # Click to zoom
        self.preview_canvas.bind('<Button-1>', lambda e: self._open_zoom_window())
        self.preview_canvas.config(cursor='hand2')

        # "No image" placeholder text
        self.preview_canvas.create_text(
            100, 140,
            text="No scan yet",
            fill=self.colors['text_dim'],
            font=('Segoe UI', 10)
        )

        # Right: Possible matches + Review form
        review_frame = tk.LabelFrame(
            top_frame,
            text="Review & Match",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        review_frame.pack(side='left', fill='both', expand=True, padx=(5, 0))

        # Possible matches listbox
        match_label = tk.Label(
            review_frame,
            text="Possible Matches (click to select):",
            font=('Segoe UI', 9),
            fg=self.colors['text'],
            bg=self.colors['surface']
        )
        match_label.pack(anchor='w', padx=5, pady=(5, 2))

        match_list_frame = tk.Frame(review_frame, bg=self.colors['surface'])
        match_list_frame.pack(fill='x', padx=5, pady=2)

        self.match_listbox = tk.Listbox(
            match_list_frame,
            font=('Consolas', 9),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            selectbackground=self.colors['accent'],
            selectforeground='white',
            height=4,
            activestyle='none'
        )
        self.match_listbox.pack(side='left', fill='x', expand=True)

        # Validation report section
        validation_label = tk.Label(
            review_frame,
            text="Cross-Validation Report:",
            font=('Segoe UI', 9, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        validation_label.pack(anchor='w', padx=5, pady=(10, 2))

        # Validation display (fixed font for alignment)
        self.validation_text = tk.Text(
            review_frame,
            font=('Consolas', 8),
            bg=self.colors['bg'],
            fg=self.colors['text'],
            height=6,
            state='disabled',
            wrap='none'
        )
        self.validation_text.pack(fill='x', padx=5, pady=2)
        
        # Configure validation tags
        self.validation_text.tag_configure('valid', foreground=self.colors['success'])
        self.validation_text.tag_configure('invalid', foreground=self.colors['error'])
        self.validation_text.tag_configure('null', foreground=self.colors['text_dim'])
        self.validation_text.tag_configure('header', foreground=self.colors['accent'], font=('Consolas', 8, 'bold'))
        self.match_listbox.bind('<<ListboxSelect>>', self._on_match_select)

        match_scroll = tk.Scrollbar(match_list_frame, command=self.match_listbox.yview)
        match_scroll.pack(side='right', fill='y')
        self.match_listbox.config(yscrollcommand=match_scroll.set)

        # Store match data for selection
        self.possible_matches = []

        # Manual input form
        form_frame = tk.Frame(review_frame, bg=self.colors['surface'])
        form_frame.pack(fill='x', padx=5, pady=5)

        # Card Name
        row1 = tk.Frame(form_frame, bg=self.colors['surface'])
        row1.pack(fill='x', pady=2)
        tk.Label(row1, text="Name:", font=('Segoe UI', 9), fg=self.colors['text'],
                 bg=self.colors['surface'], width=8, anchor='w').pack(side='left')
        self.card_name_var = tk.StringVar()
        self.card_name_entry = tk.Entry(
            row1, textvariable=self.card_name_var, font=('Segoe UI', 9),
            bg=self.colors['bg'], fg=self.colors['text'],
            insertbackground=self.colors['text']
        )
        self.card_name_entry.pack(side='left', fill='x', expand=True)

        # Set Code
        row2 = tk.Frame(form_frame, bg=self.colors['surface'])
        row2.pack(fill='x', pady=2)
        tk.Label(row2, text="Set:", font=('Segoe UI', 9), fg=self.colors['text'],
                 bg=self.colors['surface'], width=8, anchor='w').pack(side='left')
        self.card_set_var = tk.StringVar()
        self.card_set_entry = tk.Entry(
            row2, textvariable=self.card_set_var, font=('Segoe UI', 9),
            bg=self.colors['bg'], fg=self.colors['text'],
            insertbackground=self.colors['text'], width=10
        )
        self.card_set_entry.pack(side='left')

        # Collector Number
        tk.Label(row2, text="  #:", font=('Segoe UI', 9), fg=self.colors['text'],
                 bg=self.colors['surface']).pack(side='left')
        self.card_number_var = tk.StringVar()
        self.card_number_entry = tk.Entry(
            row2, textvariable=self.card_number_var, font=('Segoe UI', 9),
            bg=self.colors['bg'], fg=self.colors['text'],
            insertbackground=self.colors['text'], width=8
        )
        self.card_number_entry.pack(side='left')

        # Condition
        row3 = tk.Frame(form_frame, bg=self.colors['surface'])
        row3.pack(fill='x', pady=2)
        tk.Label(row3, text="Condition:", font=('Segoe UI', 9), fg=self.colors['text'],
                 bg=self.colors['surface'], width=8, anchor='w').pack(side='left')
        self.card_condition_var = tk.StringVar(value="NM")
        conditions = ["M", "NM", "LP", "MP", "HP", "DMG"]
        for cond in conditions:
            tk.Radiobutton(
                row3, text=cond, variable=self.card_condition_var, value=cond,
                font=('Segoe UI', 8), bg=self.colors['surface'], fg=self.colors['text'],
                selectcolor=self.colors['bg'], activebackground=self.colors['surface']
            ).pack(side='left')

        # Foil checkbox
        row4 = tk.Frame(form_frame, bg=self.colors['surface'])
        row4.pack(fill='x', pady=2)
        self.card_foil_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row4, text="Foil", variable=self.card_foil_var,
            font=('Segoe UI', 9), bg=self.colors['surface'], fg=self.colors['text'],
            selectcolor=self.colors['bg'], activebackground=self.colors['surface']
        ).pack(side='left')

        # Language
        tk.Label(row4, text="  Lang:", font=('Segoe UI', 9), fg=self.colors['text'],
                 bg=self.colors['surface']).pack(side='left')
        self.card_lang_var = tk.StringVar(value="EN")
        lang_combo = tk.OptionMenu(row4, self.card_lang_var, "EN", "JP", "DE", "FR", "IT", "ES", "PT", "KO", "ZH")
        lang_combo.config(font=('Segoe UI', 8), bg=self.colors['bg'], fg=self.colors['text'])
        lang_combo.pack(side='left')

        # Review queue navigation
        queue_frame = tk.Frame(form_frame, bg=self.colors['surface'])
        queue_frame.pack(fill='x', pady=(5, 2))

        tk.Button(
            queue_frame, text="Load Queue",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['accent'], fg='white',
            command=self._load_review_queue,
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            queue_frame, text="<",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['bg'], fg=self.colors['text'],
            command=self._prev_review,
            cursor='hand2', width=3
        ).pack(side='left', padx=2)

        self.queue_position_label = tk.Label(
            queue_frame,
            text="0 / 0",
            font=('Consolas', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            width=10
        )
        self.queue_position_label.pack(side='left', padx=5)

        tk.Button(
            queue_frame, text=">",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['bg'], fg=self.colors['text'],
            command=self._next_review,
            cursor='hand2', width=3
        ).pack(side='left', padx=2)

        # Review queue storage
        self.review_queue = []
        self.review_index = 0

        # Action buttons
        btn_frame = tk.Frame(form_frame, bg=self.colors['surface'])
        btn_frame.pack(fill='x', pady=(8, 2))

        tk.Button(
            btn_frame, text="ACCEPT",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white',
            command=self._accept_card,
            cursor='hand2', width=10
        ).pack(side='left', padx=2)

        tk.Button(
            btn_frame, text="SKIP",
            font=('Segoe UI', 10),
            bg=self.colors['warning'], fg='black',
            command=self._skip_card,
            cursor='hand2', width=8
        ).pack(side='left', padx=2)

        tk.Button(
            btn_frame, text="REJECT",
            font=('Segoe UI', 10),
            bg=self.colors['error'], fg='white',
            command=self._reject_card,
            cursor='hand2', width=8
        ).pack(side='left', padx=2)

        # Store current scan data for review
        self.current_scan = None
        self.current_image_path = None

    def _log(self, message, tag=''):
        """Log message to results panel (thread-safe)"""
        def do_log():
            try:
                timestamp = datetime.now().strftime('%H:%M:%S')
                self.results.config(state='normal')
                self.results.insert('end', f"[{timestamp}] ", 'dim')
                self.results.insert('end', f"{message}\n", tag)
                self.results.see('end')
                self.results.config(state='disabled')
            except Exception:
                pass  # Widget may be destroyed

        # Schedule on main thread for thread safety
        try:
            self._schedule_ui(do_log)
        except Exception:
            pass

    def _clear_results(self):
        """Clear results panel"""
        self.results.config(state='normal')
        self.results.delete('1.0', 'end')
        self.results.config(state='disabled')

    def _update_preview_image(self, image_path: str):
        """Update the card preview image - supports remote (DANIELSON) and local paths"""
        if not PIL_AVAILABLE:
            return

        try:
            # Check if path is on DANIELSON (remote Linux path)
            if image_path.startswith('/mnt/') or image_path.startswith('/home/'):
                # Fetch from DANIELSON via HTTP
                import urllib.parse
                encoded_path = urllib.parse.quote(image_path)
                image_url = f"{self.danielson_url}/api/scan_image?path={encoded_path}"
                response = requests.get(image_url, timeout=10)
                if response.status_code == 200:
                    from io import BytesIO
                    img = Image.open(BytesIO(response.content))
                else:
                    raise Exception(f"HTTP {response.status_code}")
            else:
                # Local path
                img = Image.open(image_path)

            # Calculate size to fit canvas (600x840) while maintaining aspect ratio - 3x zoom
            canvas_w, canvas_h = 600, 840
            img_w, img_h = img.size
            ratio = min(canvas_w / img_w, canvas_h / img_h)
            new_w = int(img_w * ratio)
            new_h = int(img_h * ratio)

            # Resize with best available resampling
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                try:
                    resample = Image.LANCZOS
                except AttributeError:
                    resample = Image.BILINEAR

            img = img.resize((new_w, new_h), resample)

            # Convert to PhotoImage
            self.preview_image = ImageTk.PhotoImage(img)

            # Clear canvas and display
            self.preview_canvas.delete('all')
            x = canvas_w // 2
            y = canvas_h // 2
            self.preview_canvas.create_image(x, y, image=self.preview_image, anchor='center')

            self.current_image_path = image_path

        except Exception as e:
            logger.error(f"Failed to load preview image: {e}")
            self.preview_canvas.delete('all')
            self.preview_canvas.create_text(
                100, 140,
                text=f"Load failed:\n{str(e)[:30]}",
                fill=self.colors['error'],
                font=('Segoe UI', 9),
                justify='center'
            )

    def _open_zoom_window(self):
        """Open current image in a new zoomable window"""
        if not self.current_image_path or not PIL_AVAILABLE:
            return

        if not os.path.exists(self.current_image_path):
            self._log("Image file not found", 'error')
            return

        # Create new toplevel window
        zoom_win = tk.Toplevel(self.frame)
        zoom_win.title("Card Preview - Click to close")
        zoom_win.configure(bg='#1a1a1a')

        # Get screen dimensions
        screen_w = zoom_win.winfo_screenwidth()
        screen_h = zoom_win.winfo_screenheight()

        try:
            img = Image.open(self.current_image_path)
            img_w, img_h = img.size

            # Scale to fit screen (max 90% of screen)
            max_w = int(screen_w * 0.9)
            max_h = int(screen_h * 0.9)
            ratio = min(max_w / img_w, max_h / img_h, 1.0)  # Don't upscale

            if ratio < 1.0:
                new_w = int(img_w * ratio)
                new_h = int(img_h * ratio)
                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = Image.LANCZOS
                img = img.resize((new_w, new_h), resample)
            else:
                new_w, new_h = img_w, img_h

            photo = ImageTk.PhotoImage(img)

            # Create label to hold image
            label = tk.Label(zoom_win, image=photo, bg='#1a1a1a')
            label.image = photo  # Keep reference
            label.pack(padx=10, pady=10)

            # Center window on screen
            x = (screen_w - new_w) // 2
            y = (screen_h - new_h) // 2
            zoom_win.geometry(f"{new_w + 20}x{new_h + 20}+{x}+{y}")

            # Click anywhere to close
            label.bind('<Button-1>', lambda e: zoom_win.destroy())
            zoom_win.bind('<Escape>', lambda e: zoom_win.destroy())
            zoom_win.bind('<Button-1>', lambda e: zoom_win.destroy())

            # Focus the window
            zoom_win.focus_set()
            zoom_win.grab_set()

        except Exception as e:
            logger.error(f"Failed to open zoom window: {e}")
            zoom_win.destroy()

    def _populate_matches(self, matches: list):
        """Populate the possible matches listbox"""
        self.match_listbox.delete(0, tk.END)
        self.possible_matches = matches

        for i, match in enumerate(matches):
            card = match.get('card', {})
            name = card.get('name', 'Unknown')
            set_code = card.get('set', '???')
            conf = match.get('confidence', 0)
            display = f"{conf:3}% | {name} ({set_code})"
            self.match_listbox.insert(tk.END, display)

            # Highlight best match
            if i == 0:
                self.match_listbox.itemconfig(i, fg=self.colors['success'])

    def _on_match_select(self, event):
        """Handle selection from possible matches list"""
        selection = self.match_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx < len(self.possible_matches):
            match = self.possible_matches[idx]
            card = match.get('card', {})

            # Populate form fields
            self.card_name_var.set(card.get('name', ''))
            self.card_set_var.set(card.get('set', ''))
            self.card_number_var.set(card.get('collector_number', ''))

            # Check if foil from card data
            if card.get('foil') or card.get('finishes', ['nonfoil'])[0] == 'foil':
                self.card_foil_var.set(True)

            self._log(f"Selected: {card.get('name')} ({card.get('set')})", 'info')

    def _clear_review_form(self):
        """Clear all review form fields"""
        self.card_name_var.set('')
        self.card_set_var.set('')
        self.card_number_var.set('')
        self.card_condition_var.set('NM')
        self.card_foil_var.set(False)
        self.card_lang_var.set('EN')
        self.match_listbox.delete(0, tk.END)
        self.possible_matches = []
        self.current_scan = None

        # Reset preview
        self.preview_canvas.delete('all')
        self.preview_canvas.create_text(
            100, 140,
            text="No scan yet",
            fill=self.colors['text_dim'],
            font=('Segoe UI', 10)
        )

    def _accept_card(self):
        """Accept the card with current form data"""
        name = self.card_name_var.get().strip()
        set_code = self.card_set_var.get().strip()

        if not name:
            messagebox.showwarning("Missing Data", "Card name is required")
            return

        card_data = {
            'name': name,
            'set': set_code,
            'collector_number': self.card_number_var.get().strip(),
            'condition': self.card_condition_var.get(),
            'foil': self.card_foil_var.get(),
            'language': self.card_lang_var.get(),
            'image_path': self.current_image_path
        }

        self._log(f"ACCEPTED: {name} ({set_code}) [{card_data['condition']}]", 'success')

        # PREGRADING MODE: mint NFT certificate if we have grade data
        if (self.current_mode == ScanMode.PREGRADING
                and self.current_grade_result
                and NFT_AVAILABLE
                and _nft_minter):
            def mint_grade_nft(card_name, grade_data, image_path):
                try:
                    self._log("  Minting grade cert NFT...", 'dim')
                    # Build metadata matching nexus_auth cert format
                    import hashlib, json as _json
                    cert_meta = {
                        'item_type': 'TCG Card',
                        'item_name': card_name,
                        'condition_score': grade_data.get('overall_grade'),
                        'condition_label': grade_data.get('grade_label'),
                        'centering': grade_data.get('centering_score'),
                        'corners': grade_data.get('corners_score'),
                        'edges': grade_data.get('edges_score'),
                        'surface': grade_data.get('surface_score'),
                        'analysis_confidence': grade_data.get('confidence'),
                        'assessor': 'NEXUS Automated Condition Assessment (not professional grading)',
                        'timestamp': grade_data.get('timestamp'),
                        'disclaimer': 'NEXUS performs automated condition assessment only. Not professional grading (PSA/BGS/CGC).',
                    }
                    # SHA-256 fingerprint of cert + image bytes
                    raw = _json.dumps(cert_meta, sort_keys=True).encode()
                    if image_path:
                        try:
                            with open(image_path, 'rb') as f:
                                raw += f.read()
                        except Exception:
                            pass
                    cert_hash = hashlib.sha256(raw).hexdigest()
                    nft_result = _nft_minter.mint_or_simulate(
                        item_id=cert_hash[:16],
                        cert_hash=cert_hash,
                        item_name=card_name,
                        item_type='TCG Card',
                        confidence=int((grade_data.get('confidence', 0)) * 100),
                        extra_metadata=cert_meta
                    )
                    tx = nft_result.get('tx_hash', 'N/A')
                    token = nft_result.get('token_id', 'N/A')
                    network = nft_result.get('network', 'demo')
                    self._log(f"  NFT minted [{network}] token:{token}", 'success')
                    self._log(f"  TX: {tx[:20]}...", 'dim')
                except Exception as me:
                    self._log(f"  NFT mint failed: {me}", 'error')

            threading.Thread(
                target=mint_grade_nft,
                args=(name, self.current_grade_result, card_data.get('image_path', '')),
                daemon=True
            ).start()

        # Capture call_number NOW before it changes
        call_num = '???'
        if self.current_scan:
            call_num = self.current_scan.get('call_number', '???')

        # Send to DANIELSON API - confirm endpoint (DANIELSON assigns call number + writes to DB)
        def send_accept(card_name, card_info):
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/review/confirm",
                    json=card_info,
                    timeout=10
                )
                if r.status_code == 200:
                    resp = r.json()
                    cn = resp.get('call_number', '')
                    if cn:
                        self._log(f"  -> Cataloged as {cn}", 'dim')
                    else:
                        self._log(f"  -> Confirmed on DANIELSON", 'dim')
                    # Refresh header card count
                    try:
                        sr = requests.get(f"{self.danielson_url}/api/library/stats", timeout=5)
                        if sr.status_code == 200:
                            total = sr.json().get('total_cards', 0)
                            app = self.frame.winfo_toplevel()
                            if hasattr(app, 'card_count_label'):
                                self.frame.after(0, lambda: app.card_count_label.config(text=f"{total:,}"))
                    except Exception:
                        pass
                else:
                    self._log(f"  -> API error: {r.status_code}", 'error')
            except Exception as e:
                self._log(f"  -> Failed to save: {e}", 'error')

        threading.Thread(target=send_accept, args=(name, card_data), daemon=True).start()

        self.scan_count += 1
        self.count_label.config(text=f"Scans: {self.scan_count}")

        # Remove from local queue and advance to next
        if self.review_queue and self.review_index < len(self.review_queue):
            self.review_queue.pop(self.review_index)
            if self.review_index >= len(self.review_queue) and self.review_index > 0:
                self.review_index -= 1
            self._update_queue_display()
            if self.review_queue:
                self._show_review_item(self.review_index)
            else:
                self._clear_review_form()
        else:
            self._clear_review_form()

    def _skip_card(self):
        """Skip current card, move to next in queue"""
        self._log("SKIPPED - Moving to next", 'info')
        # Move to next item without removing from queue
        if self.review_queue and self.review_index < len(self.review_queue) - 1:
            self.review_index += 1
            self._update_queue_display()
            self._show_review_item(self.review_index)
        else:
            self._log("End of queue", 'dim')
            self._clear_review_form()

    def _reject_card(self):
        """Reject the scan (bad image, not a card, etc.)"""
        self._log("REJECTED - Scan discarded", 'error')

        # Capture call_number NOW before it changes
        call_num = None
        if self.current_scan:
            call_num = self.current_scan.get('call_number')

        # Notify DANIELSON API using skip endpoint with call_number
        def send_reject(cn):
            try:
                self._log(f"  Skipping: {cn}", 'dim')
                if cn:
                    r = requests.post(
                        f"{self.danielson_url}/api/review/skip",
                        json={'call_number': cn},
                        timeout=5
                    )
                    self._log(f"  Skip API: {r.status_code}", 'dim')
            except Exception as e:
                self._log(f"  Skip error: {e}", 'error')

        if call_num:
            threading.Thread(target=send_reject, args=(call_num,), daemon=True).start()

        # Remove from local queue and advance
        if self.review_queue and self.review_index < len(self.review_queue):
            self.review_queue.pop(self.review_index)
            if self.review_index >= len(self.review_queue) and self.review_index > 0:
                self.review_index -= 1
            self._update_queue_display()
            if self.review_queue:
                self._show_review_item(self.review_index)
            else:
                self._clear_review_form()
        else:
            self._clear_review_form()

    def _load_review_queue(self):
        """Load pending reviews from DANIELSON"""
        self._log("Loading review queue...", 'info')

        def fetch_queue():
            try:
                r = requests.get(
                    f"{self.danielson_url}/api/review",
                    timeout=15
                )
                if r.status_code == 200:
                    result = r.json()
                    # DANIELSON returns 'items' key
                    queue = result.get('items', [])
                    self.review_queue = queue
                    self.review_index = 0

                    # Update UI on main thread
                    def update_ui():
                        self._update_queue_display()
                        if queue:
                            self._log(f"Loaded {len(queue)} items in review queue", 'success')
                            self._show_review_item(0)
                        else:
                            self._log("Review queue is empty", 'info')
                    self._schedule_ui(update_ui)
                else:
                    self._log(f"Failed to load queue: HTTP {r.status_code}", 'error')
            except Exception as e:
                self._log(f"Queue load error: {e}", 'error')

        threading.Thread(target=fetch_queue, daemon=True).start()

    def _update_queue_display(self):
        """Update the queue position label"""
        total = len(self.review_queue)
        if total > 0:
            pos = self.review_index + 1
            self.queue_position_label.config(text=f"{pos} / {total}")
        else:
            self.queue_position_label.config(text="0 / 0")

    def _show_review_item(self, index):
        """Display a specific item from the review queue"""
        if not self.review_queue or index < 0 or index >= len(self.review_queue):
            return

        item = self.review_queue[index]
        self.current_scan = item

        # Get image path - could be local path or URL
        image_path = item.get('image_path', '')

        # If it's a remote path, we need to fetch it
        if image_path.startswith('http'):
            self._fetch_and_display_image(image_path)
        elif image_path:
            # Try local path or construct from DANIELSON
            if not os.path.exists(image_path):
                # Fetch from DANIELSON using scan_image endpoint
                # Preserve slashes in path, only encode special chars
                encoded_path = quote(image_path, safe='/:')
                image_url = f"{self.danielson_url}/api/scan_image?path={encoded_path}"
                self._log(f"Fetching image: {image_path}", 'dim')
                self._fetch_and_display_image(image_url)
            else:
                self._update_preview_image(image_path)

        # Populate matches if available
        matches = item.get('possible_matches', [])
        card = (item.get('suggested_card') or item.get('card')
                or item.get('best_guess') or {})

        if card and card.get('name'):
            main_match = {'card': card, 'confidence': item.get('confidence', 0)}
            if not matches:
                matches = [main_match]
            elif matches[0].get('card', {}).get('name') != card.get('name'):
                matches = [main_match] + matches

        if matches:
            self._populate_matches(matches)

        # Fill form with best guess
        if card:
            self.card_name_var.set(card.get('name', ''))
            self.card_set_var.set(card.get('set', ''))
            self.card_number_var.set(card.get('collector_number', ''))
            self.card_foil_var.set(card.get('foil', False))
        else:
            self.card_name_var.set('')
            self.card_set_var.set('')
            self.card_number_var.set('')
            self.card_foil_var.set(False)

        name = card.get('name', 'Unknown') if card else 'Unknown'
        self._log(f"Showing item {index + 1}: {name}", 'info')

    def _fetch_and_display_image(self, url):
        """Fetch image from URL and display it"""
        def fetch():
            try:
                self._log(f"GET {url[:60]}...", 'dim')
                r = requests.get(url, timeout=10)
                self._log(f"Response: {r.status_code}, {len(r.content)} bytes", 'dim')
                if r.status_code == 200:
                    # Save to temp file and display
                    import tempfile
                    with tempfile.NamedTemporaryFile(
                        suffix='.jpg', delete=False
                    ) as f:
                        f.write(r.content)
                        temp_path = f.name

                    # Track for cleanup
                    self._temp_files.append(temp_path)
                    # Keep only last 5 temp files
                    while len(self._temp_files) > 5:
                        old = self._temp_files.pop(0)
                        try:
                            os.remove(old)
                        except Exception:
                            pass

                    def update():
                        self._update_preview_image(temp_path)
                    self._schedule_ui(update)
                else:
                    self._log(f"Failed to fetch image: {r.status_code}", 'error')
            except Exception as e:
                self._log(f"Image fetch error: {e}", 'error')

        threading.Thread(target=fetch, daemon=True).start()

    def _prev_review(self):
        """Show previous item in review queue"""
        if self.review_queue and self.review_index > 0:
            self.review_index -= 1
            self._update_queue_display()
            self._show_review_item(self.review_index)

    def _next_review(self):
        """Show next item in review queue"""
        if self.review_queue and self.review_index < len(self.review_queue) - 1:
            self.review_index += 1
            self._update_queue_display()
            self._show_review_item(self.review_index)

    # =========================================================================
    # MODE SELECTION METHODS
    # =========================================================================

    def _select_mode(self, mode: ScanMode):
        """Handle scanner mode selection."""
        self.current_mode = mode

        # Update mode button styles
        self.single_mode_btn.config(bg=self.colors['surface'])
        self.bulk_mode_btn.config(bg=self.colors['surface'])
        self.pregrade_mode_btn.config(bg=self.colors['surface'])

        if mode == ScanMode.SINGLE_TCG:
            self.single_mode_btn.config(bg=self.colors['success'])
            self.mode_info_label.config(text="Skip back scan - user specifies type")
            self.type_frame.config(fg=self.colors['success'])
            # Enable card type selection
            for btn in self.type_buttons.values():
                btn.config(state='normal')
            # Mark Step 2 as skip
            if len(self.step_indicators) > 1:
                self.step_indicators[1].config(text="--", fg=self.colors['text_dim'])

        elif mode == ScanMode.BULK:
            self.bulk_mode_btn.config(bg=self.colors['warning'])
            self.mode_info_label.config(text="Back scan required - auto-detect type")
            self.type_frame.config(fg=self.colors['text_dim'])
            # Disable card type selection (auto-detect)
            for btn in self.type_buttons.values():
                btn.config(state='disabled')
            # Reset Step 2 indicator
            if len(self.step_indicators) > 1:
                self.step_indicators[1].config(text="O", fg=self.colors['text_dim'])

        elif mode == ScanMode.PREGRADING:
            self.pregrade_mode_btn.config(bg=self.colors['accent'])
            self.mode_info_label.config(text="Full inspection + grade estimate")
            self.type_frame.config(fg=self.colors['text_dim'])
            # Disable card type selection (auto-detect)
            for btn in self.type_buttons.values():
                btn.config(state='disabled')
            # Reset Step 2 indicator
            if len(self.step_indicators) > 1:
                self.step_indicators[1].config(text="O", fg=self.colors['text_dim'])

        self._log(f"Mode: {mode.value.replace('_', ' ').title()}", 'info')

    def _select_card_type(self, card_type: CardType):
        """Handle card type selection (Single TCG mode)."""
        self.selected_card_type = card_type

        # Update button styles
        for ct, btn in self.type_buttons.items():
            if ct == card_type:
                btn.config(bg=CARD_TYPE_COLORS.get(ct, self.colors['accent']))
            else:
                btn.config(bg=self.colors['bg'])

        self._log(f"Card type: {card_type.value.upper()}", 'dim')

    def _update_step(self, step_index: int, status: str):
        """Update 5-step process indicator."""
        if step_index >= len(self.step_indicators):
            return

        def update():
            try:
                if status == "running":
                    self.step_indicators[step_index].config(text="*", fg=self.colors['warning'])
                elif status == "complete":
                    self.step_indicators[step_index].config(text="Y", fg=self.colors['success'])
                elif status == "skipped":
                    self.step_indicators[step_index].config(text="--", fg=self.colors['text_dim'])
                elif status == "error":
                    self.step_indicators[step_index].config(text="X", fg=self.colors['error'])
                else:
                    self.step_indicators[step_index].config(text="O", fg=self.colors['text_dim'])
            except Exception:
                pass

        self._schedule_ui(update)

    def _reset_step_indicators(self):
        """Reset all step indicators to initial state."""
        for i, indicator in enumerate(self.step_indicators):
            # In Single TCG mode, step 2 (Type ID) is skipped
            if i == 1 and self.current_mode == ScanMode.SINGLE_TCG:
                indicator.config(text="--", fg=self.colors['text_dim'])
            else:
                indicator.config(text="O", fg=self.colors['text_dim'])

    def _check_connections(self):
        """Single health check against DANIELSON scanner server"""
        self._log("Checking connection...", 'info')

        # Update URL from entry field if it exists
        if hasattr(self, 'danielson_ip_var'):
            self.danielson_url = self.danielson_ip_var.get()

        def check():
            try:
                r = requests.get(f"{self.danielson_url}/status", timeout=3)
                if r.status_code == 200:
                    self.connected = True
                    data = r.json()
                    cameras = data.get('cameras', [])
                    if isinstance(cameras, set):
                        cameras = list(cameras)
                    cam_str = ', '.join(str(c) for c in cameras) if cameras else 'none'
                    coral = 'TPU' if data.get('coral_loaded') else 'CPU'
                    status_text = f"DANIELSON: ONLINE ({len(cameras)} cams, {coral})"
                    self._schedule_ui(lambda: self.status_indicator.config(text=status_text, fg=self.colors['success']))
                    self._log("DANIELSON: ONLINE", 'success')
                    self._log(f"  Cameras: {cam_str} | Engine: {coral}", 'dim')
                else:
                    self.connected = False
                    self._schedule_ui(lambda: self.status_indicator.config(text="DANIELSON: ERROR", fg=self.colors['error']))
                    self._log(f"DANIELSON: ERROR ({r.status_code})", 'error')
            except Exception as e:
                self.connected = False
                self._schedule_ui(lambda: self.status_indicator.config(text="DANIELSON: OFFLINE", fg=self.colors['error']))
                self._log(f"DANIELSON: OFFLINE ({e})", 'error')

        threading.Thread(target=check, daemon=True).start()

    def _sync_inventory(self):
        """Sync local library with DANIELSON inventory"""
        if not self.connected:
            self._log("Cannot sync - DANIELSON offline", 'error')
            return

        def sync():
            try:
                self._log("Syncing with DANIELSON...", 'info')
                # Pull inventory from DANIELSON
                r = requests.get(f"{self.danielson_url}/api/inventory", timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    items = data.get('items', [])
                    self._log(f"  DANIELSON has {len(items)} cards", 'dim')

                    # Sync to local library if available
                    if self.library:
                        synced = 0
                        for item in items:
                            # Check if card exists in local library
                            name = item.get('name', '')
                            set_code = item.get('set', '')
                            if name and not self._card_in_library(name, set_code):
                                # Add to local library
                                lib_card = {
                                    'name': name,
                                    'set_code': set_code,
                                    'set_name': item.get('set_name', ''),
                                    'rarity': item.get('rarity', ''),
                                    'price_usd': item.get('prices', {}).get('usd'),
                                    'quantity': item.get('qty', 1),
                                }
                                self.library.catalog_card(lib_card)
                                synced += 1

                        if synced > 0:
                            self.library._save_library()
                            self._log(f"  Synced {synced} new cards to local library", 'success')
                        else:
                            self._log("  Local library up to date", 'dim')
                else:
                    self._log(f"  Sync failed: {r.status_code}", 'error')
            except Exception as e:
                self._log(f"  Sync error: {e}", 'error')

        threading.Thread(target=sync, daemon=True).start()

    def _card_in_library(self, name, set_code):
        """Check if card exists in local library"""
        if not self.library:
            return False
        for card in self.library.get_all_cards():
            if card.get('name') == name and card.get('set_code') == set_code:
                return True
        return False

    def _scan_card(self):
        """Perform a card scan using DANIELSON pipeline: capture → art/recognize + ocr → merge"""
        if self.scanning:
            return

        if not self.connected:
            self._log("DANIELSON not connected!", 'error')
            messagebox.showerror("Error", "DANIELSON not connected")
            return

        self.scanning = True
        self.scan_btn.config(state='disabled', text="Scanning...")

        # Reset step indicators
        self._reset_step_indicators()

        mode_name = self.current_mode.value.replace('_', ' ').title()
        self._log(f"Starting {mode_name} scan...", 'info')

        if self.current_mode == ScanMode.SINGLE_TCG:
            self._log(f"Card type: {self.selected_card_type.value.upper()}", 'dim')

        def do_scan():
            try:
                camera = self.camera_var.get()
                mode = self.current_mode
                card_type = self.selected_card_type

                # STEP 1: Capture image via DANIELSON
                self._update_step(0, "running")
                self._log(f"Step 1: Capture ({camera})...", 'dim')

                capture_endpoint = "czur" if camera == "czur" else "webcam"
                r = requests.post(
                    f"{self.danielson_url}/api/capture/{capture_endpoint}",
                    json={},
                    timeout=15
                )

                if r.status_code != 200:
                    raise Exception(f"Capture failed: HTTP {r.status_code}")

                cap_result = r.json()
                if not cap_result.get('success'):
                    raise Exception(f"Capture failed: {cap_result.get('error', 'unknown')}")

                image_path = cap_result.get('image_path', '')
                if not image_path:
                    raise Exception("No image_path in capture response")

                self._update_step(0, "complete")
                self._log(f"  Captured: {image_path}", 'dim')

                # Update preview image
                if image_path:
                    self._schedule_ui(lambda p=image_path: self._update_preview_image(p))

                # STEP 2: Type ID (skipped in Single TCG mode)
                if mode == ScanMode.SINGLE_TCG:
                    self._update_step(1, "skipped")
                else:
                    self._update_step(1, "running")
                    # TODO: back-scan type detection for BULK mode
                    self._update_step(1, "complete")

                # STEP 3: Art Match (FAISS on DANIELSON)
                self._update_step(2, "running")
                self._log("Step 3: Art recognition (FAISS)...", 'dim')

                art_result = {}
                try:
                    r = requests.post(
                        f"{self.danielson_url}/api/art/recognize",
                        json={"image_path": image_path, "card_type": card_type.value},
                        timeout=30
                    )
                    if r.status_code == 200:
                        art_result = r.json()
                        self._update_step(2, "complete")
                        art_conf = art_result.get('confidence', 0)
                        art_name = art_result.get('name', '?')
                        self._log(f"  Art: {art_name} ({art_conf}%)", 'dim')
                    else:
                        self._update_step(2, "error")
                        self._log(f"  Art match failed: HTTP {r.status_code}", 'error')
                except Exception as ae:
                    self._update_step(2, "error")
                    self._log(f"  Art match error: {ae}", 'error')

                # STEP 4: OCR (Tesseract on DANIELSON)
                self._update_step(3, "running")
                self._log("Step 4: OCR (Tesseract)...", 'dim')

                ocr_result = {}
                try:
                    r = requests.post(
                        f"{self.danielson_url}/api/ocr",
                        json={"image_path": image_path},
                        timeout=30
                    )
                    if r.status_code == 200:
                        ocr_result = r.json()
                        self._update_step(3, "complete")
                        ocr_name = ocr_result.get('name', '')
                        self._log(f"  OCR: {ocr_name or '(no text)'}", 'dim')
                    else:
                        self._update_step(3, "error")
                        self._log(f"  OCR failed: HTTP {r.status_code}", 'error')
                except Exception as oe:
                    self._update_step(3, "error")
                    self._log(f"  OCR error: {oe}", 'error')

                # STEP 5: Cross-Reference / Merge
                self._update_step(4, "running")

                # Merge: art match is primary (FAISS), OCR supplements
                confidence = art_result.get('confidence', 0)
                name = art_result.get('name') or ocr_result.get('name') or 'Unknown'
                set_code = art_result.get('set') or ocr_result.get('set') or '???'

                card = {
                    'name': name,
                    'set': set_code,
                    'collector_number': art_result.get('collector_number') or ocr_result.get('collector_number', ''),
                    'rarity': art_result.get('rarity', ''),
                    'set_name': art_result.get('set_name', ''),
                    'image_path': image_path,
                }

                status = 'identified' if confidence >= 95 else ('likely' if confidence >= 70 else 'review_needed')

                result = {
                    'success': True,
                    'card': card,
                    'confidence': confidence,
                    'image_path': image_path,
                    'art_result': art_result,
                    'ocr_result': ocr_result,
                    'status': status,
                }

                self._update_step(4, "complete")

                # Store current scan data
                self.current_scan = result
                self.current_grade_result = None

                # PREGRADING MODE: run local CV grading on the captured image
                if mode == ScanMode.PREGRADING and GRADING_AVAILABLE and image_path:
                    try:
                        # Fetch image from DANIELSON for local grading
                        import urllib.parse
                        encoded = urllib.parse.quote(image_path)
                        img_resp = requests.get(
                            f"{self.danielson_url}/api/scan_image?path={encoded}",
                            timeout=10
                        )
                        if img_resp.status_code == 200:
                            import numpy as np
                            from io import BytesIO
                            arr = np.frombuffer(img_resp.content, np.uint8)
                            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                            if img is not None:
                                analyzer = CardGradingAnalyzer()
                                grade_data = analyzer.analyze_card(img)
                                self.current_grade_result = grade_data
                                g = grade_data.get('overall_grade', '?')
                                gl = grade_data.get('grade_label', '')
                                gconf = grade_data.get('confidence', 0) * 100
                                self._log(f"  Grade: {g}/10 - {gl} ({gconf:.0f}% conf)", 'success')
                                self._log(f"  Center:{grade_data.get('centering_score',0):.0f} "
                                          f"Corners:{grade_data.get('corners_score',0):.0f} "
                                          f"Edges:{grade_data.get('edges_score',0):.0f} "
                                          f"Surface:{grade_data.get('surface_score',0):.0f}", 'dim')
                    except Exception as ge:
                        self._log(f"  Grade analysis error: {ge}", 'error')

                # Get possible matches from art result
                matches = art_result.get('matches', [])
                if card.get('name') and card['name'] != 'Unknown':
                    main_match = {'card': card, 'confidence': confidence}
                    if not matches or matches[0].get('card', {}).get('name') != name:
                        matches = [main_match] + matches

                # Populate matches list
                if matches:
                    self._schedule_ui(lambda m=matches: self._populate_matches(m))

                # Pre-fill form with best guess
                def fill_form():
                    self.card_name_var.set(name)
                    self.card_set_var.set(set_code)
                    self.card_number_var.set(card.get('collector_number', ''))
                    if card.get('foil'):
                        self.card_foil_var.set(True)
                self._schedule_ui(fill_form)

                # Log based on status
                if status == 'identified':
                    self.scan_count += 1
                    self._schedule_ui(lambda: self.count_label.config(text=f"Scans: {self.scan_count}"))
                    self._log(f"{name} ({set_code})", 'success')
                    self._log(f"  Confidence: {confidence}% - AUTO ADDED", 'dim')
                elif status == 'likely':
                    self._log(f"{name} ({set_code})", 'info')
                    self._log(f"  Confidence: {confidence}% - Verify and ACCEPT", 'dim')
                else:
                    self._log("NEEDS REVIEW", 'error')
                    self._log(f"  Best guess: {name} ({confidence}%)", 'dim')
                    self._log("  Select a match or enter data manually", 'info')

            except requests.Timeout:
                self._log("Scan timeout - no response from DANIELSON", 'error')
                for i in range(5):
                    self._update_step(i, "error")
            except Exception as e:
                self._log(f"Scan error: {e}", 'error')
                for i in range(5):
                    self._update_step(i, "error")
            finally:
                self.scanning = False
                self._schedule_ui(lambda: self.scan_btn.config(state='normal', text="SCAN CARD"))

        threading.Thread(target=do_scan, daemon=True).start()

    def _capture_only(self):
        """Capture image without OCR"""
        if not self.connected:
            self._log("DANIELSON not connected!", 'error')
            return

        self._log("Capturing image...", 'info')

        def capture():
            try:
                camera = self.camera_var.get()
                endpoint = "czur" if camera == "czur" else "webcam"
                r = requests.post(
                    f"{self.danielson_url}/api/capture/{endpoint}",
                    json={},
                    timeout=15
                )
                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        path = result.get('image_path', 'unknown')
                        self._log(f"Image captured: {path}", 'success')
                    else:
                        self._log(f"Capture failed: {result.get('error')}", 'error')
                else:
                    self._log(f"Capture error: HTTP {r.status_code}", 'error')
            except Exception as e:
                self._log(f"Capture error: {e}", 'error')

        threading.Thread(target=capture, daemon=True).start()

    def _display_validation_report(self, validation: dict):
        """Display cross-validation report with color-coded source checks"""
        try:
            self.validation_text.config(state='normal')
            self.validation_text.delete('1.0', 'end')
            
            if not validation:
                self.validation_text.insert('end', "No validation data", 'null')
                self.validation_text.config(state='disabled')
                return
            
            # Count valid sources
            valid_count = 0
            total_count = 0
            
            # OCR source
            ocr = validation.get('ocr', {})
            if isinstance(ocr, dict):
                total_count += 1
                is_valid = ocr.get('valid', False)
                if is_valid:
                    valid_count += 1
                check = '✓' if is_valid else '✗'
                tag = 'valid' if is_valid else 'invalid'
                text = ocr.get('text', 'N/A')
                self.validation_text.insert('end', f"{check} OCR:       ", tag)
                self.validation_text.insert('end', f"{text}\n")
            
            # ZULTAN source (art matching)
            zultan = validation.get('zultan', {})
            if isinstance(zultan, dict):
                total_count += 1
                is_valid = zultan.get('valid', False)
                if is_valid:
                    valid_count += 1
                check = '✓' if is_valid else '✗'
                tag = 'valid' if is_valid else 'invalid'
                match = zultan.get('match', 'N/A')
                similarity = zultan.get('similarity', 0)
                self.validation_text.insert('end', f"{check} ZULTAN:    ", tag)
                self.validation_text.insert('end', f"{match} ({similarity:.0%})\n")
            
            # Scryfall source
            scryfall = validation.get('scryfall', {})
            if isinstance(scryfall, dict):
                total_count += 1
                is_valid = scryfall.get('valid', False)
                if is_valid:
                    valid_count += 1
                check = '✓' if is_valid else '✗'
                tag = 'valid' if is_valid else 'invalid'
                match = scryfall.get('match', 'N/A')
                similarity = scryfall.get('similarity', 0)
                self.validation_text.insert('end', f"{check} Scryfall:  ", tag)
                self.validation_text.insert('end', f"{match} ({similarity:.0%})\n")
            
            # Set code source
            set_code = validation.get('set', {})
            if isinstance(set_code, dict) and set_code.get('valid') is not None:
                total_count += 1
                is_valid = set_code.get('valid', False)
                if is_valid:
                    valid_count += 1
                check = '✓' if is_valid else '✗'
                tag = 'valid' if is_valid else 'invalid'
                code = set_code.get('code', 'N/A')
                self.validation_text.insert('end', f"{check} Set Code:  ", tag)
                self.validation_text.insert('end', f"{code}\n")
            
            # Collector number source
            collector = validation.get('collector', {})
            if isinstance(collector, dict) and collector.get('valid') is not None:
                total_count += 1
                is_valid = collector.get('valid', False)
                if is_valid:
                    valid_count += 1
                check = '✓' if is_valid else '✗'
                tag = 'valid' if is_valid else 'invalid'
                num = collector.get('number', 'N/A')
                self.validation_text.insert('end', f"{check} Collector: ", tag)
                self.validation_text.insert('end', f"{num}\n")
            
            # Summary line
            self.validation_text.insert('end', '\n')
            score = f"{valid_count}/{total_count}"
            if valid_count >= 4:
                self.validation_text.insert('end', f"Score: {score} - STRONG\n", 'valid')
            elif valid_count >= 2:
                self.validation_text.insert('end', f"Score: {score} - PASS\n", 'header')
            else:
                self.validation_text.insert('end', f"Score: {score} - WEAK\n", 'invalid')
            
            self.validation_text.config(state='disabled')
            
        except Exception as e:
            logger.error(f"Failed to display validation report: {e}")
            self.validation_text.config(state='normal')
            self.validation_text.delete('1.0', 'end')
            self.validation_text.insert('end', f"Display error: {e}", 'invalid')
            self.validation_text.config(state='disabled')

    def cleanup(self):
        """Cleanup on tab close"""
        # Stop polling loops
        self._queue_polling = False

        # Stop bulk scanning if active
        self.bulk_scanning = False
        self.bulk_paused = False

        # Cancel all pending .after() callbacks
        for after_id in self._after_ids:
            try:
                self.frame.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()

        # Clean up temp files
        for temp_file in self._temp_files:
            try:
                os.remove(temp_file)
            except Exception:
                pass
        self._temp_files.clear()
