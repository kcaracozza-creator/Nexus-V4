#!/usr/bin/env python3
"""
NEXUS Scanner Station — 7" Touchscreen Employee UI
Patent Pending — Kevin Caracozza (Filed Nov 27, 2025)

800x480 kiosk for card shop employees.
Scan cards, see results, accept/skip/reject.

Usage:
    python scanner_station_ui.py              # Fullscreen on 7" touch
    python scanner_station_ui.py --windowed   # 800x480 window (testing)
"""

import os
import sys
import io
import json
import time
import logging
import threading
from datetime import datetime

import tkinter as tk
from tkinter import font as tkfont

import requests

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG
# =============================================================================
SCREEN_W = 800
SCREEN_H = 480
API = os.getenv('NEXUS_SCANNER_URL', 'http://127.0.0.1:5001')

# Colors — matches desktop dark theme
BG       = '#0d1117'
SURFACE  = '#161b22'
SURFACE2 = '#1c2330'
BORDER   = '#30363d'
ACCENT   = '#58a6ff'
GREEN    = '#3fb950'
GREEN_DK = '#238636'
YELLOW   = '#d29922'
RED      = '#f85149'
WHITE    = '#e6edf3'
DIM      = '#8b949e'
ORANGE   = '#d18616'

# TCG types with labels
TCGS = [
    ('mtg',      'MTG'),
    ('pokemon',  'Pokemon'),
    ('yugioh',   'Yu-Gi-Oh'),
    ('sports',   'Sports'),
    ('onepiece',  'One Piece'),
    ('lorcana',  'Lorcana'),
    ('fab',      'FaB'),
]

MODES = [
    ('single', 'SINGLE TCG'),
    ('bulk',   'BULK'),
    ('grade',  'GRADING'),
]


