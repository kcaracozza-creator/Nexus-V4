#!/usr/bin/env python3
"""
DANIELSON - Unified Scanner Server (Patent Pending)
NEXUS V2 Collectibles Management System
Copyright 2025-2026 Kevin Caracozza - All Rights Reserved
Patent Filed: November 27, 2025

Consolidates SNARF (scanner control) + BROCK (AI recognition) into one machine.
- USB cameras: CZUR + Webcam (no CSI — laptop has no ribbon cable ports)
- Coral M.2 TPU: Art recognition via FAISS embeddings
- OCR: Tesseract (primary), local processing (no network hop)
- ESP32 x2: Arm control (USB0) + LED lightbox (USB1)
- ACR Pipeline: All stages local except ZULTAN metadata lookup

Hardware:
  ESP32 #1 (ARM): /dev/ttyUSB0 — 5-DOF arm via serial bridge
  ESP32 #2 (LIGHT): /dev/ttyUSB1 — WS2812B NeoPixel lightbox
  CZUR (USB): Bulk document scanning
  Webcam (USB): Motion detection, monitoring
  Coral M.2 TPU: Card art embedding + FAISS search
  238GB SSD: ~/danielson (external SATA via USB, M.2 slot = Coral TPU)
"""

import os
import re
import json
import time
import base64
import logging
import itertools
import sqlite3
import subprocess
from io import BytesIO
from datetime import datetime
import threading
from threading import Thread, Event, Lock
from difflib import SequenceMatcher
from typing import Dict, Optional, List, Tuple

import signal
import atexit
import cv2
import numpy as np
import requests
from flask import Flask, jsonify, request, send_file, Response

# Optional serial for ESP32 control
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# Optional Tesseract OCR
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================
SERVER_PORT = int(os.getenv('DANIELSON_PORT', '5001'))
ZULTAN_URL = os.getenv('ZULTAN_URL', 'http://192.168.1.152:8000')
RELAY_URL = os.getenv('RELAY_URL', 'https://narwhal-council-relay.kcaracozza.workers.dev')
SCANNER_ID = 'danielson'
CLAUDE_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# Serial ports (ESP32 + Pro Micro)
ARM_PORT = os.getenv('DANIELSON_ARM_PORT', '/dev/nexus_arm')
LIGHT_PORT = os.getenv('DANIELSON_LIGHT_PORT', '/dev/nexus_light')
TOPLIGHT_PORT = os.getenv('DANIELSON_TOPLIGHT_PORT', '/dev/ttyACM1')
BAUD = 115200

# Storage (local SSD — external SATA via USB, M.2 slot has Coral TPU)
DATA_DIR = os.getenv('NEXUS_DATA', os.path.expanduser('~/danielson'))
SCAN_DIR = os.getenv('DANIELSON_SCAN_DIR', f'{DATA_DIR}/scans')
CACHE_DIR = f'{DATA_DIR}/cache'
INV_DIR = f'{DATA_DIR}/inventory'
MODEL_DIR = f'{DATA_DIR}/models'

# Fixed lightbox ROI in CZUR frame (x, y, w, h) - calibrated once
# This is where the lightbox physically sits in the 3264x2448 CZUR view
LIGHTBOX_FIXED = (1000, 630, 2000, 1700)
_lb_env = os.getenv('LIGHTBOX_RECT', '')
if _lb_env:
    _parts = [int(x) for x in _lb_env.split(',')]
    if len(_parts) == 4:
        LIGHTBOX_FIXED = tuple(_parts)

# Coral TPU model paths
TFLITE_MODEL = os.getenv('DANIELSON_MODEL', f'{MODEL_DIR}/card_embedding_fp32.tflite')
FAISS_INDEX = os.getenv('DANIELSON_FAISS', f'{MODEL_DIR}/faiss_index/card_index_ivf.faiss')
CARD_IDS_FILE = os.getenv('DANIELSON_CARD_IDS', f'{MODEL_DIR}/faiss_index/card_ids.json')
EDGETPU_LIB = '/usr/lib/x86_64-linux-gnu/libedgetpu.so.1'

# ACR confidence threshold
CONFIDENCE_THRESHOLD = 95.0

# pHash database (PRIMARY art matcher - replaces FAISS)
PHASH_DB_FILE = os.getenv('DANIELSON_PHASH_DB', f'{MODEL_DIR}/phash_db.json')

# =============================================================================
# CARD RECOGNITION PROFILES  (NEXUS Card Recognition Profiles v1.0)
# Patent Reference: Claims 66-71
# Regions: (y1_pct, y2_pct, x1_pct, x2_pct) — all 0.0–1.0 fractions
# weights: {field: fraction}  must sum to 1.0
# back_number: True = card number is on the BACK (sports); need two-pass scan
# name_at_bottom: True = name below art (Lorcana); orientation detection adjusted
# =============================================================================
CARD_PROFILES: Dict[str, dict] = {

    # ── TCG ──────────────────────────────────────────────────────────────────
    'mtg': {
        'regions': {
            'name':       (0.07, 0.12, 0.04, 0.78),  # skip frame border, just name bar
            'set_symbol': (0.15, 0.30, 0.70, 0.85),
            'collector':  (0.85, 1.00, 0.00, 0.30),
            'art':        (0.00, 0.50, 0.10, 0.90),
            'mana_cost':  (0.00, 0.08, 0.75, 0.98),
            'type_line':  (0.48, 0.55, 0.05, 0.95),
        },
        'weights':       {'name': 0.50, 'set_symbol': 0.20, 'collector': 0.30},
        'database':      'scryfall',
        'back_number':   False,
        'name_at_bottom': False,
    },

    'pokemon': {
        'regions': {
            'name':       (0.00, 0.10, 0.12, 0.75),
            'hp':         (0.00, 0.10, 0.78, 0.95),
            'set_symbol': (0.90, 0.98, 0.75, 0.92),
            'collector':  (0.90, 0.98, 0.05, 0.35),
            'art':        (0.10, 0.50, 0.08, 0.92),
            'energy_type':(0.02, 0.10, 0.90, 0.98),
            'stage':      (0.00, 0.08, 0.00, 0.15),
        },
        'weights':       {'name': 0.40, 'collector': 0.35, 'set_symbol': 0.25},
        'database':      'pokemontcg',
        'back_number':   False,
        'name_at_bottom': False,
    },

    'yugioh': {
        'regions': {
            'name':       (0.00, 0.08, 0.05, 0.85),
            'attribute':  (0.00, 0.10, 0.88, 1.00),
            'level':      (0.08, 0.14, 0.10, 0.90),
            'set_code':   (0.92, 1.00, 0.55, 0.95),
            'art':        (0.16, 0.58, 0.10, 0.90),
            'atk_def':    (0.90, 0.98, 0.60, 0.95),
            'card_number':(0.92, 1.00, 0.05, 0.30),
        },
        'weights':       {'name': 0.45, 'set_code': 0.30, 'card_number': 0.25},
        'database':      'ygoprodeck',
        'back_number':   False,
        'name_at_bottom': False,
    },

    'fab': {
        'regions': {
            'name':       (0.00, 0.12, 0.08, 0.85),
            'cost':       (0.00, 0.12, 0.00, 0.10),
            'set_code':   (0.92, 1.00, 0.05, 0.40),
            'art':        (0.12, 0.62, 0.05, 0.95),
            'class_icon': (0.00, 0.10, 0.88, 1.00),
        },
        'weights':       {'name': 0.60, 'set_code': 0.40},
        'database':      'fabdb',
        'back_number':   False,
        'name_at_bottom': False,
    },

    'onepiece': {
        'regions': {
            'name':       (0.00, 0.10, 0.10, 0.80),
            'cost':       (0.00, 0.12, 0.00, 0.12),
            'set_code':   (0.92, 1.00, 0.65, 0.95),
            'art':        (0.10, 0.60, 0.05, 0.95),
            'power':      (0.90, 1.00, 0.05, 0.25),
        },
        'weights':       {'name': 0.60, 'set_code': 0.40},
        'database':      'onepiece',
        'back_number':   False,
        'name_at_bottom': False,
    },

    'lorcana': {
        'regions': {
            'name':       (0.65, 0.72, 0.10, 0.90),   # ← Name is BELOW the art
            'cost':       (0.00, 0.12, 0.00, 0.15),
            'set_code':   (0.92, 1.00, 0.05, 0.30),
            'art':        (0.00, 0.65, 0.05, 0.95),
            'strength':   (0.90, 1.00, 0.00, 0.15),
            'willpower':  (0.90, 1.00, 0.85, 1.00),
        },
        'weights':       {'name': 0.60, 'set_code': 0.40},
        'database':      'lorcana',
        'back_number':   False,
        'name_at_bottom': True,
    },

    'digimon': {
        'regions': {
            'name':       (0.00, 0.10, 0.15, 0.85),
            'cost':       (0.00, 0.12, 0.00, 0.12),
            'set_code':   (0.92, 1.00, 0.60, 0.95),
            'art':        (0.10, 0.55, 0.05, 0.95),
            'dp':         (0.88, 0.95, 0.75, 0.95),
            'level':      (0.00, 0.10, 0.88, 1.00),
        },
        'weights':       {'name': 0.60, 'set_code': 0.40},
        'database':      'digimon',
        'back_number':   False,
        'name_at_bottom': False,
    },

    # ── Sports — by manufacturer/product ─────────────────────────────────────
    'topps_baseball_modern': {
        'regions': {
            'name':       (0.85, 0.95, 0.05, 0.70),
            'team':       (0.88, 0.98, 0.70, 1.00),
            'art':        (0.05, 0.80, 0.05, 0.95),
        },
        'weights':       {'name': 0.70, 'team': 0.30},
        'database':      'tcdb',
        'back_number':   True,
        'name_at_bottom': True,
    },

    'topps_baseball_vintage': {
        'regions': {
            'name':       (0.80, 0.92, 0.10, 0.90),
            'team':       (0.90, 0.98, 0.10, 0.90),
            'art':        (0.05, 0.75, 0.10, 0.90),
        },
        'weights':       {'name': 0.70, 'team': 0.30},
        'database':      'tcdb',
        'back_number':   True,
        'name_at_bottom': True,
    },

    'topps_chrome': {
        'regions': {
            'name':       (0.85, 0.95, 0.05, 0.70),
            'team':       (0.88, 0.98, 0.70, 1.00),
            'art':        (0.05, 0.80, 0.05, 0.95),
        },
        'weights':       {'name': 0.70, 'team': 0.30},
        'database':      'tcdb',
        'back_number':   True,
        'name_at_bottom': True,
    },

    'panini_prizm': {
        'regions': {
            'name':       (0.82, 0.92, 0.05, 0.75),
            'team':       (0.90, 0.98, 0.05, 0.50),
            'card_number':(0.90, 0.98, 0.70, 0.95),
            'art':        (0.00, 0.80, 0.00, 1.00),
        },
        'weights':       {'name': 0.70, 'card_number': 0.30},
        'database':      'tcdb',
        'back_number':   False,
        'name_at_bottom': True,
    },

    'panini_donruss': {
        'regions': {
            'name':       (0.75, 0.85, 0.10, 0.90),
            'team':       (0.85, 0.95, 0.05, 0.25),
            'art':        (0.05, 0.70, 0.05, 0.95),
        },
        'weights':       {'name': 0.80, 'team': 0.20},
        'database':      'tcdb',
        'back_number':   True,
        'name_at_bottom': True,
    },

    'panini_select': {
        'regions': {
            'name':       (0.78, 0.88, 0.10, 0.85),
            'card_number':(0.90, 0.98, 0.65, 0.95),
            'art':        (0.00, 0.75, 0.05, 0.95),
        },
        'weights':       {'name': 0.70, 'card_number': 0.30},
        'database':      'tcdb',
        'back_number':   False,
        'name_at_bottom': True,
    },

    'upper_deck_hockey': {
        'regions': {
            'name':       (0.85, 0.93, 0.05, 0.75),
            'team':       (0.85, 0.95, 0.75, 0.98),
            'card_number':(0.92, 1.00, 0.05, 0.30),
            'art':        (0.00, 0.82, 0.00, 1.00),
        },
        'weights':       {'name': 0.70, 'card_number': 0.30},
        'database':      'tcdb',
        'back_number':   False,
        'name_at_bottom': True,
    },

    'bowman_chrome': {
        'regions': {
            'name':       (0.82, 0.92, 0.08, 0.80),
            'team':       (0.90, 0.98, 0.08, 0.50),
            'card_number':(0.90, 0.98, 0.65, 0.95),
            'art':        (0.05, 0.80, 0.05, 0.95),
            'first_bowman':(0.05, 0.15, 0.05, 0.18),  # "1st" icon — major value flag
        },
        'weights':       {'name': 0.70, 'card_number': 0.30},
        'database':      'tcdb',
        'back_number':   False,
        'name_at_bottom': True,
    },
}

# Aliases — convenience names that map to canonical profiles
CARD_PROFILES['panini_prizm_football']   = CARD_PROFILES['panini_prizm']
CARD_PROFILES['panini_prizm_basketball'] = CARD_PROFILES['panini_prizm']
CARD_PROFILES['topps_baseball']          = CARD_PROFILES['topps_baseball_modern']
CARD_PROFILES['sports']                  = CARD_PROFILES['topps_baseball_modern']


def detect_card_type(image: np.ndarray) -> str:
    """
    Auto-detect card type from image using frame color + layout heuristics.
    Returns a CARD_PROFILES key. Falls back to 'mtg' if inconclusive.

    Detection strategy:
      1. Border color → yellow=pokemon, silver=mtg, black=standard
      2. Frame color (top band) → yugioh color table
      3. Name position → bottom=sports/lorcana, top=tcg
      4. Aspect ratio sanity check
    """
    if image is None or image.size == 0:
        return 'mtg'
    try:
        h, w = image.shape[:2]
        # ── Border color sample (outermost 3% ring) ──────────────────────────
        border_mask = np.zeros((h, w), dtype=np.uint8)
        thick = max(3, int(min(h, w) * 0.03))
        border_mask[:thick, :]  = 255
        border_mask[-thick:, :] = 255
        border_mask[:, :thick]  = 255
        border_mask[:, -thick:] = 255
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        border_pixels = hsv[border_mask > 0]
        if border_pixels.size:
            mean_h = float(np.mean(border_pixels[:, 0]))
            mean_s = float(np.mean(border_pixels[:, 1]))
            mean_v = float(np.mean(border_pixels[:, 2]))
            # Yellow border → Pokemon (H≈20-35, S>80)
            if 15 <= mean_h <= 38 and mean_s > 80:
                return 'pokemon'
            # Very dark border → likely MTG (black border)
            if mean_v < 60:
                pass  # fall through to layout checks

        # ── Top-band frame color → Yu-Gi-Oh ───────────────────────────────────
        top_band = hsv[:int(h * 0.04), :]
        if top_band.size:
            band_h = float(np.mean(top_band[:, :, 0]))
            band_s = float(np.mean(top_band[:, :, 1]))
            # Orange/yellow (H≈10-30) + saturated → YGO effect/normal monster
            if 8 <= band_h <= 32 and band_s > 60:
                return 'yugioh'
            # Purple (H≈130-160) → YGO fusion
            if 130 <= band_h <= 165 and band_s > 50:
                return 'yugioh'

        # ── Name region brightness test (top vs bottom) ────────────────────────
        # Sports/Lorcana have name near bottom; TCGs have name near top.
        top_region  = cv2.cvtColor(image[:int(h*0.15), :], cv2.COLOR_BGR2GRAY)
        bot_region  = cv2.cvtColor(image[int(h*0.80):, :], cv2.COLOR_BGR2GRAY)
        top_text_density = float(np.mean(cv2.Laplacian(top_region, cv2.CV_64F) ** 2))
        bot_text_density = float(np.mean(cv2.Laplacian(bot_region, cv2.CV_64F) ** 2))
        if bot_text_density > top_text_density * 2.0:
            # Text density much higher at bottom → sports or Lorcana
            # Default to topps_baseball_modern until we can distinguish further
            return 'topps_baseball_modern'

    except Exception:
        pass
    return 'mtg'  # Default

# USB cameras (detected at startup)
CAMERAS = {
    'czur': {'device': '/dev/video2', 'resolution': (3264, 2448)},
    'webcam': {'device': '/dev/video0', 'resolution': (1920, 1080)},
}

# Debug mode
DEBUG_MODE = os.getenv('DANIELSON_DEBUG', 'false').lower() == 'true'

# =============================================================================
# NFT MINTER (optional — for server-side minting on confirm)
# =============================================================================
try:
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from nexus_auth.nft_minter import NexusNFTMinter
    _nft_minter = NexusNFTMinter()
    NFT_AVAILABLE = True
except Exception as _e:
    NFT_AVAILABLE = False
    _nft_minter = None

# =============================================================================
# REVIEW QUEUE (in-memory — survives individual scans, cleared on confirm/skip)
# =============================================================================
_review_lock = Lock()
_review_queue = []

def _push_review(scan_result: dict):
    with _review_lock:
        _review_queue.append(scan_result)

def _pop_review() -> dict:
    with _review_lock:
        return _review_queue.pop(0) if _review_queue else None

def _peek_review() -> dict:
    with _review_lock:
        return _review_queue[0] if _review_queue else None

def _clear_review():
    with _review_lock:
        _review_queue.clear()

