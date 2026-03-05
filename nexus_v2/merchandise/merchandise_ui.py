"""
NEXUS Merchandise Authentication UI
18-screen guided workflow for FIFA merchandise verification.
Tkinter-based, matches NEXUS dark theme.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
import os
import io
import logging
import base64
from datetime import datetime

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

import requests

from nexus_v2.merchandise.merchandise_auth import (
    MerchandiseAuthSession,
    create_merchandise_session,
    capture_image,
    extract_tag_data,
    decode_barcode,
    verify_merchandise,
    generate_certificate,
    trigger_uv_on,
    trigger_uv_off,
    SNARF_URL,
)

logger = logging.getLogger("MERCH_UI")

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "surface2": "#21262d",
    "border": "#30363d",
    "accent": "#58a6ff",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "text": "#e6edf3",
    "text_dim": "#7d8590",
    "gold": "#ffd700",
    "verified": "#3fb950",
    "failed": "#f85149",
    "uv_purple": "#7b2fff",
}


# ---------------------------------------------------------------------------
# Step definitions for the 5-capture workflow
# ---------------------------------------------------------------------------
STEPS = [
    {
        "key": "step_1_primary_logo",
        "num": 1,
        "title": "PRIMARY LOGO",
        "instruction": "Position item so PRIMARY LOGO is visible",
        "detail": "Examples: FIFA logo, team crest,\nmanufacturer logo",
        "review_question": "Is the logo clearly visible?",
        "skippable": False,
        "run_ocr": False,
        "run_barcode": False,
        "uv_mode": False,
    },
    {
        "key": "step_2_manufacturer_tag",
        "num": 2,
        "title": "MANUFACTURER TAG",
        "instruction": "Flip item to INSIDE\nPosition NECK TAG in frame",
        "detail": "Should show: SKU, size, manufacturer,\ncountry of origin",
        "review_question": "Is the tag text clearly readable?",
        "skippable": False,
        "run_ocr": True,
        "run_barcode": False,
        "uv_mode": False,
    },
    {
        "key": "step_3_care_label",
        "num": 3,
        "title": "CARE LABEL",
        "instruction": "Position CARE LABEL in frame",
        "detail": "Should show: material composition,\nwashing instructions",
        "review_question": "Is the care label readable?",
        "skippable": True,
        "run_ocr": False,
        "run_barcode": False,
        "uv_mode": False,
    },
    {
        "key": "step_4_hang_tag",
        "num": 4,
        "title": "HANG TAG / BARCODE",
        "instruction": "If item has HANG TAG with barcode,\nposition it in frame",
        "detail": "Tag may show: barcode, price,\nFIFA branding",
        "review_question": "Is the hang tag / barcode visible?",
        "skippable": True,
        "run_barcode": True,
        "run_ocr": False,
        "uv_mode": False,
    },
    {
        "key": "step_5_uv_scan",
        "num": 5,
        "title": "UV SECURITY SCAN",
        "instruction": "Position item to capture UV features\n\nUV lights will activate automatically",
        "detail": "Look for: UV threads, watermarks,\nholograms, invisible inks",
        "review_question": "UV security features visible?",
        "skippable": False,
        "run_ocr": False,
        "run_barcode": False,
        "uv_mode": True,
    },
]


class MerchandiseAuthUI:
    """
    Embeds into a NEXUS notebook tab or runs standalone.
    All 18 screens are methods that swap the content of self.content_frame.
    """

    def __init__(self, parent, notebook=None, config=None):
        self.parent = parent
        self.notebook = notebook
        self.session: MerchandiseAuthSession = None
        self._ui_queue = queue.Queue()
        self._after_ids = []
        self._live_feed_active = False
        self._live_feed_job = None

        # Camera feed config
        self.snarf_url = SNARF_URL

        # Build outer frame
        if notebook:
            self.frame = tk.Frame(notebook, bg=COLORS["bg"])
            notebook.add(self.frame, text="  Merchandise Auth  ")
        else:
            self.frame = tk.Frame(parent, bg=COLORS["bg"])
            self.frame.pack(fill="both", expand=True)

        # Content area — screens swap here
        self.content_frame = tk.Frame(self.frame, bg=COLORS["bg"])
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Start queue processor
        self._process_queue()

        # Show mode selection
        self.show_mode_selection()

    # ------------------------------------------------------------------
    # Queue processor for thread-safe UI updates
    # ------------------------------------------------------------------
    def _process_queue(self):
        try:
            for _ in range(20):
                fn = self._ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        aid = self.frame.after(50, self._process_queue)
        self._after_ids.append(aid)

    def _ui(self, fn):
        """Schedule a function on the UI thread."""
        self._ui_queue.put(fn)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _clear(self):
        """Clear the content frame for a new screen."""
        self._stop_live_feed()
        for w in self.content_frame.winfo_children():
            w.destroy()

    def _title_bar(self, text, step=None):
        """Standard title bar across all screens."""
        bar = tk.Frame(self.content_frame, bg=COLORS["surface"], height=50)
        bar.pack(fill="x", pady=(0, 10))
        bar.pack_propagate(False)

        lbl = tk.Label(
            bar, text=text, font=("Consolas", 16, "bold"),
            fg=COLORS["gold"], bg=COLORS["surface"],
        )
        lbl.pack(side="left", padx=15, pady=10)

        if step:
            step_lbl = tk.Label(
                bar, text=f"STEP {step['num']} of 5",
                font=("Consolas", 12), fg=COLORS["accent"], bg=COLORS["surface"],
            )
            step_lbl.pack(side="right", padx=15)

        return bar

    def _btn(self, parent, text, command, color=None, width=20, **kw):
        """Styled button."""
        bg = color or COLORS["accent"]
        btn = tk.Button(
            parent, text=text, command=command,
            font=("Consolas", 12, "bold"),
            bg=bg, fg="white", activebackground=bg,
            relief="flat", cursor="hand2",
            width=width, height=2,
            **kw,
        )
        return btn

    def _progress_dots(self, parent, current_step):
        """Step progress indicator: 1 2 3 4 5."""
        frame = tk.Frame(parent, bg=COLORS["bg"])
        for i in range(1, 6):
            if i < current_step:
                color = COLORS["success"]
                txt = f" {i} "
            elif i == current_step:
                color = COLORS["accent"]
                txt = f"[{i}]"
            else:
                color = COLORS["text_dim"]
                txt = f" {i} "
            tk.Label(
                frame, text=txt, font=("Consolas", 14, "bold"),
                fg=color, bg=COLORS["bg"],
            ).pack(side="left", padx=5)
        return frame

    # ------------------------------------------------------------------
    # Live camera feed
    # ------------------------------------------------------------------
    def _start_live_feed(self, label_widget):
        """Start MJPEG snapshot polling into a label."""
        self._live_feed_active = True
        self._feed_label = label_widget

        def poll():
            while self._live_feed_active:
                try:
                    r = requests.get(
                        f"{self.snarf_url}/api/snapshot?camera=czur",
                        timeout=3,
                    )
                    if r.status_code == 200 and Image:
                        img = Image.open(io.BytesIO(r.content))
                        # Scale to fit preview area
                        img.thumbnail((640, 480))
                        photo = ImageTk.PhotoImage(img)
                        if self._live_feed_active:
                            self._ui(lambda p=photo: self._update_feed(p))
                except Exception:
                    pass
                time.sleep(0.15)  # ~7 fps

        threading.Thread(target=poll, daemon=True).start()

    def _update_feed(self, photo):
        if hasattr(self, "_feed_label") and self._feed_label.winfo_exists():
            self._feed_label.config(image=photo)
            self._feed_label._photo = photo  # prevent GC

    def _stop_live_feed(self):
        self._live_feed_active = False

    def _show_image(self, label_widget, image_path, max_size=(640, 480)):
        """Display a captured image in a label."""
        if not Image or not image_path or not os.path.exists(image_path):
            label_widget.config(text="[Image not available]")
            return
        try:
            img = Image.open(image_path)
            img.thumbnail(max_size)
            photo = ImageTk.PhotoImage(img)
            label_widget.config(image=photo, text="")
            label_widget._photo = photo
        except Exception as e:
            label_widget.config(text=f"[Error: {e}]")

    # ==================================================================
    # SCREEN 1: MODE SELECTION
    # ==================================================================
    def show_mode_selection(self):
        self._clear()
        self._title_bar("NEXUS AUTHENTICATION")

        body = tk.Frame(self.content_frame, bg=COLORS["bg"])
        body.pack(expand=True)

        tk.Label(
            body, text="Select Item Type:",
            font=("Consolas", 14), fg=COLORS["text"], bg=COLORS["bg"],
        ).pack(pady=(20, 30))

        modes = [
            ("1  TRADING CARD", COLORS["accent"], None),
            ("2  MERCHANDISE", COLORS["gold"], self.show_start_screen),
            ("3  MEMORABILIA", COLORS["text_dim"], None),
        ]

        for label, color, cmd in modes:
            state = "normal" if cmd else "disabled"
            btn = self._btn(body, label, cmd or (lambda: None), color=color, width=30)
            btn.config(state=state)
            btn.pack(pady=8)

        # Cancel
        self._btn(
            body, "CANCEL", self._on_cancel, color=COLORS["surface2"], width=20,
        ).pack(pady=(30, 0))

    # ==================================================================
    # SCREEN 2: START SCREEN
    # ==================================================================
    def show_start_screen(self):
        self._clear()
        self._title_bar("MERCHANDISE AUTHENTICATION")

        body = tk.Frame(self.content_frame, bg=COLORS["bg"])
        body.pack(expand=True)

        info = (
            "This process requires 5 photographs:\n\n"
            "  1. Primary logo / branding\n"
            "  2. Manufacturer tag (with SKU)\n"
            "  3. Care label\n"
            "  4. Hang tag with barcode (if present)\n"
            "  5. UV security scan\n\n"
            "Estimated time: 3-5 minutes\n"
            "Item must fit within 12\"x12\" frame"
        )

        tk.Label(
            body, text=info, font=("Consolas", 12),
            fg=COLORS["text"], bg=COLORS["bg"], justify="left",
        ).pack(pady=20)

        btn_row = tk.Frame(body, bg=COLORS["bg"])
        btn_row.pack(pady=20)

        self._btn(btn_row, "START", self._start_session, color=COLORS["success"]).pack(
            side="left", padx=15
        )
        self._btn(btn_row, "CANCEL", self.show_mode_selection, color=COLORS["surface2"]).pack(
            side="left", padx=15
        )

    def _start_session(self):
        self.session = create_merchandise_session()
        self._current_step_idx = 0
        self._show_capture_screen(STEPS[0])

    # ==================================================================
    # SCREENS 3,5,9,11,13: CAPTURE (parametric)
    # ==================================================================
    def _show_capture_screen(self, step):
        self._clear()
        self._title_bar(f"STEP {step['num']} of 5 — {step['title']}", step)

        self._progress_dots(self.content_frame, step["num"]).pack(pady=(0, 10))

        # Instructions
        tk.Label(
            self.content_frame, text=step["instruction"],
            font=("Consolas", 12), fg=COLORS["text"], bg=COLORS["bg"],
            justify="left",
        ).pack(pady=5)

        tk.Label(
            self.content_frame, text=step["detail"],
            font=("Consolas", 10), fg=COLORS["text_dim"], bg=COLORS["bg"],
            justify="left",
        ).pack(pady=5)

        # Camera feed area
        feed_frame = tk.Frame(
            self.content_frame, bg=COLORS["surface2"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        feed_frame.pack(pady=10, padx=20)

        feed_label = tk.Label(
            feed_frame, text="Connecting to CZUR...",
            font=("Consolas", 11), fg=COLORS["text_dim"],
            bg=COLORS["surface2"], width=80, height=25,
        )
        feed_label.pack(padx=5, pady=5)

        # Start live feed
        self._start_live_feed(feed_label)

        # Buttons
        btn_row = tk.Frame(self.content_frame, bg=COLORS["bg"])
        btn_row.pack(pady=10)

        if step["skippable"]:
            skip_text = "SKIP — No tag" if step["num"] == 4 else "SKIP"
            self._btn(
                btn_row, skip_text,
                lambda s=step: self._skip_step(s),
                color=COLORS["surface2"],
            ).pack(side="left", padx=15)

        capture_text = "CAPTURE UV PHOTO" if step["uv_mode"] else "CAPTURE PHOTO"
        self._btn(
            btn_row, capture_text,
            lambda s=step: self._do_capture(s),
            color=COLORS["accent"],
        ).pack(side="left", padx=15)

    def _do_capture(self, step):
        """Capture in background thread, then show review."""
        self._stop_live_feed()

        # Show "capturing..." overlay
        for w in self.content_frame.winfo_children():
            w.destroy()
        self._title_bar(f"STEP {step['num']} of 5 — CAPTURING...", step)
        tk.Label(
            self.content_frame, text="Capturing image...",
            font=("Consolas", 14), fg=COLORS["warning"], bg=COLORS["bg"],
        ).pack(expand=True)

        def bg():
            path = capture_image(self.session, step["key"], uv_mode=step["uv_mode"])
            self._ui(lambda: self._show_review_screen(step, path))

        threading.Thread(target=bg, daemon=True).start()

    def _skip_step(self, step):
        """Skip optional step and advance."""
        self.session.images[step["key"]] = None
        self._advance_after_step(step)

    # ==================================================================
    # SCREENS 4,6,10,12,14: IMAGE REVIEW (parametric)
    # ==================================================================
    def _show_review_screen(self, step, image_path):
        self._clear()
        self._title_bar(f"STEP {step['num']} of 5 — IMAGE REVIEW", step)

        self._progress_dots(self.content_frame, step["num"]).pack(pady=(0, 10))

        # Show captured image
        img_label = tk.Label(
            self.content_frame, text="Loading...",
            bg=COLORS["surface2"], fg=COLORS["text_dim"],
            width=80, height=22,
        )
        img_label.pack(pady=10, padx=20)

        if image_path:
            self._show_image(img_label, image_path)
        else:
            img_label.config(text="CAPTURE FAILED — Try again", fg=COLORS["error"])

        tk.Label(
            self.content_frame, text=step["review_question"],
            font=("Consolas", 12), fg=COLORS["text"], bg=COLORS["bg"],
        ).pack(pady=10)

        btn_row = tk.Frame(self.content_frame, bg=COLORS["bg"])
        btn_row.pack(pady=10)

        self._btn(
            btn_row, "RETAKE",
            lambda s=step: self._show_capture_screen(s),
            color=COLORS["warning"],
        ).pack(side="left", padx=15)

        self._btn(
            btn_row, "APPROVE",
            lambda s=step: self._approve_step(s),
            color=COLORS["success"],
        ).pack(side="left", padx=15)

    def _approve_step(self, step):
        """After approving an image, route to the next appropriate screen."""
        # Step 2 special: run OCR processing screen
        if step["run_ocr"]:
            self._show_ocr_processing(step)
            return

        # Step 4 special: run barcode decode inline
        if step["run_barcode"]:
            img = self.session.images.get(step["key"])
            if img:
                barcode = decode_barcode(img)
                if barcode:
                    self.session.extracted_data["barcode"] = barcode

        self._advance_after_step(step)

    def _advance_after_step(self, step):
        """Move to next capture step, or to verification if done."""
        idx = next(i for i, s in enumerate(STEPS) if s["key"] == step["key"])
        if idx + 1 < len(STEPS):
            self._current_step_idx = idx + 1
            self._show_capture_screen(STEPS[idx + 1])
        else:
            # All 5 steps done — run verification
            self._show_verification_processing()

    # ==================================================================
    # SCREEN 7: OCR PROCESSING
    # ==================================================================
    def _show_ocr_processing(self, step):
        self._clear()
        self._title_bar(f"STEP {step['num']} of 5 — READING TAG", step)

        body = tk.Frame(self.content_frame, bg=COLORS["bg"])
        body.pack(expand=True)

        self._ocr_lines = []
        lines = [
            ("Reading tag information...", COLORS["warning"]),
        ]

        for txt, color in lines:
            lbl = tk.Label(
                body, text=txt, font=("Consolas", 12),
                fg=color, bg=COLORS["bg"],
            )
            lbl.pack(pady=3)
            self._ocr_lines.append(lbl)

        # Placeholder labels for animated status
        self._ocr_status_labels = []
        status_items = [
            "Text extraction...",
            "SKU identification...",
            "Manufacturer detection...",
            "Format verification...",
        ]
        for item in status_items:
            lbl = tk.Label(
                body, text=f"  ... {item}",
                font=("Consolas", 11), fg=COLORS["text_dim"], bg=COLORS["bg"],
            )
            lbl.pack(pady=2, anchor="w", padx=40)
            self._ocr_status_labels.append(lbl)

        def bg_ocr():
            img = self.session.images.get(step["key"])
            if img:
                tag_data = extract_tag_data(img)
                self.session.extracted_data.update({k: v for k, v in tag_data.items() if v})

            # Animate status updates
            checks = ["Text extraction", "SKU identification",
                       "Manufacturer detection", "Format verification"]
            for i, chk in enumerate(checks):
                time.sleep(0.6)
                has_data = False
                if i == 0:
                    has_data = True  # always complete
                elif i == 1:
                    has_data = bool(self.session.extracted_data.get("sku"))
                elif i == 2:
                    has_data = bool(self.session.extracted_data.get("manufacturer"))
                elif i == 3:
                    has_data = bool(self.session.extracted_data.get("sku") or
                                    self.session.extracted_data.get("manufacturer"))
                mark = "done" if has_data else "none"
                self._ui(lambda idx=i, m=mark, c=chk: self._update_ocr_status(idx, m, c))

            time.sleep(0.5)
            self._ui(lambda: self._show_ocr_results(step))

        threading.Thread(target=bg_ocr, daemon=True).start()

    def _update_ocr_status(self, idx, status, check_name):
        if idx < len(self._ocr_status_labels):
            lbl = self._ocr_status_labels[idx]
            if status == "done":
                lbl.config(text=f"  + {check_name} complete", fg=COLORS["success"])
            else:
                lbl.config(text=f"  - {check_name} (not found)", fg=COLORS["warning"])

    # ==================================================================
    # SCREEN 8: OCR RESULTS
    # ==================================================================
    def _show_ocr_results(self, step):
        self._clear()
        self._title_bar(f"STEP {step['num']} of 5 — TAG DATA EXTRACTED", step)

        body = tk.Frame(self.content_frame, bg=COLORS["bg"])
        body.pack(expand=True)

        tk.Label(
            body, text="Detected information:",
            font=("Consolas", 13, "bold"), fg=COLORS["text"], bg=COLORS["bg"],
        ).pack(pady=(10, 20))

        data = self.session.extracted_data
        fields = [
            ("SKU", data.get("sku") or "(not detected)"),
            ("Manufacturer", data.get("manufacturer") or "(not detected)"),
            ("Size", data.get("size") or "(not detected)"),
            ("Country", data.get("country") or "(not detected)"),
            ("Material", data.get("material") or "(not detected)"),
        ]

        for label, value in fields:
            row = tk.Frame(body, bg=COLORS["bg"])
            row.pack(fill="x", padx=40, pady=3)
            tk.Label(
                row, text=f"{label}:", font=("Consolas", 12, "bold"),
                fg=COLORS["text_dim"], bg=COLORS["bg"], width=15, anchor="e",
            ).pack(side="left")
            detected = value != "(not detected)"
            tk.Label(
                row, text=f"  {value}",
                font=("Consolas", 12),
                fg=COLORS["success"] if detected else COLORS["warning"],
                bg=COLORS["bg"], anchor="w",
            ).pack(side="left")

        tk.Label(
            body, text="\nIs this correct?",
            font=("Consolas", 12), fg=COLORS["text"], bg=COLORS["bg"],
        ).pack(pady=10)

        btn_row = tk.Frame(body, bg=COLORS["bg"])
        btn_row.pack(pady=10)

        self._btn(
            btn_row, "RETAKE PHOTO",
            lambda s=step: self._show_capture_screen(s),
            color=COLORS["warning"],
        ).pack(side="left", padx=15)

        self._btn(
            btn_row, "CONTINUE",
            lambda s=step: self._advance_after_step(s),
            color=COLORS["success"],
        ).pack(side="left", padx=15)

    # ==================================================================
    # SCREEN 15: VERIFICATION PROCESSING
    # ==================================================================
    def _show_verification_processing(self):
        self._clear()
        self._title_bar("VERIFYING AUTHENTICATION")

        body = tk.Frame(self.content_frame, bg=COLORS["bg"])
        body.pack(expand=True)

        tk.Label(
            body, text="Analyzing images and data...",
            font=("Consolas", 14), fg=COLORS["warning"], bg=COLORS["bg"],
        ).pack(pady=(20, 15))

        self._verify_labels = []
        checks = [
            "SKU lookup in database",
            "Logo placement verified",
            "Tag format verified",
            "UV features checked",
            "Calculating confidence...",
        ]
        for chk in checks:
            lbl = tk.Label(
                body, text=f"  ... {chk}",
                font=("Consolas", 11), fg=COLORS["text_dim"], bg=COLORS["bg"],
            )
            lbl.pack(pady=2, anchor="w", padx=40)
            self._verify_labels.append(lbl)

        def bg_verify():
            # Run full verification
            verify_merchandise(self.session)
            cert = generate_certificate(self.session)
            v = self.session.verification

            # Animate check results
            results = [
                v["sku_in_database"],
                v["logo_verified"],
                v["tag_format_verified"],
                v["uv_features_verified"],
            ]
            names = [
                "SKU lookup in database",
                "Logo placement verified",
                "Tag format verified",
                "UV features checked",
            ]

            for i, (ok, name) in enumerate(zip(results, names)):
                time.sleep(0.7)
                self._ui(lambda idx=i, passed=ok, n=name: self._update_verify(idx, passed, n))

            # Final confidence
            time.sleep(0.5)
            conf = v["confidence_score"]
            self._ui(lambda: self._update_verify(
                4, True, f"Confidence: {conf:.1f}%"
            ))

            time.sleep(1.0)
            if v["status"] == "CHECKS_PASSED":
                self._ui(lambda: self._show_success(cert))
            else:
                self._ui(lambda: self._show_failed())

        threading.Thread(target=bg_verify, daemon=True).start()

    def _update_verify(self, idx, passed, name):
        if idx < len(self._verify_labels):
            lbl = self._verify_labels[idx]
            if passed:
                lbl.config(text=f"  + {name}", fg=COLORS["success"])
            else:
                lbl.config(text=f"  x {name}", fg=COLORS["error"])

    # ==================================================================
    # SCREEN 16: VERIFICATION SUCCESS
    # ==================================================================
    def _show_success(self, cert):
        self._clear()

        # Big green header
        header = tk.Frame(self.content_frame, bg=COLORS["success"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="SCREENING PASSED",
            font=("Consolas", 20, "bold"), fg="white", bg=COLORS["success"],
        ).pack(expand=True)

        body = tk.Frame(self.content_frame, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, pady=10)

        # Certificate summary
        info_frame = tk.Frame(body, bg=COLORS["surface"], relief="ridge", bd=1)
        info_frame.pack(fill="x", padx=20, pady=10)

        fields = [
            ("Item ID", cert.get("item_id", "")),
            ("SKU", cert.get("sku") or "N/A"),
            ("Manufacturer", cert.get("manufacturer") or "N/A"),
            ("Size", cert.get("size") or "N/A"),
            ("", ""),
            ("Location", cert["screening"]["location"]),
            ("Date", cert["screening"]["date"]),
            ("Time", cert["screening"]["time"]),
            ("", ""),
            ("Screening Score", f"{cert['screening']['screening_score']}%"),
            ("Images", f"{cert.get('images_captured', 0)} of 5 captured"),
        ]

        for label, value in fields:
            if not label:
                tk.Frame(info_frame, bg=COLORS["border"], height=1).pack(fill="x", padx=10, pady=5)
                continue
            row = tk.Frame(info_frame, bg=COLORS["surface"])
            row.pack(fill="x", padx=15, pady=2)
            tk.Label(
                row, text=f"{label}:", font=("Consolas", 11, "bold"),
                fg=COLORS["text_dim"], bg=COLORS["surface"], width=16, anchor="e",
            ).pack(side="left")
            color = COLORS["success"] if label == "Screening Score" else COLORS["text"]
            tk.Label(
                row, text=f"  {value}", font=("Consolas", 11),
                fg=color, bg=COLORS["surface"], anchor="w",
            ).pack(side="left")

        # Screening disclaimer
        tk.Label(
            body,
            text="Screening only — not professional authentication. NEXUS does not certify authenticity.",
            font=("Consolas", 9), fg=COLORS["text_dim"], bg=COLORS["bg"],
            wraplength=600,
        ).pack(pady=(0, 5))

        # Blockchain hash
        bh = cert.get("blockchain", {}).get("hash", "")
        if bh:
            tk.Label(
                body, text=f"Hash: {bh[:32]}...",
                font=("Consolas", 9), fg=COLORS["text_dim"], bg=COLORS["bg"],
            ).pack(pady=5)

        # Buttons
        btn_row = tk.Frame(body, bg=COLORS["bg"])
        btn_row.pack(pady=15)

        self._btn(
            btn_row, "VIEW CERTIFICATE",
            lambda c=cert: self._show_certificate(c),
            color=COLORS["accent"],
        ).pack(side="left", padx=15)

        self._btn(
            btn_row, "NEW SCAN",
            self.show_mode_selection,
            color=COLORS["surface2"],
        ).pack(side="left", padx=15)

    # ==================================================================
    # SCREEN 17: VERIFICATION FAILED
    # ==================================================================
    def _show_failed(self):
        self._clear()

        # Red header
        header = tk.Frame(self.content_frame, bg=COLORS["error"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="SCREENING INCOMPLETE",
            font=("Consolas", 20, "bold"), fg="white", bg=COLORS["error"],
        ).pack(expand=True)

        body = tk.Frame(self.content_frame, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, pady=10)

        tk.Label(
            body, text="Not all screening checks could be completed",
            font=("Consolas", 14), fg=COLORS["text"], bg=COLORS["bg"],
        ).pack(pady=15)

        # Show which checks failed
        v = self.session.verification
        reasons = []
        if not v["sku_in_database"]:
            reasons.append("SKU not in official database")
        if not v["logo_verified"]:
            reasons.append("Logo image missing or invalid")
        if not v["tag_format_verified"]:
            reasons.append("Tag format doesn't match expected")
        if not v["uv_features_verified"]:
            reasons.append("UV security features not captured")

        tk.Label(
            body, text="Reasons:",
            font=("Consolas", 12, "bold"), fg=COLORS["warning"], bg=COLORS["bg"],
        ).pack(pady=(10, 5), anchor="w", padx=40)

        for reason in reasons:
            tk.Label(
                body, text=f"  - {reason}",
                font=("Consolas", 11), fg=COLORS["error"], bg=COLORS["bg"],
            ).pack(anchor="w", padx=50, pady=1)

        tk.Label(
            body, text="\nThis doesn't mean counterfeit —\nmay not be in database yet",
            font=("Consolas", 10), fg=COLORS["text_dim"], bg=COLORS["bg"],
        ).pack(pady=15)

        btn_row = tk.Frame(body, bg=COLORS["bg"])
        btn_row.pack(pady=15)

        self._btn(
            btn_row, "RETRY",
            self._start_session,
            color=COLORS["warning"],
        ).pack(side="left", padx=15)

        self._btn(
            btn_row, "NEW SCAN",
            self.show_mode_selection,
            color=COLORS["surface2"],
        ).pack(side="left", padx=15)

    # ==================================================================
    # SCREEN 18: FULL CERTIFICATE
    # ==================================================================
    def _show_certificate(self, cert):
        self._clear()

        # Header
        status = cert.get("status", "UNKNOWN")
        hdr_color = COLORS["success"] if status == "CHECKS_PASSED" else COLORS["error"]

        header = tk.Frame(self.content_frame, bg=hdr_color, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text=f"NEXUS SCREENING RECORD — {status}",
            font=("Consolas", 14, "bold"), fg="white", bg=hdr_color,
        ).pack(expand=True)

        # Scrollable body
        canvas = tk.Canvas(self.content_frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=COLORS["bg"])

        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")

        # Image thumbnails row
        img_row = tk.Frame(body, bg=COLORS["bg"])
        img_row.pack(pady=10)

        step_labels = ["Logo", "Tag", "Care", "Hang", "UV"]
        for i, (key, path) in enumerate(sorted(cert.get("images", {}).items())):
            col = tk.Frame(img_row, bg=COLORS["surface2"], relief="ridge", bd=1)
            col.pack(side="left", padx=5)
            lbl_name = step_labels[i] if i < len(step_labels) else f"#{i+1}"
            tk.Label(
                col, text=lbl_name, font=("Consolas", 9, "bold"),
                fg=COLORS["text_dim"], bg=COLORS["surface2"],
            ).pack()
            img_lbl = tk.Label(col, bg=COLORS["surface2"], width=15, height=8)
            img_lbl.pack(padx=3, pady=3)
            if path and os.path.exists(path):
                self._show_image(img_lbl, path, max_size=(120, 120))
            else:
                img_lbl.config(text="skipped", fg=COLORS["text_dim"])

        # Certificate details
        detail_frame = tk.Frame(body, bg=COLORS["surface"], relief="ridge", bd=1)
        detail_frame.pack(fill="x", padx=20, pady=10)

        rows = [
            ("Item ID", cert.get("item_id")),
            ("SKU", cert.get("sku") or "N/A"),
            ("Manufacturer", cert.get("manufacturer") or "N/A"),
            ("Size", cert.get("size") or "N/A"),
            ("Country", cert.get("country") or "N/A"),
            ("Material", cert.get("material") or "N/A"),
            ("Barcode", cert.get("barcode") or "N/A"),
            ("", ""),
            ("Location", cert["screening"]["location"]),
            ("Date", cert["screening"]["date"]),
            ("Time", cert["screening"]["time"]),
            ("Screening Score", f"{cert['screening']['screening_score']}%"),
            ("", ""),
            ("Hash", cert["blockchain"]["hash"][:48] + "..."),
            ("Verify URL", cert["blockchain"]["verification_url"]),
        ]

        for label, value in rows:
            if not label:
                tk.Frame(detail_frame, bg=COLORS["border"], height=1).pack(fill="x", padx=10, pady=5)
                continue
            row = tk.Frame(detail_frame, bg=COLORS["surface"])
            row.pack(fill="x", padx=15, pady=2)
            tk.Label(
                row, text=f"{label}:", font=("Consolas", 10, "bold"),
                fg=COLORS["text_dim"], bg=COLORS["surface"], width=14, anchor="e",
            ).pack(side="left")
            tk.Label(
                row, text=f"  {value}", font=("Consolas", 10),
                fg=COLORS["text"], bg=COLORS["surface"], anchor="w",
            ).pack(side="left")

        # Buttons
        btn_row = tk.Frame(body, bg=COLORS["bg"])
        btn_row.pack(pady=15)

        self._btn(btn_row, "CLOSE", self.show_mode_selection, color=COLORS["surface2"]).pack(
            side="left", padx=10
        )
        self._btn(btn_row, "NEW SCAN", self._start_session, color=COLORS["accent"]).pack(
            side="left", padx=10
        )

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def _on_cancel(self):
        self.session = None
        self.show_mode_selection()

    def destroy(self):
        self._stop_live_feed()
        for aid in self._after_ids:
            try:
                self.frame.after_cancel(aid)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Standalone launcher
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()
    root.title("NEXUS — Merchandise Authentication")
    root.geometry("900x750")
    root.configure(bg=COLORS["bg"])

    app = MerchandiseAuthUI(root)

    root.protocol("WM_DELETE_WINDOW", lambda: (app.destroy(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
