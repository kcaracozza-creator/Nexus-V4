#!/usr/bin/env python3
"""NEXUS V2 - Live View Tab"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import queue
import time
import requests
from io import BytesIO
from datetime import datetime

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class LiveViewTab:
    """
    Live Camera View Interface.

    Features:
    - Live video stream from OwlEye, CZUR, or webcam
    - Snapshot capture
    - Focus control
    - Frame rate display
    """

    def __init__(self, parent, config):
        """
        parent: ttk.Notebook (adds as a tab) OR tk/ttk Frame (embeds directly).
        """
        self.config = config
        self.colors = self._get_colors()

        # State
        self.streaming = False
        self.stream_thread = None
        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = time.time()
        # Load scanner URL from config
        try:
            from nexus_v2.config.config_manager import config
            self.danielson_url = config.get('scanner.danielson_url', 'http://192.168.1.219:5001')
        except ImportError:
            self.danielson_url = "http://192.168.1.219:5001"
        self.current_image = None

        # Thread-safe UI queue
        self._ui_queue = queue.Queue()
        self._queue_polling = False
        self._after_ids = []  # Track .after() callback IDs for proper cleanup

        # Support both notebook tab mode and embedded frame mode
        if isinstance(parent, ttk.Notebook):
            self.notebook = parent
            self.frame = ttk.Frame(parent)
            parent.add(self.frame, text="Live View")
        else:
            # Embedded directly into a plain frame
            self.notebook = None
            self.frame = ttk.Frame(parent)
            self.frame.pack(fill='both', expand=True)

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
        except Exception as e:
            logger.warning(f"UI queue processing error: {e}")
        # Only schedule next iteration if widget still exists
        try:
            if self._queue_polling and self.frame.winfo_exists():
                after_id = self.frame.after(50, self._process_ui_queue)
                self._after_ids.append(after_id)
        except tk.TclError:
            # Widget destroyed, stop polling
            self._queue_polling = False

    def _schedule_ui(self, callback):
        """Thread-safe way to schedule a UI update."""
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
        """Build the live view interface."""
        # Main container - dark background
        container = tk.Frame(self.frame, bg='#1a1a1a')
        container.pack(fill='both', expand=True)

        # Top bar with controls
        top_bar = tk.Frame(container, bg=self.colors['surface'], height=60)
        top_bar.pack(fill='x')
        top_bar.pack_propagate(False)

        # Left controls in top bar
        left_controls = tk.Frame(top_bar, bg=self.colors['surface'])
        left_controls.pack(side='left', padx=10, pady=5)

        # Camera label (webcam only)
        tk.Label(
            left_controls, text="WEBCAM",
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['warning'], bg=self.colors['surface']
        ).pack(side='left', padx=10)

        # Stream buttons
        self.start_btn = tk.Button(
            left_controls, text="START",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['success'], fg='white',
            width=8, command=self._start_stream,
            cursor='hand2'
        )
        self.start_btn.pack(side='left', padx=3)

        self.stop_btn = tk.Button(
            left_controls, text="STOP",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['error'], fg='white',
            width=8, command=self._stop_stream,
            cursor='hand2', state='disabled'
        )
        self.stop_btn.pack(side='left', padx=3)

        # Snapshot button
        tk.Button(
            left_controls, text="SNAPSHOT",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['accent'], fg='white',
            width=10, command=self._capture_snapshot,
            cursor='hand2'
        ).pack(side='left', padx=10)

        # Right status in top bar
        right_controls = tk.Frame(top_bar, bg=self.colors['surface'])
        right_controls.pack(side='right', padx=10, pady=5)

        self.fps_label = tk.Label(
            right_controls, text="FPS: --",
            font=('Consolas', 12, 'bold'),
            fg=self.colors['warning'], bg=self.colors['surface']
        )
        self.fps_label.pack(side='left', padx=10)

        self.status_label = tk.Label(
            right_controls, text="STOPPED",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['error'], bg=self.colors['surface']
        )
        self.status_label.pack(side='left', padx=10)

        # MAIN VIDEO DISPLAY - Large black area
        video_frame = tk.Frame(container, bg='#000000', bd=2, relief='sunken')
        video_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self._create_video_display(video_frame)

        # Bottom bar with status
        bottom_bar = tk.Frame(container, bg=self.colors['surface'], height=40)
        bottom_bar.pack(fill='x')
        bottom_bar.pack_propagate(False)

        # Capture label (for snapshot feedback)
        self.capture_label = tk.Label(
            bottom_bar, text="Press SNAPSHOT to capture",
            font=('Segoe UI', 10),
            fg=self.colors['text_dim'], bg=self.colors['surface']
        )
        self.capture_label.pack(side='left', padx=15, pady=10)

        # Server info
        tk.Label(
            bottom_bar, text=f"Server: {self.danielson_url}",
            font=('Consolas', 9),
            fg=self.colors['text_dim'], bg=self.colors['surface']
        ).pack(side='right', padx=15, pady=10)

    def _create_video_display(self, parent):
        """Video display area"""
        # Video canvas
        self.video_canvas = tk.Canvas(
            parent, bg='black',
            highlightthickness=0
        )
        self.video_canvas.pack(fill='both', expand=True)

        # Placeholder text
        self.video_canvas.create_text(
            400, 300,
            text="Click START to begin streaming",
            font=('Segoe UI', 16),
            fill='#666666',
            tags='placeholder'
        )

        # Bind resize
        self.video_canvas.bind('<Configure>', self._on_canvas_resize)

    def _on_canvas_resize(self, event):
        """Handle canvas resize"""
        # Update placeholder position
        self.video_canvas.coords(
            'placeholder',
            event.width // 2, event.height // 2
        )

    def _start_stream(self):
        """Start video streaming"""
        if self.streaming:
            return

        self.streaming = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_label.config(text="CONNECTING...", fg=self.colors['warning'])
        self.video_canvas.delete('placeholder')

        # Start stream thread
        self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.stream_thread.start()

        # Start FPS counter
        self.frame_count = 0
        self.last_fps_time = time.time()
        self._update_fps()

    def _stop_stream(self):
        """Stop video streaming"""
        self.streaming = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="STOPPED", fg=self.colors['error'])
        self.fps_label.config(text="FPS: --")

        # Show placeholder
        w = self.video_canvas.winfo_width()
        h = self.video_canvas.winfo_height()
        self.video_canvas.create_text(
            w // 2, h // 2,
            text="Stream stopped",
            font=('Segoe UI', 16),
            fill='#666666',
            tags='placeholder'
        )

    def _stream_loop(self):
        """Main streaming loop - webcam only"""
        stream_url = f"{self.danielson_url}/api/video/stream?camera=webcam"

        try:
            # For MJPEG stream
            response = requests.get(
                stream_url,
                stream=True,
                timeout=10
            )

            if response.status_code == 200:
                self._schedule_ui( lambda: self.status_label.config(
                    text="STREAMING", fg=self.colors['success']
                ))

                # Parse MJPEG stream
                buffer = b''
                for chunk in response.iter_content(chunk_size=4096):
                    if not self.streaming:
                        break

                    buffer += chunk

                    # Find JPEG boundaries
                    start = buffer.find(b'\xff\xd8')
                    end = buffer.find(b'\xff\xd9')

                    if start != -1 and end != -1 and end > start:
                        jpg = buffer[start:end+2]
                        buffer = buffer[end+2:]

                        try:
                            # Decode and display
                            if PIL_AVAILABLE:
                                image = Image.open(BytesIO(jpg))
                                self._display_frame(image)
                                self.frame_count += 1
                        except Exception:
                            pass

            else:
                # Fallback to snapshot mode
                self._snapshot_stream_fallback()

        except requests.RequestException as ex:
            err_msg = str(ex)
            self._schedule_ui( lambda: self.status_label.config(
                text="ERROR", fg=self.colors['error']
            ))
            self._schedule_ui( lambda m=err_msg: messagebox.showerror(
                "Stream Error", f"Could not connect to camera: {m}"
            ))
            self._schedule_ui( self._stop_stream)

    def _snapshot_stream_fallback(self):
        """Fallback to snapshot-based streaming (webcam only)"""
        self._schedule_ui( lambda: self.status_label.config(
            text="SNAPSHOT MODE", fg=self.colors['warning']
        ))

        while self.streaming:
            try:
                # Capture webcam snapshot
                r = requests.post(
                    f"{self.danielson_url}/api/snapshot",
                    json={"camera": "webcam"},
                    timeout=5
                )

                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        image_path = result.get('image_path', '')
                        if image_path:
                            # Fetch the image
                            img_r = requests.get(
                                f"{self.danielson_url}/api/image?path={image_path}",
                                timeout=5
                            )
                            if img_r.status_code == 200:
                                if PIL_AVAILABLE:
                                    image = Image.open(BytesIO(img_r.content))
                                    self._display_frame(image)
                                    self.frame_count += 1

                time.sleep(0.1)  # ~10 FPS max in snapshot mode

            except Exception:
                time.sleep(0.5)

    def _display_frame(self, image):
        """Display a frame on the canvas"""
        if not self.streaming:
            return

        def update():
            try:
                # Get canvas size
                canvas_w = self.video_canvas.winfo_width()
                canvas_h = self.video_canvas.winfo_height()

                if canvas_w < 10 or canvas_h < 10:
                    return

                # Calculate scaling to fit
                img_w, img_h = image.size
                scale = min(canvas_w / img_w, canvas_h / img_h)
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)

                # Flip image (webcam is upside down)
                flipped = image.transpose(Image.Transpose.ROTATE_180)

                # Resize image
                resized = flipped.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # Convert to PhotoImage
                self.current_image = ImageTk.PhotoImage(resized)

                # Clear and draw
                self.video_canvas.delete('all')
                x = (canvas_w - new_w) // 2
                y = (canvas_h - new_h) // 2
                self.video_canvas.create_image(x, y, anchor='nw', image=self.current_image)

            except Exception:
                pass

        self._schedule_ui( update)

    def _update_fps(self):
        """Update FPS display"""
        if not self.streaming:
            return

        now = time.time()
        elapsed = now - self.last_fps_time

        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.fps_label.config(text=f"FPS: {self.fps:.1f}")
            self.frame_count = 0
            self.last_fps_time = now

        # Only schedule next update if widget still exists
        try:
            if self.streaming and self.frame.winfo_exists():
                after_id = self.frame.after(500, self._update_fps)
                self._after_ids.append(after_id)
        except tk.TclError:
            # Widget destroyed, stop updating
            self.streaming = False

    def _capture_snapshot(self):
        """Capture a snapshot from webcam"""
        def capture():
            try:
                r = requests.post(
                    f"{self.danielson_url}/api/capture",
                    json={"camera": "webcam"},
                    timeout=15
                )

                if r.status_code == 200:
                    result = r.json()
                    if result.get('success'):
                        path = result.get('image_path', '')
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        self._schedule_ui( lambda: self.capture_label.config(
                            text=f"Captured at {timestamp}"
                        ))
                        self._schedule_ui( lambda: messagebox.showinfo(
                            "Snapshot", f"Saved to:\n{path}"
                        ))
                    else:
                        self._schedule_ui( lambda: messagebox.showerror(
                            "Error", result.get('error', 'Capture failed')
                        ))
                else:
                    self._schedule_ui( lambda: messagebox.showerror(
                        "Error", f"HTTP {r.status_code}"
                    ))

            except Exception as ex:
                err_msg = str(ex)
                self._schedule_ui( lambda m=err_msg: messagebox.showerror(
                    "Error", f"Capture failed: {m}"
                ))

        threading.Thread(target=capture, daemon=True).start()

    def _save_frame(self):
        """Save current displayed frame"""
        if not hasattr(self, 'current_image') or not self.current_image:
            messagebox.showwarning("No Frame", "No frame to save. Start streaming first.")
            return

        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            initialfile=f"frame_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )

        if path:
            # We'd need to save the PIL image, not PhotoImage
            messagebox.showinfo("Save", f"Frame would be saved to:\n{path}")

    def cleanup(self):
        """Cleanup on tab close"""
        # Stop all polling
        self._queue_polling = False
        self.streaming = False

        # Cancel all pending .after() callbacks
        for after_id in self._after_ids:
            try:
                self.frame.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()
