#!/usr/bin/env python3
"""
NEXUS V2 - Hardware Controls Tab
Patent Pending - Kevin Caracozza (Filed Nov 27, 2025)

Controls hardware components via REST API:
- DANIELSON (192.168.1.219:5001): Cameras, LEDs, Arm, Vacuum, OCR, storage
"""

import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import hashlib
import time as _time
from datetime import datetime

import requests

from .live_view import LiveViewTab

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================
DANIELSON_URL = os.getenv('NEXUS_DANIELSON_URL', 'http://192.168.1.219:5001')

# Hardware limits
NUM_SERVOS = 8
NUM_LED_CH = 8
LIFT_SERVO_START_INDEX = 5  # Servos 5-7 are lift (yellow), 0-4 are arm (blue)

# Timing constants
API_TIMEOUT = 5  # seconds
POLL_INTERVAL_MS = 3000
TEST_DEBOUNCE_MS = 50
CONNECTION_CHECK_INTERVAL_MS = 5000

# Default values
DEFAULT_SERVO_ANGLE = 90
DEFAULT_BRIGHTNESS = 255
DEFAULT_GAMMA = 1.0


class HardwareControlsTab:
    """
    Hardware Controls Interface.

    Features:
    - Camera Focus control
    - Scanner LED controls (5 channels: GPIO12=8ring, GPIO27=80matrix, GPIO26=dead, GPIO25=caselight, GPIO33=40matrix)
    - Unified light controls (via Pro Micro, 8-channel NeoPixel)
    - 8-DOF Arm + Lift control
    - Vacuum & Fan control
    """

    def __init__(self, notebook: ttk.Notebook, config):
        """Initialize Hardware Controls tab."""
        self.notebook = notebook
        self.config = config
        self.colors = self._get_colors()

        # Server URL (from constant, configurable via environment)
        self.danielson_url = DANIELSON_URL
        self.connected = False

        # Servo state - defaults match ESP32 firmware limits
        self.joint_angles = [DEFAULT_SERVO_ANGLE] * NUM_SERVOS
        self.servo_trim = [0] * NUM_SERVOS
        self.servo_min = [47, 60, 55, 29] + [0] * (NUM_SERVOS - 4)
        self.servo_max = [115, 170, 165, 127] + [180] * (NUM_SERVOS - 4)
        self.servo_expo = [30, 30, 30, 20] + [0] * (NUM_SERVOS - 4)

        # Stepper state
        self.stepper_positions = [0]  # Base only (Shoulder is now servo)
        self.stepper_speeds = [500]

        # Relay state
        self.vacuum_state = False
        self.solenoid_state = False

        # LED channel calibration (Arduino Micro)
        self.ch_brightness = [DEFAULT_BRIGHTNESS] * NUM_LED_CH
        self.ch_gamma = [DEFAULT_GAMMA] * NUM_LED_CH
        self.ch_enabled = [True] * NUM_LED_CH

        # UI element references (initialized in _build_ui)
        self._init_ui_refs()

        # Create tab
        self.frame = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(self.frame, text="Hardware")

        self._build_ui()
        self._start_ui_queue_processor()
        self._check_connection()

    def _init_ui_refs(self):
        """Initialize UI element references to None."""
        # Status
        self.status_label = None
        # Focus
        self.focus_var = None
        self.focus_scale = None
        self.focus_label = None
        # Brightness
        self.brightness_var = None
        self.brightness_scale = None
        self.bright_label = None
        # LED channel settings
        self.ch_settings_visible = False
        self.ch_toggle_btn = None
        self.ch_settings_frame = None
        self.ch_bright_vars = []
        self.ch_bright_labels = []
        self.ch_gamma_vars = []
        self.ch_gamma_labels = []
        self.ch_enable_vars = []
        # Servo settings
        self.servo_settings_visible = False
        self.servo_toggle_btn = None
        self.servo_settings_frame = None
        self.joint_names = []
        self.joint_labels = []
        self.min_labels = [None] * 8
        self.max_labels = [None] * 8
        self.trim_labels = [None] * 8
        self.expo_labels = [None] * 8
        self.test_scales = [None] * 8
        self.angle_labels = [None] * 8
        # Stepper controls
        self.stepper_pos_labels = []
        self.stepper_speed_labels = []
        self.stepper_angle_scales = []
        self.stepper_angle_labels = []
        self.stepper_angles = [90]  # Base only (Shoulder is now servo on ch0)
        # Relay controls
        self.vacuum_status = None
        self.solenoid_status = None
        # Fan
        self.fan_var = None
        self.fan_scale = None
        # Timers
        self._brightness_timer = None
        self._fan_timer = None
        # Stats polling
        self._stats_polling = False
        # Thread-safe UI queue for background thread -> main thread communication
        self._ui_queue = queue.Queue()
        self._queue_polling = False
        self._after_ids = []  # Track .after() callback IDs for proper cleanup
        # DANIELSON stats bars
        self.cpu_bar = None
        self.cpu_label = None
        self.mem_bar = None
        self.mem_label = None
        self.disk_bar = None
        self.disk_label = None
        self.temp_label = None
        self.uptime_label = None
        # (ESP32 WiFi Monitor removed — all control via DANIELSON USB serial now)
        # Blockchain validation
        self.validate_btn = None
        self.collector_btn = None
        self.blockchain_status_label = None
        self.validation_log_text = None
        self._pop_engine = None  # ProofOfPresence instance (lazy init)

    def _start_ui_queue_processor(self):
        """Start the UI queue processor on the main thread."""
        if self._queue_polling:
            return
        self._queue_polling = True
        self._process_ui_queue()

    def _process_ui_queue(self):
        """Process pending UI updates from background threads (runs on main thread)."""
        if not self._queue_polling:
            return
        try:
            # Process up to 10 items per cycle to avoid blocking
            for _ in range(10):
                try:
                    callback = self._ui_queue.get_nowait()
                    if callable(callback):
                        callback()
                except queue.Empty:
                    break
        except Exception:
            pass
        # Only schedule next check if still polling and widget exists
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

    def _get_colors(self):
        """Get theme colors."""
        return {
            'bg': '#4a4a4a',
            'surface': '#555555',
            'accent': '#5c6bc0',
            'success': '#4caf50',
            'error': '#f44336',
            'warning': '#ff9800',
            'text': '#ffffff',
            'text_dim': '#888888'
        }

    def _build_ui(self):
        """Build the hardware controls interface."""
        # Main container with scroll
        main_canvas = tk.Canvas(self.frame, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.frame, orient='vertical', command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas, bg=self.colors['bg'])

        scrollable_frame.bind('<Configure>', lambda e: main_canvas.configure(
            scrollregion=main_canvas.bbox('all')
        ))

        self._canvas_window = main_canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        main_canvas.configure(yscrollcommand=scrollbar.set)

        # Pack scrollbar and canvas
        scrollbar.pack(side='right', fill='y')
        main_canvas.pack(side='left', fill='both', expand=True)

        # Keep scrollable_frame width matched to canvas (fills screen width)
        def _on_canvas_configure(event):
            main_canvas.itemconfig(self._canvas_window, width=event.width)
        main_canvas.bind('<Configure>', _on_canvas_configure)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        # Bind mousewheel to canvas and all children
        def _bind_mousewheel(event):
            main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            main_canvas.unbind_all("<MouseWheel>")

        main_canvas.bind("<Enter>", _bind_mousewheel)
        main_canvas.bind("<Leave>", _unbind_mousewheel)
        scrollable_frame.bind("<Enter>", _bind_mousewheel)
        scrollable_frame.bind("<Leave>", _unbind_mousewheel)

        # Update scroll region when content changes
        def _configure_scroll(event):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        scrollable_frame.bind("<Configure>", _configure_scroll)

        # Status bar at top
        self._create_status_bar(scrollable_frame)

        # Grid layout - use all space, left to right, top to bottom
        grid = tk.Frame(scrollable_frame, bg=self.colors['bg'])
        grid.pack(fill='both', expand=True, padx=5, pady=5)

        # Configure 4 equal columns
        for i in range(4):
            grid.columnconfigure(i, weight=1, uniform='col')

        # Row weights: rows 0-1 (main controls + camera) get expansion priority
        grid.rowconfigure(0, weight=0)   # LEDs/Lightbox - natural height
        grid.rowconfigure(1, weight=1)   # Arm + Camera - expand to fill
        grid.rowconfigure(2, weight=0)   # Servo settings - natural height
        grid.rowconfigure(3, weight=0)   # Stats/ESP32 - natural height

        # ROW 0: Scanner LEDs, Lightbox | Live Camera (top-right, spans 2 cols + 2 rows)
        self._create_light_controls(grid, 0, 0)
        # Lightbox only in col 1
        self._create_lightbox_controls(grid, row=0, col=1)

        cam_outer = tk.LabelFrame(
            grid,
            text="Live Camera",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['bg']
        )
        cam_outer.grid(row=0, column=2, columnspan=2, rowspan=2, sticky='nsew', padx=2, pady=2)
        self.live_camera_panel = LiveViewTab(cam_outer, self.config)

        # ROW 1: Arm Controls + Vacuum/Solenoid (spans 2 cols)
        self._create_arm_controls(grid, 1, 0, colspan=2)

        # ROW 2: Servo Settings (full width)
        servo_settings_container = tk.Frame(grid, bg=self.colors['bg'])
        servo_settings_container.grid(row=2, column=0, columnspan=4, sticky='nsew', padx=2, pady=2)
        self._create_servo_settings(servo_settings_container)

        # ROW 3: System Stats (full width)
        self._create_combined_system_stats(grid, 3, 0, colspan=4)

    def _create_status_bar(self, parent):
        """Create connection status bar with VALIDATE button."""
        status_frame = tk.Frame(parent, bg=self.colors['surface'], height=50)
        status_frame.pack(fill='x', padx=10, pady=5)
        status_frame.pack_propagate(False)

        tk.Label(
            status_frame, text="HARDWARE CONTROLS",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['accent'], bg=self.colors['surface']
        ).pack(side='left', padx=10, pady=8)

        # === VALIDATE BUTTON - Big, green, prominent ===
        self.validate_btn = tk.Button(
            status_frame, text="VALIDATE",
            font=('Segoe UI', 14, 'bold'),
            bg='#00c853', fg='white',
            activebackground='#00e676', activeforeground='white',
            width=14, height=1,
            command=self._on_validate_click,
            cursor='hand2',
            relief='raised', bd=3
        )
        self.validate_btn.pack(side='left', padx=10, pady=4)

        # === COLLECTOR BUTTON - Gold, burst capture + dual hash ===
        self.collector_btn = tk.Button(
            status_frame, text="COLLECTOR",
            font=('Segoe UI', 12, 'bold'),
            bg='#ff8f00', fg='white',
            activebackground='#ffa000', activeforeground='white',
            width=12, height=1,
            command=self._on_collector_click,
            cursor='hand2',
            relief='raised', bd=3
        )
        self.collector_btn.pack(side='left', padx=5, pady=4)

        # Blockchain status
        self.blockchain_status_label = tk.Label(
            status_frame, text="Polygon: --",
            font=('Consolas', 9),
            fg=self.colors['text_dim'], bg=self.colors['surface']
        )
        self.blockchain_status_label.pack(side='left', padx=5, pady=8)

        self.status_label = tk.Label(
            status_frame, text="DANIELSON: --",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'], bg=self.colors['surface']
        )
        self.status_label.pack(side='right', padx=10, pady=8)

        tk.Button(
            status_frame, text="Refresh",
            font=('Segoe UI', 9),
            bg=self.colors['bg'], fg=self.colors['text'],
            command=self._check_connection,
            cursor='hand2'
        ).pack(side='right', padx=5)

    def _create_focus_controls(self, parent, row=0, col=0, colspan=1):
        """Camera focus controls."""
        frame = tk.LabelFrame(
            parent,
            text="Camera",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=2, pady=2)

        # Focus slider
        slider_frame = tk.Frame(frame, bg=self.colors['surface'])
        slider_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(
            slider_frame, text="Focus:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(side='left')

        self.focus_var = tk.DoubleVar(value=9.0)
        self.focus_scale = tk.Scale(
            slider_frame,
            from_=0.0, to=15.0,
            resolution=0.5,
            orient='horizontal',
            variable=self.focus_var,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            highlightthickness=0,
            length=150,
            command=self._on_focus_change
        )
        self.focus_scale.pack(side='left', padx=10, fill='x', expand=True)

        self.focus_label = tk.Label(
            slider_frame, text="9.0",
            font=('Consolas', 11, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface'],
            width=5
        )
        self.focus_label.pack(side='left')

        # Focus buttons
        btn_frame = tk.Frame(frame, bg=self.colors['surface'])
        btn_frame.pack(fill='x', padx=10, pady=5)

        tk.Button(
            btn_frame, text="Test",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['accent'], fg='white',
            command=self._test_focus,
            cursor='hand2', width=8
        ).pack(side='left', padx=3)

        tk.Button(
            btn_frame, text="Auto",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['warning'], fg='black',
            command=self._autofocus,
            cursor='hand2', width=8
        ).pack(side='left', padx=3)

        tk.Button(
            btn_frame, text="Calibrate",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['bg'], fg=self.colors['text'],
            command=self._calibrate_focus,
            cursor='hand2', width=10
        ).pack(side='left', padx=3)

    def _create_light_controls(self, parent, row=0, col=0, colspan=1):
        """Scanner LED controls (Pro Micro, 6 NeoPixel channels) with RGB sliders."""
        frame = tk.LabelFrame(
            parent,
            text="Scanner LEDs",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=2, pady=2)

        # Master ON/OFF buttons
        master_frame = tk.Frame(frame, bg=self.colors['surface'])
        master_frame.pack(fill='x', padx=10, pady=5)

        tk.Button(
            master_frame, text="ALL ON",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white', width=8,
            command=lambda: self._set_lights('on'),
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            master_frame, text="ALL OFF",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white', width=8,
            command=lambda: self._set_lights('off'),
            cursor='hand2'
        ).pack(side='left', padx=3)

        # RGB Sliders for all channels
        self.leds_r = tk.IntVar(value=255)
        self.leds_g = tk.IntVar(value=255)
        self.leds_b = tk.IntVar(value=255)

        for color, var, clr in [("R", self.leds_r, "#ff4444"),
                                 ("G", self.leds_g, "#44ff44"),
                                 ("B", self.leds_b, "#4444ff")]:
            row = tk.Frame(frame, bg=self.colors['surface'])
            row.pack(fill='x', padx=10, pady=1)
            tk.Label(row, text=color, font=('Segoe UI', 9, 'bold'),
                     fg=clr, bg=self.colors['surface'], width=2).pack(side='left')
            slider = tk.Scale(row, from_=0, to=255, orient='horizontal',
                              variable=var, showvalue=False,
                              bg=self.colors['surface'], fg=self.colors['text'],
                              highlightthickness=0, troughcolor=clr, length=120,
                              command=lambda v: self._update_leds_preview())
            slider.pack(side='left', fill='x', expand=True)

        # Preview + Apply
        preview_frame = tk.Frame(frame, bg=self.colors['surface'])
        preview_frame.pack(fill='x', padx=10, pady=5)

        self.leds_preview = tk.Label(preview_frame, text="   ", width=4,
                                       bg='#ffffff', relief='solid', borderwidth=1)
        self.leds_preview.pack(side='left', padx=5)

        tk.Button(
            preview_frame, text="APPLY ALL",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['accent'], fg='white', width=10,
            command=self._apply_leds_rgb,
            cursor='hand2'
        ).pack(side='left', padx=5)

        # Individual channel controls — Pro Micro 6-channel NeoPixel
        indiv_frame = tk.Frame(frame, bg=self.colors['surface'])
        indiv_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(indiv_frame, text="Channels:", font=('Segoe UI', 9),
                 fg=self.colors['text_dim'], bg=self.colors['surface']).pack(side='left')

        # Pro Micro channels (1-indexed, sent directly to firmware)
        for ch_num in range(1, 7):
            tk.Button(
                indiv_frame, text=f"CH{ch_num}",
                font=('Segoe UI', 8, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text'], width=3,
                command=lambda c=ch_num: self._apply_single_ch_rgb(c),
                cursor='hand2'
            ).pack(side='left', padx=1)


    def _update_leds_preview(self):
        """Update LED color preview."""
        r, g, b = self.leds_r.get(), self.leds_g.get(), self.leds_b.get()
        self.leds_preview.config(bg=f'#{r:02x}{g:02x}{b:02x}')

    def _apply_leds_rgb(self):
        """Apply RGB values to all scanner LED channels."""
        r, g, b = self.leds_r.get(), self.leds_g.get(), self.leds_b.get()
        self._set_lights_rgb(r, g, b)

    def _apply_single_ch_rgb(self, ch_idx):
        """Apply current RGB to single LED channel (0-indexed)."""
        r, g, b = self.leds_r.get(), self.leds_g.get(), self.leds_b.get()
        self._set_ch_color(ch_idx, r, g, b)

    def _set_leds_preset(self, r, g, b):
        """Set preset color and update sliders."""
        self.leds_r.set(r)
        self.leds_g.set(g)
        self.leds_b.set(b)
        self._update_leds_preview()
        self._set_lights_rgb(r, g, b)

    def _create_ch_settings(self, parent):
        """Create per-channel LED settings for Pro Micro."""
        # Toggle button
        self.ch_settings_visible = False
        self.ch_toggle_btn = tk.Button(
            parent, text="▶ LED Channel Settings",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['bg'], fg=self.colors['accent'],
            command=self._toggle_ch_settings,
            cursor='hand2', anchor='w'
        )
        self.ch_toggle_btn.pack(fill='x', padx=10, pady=5)

        # Settings container (hidden by default)
        self.ch_settings_frame = tk.Frame(
            parent, bg=self.colors['surface']
        )

        # Channel names — Pro Micro 8-channel NeoPixel
        ch_names = ["CH1 (12 LEDs)", "CH2 (8 LEDs)", "CH3 Case (1 LED)", "CH4 (24 LEDs)", "CH5 (16 LEDs)", "CH6 (16 LEDs)", "CH7 (24 LEDs)", "CH8 (32 LEDs)"]

        # Per-channel controls
        self.ch_bright_vars = []
        self.ch_bright_labels = []
        self.ch_gamma_vars = []
        self.ch_gamma_labels = []
        self.ch_enable_vars = []

        for i in range(NUM_LED_CH):
            ch_frame = tk.LabelFrame(
                self.ch_settings_frame,
                text=ch_names[i],
                font=('Segoe UI', 9, 'bold'),
                fg=self.colors['text'],
                bg=self.colors['bg']
            )
            ch_frame.pack(fill='x', padx=5, pady=3)

            # Enable checkbox and brightness row
            row1 = tk.Frame(ch_frame, bg=self.colors['bg'])
            row1.pack(fill='x', padx=5, pady=2)

            enable_var = tk.BooleanVar(value=True)
            self.ch_enable_vars.append(enable_var)
            tk.Checkbutton(
                row1, text="On",
                variable=enable_var,
                font=('Segoe UI', 9),
                fg=self.colors['text'],
                bg=self.colors['bg'],
                selectcolor=self.colors['surface'],
                command=lambda c=i: self._on_ch_enable_change(c)
            ).pack(side='left')

            tk.Label(
                row1, text="Bright:",
                font=('Segoe UI', 9),
                fg=self.colors['text_dim'],
                bg=self.colors['bg']
            ).pack(side='left', padx=(10, 0))

            bright_var = tk.IntVar(value=255)
            self.ch_bright_vars.append(bright_var)
            tk.Scale(
                row1, from_=0, to=255,
                orient='horizontal', variable=bright_var,
                bg=self.colors['bg'], fg=self.colors['text'],
                highlightthickness=0, length=80,
                command=lambda v, c=i: self._on_ch_bright_change(c, v)
            ).pack(side='left', fill='x', expand=True)

            bright_lbl = tk.Label(
                row1, text="255",
                font=('Consolas', 9),
                fg=self.colors['text'],
                bg=self.colors['bg'], width=4
            )
            bright_lbl.pack(side='left')
            self.ch_bright_labels.append(bright_lbl)

            # Gamma row
            row2 = tk.Frame(ch_frame, bg=self.colors['bg'])
            row2.pack(fill='x', padx=5, pady=2)

            tk.Label(
                row2, text="Gamma:",
                font=('Segoe UI', 9),
                fg=self.colors['text_dim'],
                bg=self.colors['bg']
            ).pack(side='left')

            gamma_var = tk.DoubleVar(value=1.0)
            self.ch_gamma_vars.append(gamma_var)
            tk.Scale(
                row2, from_=0.5, to=3.0,
                resolution=0.1,
                orient='horizontal', variable=gamma_var,
                bg=self.colors['bg'], fg=self.colors['text'],
                highlightthickness=0, length=100,
                command=lambda v, c=i: self._on_ch_gamma_change(c, v)
            ).pack(side='left', fill='x', expand=True)

            gamma_lbl = tk.Label(
                row2, text="1.0",
                font=('Consolas', 9),
                fg=self.colors['text'],
                bg=self.colors['bg'], width=4
            )
            gamma_lbl.pack(side='left')
            self.ch_gamma_labels.append(gamma_lbl)

        # Load/Reset buttons (no EEPROM save needed)
        btn_frame = tk.Frame(
            self.ch_settings_frame, bg=self.colors['surface']
        )
        btn_frame.pack(fill='x', padx=5, pady=8)

        tk.Button(
            btn_frame, text="Load from ESP32",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['accent'], fg='white',
            command=self._load_ch_settings,
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            btn_frame, text="Reset",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['error'], fg='white',
            command=self._reset_ch_settings,
            cursor='hand2'
        ).pack(side='left', padx=3)

    def _toggle_ch_settings(self):
        """Toggle LED channel settings visibility."""
        self.ch_settings_visible = not self.ch_settings_visible
        if self.ch_settings_visible:
            self.ch_toggle_btn.config(
                text="▼ LED Channel Settings"
            )
            self.ch_settings_frame.pack(fill='x', padx=5, pady=5)
        else:
            self.ch_toggle_btn.config(
                text="▶ LED Channel Settings"
            )
            self.ch_settings_frame.pack_forget()

    def _on_ch_enable_change(self, ch):
        """Handle channel enable toggle. ch is 0-indexed."""
        enabled = self.ch_enable_vars[ch].get()
        self.ch_enabled[ch] = enabled
        # Send as 1-indexed to match hardware (ch 1, 2)
        self._send_ch_setting(
            ch + 1, 'enabled', 1 if enabled else 0
        )

    def _on_ch_bright_change(self, ch, value):
        """Handle channel brightness change. ch is 0-indexed."""
        v = int(float(value))
        self.ch_brightness[ch] = v
        self.ch_bright_labels[ch].config(text=str(v))
        # Send as 1-indexed to match hardware (ch 1, 2)
        self._send_ch_setting(ch + 1, 'brightness', v)

    def _on_ch_gamma_change(self, ch, value):
        """Handle channel gamma change. ch is 0-indexed."""
        v = float(value)
        self.ch_gamma[ch] = v
        self.ch_gamma_labels[ch].config(text=f"{v:.1f}")
        # Send gamma as int (x100), 1-indexed
        self._send_ch_setting(ch + 1, 'gamma', int(v * 100))

    def _send_ch_setting(self, ch, setting_type, value):
        """Send LED channel setting to Arduino Micro via DANIELSON."""
        if not self.connected:
            return

        # Debounce
        timer_key = f'_ch_{ch}_{setting_type}_timer'
        if hasattr(self, timer_key) and getattr(self, timer_key):
            self.frame.after_cancel(getattr(self, timer_key))

        def send():
            try:
                requests.post(
                    f"{self.danielson_url}/api/lights/ch/setting",
                    json={
                        "ch": ch,
                        "type": setting_type,
                        "value": value
                    },
                    timeout=5
                )
            except Exception:
                pass

        setattr(self, timer_key, self.frame.after(
            150, lambda: threading.Thread(
                target=send, daemon=True
            ).start()
        ))

    def _load_ch_settings(self):
        """Load LED channel settings from Arduino Micro."""
        if not self.connected:
            return

        def load():
            try:
                r = requests.get(
                    f"{self.danielson_url}/api/lights/ch/settings",
                    timeout=5
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get('success'):
                        settings = data.get('settings', {})
                        self._schedule_ui(
                            lambda: self._apply_ch_settings(
                                settings
                            )
                        )
                        self._schedule_ui(
                            lambda: self._log_status(
                                "LED settings loaded"
                            )
                        )
            except Exception as e:
                self._schedule_ui(
                    lambda err=e: self._log_status(
                        f"Load error: {err}"
                    )
                )

        threading.Thread(target=load, daemon=True).start()

    def _apply_ch_settings(self, settings):
        """Apply loaded LED channel settings to UI."""
        if 'brightness' in settings:
            for i, v in enumerate(
                settings['brightness'][:NUM_LED_CH]
            ):
                self.ch_brightness[i] = v
                self.ch_bright_vars[i].set(v)
                self.ch_bright_labels[i].config(text=str(v))
        if 'gamma' in settings:
            for i, v in enumerate(
                settings['gamma'][:NUM_LED_CH]
            ):
                g = v / 100.0
                self.ch_gamma[i] = g
                self.ch_gamma_vars[i].set(g)
                self.ch_gamma_labels[i].config(
                    text=f"{g:.1f}"
                )
        if 'enabled' in settings:
            for i, v in enumerate(
                settings['enabled'][:NUM_LED_CH]
            ):
                e = v == 1
                self.ch_enabled[i] = e
                self.ch_enable_vars[i].set(e)

    def _reset_ch_settings(self):
        """Reset all LED channel settings to defaults."""
        for i in range(NUM_LED_CH):
            self.ch_brightness[i] = 255
            self.ch_gamma[i] = 1.0
            self.ch_enabled[i] = True
            self.ch_bright_vars[i].set(255)
            self.ch_gamma_vars[i].set(1.0)
            self.ch_enable_vars[i].set(True)
            self.ch_bright_labels[i].config(text="255")
            self.ch_gamma_labels[i].config(text="1.0")
        self._log_status("LED settings reset")

    def _create_lightbox_controls(self, parent, row=0, col=0, colspan=1, pack_mode=False):
        """Lightbox (backlight) controls — ARM ESP32 bottom light."""
        frame = tk.LabelFrame(
            parent,
            text="Lightbox",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        if pack_mode:
            frame.pack(fill='x', padx=0, pady=(0, 2))
        else:
            frame.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=2, pady=2)

        # ON/OFF buttons
        btn_frame = tk.Frame(frame, bg=self.colors['surface'])
        btn_frame.pack(fill='x', padx=10, pady=5)

        tk.Button(
            btn_frame, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white', width=6,
            command=lambda: self._set_lightbox('on'),
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            btn_frame, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white', width=6,
            command=lambda: self._set_lightbox('off'),
            cursor='hand2'
        ).pack(side='left', padx=3)

        # RGB Sliders
        self.lightbox_r = tk.IntVar(value=255)
        self.lightbox_g = tk.IntVar(value=255)
        self.lightbox_b = tk.IntVar(value=255)

        for color, var, clr in [("R", self.lightbox_r, "#ff4444"),
                                 ("G", self.lightbox_g, "#44ff44"),
                                 ("B", self.lightbox_b, "#4444ff")]:
            slider_row = tk.Frame(frame, bg=self.colors['surface'])
            slider_row.pack(fill='x', padx=10, pady=1)
            tk.Label(slider_row, text=color, font=('Segoe UI', 9, 'bold'),
                     fg=clr, bg=self.colors['surface'], width=2).pack(side='left')
            tk.Scale(slider_row, from_=0, to=255, orient='horizontal',
                     variable=var, showvalue=False,
                     bg=self.colors['surface'], fg=self.colors['text'],
                     highlightthickness=0, troughcolor=clr, length=120,
                     command=lambda v: self._update_lightbox_preview()
            ).pack(side='left', fill='x', expand=True)

        # Color preview + APPLY button
        apply_frame = tk.Frame(frame, bg=self.colors['surface'])
        apply_frame.pack(fill='x', padx=10, pady=5)

        self.lightbox_preview = tk.Label(
            apply_frame, text="", width=4, height=1,
            bg='#ffffff', relief='sunken', borderwidth=2
        )
        self.lightbox_preview.pack(side='left', padx=(0, 5))

        tk.Button(
            apply_frame, text="APPLY",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['accent'], fg='white', width=8,
            command=self._apply_lightbox_rgb,
            cursor='hand2'
        ).pack(side='left', padx=3)

    def _update_lightbox_preview(self):
        """Update lightbox color preview."""
        r, g, b = self.lightbox_r.get(), self.lightbox_g.get(), self.lightbox_b.get()
        self.lightbox_preview.config(bg=f'#{r:02x}{g:02x}{b:02x}')

    def _apply_lightbox_rgb(self):
        """Apply RGB values to lightbox."""
        r, g, b = self.lightbox_r.get(), self.lightbox_g.get(), self.lightbox_b.get()
        self._set_lightbox_rgb(r, g, b)

    # ═══════════════════════════════════════════════════════════════════
    # TOP LIGHTS (Pro Micro, 8-channel canopy LEDs)
    # ═══════════════════════════════════════════════════════════════════

    def _create_toplight_controls(self, parent):
        """Top light controls (Pro Micro, 8 NeoPixel channels in canopy)."""
        frame = tk.LabelFrame(
            parent,
            text="Top Lights (Pro Micro)",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.pack(fill='x', padx=0, pady=(2, 0))

        # ON / OFF / TEST buttons
        btn_frame = tk.Frame(frame, bg=self.colors['surface'])
        btn_frame.pack(fill='x', padx=10, pady=5)

        tk.Button(
            btn_frame, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white', width=5,
            command=lambda: self._set_toplights('on'),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            btn_frame, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white', width=5,
            command=lambda: self._set_toplights('off'),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            btn_frame, text="TEST",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['accent'], fg='white', width=5,
            command=lambda: self._set_toplights('test'),
            cursor='hand2'
        ).pack(side='left', padx=2)

        # Presets
        preset_frame = tk.Frame(frame, bg=self.colors['surface'])
        preset_frame.pack(fill='x', padx=10, pady=2)
        for preset in ["SCAN", "PHOTO", "GRADE"]:
            tk.Button(
                preset_frame, text=preset,
                font=('Segoe UI', 9),
                bg=self.colors['surface'], fg=self.colors['text'],
                width=7,
                command=lambda p=preset: self._set_toplight_preset(p),
                cursor='hand2'
            ).pack(side='left', padx=2)

        # Brightness slider
        bright_frame = tk.Frame(frame, bg=self.colors['surface'])
        bright_frame.pack(fill='x', padx=10, pady=3)
        tk.Label(bright_frame, text="Brightness",
                 font=('Segoe UI', 9), fg=self.colors['text'],
                 bg=self.colors['surface']).pack(side='left')
        self.toplight_brightness = tk.IntVar(value=128)
        tk.Scale(bright_frame, from_=0, to=255, orient='horizontal',
                 variable=self.toplight_brightness, showvalue=True,
                 bg=self.colors['surface'], fg=self.colors['text'],
                 highlightthickness=0, length=120,
                 command=lambda v: self._set_toplight_brightness(int(v))
        ).pack(side='left', fill='x', expand=True)

    def _set_toplights(self, action):
        """Control top lights on/off/test."""
        if not self.connected:
            return

        def send():
            try:
                requests.post(
                    f"{self.danielson_url}/api/toplights/{action}",
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=send, daemon=True).start()

    def _set_toplight_preset(self, preset):
        """Apply top light preset."""
        if not self.connected:
            return

        def send():
            try:
                requests.post(
                    f"{self.danielson_url}/api/toplights/preset",
                    json={"preset": preset},
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=send, daemon=True).start()

    def _set_toplight_brightness(self, val):
        """Set top light brightness."""
        if not self.connected:
            return

        def send():
            try:
                requests.post(
                    f"{self.danielson_url}/api/toplights/brightness",
                    json={"brightness": val},
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=send, daemon=True).start()

    def _create_arm_controls(self, parent, row=0, col=0, colspan=1):
        """5-DOF Robotic Arm controls - matches actual hardware."""
        frame = tk.LabelFrame(
            parent,
            text="Arm",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=2, pady=2)

        # Joint names - ACTUAL WIRING (verified 2/27/2026):
        # Display: Shoulder(Ch1) → Elbow(Ch4) → Wrist Tilt(Ch3) → Card Rotate(Ch2)
        # Array index = display position, NOT PCA channel
        self.joint_names = ["Shoulder", "Card Rotate", "Elbow", "Wrist Tilt"]  # Fixed 3/4/2026: correct physical labels
        self.joint_cmds = ["shoulder", "elbow", "wpitch", "wyaw"]
        # Channel-indexed command list (index = PCA channel, for calibration panel)
        self.channel_cmds = ["shoulder", "wyaw", "wpitch", "elbow"]

        # Joint controls - 4 servos with sliders and +/- buttons
        self.joint_labels = []
        self.joint_sliders = []
        self.joint_vars = []

        # Servo limits: (min, max) - matches display order above
        # Shoulder(47-115), Elbow(29-127), WristTilt(55-165), CardRotate(60-170)
        self.joint_limits = [(47, 115), (29, 127), (55, 165), (60, 170)]

        for i in range(4):  # 4 servos: Shoulder, WristYaw, WristPitch, Elbow
            joint_frame = tk.Frame(frame, bg=self.colors['surface'])
            joint_frame.pack(fill='x', padx=10, pady=2)

            jmin, jmax = self.joint_limits[i]

            # Show joint name
            tk.Label(
                joint_frame, text=f"{self.joint_names[i]}:",
                font=('Consolas', 10),
                fg=self.colors['text_dim'],
                bg=self.colors['surface'],
                width=12, anchor='w'
            ).pack(side='left')

            tk.Button(
                joint_frame, text="-",
                font=('Segoe UI', 10, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text'],
                width=2,
                command=lambda j=i: self._jog_joint(j, -5),
                cursor='hand2'
            ).pack(side='left', padx=1)

            # Slider for direct position control
            var = tk.IntVar(value=(jmin + jmax) // 2)
            self.joint_vars.append(var)

            slider = tk.Scale(
                joint_frame,
                from_=jmin, to=jmax,
                orient='horizontal',
                variable=var,
                length=120,
                showvalue=False,
                bg=self.colors['surface'],
                fg=self.colors['text'],
                troughcolor=self.colors['bg'],
                highlightthickness=0,
                command=lambda val, j=i: self._on_joint_slider(j, int(val))
            )
            slider.pack(side='left', padx=2)
            self.joint_sliders.append(slider)

            lbl = tk.Label(
                joint_frame, text="90°",
                font=('Consolas', 11, 'bold'),
                fg=self.colors['text'],
                bg=self.colors['surface'],
                width=4
            )
            lbl.pack(side='left')
            self.joint_labels.append(lbl)

            tk.Button(
                joint_frame, text="+",
                font=('Segoe UI', 10, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text'],
                width=2,
                command=lambda j=i: self._jog_joint(j, 5),
                cursor='hand2'
            ).pack(side='left', padx=1)

        # Preset buttons
        preset_frame = tk.Frame(frame, bg=self.colors['surface'])
        preset_frame.pack(fill='x', padx=10, pady=8)

        tk.Button(
            preset_frame, text="HOME",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['warning'], fg='black',
            command=lambda: self._goto_preset('home'),
            cursor='hand2', width=20
        ).pack(fill='x', pady=3)

        btn_row = tk.Frame(preset_frame, bg=self.colors['surface'])
        btn_row.pack(fill='x', pady=3)

        for name in ["Scan", "Pickup", "Eject", "Stack"]:
            tk.Button(
                btn_row, text=name,
                font=('Segoe UI', 10, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text'],
                command=lambda n=name.lower(): self._goto_preset(n),
                cursor='hand2', width=5
            ).pack(side='left', padx=2, expand=True, fill='x')

        # Save current position as preset
        save_frame = tk.Frame(preset_frame, bg=self.colors['surface'])
        save_frame.pack(fill='x', pady=3)

        self.preset_name_var = tk.StringVar(value="home")
        preset_dropdown = ttk.Combobox(
            save_frame, textvariable=self.preset_name_var,
            values=["home", "scan", "pickup", "eject", "stack"],
            width=10, font=('Consolas', 10)
        )
        preset_dropdown.pack(side='left', padx=2)

        tk.Button(
            save_frame, text="SAVE POS",
            font=('Segoe UI', 10, 'bold'),
            bg='#27ae60', fg='white',
            command=self._save_preset,
            cursor='hand2', width=10
        ).pack(side='left', padx=2)

        self.save_status_label = tk.Label(
            save_frame, text="",
            font=('Consolas', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        )
        self.save_status_label.pack(side='left', padx=5)

        # ============== VACUUM / SOLENOID CONTROLS ==============
        vac_sol_frame = tk.LabelFrame(
            frame,
            text="Vacuum / Solenoid",
            font=('Segoe UI', 10, 'bold'),
            fg='#e67e22',
            bg=self.colors['surface']
        )
        vac_sol_frame.pack(fill='x', pady=2)

        vac_row = tk.Frame(vac_sol_frame, bg=self.colors['surface'])
        vac_row.pack(fill='x', padx=5, pady=3)

        tk.Label(
            vac_row, text="Vacuum:",
            font=('Consolas', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface'], width=10, anchor='w'
        ).pack(side='left')

        tk.Button(
            vac_row, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white', width=5,
            command=lambda: self._set_vacuum(True),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            vac_row, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white', width=5,
            command=lambda: self._set_vacuum(False),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            vac_row, text="Pulse",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['warning'], fg='black', width=6,
            command=self._pulse_vacuum,
            cursor='hand2'
        ).pack(side='left', padx=2)

        sol_row = tk.Frame(vac_sol_frame, bg=self.colors['surface'])
        sol_row.pack(fill='x', padx=5, pady=3)

        tk.Label(
            sol_row, text="Solenoid:",
            font=('Consolas', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface'], width=10, anchor='w'
        ).pack(side='left')

        tk.Button(
            sol_row, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white', width=5,
            command=lambda: self._set_solenoid(True),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            sol_row, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white', width=5,
            command=lambda: self._set_solenoid(False),
            cursor='hand2'
        ).pack(side='left', padx=2)

        # ============== STEPPER CONTROLS (Base only) ==============
        stepper_frame = tk.LabelFrame(
            frame,
            text="Base Stepper",
            font=('Segoe UI', 10, 'bold'),
            fg='#9b59b6',
            bg=self.colors['surface']
        )
        stepper_frame.pack(fill='x', pady=2)

        self.stepper_pos_labels = []
        stepper_names = ["Base"]

        for i, name in enumerate(stepper_names):
            row = tk.Frame(stepper_frame, bg=self.colors['surface'])
            row.pack(fill='x', padx=5, pady=3)

            # Stepper name
            tk.Label(
                row, text=f"{name}:",
                font=('Consolas', 10),
                fg=self.colors['text_dim'],
                bg=self.colors['surface'],
                width=8, anchor='w'
            ).pack(side='left')

            # Step buttons: -400, -200, -100, POS, +100, +200, +400
            for steps in [-400, -200, -100]:
                tk.Button(
                    row, text=str(steps), width=4,
                    font=('Segoe UI', 9, 'bold'),
                    bg='#8e44ad', fg='white',
                    command=lambda j=i, s=steps: self._jog_stepper(j, s),
                    cursor='hand2'
                ).pack(side='left', padx=1)

            # Position display
            pos_lbl = tk.Label(
                row, text="0",
                font=('Consolas', 11, 'bold'),
                fg='#9b59b6', bg=self.colors['surface'], width=6
            )
            pos_lbl.pack(side='left', padx=5)
            self.stepper_pos_labels.append(pos_lbl)

            for steps in [100, 200, 400]:
                tk.Button(
                    row, text=f"+{steps}", width=4,
                    font=('Segoe UI', 9, 'bold'),
                    bg='#9b59b6', fg='white',
                    command=lambda j=i, s=steps: self._jog_stepper(j, s),
                    cursor='hand2'
                ).pack(side='left', padx=1)

            # HOME button
            tk.Button(
                row, text="HOME", width=5,
                font=('Segoe UI', 9, 'bold'),
                bg='#e74c3c', fg='white',
                command=lambda j=i: self._home_stepper(j),
                cursor='hand2'
            ).pack(side='left', padx=5)

        # Base angle slider row
        slider_row = tk.Frame(stepper_frame, bg=self.colors['surface'])
        slider_row.pack(fill='x', padx=5, pady=3)

        tk.Label(
            slider_row, text="Angle:",
            font=('Consolas', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface'],
            width=8, anchor='w'
        ).pack(side='left')

        self.base_angle_var = tk.IntVar(value=0)
        self.base_angle_slider = tk.Scale(
            slider_row,
            from_=0, to=180,
            orient='horizontal',
            variable=self.base_angle_var,
            length=200,
            showvalue=False,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            troughcolor=self.colors['bg'],
            highlightthickness=0,
            command=self._on_base_angle_slider
        )
        self.base_angle_slider.pack(side='left', padx=5)

        self.base_angle_label = tk.Label(
            slider_row, text="0°",
            font=('Consolas', 11, 'bold'),
            fg='#9b59b6', bg=self.colors['surface'], width=5
        )
        self.base_angle_label.pack(side='left')

    def _on_base_angle_slider(self, val):
        """Handle base angle slider change."""
        angle = int(val)
        self.base_angle_label.config(text=f"{angle}°")

        if not self.connected:
            return

        def set_angle():
            try:
                requests.post(
                    f"{self.danielson_url}/api/stepper/angle",
                    json={"angle": angle},
                    timeout=5
                )
            except:
                pass

        threading.Thread(target=set_angle, daemon=True).start()

    def _create_servo_settings(self, parent):
        """Create collapsible servo calibration section - compact table layout."""
        # Toggle button
        self.servo_settings_visible = False
        self.servo_toggle_btn = tk.Button(
            parent, text="▶ Servo Settings",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['bg'], fg=self.colors['accent'],
            command=self._toggle_servo_settings,
            cursor='hand2', anchor='w'
        )
        self.servo_toggle_btn.pack(fill='x', padx=10, pady=5)

        # Settings container (hidden by default)
        self.servo_settings_frame = tk.Frame(parent, bg=self.colors['bg'])

        # Title
        tk.Label(
            self.servo_settings_frame,
            text="SERVO CALIBRATION",
            font=('Segoe UI', 12, 'bold'),
            fg='#4caf50', bg=self.colors['bg']
        ).pack(pady=(5, 8))

        # Header row
        header = tk.Frame(self.servo_settings_frame, bg=self.colors['bg'])
        header.pack(fill='x', padx=5)

        # Column widths (must match control widths below)
        name_w = 8
        val_w = 4
        btn_w = 2
        ctrl_w = btn_w + val_w + btn_w + 2  # -/value/+ plus padding = 10

        tk.Label(header, text="", width=name_w, bg=self.colors['bg']).pack(side='left')
        tk.Label(header, text="MIN", font=('Segoe UI', 8, 'bold'), fg='#888',
                 bg=self.colors['bg'], width=ctrl_w, anchor='center').pack(side='left', padx=2)
        tk.Label(header, text="MAX", font=('Segoe UI', 8, 'bold'), fg='#888',
                 bg=self.colors['bg'], width=ctrl_w, anchor='center').pack(side='left', padx=2)
        tk.Label(header, text="TRIM", font=('Segoe UI', 8, 'bold'), fg='#888',
                 bg=self.colors['bg'], width=ctrl_w, anchor='center').pack(side='left', padx=2)
        tk.Label(header, text="EXPO", font=('Segoe UI', 8, 'bold'), fg='#888',
                 bg=self.colors['bg'], width=ctrl_w, anchor='center').pack(side='left', padx=2)
        tk.Label(header, text="TEST", font=('Segoe UI', 8, 'bold'), fg='#888',
                 bg=self.colors['bg'], width=70, anchor='center').pack(side='left', padx=5)
        tk.Label(header, text="", width=5, bg=self.colors['bg']).pack(side='left')

        # Storage for UI elements - pre-allocate by channel index
        self.min_labels = [None] * 8
        self.max_labels = [None] * 8
        self.trim_labels = [None] * 8
        self.expo_labels = [None] * 8
        self.test_scales = [None] * 8
        self.angle_labels = [None] * 8

        # Servo display names - indexed by PCA channel (verified 2/27/2026)
        # Ch0=Shoulder, Ch1=CardRotate, Ch2=Elbow, Ch3=WristTilt (verified 3/4/2026)
        # Vacuum suction cup for card pickup (no grabber servo)
        servo_names = ["Shoulder", "Card Rotate", "Elbow", "Wrist Tilt"]  # Fixed 3/4/2026: CH2=Elbow, CH3=WristTilt

        for i in [0, 2, 3, 1]:  # Display: Shoulder, Elbow, Wrist Tilt, Card Rotate (fixed 3/4/2026)
            row = tk.Frame(self.servo_settings_frame, bg=self.colors['bg'])
            row.pack(fill='x', padx=5, pady=2)

            # Servo name
            tk.Label(
                row, text=servo_names[i],
                font=('Consolas', 9),
                fg=self.colors['text'], bg=self.colors['bg'],
                width=name_w, anchor='w'
            ).pack(side='left')

            # MIN controls: - value + (red/green buttons)
            min_frame = tk.Frame(row, bg=self.colors['bg'])
            min_frame.pack(side='left', padx=2)

            tk.Button(
                min_frame, text="-", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#c0392b', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'min', -5),
                cursor='hand2'
            ).pack(side='left')

            min_lbl = tk.Label(
                min_frame, text=str(self.servo_min[i]),
                font=('Consolas', 9), fg=self.colors['text'],
                bg=self.colors['bg'], width=val_w
            )
            min_lbl.pack(side='left')
            self.min_labels[i] = min_lbl

            tk.Button(
                min_frame, text="+", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#27ae60', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'min', 5),
                cursor='hand2'
            ).pack(side='left')

            # MAX controls
            max_frame = tk.Frame(row, bg=self.colors['bg'])
            max_frame.pack(side='left', padx=2)

            tk.Button(
                max_frame, text="-", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#c0392b', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'max', -5),
                cursor='hand2'
            ).pack(side='left')

            max_lbl = tk.Label(
                max_frame, text=str(self.servo_max[i]),
                font=('Consolas', 9), fg=self.colors['text'],
                bg=self.colors['bg'], width=val_w
            )
            max_lbl.pack(side='left')
            self.max_labels[i] = max_lbl

            tk.Button(
                max_frame, text="+", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#27ae60', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'max', 5),
                cursor='hand2'
            ).pack(side='left')

            # TRIM controls
            trim_frame = tk.Frame(row, bg=self.colors['bg'])
            trim_frame.pack(side='left', padx=2)

            tk.Button(
                trim_frame, text="-", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#c0392b', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'trim', -1),
                cursor='hand2'
            ).pack(side='left')

            trim_lbl = tk.Label(
                trim_frame, text="+0",
                font=('Consolas', 9), fg=self.colors['text'],
                bg=self.colors['bg'], width=val_w
            )
            trim_lbl.pack(side='left')
            self.trim_labels[i] = trim_lbl

            tk.Button(
                trim_frame, text="+", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#27ae60', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'trim', 1),
                cursor='hand2'
            ).pack(side='left')

            # EXPO controls
            expo_frame = tk.Frame(row, bg=self.colors['bg'])
            expo_frame.pack(side='left', padx=2)

            tk.Button(
                expo_frame, text="-", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#c0392b', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'expo', -5),
                cursor='hand2'
            ).pack(side='left')

            expo_lbl = tk.Label(
                expo_frame, text="30%",
                font=('Consolas', 9), fg=self.colors['text'],
                bg=self.colors['bg'], width=val_w
            )
            expo_lbl.pack(side='left')
            self.expo_labels[i] = expo_lbl

            tk.Button(
                expo_frame, text="+", width=btn_w,
                font=('Segoe UI', 8, 'bold'),
                bg='#27ae60', fg='white',
                command=lambda j=i: self._adjust_servo_setting(j, 'expo', 5),
                cursor='hand2'
            ).pack(side='left')

            # TEST slider (blue for servos)
            test_color = '#3498db'
            test_scale = tk.Scale(
                row, from_=0, to=180,
                orient='horizontal',
                bg=self.colors['bg'], fg=self.colors['text'],
                troughcolor=test_color,
                highlightthickness=0, length=200,
                showvalue=False,
                command=lambda v, j=i: self._test_servo(j, int(float(v)))
            )
            test_scale.set(90)
            test_scale.pack(side='left', padx=5)
            self.test_scales[i] = test_scale

            # Current angle display
            angle_lbl = tk.Label(
                row, text="90°",
                font=('Consolas', 10, 'bold'),
                fg=self.colors['text'], bg=self.colors['bg'],
                width=5
            )
            angle_lbl.pack(side='left')
            self.angle_labels[i] = angle_lbl

        # ============== STEPPER SECTION ==============
        stepper_header = tk.Label(
            self.servo_settings_frame,
            text="─── STEPPERS ───",
            font=('Segoe UI', 10, 'bold'),
            fg='#9b59b6', bg=self.colors['bg']
        )
        stepper_header.pack(pady=(10, 5))

        # Motor names matching ESP32 firmware (nexus_arm_controller.ino):
        # BA = Base stepper (TB6600 - DIR 18/19, PUL 33/25)
        # SH = Shoulder servo (PCA ch0) - NOT a stepper
        stepper_names = ["Base"]
        self.stepper_pos_labels = []
        self.stepper_speed_labels = []

        for i, name in enumerate(stepper_names):
            row = tk.Frame(self.servo_settings_frame, bg=self.colors['bg'])
            row.pack(fill='x', padx=5, pady=2)

            # Stepper name
            tk.Label(
                row, text=name,
                font=('Consolas', 9),
                fg=self.colors['text'], bg=self.colors['bg'],
                width=name_w, anchor='w'
            ).pack(side='left')

            # Step buttons: -400, -200, -100, POS, +100, +200, +400
            step_frame = tk.Frame(row, bg=self.colors['bg'])
            step_frame.pack(side='left', padx=5)

            for steps in [-400, -200, -100]:
                tk.Button(
                    step_frame, text=str(steps), width=4,
                    font=('Segoe UI', 8, 'bold'),
                    bg='#8e44ad', fg='white',
                    command=lambda j=i, s=steps: self._jog_stepper(j, s),
                    cursor='hand2'
                ).pack(side='left', padx=1)

            # Position display
            pos_lbl = tk.Label(
                step_frame, text="0",
                font=('Consolas', 10, 'bold'),
                fg='#9b59b6', bg=self.colors['bg'], width=6
            )
            pos_lbl.pack(side='left', padx=5)
            self.stepper_pos_labels.append(pos_lbl)

            for steps in [100, 200, 400]:
                tk.Button(
                    step_frame, text=f"+{steps}", width=4,
                    font=('Segoe UI', 8, 'bold'),
                    bg='#9b59b6', fg='white',
                    command=lambda j=i, s=steps: self._jog_stepper(j, s),
                    cursor='hand2'
                ).pack(side='left', padx=1)

            # HOME button
            tk.Button(
                step_frame, text="HOME", width=5,
                font=('Segoe UI', 8, 'bold'),
                bg='#e74c3c', fg='white',
                command=lambda j=i: self._home_stepper(j),
                cursor='hand2'
            ).pack(side='left', padx=5)

            # Speed control
            tk.Label(
                row, text="Speed:",
                font=('Segoe UI', 8),
                fg=self.colors['text_dim'], bg=self.colors['bg']
            ).pack(side='left', padx=(10, 2))

            speed_scale = tk.Scale(
                row, from_=100, to=2000,
                orient='horizontal',
                bg=self.colors['bg'], fg=self.colors['text'],
                troughcolor='#9b59b6',
                highlightthickness=0, length=100,
                showvalue=False,
                command=lambda v, j=i: self._set_stepper_speed(j, int(float(v)))
            )
            speed_scale.set(500)
            speed_scale.pack(side='left')

            speed_lbl = tk.Label(
                row, text="500",
                font=('Consolas', 9),
                fg=self.colors['text'], bg=self.colors['bg'], width=4
            )
            speed_lbl.pack(side='left')
            self.stepper_speed_labels.append(speed_lbl)

            # Angle slider row
            angle_row = tk.Frame(self.servo_settings_frame, bg=self.colors['bg'])
            angle_row.pack(fill='x', padx=5, pady=1)

            tk.Label(
                angle_row, text=f"  {name} Angle:",
                font=('Segoe UI', 8),
                fg='#9b59b6', bg=self.colors['bg'],
                width=name_w + 2, anchor='w'
            ).pack(side='left')

            angle_scale = tk.Scale(
                angle_row, from_=0, to=180,
                orient='horizontal',
                bg=self.colors['bg'], fg=self.colors['text'],
                troughcolor='#9b59b6',
                highlightthickness=0, length=250,
                showvalue=False,
                command=lambda v, j=i: self._on_stepper_angle_change(j, int(float(v)))
            )
            angle_scale.set(90)
            angle_scale.pack(side='left', padx=5)
            self.stepper_angle_scales.append(angle_scale)

            angle_lbl = tk.Label(
                angle_row, text="90°",
                font=('Consolas', 10, 'bold'),
                fg='#9b59b6', bg=self.colors['bg'], width=5
            )
            angle_lbl.pack(side='left')
            self.stepper_angle_labels.append(angle_lbl)

            # GO button to send angle command
            tk.Button(
                angle_row, text="GO",
                font=('Segoe UI', 8, 'bold'),
                bg='#27ae60', fg='white', width=4,
                command=lambda j=i: self._send_stepper_angle(j),
                cursor='hand2'
            ).pack(side='left', padx=5)

        # ============== RELAY SECTION ==============
        relay_header = tk.Label(
            self.servo_settings_frame,
            text="─── RELAYS ───",
            font=('Segoe UI', 10, 'bold'),
            fg='#e67e22', bg=self.colors['bg']
        )
        relay_header.pack(pady=(10, 5))

        relay_row = tk.Frame(self.servo_settings_frame, bg=self.colors['bg'])
        relay_row.pack(fill='x', padx=5, pady=5)

        # Vacuum Pump
        vacuum_frame = tk.LabelFrame(
            relay_row, text="Vacuum Pump",
            font=('Segoe UI', 9, 'bold'),
            fg='#e67e22', bg=self.colors['bg']
        )
        vacuum_frame.pack(side='left', padx=10, pady=5)

        self.vacuum_status = tk.Label(
            vacuum_frame, text="OFF",
            font=('Consolas', 12, 'bold'),
            fg='#e74c3c', bg=self.colors['bg'], width=5
        )
        self.vacuum_status.pack(pady=5)

        vac_btns = tk.Frame(vacuum_frame, bg=self.colors['bg'])
        vac_btns.pack(pady=5)

        tk.Button(
            vac_btns, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg='#27ae60', fg='white', width=5,
            command=lambda: self._set_relay('vacuum', True),
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            vac_btns, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg='#e74c3c', fg='white', width=5,
            command=lambda: self._set_relay('vacuum', False),
            cursor='hand2'
        ).pack(side='left', padx=3)

        # Solenoid
        solenoid_frame = tk.LabelFrame(
            relay_row, text="Solenoid",
            font=('Segoe UI', 9, 'bold'),
            fg='#e67e22', bg=self.colors['bg']
        )
        solenoid_frame.pack(side='left', padx=10, pady=5)

        self.solenoid_status = tk.Label(
            solenoid_frame, text="OFF",
            font=('Consolas', 12, 'bold'),
            fg='#e74c3c', bg=self.colors['bg'], width=5
        )
        self.solenoid_status.pack(pady=5)

        sol_btns = tk.Frame(solenoid_frame, bg=self.colors['bg'])
        sol_btns.pack(pady=5)

        tk.Button(
            sol_btns, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg='#27ae60', fg='white', width=5,
            command=lambda: self._set_relay('solenoid', True),
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            sol_btns, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg='#e74c3c', fg='white', width=5,
            command=lambda: self._set_relay('solenoid', False),
            cursor='hand2'
        ).pack(side='left', padx=3)

        # Quick actions
        quick_frame = tk.LabelFrame(
            relay_row, text="Quick Actions",
            font=('Segoe UI', 9, 'bold'),
            fg='#e67e22', bg=self.colors['bg']
        )
        quick_frame.pack(side='left', padx=10, pady=5)

        tk.Button(
            quick_frame, text="GRAB",
            font=('Segoe UI', 11, 'bold'),
            bg='#27ae60', fg='white', width=8,
            command=lambda: self._vacuum_action('pick'),
            cursor='hand2'
        ).pack(pady=3, padx=5)

        tk.Button(
            quick_frame, text="RELEASE",
            font=('Segoe UI', 11, 'bold'),
            bg='#e74c3c', fg='white', width=8,
            command=lambda: self._vacuum_action('drop'),
            cursor='hand2'
        ).pack(pady=3, padx=5)

        # SAVE button (prominent, cyan like reference)
        tk.Button(
            self.servo_settings_frame,
            text="SAVE",
            font=('Segoe UI', 12, 'bold'),
            bg='#00bcd4', fg='white',
            width=15, height=1,
            command=self._save_servo_settings,
            cursor='hand2'
        ).pack(pady=10)

    def _adjust_servo_setting(self, joint, setting_type, delta):
        """Adjust servo setting by delta amount."""
        # Safety check
        if joint < 0 or joint >= 8:
            return

        try:
            if setting_type == 'min':
                self.servo_min[joint] = max(0, min(180, self.servo_min[joint] + delta))
                if joint < len(self.min_labels):
                    self.min_labels[joint].config(text=str(self.servo_min[joint]))
                self._send_servo_setting(joint, 'min', self.servo_min[joint])
            elif setting_type == 'max':
                self.servo_max[joint] = max(0, min(180, self.servo_max[joint] + delta))
                if joint < len(self.max_labels):
                    self.max_labels[joint].config(text=str(self.servo_max[joint]))
                self._send_servo_setting(joint, 'max', self.servo_max[joint])
            elif setting_type == 'trim':
                self.servo_trim[joint] = max(-50, min(50, self.servo_trim[joint] + delta))
                v = self.servo_trim[joint]
                if joint < len(self.trim_labels):
                    self.trim_labels[joint].config(text=f"{'+' if v >= 0 else ''}{v}")
                self._send_servo_setting(joint, 'trim', self.servo_trim[joint])
            elif setting_type == 'expo':
                self.servo_expo[joint] = max(-100, min(100, self.servo_expo[joint] + delta))
                if joint < len(self.expo_labels):
                    self.expo_labels[joint].config(text=f"{self.servo_expo[joint]}%")
                self._send_servo_setting(joint, 'expo', self.servo_expo[joint])
        except (tk.TclError, IndexError):
            pass  # UI element not ready

    def _test_servo(self, joint, angle):
        """Move servo to test angle."""
        if not self.connected:
            return

        # Safety check - ensure UI is initialized
        if joint < 0 or joint >= len(self.angle_labels):
            return

        try:
            self.angle_labels[joint].config(text=f"{angle}°")
        except (tk.TclError, IndexError):
            return

        # Debounce rapid slider movements
        timer_key = f'_test_servo_{joint}_timer'
        try:
            if hasattr(self, timer_key) and getattr(self, timer_key):
                self.frame.after_cancel(getattr(self, timer_key))
        except (tk.TclError, ValueError):
            pass  # Timer already expired or invalid

        # Direct servo move - set absolute angle using channel command
        def send_direct():
            try:
                joint_key = self.channel_cmds[joint] if joint < len(self.channel_cmds) else str(joint)
                requests.post(
                    f"{self.danielson_url}/api/arm/set",
                    json={"cmd": joint_key, "angle": angle},
                    timeout=3
                )
            except Exception:
                pass

        try:
            setattr(self, timer_key, self.frame.after(50, lambda: threading.Thread(
                target=send_direct, daemon=True
            ).start()))
        except tk.TclError:
            pass  # Frame destroyed

    def _toggle_servo_settings(self):
        """Toggle servo settings visibility."""
        self.servo_settings_visible = not self.servo_settings_visible
        if self.servo_settings_visible:
            self.servo_toggle_btn.config(text="▼ Servo Settings")
            self.servo_settings_frame.pack(fill='x', padx=5, pady=5)
        else:
            self.servo_toggle_btn.config(text="▶ Servo Settings")
            self.servo_settings_frame.pack_forget()

    def _send_servo_setting(self, joint, setting_type, value):
        """Send servo setting to ESP32 via DANIELSON."""
        if not self.connected:
            return

        # Debounce
        timer_key = f'_servo_{joint}_{setting_type}_timer'
        try:
            if hasattr(self, timer_key) and getattr(self, timer_key):
                self.frame.after_cancel(getattr(self, timer_key))
        except (tk.TclError, ValueError):
            pass  # Timer already expired or invalid

        def send():
            try:
                joint_key = self.joint_cmds[joint] if joint < len(self.joint_cmds) else str(joint)
                requests.post(
                    f"{self.danielson_url}/api/arm/servo/setting",
                    json={"joint": joint_key, "index": joint, "type": setting_type, "value": value},
                    timeout=5
                )
            except Exception:
                pass

        try:
            setattr(self, timer_key, self.frame.after(150, lambda: threading.Thread(
                target=send, daemon=True
            ).start()))
        except tk.TclError:
            pass  # Frame destroyed

    def _save_servo_settings(self):
        """Save all servo settings to ESP32 EEPROM."""
        if not self.connected:
            return

        def save():
            try:
                settings = {
                    "trim": self.servo_trim,
                    "min": self.servo_min,
                    "max": self.servo_max,
                    "expo": self.servo_expo
                }
                r = requests.post(
                    f"{self.danielson_url}/api/arm/servo/save",
                    json=settings,
                    timeout=10
                )
                if r.status_code == 200:
                    self._schedule_ui(lambda: self._log_status("Servo settings saved"))
            except Exception as e:
                self._schedule_ui(lambda err=e: self._log_status(f"Save error: {err}"))

        threading.Thread(target=save, daemon=True).start()

    # ============== Stepper Control Methods ==============

    def _jog_stepper(self, stepper_idx, steps):
        """Jog stepper motor by specified steps."""
        print(f"[STEPPER] _jog_stepper called: idx={stepper_idx}, steps={steps}, connected={self.connected}")
        if not self.connected:
            print("[STEPPER] Not connected, returning")
            return

        stepper_cmds = ['base']
        if stepper_idx >= len(stepper_cmds):
            print(f"[STEPPER] Invalid index {stepper_idx}")
            return

        def jog():
            try:
                # Send to ESP32 via telnet or DANIELSON API
                cmd = stepper_cmds[stepper_idx]
                url = f"{self.danielson_url}/api/stepper/jog"
                print(f"[STEPPER] POST {url} -> steps={steps}")
                r = requests.post(
                    url,
                    json={"steps": steps},
                    timeout=5
                )
                print(f"[STEPPER] Response: {r.status_code} - {r.text}")
                if r.status_code == 200:
                    # Server doesn't return position, track client-side
                    current = int(self.stepper_pos_labels[stepper_idx].cget('text')) if stepper_idx < len(self.stepper_pos_labels) else 0
                    pos = current + steps
                    self._schedule_ui(lambda p=pos: self._update_stepper_pos(stepper_idx, p))
            except Exception as e:
                print(f"[STEPPER] Exception: {e}")

        threading.Thread(target=jog, daemon=True).start()

    def _home_stepper(self, stepper_idx):
        """Home stepper motor."""
        if not self.connected:
            return

        stepper_cmds = ['base']
        if stepper_idx >= len(stepper_cmds):
            return

        def home():
            try:
                cmd = stepper_cmds[stepper_idx]
                r = requests.post(
                    f"{self.danielson_url}/api/stepper/home",
                    json={"stepper": cmd},
                    timeout=10
                )
                if r.status_code == 200:
                    self._schedule_ui(lambda: self._update_stepper_pos(stepper_idx, 0))
            except Exception:
                pass

        threading.Thread(target=home, daemon=True).start()

    def _set_stepper_speed(self, stepper_idx, speed):
        """Set stepper motor speed."""
        if stepper_idx < len(self.stepper_speed_labels):
            self.stepper_speed_labels[stepper_idx].config(text=str(speed))

    def _update_stepper_pos(self, stepper_idx, pos):
        """Update stepper position display."""
        if stepper_idx < len(self.stepper_pos_labels):
            self.stepper_pos_labels[stepper_idx].config(text=str(pos))

    def _on_stepper_angle_change(self, stepper_idx, angle):
        """Handle angle slider change - updates label only (doesn't send yet)."""
        if stepper_idx < len(self.stepper_angle_labels):
            self.stepper_angle_labels[stepper_idx].config(text=f"{angle}°")
            self.stepper_angles[stepper_idx] = angle

    def _send_stepper_angle(self, stepper_idx):
        """Send stepper angle command to server."""
        if not self.connected:
            print("[STEPPER] Not connected")
            return

        angle = self.stepper_angles[stepper_idx]
        motor = stepper_idx + 1  # API uses 1=base, 2=shoulder
        print(f"[STEPPER] Sending angle: motor={motor}, angle={angle}")

        def send():
            try:
                url = f"{self.danielson_url}/api/stepper/angle"
                r = requests.post(
                    url,
                    json={"motor": motor, "angle": angle},
                    timeout=10
                )
                print(f"[STEPPER] Response: {r.status_code} - {r.text}")
                if r.status_code == 200:
                    self._schedule_ui(lambda a=angle: self._update_stepper_pos(stepper_idx, a))
            except Exception as e:
                print(f"[STEPPER] Exception: {e}")

        threading.Thread(target=send, daemon=True).start()

    def _set_stepper_angle_live(self, stepper_idx, angle):
        """Set stepper angle with live updates (called on slider release or with debounce)."""
        if not self.connected:
            return

        # Update display
        if stepper_idx < len(self.stepper_angle_labels):
            self.stepper_angle_labels[stepper_idx].config(text=f"{angle}°")
            self.stepper_angles[stepper_idx] = angle

        motor = stepper_idx + 1

        def send():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/stepper/angle",
                    json={"motor": motor, "angle": angle},
                    timeout=10
                )
                if r.status_code == 200:
                    self._schedule_ui(lambda: self._update_stepper_pos(stepper_idx, angle))
            except Exception:
                pass

        threading.Thread(target=send, daemon=True).start()

    # ============== Relay Control Methods ==============

    def _set_relay(self, relay_type, state):
        """Set relay state (vacuum or solenoid)."""
        if not self.connected:
            return

        def set_state():
            try:
                if relay_type == 'vacuum':
                    cmd = "vacuum on" if state else "vacuum off"
                    endpoint = "/api/vacuum/on" if state else "/api/vacuum/off"
                else:
                    cmd = "solenoid on" if state else "solenoid off"
                    endpoint = "/api/solenoid/on" if state else "/api/solenoid/off"

                r = requests.post(
                    f"{self.danielson_url}{endpoint}",
                    timeout=5
                )
                if r.status_code == 200:
                    self._schedule_ui(lambda: self._update_relay_status(relay_type, state))
            except Exception:
                pass

        threading.Thread(target=set_state, daemon=True).start()

    def _update_relay_status(self, relay_type, state):
        """Update relay status display."""
        status_text = "ON" if state else "OFF"
        status_color = '#27ae60' if state else '#e74c3c'

        try:
            if relay_type == 'vacuum' and self.vacuum_status:
                self.vacuum_status.config(text=status_text, fg=status_color)
            elif relay_type != 'vacuum' and self.solenoid_status:
                self.solenoid_status.config(text=status_text, fg=status_color)
        except (tk.TclError, AttributeError):
            pass

    def _vacuum_action(self, action):
        """Perform vacuum pick or drop action."""
        if not self.connected:
            return

        def do_action():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/vacuum/{action}",
                    timeout=5
                )
                if r.status_code == 200:
                    if action == 'pick':
                        self._schedule_ui(lambda: self._update_relay_status('vacuum', True))
                        self._schedule_ui(lambda: self._update_relay_status('solenoid', False))
                    elif action == 'drop':
                        self._schedule_ui(lambda: self._update_relay_status('vacuum', False))
                        self._schedule_ui(lambda: self._update_relay_status('solenoid', False))
            except Exception:
                pass

        threading.Thread(target=do_action, daemon=True).start()

    def _load_servo_settings(self):
        """Load servo settings from ESP32."""
        if not self.connected:
            return

        def load():
            try:
                r = requests.get(
                    f"{self.danielson_url}/api/arm/servo/settings",
                    timeout=5
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get('success'):
                        settings = data.get('settings', {})
                        self._schedule_ui(lambda: self._apply_servo_settings(settings))
                        self._schedule_ui(lambda: self._log_status("Settings loaded"))
            except Exception as e:
                self._schedule_ui(lambda err=e: self._log_status(f"Load error: {err}"))

        threading.Thread(target=load, daemon=True).start()

    def _apply_servo_settings(self, settings):
        """Apply loaded settings to UI."""
        try:
            if 'trim' in settings:
                for i, v in enumerate(settings['trim'][:8]):
                    self.servo_trim[i] = v
                    if i < len(self.trim_labels):
                        self.trim_labels[i].config(text=f"{'+' if v >= 0 else ''}{v}")
            if 'min' in settings:
                for i, v in enumerate(settings['min'][:8]):
                    self.servo_min[i] = v
                    if i < len(self.min_labels):
                        self.min_labels[i].config(text=str(v))
            if 'max' in settings:
                for i, v in enumerate(settings['max'][:8]):
                    self.servo_max[i] = v
                    if i < len(self.max_labels):
                        self.max_labels[i].config(text=str(v))
            if 'expo' in settings:
                for i, v in enumerate(settings['expo'][:8]):
                    self.servo_expo[i] = v
                    if i < len(self.expo_labels):
                        self.expo_labels[i].config(text=f"{v}%")
        except (tk.TclError, IndexError):
            pass  # UI not ready

    def _reset_servo_settings(self):
        """Reset all servo settings to defaults."""
        try:
            for i in range(8):
                self.servo_trim[i] = 0
                self.servo_min[i] = 0
                self.servo_max[i] = 180
                self.servo_expo[i] = 30  # Default expo
                if i < len(self.trim_labels):
                    self.trim_labels[i].config(text="+0")
                if i < len(self.min_labels):
                    self.min_labels[i].config(text="0")
                if i < len(self.max_labels):
                    self.max_labels[i].config(text="180")
                if i < len(self.expo_labels):
                    self.expo_labels[i].config(text="30%")
                if i < len(self.test_scales):
                    self.test_scales[i].set(90)
                if i < len(self.angle_labels):
                    self.angle_labels[i].config(text="90°")
            self._log_status("Settings reset to defaults")
        except (tk.TclError, IndexError):
            pass  # UI not ready

    def _create_vacuum_fan_controls(self, parent, row=0, col=0, colspan=1):
        """Vacuum solenoid and fan controls."""
        frame = tk.LabelFrame(
            parent,
            text="Vacuum/Fan",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=2, pady=2)

        # Vacuum controls
        vac_frame = tk.Frame(frame, bg=self.colors['surface'])
        vac_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(
            vac_frame, text="Vacuum:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(side='left')

        tk.Button(
            vac_frame, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white', width=5,
            command=lambda: self._set_vacuum(True),
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            vac_frame, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white', width=5,
            command=lambda: self._set_vacuum(False),
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            vac_frame, text="Pulse",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['warning'], fg='black', width=6,
            command=self._pulse_vacuum,
            cursor='hand2'
        ).pack(side='left', padx=3)

        # Solenoid controls
        sol_frame = tk.Frame(frame, bg=self.colors['surface'])
        sol_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(
            sol_frame, text="Solenoid:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(side='left')

        tk.Button(
            sol_frame, text="ON",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white', width=5,
            command=lambda: self._set_solenoid(True),
            cursor='hand2'
        ).pack(side='left', padx=3)

        tk.Button(
            sol_frame, text="OFF",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white', width=5,
            command=lambda: self._set_solenoid(False),
            cursor='hand2'
        ).pack(side='left', padx=3)

        # Fan controls
        fan_frame = tk.Frame(frame, bg=self.colors['surface'])
        fan_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(
            fan_frame, text="Fan:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        ).pack(side='left')

        self.fan_var = tk.IntVar(value=0)
        self.fan_scale = tk.Scale(
            fan_frame,
            from_=0, to=255,
            orient='horizontal',
            variable=self.fan_var,
            bg=self.colors['surface'],
            fg=self.colors['text'],
            highlightthickness=0,
            length=120,
            command=self._on_fan_change
        )
        self.fan_scale.pack(side='left', padx=5, fill='x', expand=True)

        tk.Button(
            fan_frame, text="MAX",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['accent'], fg='white', width=4,
            command=lambda: self._set_fan(255),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            fan_frame, text="OFF",
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['bg'], fg=self.colors['text'], width=4,
            command=lambda: self._set_fan(0),
            cursor='hand2'
        ).pack(side='left', padx=2)

    # ============== Connection Methods ==============

    def _check_connection(self):
        """Check DANIELSON connection."""
        def check():
            try:
                r = requests.get(f"{self.danielson_url}/status", timeout=3)
                if r.status_code == 200:
                    self.connected = True
                    data = r.json()
                    coral = 'TPU' if data.get('coral_loaded') else 'CPU'
                    status_text = f"DANIELSON: ON ({coral})"
                    color = self.colors['success']
                else:
                    self.connected = False
                    status_text = "DANIELSON: ERROR"
                    color = self.colors['error']
            except Exception:
                self.connected = False
                status_text = "DANIELSON: OFFLINE"
                color = self.colors['error']

            self._schedule_ui(
                lambda: self.status_label.config(text=status_text, fg=color)
            )

        threading.Thread(target=check, daemon=True).start()

    def _log_status(self, message):
        """Update status label temporarily."""
        self.status_label.config(text=message)

    # ============== Focus Methods ==============

    def _on_focus_change(self, value):
        """Handle focus slider change."""
        self.focus_label.config(text=f"{float(value):.1f}")

    def _test_focus(self):
        """Take a test shot with current focus."""
        if not self.connected:
            return

        focus_val = self.focus_var.get()

        def test():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/focus/test",
                    json={"position": focus_val},
                    timeout=15
                )
                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        sharpness = result.get('sharpness', 0)
                        self._schedule_ui(lambda: self._log_status(
                            f"Focus test: sharpness={sharpness:.1f}"
                        ))
            except Exception as e:
                self._schedule_ui(lambda err=e: self._log_status(f"Error: {err}"))

        threading.Thread(target=test, daemon=True).start()

    def _autofocus(self):
        """Run autofocus."""
        if not self.connected:
            return

        self._log_status("Running autofocus...")

        def autofocus():
            try:
                # Use /api/capture with autofocus=True
                r = requests.post(
                    f"{self.danielson_url}/api/capture",
                    json={"autofocus": True},
                    timeout=20
                )
                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        self._schedule_ui(lambda: self._log_status("Autofocus complete"))
            except Exception as e:
                self._schedule_ui(lambda err=e: self._log_status(f"Error: {err}"))

        threading.Thread(target=autofocus, daemon=True).start()

    def _calibrate_focus(self):
        """Run focus calibration."""
        if not self.connected:
            return

        self._log_status("Calibrating focus (~30s)...")

        def calibrate():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/focus/calibrate",
                    timeout=60
                )
                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        best_pos = result.get('best_position', 9.0)
                        self._schedule_ui(lambda: self.focus_var.set(best_pos))
                        self._schedule_ui(
                            lambda: self.focus_label.config(text=f"{best_pos:.1f}")
                        )
                        self._schedule_ui(
                            lambda: self._log_status(f"Best focus: {best_pos}")
                        )
            except Exception as e:
                self._schedule_ui(lambda err=e: self._log_status(f"Error: {err}"))

        threading.Thread(target=calibrate, daemon=True).start()

    # ============== Light Methods ==============

    def _set_lights(self, state):
        """Control all lights on/off."""
        if not self.connected:
            return

        def set_light():
            try:
                endpoint = "on" if state == "on" else "off"
                requests.post(
                    f"{self.danielson_url}/api/lights/{endpoint}",
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=set_light, daemon=True).start()

    def _set_lights_rgb(self, r, g, b):
        """Set all lights to RGB color."""
        if not self.connected:
            return

        def set_color():
            try:
                requests.post(
                    f"{self.danielson_url}/api/lights/rgb",
                    json={"r": r, "g": g, "b": b},
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=set_color, daemon=True).start()

    def _set_ch_color(self, ch, r, g, b):
        """Set individual LED channel to RGB color."""
        if not self.connected:
            return

        def set_ch():
            try:
                requests.post(
                    f"{self.danielson_url}/api/lights/ch/{ch}",
                    json={"r": r, "g": g, "b": b},
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=set_ch, daemon=True).start()

    def _on_brightness_change(self, value):
        """Handle brightness slider change."""
        self.bright_label.config(text=str(int(float(value))))

        if not self.connected:
            return

        # Debounce
        if hasattr(self, '_brightness_timer') and self._brightness_timer:
            self.frame.after_cancel(self._brightness_timer)

        def set_brightness():
            try:
                requests.post(
                    f"{self.danielson_url}/api/lights/brightness",
                    json={"brightness": int(float(value))},
                    timeout=5
                )
            except Exception:
                pass

        self._brightness_timer = self.frame.after(100, lambda: threading.Thread(
            target=set_brightness, daemon=True
        ).start())

    def _set_led_mode(self, mode):
        """Set LED scan mode via Light ESP32 presets."""
        if not self.connected:
            return

        # Map UI modes to firmware presets
        mode_to_preset = {"flat": "scan", "surface": "photo", "foil": "grade"}
        preset = mode_to_preset.get(mode, "scan")

        def set_mode():
            try:
                requests.post(
                    f"{self.danielson_url}/api/lights/preset",
                    json={"preset": preset},
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=set_mode, daemon=True).start()

    # ============== Lightbox Methods (ARM ESP32 bottom light) ==============

    def _set_lightbox(self, state):
        """Control lightbox on/off."""
        if not self.connected:
            return

        def set_lb():
            try:
                if state == 'on':
                    r = self.lightbox_r.get()
                    g = self.lightbox_g.get()
                    b = self.lightbox_b.get()
                    requests.post(
                        f"{self.danielson_url}/api/arm/set",
                        json={"cmd": "lightbox", "r": r, "g": g, "b": b},
                        timeout=5
                    )
                else:
                    requests.post(
                        f"{self.danielson_url}/api/arm/set",
                        json={"cmd": "lightbox", "r": 0, "g": 0, "b": 0},
                        timeout=5
                    )
            except Exception:
                pass

        threading.Thread(target=set_lb, daemon=True).start()

    def _set_lightbox_rgb(self, r, g, b):
        """Set lightbox RGB color."""
        if not self.connected:
            return

        def set_color():
            try:
                requests.post(
                    f"{self.danielson_url}/api/arm/set",
                    json={"cmd": "lightbox", "r": r, "g": g, "b": b},
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=set_color, daemon=True).start()

    # ============== Demo Recording Methods ==============

    def _save_arm_demo(self):
        """Save current arm position + camera frame as training demo."""
        name = self.demo_name_entry.get().strip() or "demo"
        self.demo_status_label.config(text="Saving...")

        def save():
            try:
                import json
                import os
                from datetime import datetime

                # Get arm position
                angles = []
                try:
                    r = requests.get(f"{self.danielson_url}/api/arm/position", timeout=2)
                    if r.status_code == 200:
                        angles = r.json().get("angles", [])[:8]
                except Exception:
                    pass

                # Get camera frame via snapshot (DANIELSON :5001)
                frame = None
                try:
                    r = requests.get(f"{self.danielson_url}/api/snapshot?camera=owleye", timeout=5)
                    if r.status_code == 200:
                        frame = r.content
                except Exception:
                    pass

                # Card detection not available via standalone endpoint
                card = None

                # Save demo
                demo_dir = os.path.join(os.path.dirname(__file__), "..", "..", "ai", "robot_simulation", "demos")
                os.makedirs(demo_dir, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                demo_name = f"{name}_{timestamp}"

                if frame:
                    with open(os.path.join(demo_dir, f"{demo_name}.jpg"), "wb") as f:
                        f.write(frame)

                meta = {
                    "name": name,
                    "timestamp": timestamp,
                    "arm_angles": angles,
                    "card_detection": card
                }
                with open(os.path.join(demo_dir, f"{demo_name}.json"), "w") as f:
                    json.dump(meta, f, indent=2)

                self._schedule_ui(lambda: self.demo_status_label.config(text=f"Saved: {demo_name}"))

            except Exception as e:
                self._schedule_ui(lambda: self.demo_status_label.config(text=f"Error: {e}"))

        threading.Thread(target=save, daemon=True).start()

    def _open_vision_stream(self):
        """Open vision camera stream in browser."""
        import webbrowser
        vision_url = "http://192.168.1.219:5002/api/vision/stream"
        webbrowser.open(vision_url)
        self.demo_status_label.config(text="Opening camera...")

    # ============== Arm Methods ==============

    def _jog_joint(self, joint, degrees):
        """Jog a single joint by degrees."""
        if not self.connected:
            return

        # joint_cmds: ["shoulder", "wrist", "elbow"]
        cmd = self.joint_cmds[joint]

        def jog():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/arm/jog",
                    json={"cmd": cmd, "degrees": degrees},
                    timeout=5
                )
                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        angles = result.get('angles', {})
                        self._schedule_ui(lambda: self._update_joint_display(angles))
            except Exception:
                pass

        threading.Thread(target=jog, daemon=True).start()

    def _update_joint_display(self, angles):
        """Update joint angle display and sliders."""
        if isinstance(angles, dict):
            for i, cmd in enumerate(self.joint_cmds):
                angle = angles.get(cmd, 90)
                if i < len(self.joint_labels):
                    self.joint_labels[i].config(text=f"{angle}°")
                if hasattr(self, 'joint_vars') and i < len(self.joint_vars):
                    self.joint_vars[i].set(int(angle))
            # Update base stepper display if present
            if 'base' in angles and hasattr(self, 'stepper_pos_labels') and self.stepper_pos_labels:
                self.stepper_pos_labels[0].config(text=str(angles['base']))

    def _on_joint_slider(self, joint, angle):
        """Handle slider change - set joint to absolute position."""
        logger.info(f"[SLIDER] joint={joint} angle={angle} connected={self.connected}")
        print(f"[SLIDER] joint={joint} angle={angle} connected={self.connected}", flush=True)
        if not self.connected:
            return

        # Update label immediately
        if joint < len(self.joint_labels):
            self.joint_labels[joint].config(text=f"{angle}°")

        # joint_cmds: ["shoulder", "wrist", "elbow"]
        cmd = self.joint_cmds[joint]

        # Send command to hardware
        def set_angle():
            try:
                url = f"{self.danielson_url}/api/arm/set"
                payload = {"cmd": cmd, "angle": angle}
                print(f"[ARM] POST {url} {payload}", flush=True)
                r = requests.post(url, json=payload, timeout=5)
                print(f"[ARM] Response: {r.status_code} {r.text[:100]}", flush=True)
            except Exception as e:
                print(f"[ARM] ERROR: {e}", flush=True)

        threading.Thread(target=set_angle, daemon=True).start()

    def _goto_preset(self, position):
        """Move arm to preset position."""
        if not self.connected:
            return

        def goto():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/arm/preset",
                    json={"position": position},
                    timeout=10
                )
                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        angles = result.get('angles', [])
                        self._schedule_ui(lambda: self._update_joint_display(angles))
            except Exception:
                pass

        threading.Thread(target=goto, daemon=True).start()

    def _save_preset(self):
        """Save current arm position as a named preset on DANIELSON."""
        if not self.connected:
            return

        name = self.preset_name_var.get().strip().lower()
        if not name:
            return

        self.save_status_label.config(text="Saving...", fg=self.colors['text_dim'])

        def save():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/arm/preset/save",
                    json={"name": name},
                    timeout=5
                )
                if r.status_code == 200 and r.json().get('success'):
                    angles = r.json().get('angles', {})
                    msg = f"Saved '{name}'"
                    self._schedule_ui(
                        lambda: self.save_status_label.config(text=msg, fg='#27ae60'))
                else:
                    self._schedule_ui(
                        lambda: self.save_status_label.config(text="Failed", fg='#e74c3c'))
            except Exception:
                self._schedule_ui(
                    lambda: self.save_status_label.config(text="Error", fg='#e74c3c'))

        threading.Thread(target=save, daemon=True).start()

    # ============== Vacuum Methods ==============

    def _set_vacuum(self, on):
        """Control vacuum pump + solenoid together (coordinated). Fixed 3/4/2026."""
        if not self.connected:
            return

        def set_vac():
            try:
                endpoint = "/api/vacuum/on" if on else "/api/vacuum/off"
                requests.post(f"{self.danielson_url}{endpoint}", timeout=5)
                self._schedule_ui(lambda: self._update_relay_status("vacuum", on))
            except Exception:
                pass

        threading.Thread(target=set_vac, daemon=True).start()



    def _pulse_vacuum(self):
        """Pulse vacuum for pickup."""
        if not self.connected:
            return

        def pulse():
            try:
                requests.post(
                    f"{self.danielson_url}/api/vacuum",
                    json={"pulse": 500},
                    timeout=5
                )
            except Exception:
                pass

        threading.Thread(target=pulse, daemon=True).start()

    def _set_solenoid(self, on):
        """Control solenoid valve."""
        if not self.connected:
            return

        def set_sol():
            try:
                endpoint = "/api/solenoid/on" if on else "/api/solenoid/off"
                requests.post(f"{self.danielson_url}{endpoint}", timeout=5)
            except Exception:
                pass

        threading.Thread(target=set_sol, daemon=True).start()

    # ============== Fan Methods ==============

    def _on_fan_change(self, value):
        """Handle fan slider change."""
        self._set_fan(int(float(value)))

    def _set_fan(self, speed):
        """Set fan speed."""
        if not self.connected:
            return

        self.fan_var.set(speed)

        # Debounce
        if hasattr(self, '_fan_timer') and self._fan_timer:
            self.frame.after_cancel(self._fan_timer)

        def set_fan():
            try:
                requests.post(
                    f"{self.danielson_url}/api/fan",
                    json={"speed": speed},
                    timeout=5
                )
            except Exception:
                pass

        self._fan_timer = self.frame.after(100, lambda: threading.Thread(
            target=set_fan, daemon=True
        ).start())

    # ============== System Stats Methods ==============

    def _create_combined_system_stats(self, parent, row=0, col=0, colspan=1):
        """DANIELSON system stats panel."""
        frame = tk.LabelFrame(
            parent,
            text="DANIELSON Stats",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=2, pady=2)

        inner = tk.Frame(frame, bg=self.colors['surface'])
        inner.pack(fill='both', expand=True, padx=5, pady=5)

        for attr_prefix, label_text in [('cpu', 'CPU'), ('mem', 'Mem'), ('disk', 'Disk')]:
            row_f = tk.Frame(inner, bg=self.colors['surface'])
            row_f.pack(fill='x', pady=1)
            tk.Label(row_f, text=f"{label_text}:", font=('Segoe UI', 9),
                     fg=self.colors['text_dim'], bg=self.colors['surface'],
                     width=5, anchor='w').pack(side='left')
            bar = tk.Canvas(row_f, width=120, height=12, bg='#333333',
                           highlightthickness=1, highlightbackground=self.colors['text_dim'])
            bar.pack(side='left', padx=3)
            setattr(self, f'{attr_prefix}_bar', bar)
            lbl = tk.Label(row_f, text="--%", font=('Consolas', 9),
                          fg=self.colors['text'], bg=self.colors['surface'], width=14)
            lbl.pack(side='left')
            setattr(self, f'{attr_prefix}_label', lbl)

        temp_row = tk.Frame(inner, bg=self.colors['surface'])
        temp_row.pack(fill='x', pady=1)
        self.temp_label = tk.Label(temp_row, text="--\u00b0C", font=('Consolas', 10, 'bold'),
                                   fg=self.colors['text'], bg=self.colors['surface'])
        self.temp_label.pack(side='left')
        self.uptime_label = tk.Label(temp_row, text="Up: --", font=('Consolas', 8),
                                      fg=self.colors['text_dim'], bg=self.colors['surface'])
        self.uptime_label.pack(side='right')

        # Start polling
        self._stats_polling = True
        self._poll_system_stats()

    def _create_system_stats(self, parent, row=0, col=0, colspan=1):
        """Create system stats monitoring panel (legacy - use _create_combined_system_stats)."""
        frame = tk.LabelFrame(
            parent,
            text="DANIELSON Stats",
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['accent'],
            bg=self.colors['surface']
        )
        frame.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=2, pady=2)

        # Stats grid
        stats_frame = tk.Frame(frame, bg=self.colors['surface'])
        stats_frame.pack(fill='x', padx=10, pady=5)

        # CPU row
        cpu_row = tk.Frame(stats_frame, bg=self.colors['surface'])
        cpu_row.pack(fill='x', pady=2)

        tk.Label(
            cpu_row, text="CPU:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface'], width=8, anchor='w'
        ).pack(side='left')

        self.cpu_bar = tk.Canvas(
            cpu_row, width=120, height=16,
            bg='#333333', highlightthickness=1,
            highlightbackground=self.colors['text_dim']
        )
        self.cpu_bar.pack(side='left', padx=5)

        self.cpu_label = tk.Label(
            cpu_row, text="--%",
            font=('Consolas', 10, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface'], width=6
        )
        self.cpu_label.pack(side='left')

        # Memory row
        mem_row = tk.Frame(stats_frame, bg=self.colors['surface'])
        mem_row.pack(fill='x', pady=2)

        tk.Label(
            mem_row, text="Memory:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface'], width=8, anchor='w'
        ).pack(side='left')

        self.mem_bar = tk.Canvas(
            mem_row, width=120, height=16,
            bg='#333333', highlightthickness=1,
            highlightbackground=self.colors['text_dim']
        )
        self.mem_bar.pack(side='left', padx=5)

        self.mem_label = tk.Label(
            mem_row, text="--% (--MB)",
            font=('Consolas', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'], width=14
        )
        self.mem_label.pack(side='left')

        # Disk row
        disk_row = tk.Frame(stats_frame, bg=self.colors['surface'])
        disk_row.pack(fill='x', pady=2)

        tk.Label(
            disk_row, text="Disk:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface'], width=8, anchor='w'
        ).pack(side='left')

        self.disk_bar = tk.Canvas(
            disk_row, width=120, height=16,
            bg='#333333', highlightthickness=1,
            highlightbackground=self.colors['text_dim']
        )
        self.disk_bar.pack(side='left', padx=5)

        self.disk_label = tk.Label(
            disk_row, text="--% (--GB)",
            font=('Consolas', 10),
            fg=self.colors['text'],
            bg=self.colors['surface'], width=14
        )
        self.disk_label.pack(side='left')

        # Temp row
        temp_row = tk.Frame(stats_frame, bg=self.colors['surface'])
        temp_row.pack(fill='x', pady=2)

        tk.Label(
            temp_row, text="Temp:",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'],
            bg=self.colors['surface'], width=8, anchor='w'
        ).pack(side='left')

        self.temp_label = tk.Label(
            temp_row, text="--°C",
            font=('Consolas', 12, 'bold'),
            fg=self.colors['text'],
            bg=self.colors['surface'], width=6
        )
        self.temp_label.pack(side='left', padx=5)

        self.uptime_label = tk.Label(
            temp_row, text="Uptime: --",
            font=('Consolas', 9),
            fg=self.colors['text_dim'],
            bg=self.colors['surface']
        )
        self.uptime_label.pack(side='right', padx=5)

        # Start polling
        self._stats_polling = True
        self._poll_system_stats()

    def _poll_system_stats(self):
        """Poll system stats from DANIELSON."""
        if not self._stats_polling:
            return

        def fetch():
            if not self.connected:
                return None

            try:
                r = requests.get(
                    f"{self.danielson_url}/api/system/stats",
                    timeout=3
                )
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            return None

        def on_complete(stats):
            if stats:
                self._update_stats_display(stats)
            # Schedule next poll from main thread (check widget exists first)
            try:
                if self._stats_polling and self.frame.winfo_exists():
                    self.frame.after(3000, self._poll_system_stats)
            except tk.TclError:
                # Widget destroyed, stop polling
                self._stats_polling = False

        def run_fetch():
            stats = fetch()
            # Schedule UI update via thread-safe queue
            self._schedule_ui(lambda: on_complete(stats))

        threading.Thread(target=run_fetch, daemon=True).start()

    def _update_stats_display(self, stats):
        """Update system stats UI."""
        # CPU
        cpu = stats.get('cpu_percent')
        if cpu is not None:
            self.cpu_label.config(text=f"{cpu:.0f}%")
            self._draw_bar(self.cpu_bar, cpu, self._get_load_color(cpu))
        else:
            self.cpu_label.config(text="--%")

        # Memory
        mem = stats.get('memory_percent')
        mem_used = stats.get('memory_used_mb')
        if mem is not None:
            if mem_used:
                self.mem_label.config(text=f"{mem:.0f}% ({mem_used}MB)")
            else:
                self.mem_label.config(text=f"{mem:.0f}%")
            self._draw_bar(self.mem_bar, mem, self._get_load_color(mem))
        else:
            self.mem_label.config(text="--% (--MB)")

        # Disk
        disk = stats.get('disk_percent')
        disk_used = stats.get('disk_used_gb')
        if disk is not None:
            if disk_used:
                self.disk_label.config(text=f"{disk:.0f}% ({disk_used}GB)")
            else:
                self.disk_label.config(text=f"{disk:.0f}%")
            self._draw_bar(self.disk_bar, disk, self._get_load_color(disk))
        else:
            self.disk_label.config(text="--% (--GB)")

        # Temperature
        temp = stats.get('temperature')
        if temp is not None:
            color = self._get_temp_color(temp)
            self.temp_label.config(text=f"{temp:.1f}°C", fg=color)
        else:
            self.temp_label.config(text="--°C", fg=self.colors['text'])

        # Uptime
        uptime = stats.get('uptime')
        if uptime is not None:
            hours = uptime // 3600
            mins = (uptime % 3600) // 60
            if hours > 24:
                days = hours // 24
                hours = hours % 24
                self.uptime_label.config(text=f"Up: {days}d {hours}h")
            else:
                self.uptime_label.config(text=f"Up: {hours}h {mins}m")
        else:
            self.uptime_label.config(text="Uptime: --")

    def _draw_bar(self, canvas, percent, color):
        """Draw a progress bar on canvas."""
        canvas.delete('all')
        width = canvas.winfo_width() - 4
        if width < 10:
            width = 116
        fill_width = int((percent / 100) * width)
        canvas.create_rectangle(2, 2, fill_width + 2, 14, fill=color, outline='')

    def _get_load_color(self, percent):
        """Get color based on load percentage."""
        if percent < 50:
            return self.colors['success']
        elif percent < 75:
            return self.colors['warning']
        else:
            return self.colors['error']

    def _get_temp_color(self, temp):
        """Get color based on temperature."""
        if temp < 50:
            return self.colors['success']
        elif temp < 70:
            return self.colors['warning']
        else:
            return self.colors['error']

    # =========================================================================
    # BLOCKCHAIN VALIDATION (Proof of Presence)
    # =========================================================================

    def _init_blockchain(self):
        """Lazy-initialize the Proof of Presence engine."""
        if self._pop_engine is not None:
            return True
        try:
            import sys
            from pathlib import Path
            # Add blockchain dir to path
            blockchain_dir = Path(__file__).parent.parent.parent.parent / "blockchain"
            if str(blockchain_dir) not in sys.path:
                sys.path.insert(0, str(blockchain_dir))
            from proof_of_presence import ProofOfPresence
            self._pop_engine = ProofOfPresence()
            balance = self._pop_engine.check_balance()
            self._schedule_ui(lambda b=balance: self.blockchain_status_label.config(
                text=f"Polygon: {b:.2f} POL",
                fg='#00c853'
            ))
            return True
        except Exception as e:
            logger.error(f"Blockchain init failed: {e}")
            self._schedule_ui(lambda err=str(e): self.blockchain_status_label.config(
                text=f"Polygon: ERROR",
                fg=self.colors['error']
            ))
            return False

    def _on_validate_click(self):
        """Handle VALIDATE button click - capture + hash + mint."""
        # Disable button during validation
        self.validate_btn.config(state='disabled', text='VALIDATING...', bg='#ff9800')

        def run_validation():
            try:
                # Step 1: Initialize blockchain (lazy)
                self._schedule_ui(lambda: self.validate_btn.config(text='CONNECTING...'))
                if not self._init_blockchain():
                    self._schedule_ui(lambda: messagebox.showerror(
                        "Blockchain Error",
                        "Could not connect to Polygon.\nCheck polygon_config.json"
                    ))
                    self._reset_validate_btn()
                    return

                # Step 2: Get image - try DANIELSON cameras, fallback to file picker
                self._schedule_ui(lambda: self.validate_btn.config(text='CAPTURING...'))
                image_path = self._capture_for_validation()
                if not image_path:
                    # Fallback: file picker
                    self._schedule_ui(lambda: self.validate_btn.config(text='SELECT IMAGE...'))
                    image_path = self._pick_image_file()

                if not image_path:
                    self._reset_validate_btn()
                    return

                # Step 3: Run Proof of Presence validation
                self._schedule_ui(lambda: self.validate_btn.config(text='HASHING...'))

                # Determine card info from filename or barcode
                import os.path
                fname = os.path.basename(image_path)
                card_name = os.path.splitext(fname)[0].replace('_', ' ').title()

                self._schedule_ui(lambda: self.validate_btn.config(text='MINTING ON POLYGON...'))
                result = self._pop_engine.validate(
                    image_path=image_path,
                    card_name=card_name,
                    tcg_type="Sports"
                )

                # Step 4: Show result
                if result.get('success'):
                    receipt_text = self._pop_engine.get_receipt_text(result)
                    self._schedule_ui(lambda r=result, rt=receipt_text: self._show_validation_receipt(r, rt))
                else:
                    err = result.get('error', 'Unknown error')
                    # Even if receipt timed out, TX may still be on-chain
                    tx = result.get('tx_hash', '')
                    ps = result.get('polygonscan', '')
                    msg = f"Blockchain mint issue:\n{err}"
                    if tx:
                        msg += f"\n\nTX may still confirm. Check:\n{ps}"
                    self._schedule_ui(lambda m=msg: messagebox.showwarning(
                        "Validation Status", m
                    ))

            except Exception as e:
                logger.error(f"Validation error: {e}")
                self._schedule_ui(lambda err=str(e): messagebox.showerror(
                    "Validation Error", f"Error: {err}"
                ))
            finally:
                self._reset_validate_btn()

        threading.Thread(target=run_validation, daemon=True).start()

    def _capture_for_validation(self) -> str:
        """Try to capture an image from DANIELSON. CZUR first, then webcam. Returns local path or None."""
        import tempfile
        temp_dir = os.path.join(tempfile.gettempdir(), 'nexus_validate')
        os.makedirs(temp_dir, exist_ok=True)

        # Try 1: CZUR dedicated endpoint (highest quality, 4624x3472)
        try:
            r = requests.post(
                f"{self.danielson_url}/api/capture/czur",
                timeout=15
            )
            if r.status_code == 200:
                data = r.json()
                if data.get('success'):
                    remote_path = data.get('image_path', '')
                    if remote_path:
                        img_r = requests.get(
                            f"{self.danielson_url}/api/image?path={remote_path}",
                            timeout=15
                        )
                        if img_r.status_code == 200:
                            local_path = os.path.join(
                                temp_dir,
                                f"czur_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            )
                            with open(local_path, 'wb') as f:
                                f.write(img_r.content)
                            logger.info(f"CZUR capture: {local_path} ({len(img_r.content)} bytes)")
                            return local_path
        except requests.RequestException:
            pass

        # Try 2: Generic capture endpoint (CZUR, then webcam)
        for camera in ['czur', 'owleye', 'webcam']:
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/capture",
                    json={"camera": camera},
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get('success'):
                        remote_path = data.get('image_path', '')
                        if remote_path:
                            img_r = requests.get(
                                f"{self.danielson_url}/api/image?path={remote_path}",
                                timeout=10
                            )
                            if img_r.status_code == 200:
                                local_path = os.path.join(
                                    temp_dir,
                                    f"{camera}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                )
                                with open(local_path, 'wb') as f:
                                    f.write(img_r.content)
                                logger.info(f"{camera} capture: {local_path}")
                                return local_path
            except requests.RequestException:
                continue

        return None

    def _pick_image_file(self) -> str:
        """Open file picker for selecting an image to validate. Runs on UI thread."""
        result = [None]
        event = threading.Event()

        def do_pick():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Select Image to Validate",
                filetypes=[
                    ("Images", "*.jpg *.jpeg *.png *.bmp *.tiff"),
                    ("All files", "*.*")
                ]
            )
            result[0] = path if path else None
            event.set()

        self._schedule_ui(do_pick)
        event.wait(timeout=120)  # Wait up to 2 min for user to pick
        return result[0]

    def _show_validation_receipt(self, result: dict, receipt_text: str):
        """Show the validation receipt in a popup window."""
        popup = tk.Toplevel(self.frame)
        popup.title("NEXUS - Proof of Presence")
        popup.geometry("550x650")
        popup.configure(bg='#1a1a1a')
        popup.attributes('-topmost', True)

        # Header
        tk.Label(
            popup, text="VALIDATION COMPLETE",
            font=('Segoe UI', 18, 'bold'),
            fg='#00c853', bg='#1a1a1a'
        ).pack(pady=(20, 5))

        tk.Label(
            popup, text="Proof of Presence Minted on Polygon",
            font=('Segoe UI', 11),
            fg='#888888', bg='#1a1a1a'
        ).pack(pady=(0, 15))

        # Receipt text
        receipt_frame = tk.Frame(popup, bg='#2a2a2a', bd=2, relief='sunken')
        receipt_frame.pack(fill='both', expand=True, padx=20, pady=5)

        receipt_display = tk.Text(
            receipt_frame,
            font=('Consolas', 10),
            fg='#00ff00', bg='#1a1a1a',
            wrap='word', bd=0,
            padx=10, pady=10
        )
        receipt_display.pack(fill='both', expand=True)
        receipt_display.insert('1.0', receipt_text)
        receipt_display.config(state='disabled')

        # Buttons
        btn_frame = tk.Frame(popup, bg='#1a1a1a')
        btn_frame.pack(fill='x', padx=20, pady=15)

        polygonscan_url = result.get('polygonscan', '')

        def open_polygonscan():
            if polygonscan_url:
                import webbrowser
                webbrowser.open(polygonscan_url)

        tk.Button(
            btn_frame, text="View on Polygonscan",
            font=('Segoe UI', 11, 'bold'),
            bg='#7c4dff', fg='white',
            command=open_polygonscan,
            cursor='hand2', width=20
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame, text="Close",
            font=('Segoe UI', 11),
            bg='#555555', fg='white',
            command=popup.destroy,
            cursor='hand2', width=10
        ).pack(side='right', padx=5)

        # Token ID display
        token_id = result.get('token_id', 'N/A')
        tx_hash = result.get('tx_hash', 'N/A')
        tk.Label(
            popup,
            text=f"Token #{token_id}  |  TX: 0x{tx_hash[:12]}...",
            font=('Consolas', 9),
            fg='#666666', bg='#1a1a1a'
        ).pack(pady=(0, 10))

    def _reset_validate_btn(self):
        """Reset the VALIDATE button to ready state."""
        self._schedule_ui(lambda: self.validate_btn.config(
            state='normal', text='VALIDATE', bg='#00c853'
        ))

    def _reset_collector_btn(self):
        """Reset the COLLECTOR button to ready state."""
        self._schedule_ui(lambda: self.collector_btn.config(
            state='normal', text='COLLECTOR', bg='#ff8f00'
        ))

    def _on_collector_click(self):
        """Handle COLLECTOR button - burst capture + dual-hash forensic validation."""
        self.collector_btn.config(state='disabled', text='SCANNING...', bg='#e65100')

        def run_collector():
            try:
                # Step 1: Init blockchain
                self._schedule_ui(lambda: self.collector_btn.config(text='CONNECTING...'))
                if not self._init_blockchain():
                    self._schedule_ui(lambda: messagebox.showerror(
                        "Blockchain Error",
                        "Could not connect to Polygon.\nCheck polygon_config.json"
                    ))
                    self._reset_collector_btn()
                    return

                # Step 2: Burst capture (5-shot, best sharpness)
                self._schedule_ui(lambda: self.collector_btn.config(text='BURST 5-SHOT...'))
                image_path = self._capture_collector_tier()
                if not image_path:
                    self._schedule_ui(lambda: self.collector_btn.config(text='SELECT IMAGE...'))
                    image_path = self._pick_image_file()

                if not image_path:
                    self._reset_collector_btn()
                    return

                # Step 3: Dual-hash validation (wide + detail crop)
                self._schedule_ui(lambda: self.collector_btn.config(text='DUAL HASHING...'))

                import os.path
                fname = os.path.basename(image_path)
                card_name = os.path.splitext(fname)[0].replace('_', ' ').title()

                self._schedule_ui(lambda: self.collector_btn.config(text='MINTING COLLECTOR...'))
                result = self._pop_engine.validate_collector_tier(
                    image_path=image_path,
                    card_name=card_name,
                    tcg_type="Sports"
                )

                # Step 4: Show result
                if result.get('success'):
                    receipt_text = self._pop_engine.get_receipt_text(result)
                    self._schedule_ui(lambda r=result, rt=receipt_text: self._show_validation_receipt(r, rt))
                else:
                    err = result.get('error', 'Unknown error')
                    tx = result.get('tx_hash', '')
                    ps = result.get('polygonscan', '')
                    msg = f"Collector validation issue:\n{err}"
                    if tx:
                        msg += f"\n\nTX may still confirm. Check:\n{ps}"
                    self._schedule_ui(lambda m=msg: messagebox.showwarning(
                        "Collector Status", m
                    ))

            except Exception as e:
                logger.error(f"Collector validation error: {e}")
                self._schedule_ui(lambda err=str(e): messagebox.showerror(
                    "Collector Error", f"Error: {err}"
                ))
            finally:
                self._reset_collector_btn()

        threading.Thread(target=run_collector, daemon=True).start()

    def _capture_collector_tier(self) -> str:
        """
        Collector Tier capture - burst 5 shots, return the sharpest.
        Uses /api/capture/optimal with multi_shot=5.
        Falls back to standard CZUR capture if optimal endpoint unavailable.
        """
        import tempfile
        temp_dir = os.path.join(tempfile.gettempdir(), 'nexus_validate')
        os.makedirs(temp_dir, exist_ok=True)

        # Try 1: Optimal endpoint with burst mode (5-shot, picks sharpest)
        try:
            r = requests.post(
                f"{self.danielson_url}/api/capture/optimal",
                json={"multi_shot": 5},
                timeout=30
            )
            if r.status_code == 200:
                data = r.json()
                if data.get('success'):
                    remote_path = data.get('image_path', data.get('best_path', ''))
                    if remote_path:
                        img_r = requests.get(
                            f"{self.danielson_url}/api/image?path={remote_path}",
                            timeout=15
                        )
                        if img_r.status_code == 200:
                            local_path = os.path.join(
                                temp_dir,
                                f"collector_burst_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            )
                            with open(local_path, 'wb') as f:
                                f.write(img_r.content)
                            logger.info(f"Collector burst capture: {local_path} ({len(img_r.content)} bytes)")
                            return local_path
        except requests.RequestException as e:
            logger.warning(f"Optimal burst capture failed: {e}")

        # Try 2: CZUR single shot (still good quality, just no burst selection)
        logger.info("Burst unavailable, falling back to CZUR single capture")
        return self._capture_for_validation()

    def cleanup(self):
        """Cleanup on tab close."""
        # Stop all polling
        self._queue_polling = False
        self._stats_polling = False

        # Cleanup embedded live camera panel
        if hasattr(self, 'live_camera_panel'):
            try:
                self.live_camera_panel.cleanup()
            except Exception:
                pass

        # Cancel all pending .after() callbacks
        for after_id in self._after_ids:
            try:
                self.frame.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()


