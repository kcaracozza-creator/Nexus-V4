"""
NEXUS Shop Launcher
───────────────────
Boots the TCG card scanner interface.
Deploy this at card shops, game stores, shows.

Usage:
  python launch_shop.py

Hardware: Danielson laptop (192.168.1.219) with Coral TPU + CZUR camera
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Delegate to existing main entry point
from nexus_v2.main import main

if __name__ == "__main__":
    main()
