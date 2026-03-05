#!/usr/bin/env python3
"""
NEXUS Proof of Presence - 7" Touchscreen Kiosk UI
Patent Pending - Kevin Caracozza

Designed for 800x480 touchscreen on DANIELSON scanner station.
Full-screen, big buttons, no keyboard needed.

Usage:
    python touch_validator.py              # Auto-detect screen
    python touch_validator.py --fullscreen # Force fullscreen
    python touch_validator.py --windowed   # 800x480 window (testing)
"""

import os
import sys
import json
import time
import logging
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import font as tkfont

import requests

# Add blockchain module to path
BLOCKCHAIN_DIR = Path(__file__).parent.parent.parent / "blockchain"
if str(BLOCKCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BLOCKCHAIN_DIR))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG
# =============================================================================
SCREEN_W = 800
SCREEN_H = 480
SCANNER_URL = "http://127.0.0.1:5001"  # Local on DANIELSON

# Colors (dark theme, high contrast for outdoor/event use)
BG = '#0a0a0a'
SURFACE = '#1a1a1a'
GREEN = '#00c853'
GREEN_DARK = '#009624'
GOLD = '#ff8f00'
GOLD_DARK = '#c56000'
RED = '#ff1744'
WHITE = '#ffffff'
GRAY = '#888888'
DIM = '#555555'
BLUE = '#448aff'


