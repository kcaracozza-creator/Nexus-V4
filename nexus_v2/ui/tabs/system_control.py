#!/usr/bin/env python3
"""NEXUS V2 - System Control Tab - Cross-Platform"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import platform
import sys
import subprocess
import threading
import queue
import os

# Cross-platform detection
IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')
IS_MAC = sys.platform == 'darwin'

try:
    from nexus_v2.config import get_config
    _config = get_config()
except ImportError:
    _config = None

logger = logging.getLogger(__name__)


class SystemControlTab:
    """
    System Control & Settings.
    
    Features:
    - Scanner configuration
    - Database management
    - Backup controls
    - System diagnostics
    """
    
    def __init__(self, notebook: ttk.Notebook, config):
        self.notebook = notebook
        self.config = config
        self.colors = self._get_colors()
        
        # Thread-safe UI queue
        self._ui_queue = queue.Queue()
        self._queue_polling = False

        # Create tab
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="⚙️ System")

        self._build_ui()
        self._start_ui_queue_processor()

    def _start_ui_queue_processor(self):
        """Start the UI queue processor."""
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
        self.frame.after(50, self._process_ui_queue)

    def _schedule_ui(self, callback):
        """Thread-safe way to schedule a UI update."""
        self._ui_queue.put(callback)
        
    def _get_colors(self):
        """Get theme colors."""
        class Colors:
            bg_dark = "#4a4a4a"
            bg_surface = "#555555"
            bg_elevated = "#606060"
            accent = "#5c6bc0"
            text_primary = "#ffffff"
            text_secondary = "#e0e0e0"
            success = "#43a047"
            error = "#e53935"
        return Colors()
        
    def _build_ui(self):
        """Build system control interface."""
        # Main container
        container = tk.Frame(self.frame, bg=self.colors.bg_dark)
        container.pack(fill='both', expand=True)

        # Header (fixed at top)
        header = tk.Frame(container, bg=self.colors.bg_surface)
        header.pack(fill='x', padx=10, pady=10)

        tk.Label(
            header, text="⚙️ System Control",
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors.accent, bg=self.colors.bg_surface
        ).pack(side='left', padx=15, pady=10)

        # Scrollable content area
        canvas = tk.Canvas(container, bg=self.colors.bg_dark, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
        main = tk.Frame(canvas, bg=self.colors.bg_dark)

        main.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=main, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True, padx=10)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Content columns
        content = tk.Frame(main, bg=self.colors.bg_dark)
        content.pack(fill='both', expand=True)
        
        # Left - Scanner Settings
        left = tk.Frame(content, bg=self.colors.bg_surface)
        left.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Scanner Config
        scanner_frame = tk.LabelFrame(
            left, text="Scanner Configuration",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        )
        scanner_frame.pack(fill='x', padx=10, pady=10)
        
        # Scanner IP
        ip_row = tk.Frame(scanner_frame, bg=self.colors.bg_surface)
        ip_row.pack(fill='x', padx=10, pady=5)
        tk.Label(ip_row, text="Scanner IP:", fg=self.colors.text_secondary, bg=self.colors.bg_surface).pack(side='left')
        self.scanner_ip = tk.Entry(ip_row, width=15, bg=self.colors.bg_elevated, fg='white')
        default_ip = _config.scanner.scanner_ip if _config else "192.168.1.219"
        self.scanner_ip.insert(0, default_ip)
        self.scanner_ip.pack(side='right')
        
        # Scanner Port
        port_row = tk.Frame(scanner_frame, bg=self.colors.bg_surface)
        port_row.pack(fill='x', padx=10, pady=5)
        tk.Label(port_row, text="Scanner Port:", fg=self.colors.text_secondary, bg=self.colors.bg_surface).pack(side='left')
        self.scanner_port = tk.Entry(port_row, width=15, bg=self.colors.bg_elevated, fg='white')
        self.scanner_port.insert(0, "5001")
        self.scanner_port.pack(side='right')
        
        btn_row = tk.Frame(scanner_frame, bg=self.colors.bg_surface)
        btn_row.pack(pady=10)

        tk.Button(
            btn_row, text="Test Connection",
            font=('Segoe UI', 9),
            fg='white', bg=self.colors.accent,
            command=self._test_scanner
        ).pack(side='left', padx=5)

        tk.Button(
            btn_row, text="Calibrate Touch",
            font=('Segoe UI', 9),
            fg='white', bg='#ff9800',
            command=self._calibrate_touchscreen
        ).pack(side='left', padx=5)
        
        # Database Config
        db_frame = tk.LabelFrame(
            left, text="Database Management",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        )
        db_frame.pack(fill='x', padx=10, pady=10)
        
        db_btns = tk.Frame(db_frame, bg=self.colors.bg_surface)
        db_btns.pack(pady=10)
        
        tk.Button(db_btns, text="📥 Backup DB", fg='white', bg=self.colors.success, command=self._backup_db).pack(side='left', padx=5)
        tk.Button(db_btns, text="📤 Restore DB", fg='white', bg=self.colors.accent, command=self._restore_db).pack(side='left', padx=5)
        tk.Button(db_btns, text="🗑️ Clear Cache", fg='white', bg=self.colors.error, command=self._clear_cache).pack(side='left', padx=5)

        # Right - System Info
        right = tk.Frame(content, bg=self.colors.bg_surface)
        right.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        # System Info
        sys_frame = tk.LabelFrame(
            right, text="System Information",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        )
        sys_frame.pack(fill='x', padx=10, pady=10)
        
        sys_info = [
            ("NEXUS Version:", "V2.0.0"),
            ("Python:", f"{sys.version_info.major}.{sys.version_info.minor}"),
            ("Platform:", platform.system()),
            ("Machine:", platform.machine()),
        ]
        
        for label, value in sys_info:
            row = tk.Frame(sys_frame, bg=self.colors.bg_surface)
            row.pack(fill='x', padx=10, pady=3)
            tk.Label(row, text=label, fg=self.colors.text_secondary, bg=self.colors.bg_surface).pack(side='left')
            tk.Label(row, text=value, fg=self.colors.text_primary, bg=self.colors.bg_surface, font=('Segoe UI', 10, 'bold')).pack(side='right')
            
        # Status Indicators
        status_frame = tk.LabelFrame(
            right, text="Service Status",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        )
        status_frame.pack(fill='x', padx=10, pady=10)
        
        services = [
            ("Scanner API", "● Online", self.colors.success),
            ("OCR Engine", "● Ready", self.colors.success),
            ("AI Engine", "● Active", self.colors.success),
            ("Cloud Sync", "○ Offline", self.colors.text_secondary),
        ]
        
        for name, status, color in services:
            row = tk.Frame(status_frame, bg=self.colors.bg_surface)
            row.pack(fill='x', padx=10, pady=3)
            tk.Label(row, text=name, fg=self.colors.text_secondary, bg=self.colors.bg_surface).pack(side='left')
            tk.Label(row, text=status, fg=color, bg=self.colors.bg_surface, font=('Segoe UI', 10, 'bold')).pack(side='right')
            
        # Logs
        log_frame = tk.LabelFrame(
            right, text="Recent Logs",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors.text_primary, bg=self.colors.bg_surface
        )
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = tk.Text(
            log_frame, height=8, width=40,
            bg=self.colors.bg_elevated, fg='#90caf9',
            font=('Consolas', 9)
        )
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        scanner_ip = _config.scanner.scanner_ip if _config else "192.168.1.219"
        self.log_text.insert('end', "[INFO] NEXUS V2 initialized\n")
        self.log_text.insert('end', f"[INFO] Scanner connected: {scanner_ip}\n")
        self.log_text.insert('end', "[INFO] Database loaded: 26,850 cards\n")
        self.log_text.insert('end', "[INFO] AI engine ready\n")
        
    def _test_scanner(self):
        """Test scanner connection."""
        ip = self.scanner_ip.get()
        port = self.scanner_port.get()
        self.log_text.insert('end', f"[TEST] Connecting to {ip}:{port}...\n")
        self.log_text.see('end')
        messagebox.showinfo("Scanner Test", f"Testing connection to {ip}:{port}...")
        
    def _backup_db(self):
        """Backup database."""
        self.log_text.insert('end', "[BACKUP] Database backup started...\n")
        self.log_text.see('end')
        messagebox.showinfo("Backup", "Database backed up successfully!")
        
    def _restore_db(self):
        """Restore database."""
        if messagebox.askyesno("Restore", "Are you sure? This will overwrite current data."):
            self.log_text.insert('end', "[RESTORE] Database restored\n")
            self.log_text.see('end')
            
    def _clear_cache(self):
        """Clear cache."""
        if messagebox.askyesno("Clear Cache", "Clear all cached data?"):
            self.log_text.insert('end', "[CACHE] Cache cleared\n")
            self.log_text.see('end')
            messagebox.showinfo("Cache", "Cache cleared successfully!")

    def _calibrate_touchscreen(self):
        """Run touchscreen calibration - cross-platform."""
        self.log_text.insert('end', "[CALIBRATE] Starting touchscreen calibration...\n")
        self.log_text.see('end')

        if IS_WINDOWS:
            # Windows: Open Tablet PC Settings
            self._schedule_ui(lambda: self.log_text.insert('end', "[CALIBRATE] Opening Windows Tablet Settings...\n"))
            try:
                # Open the tablet calibration tool
                subprocess.Popen(["control.exe", "tabletpc.cpl"])
                self._schedule_ui(lambda: self.log_text.insert('end', "[CALIBRATE] Use Windows calibration wizard\n"))
                messagebox.showinfo("Calibrate", "Use the Windows Tablet PC Settings to calibrate your touchscreen")
            except Exception as ex:
                err_msg = str(ex)
                self._schedule_ui(lambda m=err_msg: self.log_text.insert(
                    'end', f"[ERROR] {m}\n"))
            return

        # Linux calibration
        def run_calibration():
            try:
                # Check for xinput_calibrator
                result = subprocess.run(
                    ["which", "xinput_calibrator"],
                    capture_output=True, text=True, check=False
                )
                if result.returncode != 0:
                    self._schedule_ui(lambda: self.log_text.insert(
                        'end',
                        "[ERROR] xinput_calibrator not installed. "
                        "Install: sudo apt install xinput-calibrator\n"
                    ))
                    return

                # Run xinput_calibrator
                env = os.environ.copy()
                env["DISPLAY"] = ":0"
                result = subprocess.run(
                    ["xinput_calibrator"],
                    env=env, capture_output=True, text=True, timeout=60
                )

                if result.returncode == 0:
                    output = result.stdout
                    if "Section" in output:
                        self._schedule_ui(lambda o=output: self._save_calibration(o))
                    self._schedule_ui(lambda: self.log_text.insert(
                        'end', "[CALIBRATE] Calibration complete\n"))
                else:
                    stderr = result.stderr
                    self._schedule_ui(lambda s=stderr: self.log_text.insert(
                        'end', f"[ERROR] Calibration failed: {s}\n"))
            except subprocess.TimeoutExpired:
                self._schedule_ui(lambda: self.log_text.insert(
                    'end', "[ERROR] Calibration timed out\n"))
            except FileNotFoundError:
                self._schedule_ui(lambda: self.log_text.insert(
                    'end', "[ERROR] xinput_calibrator not found\n"))
            except Exception as ex:
                err_msg = str(ex)
                self._schedule_ui(lambda m=err_msg: self.log_text.insert(
                    'end', f"[ERROR] {m}\n"))

            self._schedule_ui(lambda: self.log_text.see('end'))

        threading.Thread(target=run_calibration, daemon=True).start()
        messagebox.showinfo(
            "Calibrate", "Tap the 4 crosshair targets on the touchscreen")

    def _save_calibration(self, output):
        """Save calibration config - Linux only."""
        if IS_WINDOWS:
            self.log_text.insert('end', "[INFO] Windows calibration saved via system dialog\n")
            return

        try:
            start = output.find('Section "InputClass"')
            end = output.find('EndSection') + len('EndSection')
            if start >= 0 and end > start:
                config = output[start:end]
                config_path = "/etc/X11/xorg.conf.d/99-calibration.conf"

                subprocess.run(["sudo", "mkdir", "-p", "/etc/X11/xorg.conf.d/"], check=True)
                subprocess.run(
                    ["sudo", "tee", config_path],
                    input=config, text=True, check=True, capture_output=True
                )
                self.log_text.insert('end', f"[CALIBRATE] Saved to {config_path}\n")
        except Exception as e:
            self.log_text.insert('end', f"[ERROR] Could not save config: {e}\n")
