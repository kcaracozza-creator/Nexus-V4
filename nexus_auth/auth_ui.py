"""
NEXUS Auth UI — Venue Memorabilia Authentication Interface
Completely separate from TCG shop UI.
Tkinter dark theme, item-type-driven 5-step workflow, Polygon NFT mint + QR cert.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
import os
import io
import logging
from datetime import datetime
from typing import Optional

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import requests

from nexus_auth.item_types import get_items_by_category, get_item, get_categories
from nexus_auth.auth_engine import (
    AuthSession, create_session,
    capture_image, run_authentication,
    DANIELSON_URL,
)
from nexus_auth.nft_minter import mint_or_simulate, generate_qr

logger = logging.getLogger("NEXUS_AUTH_UI")

# ---------------------------------------------------------------------------
# Theme — venue edition (slightly warmer than shop dark theme)
# ---------------------------------------------------------------------------
C = {
    "bg":       "#0a0e14",
    "surface":  "#13181f",
    "surface2": "#1c2330",
    "border":   "#2a3340",
    "accent":   "#4fa3e0",
    "gold":     "#f0c040",
    "success":  "#3dba6c",
    "warning":  "#d4a017",
    "error":    "#e84040",
    "text":     "#dce8f5",
    "dim":      "#6a7d90",
    "uv":       "#8040ff",
    "nft":      "#9945ff",   # Polygon purple
}

FONT_TITLE  = ("Consolas", 18, "bold")
FONT_HEAD   = ("Consolas", 14, "bold")
FONT_BODY   = ("Consolas", 12)
FONT_SMALL  = ("Consolas", 10)
FONT_MONO   = ("Consolas", 9)


class AuthUI:
    """
    Main venue authentication app.
    Can embed in a notebook or run standalone.
    """

    def __init__(self, parent, notebook=None):
        self.parent   = parent
        self.notebook = notebook
        self.session: AuthSession = None
        self._q       = queue.Queue()
        self._after   = []
        self._feed_active = False

        if notebook:
            self.frame = tk.Frame(notebook, bg=C["bg"])
            notebook.add(self.frame, text="  Auth  ")
        else:
            self.frame = tk.Frame(parent, bg=C["bg"])
            self.frame.pack(fill="both", expand=True)

        self.content = tk.Frame(self.frame, bg=C["bg"])
        self.content.pack(fill="both", expand=True, padx=12, pady=12)

        self._poll_queue()
        self.show_home()

    # ------------------------------------------------------------------
    # Thread-safe UI queue
    # ------------------------------------------------------------------
    def _poll_queue(self):
        try:
            for _ in range(30):
                self._q.get_nowait()()
        except queue.Empty:
            pass
        aid = self.frame.after(40, self._poll_queue)
        self._after.append(aid)

    def _ui(self, fn):
        self._q.put(fn)

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _clear(self):
        self._stop_feed()
        for w in self.content.winfo_children():
            w.destroy()

    def _header(self, left_text, right_text="NEXUS AUTHENTICATION"):
        bar = tk.Frame(self.content, bg=C["surface"], height=54)
        bar.pack(fill="x", pady=(0, 12))
        bar.pack_propagate(False)

        tk.Label(bar, text=right_text, font=FONT_SMALL,
                 fg=C["dim"], bg=C["surface"]).pack(side="right", padx=16, pady=8)
        tk.Label(bar, text=left_text, font=FONT_HEAD,
                 fg=C["gold"], bg=C["surface"]).pack(side="left", padx=16, pady=8)

    def _btn(self, parent, text, cmd, color=None, width=22, height=2, **kw):
        bg = color or C["accent"]
        return tk.Button(
            parent, text=text, command=cmd,
            font=FONT_BODY, bg=bg, fg="white",
            activebackground=bg, relief="flat",
            cursor="hand2", width=width, height=height, **kw,
        )

    def _divider(self, parent):
        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=10, pady=8)

    def _step_dots(self, parent, current):
        row = tk.Frame(parent, bg=C["bg"])
        for i in range(1, 6):
            if i < current:
                clr, txt = C["success"], f" {i} "
            elif i == current:
                clr, txt = C["accent"],  f"[{i}]"
            else:
                clr, txt = C["dim"],     f" {i} "
            tk.Label(row, text=txt, font=("Consolas", 14, "bold"),
                     fg=clr, bg=C["bg"]).pack(side="left", padx=6)
        return row

    # ------------------------------------------------------------------
    # Live camera feed
    # ------------------------------------------------------------------
    def _start_feed(self, lbl):
        self._feed_active = True
        self._feed_lbl    = lbl

        def poll():
            while self._feed_active:
                try:
                    r = requests.get(
                        f"{DANIELSON_URL}/api/snapshot?camera=czur", timeout=3
                    )
                    if r.status_code == 200 and PIL_AVAILABLE:
                        img = Image.open(io.BytesIO(r.content))
                        img.thumbnail((660, 480))
                        photo = ImageTk.PhotoImage(img)
                        if self._feed_active:
                            self._ui(lambda p=photo: self._set_feed(p))
                except Exception:
                    pass
                time.sleep(0.14)

        threading.Thread(target=poll, daemon=True).start()

    def _set_feed(self, photo):
        if hasattr(self, "_feed_lbl") and self._feed_lbl.winfo_exists():
            self._feed_lbl.config(image=photo, text="")
            self._feed_lbl._photo = photo

    def _stop_feed(self):
        self._feed_active = False

    def _show_img(self, lbl, path, max_size=(660, 480)):
        if not PIL_AVAILABLE or not path or not os.path.exists(path):
            lbl.config(text="[image unavailable]")
            return
        try:
            img = Image.open(path)
            img.thumbnail(max_size)
            photo = ImageTk.PhotoImage(img)
            lbl.config(image=photo, text="")
            lbl._photo = photo
        except Exception as e:
            lbl.config(text=f"[error: {e}]")


    # ==================================================================
    # SCREEN: HOME
    # ==================================================================
    def show_home(self):
        self._clear()
        self._header("SELECT ITEM TYPE")

        # Scrollable item type grid
        outer = tk.Frame(self.content, bg=C["bg"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body   = tk.Frame(canvas, bg=C["bg"])

        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        categories = get_items_by_category()

        for cat_name, items in categories.items():
            # Category header
            tk.Label(body, text=cat_name.upper(),
                     font=("Consolas", 11, "bold"),
                     fg=C["dim"], bg=C["bg"]).pack(
                         anchor="w", padx=20, pady=(16, 4))
            self._divider(body)

            row_frame = tk.Frame(body, bg=C["bg"])
            row_frame.pack(fill="x", padx=20, pady=4)

            for i, (type_key, item) in enumerate(items):
                col = i % 3
                if col == 0 and i > 0:
                    row_frame = tk.Frame(body, bg=C["bg"])
                    row_frame.pack(fill="x", padx=20, pady=4)

                tile = tk.Frame(row_frame, bg=C["surface2"],
                                highlightbackground=C["border"],
                                highlightthickness=1)
                tile.pack(side="left", padx=6, pady=4, ipadx=10, ipady=8)

                tk.Label(tile, text=item["icon"],
                         font=("Segoe UI Emoji", 24),
                         bg=C["surface2"]).pack()
                tk.Label(tile, text=item["label"],
                         font=FONT_SMALL, fg=C["text"],
                         bg=C["surface2"], wraplength=150).pack(pady=(2, 6))

                tk.Button(
                    tile, text="SELECT",
                    command=lambda k=type_key: self._start_auth(k),
                    font=("Consolas", 9, "bold"),
                    bg=C["accent"], fg="white",
                    activebackground=C["accent"],
                    relief="flat", cursor="hand2",
                    width=14,
                ).pack()

    # ==================================================================
    # START AUTH SESSION
    # ==================================================================
    def _start_auth(self, type_key: str):
        self.session = create_session(type_key)
        item = get_item(type_key)
        self._show_briefing(item)

    def _show_briefing(self, item: dict):
        self._clear()
        self._header(f"{item['icon']}  {item['label'].upper()}")

        body = tk.Frame(self.content, bg=C["bg"])
        body.pack(expand=True)

        tk.Label(body, text="5-STEP AUTHENTICATION PROCESS",
                 font=FONT_HEAD, fg=C["gold"], bg=C["bg"]).pack(pady=(20, 10))

        steps = item["steps"]
        for step in steps:
            skip_note = "  (skippable)" if step["skippable"] else ""
            txt = f"  Step {step['num']}:  {step['title']}{skip_note}"
            color = C["dim"] if step["skippable"] else C["text"]
            tk.Label(body, text=txt, font=FONT_BODY,
                     fg=color, bg=C["bg"]).pack(anchor="w", padx=40, pady=2)

        self._divider(body)

        tk.Label(body,
                 text="Each image is reviewed before proceeding.\n"
                      "Certificate + Polygon NFT generated on completion.",
                 font=FONT_SMALL, fg=C["dim"], bg=C["bg"],
                 justify="center").pack(pady=12)

        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(pady=16)

        self._btn(btn_row, "START", self._begin_capture,
                  color=C["success"]).pack(side="left", padx=12)
        self._btn(btn_row, "BACK", self.show_home,
                  color=C["surface2"]).pack(side="left", padx=12)

    def _begin_capture(self):
        item = get_item(self.session.item_type_key)
        self._show_capture(item["steps"][0])


    # ==================================================================
    # CAPTURE SCREEN
    # ==================================================================
    def _show_capture(self, step: dict):
        self._clear()
        self._header(f"STEP {step['num']} — {step['title']}")

        self._step_dots(self.content, step["num"]).pack(pady=(0, 8))

        tk.Label(self.content, text=step["instruction"],
                 font=FONT_BODY, fg=C["text"],
                 bg=C["bg"], justify="center").pack(pady=4)

        if step["detail"]:
            tk.Label(self.content, text=step["detail"],
                     font=FONT_SMALL, fg=C["dim"],
                     bg=C["bg"], justify="center").pack(pady=2)

        # UV indicator
        if step["uv_mode"]:
            tk.Label(self.content, text="⬤  UV MODE — lights will activate",
                     font=FONT_SMALL, fg=C["uv"], bg=C["bg"]).pack(pady=4)

        # Camera feed
        feed_outer = tk.Frame(self.content, bg=C["surface2"],
                              highlightbackground=C["border"],
                              highlightthickness=1)
        feed_outer.pack(pady=8, padx=20)

        feed_lbl = tk.Label(feed_outer,
                            text="Connecting to camera...",
                            font=FONT_SMALL, fg=C["dim"],
                            bg=C["surface2"], width=88, height=26)
        feed_lbl.pack(padx=4, pady=4)
        self._start_feed(feed_lbl)

        btn_row = tk.Frame(self.content, bg=C["bg"])
        btn_row.pack(pady=10)

        if step["skippable"]:
            self._btn(btn_row, "SKIP", lambda s=step: self._skip_step(s),
                      color=C["surface2"], width=14).pack(side="left", padx=10)

        cap_text = "CAPTURE UV PHOTO" if step["uv_mode"] else "CAPTURE PHOTO"
        self._btn(btn_row, cap_text,
                  lambda s=step: self._do_capture(s),
                  color=C["uv"] if step["uv_mode"] else C["accent"],
                  width=20).pack(side="left", padx=10)

    def _do_capture(self, step: dict):
        self._stop_feed()
        self._clear()
        self._header(f"STEP {step['num']} — CAPTURING...")

        tk.Label(self.content, text="📸  Capturing image...",
                 font=FONT_HEAD, fg=C["warning"], bg=C["bg"]).pack(expand=True)

        def bg():
            path = capture_image(self.session, step["key"],
                                 uv_mode=step["uv_mode"])
            self._ui(lambda: self._show_review(step, path))

        threading.Thread(target=bg, daemon=True).start()

    def _skip_step(self, step: dict):
        self.session.images[step["key"]] = None
        self._advance(step)

    # ==================================================================
    # REVIEW SCREEN
    # ==================================================================
    def _show_review(self, step: dict, image_path: Optional[str]):
        self._clear()
        self._header(f"STEP {step['num']} — REVIEW IMAGE")

        self._step_dots(self.content, step["num"]).pack(pady=(0, 8))

        img_lbl = tk.Label(self.content, text="Loading...",
                           bg=C["surface2"], fg=C["dim"],
                           width=88, height=24)
        img_lbl.pack(pady=8, padx=20)

        if image_path:
            self._show_img(img_lbl, image_path)
        else:
            img_lbl.config(
                text="⚠  CAPTURE FAILED\nCheck camera connection and try again",
                fg=C["error"],
            )

        tk.Label(self.content, text=step["review_question"],
                 font=FONT_BODY, fg=C["text"], bg=C["bg"]).pack(pady=8)

        btn_row = tk.Frame(self.content, bg=C["bg"])
        btn_row.pack(pady=10)

        self._btn(btn_row, "RETAKE",
                  lambda s=step: self._show_capture(s),
                  color=C["warning"], width=14).pack(side="left", padx=12)
        self._btn(btn_row, "APPROVE ✓",
                  lambda s=step: self._approve(s),
                  color=C["success"], width=16).pack(side="left", padx=12)

    def _approve(self, step: dict):
        self._advance(step)

    def _advance(self, step: dict):
        item  = get_item(self.session.item_type_key)
        steps = item["steps"]
        idx   = next(i for i, s in enumerate(steps) if s["key"] == step["key"])
        if idx + 1 < len(steps):
            self._show_capture(steps[idx + 1])
        else:
            self._show_processing()


    # ==================================================================
    # PROCESSING SCREEN
    # ==================================================================
    def _show_processing(self):
        self._clear()
        self._header("AUTHENTICATING...")

        body = tk.Frame(self.content, bg=C["bg"])
        body.pack(expand=True)

        tk.Label(body, text="Analyzing captures and generating certificate...",
                 font=FONT_BODY, fg=C["warning"], bg=C["bg"]).pack(pady=(20, 16))

        steps_txt = [
            "Running OCR on signature and tag images",
            "Computing SHA-256 image fingerprint",
            "Scoring authentication confidence",
            "Generating certificate",
            "Preparing Polygon NFT mint",
        ]

        self._proc_labels = []
        for txt in steps_txt:
            lbl = tk.Label(body, text=f"  ···  {txt}",
                           font=FONT_SMALL, fg=C["dim"], bg=C["bg"])
            lbl.pack(anchor="w", padx=40, pady=2)
            self._proc_labels.append(lbl)

        def bg():
            cert = run_authentication(self.session)

            def animate(i, ok, txt):
                if i < len(self._proc_labels):
                    color = C["success"] if ok else C["error"]
                    mark  = "  ✓  " if ok else "  ✗  "
                    self._proc_labels[i].config(
                        text=f"{mark}{txt}", fg=color)

            checks = [
                (True,  "OCR complete"),
                (True,  f"Hash: {self.session.auth_hash[:20] if self.session.auth_hash else '---'}..."),
                (cert["authentication"]["confidence"] >= 60, f"Confidence: {cert['authentication']['confidence']}%"),
                (True,  f"Certificate: {cert['item_id']}"),
                (True,  "Minting NFT to Polygon..."),
            ]

            for i, (ok, txt) in enumerate(checks):
                time.sleep(0.6)
                self._ui(lambda idx=i, o=ok, t=txt: animate(idx, o, t))

            # Mint NFT (real or simulated)
            nft_result = mint_or_simulate(cert)
            if nft_result.get("tx_hash"):
                self.session.nft_tx = nft_result["tx_hash"]
                cert["blockchain"]["nft_tx"] = nft_result["tx_hash"]

            # Generate QR
            qr_bytes = generate_qr(cert, nft_result)

            time.sleep(0.8)
            if cert["authentication"]["confidence"] >= 60:
                self._ui(lambda: self._show_success(cert, nft_result, qr_bytes))
            else:
                self._ui(lambda: self._show_failed(cert))

        threading.Thread(target=bg, daemon=True).start()

    # ==================================================================
    # SUCCESS SCREEN
    # ==================================================================
    def _show_success(self, cert: dict, nft_result: dict, qr_bytes: Optional[bytes]):
        self._clear()

        # Big green banner
        banner = tk.Frame(self.content, bg=C["success"], height=64)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        item = get_item(self.session.item_type_key)
        tk.Label(banner,
                 text=f"{item['icon']}  AUTHENTICATED  {item['icon']}",
                 font=("Consolas", 20, "bold"),
                 fg="white", bg=C["success"]).pack(expand=True)

        body = tk.Frame(self.content, bg=C["bg"])
        body.pack(fill="both", expand=True, pady=10)

        # Split: cert details left, QR right
        split = tk.Frame(body, bg=C["bg"])
        split.pack(fill="both", expand=True, padx=20)

        left = tk.Frame(split, bg=C["surface"],
                        highlightbackground=C["border"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=4)

        right = tk.Frame(split, bg=C["surface"],
                         highlightbackground=C["border"], highlightthickness=1)
        right.pack(side="right", fill="y", pady=4, ipadx=10, ipady=10)

        # Left: certificate details
        auth = cert["authentication"]
        ocr  = cert.get("ocr_data", {})

        rows = [
            ("Item ID",     cert["item_id"]),
            ("Type",        f"{item['icon']} {item['label']}"),
            ("",            ""),
            ("Date",        auth["date"]),
            ("Time",        auth["time"]),
            ("Operator",    auth["operator"]),
            ("",            ""),
            ("Confidence",  f"{auth['confidence']}%"),
            ("Images",      f"{cert['images_captured']} / 5 captured"),
        ]

        # Add any OCR data that was found
        if ocr.get("serial_number"):
            rows += [("", ""), ("Serial #", ocr["serial_number"])]
        if ocr.get("grader"):
            rows += [("Grader", f"{ocr['grader']} {ocr.get('grade', '')}".strip())]
        if ocr.get("year"):
            rows += [("Year", ocr["year"])]
        if ocr.get("edition"):
            rows += [("Edition", ocr["edition"])]

        rows += [
            ("", ""),
            ("Hash",        cert["blockchain"]["hash"][:32] + "..."),
            ("Network",     cert["blockchain"]["network"]),
        ]
        if nft_result.get("tx_hash"):
            rows += [("TX", nft_result["tx_hash"][:24] + "...")]
        if nft_result.get("simulated"):
            rows += [("NFT", "DEMO MODE — configure wallet to go live")]

        for label, value in rows:
            if not label:
                tk.Frame(left, bg=C["border"], height=1).pack(fill="x", padx=8, pady=4)
                continue
            row = tk.Frame(left, bg=C["surface"])
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=f"{label}:",
                     font=("Consolas", 10, "bold"),
                     fg=C["dim"], bg=C["surface"],
                     width=12, anchor="e").pack(side="left")
            color = C["success"] if label == "Confidence" else C["text"]
            tk.Label(row, text=f"  {value}",
                     font=FONT_MONO, fg=color,
                     bg=C["surface"], anchor="w").pack(side="left")

        # Right: QR code
        tk.Label(right, text="Scan for NFT Certificate",
                 font=FONT_SMALL, fg=C["nft"], bg=C["surface"]).pack(pady=(8, 4))

        if qr_bytes and PIL_AVAILABLE:
            try:
                img = Image.open(io.BytesIO(qr_bytes))
                img = img.resize((200, 200))
                photo = ImageTk.PhotoImage(img)
                qr_lbl = tk.Label(right, image=photo, bg=C["surface"])
                qr_lbl.pack(padx=10, pady=4)
                qr_lbl._photo = photo
            except Exception:
                tk.Label(right, text="[QR unavailable]",
                         font=FONT_SMALL, fg=C["dim"],
                         bg=C["surface"]).pack(pady=20)
        else:
            tk.Label(right, text="nexus.io/auth/\n" + cert["item_id"],
                     font=FONT_MONO, fg=C["accent"],
                     bg=C["surface"]).pack(pady=20)

        tk.Label(right, text=f"nexus.io/auth/{cert['item_id']}",
                 font=FONT_MONO, fg=C["dim"],
                 bg=C["surface"], wraplength=220).pack(pady=(0, 8))

        # Bottom buttons
        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(pady=12)

        self._btn(btn_row, "NEW SCAN", self.show_home,
                  color=C["accent"], width=18).pack(side="left", padx=12)
        self._btn(btn_row, "VIEW FULL CERT",
                  lambda c=cert: self._show_cert(c),
                  color=C["surface2"], width=18).pack(side="left", padx=12)

    # ==================================================================
    # FAILED SCREEN
    # ==================================================================
    def _show_failed(self, cert: dict):
        self._clear()

        banner = tk.Frame(self.content, bg=C["error"], height=64)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="⚠  AUTHENTICATION FAILED",
                 font=("Consolas", 20, "bold"),
                 fg="white", bg=C["error"]).pack(expand=True)

        body = tk.Frame(self.content, bg=C["bg"])
        body.pack(expand=True)

        score = self.session.scoring
        reasons = []
        if not score["front_captured"]:
            reasons.append("Primary face image missing or too small")
        if not score["signature_captured"]:
            reasons.append("Signature image missing or unclear")
        if not score["uv_captured"]:
            reasons.append("UV scan not completed")

        tk.Label(body,
                 text=f"Confidence score: {score['confidence_score']}% (minimum 60%)",
                 font=FONT_BODY, fg=C["warning"], bg=C["bg"]).pack(pady=(20, 10))

        if reasons:
            tk.Label(body, text="Missing:", font=("Consolas", 12, "bold"),
                     fg=C["text"], bg=C["bg"]).pack(anchor="w", padx=40)
            for r in reasons:
                tk.Label(body, text=f"  —  {r}",
                         font=FONT_BODY, fg=C["error"],
                         bg=C["bg"]).pack(anchor="w", padx=50, pady=2)

        tk.Label(body,
                 text="\nNote: Failed authentication ≠ counterfeit.\n"
                      "Item may be authentic but scan was incomplete.",
                 font=FONT_SMALL, fg=C["dim"], bg=C["bg"],
                 justify="center").pack(pady=16)

        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(pady=10)

        self._btn(btn_row, "RETRY",
                  lambda: self._begin_capture(),
                  color=C["warning"], width=14).pack(side="left", padx=12)
        self._btn(btn_row, "NEW SCAN", self.show_home,
                  color=C["surface2"], width=14).pack(side="left", padx=12)


    # ==================================================================
    # FULL CERTIFICATE SCREEN
    # ==================================================================
    def _show_cert(self, cert: dict):
        self._clear()

        status    = cert.get("status", "UNKNOWN")
        hdr_color = C["success"] if status == "AUTHENTICATED" else C["error"]

        banner = tk.Frame(self.content, bg=hdr_color, height=52)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        item = get_item(self.session.item_type_key)
        tk.Label(banner,
                 text=f"NEXUS AUTHENTICATION CERTIFICATE — {item['icon']} {item['label'].upper()}",
                 font=("Consolas", 13, "bold"),
                 fg="white", bg=hdr_color).pack(expand=True)

        # Scrollable body
        outer  = tk.Frame(self.content, bg=C["bg"])
        outer.pack(fill="both", expand=True, padx=10, pady=6)

        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body   = tk.Frame(canvas, bg=C["bg"])

        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Thumbnail row
        img_row = tk.Frame(body, bg=C["bg"])
        img_row.pack(pady=10)

        labels = ["Front", "Signature", "Tag", "Detail", "UV"]
        keys   = ["front", "signature", "tag", "detail", "uv"]
        for i, (key, lbl_txt) in enumerate(zip(keys, labels)):
            path = cert.get("images", {}).get(key)
            col  = tk.Frame(img_row, bg=C["surface2"],
                            highlightbackground=C["border"],
                            highlightthickness=1)
            col.pack(side="left", padx=5)
            tk.Label(col, text=lbl_txt, font=FONT_MONO,
                     fg=C["dim"], bg=C["surface2"]).pack(pady=2)
            img_lbl = tk.Label(col, bg=C["surface2"], width=16, height=8)
            img_lbl.pack(padx=3, pady=3)
            if path and os.path.exists(path):
                self._show_img(img_lbl, path, max_size=(130, 110))
            else:
                img_lbl.config(text="—", fg=C["dim"])

        # Details
        self._divider(body)

        auth = cert["authentication"]
        ocr  = cert.get("ocr_data", {})
        bc   = cert.get("blockchain", {})

        all_rows = [
            ("Item ID",     cert.get("item_id")),
            ("Type",        f"{item['icon']} {item['label']}"),
            ("Status",      status),
            ("",            ""),
            ("Date",        auth["date"]),
            ("Time",        auth["time"]),
            ("Operator",    auth["operator"]),
            ("",            ""),
            ("Confidence",  f"{auth['confidence']}%"),
            ("Images",      f"{cert['images_captured']} / 5"),
            ("",            ""),
        ]

        # OCR fields
        for field_key in ["serial_number", "cert_number", "grader", "grade",
                          "player_name", "team", "year", "edition", "manufacturer"]:
            val = ocr.get(field_key)
            if val:
                all_rows.append((field_key.replace("_", " ").title(), val))

        if ocr.get("text_raw"):
            all_rows += [("", ""), ("OCR Raw", ocr["text_raw"][:120] + "...")]

        all_rows += [
            ("",            ""),
            ("Hash",        bc.get("hash", "")),
            ("Network",     bc.get("network", "Polygon")),
            ("NFT TX",      bc.get("nft_tx") or "Pending"),
            ("Verify",      bc.get("verification_url", "")),
        ]

        detail = tk.Frame(body, bg=C["surface"],
                          highlightbackground=C["border"],
                          highlightthickness=1)
        detail.pack(fill="x", padx=20, pady=8)

        for label, value in all_rows:
            if not label:
                tk.Frame(detail, bg=C["border"], height=1).pack(fill="x", padx=8, pady=4)
                continue
            row = tk.Frame(detail, bg=C["surface"])
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=f"{label}:",
                     font=("Consolas", 10, "bold"),
                     fg=C["dim"], bg=C["surface"],
                     width=16, anchor="e").pack(side="left")
            color = C["success"] if label == "Status" and value == "AUTHENTICATED" else C["text"]
            tk.Label(row, text=f"  {value}",
                     font=FONT_MONO, fg=color,
                     bg=C["surface"], anchor="w",
                     wraplength=600).pack(side="left")

        # Bottom buttons
        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(pady=16)

        self._btn(btn_row, "NEW SCAN", self.show_home,
                  color=C["accent"], width=16).pack(side="left", padx=10)
        self._btn(btn_row, "CLOSE", self.show_home,
                  color=C["surface2"], width=14).pack(side="left", padx=10)

    # ------------------------------------------------------------------
    def destroy(self):
        self._stop_feed()
        for aid in self._after:
            try:
                self.frame.after_cancel(aid)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Standalone launcher
# ---------------------------------------------------------------------------
def main():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("NEXUS — Venue Authentication")
    root.geometry("1100x800")
    root.configure(bg=C["bg"])

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar",
                    background=C["surface2"], troughcolor=C["bg"],
                    bordercolor=C["border"], arrowcolor=C["dim"])

    app = AuthUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.destroy(), root.destroy()))
    root.mainloop()