# =============================================================================
# FLASK APP
# =============================================================================
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [DANIELSON] %(levelname)s: %(message)s'
)
logger = logging.getLogger("DANIELSON")

# Ensure directories exist
for d in [SCAN_DIR, CACHE_DIR, INV_DIR]:
    os.makedirs(d, exist_ok=True)

# =============================================================================
# CORAL TPU + FAISS (from BROCK)
# =============================================================================
coral_interpreter = None
CORAL_LOADED = False
card_ids = []
faiss_index = None

def init_coral():
    """Initialize Coral M.2 TPU for card art embeddings."""
    global coral_interpreter, CORAL_LOADED
    try:
        try:
            from tflite_runtime.interpreter import Interpreter, load_delegate
            logger.info("Using tflite_runtime for Coral TPU")
        except ImportError:
            try:
                from ai_edge_litert.interpreter import Interpreter, load_delegate
                logger.info("Using ai-edge-litert for Coral TPU")
            except ImportError:
                import tensorflow as tf
                Interpreter = tf.lite.Interpreter
                load_delegate = tf.lite.experimental.load_delegate
                logger.info("Using tensorflow for Coral TPU")

        if not os.path.exists(TFLITE_MODEL):
            logger.warning(f"TFLite model not found: {TFLITE_MODEL}")
            return False

        # Try EdgeTPU delegate first, fall back to CPU
        try:
            if os.path.exists(EDGETPU_LIB):
                coral_interpreter = Interpreter(
                    model_path=TFLITE_MODEL,
                    experimental_delegates=[load_delegate(EDGETPU_LIB)]
                )
                CORAL_LOADED = True
                logger.info("Coral M.2 EdgeTPU loaded")
            else:
                raise Exception("EdgeTPU lib not found")
        except Exception as e:
            logger.warning(f"EdgeTPU failed ({e}), falling back to CPU")
            coral_interpreter = Interpreter(model_path=TFLITE_MODEL)
            CORAL_LOADED = False

        coral_interpreter.allocate_tensors()
        logger.info(f"Model loaded: {TFLITE_MODEL}")
        return True

    except Exception as e:
        logger.error(f"Coral init failed: {e}")
        return False


def init_faiss():
    """Load FAISS index and card ID mapping."""
    global faiss_index, card_ids
    try:
        import faiss as faiss_lib
        if not os.path.exists(FAISS_INDEX):
            logger.warning(f"FAISS index not found: {FAISS_INDEX}")
            return False

        faiss_index = faiss_lib.read_index(FAISS_INDEX)
        logger.info(f"FAISS index loaded: {faiss_index.ntotal} vectors")

        if os.path.exists(CARD_IDS_FILE):
            with open(CARD_IDS_FILE, 'r') as f:
                card_ids = json.load(f)
            logger.info(f"Card IDs loaded: {len(card_ids)} entries")

        return True
    except ImportError:
        logger.warning("faiss-cpu not installed — art matching disabled")
        return False
    except Exception as e:
        logger.error(f"FAISS init failed: {e}")
        return False


def extract_embedding(image_path: str) -> Optional[np.ndarray]:
    """Extract art embedding from card image using Coral TPU."""
    if coral_interpreter is None:
        return None
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (224, 224))
        img_normalized = img_resized.astype(np.float32) / 255.0

        input_details = coral_interpreter.get_input_details()
        output_details = coral_interpreter.get_output_details()
        expected_shape = input_details[0]["shape"]

        # Handle NCHW vs NHWC based on model's expected input shape
        if expected_shape[1] == 3:  # NCHW: [1, 3, 224, 224]
            img_batch = np.expand_dims(np.transpose(img_normalized, (2, 0, 1)), axis=0)
        else:  # NHWC: [1, 224, 224, 3]
            img_batch = np.expand_dims(img_normalized, axis=0)

        coral_interpreter.set_tensor(input_details[0]["index"], img_batch)
        coral_interpreter.invoke()

        embedding = coral_interpreter.get_tensor(output_details[0]["index"]).flatten()
        # L2 normalize (norm layer stripped from TFLite for compatibility)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding
    except Exception as e:
        logger.error(f"Embedding extraction failed: {e}")
        return None


def art_match(image_path: str, top_k: int = 5) -> Dict:
    """Run Coral TPU art matching + FAISS search locally."""
    embedding = extract_embedding(image_path)
    if embedding is None:
        return {'success': False, 'confidence': 0.0, 'error': 'Embedding extraction failed'}

    if faiss_index is None:
        return {'success': False, 'confidence': 0.0, 'error': 'FAISS index not loaded'}

    try:
        query = np.array([embedding], dtype=np.float32)
        distances, indices = faiss_index.search(query, top_k)

        results = []
        for i in range(top_k):
            idx = int(indices[0][i])
            distance = float(distances[0][i])
            confidence = 100.0 / (1.0 + distance)
            card_id = card_ids[idx] if idx < len(card_ids) else f"unknown_{idx}"
            results.append({
                "index": idx,
                "card_id": card_id,
                "distance": distance,
                "confidence": round(confidence, 2)
            })

        best = results[0]
        return {
            'success': True,
            'confidence': best['confidence'],
            'best_match': best,
            'all_matches': results,
            'method': 'coral_tpu_faiss' if CORAL_LOADED else 'cpu_faiss',
            'stage': 'art_match'
        }
    except Exception as e:
        logger.error(f"FAISS search failed: {e}")
        return {'success': False, 'confidence': 0.0, 'error': str(e)}


# =============================================================================
# pHASH ART MATCHING (PRIMARY - replaces FAISS for production)
# =============================================================================
# pHash is robust to lighting, no training required, works on physical scans.
# FAISS trained on digital Scryfall images fails on physical cards.

_phash_db: Dict[str, str] = {}  # hash_hex → scryfall_uuid
PHASH_LOADED = False


def init_phash() -> bool:
    """Load pHash database from JSON file."""
    global _phash_db, PHASH_LOADED
    try:
        if not os.path.exists(PHASH_DB_FILE):
            logger.warning(f"pHash DB not found: {PHASH_DB_FILE}")
            logger.warning("Run build_phash_db.py on ZULTAN to generate it")
            return False
        
        with open(PHASH_DB_FILE, 'r') as f:
            _phash_db = json.load(f)
        
        PHASH_LOADED = True
        logger.info(f"pHash DB loaded: {len(_phash_db):,} hashes")
        return True
    except Exception as e:
        logger.error(f"pHash init failed: {e}")
        return False


def _compute_phash(img: np.ndarray) -> str:
    """
    Compute 64-bit DCT perceptual hash from image.
    Returns 16-char hex string.
    """
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
        dct = cv2.dct(resized)
        low = dct[:8, :8].flatten()
        median = np.median(low[1:])  # skip DC component
        bits = (low > median).astype(np.uint8)
        hash_int = sum(int(b) << i for i, b in enumerate(bits))
        return f"{hash_int:016x}"
    except Exception:
        return ""


def _hamming_distance(h1: str, h2: str) -> int:
    """Hamming distance between two 64-bit hex hashes."""
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count('1')
    except:
        return 64


def phash_match(image: np.ndarray, art_region: tuple = None, top_k: int = 5) -> Dict:
    """
    PRIMARY art matcher using perceptual hashing.
    
    Args:
        image: Full card image (BGR)
        art_region: (y1_pct, y2_pct, x1_pct, x2_pct) or None for full image
        top_k: Number of candidates to return
    
    Returns:
        Dict with 'success', 'confidence', 'best_match', 'all_matches'
    """
    if not PHASH_LOADED or not _phash_db:
        return {'success': False, 'confidence': 0.0, 'error': 'pHash DB not loaded'}
    
    # Crop to art region if specified
    if art_region:
        h, w = image.shape[:2]
        y1, y2, x1, x2 = art_region
        crop = image[int(h*y1):int(h*y2), int(w*x1):int(w*x2)]
    else:
        crop = image
    
    if crop is None or crop.size == 0:
        return {'success': False, 'confidence': 0.0, 'error': 'Empty art region'}
    
    # Compute query hash
    query_hash = _compute_phash(crop)
    if not query_hash:
        return {'success': False, 'confidence': 0.0, 'error': 'Hash computation failed'}
    
    # Find closest matches by hamming distance
    distances = []
    for db_hash, uuid in _phash_db.items():
        dist = _hamming_distance(query_hash, db_hash)
        distances.append((dist, uuid, db_hash))
    
    # Sort by distance, take top_k
    distances.sort(key=lambda x: x[0])
    
    results = []
    for dist, uuid, db_hash in distances[:top_k]:
        # Confidence: 64 bits total, lower distance = higher confidence
        # dist=0 → 100%, dist=10 → 84%, dist=20 → 69%
        confidence = (64 - dist) / 64 * 100
        results.append({
            'card_id': uuid,
            'distance': dist,
            'confidence': round(confidence, 1),
            'hash': db_hash,
        })
    
    if not results:
        return {'success': False, 'confidence': 0.0, 'error': 'No matches found'}
    
    best = results[0]
    
    # Strong match: distance < 10 bits (84%+ confidence)
    success = best['distance'] < 15
    
    logger.info(f"[pHash] Best: {best['card_id'][:8]}... dist={best['distance']} ({best['confidence']:.0f}%)")
    
    return {
        'success': success,
        'confidence': best['confidence'],
        'best_match': best,
        'all_matches': results,
        'query_hash': query_hash,
        'method': 'phash',
        'stage': 'art_match',
    }


# =============================================================================
# CARD DETECTION + CROP
# =============================================================================

def crop_to_lightbox(image: np.ndarray) -> np.ndarray:
    """Crop full CZUR frame down to the lightbox region.
    The lightbox is the brightest rectangular area in the frame."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Threshold to find the lit lightbox area
    _, thresh = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        logger.warning("[CROP] No lightbox region found, using full frame")
        return image
    # Largest bright region = lightbox
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    # Sanity: lightbox should be at least 10% of frame
    frame_area = image.shape[0] * image.shape[1]
    if (w * h) < frame_area * 0.1:
        logger.warning("[CROP] Lightbox region too small, using full frame")
        return image
    logger.info(f"[CROP] Lightbox region: {w}x{h} at ({x},{y})")
    return image[y:y+h, x:x+w]


def detect_and_crop_card(image: np.ndarray) -> Optional[np.ndarray]:
    """Detect card edges within lightbox region and crop to card.
    Uses edge detection + contour finding for rectangular card shape."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    # Dilate to close gaps in card border
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Sort by area, look for card-shaped rectangle
    img_area = image.shape[0] * image.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(contour)
        if area < img_area * 0.05:
            break  # too small
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        # Card is a rectangle (4 corners)
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
            # Order: top-left, top-right, bottom-right, bottom-left
            rect = _order_points(pts)
            w = int(max(np.linalg.norm(rect[0] - rect[1]), np.linalg.norm(rect[2] - rect[3])))
            h = int(max(np.linalg.norm(rect[1] - rect[2]), np.linalg.norm(rect[0] - rect[3])))
            # Card aspect ratio ~1.4 (standard TCG), allow some slack
            if w > 0 and h > 0:
                aspect = max(w, h) / min(w, h)
                if 1.1 <= aspect <= 2.0:
                    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
                    M = cv2.getPerspectiveTransform(rect, dst)
                    warped = cv2.warpPerspective(image, M, (w, h))
                    # Ensure portrait orientation (taller than wide)
                    if warped.shape[1] > warped.shape[0]:
                        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
                    logger.info(f"[CROP] Card detected: {warped.shape[1]}x{warped.shape[0]} (aspect={aspect:.2f})")
                    return warped

        # Fallback: bounding rect for large contours
        if area > img_area * 0.15:
            x, y, w, h = cv2.boundingRect(contour)
            logger.info(f"[CROP] Card bbox fallback: {w}x{h}")
            return image[y:y+h, x:x+w]

    return None


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points: top-left, top-right, bottom-right, bottom-left."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).flatten()
    return np.array([
        pts[np.argmin(s)],   # top-left
        pts[np.argmin(d)],   # top-right
        pts[np.argmax(s)],   # bottom-right
        pts[np.argmax(d)],   # bottom-left
    ], dtype=np.float32)


# =============================================================================
# OCR ENGINE (from BROCK — Tesseract, local)
# =============================================================================

# Common MTG OCR corrections
OCR_CORRECTIONS = {
    '0': 'O', '5': 'S', '8': 'B', '@': 'a', '|': 'I',
    'tho': 'the', 'af': 'of', 'ancl': 'and', 'wilh': 'with',
}

MTG_ABILITY_KEYWORDS = {
    'cycling', 'flying', 'trample', 'haste', 'vigilance', 'reach',
    'deathtouch', 'lifelink', 'menace', 'flash', 'hexproof', 'indestructible',
    'defender', 'first strike', 'double strike', 'prowess', 'convoke',
}


