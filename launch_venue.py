"""
NEXUS Venue Launcher
────────────────────
Boots the memorabilia authentication interface.
Deploy this at card shows, FIFA events, signing sessions.

Usage:
  python launch_venue.py

Hardware: Danielson laptop (192.168.1.219) with Coral TPU + CZUR camera
"""

import sys
import os
import logging

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger("NEXUS_VENUE")


def main():
    logger.info("=" * 55)
    logger.info("  NEXUS AUTHENTICATION — VENUE MODE")
    logger.info("  Memorabilia Auth + Polygon NFT")
    logger.info("=" * 55)

    # Check dependencies
    missing = []
    try:
        import PIL
    except ImportError:
        missing.append("Pillow  →  pip install Pillow")
    try:
        import requests
    except ImportError:
        missing.append("requests  →  pip install requests")

    if missing:
        print("\n⚠  Missing dependencies:")
        for m in missing:
            print(f"   {m}")
        print()

    # Optional
    try:
        import qrcode
    except ImportError:
        logger.warning("qrcode not installed — QR codes disabled. "
                       "Run: pip install qrcode[pil]")
    try:
        import web3
    except ImportError:
        logger.warning("web3 not installed — NFT minting will run in DEMO mode. "
                       "Run: pip install web3")

    import tkinter as tk
    from tkinter import ttk
    from nexus_auth.auth_ui import AuthUI, C

    root = tk.Tk()
    root.title("NEXUS — Venue Authentication")
    root.geometry("1100x820")
    root.configure(bg=C["bg"])
    root.resizable(True, True)

    try:
        icon_path = os.path.join("nexus_v2", "assets", "nexus.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar",
                    background=C["surface2"], troughcolor=C["bg"],
                    bordercolor=C["border"], arrowcolor=C["dim"])

    app = AuthUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.destroy(), root.destroy()))

    logger.info("Venue UI launched.")
    root.mainloop()


if __name__ == "__main__":
    main()
