#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# NEXUS: Universal Collectibles Recognition and Management System
# ═══════════════════════════════════════════════════════════════════════════════
# 
# Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.
# 
# PATENT PENDING - U.S. Provisional Application Filed November 27, 2025
# Application: 35 U.S.C. § 111(b)
# Classification: G06V 10/00, G06V 30/19, G06N 3/08, G06Q 30/02, H04N 23/00
# 
# This software is proprietary and confidential. Unauthorized copying,
# modification, distribution, or use is strictly prohibited.
# 
# See LICENSE file for full terms.
# ═══════════════════════════════════════════════════════════════════════════════

# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗    ██╗   ██╗██████╗            ║
║   ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝    ██║   ██║╚════██╗           ║
║   ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗    ██║   ██║ █████╔╝           ║
║   ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║    ╚██╗ ██╔╝██╔═══╝            ║
║   ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║     ╚████╔╝ ███████╗           ║
║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝      ╚═══╝  ╚══════╝           ║
║                                                                               ║
║   Universal Collectibles Recognition and Management System                    ║
║   with Adaptive Intelligence                                                  ║
║                                                                               ║
║   Patent Pending - Filed November 27, 2025                                    ║
║   Inventor: Kevin Caracozza                                                   ║
║                                                                               ║
║   🏎️ LEXUS → LAMBO: Same power, sleeker body, better architecture 🏎️          ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

NEXUS V3 - Main Entry Point
===========================

Run this file to start NEXUS V3:

    python main.py
    
Or from the parent directory:

    python -m nexus_v2.main
"""

import os
import sys
import logging
from pathlib import Path

# Ensure proper imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """Main entry point for NEXUS V3"""
    
    # Setup logging first
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger('NEXUS')
    
    # Splash
    print()
    print("=" * 60)
    print("  NEXUS V3 - Universal Collectibles Management")
    print("  Patent Pending - Kevin Caracozza")
    print("=" * 60)
    print()
    
    # Try to enable crash protection
    try:
        from crash_protection import init_crash_protection, register_app
        init_crash_protection()
        crash_protection = True
        logger.info("Crash protection: ENABLED")
    except ImportError:
        crash_protection = False
        logger.warning("Crash protection: DISABLED (module not found)")
    
    # Auto-update from Zultan
    try:
        from nexus_v2.updates.update_client import check_and_update, VERSION
        logger.info(f"Version: {VERSION}")
        updated = check_and_update()
        if updated:
            logger.info("UPDATE APPLIED - restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.info(f"Update check skipped: {e}")

    # Check portal license
    try:
        from nexus_v2.portal import is_licensed
        if is_licensed():
            logger.info("License: VALID")
        else:
            logger.info("License: OFFLINE MODE")
    except ImportError:
        logger.warning("Portal module not available")

    # Import and run app
    try:
        from nexus_v2.ui.app import NexusApp

        logger.info("Creating application...")
        app = NexusApp()
        
        if crash_protection:
            register_app(app)
            
        logger.info("Starting application...")
        app.run()
        
    except ImportError as e:
        logger.warning(f"Import warning: {e}")
        logger.info("Some optional features may be disabled")
        # Try to run anyway
        try:
            from nexus_v2.ui.app import NexusApp
            app = NexusApp()
            app.run()
        except Exception as e2:
            logger.error(f"Cannot start application: {e2}")
            logger.error("Install dependencies with: pip install pillow requests")
            sys.exit(1)
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