def run_ocr(image_path: str) -> Dict:
    """Run local OCR on card image. Crops to name and type regions for accuracy."""
    if not PYTESSERACT_AVAILABLE:
        return {'success': False, 'error': 'pytesseract not installed'}

    try:
        img = cv2.imread(image_path)
        if img is None:
            return {'success': False, 'error': f'Cannot read image: {image_path}'}

        h, w = img.shape[:2]

        # --- REGION-BASED OCR: crop specific card areas ---
        # MTG card layout (portrait, standard frame):
        #   Name:     top 3-10% height, 5-80% width  (dark bg on many frame styles)
        #   Type:     ~55-62% height, 5-80% width
        #   Set/Num:  bottom 92-99% height
        # Multiple crop candidates per region (cards vary slightly in border size)
        region_candidates = {
            'name': [
                (int(h*0.03), int(h*0.10), int(w*0.05), int(w*0.75)),
                (int(h*0.02), int(h*0.11), int(w*0.04), int(w*0.80)),
                (int(h*0.03), int(h*0.09), int(w*0.06), int(w*0.72)),
            ],
            'type': [
                (int(h*0.54), int(h*0.61), int(w*0.05), int(w*0.80)),
                (int(h*0.55), int(h*0.63), int(w*0.05), int(w*0.85)),
                (int(h*0.52), int(h*0.60), int(w*0.05), int(w*0.80)),
            ],
            'set_num': [
                (int(h*0.92), int(h*0.99), int(w*0.03), int(w*0.97)),
                (int(h*0.90), int(h*0.99), int(w*0.03), int(w*0.97)),
            ],
        }

        def _ocr_region(crop, psm=7, min_height=120):
            """Run OCR on a region, handling dark-background frames (invert if dark)."""
            if crop is None or crop.size == 0:
                return '', 0
            # Always upscale to at least min_height for accuracy
            if crop.shape[0] < min_height:
                scale = min_height / crop.shape[0]
                crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            mean_br = gray.mean()
            config = f'--oem 3 --psm {psm}'
            # If region is dark (dark-frame card style), invert so tesseract sees dark text on white
            if mean_br < 100:
                proc = cv2.bitwise_not(gray)
            else:
                proc = crop  # raw color works well for light backgrounds
            text = pytesseract.image_to_string(proc, config=config).strip()
            data = pytesseract.image_to_data(proc, config=config, output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data['conf'] if int(c) > 0]
            avg_conf = sum(confs) / len(confs) if confs else 0
            # If inverted result is poor and background was borderline, try raw color too
            if mean_br < 100 and avg_conf < 30 and len(text) < 3:
                text2 = pytesseract.image_to_string(crop, config=config).strip()
                data2 = pytesseract.image_to_data(crop, config=config, output_type=pytesseract.Output.DICT)
                confs2 = [int(c) for c in data2['conf'] if int(c) > 0]
                avg_conf2 = sum(confs2) / len(confs2) if confs2 else 0
                if avg_conf2 > avg_conf:
                    text, avg_conf = text2, avg_conf2
            return text, avg_conf

        results = {}
        for region_name, candidates in region_candidates.items():
            best_text = ''
            best_conf = 0
            for (y1, y2, x1, x2) in candidates:
                crop = img[y1:y2, x1:x2]
                if crop is None or crop.size == 0:
                    continue
                text, avg_conf = _ocr_region(crop)
                if avg_conf > best_conf and len(text) > len(best_text):
                    best_text = text
                    best_conf = avg_conf
                elif not best_text and text:
                    best_text = text
                    best_conf = avg_conf
                if avg_conf > 60 and len(text) >= 3:
                    break
            results[region_name] = {'text': best_text, 'confidence': round(best_conf, 1)}

        # Full-card OCR: run PSM 6 on the TEXT BOX ONLY (lower ~45% of card, below art).
        # Running PSM 6 on the full card causes the art to generate garbage OCR noise.
        # The text box contains: type line, ability text, flavor text, P/T.
        text_box_y1 = int(h * 0.52)
        text_box_img = img[text_box_y1:, :]
        full_text = pytesseract.image_to_string(text_box_img, config=r'--oem 3 --psm 6')
        full_data = pytesseract.image_to_data(text_box_img, config=r'--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
        full_confs = [int(c) for c in full_data['conf'] if int(c) > 0]
        full_avg = sum(full_confs) / len(full_confs) if full_confs else 0

        # Also run sparse OCR on full card to catch name if region crop missed it
        sparse_text = pytesseract.image_to_string(img, config=r'--oem 3 --psm 11')
        # Merge full_text with sparse_text lines (deduplicated)
        full_text_combined = full_text + chr(10) + sparse_text

        # Extract card name from ability text patterns:
        # "Whenever [Card Name] deals", "if [Card Name] is", "[Card Name]'s", etc.
        # The card's own name appears in its ability text (self-referential)
        _ability_name = ''
        _ability_patterns = [
            r'Whenever\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s+(?:deals|attacks|blocks|becomes|is)',
            r'if\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s+(?:is|has|would)',
            # apostrophe pattern removed (quote conflict),
            r'put\s+(?:a|X|\d+)\s+\w+\s+counter\s+on\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})',
        ]
        # Look in ability text (lower portion of sparse_text)
        _ability_lines = [l.strip() for l in sparse_text.split(chr(10)) if len(l.strip()) > 5]
        _name_candidates = {}
        for _pat in _ability_patterns:
            for _line in _ability_lines:
                _m = re.search(_pat, _line)
                if _m:
                    _cname = _m.group(1).strip()
                    # Validate: 2-4 words, each capitalized, 3-20 chars
                    _words = _cname.split()
                    if 1 <= len(_words) <= 4 and all(w[0].isupper() for w in _words if w):
                        _name_candidates[_cname] = _name_candidates.get(_cname, 0) + 1
        # The most frequently mentioned proper name is likely the card name
        if _name_candidates:
            _best_ability_name = max(_name_candidates, key=_name_candidates.get)
            _best_count = _name_candidates[_best_ability_name]
            if _best_count >= 1:
                _ability_name = _best_ability_name
                logger.info(f"[OCR] Ability text name: '{_ability_name}' (seen {_best_count}x)")

        # Pick card name: prefer ability text name, then region crop, then full text scan
        name_result = results.get('name', {})
        card_name = ''
        name_conf = 0

        # Priority 1: ability text pattern match (self-referential card name)
        if _ability_name and len(_ability_name) >= 3:
            card_name = _ability_name
            name_conf = 85.0  # High confidence: found in own text
            logger.info(f"[OCR] Using ability text name: '{card_name}'")

        # Priority 2: name region crop with decent confidence
        if not card_name and isinstance(name_result, dict) and name_result.get('confidence', 0) > 50:
            card_name = name_result['text']
            name_conf = name_result['confidence']

        if not card_name:
            # Priority 3: Search all lines from full-card OCR
            # A card name is: 2-40 chars, mostly alphabetic, appears in top portion of output
            lines = [l.strip() for l in full_text_combined.split('\n') if l.strip()]
            best_line = ''
            best_score = -1
            for line_idx, line in enumerate(lines[:12]):
                clean = re.sub(r'[^a-zA-Z\s\-\',]', '', line).strip()
                if len(clean) < 3 or len(clean) > 35:
                    continue
                words = clean.split()
                if not words or len(words) > 5:
                    continue
                # Skip lines with repeated character runs (OCR noise artifacts)
                max_run = max((sum(1 for _ in g) for _, g in itertools.groupby(clean.lower())), default=0)
                if max_run > 4:
                    continue
                # Prefer lines where at least one word is capitalized (card names)
                has_cap = any(w[0].isupper() for w in words if w)
                alpha_ratio = len(clean) / max(len(line), 1)
                # Word count penalty: card names are 1-3 words; 4-5 words less likely
                word_penalty = max(0, len(words) - 3) * 0.25
                # Position bonus: earlier lines more likely to be the name
                position_bonus = max(0, (6 - line_idx) * 0.05)
                score = alpha_ratio * (1.5 if has_cap else 1.0) - word_penalty + position_bonus
                if score > best_score:
                    best_score = score
                    best_line = clean
            card_name = best_line
            name_conf = full_avg

        # Clean card name: remove non-alpha junk, keep letters/spaces/hyphens/apostrophes
        card_name = re.sub(r"[^a-zA-Z\s\-',.]", '', card_name).strip()

        # Extract set code and collector number
        set_code = ''
        collector_number = ''
        set_text = results.get('set_num', {}).get('text', '') if isinstance(results.get('set_num'), dict) else ''
        all_text = set_text + '\n' + full_text_combined
        for line in reversed(all_text.split('\n')):
            match = re.search(r'([A-Z]{3,5})?\s*(\d{1,4})\s*/\s*(\d{1,4})', line)
            if match:
                if match.group(1):
                    set_code = match.group(1)
                collector_number = match.group(2)
                break

        # Type line
        type_result = results.get('type', {})
        type_line = type_result.get('text', '') if isinstance(type_result, dict) else ''

        # Overall confidence: weight name region heavily
        overall = name_conf * 0.7 + full_avg * 0.3

        logger.info(f"[OCR] Name: '{card_name}' ({name_conf:.0f}%), Type: '{type_line}', Set: '{set_code}' #{collector_number}")

        return {
            'success': True,
            'card_name': card_name,
            'type_line': type_line,
            'set_code': set_code,
            'collector_number': collector_number,
            'full_text': full_text_combined,
            'overall_confidence': round(overall, 1),
            'method': 'tesseract_regions',
            'word_count': len(full_confs),
            'regions': {k: v for k, v in results.items() if isinstance(v, dict)},
        }
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# REGION-BASED CARD RECOGNITION  (NEXUS Card Recognition Protocol v1.0)
# Patent Reference: Claims 66-71
# =============================================================================
# Stage order (all card types):
#   1. EDGE DETECTION   → adaptive_capture (handled upstream)
#   2. CATEGORY DETECT  → detect_card_type() or user selection
#   3. LOAD PROFILE     → CARD_PROFILES[card_type]
#   4. REGION SCAN      → OCR/hash each targeted region per profile
#   5. CROSS-VALIDATE   → ZULTAN/API lookup with confidence scoring
#   6. CONFIDENCE CHECK → weighted score vs CONFIDENCE_THRESHOLD
# Confidence formula: name_sim(w_name) + ocr_conf(w_collector), weights from profile
# Sports back_number=True: front scan returns needs_back_scan flag

def _binarize(gray: np.ndarray) -> np.ndarray:
    """Otsu binarize, auto-inverts if background is dark. Falls back to adaptive
    thresholding when Otsu produces too many small blobs (textured background)."""
    mean = gray.mean()
    if mean < 128:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Adaptive fallback: too many connected components = textured background (e.g. Theros frame)
    n_labels, _, _, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    if n_labels > 50:
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, blockSize=31, C=10)
        if mean < 128:
            bw = cv2.bitwise_not(bw)
    return bw


def _crop_region(img: np.ndarray, y1_pct, y2_pct, x1_pct, x2_pct,
                 min_height: int = 0) -> np.ndarray:
    """Crop percentage region and optionally upscale to min_height."""
    h, w = img.shape[:2]
    crop = img[int(h * y1_pct):int(h * y2_pct), int(w * x1_pct):int(w * x2_pct)]
    if crop.size == 0:
        return crop
    if min_height and crop.shape[0] < min_height:
        scale = min_height / crop.shape[0]
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return crop


def _ocr_crop(crop: np.ndarray, psm: int = 7) -> tuple:
    """Run Tesseract on a preprocessed crop. Returns (text, avg_confidence)."""
    if crop is None or crop.size == 0:
        return '', 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    bw = _binarize(gray)
    cfg = f'--oem 3 --psm {psm}'
    try:
        text = pytesseract.image_to_string(bw, config=cfg).strip()
        data = pytesseract.image_to_data(bw, config=cfg, output_type=pytesseract.Output.DICT)
        confs = [int(c) for c in data['conf'] if int(c) > 0]
        conf = sum(confs) / len(confs) if confs else 0.0
        return text, conf
    except Exception:
        return '', 0.0