class TouchValidator:
    """Full-screen touch UI for on-site Proof of Presence validation."""

    def __init__(self, fullscreen=True):
        self.root = tk.Tk()
        self.root.title("NEXUS Validator")
        self.root.configure(bg=BG)
        self.root.geometry(f"{SCREEN_W}x{SCREEN_H}")

        if fullscreen:
            self.root.attributes('-fullscreen', True)
            # Escape to exit fullscreen (dev only)
            self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

        # Hide cursor for touch
        self.root.config(cursor='none')

        # Proof of Presence engine (lazy init)
        self._pop = None
        self._busy = False

        # Temp dir for captures
        self._temp_dir = os.path.join(tempfile.gettempdir(), 'nexus_touch')
        os.makedirs(self._temp_dir, exist_ok=True)

        # Build UI
        self._build_ui()

        # Init blockchain in background
        threading.Thread(target=self._init_blockchain, daemon=True).start()

    def _build_ui(self):
        """Build the touch-optimized interface."""

        # === TOP BAR: Status ===
        top = tk.Frame(self.root, bg=SURFACE, height=50)
        top.pack(fill='x')
        top.pack_propagate(False)

        tk.Label(
            top, text="NEXUS", font=('Arial', 20, 'bold'),
            fg=GREEN, bg=SURFACE
        ).pack(side='left', padx=15)

        tk.Label(
            top, text="PROOF OF PRESENCE",
            font=('Arial', 14), fg=WHITE, bg=SURFACE
        ).pack(side='left', padx=5)

        self.status_label = tk.Label(
            top, text="INITIALIZING...",
            font=('Arial', 12, 'bold'), fg=GOLD, bg=SURFACE
        )
        self.status_label.pack(side='right', padx=15)

        self.balance_label = tk.Label(
            top, text="", font=('Arial', 10), fg=GRAY, bg=SURFACE
        )
        self.balance_label.pack(side='right', padx=10)

        # === MIDDLE: Main content area ===
        middle = tk.Frame(self.root, bg=BG)
        middle.pack(fill='both', expand=True, pady=10)

        # Left side: Buttons (big, touch-friendly)
        btn_frame = tk.Frame(middle, bg=BG)
        btn_frame.pack(side='left', fill='both', expand=True, padx=15)

        # VALIDATE button - fills most of the left side
        self.validate_btn = tk.Button(
            btn_frame, text="VALIDATE",
            font=('Arial', 36, 'bold'),
            bg=GREEN, fg=WHITE,
            activebackground=GREEN_DARK, activeforeground=WHITE,
            relief='flat', bd=0,
            command=self._on_validate
        )
        self.validate_btn.pack(fill='both', expand=True, pady=(0, 8))

        # COLLECTOR button - below validate
        self.collector_btn = tk.Button(
            btn_frame, text="COLLECTOR",
            font=('Arial', 24, 'bold'),
            bg=GOLD, fg=WHITE,
            activebackground=GOLD_DARK, activeforeground=WHITE,
            relief='flat', bd=0,
            command=self._on_collector
        )
        self.collector_btn.pack(fill='x', ipady=15)

        # Right side: Receipt / info display
        info_frame = tk.Frame(middle, bg=SURFACE, width=340)
        info_frame.pack(side='right', fill='both', padx=(0, 15))
        info_frame.pack_propagate(False)

        # Info header
        tk.Label(
            info_frame, text="SCAN RESULT",
            font=('Arial', 14, 'bold'), fg=GRAY, bg=SURFACE
        ).pack(pady=(10, 5))

        # Receipt text area
        self.receipt_text = tk.Text(
            info_frame, font=('Courier', 9),
            fg=GREEN, bg='#111111',
            wrap='word', bd=0,
            padx=8, pady=8,
            state='disabled'
        )
        self.receipt_text.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        # Show welcome message
        self._set_receipt("Place item on scanner\nand tap VALIDATE\n\nor COLLECTOR for\npremium dual-hash scan")

        # === BOTTOM BAR: Info ===
        bottom = tk.Frame(self.root, bg=SURFACE, height=40)
        bottom.pack(fill='x')
        bottom.pack_propagate(False)

        self.zone_label = tk.Label(
            bottom, text="Zone: --",
            font=('Arial', 10), fg=GRAY, bg=SURFACE
        )
        self.zone_label.pack(side='left', padx=15)

        self.token_label = tk.Label(
            bottom, text="",
            font=('Courier', 9), fg=DIM, bg=SURFACE
        )
        self.token_label.pack(side='left', padx=10)

        # Scan counter
        self.scan_count = 0
        self.count_label = tk.Label(
            bottom, text="Scans: 0",
            font=('Arial', 10), fg=GRAY, bg=SURFACE
        )
        self.count_label.pack(side='right', padx=15)

        self.time_label = tk.Label(
            bottom, text="",
            font=('Arial', 10), fg=DIM, bg=SURFACE
        )
        self.time_label.pack(side='right', padx=10)

        # EXIT button (double-tap to exit kiosk → Ubuntu desktop)
        self._exit_tap_time = 0
        exit_btn = tk.Button(
            bottom, text="EXIT",
            font=('Arial', 9, 'bold'),
            bg='#333333', fg=RED,
            activebackground='#550000', activeforeground=WHITE,
            relief='flat', bd=0,
            width=6,
            command=self._on_exit_tap
        )
        exit_btn.pack(side='left', padx=(10, 0))

        # Clock update
        self._update_clock()

    def _update_clock(self):
        """Update time display every second."""
        now = datetime.now().strftime('%H:%M:%S')
        self.time_label.config(text=now)
        self.root.after(1000, self._update_clock)

    def _set_receipt(self, text):
        """Set the receipt display text."""
        self.receipt_text.config(state='normal')
        self.receipt_text.delete('1.0', 'end')
        self.receipt_text.insert('1.0', text)
        self.receipt_text.config(state='disabled')

    def _set_status(self, text, color=GOLD):
        """Update status label."""
        self.status_label.config(text=text, fg=color)

    def _set_buttons_enabled(self, enabled):
        """Enable/disable both buttons."""
        state = 'normal' if enabled else 'disabled'
        self.validate_btn.config(state=state)
        self.collector_btn.config(state=state)
        if not enabled:
            self.validate_btn.config(bg=DIM)
            self.collector_btn.config(bg=DIM)
        else:
            self.validate_btn.config(bg=GREEN)
            self.collector_btn.config(bg=GOLD)

    # =========================================================================
    # BLOCKCHAIN
    # =========================================================================

    def _init_blockchain(self):
        """Initialize Proof of Presence engine."""
        try:
            from proof_of_presence import ProofOfPresence
            self._pop = ProofOfPresence()
            balance = self._pop.check_balance()

            # Show zone info
            in_zone, zone_name, dist = self._pop.is_in_geofence()
            zone_text = f"Zone: {zone_name}" if in_zone else "Zone: OUTSIDE GEOFENCE"
            zone_color = GREEN if in_zone else RED

            self.root.after(0, lambda: [
                self._set_status("READY", GREEN),
                self.balance_label.config(text=f"{balance:.2f} POL"),
                self.zone_label.config(text=zone_text, fg=zone_color),
            ])

        except Exception as e:
            logger.error(f"Blockchain init failed: {e}")
            self.root.after(0, lambda: [
                self._set_status("OFFLINE", RED),
                self._set_receipt(f"Blockchain connection failed:\n{e}\n\nCheck polygon_config.json"),
            ])

    # =========================================================================
    # CAPTURE
    # =========================================================================

    def _capture_image(self, burst=False) -> str:
        """Capture image from local DANIELSON cameras. Returns path or None."""

        # Burst mode: 5-shot optimal
        if burst:
            try:
                r = requests.post(
                    f"{SCANNER_URL}/api/capture/optimal",
                    json={"multi_shot": 5},
                    timeout=30
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get('success'):
                        remote_path = data.get('image_path', data.get('best_path', ''))
                        if remote_path:
                            return self._download_image(remote_path, "burst")
            except Exception as e:
                logger.warning(f"Burst capture failed: {e}")

        # CZUR single shot
        for camera in ['czur', 'owleye', 'webcam']:
            try:
                r = requests.post(
                    f"{SCANNER_URL}/api/capture",
                    json={"camera": camera},
                    timeout=15
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get('success'):
                        remote_path = data.get('image_path', '')
                        if remote_path:
                            return self._download_image(remote_path, camera)
            except Exception:
                continue

        return None

    def _download_image(self, remote_path, prefix) -> str:
        """Download image from scanner API to local temp file."""
        img_r = requests.get(
            f"{SCANNER_URL}/api/image?path={remote_path}",
            timeout=15
        )
        if img_r.status_code == 200:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            local_path = os.path.join(self._temp_dir, f"{prefix}_{ts}.jpg")
            with open(local_path, 'wb') as f:
                f.write(img_r.content)
            logger.info(f"Captured: {local_path} ({len(img_r.content)} bytes)")
            return local_path
        return None

    # =========================================================================
    # VALIDATION HANDLERS
    # =========================================================================

    def _on_validate(self):
        """Standard validation - single shot, single hash."""
        if self._busy:
            return
        self._busy = True
        self._set_buttons_enabled(False)
        self._set_status("CAPTURING...", GOLD)
        self._set_receipt("Capturing image...")

        def run():
            try:
                if not self._pop:
                    self._show_error("Blockchain not connected")
                    return

                # Capture
                self.root.after(0, lambda: self._set_status("CAPTURING...", GOLD))
                image_path = self._capture_image(burst=False)
                if not image_path:
                    self._show_error("Camera capture failed.\nCheck USB connections.")
                    return

                # Validate
                self.root.after(0, lambda: [
                    self._set_status("MINTING...", GOLD),
                    self._set_receipt("Hashing image...\nMinting on Polygon...\n\nPlease wait ~6 seconds"),
                ])

                result = self._pop.validate(image_path=image_path)
                self._handle_result(result)

            except Exception as e:
                self._show_error(str(e))
            finally:
                self._busy = False
                self.root.after(0, lambda: self._set_buttons_enabled(True))

        threading.Thread(target=run, daemon=True).start()

    def _on_collector(self):
        """Collector tier - burst capture, dual hash."""
        if self._busy:
            return
        self._busy = True
        self._set_buttons_enabled(False)
        self._set_status("BURST CAPTURE...", GOLD)
        self._set_receipt("5-shot burst capture...\nSelecting sharpest image...")

        def run():
            try:
                if not self._pop:
                    self._show_error("Blockchain not connected")
                    return

                # Burst capture
                self.root.after(0, lambda: self._set_status("BURST 5-SHOT...", GOLD))
                image_path = self._capture_image(burst=True)
                if not image_path:
                    self._show_error("Camera capture failed.\nCheck USB connections.")
                    return

                # Collector tier validate
                self.root.after(0, lambda: [
                    self._set_status("DUAL HASHING...", GOLD),
                    self._set_receipt(
                        "Hashing wide shot...\n"
                        "Cropping center detail...\n"
                        "Hashing detail...\n"
                        "Minting dual-hash on Polygon...\n\n"
                        "Please wait ~6 seconds"
                    ),
                ])

                result = self._pop.validate_collector_tier(image_path=image_path)
                self._handle_result(result)

            except Exception as e:
                self._show_error(str(e))
            finally:
                self._busy = False
                self.root.after(0, lambda: self._set_buttons_enabled(True))

        threading.Thread(target=run, daemon=True).start()

    def _handle_result(self, result):
        """Handle validation result - update UI."""
        if result.get('success'):
            receipt = self._pop.get_receipt_text(result)
            token_id = result.get('token_id', '?')
            elapsed = result.get('elapsed_seconds', '?')
            tier = result.get('tier', 'STANDARD')
            barcode = result.get('barcode', '')

            barcode_note = f"\nBarcode: {barcode}" if barcode else ""

            self.scan_count += 1

            self.root.after(0, lambda: [
                self._set_status(f"VALIDATED #{token_id}", GREEN),
                self._set_receipt(receipt),
                self.token_label.config(
                    text=f"Token #{token_id} | {elapsed}s | {tier}",
                    fg=GREEN
                ),
                self.count_label.config(text=f"Scans: {self.scan_count}"),
                # Update balance
                self.balance_label.config(text=f"{self._pop.check_balance():.2f} POL"),
            ])

            # Flash green background briefly
            self.root.after(0, lambda: self.root.configure(bg=GREEN_DARK))
            self.root.after(500, lambda: self.root.configure(bg=BG))

        else:
            err = result.get('error', 'Unknown error')
            tx = result.get('tx_hash', '')
            ps = result.get('polygonscan', '')

            msg = f"VALIDATION ISSUE:\n{err}"
            if tx:
                msg += f"\n\nTX may still confirm:\n{ps}"

            self.root.after(0, lambda: [
                self._set_status("ERROR", RED),
                self._set_receipt(msg),
            ])

            # Flash red background briefly
            self.root.after(0, lambda: self.root.configure(bg='#330000'))
            self.root.after(500, lambda: self.root.configure(bg=BG))

        # Reset status after 10 seconds
        self.root.after(10000, lambda: self._set_status("READY", GREEN) if not self._busy else None)

    def _show_error(self, msg):
        """Show error on screen."""
        self.root.after(0, lambda: [
            self._set_status("ERROR", RED),
            self._set_receipt(f"ERROR:\n{msg}"),
            self._set_buttons_enabled(True),
        ])
        self._busy = False

    # =========================================================================
    # EXIT TO DESKTOP
    # =========================================================================

    def _on_exit_tap(self):
        """Double-tap EXIT to leave kiosk and return to Ubuntu desktop."""
        now = time.time()
        if now - self._exit_tap_time < 1.5:
            # Second tap within 1.5s — exit kiosk
            logger.info("Double-tap EXIT — returning to desktop")
            self.root.attributes('-fullscreen', False)
            self.root.destroy()
        else:
            # First tap — show hint
            self._exit_tap_time = now
            self._set_status("TAP EXIT AGAIN TO QUIT", RED)
            self.root.after(2000, lambda: self._set_status("READY", GREEN) if not self._busy else None)

    # =========================================================================
    # RUN
    # =========================================================================

    def run(self):
        """Start the touch UI main loop."""
        logger.info(f"Touch Validator starting ({SCREEN_W}x{SCREEN_H})")
        self.root.mainloop()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='NEXUS Touch Validator')
    parser.add_argument('--fullscreen', action='store_true', default=True,
                        help='Run fullscreen (default)')
    parser.add_argument('--windowed', action='store_true',
                        help='Run in 800x480 window')
    args = parser.parse_args()

    fullscreen = not args.windowed

    app = TouchValidator(fullscreen=fullscreen)
    app.run()