class ScannerStation:
    """Employee scanner station for 7" touchscreen."""

    def __init__(self, fullscreen=True):
        self.root = tk.Tk()
        self.root.title("NEXUS Scanner Station")
        self.root.configure(bg=BG)
        self.root.geometry(f"{SCREEN_W}x{SCREEN_H}")

        if fullscreen:
            self.root.attributes('-fullscreen', True)
            self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

        self.root.config(cursor='none' if fullscreen else '')

        # State
        self.mode = 'single'
        self.tcg = 'mtg'
        self.connected = False
        self.scanning = False
        self.last_result = None
        self._preview_img = None  # hold ref so tk doesn't GC it

        # Session stats
        self.total_scans = 0
        self.accepted = 0
        self.rejected = 0
        self.skipped = 0
        self.avg_time_ms = 0
        self._scan_times = []

        # Fonts
        self.f_title = ('Consolas', 14, 'bold')
        self.f_mode  = ('Consolas', 9, 'bold')
        self.f_body  = ('Consolas', 10)
        self.f_small = ('Consolas', 8)
        self.f_big   = ('Consolas', 18, 'bold')
        self.f_btn   = ('Consolas', 14, 'bold')
        self.f_card  = ('Consolas', 13, 'bold')

        self._build_ui()
        self._check_connection()

    # =========================================================================
    # UI BUILD
    # =========================================================================

    def _build_ui(self):
        # === TOP BAR ===
        top = tk.Frame(self.root, bg=SURFACE, height=36)
        top.pack(fill='x')
        top.pack_propagate(False)

        tk.Label(top, text="NEXUS", font=self.f_title, fg=GREEN, bg=SURFACE).pack(side='left', padx=8)

        # Mode buttons
        self._mode_btns = {}
        mode_f = tk.Frame(top, bg=SURFACE)
        mode_f.pack(side='left', padx=(10, 0))
        for key, label in MODES:
            b = tk.Button(
                mode_f, text=label, font=self.f_mode,
                bg=SURFACE2, fg=DIM, activebackground=ACCENT, activeforeground=WHITE,
                relief='flat', bd=0, padx=8, pady=2,
                command=lambda k=key: self._set_mode(k)
            )
            b.pack(side='left', padx=1)
            self._mode_btns[key] = b

        # Connection status (right side)
        self.conn_label = tk.Label(
            top, text="OFFLINE", font=self.f_small,
            fg=RED, bg=SURFACE
        )
        self.conn_label.pack(side='right', padx=8)

        # Session counter (right side)
        self.count_label = tk.Label(
            top, text="0 cards", font=self.f_small,
            fg=DIM, bg=SURFACE
        )
        self.count_label.pack(side='right', padx=4)

        # === MAIN AREA (3 columns) ===
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill='both', expand=True, pady=2)

        # --- LEFT: TCG selector + SCAN button + stats ---
        left = tk.Frame(main, bg=BG, width=200)
        left.pack(side='left', fill='y', padx=(4, 2))
        left.pack_propagate(False)

        # TCG grid (2 columns)
        tcg_frame = tk.Frame(left, bg=BG)
        tcg_frame.pack(fill='x', pady=(2, 4))

        tk.Label(tcg_frame, text="Card Type", font=self.f_small, fg=ACCENT, bg=BG).pack(anchor='w')

        grid = tk.Frame(tcg_frame, bg=BG)
        grid.pack(fill='x')

        self._tcg_btns = {}
        for i, (key, label) in enumerate(TCGS):
            row, col = divmod(i, 2)
            b = tk.Button(
                grid, text=label, font=self.f_small,
                bg=SURFACE2, fg=DIM, activebackground=ACCENT,
                relief='flat', bd=0, width=9, pady=3,
                command=lambda k=key: self._set_tcg(k)
            )
            b.grid(row=row, column=col, padx=1, pady=1, sticky='ew')
            self._tcg_btns[key] = b

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # SCAN button
        self.scan_btn = tk.Button(
            left, text="SCAN CARD", font=self.f_btn,
            bg=GREEN, fg=WHITE,
            activebackground=GREEN_DK, activeforeground=WHITE,
            relief='flat', bd=0,
            command=self._on_scan
        )
        self.scan_btn.pack(fill='x', pady=(6, 4), ipady=12)

        # Pipeline steps
        steps_frame = tk.Frame(left, bg=SURFACE, bd=1, relief='flat')
        steps_frame.pack(fill='x', pady=(2, 4))

        self._step_labels = []
        steps = [
            ("1: Capture", "Camera + lights"),
            ("2: OCR", "Name + collector #"),
            ("3: Art Match", "FAISS embedding"),
            ("4: Cross-Ref", "ZULTAN lookup"),
        ]
        for name, desc in steps:
            row = tk.Frame(steps_frame, bg=SURFACE)
            row.pack(fill='x', padx=4, pady=1)
            dot = tk.Label(row, text="\u25cb", font=self.f_small, fg=DIM, bg=SURFACE)
            dot.pack(side='left')
            tk.Label(row, text=f" {name}", font=self.f_small, fg=WHITE, bg=SURFACE).pack(side='left')
            tk.Label(row, text=f"  {desc}", font=self.f_small, fg=DIM, bg=SURFACE).pack(side='left')
            self._step_labels.append(dot)

        # Session stats
        stats_frame = tk.Frame(left, bg=SURFACE, bd=1, relief='flat')
        stats_frame.pack(fill='both', expand=True, pady=(2, 0))

        tk.Label(stats_frame, text="Session", font=self.f_small, fg=ACCENT, bg=SURFACE).pack(anchor='w', padx=4, pady=(2, 0))
        self.stats_text = tk.Label(
            stats_frame, text="Scans: 0\nAccepted: 0\nAvg: --",
            font=self.f_small, fg=DIM, bg=SURFACE, justify='left', anchor='nw'
        )
        self.stats_text.pack(fill='both', expand=True, padx=4, pady=2)

        # --- CENTER: Card preview + scan log ---
        center = tk.Frame(main, bg=BG)
        center.pack(side='left', fill='both', expand=True, padx=2)

        # Preview label
        tk.Label(center, text="Card Preview", font=self.f_small, fg=ACCENT, bg=BG).pack(anchor='w')

        self.preview_frame = tk.Frame(center, bg=SURFACE2, bd=1, relief='flat')
        self.preview_frame.pack(fill='both', expand=True)

        self.preview_label = tk.Label(
            self.preview_frame, text="Place card on scanner\nand tap SCAN",
            font=self.f_body, fg=DIM, bg=SURFACE2
        )
        self.preview_label.pack(fill='both', expand=True)

        # Scan log (2 lines max)
        self.log_label = tk.Label(
            center, text="", font=('Courier', 7), fg=DIM, bg=BG,
            anchor='w', justify='left'
        )
        self.log_label.pack(fill='x', pady=(2, 0))

        # --- RIGHT: Match result + actions ---
        right = tk.Frame(main, bg=BG, width=260)
        right.pack(side='right', fill='y', padx=(2, 4))
        right.pack_propagate(False)

        # Match result panel
        result_frame = tk.Frame(right, bg=SURFACE, bd=1, relief='flat')
        result_frame.pack(fill='x', pady=(0, 4))

        tk.Label(result_frame, text="Match Result", font=self.f_small, fg=ACCENT, bg=SURFACE).pack(anchor='w', padx=6, pady=(4, 0))

        # Card name
        self.card_name = tk.Label(
            result_frame, text="--", font=self.f_card,
            fg=WHITE, bg=SURFACE, wraplength=240, anchor='w', justify='left'
        )
        self.card_name.pack(fill='x', padx=6, pady=(2, 0))

        # Confidence bar
        conf_row = tk.Frame(result_frame, bg=SURFACE)
        conf_row.pack(fill='x', padx=6, pady=2)
        tk.Label(conf_row, text="Conf:", font=self.f_small, fg=DIM, bg=SURFACE).pack(side='left')

        self.conf_bar_bg = tk.Frame(conf_row, bg=BORDER, height=12, width=140)
        self.conf_bar_bg.pack(side='left', padx=4)
        self.conf_bar_bg.pack_propagate(False)
        self.conf_bar = tk.Frame(self.conf_bar_bg, bg=GREEN, height=12, width=0)
        self.conf_bar.place(x=0, y=0, relheight=1.0)

        self.conf_pct = tk.Label(conf_row, text="0%", font=self.f_small, fg=DIM, bg=SURFACE)
        self.conf_pct.pack(side='left')

        # Set + Collector #
        info_row = tk.Frame(result_frame, bg=SURFACE)
        info_row.pack(fill='x', padx=6, pady=(0, 2))
        self.set_label = tk.Label(info_row, text="Set: --", font=self.f_small, fg=DIM, bg=SURFACE)
        self.set_label.pack(side='left')
        self.coll_label = tk.Label(info_row, text="  #: --", font=self.f_small, fg=DIM, bg=SURFACE)
        self.coll_label.pack(side='left')

        # Price
        self.price_label = tk.Label(
            result_frame, text="", font=self.f_body, fg=YELLOW, bg=SURFACE
        )
        self.price_label.pack(fill='x', padx=6, pady=(0, 4))

        # Other matches
        other_frame = tk.Frame(right, bg=SURFACE, bd=1, relief='flat')
        other_frame.pack(fill='x', pady=(0, 4))
        tk.Label(other_frame, text="Other matches", font=self.f_small, fg=ACCENT, bg=SURFACE).pack(anchor='w', padx=6, pady=(2, 0))
        self.other_text = tk.Label(
            other_frame, text="", font=self.f_small,
            fg=DIM, bg=SURFACE, anchor='nw', justify='left', wraplength=240
        )
        self.other_text.pack(fill='x', padx=6, pady=(0, 4))

        # Spacer pushes buttons to bottom
        tk.Frame(right, bg=BG).pack(fill='both', expand=True)

        # Action buttons — big touch targets
        btn_frame = tk.Frame(right, bg=BG)
        btn_frame.pack(fill='x', pady=(0, 4))

        self.accept_btn = tk.Button(
            btn_frame, text="ACCEPT", font=self.f_btn,
            bg=GREEN, fg=WHITE, activebackground=GREEN_DK,
            relief='flat', bd=0, state='disabled',
            command=self._on_accept
        )
        self.accept_btn.pack(fill='x', ipady=8, pady=(0, 3))

        mid_btns = tk.Frame(btn_frame, bg=BG)
        mid_btns.pack(fill='x')

        self.skip_btn = tk.Button(
            mid_btns, text="SKIP", font=self.f_mode,
            bg=YELLOW, fg=WHITE, activebackground=ORANGE,
            relief='flat', bd=0, state='disabled',
            command=self._on_skip
        )
        self.skip_btn.pack(side='left', fill='x', expand=True, ipady=6, padx=(0, 2))

        self.reject_btn = tk.Button(
            mid_btns, text="REJECT", font=self.f_mode,
            bg=RED, fg=WHITE, activebackground='#b62324',
            relief='flat', bd=0, state='disabled',
            command=self._on_reject
        )
        self.reject_btn.pack(side='right', fill='x', expand=True, ipady=6, padx=(2, 0))

        # Double-tap exit
        self._exit_time = 0
        exit_btn = tk.Button(
            right, text="EXIT", font=('Consolas', 7),
            bg=SURFACE2, fg=DIM, relief='flat', bd=0,
            command=self._on_exit
        )
        exit_btn.pack(anchor='se', pady=(0, 2))

        # Set initial selection highlights
        self._set_mode(self.mode)
        self._set_tcg(self.tcg)

    # =========================================================================
    # MODE / TCG SELECTION
    # =========================================================================

    def _set_mode(self, mode):
        self.mode = mode
        for k, b in self._mode_btns.items():
            if k == mode:
                b.config(bg=ACCENT, fg=WHITE)
            else:
                b.config(bg=SURFACE2, fg=DIM)

    def _set_tcg(self, tcg):
        self.tcg = tcg
        for k, b in self._tcg_btns.items():
            if k == tcg:
                b.config(bg=ORANGE, fg=WHITE)
            else:
                b.config(bg=SURFACE2, fg=DIM)

    # =========================================================================
    # CONNECTION CHECK
    # =========================================================================

    def _check_connection(self):
        def check():
            try:
                r = requests.get(f"{API}/status", timeout=3)
                online = r.status_code == 200
                data = r.json() if online else {}
                cpu = data.get('cpu_percent', '?')
                self.root.after(0, lambda: self._set_conn(True, cpu))
            except Exception:
                self.root.after(0, lambda: self._set_conn(False))
        threading.Thread(target=check, daemon=True).start()
        self.root.after(5000, self._check_connection)

    def _set_conn(self, online, cpu='?'):
        self.connected = online
        if online:
            self.conn_label.config(text=f"ONLINE ({cpu}%)", fg=GREEN)
        else:
            self.conn_label.config(text="OFFLINE", fg=RED)

    # =========================================================================
    # SCANNING
    # =========================================================================

    def _on_scan(self):
        if self.scanning or not self.connected:
            return
        self.scanning = True
        self.scan_btn.config(bg=DIM, text="SCANNING...", state='disabled')
        self._set_actions_enabled(False)
        self._reset_steps()
        self._log("Scanning...")

        def run():
            t0 = time.time()
            try:
                # Step 1: Capture
                self.root.after(0, lambda: self._mark_step(0, 'active'))

                payload = {
                    'mode': self.mode,
                    'tcg_type': self.tcg,
                }
                r = requests.post(f"{API}/api/acr", json=payload, timeout=60)
                elapsed_ms = int((time.time() - t0) * 1000)

                if r.status_code == 200:
                    data = r.json()
                    self._scan_times.append(elapsed_ms)
                    self.total_scans += 1

                    # Update step indicators from response
                    stages = data.get('stages', {})
                    if stages.get('capture', {}).get('success'):
                        self.root.after(0, lambda: self._mark_step(0, 'done'))
                    if stages.get('ocr', {}).get('success') or stages.get('region_ocr', {}).get('name'):
                        self.root.after(0, lambda: self._mark_step(1, 'done'))
                    if stages.get('art_match', {}).get('success'):
                        self.root.after(0, lambda: self._mark_step(2, 'done'))
                    if data.get('card_name') or data.get('best_match', {}).get('name'):
                        self.root.after(0, lambda: self._mark_step(3, 'done'))

                    self.root.after(0, lambda: self._show_result(data, elapsed_ms))
                else:
                    self.root.after(0, lambda: self._scan_error(f"Server returned {r.status_code}"))

            except requests.Timeout:
                self.root.after(0, lambda: self._scan_error("Scan timed out"))
            except Exception as e:
                self.root.after(0, lambda: self._scan_error(str(e)))
            finally:
                self.scanning = False
                self.root.after(0, lambda: [
                    self.scan_btn.config(bg=GREEN, text="SCAN CARD", state='normal'),
                    self._update_stats(),
                ])

        threading.Thread(target=run, daemon=True).start()

    def _show_result(self, data, elapsed_ms):
        """Display ACR pipeline result."""
        self.last_result = data

        # Extract card info from various response shapes
        name = (data.get('card_name') or
                data.get('best_match', {}).get('name') or
                data.get('stages', {}).get('region_ocr', {}).get('name') or
                '--')
        conf = (data.get('confidence') or
                data.get('best_match', {}).get('confidence') or 0)
        if isinstance(conf, str):
            try: conf = float(conf)
            except: conf = 0
        conf = min(conf, 100)

        set_name = (data.get('set_name') or
                    data.get('best_match', {}).get('set_name') or '--')
        coll_num = (data.get('collector_number') or
                    data.get('best_match', {}).get('collector_number') or '--')
        price = data.get('price') or data.get('best_match', {}).get('price')

        # Update card name
        self.card_name.config(text=name, fg=WHITE if name != '--' else DIM)

        # Update confidence bar
        bar_color = GREEN if conf >= 90 else YELLOW if conf >= 70 else RED
        bar_w = max(1, int(140 * conf / 100))
        self.conf_bar.config(bg=bar_color)
        self.conf_bar.place(x=0, y=0, width=bar_w, relheight=1.0)
        self.conf_pct.config(text=f"{conf:.0f}%", fg=bar_color)

        # Set + collector
        self.set_label.config(text=f"Set: {set_name}")
        self.coll_label.config(text=f"  #: {coll_num}")

        # Price
        if price:
            self.price_label.config(text=f"${price:.2f}" if isinstance(price, (int, float)) else str(price))
        else:
            self.price_label.config(text="")

        # Other matches
        others = data.get('other_matches', data.get('alternatives', []))
        if others:
            lines = []
            for m in others[:3]:
                n = m.get('name', '?')
                c = m.get('confidence', 0)
                lines.append(f"{n} ({c:.0f}%)")
            self.other_text.config(text='\n'.join(lines))
        else:
            self.other_text.config(text="")

        # Preview image
        img_path = (data.get('image_path') or
                    data.get('stages', {}).get('capture', {}).get('image_path'))
        if img_path and PIL_OK:
            self._load_preview(img_path)

        # Log
        self._log(f"Match: {name} ({conf:.0f}%) in {elapsed_ms}ms")

        # Enable action buttons
        self._set_actions_enabled(True)

    def _load_preview(self, remote_path):
        """Fetch captured image and show in preview."""
        def fetch():
            try:
                r = requests.get(f"{API}/api/image?path={remote_path}", timeout=10)
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content))
                    # Fit to preview area (approx 320x300)
                    img.thumbnail((320, 300), Image.LANCZOS)
                    self.root.after(0, lambda: self._set_preview(img))
            except Exception as e:
                logger.warning(f"Preview load failed: {e}")
        threading.Thread(target=fetch, daemon=True).start()

    def _set_preview(self, pil_img):
        self._preview_img = ImageTk.PhotoImage(pil_img)
        self.preview_label.config(image=self._preview_img, text='')

    def _scan_error(self, msg):
        self.card_name.config(text="SCAN FAILED", fg=RED)
        self._log(f"Error: {msg}")
        self._set_actions_enabled(False)

    # =========================================================================
    # PIPELINE STEP INDICATORS
    # =========================================================================

    def _reset_steps(self):
        for lbl in self._step_labels:
            lbl.config(text="\u25cb", fg=DIM)  # empty circle

    def _mark_step(self, idx, state):
        if idx < len(self._step_labels):
            if state == 'active':
                self._step_labels[idx].config(text="\u25cf", fg=YELLOW)  # filled, yellow
            elif state == 'done':
                self._step_labels[idx].config(text="\u25cf", fg=GREEN)   # filled, green
            elif state == 'fail':
                self._step_labels[idx].config(text="\u25cf", fg=RED)

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def _set_actions_enabled(self, enabled):
        state = 'normal' if enabled else 'disabled'
        self.accept_btn.config(state=state, bg=GREEN if enabled else SURFACE2)
        self.skip_btn.config(state=state, bg=YELLOW if enabled else SURFACE2)
        self.reject_btn.config(state=state, bg=RED if enabled else SURFACE2)

    def _on_accept(self):
        if not self.last_result:
            return
        self.accepted += 1
        self._log(f"ACCEPTED: {self.card_name.cget('text')}")
        self._set_actions_enabled(False)

        # Tell server to add to inventory
        def submit():
            try:
                requests.post(f"{API}/api/inventory/add", json={
                    'card_name': self.last_result.get('card_name') or self.last_result.get('best_match', {}).get('name'),
                    'set_name': self.last_result.get('set_name') or self.last_result.get('best_match', {}).get('set_name'),
                    'collector_number': self.last_result.get('collector_number'),
                    'confidence': self.last_result.get('confidence', 0),
                    'tcg_type': self.tcg,
                    'scan_data': self.last_result,
                }, timeout=5)
            except Exception as e:
                logger.warning(f"Inventory add failed: {e}")
        threading.Thread(target=submit, daemon=True).start()

        self._update_stats()
        self._flash(GREEN)

    def _on_skip(self):
        self.skipped += 1
        self._log("SKIPPED")
        self._set_actions_enabled(False)
        self._update_stats()

    def _on_reject(self):
        self.rejected += 1
        self._log("REJECTED")
        self._set_actions_enabled(False)
        self._update_stats()
        self._flash(RED)

    def _flash(self, color):
        """Brief color flash on the preview border."""
        self.preview_frame.config(bg=color)
        self.root.after(300, lambda: self.preview_frame.config(bg=SURFACE2))

    # =========================================================================
    # STATS / LOG
    # =========================================================================

    def _update_stats(self):
        avg = int(sum(self._scan_times) / len(self._scan_times)) if self._scan_times else 0
        self.stats_text.config(
            text=f"Scans: {self.total_scans}\n"
                 f"Accepted: {self.accepted}\n"
                 f"Skipped: {self.skipped}\n"
                 f"Rejected: {self.rejected}\n"
                 f"Avg: {avg}ms"
        )
        total = self.accepted + self.skipped + self.rejected
        self.count_label.config(text=f"{self.accepted} cards")

    def _log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_label.config(text=f"[{ts}] {msg}")

    # =========================================================================
    # EXIT
    # =========================================================================

    def _on_exit(self):
        now = time.time()
        if now - self._exit_time < 1.5:
            self.root.destroy()
        else:
            self._exit_time = now
            self._log("Tap EXIT again to quit")

    def run(self):
        logger.info(f"Scanner Station UI starting ({SCREEN_W}x{SCREEN_H})")
        self.root.mainloop()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='NEXUS Scanner Station UI')
    parser.add_argument('--windowed', action='store_true', help='Run in 800x480 window')
    args = parser.parse_args()

    app = ScannerStation(fullscreen=not args.windowed)
    app.run()