def _art_phash(img: np.ndarray) -> str:
    """64-bit perceptual hash of the art region (DCT-based). Returns bit string."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        small = cv2.resize(gray, (32, 32)).astype(np.float32)
        dct = cv2.dct(small)
        low = dct[:8, :8].flatten()
        med = float(np.median(low))
        return ''.join('1' if v > med else '0' for v in low)
    except Exception:
        return ''


def recognize_card_regions(image_path: str, card_type: str = 'mtg') -> Dict:
    """
    NEXUS Card Recognition Protocol v1.0 — profile-driven primary recognition.

    Loads the region profile for the given card_type, runs targeted OCR on each
    region, then cross-references ZULTAN/the appropriate database.

    Args:
        image_path: Path to the cropped card image (from adaptive_capture).
        card_type:  Key into CARD_PROFILES. Pass 'auto' to use detect_card_type().
    """
    result: Dict = {
        'success': False, 'confidence': 0.0,
        'method': 'region_ocr',
        'card_type': card_type,
        'ocr_name': '', 'ocr_set': '', 'ocr_collector': '', 'art_hash': '',
        'profile': card_type,
    }

    if not PYTESSERACT_AVAILABLE:
        result['error'] = 'pytesseract not installed'
        return result

    img = cv2.imread(image_path)
    if img is None:
        result['error'] = f'Cannot read: {image_path}'
        return result

    # ── 0. Card type auto-detect ──────────────────────────────────────────────
    if card_type == 'auto':
        card_type = detect_card_type(img)
        result['card_type'] = card_type
        result['profile'] = card_type
        logger.info(f'[RECOG] Auto-detected card type: {card_type}')

    profile = CARD_PROFILES.get(card_type, CARD_PROFILES['mtg'])
    regions = profile['regions']
    weights = profile['weights']
    name_at_bottom = profile.get('name_at_bottom', False)

    # ── 1. Orientation detection ──────────────────────────────────────────────
    # Profile-aware: test the profile's actual name region in both 0° and 180°.
    # For cards with name at bottom (sports, Lorcana), the same logic applies —
    # we test the profile's name coordinates, which happen to be near the bottom.
    nr = regions['name']  # (y1, y2, x1, x2)

    def _name_score(im: np.ndarray) -> float:
        """Score name region using red-channel OCR for orientation detection."""
        crop = _crop_region(im, nr[0], nr[1], nr[2], nr[3], min_height=80)
        if crop.size == 0:
            return 0.0
        up = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        _, _, r_ch = cv2.split(up)
        _, bw = cv2.threshold(r_ch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        try:
            data = pytesseract.image_to_data(bw, config='--oem 3 --psm 11',
                                             output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data['conf'] if int(c) > 30]
            texts = [t for t, c in zip(data['text'], data['conf'])
                     if int(c) > 30 and len(t.strip()) >= 2]
            if not confs:
                return 0.0
            avg = sum(confs) / len(confs)
            return avg + min(len(texts), 3) * 5
        except Exception:
            return 0.0

    score_0   = _name_score(img)
    img_180   = cv2.rotate(img, cv2.ROTATE_180)
    score_180 = _name_score(img_180)
    if score_180 > score_0 + 10:
        logger.info(f'[RECOG] Rotated 180° (name score {score_0:.0f}→{score_180:.0f})')
        img = img_180
        cv2.imwrite(image_path, img)  # persist corrected orientation for art_match()

    # ── 2. Name OCR ──────────────────────────────────────────────────────────
    # Multi-strategy: red-channel binarization handles colored frames (MTG gold/orange).
    # PSM 11 (sparse text) finds text anywhere in the crop regardless of frame noise.
    name_text, name_conf = '', 0.0
    y1n, y2n, x1n, x2n = nr

    def _ocr_name_crop(crop_img):
        """OCR a name region using red-channel binarization + PSM 11, fallback to gray."""
        best_t, best_c = '', 0.0
        h_c, w_c = crop_img.shape[:2]
        scale = max(4.0, 400 / h_c)
        up = cv2.resize(crop_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        b_ch, g_ch, r_ch = cv2.split(up)
        gray_ch = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
        for is_red, ch in ((True, r_ch), (False, gray_ch)):
            mean_ch = ch.mean()
            if is_red:
                # Red channel: orange bg=high R=white, dark text=low R=black — always BINARY
                _, bw = cv2.threshold(ch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            elif mean_ch < 128:
                _, bw = cv2.threshold(ch, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            else:
                _, bw = cv2.threshold(ch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            for psm in (11, 7):
                try:
                    raw = pytesseract.image_to_string(bw, config=f'--oem 3 --psm {psm}')
                    data = pytesseract.image_to_data(bw, config=f'--oem 3 --psm {psm}',
                                                     output_type=pytesseract.Output.DICT)
                    confs = [int(c) for c in data['conf'] if int(c) > 0]
                    avg_c = sum(confs) / len(confs) if confs else 0.0
                    # For PSM 11, pick longest clean line
                    lines = [re.sub(r"[^a-zA-Z0-9\s\-',.]", '', l).strip()
                             for l in raw.splitlines()]
                    t = max(lines, key=lambda l: len(l) * (1 + 0.1 * avg_c), default='')
                    if len(t) > len(best_t) or (len(t) == len(best_t) and avg_c > best_c):
                        best_t, best_c = t, avg_c
                    if len(best_t) >= 4 and best_c >= 60:
                        return best_t, best_c
                except Exception:
                    pass
        return best_t, best_c

    for dy in (0.0, -0.02, 0.02):
        crop = _crop_region(img, max(0, y1n+dy), min(1, y2n+dy), x1n, x2n, min_height=80)
        t, c = _ocr_name_crop(crop)
        t = re.sub(r"[^a-zA-Z0-9\s\-',./!]", '', t).strip()
        if len(t) > len(name_text) or (len(t) == len(name_text) and c > name_conf):
            name_text, name_conf = t, c
        if name_conf >= 60 and len(name_text) >= 3:
            break
    result['ocr_name'] = name_text
    logger.info(f'[RECOG] Name: {repr(name_text)} ({name_conf:.0f}%) [profile={card_type}]')

    # ── 3. Collector / Number OCR ─────────────────────────────────────────────
    # Uses profile's 'collector', 'set_code', or 'card_number' region (whichever present).
    # Sports with back_number=True skip this region on the front scan.
    set_code, collector_num = '', ''
    if not profile.get('back_number', False):
        coll_region_key = next(
            (k for k in ('collector', 'set_code', 'card_number') if k in regions), None
        )
        if coll_region_key:
            try:
                cy1, cy2, cx1, cx2 = regions[coll_region_key]
                coll_crop = _crop_region(img, cy1, cy2, cx1, cx2)
                if coll_crop.size:
                    ch = coll_crop.shape[0]
                    scale = max(5.0, 280 / ch)
                    coll_up = cv2.resize(coll_crop, None, fx=scale, fy=scale,
                                         interpolation=cv2.INTER_CUBIC)
                    gray_c = cv2.cvtColor(coll_up, cv2.COLOR_BGR2GRAY)
                    bw_c = _binarize(gray_c)
                    raw6 = pytesseract.image_to_string(bw_c, config='--oem 3 --psm 6').strip()
                    raw7 = pytesseract.image_to_string(bw_c, config='--oem 3 --psm 7').strip()
                    combined = (raw6 + ' ' + raw7).upper()
                    # SET NNN/NNN or SET · NNN/NNN  (TCG format)
                    m = re.search(r'\b([A-Z][A-Z0-9]{1,4})\b.{0,6}(\d{1,4})\s*/\s*\d{1,4}',
                                  combined)
                    if m:
                        set_code = m.group(1)
                        collector_num = str(int(m.group(2)))
                    else:
                        # Number only (sports: NNN, no slash)
                        m2 = re.search(r'(\d{1,4})\s*/?\s*\d{0,4}', combined)
                        if m2:
                            collector_num = str(int(m2.group(1)))
            except Exception as e:
                logger.debug(f'[RECOG] Collector OCR error: {e}')
    else:
        result['needs_back_scan'] = True  # Sports: number on back, flag for two-pass

    result['ocr_set'] = set_code
    result['ocr_collector'] = collector_num
    logger.info(f'[RECOG] Collector: set={repr(set_code)} num={repr(collector_num)}')

    # ── 4. Art pHash ─────────────────────────────────────────────────────────
    art_r = regions.get('art', (0.10, 0.62, 0.08, 0.92))
    art_crop = _crop_region(img, art_r[0], art_r[1], art_r[2], art_r[3])
    result['art_hash'] = _art_phash(art_crop)

    # ── 5. ZULTAN cross-reference + confidence ────────────────────────────────
    # Weight for name vs collector comes from the profile.
    w_name = weights.get('name', 0.60)
    w_coll = weights.get('collector', weights.get('set_code',
                         weights.get('card_number', 0.40)))
    # Normalise so they sum to 1.0 (in case profile has only 2 of 3 fields)
    w_total = w_name + w_coll
    w_name /= w_total
    w_coll /= w_total

    # Path A: Collector exact match → 99% (deterministic unique lookup)
    if set_code and collector_num:
        try:
            meta = _zultan_metadata(set_code=set_code, collector_number=collector_num,
                                    card_name=name_text or None, card_type=card_type)
            if meta.get('success') and meta.get('card_name'):
                result.update({
                    'success': True,
                    'card_name': meta['card_name'],
                    'set_code': meta.get('set_code', set_code),
                    'collector_number': meta.get('collector_number', collector_num),
                    'confidence': 99.0,
                    'method': 'collector_exact',
                    'card': meta.get('card'),
                })
                logger.info(f"[RECOG] Collector exact hit: {meta['card_name']} "
                            f"{set_code}/{collector_num} @ 99%")
                return result
        except Exception as e:
            logger.debug(f'[RECOG] Collector lookup failed: {e}')

    # Path B: Name fuzzy → ZULTAN/API search
    if name_text and len(name_text) >= 3:
        try:
            meta = _zultan_metadata(card_name=name_text, card_type=card_type)
            if meta.get('success') and meta.get('card_name'):
                matched_name = meta['card_name']
                sim = SequenceMatcher(None, name_text.lower(),
                                      matched_name.lower()).ratio()
                # Profile-weighted confidence formula
                conf = (sim * w_name + (name_conf / 100.0) * w_coll) * 100.0

                # Collector bonus: +10 if collector also present and matches
                if collector_num and str(meta.get('collector_number', '')) == collector_num:
                    conf = min(conf + 10.0, 99.0)
                # Partial set-code bonus: +3 if set code matches
                elif set_code and meta.get('set_code', '').upper() == set_code.upper():
                    conf = min(conf + 3.0, 97.0)

                conf = round(conf, 1)
                logger.info(f'[RECOG] Name fuzzy: "{name_text}" → "{matched_name}" '
                            f'sim={sim:.2f} ocr={name_conf:.0f}% → {conf}%')

                if conf >= 60.0:
                    result.update({
                        'success': conf >= CONFIDENCE_THRESHOLD,
                        'card_name': matched_name,
                        'set_code': meta.get('set_code'),
                        'collector_number': meta.get('collector_number'),
                        'confidence': conf,
                        'method': 'name_fuzzy',
                        'card': meta.get('card'),
                    })
                    return result
        except Exception as e:
            logger.debug(f'[RECOG] Name lookup failed: {e}')

    # Path C: Collector number only (no readable name — rare fallback)
    if collector_num and not name_text:
        result['confidence'] = 40.0
        result['ocr_collector'] = collector_num

    return result


# =============================================================================
# ESP32 SERIAL CONTROL
# =============================================================================

# ── V4 Persistent Serial Connections ──────────────────────────────────────

class PersistentSerial:
    """Thread-safe persistent serial connection to ESP32/Pro Micro."""

    def __init__(self, name, port, baud=115200, cdc_mode=False):
        self.name = name
        self.port = port
        self.baud = baud
        self.cdc_mode = cdc_mode  # True for Pro Micro (ATmega32U4 USB CDC)
        self._ser = None
        self._lock = threading.Lock()

    def _ensure_connected(self):
        if self._ser is not None and self._ser.is_open:
            return True
        try:
            if self.cdc_mode:
                # Pro Micro (Leonardo) — constructor form triggers CDC wake-up
                self._ser = serial.Serial(self.port, self.baud, timeout=3, dsrdtr=False, rtscts=False)
                time.sleep(2)  # Pro Micro setup() takes ~1s (NeoPixel init + test flash)
            else:
                # ESP32 — step-by-step with dtr=False to prevent board reset
                self._ser = serial.Serial()
                self._ser.port = self.port
                self._ser.baudrate = self.baud
                self._ser.timeout = 2
                self._ser.dtr = False
                self._ser.rts = False
                self._ser.open()
                time.sleep(0.5)
            # Drain any boot/ready messages
            if self._ser.in_waiting:
                self._ser.read(self._ser.in_waiting)
            logger.info(f"[{self.name}] Connected on {self.port}")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            self._ser = None
            return False

    def send(self, cmd_dict: dict) -> Optional[dict]:
        """Send JSON command, return parsed JSON response."""
        with self._lock:
            if not self._ensure_connected():
                return None
            try:
                msg = json.dumps(cmd_dict) + "\n"
                self._ser.write(msg.encode())
                self._ser.flush()
                raw = self._ser.readline().decode().strip()
                logger.info(f"[{self.name}] {cmd_dict.get('cmd','')} -> {raw}")
                if raw:
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return {"status": "ok", "raw": raw}
                return {"status": "timeout"}
            except serial.SerialException as e:
                logger.error(f"[{self.name}] Serial error: {e}")
                try:
                    self._ser.close()
                except:
                    pass
                self._ser = None
                return None

    def send_text(self, text_cmd: str) -> Optional[dict]:
        """Send text command (newline-terminated), return parsed JSON response.
        Used for Pro Micro which receives text but responds with JSON."""
        with self._lock:
            if not self._ensure_connected():
                return None
            try:
                msg = text_cmd.strip() + "\n"
                self._ser.write(msg.encode())
                self._ser.flush()
                raw = self._ser.readline().decode().strip()
                logger.info(f"[{self.name}] {text_cmd} -> {raw}")
                if raw:
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return {"status": "ok", "raw": raw}
                return {"status": "timeout"}
            except serial.SerialException as e:
                logger.error(f"[{self.name}] Serial error: {e}")
                try:
                    self._ser.close()
                except:
                    pass
                self._ser = None
                return None

    def close(self):
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._ser = None


# Create persistent connections
_arm_serial = PersistentSerial("ARM", ARM_PORT)
_light_serial = PersistentSerial("LIGHT", LIGHT_PORT)
_toplight_serial = PersistentSerial("TOPLIGHT", TOPLIGHT_PORT, cdc_mode=True)


def send_serial(port: str, command: str) -> Optional[str]:
    """Legacy wrapper - converts string to JSON for V4 protocol."""
    logger.warning(f"Legacy send_serial called: {command}")
    return command  # Should not be called anymore


# V4 joint name to PCA9685 channel
V4_JOINT_CHANNEL = {
    "SHOULDER": 1,
    "ELBOW": 2,
    "YAW": 3,
    "PITCH": 4,
}

# Stepper: pulses per degree (tune to your gear ratio)
STEPS_PER_DEGREE = 5


# --- ARM CONTROL (ESP32 #1 via serial bridge or direct) ---

ARM_BRIDGE_URL = os.getenv('ARM_BRIDGE_URL', 'http://localhost:8218')

arm_angles = [90] * 8
arm_angles[5] = 0  # vacuum off
arm_angles[6] = 0  # lift down
base_angle = 0

DEFAULT_ARM_PRESETS = {
    'home':   {"shoulder": 115, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 29, "base": 0},
    'scan':   {"shoulder": 60, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 120, "base": 0},
    'pickup': {"shoulder": 45, "wrist_yaw": 98, "wrist_pitch": 60, "elbow": 127, "base": 0},
    'eject':  {"shoulder": 115, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 29, "base": 90},
    'stack':  {"shoulder": 115, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 29, "base": 180},
}

ARM_PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'arm_presets.json')

def load_arm_presets():
    if os.path.exists(ARM_PRESETS_FILE):
        try:
            with open(ARM_PRESETS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_ARM_PRESETS)

def save_arm_presets(presets):
    try:
        with open(ARM_PRESETS_FILE, 'w') as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception:
        return False

arm_presets = load_arm_presets()


def _parse_arm_text(cmd_str: str) -> Optional[dict]:
    """Convert legacy ARM text commands to V4 JSON dict."""
    parts = cmd_str.strip().split(':')

    if parts[0] == 'ARM':
        if len(parts) >= 2 and parts[1].upper() == 'HOME':
            return {"cmd": "home"}
        if len(parts) >= 3:
            joint = parts[1].upper()
            try:
                angle = int(parts[2])
            except ValueError:
                return None
            ch = V4_JOINT_CHANNEL.get(joint)
            if ch:
                return {"cmd": "servo", "channel": ch, "angle": angle}
        return None

    elif parts[0] == 'VACUUM':
        if len(parts) < 2:
            return None
        action = parts[1].upper()
        if action == 'ON' or action == 'PICK':
            return {"cmd": "relay", "channel": 5, "state": 1}
        elif action == 'OFF':
            return {"cmd": "relay", "channel": 5, "state": 0}
        elif action == 'DROP':
            return {"cmd": "relay", "channel": 6, "state": 1}  # solenoid
        return None

    elif parts[0] == 'STEP':
        if len(parts) >= 3 and parts[1] == 'GOTO':
            try:
                target_angle = int(parts[2])
            except ValueError:
                return None
            global base_angle
            delta = target_angle - base_angle
            steps = abs(delta) * STEPS_PER_DEGREE
            direction = 1 if delta >= 0 else -1
            base_angle = target_angle
            return {"cmd": "move_base", "steps": steps, "dir": direction, "speed": 800}
        return None

    elif parts[0] == 'LIGHTBOX':
        if len(parts) >= 2 and parts[1].upper() == 'OFF':
            return {"cmd": "lightbox_off"}
        if len(parts) >= 4:
            try:
                return {"cmd": "lightbox", "r": int(parts[1]), "g": int(parts[2]), "b": int(parts[3])}
            except ValueError:
                return None
        return None

    return None


def arm_command(command) -> Optional[str]:
    """Send command to arm ESP32 (V4 JSON protocol).
    Accepts a dict (direct V4 JSON) or string (legacy format, auto-converted).
    """
    # Handle VACUUM:DROP specially (needs two sequential commands)
    if isinstance(command, str) and command.strip() == 'VACUUM:DROP':
        _arm_serial.send({"cmd": "relay", "channel": 6, "state": 1})
        time.sleep(0.15)
        resp = _arm_serial.send({"cmd": "relay", "channel": 6, "state": 0})
        return 'OK' if resp else None

    if isinstance(command, dict):
        cmd_dict = command
    else:
        cmd_dict = _parse_arm_text(command)
        if cmd_dict is None:
            logger.warning(f"Unknown arm command: {command}")
            return "ERR:UNKNOWN"

    resp = _arm_serial.send(cmd_dict)
    if resp is None:
        return None
    status = resp.get('status', '')
    if status == 'ok':
        return 'OK'
    elif status == 'pong':
        return 'PONG'
    elif status == 'error':
        return f"ERR:{resp.get('msg', 'unknown')}"
    return resp.get('raw', 'OK')


# --- LIGHTBOX CONTROL (ESP32 #2, /dev/ttyUSB1) ---

# V4 Light ESP32 GPIO pins (matches nexus_light_v4.ino)
LIGHT_GPIO_PINS = [12, 27, 26, 25, 33]


def _parse_light_text(cmd_str: str) -> Optional[dict]:
    """Convert legacy light text commands to V4 JSON dict."""
    cmd_str = cmd_str.strip()
    if cmd_str == 'L1':
        return {"cmd": "all_on", "brightness": 255}
    elif cmd_str == 'L0':
        return {"cmd": "all_off"}
    elif cmd_str.startswith('PRESET:'):
        return {"cmd": "all_on", "brightness": 200}
    elif cmd_str.startswith('CH:'):
        parts = cmd_str.split(':')
        if len(parts) >= 3:
            try:
                ch_idx = int(parts[1])
                val = int(parts[2])
                if 0 <= ch_idx < len(LIGHT_GPIO_PINS):
                    return {"cmd": "set_channel", "channel": LIGHT_GPIO_PINS[ch_idx], "value": val}
            except ValueError:
                pass
    elif cmd_str.startswith('RGB:'):
        parts = cmd_str.split(':')
        if len(parts) >= 5:
            try:
                ch_idx = int(parts[1])
                if 0 <= ch_idx < len(LIGHT_GPIO_PINS):
                    return {"cmd": "rgb", "channel": LIGHT_GPIO_PINS[ch_idx], "r": int(parts[2]), "g": int(parts[3]), "b": int(parts[4])}
            except ValueError:
                pass
    return None


def lightbox_command(command) -> Optional[str]:
    """Send command to lightbox ESP32 (V4 JSON protocol).
    Accepts a dict (direct V4 JSON) or string (legacy format, auto-converted).
    """
    if isinstance(command, dict):
        cmd_dict = command
    else:
        cmd_dict = _parse_light_text(command)
        if cmd_dict is None:
            logger.warning(f"Unknown light command: {command}")
            return "ERR:UNKNOWN"

    resp = _light_serial.send(cmd_dict)
    if resp is None:
        return None
    if resp.get('status') == 'ok':
        return 'OK'
    return resp.get('raw', 'OK')


def lights_on():
    toplight_command("ON")
    toplight_command("B:255")

def lights_off():
    toplight_command("OFF")


# ─── Top Lights (Pro Micro via /dev/ttyACM0) ───────────────────────

def toplight_command(cmd: str) -> Optional[dict]:
    """Send text command to Pro Micro top lights. Returns JSON response."""
    return _toplight_serial.send_text(cmd)

def set_light_preset(preset: str):
    """Set light preset via Pro Micro."""
    p = preset.upper()
    if p in ("PHOTO", "SCAN", "GRADE", "OFF"):
        toplight_command(f"P:{p}")
    else:
        toplight_command("ON")

def set_light_channel(ch: int, val: int):
    toplight_command(f"C:{ch}:{val}:{val}:{val}")

def set_light_rgb(ch: int, r: int, g: int, b: int):
    toplight_command(f"C:{ch}:{r}:{g}:{b}")


# =============================================================================
# USB CAMERA CAPTURE
# =============================================================================

# Shared camera for multi-viewer MJPEG streaming
class SharedCamera:
    """Thread-safe shared camera for multiple MJPEG viewers."""

    def __init__(self, device, width=1920, height=1080):
        self.device = device
        self.width = width
        self.height = height
        self.frame = None
        self.lock = Lock()
        self.running = False
        self._cap = None

    def start(self):
        if self.running:
            return
        self.running = True
        Thread(target=self._capture_loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self._cap:
            self._cap.release()

    def _capture_loop(self):
        dev_num = int(self.device.replace('/dev/video', '')) if '/dev/video' in self.device else 0
        self._cap = cv2.VideoCapture(dev_num)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        while self.running:
            ret, frame = self._cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            time.sleep(0.033)  # ~30fps

        self._cap.release()

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def get_fresh_frame(self, sharpness_threshold=100.0, stable_count=3, timeout_ms=20000):
        """Wait until CZUR firmware delivers a sharp, stable frame.
        Measures Laplacian variance — when sharpness exceeds threshold
        for stable_count consecutive frames, the image is in focus."""
        with self.lock:
            self.frame = None
        deadline = time.time() + (timeout_ms / 1000.0)
        sharp_streak = 0
        best_frame = None
        best_sharpness = 0
        while time.time() < deadline:
            with self.lock:
                if self.frame is None:
                    continue
                frame = self.frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            if sharpness > best_sharpness:
                best_sharpness = sharpness
                best_frame = frame
            if sharpness >= sharpness_threshold:
                sharp_streak += 1
                if sharp_streak >= stable_count:
                    logger.info(f"CZUR settled: sharpness={sharpness:.1f} after {sharp_streak} stable frames")
                    return frame
            else:
                sharp_streak = 0
            time.sleep(0.05)
        # Timeout — return best frame we got
        if best_frame is not None:
            logger.warning(f"CZUR settle timeout, using best frame (sharpness={best_sharpness:.1f})")
        return best_frame

shared_cameras = {}


def get_shared_camera(name: str) -> SharedCamera:
    """Get or create a shared camera by name."""
    if name not in shared_cameras:
        cam_config = CAMERAS.get(name)
        if not cam_config:
            return None
        shared_cameras[name] = SharedCamera(
            cam_config['device'],
            cam_config['resolution'][0],
            cam_config['resolution'][1]
        )
        shared_cameras[name].start()
    return shared_cameras[name]


def capture_usb(device='/dev/video0', width=1920, height=1080, suffix="", cam_name=None):
    """Capture from USB camera (CZUR or webcam)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not cam_name:
        cam_name = 'czur' if 'video0' in str(device) else 'webcam'
    filename = f"{SCAN_DIR}/{cam_name}_{timestamp}{suffix}.jpg"

    try:
        # Try fswebcam first (handles auto-exposure well)
        skip = 20 if 'czur' in cam_name.lower() else 10
        cmd = [
            'fswebcam', '-d', str(device), '--no-banner',
            '-r', f'{width}x{height}', '-S', str(skip), filename
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(filename):
            logger.info(f"USB captured: {filename} ({os.path.getsize(filename)} bytes)")
            return filename

        # Fallback: OpenCV capture
        logger.warning("fswebcam failed, trying OpenCV")
        frame = get_best_frame(device, count=5, width=width, height=height)
        if frame is not None:
            cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if os.path.exists(filename):
                logger.info(f"OpenCV captured: {filename}")
                return filename

        logger.error(f"USB capture failed for {device}")
        return None
    except Exception as e:
        logger.error(f"USB capture error: {e}")
        return None


def get_best_frame(device, count=5, width=1920, height=1080):
    """Capture multiple frames, return the one with least glare."""
    camera = None
    try:
        dev_num = int(device.replace('/dev/video', '')) if isinstance(device, str) and '/dev/video' in device else int(device or 0)
        camera = cv2.VideoCapture(dev_num)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not camera.isOpened():
            return None

        # Let auto-exposure settle
        for _ in range(15):
            camera.read()
            time.sleep(0.03)

        frames = []
        for _ in range(count):
            ret, frame = camera.read()
            if ret and frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                glare_score = np.sum(gray > 250)
                frames.append((glare_score, frame))
                time.sleep(0.05)

        if not frames:
            return None
        frames.sort(key=lambda x: x[0])
        return frames[0][1]
    except Exception as e:
        logger.error(f"get_best_frame failed: {e}")
        return None
    finally:
        if camera is not None:
            camera.release()


def calculate_sharpness(image_path):
    """Calculate image sharpness using Laplacian variance."""
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0
        return cv2.Laplacian(img, cv2.CV_64F).var()
    except Exception:
        return 0


def select_best_image(images):
    """Select the sharpest image from a list."""
    best, best_score = None, 0
    for img_path in images:
        if img_path and os.path.exists(img_path):
            score = calculate_sharpness(img_path)
            if score > best_score:
                best_score = score
                best = img_path
    return best


# =============================================================================
# MOTION DETECTION + AUTO-SCAN
# =============================================================================

autoscan_running = False
autoscan_thread = None
last_scan_result = None
card_present = False


def detect_motion(frame1, frame2, threshold=5000):
    """Detect motion between two frames."""
    if frame1 is None or frame2 is None:
        return False
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    return np.sum(thresh > 0) > threshold


def motion_monitor_loop():
    """Background thread: webcam motion → auto-scan → art match → OCR."""
    global autoscan_running, card_present, last_scan_result

    logger.info("Motion monitor started — place card to auto-scan")
    set_light_preset('SCAN')
    last_frame = None
    settle_frames = 0

    while autoscan_running:
        try:
            cam = get_shared_camera('webcam')
            frame = cam.get_frame() if cam else None
            if frame is None:
                time.sleep(0.5)
                continue

            if last_frame is not None:
                motion = detect_motion(last_frame, frame, threshold=8000)
                if motion:
                    settle_frames = 0
                else:
                    settle_frames += 1
                    if settle_frames >= 3 and not card_present:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        if np.mean(gray) > 30:
                            card_present = True
                            logger.info("Card settled — running ACR pipeline")
                            set_light_preset('PHOTO')
                            time.sleep(2.0)

                            result = run_acr_pipeline()
                            last_scan_result = result
                            if result.get('success'):
                                logger.info(f"ACR result: {result.get('card_name')} ({result.get('confidence'):.1f}%)")
                            set_light_preset('SCAN')
                            time.sleep(1)

                    elif settle_frames > 10 and card_present:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        if np.mean(gray) < 25:
                            card_present = False
                            settle_frames = 0
                            logger.info("Card removed — ready for next")

            last_frame = frame.copy()
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"Motion monitor error: {e}")
            time.sleep(1)

    lights_off()
    logger.info("Motion monitor stopped")


# =============================================================================
# ACR PIPELINE (all local except ZULTAN metadata)
# =============================================================================

def run_acr_pipeline(image_path: Optional[str] = None, card_type: str = 'mtg') -> Dict:
    """
    Automated Card Recognition pipeline (NEXUS Card Recognition Protocol):
    1. Capture (adaptive: lights, CZUR, quality gate)
    2. Region OCR — Name + Collector → ZULTAN cross-ref  ≥95% → done
    3. FAISS Art Match — validates 60-94% OCR partials, or takes over when OCR misses
       • OCR + FAISS agree  → boosted confidence → done
       • FAISS only ≥95%   → done
    4. Claude Vision API   — last resort when all else is below 70%
    """
    start_time = time.time()
    stages_run = []
    result = {
        'success': False,
        'card_name': None,
        'set_code': None,
        'collector_number': None,
        'confidence': 0.0,
        'stage': None,
        'method': None,
        'card_type': card_type,
        'stages': {},
    }

    # Stage 1: Adaptive Capture (lights + quality gate — CZUR handles its own crop)
    # try/finally ensures lights always off even if capture throws unexpectedly.
    stages_run.append('capture')
    try:
        if not image_path:
            capture_result = adaptive_capture(camera_name='czur', max_attempts=3)
            image_path = capture_result.get('image_path')
            result['stages']['capture'] = {
                'success': image_path is not None,
                'image_path': image_path,
                'quality': capture_result.get('quality', {}),
                'attempts': capture_result.get('attempts', 0),
                'adjustments': capture_result.get('adjustments', []),
            }
            if not image_path:
                result['error'] = 'Adaptive capture failed'
                result['stages_run'] = stages_run
                result['elapsed_ms'] = int((time.time() - start_time) * 1000)
                return result
        else:
            result['stages']['capture'] = {'success': True, 'image_path': image_path}
        result['image_path'] = image_path
    finally:
        lights_off()

    # ── Stage 2: Region OCR Recognition (PRIMARY) ────────────────────────────
    # Name OCR + Collector OCR → ZULTAN cross-reference.
    # Works on ALL cards (all eras). Collector is a bonus for newer sets only.
    stages_run.append('region_ocr')
    recog = recognize_card_regions(image_path, card_type=card_type)
    result['stages']['region_ocr'] = recog
    recog_conf = recog.get('confidence', 0)
    recog_name = recog.get('card_name', '')

    if recog.get('success') and recog_conf >= CONFIDENCE_THRESHOLD:
        result.update({
            'success': True,
            'card_name': recog_name,
            'set_code': recog.get('set_code'),
            'collector_number': recog.get('collector_number'),
            'confidence': recog_conf,
            'stage': 'region_ocr',
            'method': recog.get('method'),
            'card': recog.get('card'),
            'stages_run': stages_run,
            'elapsed_ms': int((time.time() - start_time) * 1000),
        })
        logger.info(f"[ACR] Region OCR hit: {recog_name!r} @ {recog_conf:.1f}% in {result['elapsed_ms']}ms")
        return result

    logger.info(f"[ACR] Region OCR partial: {recog_name!r} @ {recog_conf:.1f}% — running art match")

    # ── Stage 3: pHash Art Match (PRIMARY — fast, no training needed) ─────────
    # pHash works on physical scans without retraining. FAISS is fallback.
    stages_run.append('phash')
    img_for_phash = cv2.imread(image_path)
    art_region = CARD_PROFILES.get(card_type, CARD_PROFILES['mtg'])['regions'].get('art')
    phash_result = phash_match(img_for_phash, art_region=art_region) if PHASH_LOADED else {'success': False}
    result['stages']['phash'] = phash_result
    phash_conf = phash_result.get('confidence', 0)

    # Resolve pHash match to card name via ZULTAN
    phash_name, phash_meta, phash_card_id = '', {}, None
    if phash_result.get('success') and phash_conf >= 75.0:
        phash_card_id = phash_result.get('best_match', {}).get('card_id')
        if phash_card_id:
            try:
                phash_meta = _zultan_metadata(card_type=card_type, card_id=phash_card_id,
                                              source_confidence=phash_conf)
                phash_name = phash_meta.get('card_name', '')
            except Exception as e:
                logger.debug(f'[ACR] pHash meta lookup failed: {e}')

    # pHash hit with high confidence
    if phash_conf >= CONFIDENCE_THRESHOLD and phash_meta.get('success'):
        result.update({
            'success': True,
            'card_name': phash_name,
            'set_code': phash_meta.get('set_code'),
            'collector_number': phash_meta.get('collector_number'),
            'confidence': phash_conf,
            'stage': 'phash',
            'method': 'phash',
            'card': phash_meta.get('card'),
            'card_id': phash_card_id,
            'stages_run': stages_run,
            'elapsed_ms': int((time.time() - start_time) * 1000),
        })
        logger.info(f'[ACR] pHash hit: {phash_name!r} @ {phash_conf:.1f}%')
        return result

    # OCR + pHash cross-validation
    if recog_conf >= 60.0 and phash_conf >= 70.0 and phash_name:
        sim = SequenceMatcher(None, recog_name.lower(), phash_name.lower()).ratio()
        logger.info(f'[ACR] OCR={recog_name!r}({recog_conf:.0f}%) pHash={phash_name!r}({phash_conf:.0f}%) sim={sim:.2f}')
        if sim >= 0.6:
            boosted = min(max(recog_conf, phash_conf) + 3.0, 97.0)
            winner_name = recog_name if recog_conf >= phash_conf else phash_name
            result.update({
                'success': True,
                'card_name': winner_name,
                'set_code': recog.get('set_code') or phash_meta.get('set_code'),
                'collector_number': recog.get('collector_number') or phash_meta.get('collector_number'),
                'confidence': boosted,
                'stage': 'region_ocr+phash',
                'method': 'ocr_phash_agree',
                'card': recog.get('card') or phash_meta.get('card'),
                'card_id': phash_card_id,
                'stages_run': stages_run,
                'elapsed_ms': int((time.time() - start_time) * 1000),
            })
            logger.info(f'[ACR] OCR+pHash agree: {winner_name!r} @ {boosted:.1f}%')
            return result

    # ── Stage 4: FAISS Art Match (FALLBACK — needs retraining for physical scans) ──────
    # Run always after a partial OCR result (60-94%) or OCR miss (<60%).
    # When OCR and FAISS agree, confidence is boosted. When OCR wins alone
    # (and is ≥95%), we already returned above.
    stages_run.append('art_match')
    art = art_match(image_path)
    result['stages']['art_match'] = art
    art_conf = art.get('confidence', 0)

    # Resolve FAISS top match name for cross-validation
    art_name, art_meta, art_card_id = '', {}, None
    if art.get('success') and art_conf >= 70.0:
        art_card_id = art.get('best_match', {}).get('card_id')
        if art_card_id:
            try:
                art_meta = _zultan_metadata(card_type=card_type, card_id=art_card_id,
                                            source_confidence=art_conf)
                art_name = art_meta.get('card_name', '')
            except Exception as e:
                logger.debug(f'[ACR] FAISS meta lookup failed: {e}')

    # Case A: OCR partial (60-94%) + FAISS usable (≥70%) — cross-validate
    if recog_conf >= 60.0 and art_conf >= 70.0 and art_name:
        sim = SequenceMatcher(None, recog_name.lower(), art_name.lower()).ratio()
        logger.info(f'[ACR] OCR={recog_name!r}({recog_conf:.0f}%) FAISS={art_name!r}({art_conf:.0f}%) sim={sim:.2f}')

        if sim >= 0.6:
            # Agreement — boost to max of both + 3, capped at 97
            boosted = min(max(recog_conf, art_conf) + 3.0, 97.0)
            # Prefer OCR name (more precise for disambiguation)
            winner_name = recog_name if recog_conf >= art_conf else art_name
            winner_meta = recog if recog_conf >= art_conf else art_meta
            result.update({
                'success': True,
                'card_name': winner_name,
                'set_code': recog.get('set_code') or art_meta.get('set_code'),
                'collector_number': recog.get('collector_number') or art_meta.get('collector_number'),
                'confidence': boosted,
                'stage': 'region_ocr+faiss',
                'method': 'ocr_faiss_agree',
                'card': recog.get('card') or art_meta.get('card'),
                'card_id': art_card_id,
                'stages_run': stages_run,
                'elapsed_ms': int((time.time() - start_time) * 1000),
            })
            logger.info(f'[ACR] OCR+FAISS agree: {winner_name!r} @ {boosted:.1f}%')
            return result

        else:
            # Disagreement — trust the higher-confidence signal
            logger.info(f'[ACR] OCR/FAISS disagree: OCR={recog_name!r}, FAISS={art_name!r}')
            if art_conf > recog_conf and art_conf >= CONFIDENCE_THRESHOLD and art_meta.get('success'):
                result.update({
                    'success': True,
                    'card_name': art_name,
                    'set_code': art_meta.get('set_code'),
                    'collector_number': art_meta.get('collector_number'),
                    'confidence': art_conf,
                    'stage': 'art_match',
                    'method': art.get('method'),
                    'card': art_meta.get('card'),
                    'card_id': art_card_id,
                    'stages_run': stages_run,
                    'elapsed_ms': int((time.time() - start_time) * 1000),
                })
                logger.info(f'[ACR] FAISS wins disagreement: {art_name!r} @ {art_conf:.1f}%')
                return result
            # OCR wins or neither is confident enough — fall through to Claude

    # Case B: OCR miss (<60%) but FAISS is confident (≥95%)
    elif art_conf >= CONFIDENCE_THRESHOLD and art_meta.get('success'):
        result.update({
            'success': True,
            'card_name': art_name,
            'set_code': art_meta.get('set_code'),
            'collector_number': art_meta.get('collector_number'),
            'confidence': art_conf,
            'stage': 'art_match',
            'method': art.get('method'),
            'card': art_meta.get('card'),
            'card_id': art_card_id,
            'stages_run': stages_run,
            'elapsed_ms': int((time.time() - start_time) * 1000),
        })
        logger.info(f'[ACR] FAISS hit (OCR miss): {art_name!r} @ {art_conf:.1f}%')
        return result

    # ── Stage 4: Claude Vision (last resort — everything below 70%) ───────────
    stages_run.append('claude')
    if CLAUDE_API_KEY:
        try:
            claude = _claude_vision(image_path)
            result['stages']['claude'] = claude
            if claude.get('success'):
                result.update({
                    'success': True,
                    'card_name': claude.get('card_name'),
                    'set_code': claude.get('set_code'),
                    'collector_number': claude.get('collector_number'),
                    'confidence': claude.get('confidence', 85.0),
                    'stage': 'claude_vision',
                    'method': 'claude_api',
                    'stages_run': stages_run,
                    'elapsed_ms': int((time.time() - start_time) * 1000),
                })
                logger.info(f"[ACR] Claude vision: {claude.get('card_name')} in {result['elapsed_ms']}ms")
                return result
        except Exception as e:
            result['stages']['claude'] = {'success': False, 'error': str(e)}

    # All stages exhausted — return best partial result with pick list for UI
    result['error'] = 'All stages below confidence threshold'
    result['stages_run'] = stages_run
    result['elapsed_ms'] = int((time.time() - start_time) * 1000)
    best_conf = 0
    for stage_name, stage_data in result['stages'].items():
        if isinstance(stage_data, dict) and stage_data.get('confidence', 0) > best_conf:
            best_conf = stage_data['confidence']
            result['confidence'] = best_conf
            result['stage'] = stage_name

    # Build possible_matches from all signals so UI can show a pick list
    possible_matches = []

    # First: region OCR result (if any name found)
    if recog_name:
        possible_matches.append({
            'card': recog.get('card', {}),
            'confidence': recog_conf,
            'method': recog.get('method', 'region_ocr'),
        })

    # Then: FAISS candidates resolved via ZULTAN
    seen_ids = set()
    if art_card_id:
        seen_ids.add(art_card_id)
    all_art = art.get('all_matches', [])
    for art_candidate in all_art[:5]:
        cid = art_candidate.get('card_id', '')
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        try:
            meta = _zultan_metadata(card_type=card_type, card_id=cid,
                                    source_confidence=art_candidate.get('confidence', 0))
            if meta.get('success') and meta.get('card_name'):
                possible_matches.append({
                    'card': meta.get('card', {}),
                    'confidence': art_candidate.get('confidence', 0),
                    'method': 'faiss_candidate',
                })
        except Exception:
            pass
        if len(possible_matches) >= 5:
            break

    result['possible_matches'] = possible_matches
    if possible_matches:
        result['card_name'] = possible_matches[0].get('card', {}).get('name', '') or recog_name
        result['card'] = possible_matches[0].get('card', {})
        logger.info(f"[ACR] Near-miss: {len(possible_matches)} candidates, best="
                    f"{result['card_name']!r} @ {best_conf:.1f}%")

    return result



def _normalize_card(card):
    """Normalize card object so both 'set' and 'set_code' exist for UI compatibility."""
    if not isinstance(card, dict):
        return card
    card = card.copy()  # Never mutate caller's dict
    # Ensure 'set' field exists (UI expects card.get('set'))
    if 'set' not in card and 'set_code' in card:
        card['set'] = card['set_code']
    elif 'set_code' not in card and 'set' in card:
        card['set_code'] = card['set']
    # Uppercase set codes
    if card.get('set'):
        card['set'] = card['set'].upper()
    if card.get('set_code'):
        card['set_code'] = card['set_code'].upper()
    # Ensure 'number' alias for collector_number
    if 'number' not in card and 'collector_number' in card:
        card['number'] = card['collector_number']
    return card

def _zultan_metadata(set_code=None, collector_number=None, card_name=None, card_type='mtg', card_id=None, source_confidence=None):
    """Cross-reference against ZULTAN's card databases."""
    # Direct lookup by scryfall UUID (from FAISS art match)
    if card_id:
        try:
            r = requests.get(f'{ZULTAN_URL}/api/{card_type}/card/{card_id}', timeout=10)
            if r.status_code == 200:
                card = r.json()
                if card.get('name'):
                    return {
                        'success': True, 'confidence': source_confidence if source_confidence else 70.0,  # honest pass-through, no inflation
                        'method': 'card_id_lookup',
                        'card': _normalize_card(card), 'card_name': card['name'],
                        'set_code': (card.get('set_code') or card.get('set', '')).upper(),
                        'collector_number': str(card.get('collector_number') or card.get('number', '')),
                    }
        except Exception as e:
            logger.warning(f"[ACR] card_id lookup failed for {card_id}: {e}")

    # Exact lookup by set + collector
    if set_code and collector_number:
        r = requests.get(
            f'{ZULTAN_URL}/api/{card_type}/search',
            params={'q': f'{set_code} {collector_number}'},
            timeout=10
        )
        if r.status_code == 200:
            results = r.json().get('results', [])
            for card in results:
                c_set = (card.get('set_code') or card.get('set', '')).upper()
                c_num = str(card.get('collector_number') or card.get('number', ''))
                if c_set == set_code.upper() and c_num == collector_number:
                    return {
                        'success': True, 'confidence': 99.0,
                        'method': 'exact_set_collector',
                        'card': _normalize_card(card), 'card_name': card.get('name'),
                        'set_code': c_set, 'collector_number': c_num,
                    }

    # Fuzzy name search
    if card_name:
        r = requests.get(
            f'{ZULTAN_URL}/api/{card_type}/search',
            params={'q': card_name}, timeout=10
        )
        if r.status_code == 200:
            results = r.json().get('results', [])
            if results:
                best = results[0]
                similarity = SequenceMatcher(
                    None, card_name.lower(), best.get('name', '').lower()
                ).ratio() * 100
                return {
                    'success': True, 'confidence': similarity,
                    'method': 'name_fuzzy',
                    'card': _normalize_card(best), 'card_name': best.get('name'),
                    'set_code': best.get('set_code') or best.get('set'),
                    'collector_number': str(best.get('collector_number') or best.get('number', '')),
                }

    return {'success': False, 'confidence': 0.0, 'error': 'No params'}


def _claude_vision(image_path: str) -> Dict:
    """Last resort: Claude API vision identification."""
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    r = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': CLAUDE_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        },
        json={
            'model': 'claude-sonnet-4-5-20250929',
            'max_tokens': 300,
            'messages': [{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': img_b64}
                    },
                    {
                        'type': 'text',
                        'text': 'Identify this trading card. Return JSON: {"card_name": "...", "set_code": "...", "collector_number": "...", "card_type": "mtg|pokemon|sports"}'
                    }
                ]
            }]
        },
        timeout=30
    )

    if r.status_code == 200:
        text = r.json()['content'][0]['text']
        # Parse JSON from response
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                'success': True,
                'card_name': data.get('card_name'),
                'set_code': data.get('set_code'),
                'collector_number': data.get('collector_number'),
                'confidence': 85.0,
            }
    return {'success': False, 'error': f'Claude returned {r.status_code}'}


# =============================================================================
# RELAY PUSH (Narwhal Council)
# =============================================================================

def push_to_relay(camera, scan_result=None, card_detected=False, ocr_text=None):
    """Push scan result to Narwhal Council Relay (non-blocking)."""
    def _push():
        try:
            payload = {
                'scanner': SCANNER_ID,
                'camera': camera,
                'card_detected': card_detected,
                'scan_result': scan_result,
                'ocr_text': ocr_text,
            }
            requests.post(f'{RELAY_URL}/camera/push', json=payload, timeout=5)
        except Exception:
            pass
    Thread(target=_push, daemon=True).start()


# =============================================================================
# FLASK ENDPOINTS
# =============================================================================

@app.route('/status')
def status():
    return jsonify({
        "status": "online",
        "name": "DANIELSON",
        "role": "unified_scanner",
        "replaces": ["SNARF", "BROCK"],
        "cameras": list(CAMERAS.keys()),
        "coral_loaded": CORAL_LOADED,
        "faiss_loaded": faiss_index is not None,
        "faiss_vectors": faiss_index.ntotal if faiss_index else 0,
        "card_ids": len(card_ids),
        "ocr_available": PYTESSERACT_AVAILABLE,
        "serial_available": SERIAL_AVAILABLE,
        "arm_port": ARM_PORT,
        "light_port": LIGHT_PORT,
        "toplight_port": TOPLIGHT_PORT,
        "hdd": DATA_DIR,
        "scan_dir": SCAN_DIR,
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok", "name": "DANIELSON", "timestamp": datetime.now().isoformat()})


# --- Camera endpoints ---

@app.route('/api/snapshot')
def snapshot():
    """Get a snapshot from a camera."""
    cam_name = request.args.get('camera', 'webcam')
    cam = get_shared_camera(cam_name)
    if cam is None:
        return jsonify({"error": f"Unknown camera: {cam_name}"}), 404

    frame = cam.get_frame()
    if frame is None:
        return jsonify({"error": "No frame available"}), 503

    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/api/video/stream')
def video_stream():
    """MJPEG video stream."""
    cam_name = request.args.get('camera', 'webcam')

    def generate():
        cam = get_shared_camera(cam_name)
        if cam is None:
            return
        while True:
            frame = cam.get_frame()
            if frame is not None:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                       buffer.tobytes() + b'\r\n')
            time.sleep(0.033)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def _capture_from_shared(cam_name: str, fresh: bool = False) -> Optional[str]:
    """Capture a frame from the shared camera and save to disk.
    fresh=True flushes the buffer and waits for CZUR auto-focus/exposure/crop to settle."""
    cam = get_shared_camera(cam_name)
    if cam is None:
        return None
    frame = cam.get_fresh_frame() if fresh else cam.get_frame()
    if frame is None:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{SCAN_DIR}/{cam_name}_{timestamp}.jpg"
    os.makedirs(SCAN_DIR, exist_ok=True)
    cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if os.path.exists(filename):
        logger.info(f"Shared camera captured: {filename} ({os.path.getsize(filename)} bytes)")
        return filename
    return None



# ---------------------------------------------------------------------------
# Image Quality Assessment + Adaptive Capture
# ---------------------------------------------------------------------------

QUALITY_SHARPNESS_MIN = 80.0      # Laplacian variance
QUALITY_BRIGHTNESS_LOW = 50.0    # mean gray — too dark below this
QUALITY_BRIGHTNESS_HIGH = 180.0   # mean gray — too bright above this
QUALITY_GLARE_MAX_PCT = 2.0       # % pixels > 245 brightness

def assess_image_quality(frame) -> dict:
    """Analyze a captured frame for sharpness, exposure, and glare.
    Returns quality report with pass/fail verdict."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Sharpness — Laplacian variance (same method as get_fresh_frame)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharp_ok = bool(sharpness >= QUALITY_SHARPNESS_MIN)

    # Exposure — mean brightness
    mean_brightness = float(np.mean(gray))
    if mean_brightness < QUALITY_BRIGHTNESS_LOW:
        exposure = "dark"
    elif mean_brightness > QUALITY_BRIGHTNESS_HIGH:
        exposure = "bright"
    else:
        exposure = "ok"

    # Glare — percentage of blown-out pixels (same idea as get_best_frame)
    total_pixels = gray.shape[0] * gray.shape[1]
    glare_pixels = int(np.sum(gray > 245))
    glare_pct = (glare_pixels / total_pixels) * 100.0
    glare_ok = bool(glare_pct <= QUALITY_GLARE_MAX_PCT)

    passed = bool(sharp_ok and exposure == "ok" and glare_ok)

    return {
        "passed": passed,
        "sharp": sharp_ok,
        "sharpness_val": round(float(sharpness), 1),
        "exposure": exposure,
        "mean_brightness": round(mean_brightness, 1),
        "glare": not glare_ok,
        "glare_pct": round(float(glare_pct), 2),
    }


def adaptive_capture(camera_name="czur", max_attempts=3) -> dict:
    """Fixed-crop capture with edge-based card detection.
    Uses LIGHTBOX_FIXED for the known lightbox position in CZUR frame.
    """
    logger.info("[ADAPTIVE] Lights on (PHOTO preset)")
    toplight_command("ON")
    toplight_command("B:255")
    set_light_preset("PHOTO")
    time.sleep(4.0)

    best_frame = None
    best_path = None
    best_sharpness = 0
    best_ocr_words = 0

    for attempt in range(1, max_attempts + 1):
        image_path = _capture_from_shared(camera_name, fresh=True)
        if not image_path:
            czur = CAMERAS.get(camera_name, CAMERAS["czur"])
            image_path = capture_usb(czur["device"], *czur["resolution"], cam_name=camera_name)
        if not image_path:
            logger.warning(f"[ADAPTIVE] Attempt {attempt}: capture failed")
            continue

        frame = cv2.imread(image_path)
        if frame is None:
            logger.warning(f"[ADAPTIVE] Attempt {attempt}: could not read image")
            continue

        fh, fw = frame.shape[:2]
        logger.info(f"[ADAPTIVE] Attempt {attempt}: frame {fw}x{fh}")

        # Crop to fixed lightbox ROI
        cropped = frame
        if LIGHTBOX_FIXED:
            lx, ly, lw, lh = LIGHTBOX_FIXED
            lx = max(0, min(lx, fw - 1))
            ly = max(0, min(ly, fh - 1))
            lw = min(lw, fw - lx)
            lh = min(lh, fh - ly)
            cropped = frame[ly:ly+lh, lx:lx+lw]
            logger.info(f"[ADAPTIVE] Fixed lightbox crop: {lw}x{lh} at ({lx},{ly})")
            cv2.imwrite(os.path.join(SCAN_DIR, "debug_lightbox_crop.jpg"), cropped)

            # Find card via brightness thresholding
            # Card is darker than lightbox surface under top lighting
            gray_crop = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray_crop, 160, 255, cv2.THRESH_BINARY_INV)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            cv2.imwrite(os.path.join(SCAN_DIR, "debug_card_thresh.jpg"), thresh)

            card_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            crop_area = lw * lh

            card_found = False
            for cc in sorted(card_contours, key=cv2.contourArea, reverse=True):
                cx, cy, cw, ch = cv2.boundingRect(cc)
                ca = cw * ch
                pct = (ca / crop_area) * 100
                aspect = max(cw, ch) / max(min(cw, ch), 1)
                logger.info(f"[ADAPTIVE] Contour: {cw}x{ch} area={pct:.1f}% aspect={aspect:.2f}")

                if pct < 5 or pct > 95:
                    continue
                if aspect < 1.05 or aspect > 2.0:
                    continue

                pad = 5
                cx = max(0, cx - pad)
                cy = max(0, cy - pad)
                cw = min(cw + 2 * pad, cropped.shape[1] - cx)
                ch = min(ch + 2 * pad, cropped.shape[0] - cy)
                cropped = cropped[cy:cy+ch, cx:cx+cw]
                logger.info(f"[ADAPTIVE] Card detected: {cw}x{ch} at ({cx},{cy}) aspect={aspect:.2f}")

                debug_rect = frame.copy()
                abs_x, abs_y = lx + cx, ly + cy
                cv2.rectangle(debug_rect, (abs_x, abs_y), (abs_x+cw, abs_y+ch), (0, 255, 0), 4)
                cv2.imwrite(os.path.join(SCAN_DIR, "debug_card_rect.jpg"), debug_rect)
                card_found = True
                break

            if not card_found:
                logger.warning("[ADAPTIVE] No card in lightbox crop, using full ROI")
        else:
            logger.warning("[ADAPTIVE] No LIGHTBOX_FIXED set, using full frame")

        # Auto-rotate if card is landscape (any time width > height, rotate to portrait)
        ch_crop, cw_crop = cropped.shape[:2]
        if cw_crop > ch_crop:
            cropped = cv2.rotate(cropped, cv2.ROTATE_90_CLOCKWISE)
            logger.info(f"[ADAPTIVE] Rotated 90 CW: {cropped.shape[1]}x{cropped.shape[0]}")

        # Deskew: correct card tilt using HoughLinesP on card edges
        # Finds near-vertical card edge lines and computes deviation from 90°
        try:
            _dh, _dw = cropped.shape[:2]
            _gray_d = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            _edges_d = cv2.Canny(_gray_d, 30, 200, apertureSize=3)
            _lines_d = cv2.HoughLinesP(_edges_d, 1, np.pi/180, threshold=200,
                                        minLineLength=int(_dh*0.2), maxLineGap=30)
            if _lines_d is not None:
                _vert_angles = []
                for _l in _lines_d:
                    _x1, _y1, _x2, _y2 = _l[0]
                    _dx, _dy = _x2-_x1, _y2-_y1
                    if abs(_dy) > abs(_dx):  # near-vertical line
                        _ang = np.degrees(np.arctan2(_dy, _dx))
                        # normalize to deviation from vertical
                        _dev = _ang + 90 if _ang < 0 else _ang - 90
                        _vert_angles.append(_dev)
                if _vert_angles:
                    _tilt = float(np.median(_vert_angles))
                    if 0.5 < abs(_tilt) < 20:
                        _center = (_dw // 2, _dh // 2)
                        _M = cv2.getRotationMatrix2D(_center, _tilt, 1.0)
                        cropped = cv2.warpAffine(cropped, _M, (_dw, _dh), borderMode=cv2.BORDER_REPLICATE)
                        logger.info(f"[ADAPTIVE] Deskewed {_tilt:.1f}° (Hough): {_dw}x{_dh}")
        except Exception as _de:
            logger.warning(f"[ADAPTIVE] Deskew failed: {_de}")

        crop_path = image_path.replace(".jpg", "_cropped.jpg")
        cv2.imwrite(crop_path, cropped)
        image_path = crop_path

        quality = assess_image_quality(cropped)
        logger.info(f"[ADAPTIVE] Attempt {attempt}: sharpness={quality['sharpness_val']}, "
                     f"brightness={quality['mean_brightness']}, glare={quality['glare_pct']}%%, "
                     f"passed={quality['passed']}")

        # Count OCR words as a quality signal — more words = better OCR result
        ocr_word_count = 0
        if PYTESSERACT_AVAILABLE:
            try:
                import pytesseract as _pyt_quick
                _quick_text = _pyt_quick.image_to_string(cropped, config='--oem 3 --psm 6')
                ocr_word_count = len([w for w in _quick_text.split() if len(w) >= 3])
                logger.info(f"[ADAPTIVE] Attempt {attempt}: OCR word count={ocr_word_count}")
            except Exception as _e:
                logger.warning(f"[ADAPTIVE] Quick OCR failed: {_e}")

        # Track best frame: prioritize OCR words (readability) over sharpness
        if ocr_word_count > best_ocr_words or (ocr_word_count == best_ocr_words and quality['sharpness_val'] > best_sharpness):
            best_ocr_words = ocr_word_count
            best_sharpness = quality['sharpness_val']
            best_frame = cropped
            best_path = image_path

        # Early return: good quality OR enough OCR words to work with
        if quality['passed'] or ocr_word_count >= 8:
            logger.info(f"[ADAPTIVE] Returning on attempt {attempt} (passed={quality['passed']}, ocr_words={ocr_word_count})")
            return {
                "image_path": image_path,
                "quality": quality,
                "attempts": attempt,
            }

        logger.info("[ADAPTIVE] Waiting for CZUR to settle...")
        time.sleep(3.0)

    logger.warning(f"[ADAPTIVE] All {max_attempts} attempts used, best sharpness={best_sharpness:.1f}")
    if best_path:
        return {
            "image_path": best_path,
            "quality": assess_image_quality(best_frame) if best_frame is not None else {},
            "attempts": max_attempts,
        }
    return {"image_path": None, "quality": {}, "attempts": max_attempts}


@app.route('/api/capture/czur', methods=['POST'])
def capture_czur():
    """Capture from CZUR scanner."""
    filename = _capture_from_shared('czur')
    if not filename:
        # Fallback: try fswebcam/OpenCV direct (camera may not be in shared pool)
        czur = CAMERAS['czur']
        filename = capture_usb(czur['device'], *czur['resolution'], cam_name='czur')
    if filename:
        push_to_relay('czur', scan_result=filename, card_detected=True)
        return jsonify({
            "success": True, "good_read": True,
            "image_path": filename,
            "card_image_b64": _encode_image_b64(filename),
        })
    return jsonify({"success": False, "error": "CZUR capture failed"}), 500


@app.route('/api/capture/quality_test', methods=['POST'])
def capture_quality_test():
    """Capture a frame and return quality assessment without running ACR pipeline.
    Useful for testing lighting adjustments."""
    cam_name = 'czur'
    if request.json:
        cam_name = request.json.get('camera', 'czur')

    # Capture current frame
    image_path = _capture_from_shared(cam_name, fresh=True)
    if not image_path:
        cam = CAMERAS.get(cam_name, CAMERAS['czur'])
        image_path = capture_usb(cam['device'], *cam['resolution'], cam_name=cam_name)

    if not image_path:
        return jsonify({"success": False, "error": "Capture failed"}), 500

    frame = cv2.imread(image_path)
    if frame is None:
        return jsonify({"success": False, "error": "Could not read captured image"}), 500

    quality = assess_image_quality(frame)
    return jsonify({
        "success": True,
        "image_path": image_path,
        "quality": quality,
        "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
        "file_size": os.path.getsize(image_path),
    })


@app.route('/api/capture', methods=['POST'])
def capture():
    """Generic capture from any USB camera."""
    cam_name = request.json.get('camera', 'czur') if request.json else 'czur'
    if cam_name not in CAMERAS:
        return jsonify({"error": f"Unknown camera: {cam_name}"}), 404
    filename = _capture_from_shared(cam_name)
    if not filename:
        cam = CAMERAS[cam_name]
        filename = capture_usb(cam['device'], *cam['resolution'], cam_name=cam_name)
    if filename:
        return jsonify({"success": True, "image_path": filename})
    return jsonify({"success": False, "error": "Capture failed"}), 500


def _encode_image_b64(filepath, max_width=800):
    """Encode image to base64 with optional resize."""
    try:
        img = cv2.imread(filepath)
        if img is None:
            return None
        h, w = img.shape[:2]
        if w > max_width:
            scale = max_width / w
            img = cv2.resize(img, (max_width, int(h * scale)))
        _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"
    except Exception:
        return None


# --- ACR Pipeline endpoint ---

@app.route('/api/acr', methods=['POST'])
def acr_endpoint():
    """Run full ACR pipeline. Optionally pass image_path and card_type in JSON body."""
    data = request.json or {}
    image_path = data.get('image_path')
    card_type = data.get('card_type', 'mtg')
    result = run_acr_pipeline(image_path, card_type=card_type)
    return jsonify(result)


# --- /api/scan alias (Pi5ScannerClient compatibility) ---

@app.route('/api/scan', methods=['POST'])
def scan_endpoint():
    """
    /api/scan — drop-in replacement for legacy Snarf/Brok /api/scan.
    Accepts: {camera: str, mode: str, image_path: str (optional)}
    Runs full ACR pipeline then pushes result to review queue.
    """
    data = request.json or {}
    image_path = data.get('image_path')
    card_type = data.get('card_type', 'mtg')
    result = run_acr_pipeline(image_path, card_type=card_type)
    result.setdefault('filename', result.get('image_path', ''))
    _push_review(result)
    return jsonify(result)


@app.route('/api/multi_scan', methods=['POST'])
def multi_scan_endpoint():
    """
    /api/multi_scan — multi-pass scan alias.
    Danielson is a unified machine so we just run ACR once (no separate passes needed).
    """
    result = run_acr_pipeline(None)
    _push_review(result)
    return jsonify({
        'success': result.get('success', False),
        'best_result': result,
        'passes': {'acr': result},
        'method': 'danielson_unified',
    })


# --- Review queue endpoints ---

@app.route('/api/review', methods=['GET'])
def review_get():
    """Get the current card waiting for operator review.
    Returns both singular 'card' (peek at head) and 'items' list (full queue) so
    the desktop Load Queue and direct callers both get what they need.
    """
    with _review_lock:
        queue_snapshot = list(_review_queue)
    item = queue_snapshot[0] if queue_snapshot else None
    if item:
        return jsonify({
            'success': True,
            'card': item,
            'items': queue_snapshot,
            'queue_depth': len(queue_snapshot),
        })
    return jsonify({'success': False, 'error': 'Queue empty', 'items': [], 'queue_depth': 0})


@app.route('/api/review/confirm', methods=['POST'])
def review_confirm():
    """
    Operator accepted the scanned card.
    Pops from review queue OR accepts inline card data from POST body.
    Writes to inventory JSONL log AND nexus_library.db SQLite.
    Optionally mints NFT.
    """
    data = request.json or {}

    # Try review queue first; fall back to inline data from POST body (fresh scan accept)
    item = _pop_review()
    if not item:
        card_data = data.get('card') or {}
        item = {
            'card_name': data.get('card_name', card_data.get('name', '')),
            'card_type': data.get('card_type', 'mtg'),
            'confidence': data.get('confidence', 0),
            'image_path': data.get('image_path', ''),
            'card': card_data,
            'set_code': data.get('set_code', card_data.get('set', card_data.get('set_code', ''))),
            'collector_number': data.get('collector_number', card_data.get('collector_number', '')),
        }
        if not item['card_name']:
            return jsonify({'success': False, 'error': 'No card data provided'}), 400

    # Merge operator corrections from POST body (condition/foil/lang/name override)
    condition = data.get('condition', 'NM')
    foil = data.get('foil', False)
    lang = data.get('lang', 'EN')
    if data.get('card_name'):
        item['card_name'] = data['card_name']
    if data.get('set_code'):
        item['set_code'] = data['set_code']
    if data.get('collector_number'):
        item['collector_number'] = data['collector_number']

    # Persist to inventory log (one JSON-line per accepted card)
    inv_path = os.path.join(INV_DIR, 'accepted_cards.jsonl')
    entry = {
        **item,
        'accepted_at': datetime.now().isoformat(),
        'operator_notes': data.get('notes', ''),
        'condition': condition,
        'foil': foil,
        'lang': lang,
    }
    try:
        with open(inv_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        logger.warning(f"Inventory JSONL write failed: {e}")

    # Write to SQLite nexus_library.db (what the Collection tab reads)
    try:
        db_dir = os.path.join(DATA_DIR, 'inventory')
        os.makedirs(db_dir, exist_ok=True)
        _db = sqlite3.connect(LIBRARY_DB_PATH)
        _db.execute('''CREATE TABLE IF NOT EXISTS cards (
            call_number TEXT PRIMARY KEY,
            box_id TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0,
            name TEXT NOT NULL DEFAULT '',
            set_code TEXT, set_name TEXT, collector_number TEXT,
            rarity TEXT, colors TEXT, color_identity TEXT,
            mana_cost TEXT, cmc REAL DEFAULT 0,
            type_line TEXT, oracle_text TEXT, power TEXT, toughness TEXT,
            foil INTEGER DEFAULT 0, condition TEXT DEFAULT 'NM',
            language TEXT DEFAULT 'en',
            price REAL DEFAULT 0, price_foil REAL DEFAULT 0,
            price_source TEXT, price_updated TEXT,
            image_url TEXT, image_url_small TEXT,
            art_hash TEXT, scryfall_id TEXT, uuid TEXT,
            cataloged_at TEXT, updated_at TEXT, notes TEXT,
            display INTEGER DEFAULT 0, display_case INTEGER,
            card_type TEXT DEFAULT 'mtg',
            yugioh_id INTEGER, yugioh_type TEXT, yugioh_race TEXT,
            yugioh_attribute TEXT, yugioh_atk INTEGER, yugioh_def INTEGER,
            yugioh_level INTEGER, yugioh_archetype TEXT,
            listing_status TEXT DEFAULT 'available',
            listing_id TEXT, listed_at TEXT, sold_at TEXT, sold_price REAL
        )''')
        card = entry.get('card') or {}
        card_type = entry.get('card_type', 'mtg')
        now = datetime.now().isoformat()
        cn_prefix = {'mtg': 'M', 'pokemon': 'P', 'yugioh': 'Y', 'sports': 'S',
                     'lorcana': 'L', 'onepiece': 'O', 'fab': 'F'}.get(card_type, 'X')
        call_number = f"{cn_prefix}{int(time.time() * 1000)}"
        raw_set = entry.get('set_code') or card.get('set') or card.get('set_code') or ''
        raw_num = entry.get('collector_number') or card.get('collector_number') or card.get('number') or ''
        _db.execute(
            '''INSERT OR REPLACE INTO cards (
                call_number, name, set_code, set_name, collector_number,
                rarity, mana_cost, cmc, type_line, oracle_text,
                power, toughness, foil, condition, language,
                price, price_foil, image_url, image_url_small, scryfall_id,
                cataloged_at, updated_at, card_type, listing_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (
                call_number,
                entry.get('card_name') or card.get('name', ''),
                raw_set.upper() if raw_set else '',
                card.get('set_name', ''),
                str(raw_num),
                card.get('rarity', ''),
                card.get('mana_cost', ''),
                card.get('cmc', 0) or 0,
                card.get('type_line', ''),
                card.get('oracle_text', ''),
                card.get('power', ''),
                card.get('toughness', ''),
                1 if foil else 0,
                condition,
                lang,
                float(card.get('prices', {}).get('usd', 0) or 0),
                float(card.get('prices', {}).get('usd_foil', 0) or 0),
                card.get('image_uris', {}).get('normal', card.get('image_url', '')),
                card.get('image_uris', {}).get('small', card.get('image_url_small', '')),
                card.get('id', card.get('scryfall_id', '')),
                now, now,
                card_type,
                'available',
            )
        )
        _db.commit()
        _db.close()
        logger.info(f"[LIBRARY] Cataloged {call_number}: {entry.get('card_name')}")
        entry['call_number'] = call_number
    except Exception as e:
        logger.error(f"Library DB write failed: {e}")

    # NFT mint (background thread, non-blocking)
    nft_result = None
    if NFT_AVAILABLE and _nft_minter:
        def _do_mint(card_entry):
            try:
                import hashlib, json as _j
                raw = _j.dumps(card_entry, sort_keys=True).encode()
                img_path = card_entry.get('image_path', '')
                if img_path and os.path.exists(img_path):
                    with open(img_path, 'rb') as f:
                        raw += f.read()
                cert_hash = hashlib.sha256(raw).hexdigest()
                result = _nft_minter.mint_or_simulate(
                    item_id=cert_hash[:16],
                    cert_hash=cert_hash,
                    item_name=card_entry.get('card_name', 'Unknown'),
                    item_type='TCG Card',
                    confidence=int(card_entry.get('confidence', 0)),
                    extra_metadata=card_entry,
                )
                logger.info(f"[NFT] Minted: token={result.get('token_id')} tx={result.get('tx_hash', '')[:20]}")
            except Exception as me:
                logger.error(f"[NFT] Mint failed: {me}")
        _threading.Thread(target=_do_mint, args=(entry,), daemon=True).start()

    return jsonify({'success': True, 'card': entry, 'call_number': entry.get('call_number', ''), 'queue_depth': len(_review_queue)})


@app.route('/api/review/skip', methods=['POST'])
def review_skip():
    """Operator rejected / skipped the current card."""
    item = _pop_review()
    if not item:
        return jsonify({'success': False, 'error': 'Nothing in review queue'}), 400
    logger.info(f"[REVIEW] Skipped: {item.get('card_name', 'unknown')}")
    return jsonify({'success': True, 'skipped': item, 'queue_depth': len(_review_queue)})


# --- Image serving ---

@app.route('/api/scan_image', methods=['GET'])
def scan_image():
    """Serve a scan image by path. Query param: ?path=/absolute/path/to/file.jpg"""
    path = request.args.get('path', '')
    # Security: only serve files inside SCAN_DIR or DATA_DIR
    real = os.path.realpath(path)
    allowed = (os.path.realpath(SCAN_DIR), os.path.realpath(DATA_DIR))
    if not any(real.startswith(a) for a in allowed):
        return jsonify({'error': 'Access denied'}), 403
    if not os.path.exists(real):
        return jsonify({'error': 'Not found'}), 404
    return send_file(real, mimetype='image/jpeg')


# --- Inventory stats ---

@app.route('/api/inventory', methods=['GET'])
def inventory_endpoint():
    """Return inventory stats: total accepted cards, last scan, etc."""
    inv_path = os.path.join(INV_DIR, 'accepted_cards.jsonl')
    total = 0
    last = None
    try:
        if os.path.exists(inv_path):
            with open(inv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            total = len(lines)
            if lines:
                last = json.loads(lines[-1])
    except Exception as e:
        logger.warning(f"Inventory read error: {e}")

    return jsonify({
        'success': True,
        'total_accepted': total,
        'last_card': last.get('card_name') if last else None,
        'last_accepted_at': last.get('accepted_at') if last else None,
        'queue_depth': len(_review_queue),
        'faiss_loaded': faiss_index is not None,
        'coral_loaded': CORAL_LOADED,
    })


# --- Art recognition endpoint (direct) ---

@app.route('/api/art/recognize', methods=['POST'])
def art_recognize():
    """Direct art recognition via Coral TPU + FAISS."""
    data = request.json
    if not data or not data.get('image_path'):
        return jsonify({"error": "image_path required"}), 400
    result = art_match(data['image_path'], data.get('top_k', 5))
    return jsonify(result)


# --- OCR endpoint (direct) ---

@app.route('/api/ocr', methods=['POST'])
def ocr_endpoint():
    """Direct OCR on image."""
    data = request.json
    if not data or not data.get('image_path'):
        return jsonify({"error": "image_path required"}), 400
    result = run_ocr(data['image_path'])
    return jsonify(result)


# --- Scan file management ---

@app.route('/api/scans/list', methods=['GET'])
def scans_list():
    """List recent scan files."""
    try:
        files = []
        for fn in os.listdir(SCAN_DIR):
            fp = os.path.join(SCAN_DIR, fn)
            if os.path.isfile(fp):
                stat = os.stat(fp)
                files.append({
                    'filename': fn,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        files.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({"files": files[:100]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/scans/<path:filename>')
def serve_scan(filename):
    """Serve a scan file."""
    filepath = os.path.join(SCAN_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    return jsonify({"error": "Not found"}), 404


# --- Library/Inventory API ---

LIBRARY_DB_PATH = os.path.join(DATA_DIR, 'inventory', 'nexus_library.db')


@app.route('/api/library/all', methods=['GET'])
def library_all():
    """Return all cards from the inventory database.
    Used by the Collection tab in the desktop app.
    ?raw=1 returns flat list, otherwise wrapped in {cards: [...]}.
    """
    if not os.path.exists(LIBRARY_DB_PATH):
        return jsonify({"error": "Library database not found", "path": LIBRARY_DB_PATH}), 404

    try:
        db = sqlite3.connect(LIBRARY_DB_PATH)
        db.row_factory = sqlite3.Row
        c = db.cursor()
        c.execute("SELECT * FROM cards ORDER BY call_number")
        rows = c.fetchall()
        cards = [dict(r) for r in rows]
        db.close()

        raw = request.args.get('raw', '0')
        if raw == '1':
            return jsonify({"cards": cards})
        return jsonify({"cards": cards, "total": len(cards)})

    except Exception as e:
        logger.error(f"Library DB error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/library/search', methods=['GET'])
def library_search():
    """Search cards by name. ?q=name&limit=50"""
    q = request.args.get('q', '')
    limit = int(request.args.get('limit', 50))

    if not q:
        return jsonify({"cards": [], "total": 0})

    if not os.path.exists(LIBRARY_DB_PATH):
        return jsonify({"error": "Library database not found"}), 404

    try:
        db = sqlite3.connect(LIBRARY_DB_PATH)
        db.row_factory = sqlite3.Row
        c = db.cursor()
        c.execute("SELECT * FROM cards WHERE name LIKE ? ORDER BY name LIMIT ?",
                  (f"%{q}%", limit))
        rows = c.fetchall()
        cards = [dict(r) for r in rows]
        db.close()
        return jsonify({"cards": cards, "total": len(cards)})

    except Exception as e:
        logger.error(f"Library search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/library/stats', methods=['GET'])
def library_stats():
    """Library statistics - total cards, sets, rarities, boxes."""
    if not os.path.exists(LIBRARY_DB_PATH):
        return jsonify({"error": "Library database not found"}), 404

    try:
        db = sqlite3.connect(LIBRARY_DB_PATH)
        c = db.cursor()

        c.execute("SELECT count(*) FROM cards")
        total = c.fetchone()[0]

        c.execute("SELECT count(DISTINCT set_code) FROM cards WHERE set_code IS NOT NULL AND set_code != ''")
        sets = c.fetchone()[0]

        c.execute("SELECT count(DISTINCT box_id) FROM cards")
        boxes = c.fetchone()[0]

        c.execute("SELECT rarity, count(*) FROM cards GROUP BY rarity ORDER BY count(*) DESC")
        rarities = {r[0]: r[1] for r in c.fetchall()}

        c.execute("SELECT SUM(price) FROM cards WHERE price > 0")
        total_value = c.fetchone()[0] or 0

        db.close()
        return jsonify({
            "total_cards": total,
            "total_sets": sets,
            "total_boxes": boxes,
            "rarities": rarities,
            "total_value": round(total_value, 2),
        })

    except Exception as e:
        logger.error(f"Library stats error: {e}")
        return jsonify({"error": str(e)}), 500


# --- Arm control endpoints ---

# Map joint index/name to ESP32 ARM command
JOINT_MAP = {
    0: "SHOULDER", "shoulder": "SHOULDER",
    1: "YAW", "wyaw": "YAW", "wrist_yaw": "YAW", "yaw": "YAW",
    2: "PITCH", "wpitch": "PITCH", "wrist_pitch": "PITCH", "pitch": "PITCH",
    3: "ELBOW", "elbow": "ELBOW",
}


@app.route('/api/arm/set', methods=['POST'])
def arm_set():
    """Set a single arm joint or lightbox. Body: {cmd: 'shoulder', angle: 90} or {cmd: 'lightbox', r, g, b}"""
    data = request.json
    cmd = data.get('cmd', '')
    # Handle lightbox commands — pass as JSON dict directly to ARM ESP32
    if isinstance(cmd, str) and cmd.lower() == 'lightbox':
        r = int(data.get('r', 255))
        g = int(data.get('g', 255))
        b = int(data.get('b', 255))
        resp = arm_command({"cmd": "lightbox", "r": r, "g": g, "b": b})
        return jsonify({"success": True, "response": resp})
    angle = data.get('angle', 90)
    joint_name = JOINT_MAP.get(cmd.lower() if isinstance(cmd, str) else cmd, cmd)
    if isinstance(joint_name, str) and joint_name in ("SHOULDER", "ELBOW", "YAW", "PITCH"):
        resp = arm_command(f"ARM:{joint_name}:{angle}")
    else:
        resp = arm_command(f"ARM:CH{cmd}:{angle}" if isinstance(cmd, int) else f"ARM:{str(cmd).upper()}:{angle}")
    idx_map = {"SHOULDER": 0, "YAW": 1, "PITCH": 2, "ELBOW": 3}
    idx = idx_map.get(joint_name if isinstance(joint_name, str) else "")
    if idx is not None and idx < len(arm_angles):
        arm_angles[idx] = angle
    return jsonify({"success": True, "response": resp, "angles": arm_angles})


@app.route('/api/arm/servo/setting', methods=['POST'])
def arm_servo_setting():
    """Set servo trim/min/max."""
    data = request.json
    return jsonify({"success": True, "received": data})


@app.route('/api/arm/servo/settings', methods=['GET'])
def arm_servo_settings():
    """Get servo settings."""
    return jsonify({"settings": {}})


@app.route('/api/arm/servo/save', methods=['POST'])
def arm_servo_save():
    """Save servo settings."""
    return jsonify({"success": True})


@app.route('/api/arm/jog', methods=['POST'])
def arm_jog():
    """Jog a single arm joint by degrees (relative move).
    UI sends: {"cmd": "shoulder", "degrees": 5}
    Also accepts: {"joint": 0, "angle": 90} (legacy absolute)
    """
    data = request.json

    # Handle UI format: {"cmd": "shoulder", "degrees": 5}
    cmd = data.get('cmd')
    degrees = data.get('degrees')

    if cmd and degrees is not None:
        joint_name = JOINT_MAP.get(cmd.lower() if isinstance(cmd, str) else cmd, cmd)
        idx_map = {"SHOULDER": 0, "YAW": 1, "PITCH": 2, "ELBOW": 3}
        idx = idx_map.get(joint_name if isinstance(joint_name, str) else "", None)
        if idx is not None and idx < len(arm_angles):
            current = arm_angles[idx]
            new_angle = current + int(degrees)
            new_angle = max(0, min(180, new_angle))
            arm_angles[idx] = new_angle
            if isinstance(joint_name, str) and joint_name in ("SHOULDER", "ELBOW", "YAW", "PITCH"):
                resp = arm_command(f"ARM:{joint_name}:{new_angle}")
            else:
                resp = arm_command(f"ARM:{str(joint_name).upper()}:{new_angle}")
            return jsonify({"success": True, "response": resp, "angles": arm_angles})
        return jsonify({"success": False, "error": f"Unknown joint: {cmd}"}), 400

    # Legacy format: {"joint": 0, "angle": 90}
    joint = data.get('joint', 0)
    angle = data.get('angle', 90)
    joint_name = JOINT_MAP.get(joint, None)
    if joint_name:
        resp = arm_command(f"ARM:{joint_name}:{angle}")
    else:
        resp = arm_command(f"ARM:CH{joint}:{angle}")
    if isinstance(joint, int) and joint < len(arm_angles):
        arm_angles[joint] = angle
    return jsonify({"success": True, "response": resp, "angles": arm_angles})


@app.route('/api/arm/position', methods=['GET'])
def arm_position():
    return jsonify({"angles": arm_angles, "base": base_angle})


@app.route('/api/arm/preset', methods=['POST'])
def arm_preset():
    """Move arm to a named preset."""
    data = request.json
    name = data.get('name', 'home')
    preset = arm_presets.get(name)
    if not preset:
        return jsonify({"error": f"Unknown preset: {name}"}), 404

    for joint_name, angle in preset.items():
        if joint_name == 'base':
            arm_command(f"STEP:GOTO:{angle}")
        elif joint_name == 'shoulder':
            arm_command(f"ARM:SHOULDER:{angle}")
        elif joint_name == 'elbow':
            arm_command(f"ARM:ELBOW:{angle}")
        elif joint_name == 'wrist_yaw':
            arm_command(f"ARM:YAW:{angle}")
        elif joint_name == 'wrist_pitch':
            arm_command(f"ARM:PITCH:{angle}")
        time.sleep(0.05)

    return jsonify({"success": True, "preset": name, "angles": preset})


@app.route('/api/arm/presets', methods=['GET'])
def arm_presets_list():
    return jsonify({"presets": arm_presets})


@app.route('/api/arm/preset/save', methods=['POST'])
def arm_preset_save():
    data = request.json
    name = data.get('name')
    angles = data.get('angles')
    if not name or not angles:
        return jsonify({"error": "name and angles required"}), 400
    arm_presets[name] = angles
    save_arm_presets(arm_presets)
    return jsonify({"success": True, "preset": name})


# --- Vacuum/gripper ---

@app.route('/api/vacuum/on', methods=['POST'])
def vacuum_on():
    return jsonify({"response": arm_command("VACUUM:ON")})

@app.route('/api/vacuum/off', methods=['POST'])
def vacuum_off():
    return jsonify({"response": arm_command("VACUUM:OFF")})

@app.route('/api/vacuum/pick', methods=['POST'])
def vacuum_pick():
    return jsonify({"response": arm_command("VACUUM:PICK")})

@app.route('/api/vacuum/drop', methods=['POST'])
def vacuum_drop():
    return jsonify({"response": arm_command("VACUUM:DROP")})


@app.route('/api/solenoid/on', methods=['POST'])
def solenoid_on():
    """Turn solenoid on (PCA ch6)."""
    resp = arm_command({"cmd": "relay", "channel": 6, "state": 1})
    return jsonify({"response": resp})

@app.route('/api/solenoid/off', methods=['POST'])
def solenoid_off():
    """Turn solenoid off (PCA ch6)."""
    resp = arm_command({"cmd": "relay", "channel": 6, "state": 0})
    return jsonify({"response": resp})


# --- Stepper (base rotation) ---

@app.route('/api/stepper/jog', methods=['POST'])
def stepper_jog():
    """Jog stepper by steps. Body: {steps: 100}"""
    data = request.json
    steps = data.get('steps', 0)
    if steps == 0:
        return jsonify({"response": "OK", "steps": 0})
    direction = 1 if steps > 0 else -1
    abs_steps = abs(steps)
    resp = arm_command({"cmd": "move_base", "steps": abs_steps, "dir": direction, "speed": 800})
    return jsonify({"response": resp, "steps": steps})


@app.route('/api/stepper/home', methods=['POST'])
def stepper_home():
    """Home stepper (return to 0). Body: {stepper: 'base'}"""
    global base_angle
    if base_angle != 0:
        delta = -base_angle
        steps = abs(delta) * STEPS_PER_DEGREE
        direction = 1 if delta > 0 else -1
        resp = arm_command({"cmd": "move_base", "steps": steps, "dir": direction, "speed": 800})
        base_angle = 0
    else:
        resp = "OK"
    return jsonify({"response": resp, "angle": 0})


@app.route('/api/stepper/angle', methods=['POST'])
def stepper_angle():
    global base_angle
    data = request.json
    angle = data.get('angle', 0)
    resp = arm_command(f"STEP:GOTO:{angle}")
    base_angle = angle
    return jsonify({"response": resp, "angle": base_angle})


# --- Lightbox endpoints ---

@app.route('/api/lights', methods=['POST'])
def lights_endpoint():
    """Control lightbox. Body: {command: "ON|OFF|PRESET:X|CH:N:V|RGB:N:R:G:B"}"""
    data = request.json
    cmd = data.get('command', 'LIGHTS_ON')
    # Route through Pro Micro (unified lighting)
    resp = toplight_command(cmd)
    return jsonify({"success": True, "command": cmd, "response": resp})


@app.route('/api/lights/on', methods=['POST'])
def lights_on_endpoint():
    lights_on()
    return jsonify({"success": True})

@app.route('/api/lights/off', methods=['POST'])
def lights_off_endpoint():
    lights_off()
    return jsonify({"success": True})

@app.route('/api/lights/preset', methods=['POST'])
def lights_preset():
    data = request.json
    preset = data.get('preset', 'SCAN')
    set_light_preset(preset)
    return jsonify({"success": True, "preset": preset})


@app.route('/api/lights/ch/<int:ch>', methods=['POST'])
def lights_channel_endpoint(ch):
    """Set individual LED channel color. Body: {r, g, b} or {brightness}."""
    data = request.json or {}
    if 'brightness' in data:
        val = int(data['brightness'])
        set_light_channel(ch, val)
        return jsonify({"success": True, "channel": ch, "brightness": val})
    r = int(data.get('r', 255))
    g = int(data.get('g', 255))
    b = int(data.get('b', 255))
    set_light_rgb(ch, r, g, b)
    return jsonify({"success": True, "channel": ch, "r": r, "g": g, "b": b})


@app.route('/api/lights/rgb', methods=['POST'])
def lights_rgb_endpoint():
    """Set all LED channels to RGB color. Body: {r, g, b}."""
    data = request.json or {}
    r = int(data.get('r', 255))
    g = int(data.get('g', 255))
    b = int(data.get('b', 255))
    for ch in range(1, 7):  # Pro Micro channels 1-6 (1-indexed)
        set_light_rgb(ch, r, g, b)
    return jsonify({"success": True, "r": r, "g": g, "b": b})


@app.route('/api/lights/brightness', methods=['POST'])
def lights_brightness_endpoint():
    """Set global brightness. Body: {brightness: 0-255}."""
    data = request.json or {}
    val = int(data.get('brightness', 255))
    toplight_command(f"B:{val}")
    return jsonify({"success": True, "brightness": val})


@app.route('/api/lights/status', methods=['GET'])
def lights_status_endpoint():
    """Get light ESP32 status."""
    resp = toplight_command("S")
    return jsonify({"success": True, "response": resp})


# ─── Top Lights API (Pro Micro v3.0, 6-channel canopy LEDs) ─────────

@app.route('/api/toplights/on', methods=['POST'])
def toplights_on_endpoint():
    """Turn all top light channels on (white)."""
    resp = toplight_command("ON")
    return jsonify({"success": resp is not None, "response": resp})

@app.route('/api/toplights/off', methods=['POST'])
def toplights_off_endpoint():
    """Turn all top light channels off."""
    resp = toplight_command("OFF")
    return jsonify({"success": resp is not None, "response": resp})

@app.route('/api/toplights/brightness', methods=['POST'])
def toplights_brightness_endpoint():
    """Set top light brightness. Body: {brightness: 0-255}."""
    data = request.json or {}
    val = int(data.get('brightness', 128))
    resp = toplight_command(f"B:{val}")
    return jsonify({"success": resp is not None, "brightness": val, "response": resp})

@app.route('/api/toplights/ch/<int:ch>', methods=['POST'])
def toplights_channel_endpoint(ch):
    """Set single top light channel RGB. Body: {r, g, b}. Channel 1-6."""
    data = request.json or {}
    r = int(data.get('r', 255))
    g = int(data.get('g', 255))
    b = int(data.get('b', 255))
    resp = toplight_command(f"C:{ch}:{r}:{g}:{b}")
    return jsonify({"success": resp is not None, "channel": ch, "response": resp})

@app.route('/api/toplights/rgb', methods=['POST'])
def toplights_rgb_endpoint():
    """Set all top light channels to same RGB. Body: {r, g, b}."""
    data = request.json or {}
    r = int(data.get('r', 255))
    g = int(data.get('g', 255))
    b = int(data.get('b', 255))
    resp = toplight_command(f"A:{r}:{g}:{b}")
    return jsonify({"success": resp is not None, "r": r, "g": g, "b": b, "response": resp})

@app.route('/api/toplights/preset', methods=['POST'])
def toplights_preset_endpoint():
    """Apply top light preset. Body: {preset: SCAN|PHOTO|GRADE|OFF}."""
    data = request.json or {}
    preset = data.get('preset', 'SCAN').upper()
    resp = toplight_command(f"P:{preset}")
    return jsonify({"success": resp is not None, "preset": preset, "response": resp})

@app.route('/api/toplights/status', methods=['GET'])
def toplights_status_endpoint():
    """Get top light Pro Micro status (6 channels)."""
    resp = toplight_command("S")
    return jsonify({"success": resp is not None, "response": resp})

@app.route('/api/toplights/test', methods=['POST'])
def toplights_test_endpoint():
    """Run top light test sequence (chases through each channel)."""
    resp = toplight_command("T")
    return jsonify({"success": resp is not None, "response": resp})


@app.route('/api/lightbox', methods=['POST'])
def lightbox_endpoint():
    """Lightbox control - maps to ARM ESP32 LIGHTBOX commands."""
    data = request.json
    state = data.get('state', '')
    r = data.get('r', 255)
    g = data.get('g', 255)
    b = data.get('b', 255)
    if state == 'on':
        resp = arm_command(f"LIGHTBOX:{r}:{g}:{b}")
    elif state == 'off':
        resp = arm_command("LIGHTBOX:OFF")
    else:
        resp = arm_command(f"LIGHTBOX:{r}:{g}:{b}")
    return jsonify({"success": True, "response": resp})


@app.route('/api/vacuum', methods=['POST'])
def vacuum_endpoint():
    """Vacuum control via JSON body."""
    data = request.json
    state = data.get('state', 'off')
    if state == 'on':
        resp = arm_command("VACUUM:ON")
    else:
        resp = arm_command("VACUUM:OFF")
    return jsonify({"success": True, "response": resp})


@app.route('/api/arm/home', methods=['POST'])
def arm_home():
    """Home the arm."""
    resp = arm_command("ARM:HOME")
    return jsonify({"success": True, "response": resp})


# --- Auto-scan ---

@app.route('/api/autoscan/start', methods=['POST'])
def autoscan_start():
    global autoscan_running, autoscan_thread
    if autoscan_running:
        return jsonify({"status": "already running"})
    autoscan_running = True
    autoscan_thread = Thread(target=motion_monitor_loop, daemon=True)
    autoscan_thread.start()
    return jsonify({"status": "started"})


@app.route('/api/autoscan/stop', methods=['POST'])
def autoscan_stop():
    global autoscan_running
    autoscan_running = False
    return jsonify({"status": "stopped"})


@app.route('/api/autoscan/status', methods=['GET'])
def autoscan_status():
    return jsonify({
        "running": autoscan_running,
        "card_present": card_present,
        "last_result": last_scan_result,
    })


# --- System stats ---

@app.route('/api/system/stats', methods=['GET'])
def system_stats():
    """System resource stats."""
    stats = {"name": "DANIELSON", "timestamp": datetime.now().isoformat()}
    try:
        import shutil
        total, used, free = shutil.disk_usage(DATA_DIR)
        stats['disk'] = {
            'total_gb': round(total / (1024**3), 1),
            'used_gb': round(used / (1024**3), 1),
            'free_gb': round(free / (1024**3), 1),
        }
    except Exception:
        pass

    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        for line in meminfo.split('\n'):
            if 'MemTotal' in line:
                stats['ram_total_mb'] = int(line.split()[1]) // 1024
            elif 'MemAvailable' in line:
                stats['ram_available_mb'] = int(line.split()[1]) // 1024
    except Exception:
        pass

    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()
        stats['load_avg'] = [float(load[0]), float(load[1]), float(load[2])]
    except Exception:
        pass

    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            stats['cpu_temp_c'] = int(f.read().strip()) / 1000
    except Exception:
        pass

    stats['scan_count'] = len(os.listdir(SCAN_DIR)) if os.path.exists(SCAN_DIR) else 0
    return jsonify(stats)


# --- Debug endpoint (protected) ---

if DEBUG_MODE:
    @app.route('/api/debug/exec', methods=['POST'])
    def debug_exec():
        """Execute arbitrary command (DEBUG ONLY)."""
        data = request.json
        cmd = data.get('command', '')
        if not cmd:
            return jsonify({"error": "No command"}), 400
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=10,
                text=True
            )
            return jsonify({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500


# =============================================================================
# STARTUP
# =============================================================================

def detect_cameras():
    """Auto-detect USB cameras on startup."""
    logger.info("Detecting USB cameras...")
    try:
        result = subprocess.run(['v4l2-ctl', '--list-devices'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info(f"Available devices:\n{result.stdout}")
        else:
            logger.warning("v4l2-ctl not available, using defaults")
    except Exception:
        logger.warning("v4l2-ctl not found, using default camera config")


def _release_all_cameras():
    """Release all shared cameras cleanly on shutdown."""
    for name, cam in list(shared_cameras.items()):
        try:
            cam.stop()
            logger.info(f"Released camera: {name}")
        except Exception:
            pass
    shared_cameras.clear()


def _shutdown_handler(signum, frame):
    """Handle SIGTERM/SIGINT — release USB devices before exit."""
    logger.info(f"Received signal {signum}, releasing cameras...")
    _release_all_cameras()
    raise SystemExit(0)


# Register cleanup for both normal exit and signals
atexit.register(_release_all_cameras)
signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)


def main():
    logger.info("=" * 60)
    logger.info("  DANIELSON — Unified Scanner Server")
    logger.info("  Replaces SNARF + BROCK")
    logger.info("=" * 60)

    # Brief pause to let USB devices settle after a restart
    time.sleep(1)

    # Detect cameras
    detect_cameras()

    # Initialize AI
    phash_ok = init_phash()  # PRIMARY art matcher
    coral_ok = init_coral()  # Fallback (requires retraining for physical scans)
    faiss_ok = init_faiss()  # Fallback (requires retraining for physical scans)
    logger.info(f"pHash DB: {'LOADED' if PHASH_LOADED else 'DISABLED'} (PRIMARY)")
    logger.info(f"Coral TPU: {'LOADED' if CORAL_LOADED else 'CPU fallback' if coral_ok else 'DISABLED'} (fallback)")
    logger.info(f"FAISS index: {'LOADED' if faiss_ok else 'DISABLED'} (fallback)")
    logger.info(f"OCR (Tesseract): {'AVAILABLE' if PYTESSERACT_AVAILABLE else 'DISABLED'}")
    logger.info(f"Serial (ESP32): {'AVAILABLE' if SERIAL_AVAILABLE else 'DISABLED'}")
    logger.info(f"Data dir: {DATA_DIR}")
    logger.info(f"Scan dir: {SCAN_DIR}")
    logger.info(f"ZULTAN: {ZULTAN_URL}")
    logger.info(f"Relay: {RELAY_URL}")
    logger.info(f"Port: {SERVER_PORT}")

    # Start Flask
    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False, threaded=True)



@app.route("/api/calibrate/lightbox", methods=["POST", "GET"])
def calibrate_lightbox():
    """Get or set lightbox ROI. POST {"x","y","w","h"} to update."""
    global LIGHTBOX_FIXED
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if all(k in data for k in ("x", "y", "w", "h")):
            LIGHTBOX_FIXED = (int(data["x"]), int(data["y"]), int(data["w"]), int(data["h"]))
            return jsonify({"ok": True, "lightbox": LIGHTBOX_FIXED, "method": "manual"})
    return jsonify({"ok": True, "lightbox": LIGHTBOX_FIXED})

if __name__ == '__main__':
    main()
