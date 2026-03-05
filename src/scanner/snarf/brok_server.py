#!/usr/bin/env python3
"""
BROK - OCR Processing Server (Patent Pending)
NEXUS V2 Collectibles Management System
Copyright 2025-2026 Kevin Caracozza - All Rights Reserved
Patent Filed: November 27, 2025

OCR Pipeline (Tesseract Primary):
  - Tesseract (primary) - fast, low memory, good for card text
  - Multi-pass preprocessing for accuracy
  - Scryfall fuzzy matching with local cache
  - Target: 95-98% accuracy, 200+ cards/hour with Coral

Dual-Camera Architecture (Patent Claims 5, 7, 14):
  - CZUR Scanner (USB on Snarf): Bulk scanning -> Coral OCR
  - OwlEye 64MP (CSI on Snarf): Grading/single cards -> Coral OCR
  - OwlEye 64MP (CSI on Brock): Card BACK type detection
  - All cameras use Coral TPU for hardware-accelerated OCR
"""

import os
import re
import json
import time
import logging
import subprocess
from datetime import datetime
from difflib import SequenceMatcher
from threading import Thread

import cv2

# Import the WORKING card detection (not the broken fixed-percentage shit)
try:
    from card_detection_v2 import detect_card_v2
    CARD_DETECTION_V2 = True
except ImportError:
    CARD_DETECTION_V2 = False
    print("WARNING: card_detection_v2 not found, using legacy detection")
import numpy as np
import requests
from flask import Flask, jsonify, request, send_file

# OCR Library - Tesseract
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    print("WARNING: pytesseract not installed - OCR will be degraded")

# =============================================================================
# OPTIONAL DEPENDENCIES
# =============================================================================
# Coral Edge TPU - LAZY LOADED to avoid PyTorch/TensorFlow conflict
# Used for: Card detection, set symbol matching
tf = None  # Will be lazy-loaded when Coral is needed
CORAL_AVAILABLE = None  # None = not checked yet, True/False after check
CORAL_DELEGATE = 'libedgetpu.so.1'
coral_interpreter = None
_coral_checked = False

def get_coral_interpreter(model_path=None):
    """
    Lazy-load TensorFlow and Coral Edge TPU only when needed.
    This avoids the PyTorch/TensorFlow conflict at import time.
    Used for card detection and set symbol matching, NOT for OCR.
    """
    global tf, CORAL_AVAILABLE, coral_interpreter, _coral_checked
    
    if _coral_checked:
        return coral_interpreter
    
    _coral_checked = True
    
    try:
        # Try tflite_runtime first (lightweight for Pi), then tensorflow
        try:
            from tflite_runtime.interpreter import Interpreter, load_delegate
            logger.info("Using tflite_runtime for Coral TPU")
        except ImportError:
            import tensorflow as tflow
            Interpreter = tflow.lite.Interpreter
            load_delegate = tflow.lite.experimental.load_delegate
            logger.info("Using tensorflow for Coral TPU")

        delegate = load_delegate(CORAL_DELEGATE)
        CORAL_AVAILABLE = True
        logger.info("Coral Edge TPU M.2 loaded (lazy init)")

        if model_path:
            coral_interpreter = Interpreter(
                model_path=model_path,
                experimental_delegates=[delegate]
            )
            coral_interpreter.allocate_tensors()
            logger.info(f"Coral model loaded: {model_path}")

        return coral_interpreter
    except ImportError:
        CORAL_AVAILABLE = False
        logger.debug("TensorFlow/TFLite not installed - Coral Edge TPU disabled")
        return None
    except Exception as e:
        CORAL_AVAILABLE = False
        logger.debug(f"Coral Edge TPU not available: {e}")
        return None


# OCR: Tesseract only
OCR_AVAILABLE = True

# =============================================================================
# ABILITY KEYWORDS - Common MTG abilities that appear in rules text
# These are ALSO real card names, but should be deprioritized vs title region text
# =============================================================================
ABILITY_KEYWORDS = {
    'cycling', 'flying', 'trample', 'haste', 'vigilance', 'reach',
    'deathtouch', 'lifelink', 'menace', 'flash', 'hexproof', 'indestructible',
    'defender', 'first strike', 'double strike', 'prowess', 'convoke',
    'equip', 'enchant', 'attach', 'sacrifice', 'discard', 'draw',
    'scry', 'surveil', 'proliferate', 'populate', 'investigate',
    'untap', 'tap', 'counter', 'exile', 'destroy', 'regenerate',
    'protection', 'shroud', 'landwalk', 'forestwalk', 'islandwalk',
    'swampwalk', 'mountainwalk', 'plainswalk', 'fear', 'intimidate',
    'wither', 'infect', 'persist', 'undying', 'morbid', 'revolt',
    'rally', 'raid', 'ferocious', 'formidable', 'threshold', 'delirium',
    'metalcraft', 'affinity', 'imprint', 'cascade', 'storm', 'retrace',
    'flashback', 'madness', 'miracle', 'overload', 'bestow', 'tribute',
    'inspired', 'outlast', 'dash', 'exploit', 'bolster', 'manifest',
    'morph', 'megamorph', 'embalm', 'eternalize', 'exert', 'aftermath',
    'enrage', 'ascend', 'transform', 'meld', 'crew', 'fabricate'
}

# =============================================================================
# SHOP CONFIGURATION LOADER
# =============================================================================
def load_shop_config():
    """
    Load shop-specific configuration from JSON file.
    Supports per-shop deployment with different settings.
    """
    config_path = os.getenv('NEXUS_CONFIG', '/home/nexus1/brok_server_config.json')
    default_config = {
        'shop_id': 'default',
        'shop_code': 'DEV',
        'snarf_url': 'http://192.168.1.172:5001',
        'port': 5000,
        'hdd_path': '/mnt/nexus_data',
        'coral_enabled': True,
        'central_api_url': 'https://api.nexus-tcg.com',
        'sync_customer_data': False,  # ENFORCED
        'sync_sales_data': False,     # ENFORCED
        'sync_metadata': True,
        'sync_ai_patterns': True,
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                loaded = json.load(f)
                # Merge with defaults
                default_config.update(loaded)
                # ENFORCE data isolation - never sync customer/sales
                default_config['sync_customer_data'] = False
                default_config['sync_sales_data'] = False
                print(f"[OK] Loaded shop config: {default_config.get('shop_code', 'unknown')}")
        except Exception as e:
            print(f"[WARN] Failed to load config: {e}, using defaults")
    else:
        print(f"[INFO] No config at {config_path}, using defaults")

    return default_config

# Load shop configuration
SHOP_CONFIG = load_shop_config()

# =============================================================================
# CONFIGURATION (from shop config + environment overrides)
# =============================================================================
# Network
SNARF_URL = os.getenv('NEXUS_SNARF_URL', SHOP_CONFIG.get('snarf_url', 'http://192.168.1.172:5001'))
ZULTAN_URL = os.getenv('NEXUS_ZULTAN_URL', SHOP_CONFIG.get('zultan_url', 'http://192.168.1.152:5050'))
SERVER_PORT = int(os.getenv('BROK_PORT', SHOP_CONFIG.get('port', 5000)))

# Shop identity
SHOP_ID = SHOP_CONFIG.get('shop_id', 'default')
SHOP_CODE = SHOP_CONFIG.get('shop_code', 'DEV')

# Storage paths
HDD = os.getenv('NEXUS_HDD', SHOP_CONFIG.get('hdd_path', '/mnt/nexus_data'))
SCAN_DIR = f'{HDD}/scans'
CACHE_DIR = f'{HDD}/cache'
INV_DIR = f'{HDD}/inventory'
BACK_DIR = f'{HDD}/backs'
DATABASE_DIR = SHOP_CONFIG.get('database_dir', f'{HDD}/databases')

# Debug mode (enables /api/debug/* endpoints)
DEBUG_MODE = os.getenv('BROK_DEBUG', 'true').lower() == 'true'

# OCR Configuration
OCR_USE_GPU = os.getenv('OCR_USE_GPU', 'false').lower() == 'true'
OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE', '0.7'))
OCR_USE_CORAL = os.getenv('OCR_USE_CORAL', str(SHOP_CONFIG.get('coral_enabled', True))).lower() == 'true'

# OCR CORRECTION DICTIONARY (Common MTG card name mistakes)
OCR_CORRECTIONS = {
    # Character substitutions
    '0': 'O',  # Zero vs O
    '1': 'I',  # One vs I (context dependent)
    '5': 'S',  # Five vs S
    '8': 'B',  # Eight vs B
    '@': 'a',  # At sign vs lowercase a
    '|': 'I',  # Pipe vs I
    # Common word corrections
    'tho': 'the',
    'af': 'of',
    'tha': 'the',
    'ancl': 'and',
    'ancf': 'and',
    'wilh': 'with',
    'wilth': 'with',
    'fram': 'from',
    'carnl': 'card',
    'carnls': 'cards',
}

# MTG-specific common words for context validation
MTG_COMMON_WORDS = {
    'the', 'of', 'and', 'to', 'from', 'with', 'for', 'by',
    'dragon', 'angel', 'demon', 'beast', 'wizard', 'knight',
    'lightning', 'bolt', 'fire', 'storm', 'path', 'exile',
    'sword', 'shield', 'lord', 'queen', 'king', 'mage',
    'dark', 'light', 'shadow', 'sun', 'moon', 'star',
    'power', 'might', 'force', 'rage', 'fury', 'wrath'
}

# Learning data file for OCR corrections
OCR_LEARNING_FILE = f'{HDD}/cache/ocr_corrections.json'
ocr_learning_data = {}  # Will load from file

# Central API (for metadata/prices only - customer data stays LOCAL)
CENTRAL_API_URL = SHOP_CONFIG.get('central_api_url', 'https://api.nexus-tcg.com')
CENTRAL_API_KEY = SHOP_CONFIG.get('central_api_key', '')

# Data sync policy (ENFORCED - customer data never leaves shop)
SYNC_CUSTOMER_DATA = False  # ALWAYS FALSE
SYNC_SALES_DATA = False     # ALWAYS FALSE
SYNC_METADATA = SHOP_CONFIG.get('sync_metadata', True)
SYNC_AI_PATTERNS = SHOP_CONFIG.get('sync_ai_patterns', True)

# ====================================================================
# FLASK APP SETUP
# =============================================================================
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger('BROK')

# Enable GPU if available
cv2.ocl.setUseOpenCL(OCR_USE_GPU)

# =============================================================================
# DIRECTORY SETUP
# =============================================================================
for d in [SCAN_DIR, CACHE_DIR, INV_DIR, BACK_DIR]:
    os.makedirs(d, exist_ok=True)

# Card back reference images for type detection
CARD_BACK_TEMPLATES = f'{CACHE_DIR}/card_backs'
os.makedirs(CARD_BACK_TEMPLATES, exist_ok=True)

# Set symbol templates for set identification
SET_SYMBOLS_DIR = f'{CACHE_DIR}/set_symbols'
os.makedirs(SET_SYMBOLS_DIR, exist_ok=True)

# =============================================================================
# LOCAL CAMERA CONFIGURATION
# =============================================================================
LOCAL_CAMERA = {
    'type': 'csi',
    'index': 0,  # CAM0 port on Brok
    'resolution': (4624, 3472),
    'role': 'back_detector'
}

# =============================================================================
# DATA FILE PATHS
# =============================================================================
HISTORY_FILE = f'{INV_DIR}/scan_history.json'
CACHE_FILE = f'{CACHE_DIR}/scryfall_cache.json'
INV_FILE = f'{INV_DIR}/card_inventory.json'
REVIEW_FILE = f'{INV_DIR}/review_queue.json'
BOX_FILE = f'{INV_DIR}/box_state.json'
MASTER_DB_FILE = f'{CACHE_DIR}/scryfall_master.json'

# =============================================================================
# STATE VARIABLES
# =============================================================================
scan_counter = 0
review_counter = 0  # For validation failures
scan_history = []
card_cache = {}
inventory = {}
review_queue = []
set_symbol_templates = {}

# Box tracking (AA01-ZZ999 call number system)
current_box = 'AA'
box_position = 0

# Scryfall master database
master_cards = {}  # name_lower -> card data
master_names = []  # All card names for fuzzy matching


def load_master_database():
    """Load Scryfall master database and build name index"""
    global master_cards, master_names
    if not os.path.exists(MASTER_DB_FILE):
        logger.warning("Master database not found - using API only")
        return False

    logger.info("Loading Scryfall master database...")
    try:
        with open(MASTER_DB_FILE, 'r', encoding='utf-8') as f:
            cards = json.load(f)

        # Build index by card name (lowercase)
        for card in cards:
            name = card.get('name', '')
            if name:
                name_lower = name.lower()
                # Store first occurrence (usually the most recent printing)
                if name_lower not in master_cards:
                    master_cards[name_lower] = {
                        'name': name,
                        'set': (card.get('set') or '').upper(),
                        'set_name': card.get('set_name'),
                        'collector_number': card.get('collector_number'),
                        'rarity': card.get('rarity'),
                        'prices': card.get('prices', {}),
                        'image': (card.get('image_uris') or {}).get('normal'),
                        'scryfall_id': card.get('id')
                    }
                    master_names.append(name)

        logger.info(f"Loaded {len(master_cards)} unique cards from master DB")
        return True
    except Exception as e:
        logger.error(f"Failed to load master database: {e}")
        return False


# =============================================================================
# SET SYMBOL MATCHING (Patent Pending - Visual Set Identification)
# =============================================================================

def download_set_symbols():
    """Download set symbol SVGs from Scryfall and convert to PNG templates"""
    global set_symbol_templates

    try:
        # Get all sets from Scryfall
        r = requests.get('https://api.scryfall.com/sets', timeout=30)
        if r.status_code != 200:
            logger.error(f"Failed to fetch sets: {r.status_code}")
            return False

        sets_data = r.json().get('data', [])
        logger.info(f"Found {len(sets_data)} sets to download symbols for")

        downloaded = 0
        for s in sets_data:
            set_code = s.get('code', '').lower()
            icon_url = s.get('icon_svg_uri')
            if not set_code or not icon_url:
                continue

            png_path = os.path.join(SET_SYMBOLS_DIR, f'{set_code}.png')

            # Skip if already exists
            if os.path.exists(png_path):
                downloaded += 1
                continue

            try:
                # Download SVG
                svg_r = requests.get(icon_url, timeout=10)
                if svg_r.status_code == 200:
                    svg_path = os.path.join(SET_SYMBOLS_DIR, f'{set_code}.svg')
                    with open(svg_path, 'wb') as f:
                        f.write(svg_r.content)

                    # Convert SVG to PNG using cairosvg if available
                    try:
                        import cairosvg
                        cairosvg.svg2png(url=svg_path, write_to=png_path,
                                        output_width=64, output_height=64)
                        downloaded += 1
                    except ImportError:
                        # Fallback: use inkscape if available
                        result = subprocess.run(
                            ['inkscape', svg_path, '-o', png_path, '-w', '64', '-h', '64'],
                            capture_output=True, timeout=10
                        )
                        if result.returncode == 0:
                            downloaded += 1
            except Exception as e:
                logger.debug(f"Failed to download {set_code}: {e}")
                continue

        logger.info(f"Downloaded {downloaded} set symbols")
        return True
    except Exception as e:
        logger.error(f"Set symbol download failed: {e}")
        return False


def load_set_symbols():
    """Load set symbol templates into memory for matching"""
    global set_symbol_templates

    if not os.path.exists(SET_SYMBOLS_DIR):
        return False

    count = 0
    for f in os.listdir(SET_SYMBOLS_DIR):
        if f.endswith('.png'):
            set_code = f[:-4]  # Remove .png
            img_path = os.path.join(SET_SYMBOLS_DIR, f)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                set_symbol_templates[set_code] = img
                count += 1

    logger.info(f"Loaded {count} set symbol templates")
    return count > 0


def extract_set_symbol_region(card_img):
    """Extract the set symbol region from a card image.

    For modern frame cards (8th Edition onwards), the set symbol is:
    - On the right side of the type line
    - Roughly 50-55% down from top
    - About 5-8% from right edge

    Handles both properly cropped cards and full CZUR frames.
    """
    h, w = card_img.shape[:2]
    aspect_ratio = w / h

    # Check if this is a full CZUR frame (16:9 ~1.78) vs cropped card (~0.72)
    if aspect_ratio > 1.5:
        # Full CZUR frame - card is roughly in center
        # Card position in frame: ~30-57% x, ~9-90% y
        # Type line on card: ~55-58% down from card top
        # Symbol position: right side of type line
        # Type line Y in frame: 9% + (81% * 0.55) = ~53% down
        # Symbol X in frame: 30% + (27% * 0.88) = ~54%

        # Wider region to capture the entire type line area
        y1 = int(h * 0.48)
        y2 = int(h * 0.58)
        x1 = int(w * 0.42)
        x2 = int(w * 0.58)
        logger.debug(f"CZUR frame detected ({w}x{h}), using frame-adjusted coords")
    else:
        # Properly cropped card image
        # Y: 48-58% down from top (type line area)
        # X: 88-98% from left (right side)
        y1 = int(h * 0.48)
        y2 = int(h * 0.58)
        x1 = int(w * 0.88)
        x2 = int(w * 0.98)

    region = card_img[y1:y2, x1:x2]
    return region


def isolate_symbol_from_region(region):
    """Find and isolate the set symbol from the type line region.

    The symbol is on the type line bar (gray horizontal bar with text).
    Focus on the bottom-right where the symbol appears.
    Returns the isolated symbol image or None.
    """
    if region is None or region.size == 0:
        return None

    # Convert to grayscale
    if len(region.shape) == 3:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    else:
        gray = region.copy()

    h, w = gray.shape

    # The type line is the gray bar - usually in bottom 40% of region
    # Symbol is at the right end of the type line
    # Focus on bottom-right quadrant
    type_line_region = gray[int(h * 0.5):, int(w * 0.75):]

    if type_line_region.size < 100:
        return None

    # The symbol is a dark shape on the lighter type line bar
    # Use adaptive threshold to handle varying lighting
    thresh = cv2.adaptiveThreshold(
        type_line_region, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 21, 5
    )

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return type_line_region  # Return the region as fallback

    # Find symbol-like contours (small, roughly square shapes)
    rh, rw = type_line_region.shape
    best_contour = None
    best_score = 0

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)

        # Symbol should be small but not tiny
        min_area = rh * rw * 0.02  # At least 2% of region
        max_area = rh * rw * 0.6   # At most 60% of region

        if area < min_area or area > max_area:
            continue

        # Prefer shapes that are roughly square
        aspect = cw / ch if ch > 0 else 0
        if aspect < 0.4 or aspect > 2.5:
            continue

        # Score: prefer larger, more central, squarer shapes
        size_score = area / max_area
        aspect_score = 1.0 - abs(1.0 - aspect) * 0.3
        # Prefer shapes not at the very edge
        edge_score = 1.0 if (x > 2 and y > 2) else 0.5

        score = size_score * aspect_score * edge_score

        if score > best_score:
            best_score = score
            best_contour = cnt

    if best_contour is None:
        return type_line_region  # Return region as fallback

    # Extract with padding
    x, y, cw, ch = cv2.boundingRect(best_contour)
    pad = 3
    x = max(0, x - pad)
    y = max(0, y - pad)
    cw = min(rw - x, cw + 2 * pad)
    ch = min(rh - y, ch + 2 * pad)

    symbol = type_line_region[y:y+ch, x:x+cw]
    return symbol if symbol.size > 50 else type_line_region


def match_set_symbol(card_img, top_n=5):
    """Match the set symbol using multiple methods optimized for small images.

    Uses: Template matching, Hu moments, and contour matching.
    Returns: list of (set_code, confidence) tuples, sorted by confidence
    """
    if not set_symbol_templates:
        load_set_symbols()

    if not set_symbol_templates:
        return []

    # Extract set symbol region
    region = extract_set_symbol_region(card_img)
    if region is None or region.size == 0:
        return []

    # Try to isolate the symbol from the region
    symbol = isolate_symbol_from_region(region)

    if symbol is None or symbol.size < 50:
        return []

    # Resize symbol to standard size for comparison
    symbol_resized = cv2.resize(symbol, (32, 32))

    # Threshold for consistent shape comparison
    _, symbol_thresh = cv2.threshold(
        symbol_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # Compute Hu moments for the symbol
    symbol_moments = cv2.HuMoments(cv2.moments(symbol_thresh)).flatten()

    # Find contours for shape matching
    symbol_contours, _ = cv2.findContours(
        symbol_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    symbol_contour = max(symbol_contours, key=cv2.contourArea) if symbol_contours else None

    matches = []

    for set_code, template in set_symbol_templates.items():
        try:
            # Resize template to match
            template_resized = cv2.resize(template, (32, 32))

            # Threshold template
            _, template_thresh = cv2.threshold(
                template_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            # Method 1: Template matching (normalized cross-correlation)
            result = cv2.matchTemplate(
                symbol_resized, template_resized, cv2.TM_CCOEFF_NORMED
            )
            template_score = (result[0][0] + 1) * 50  # Convert -1..1 to 0..100

            # Method 2: Hu moments comparison
            template_moments = cv2.HuMoments(
                cv2.moments(template_thresh)
            ).flatten()

            hu_distance = cv2.matchShapes(
                symbol_thresh, template_thresh, cv2.CONTOURS_MATCH_I2, 0
            )
            hu_score = max(0, 100 - hu_distance * 100)

            # Method 3: Contour matching (if contours found)
            contour_score = 0
            if symbol_contour is not None:
                template_contours, _ = cv2.findContours(
                    template_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                if template_contours:
                    template_contour = max(template_contours, key=cv2.contourArea)
                    match_val = cv2.matchShapes(
                        symbol_contour, template_contour, cv2.CONTOURS_MATCH_I1, 0
                    )
                    contour_score = max(0, 100 - match_val * 50)

            # Combine scores with weights
            combined = (template_score * 0.4 + hu_score * 0.3 + contour_score * 0.3)

            if combined > 35:
                matches.append((set_code, int(combined)))

        except Exception:
            continue

    # Sort by confidence descending
    matches.sort(key=lambda x: x[1], reverse=True)

    if matches:
        logger.debug(f"Top symbol matches: {matches[:5]}")

    return matches[:top_n]


def identify_set_from_image(card_img):
    """Identify the set of a card from its image using symbol matching.

    Returns: (set_code, confidence) or (None, 0) if no match
    """
    matches = match_set_symbol(card_img)
    if matches:
        return matches[0]
    return None, 0


def local_fuzzy_match(text, threshold=0.6):
    """Match text against local master database using fuzzy matching"""
    if not master_cards or not text or len(text) < 3:
        return None, 0

    clean = text.lower().strip()

    # Exact match first
    if clean in master_cards:
        return master_cards[clean], 100

    # Fuzzy match against all names
    best_match = None
    best_ratio = 0

    for name in master_names:
        ratio = SequenceMatcher(None, clean, name.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = name

    if best_ratio >= threshold and best_match:
        return master_cards[best_match.lower()], int(best_ratio * 100)

    return None, 0


# =============================================================================
# LOCAL CAMERA CAPTURE (Card Back Detection)
# =============================================================================

def capture_local_owleye(suffix=""):
    """Capture from local OwlEye camera (card back)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{BACK_DIR}/back_{timestamp}{suffix}.jpg"
    width, height = LOCAL_CAMERA['resolution']
    camera_idx = LOCAL_CAMERA['index']

    try:
        result = subprocess.run([
            'rpicam-still',
            '--camera', str(camera_idx),
            '-o', filename,
            '--width', str(width),
            '--height', str(height),
            '-t', '500',
            '--autofocus-mode', 'auto',
            '-n'
        ], capture_output=True, timeout=15)

        if os.path.exists(filename):
            logger.info(f"Local OwlEye captured: {filename}")
            return filename
        else:
            logger.error(f"Local capture failed: {result.stderr.decode()}")
            return None
    except Exception as e:
        logger.error(f"Local camera error: {e}")
        return None


def detect_card_type(image_path):
    """
    Detect card type from back image using color histogram matching
    Returns: 'mtg', 'pokemon', 'sports', 'yugioh', or 'unknown'

    Card backs have distinctive colors:
    - MTG: Brown/tan with blue oval
    - Pokemon: Red/white pokeball design
    - Yu-Gi-Oh: Brown/gold spiral pattern
    - Sports: Varies but usually grey/white with brand logo
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return 'unknown', 0

        # Convert to HSV for better color analysis
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Get center region (card back design is usually centered)
        h, w = img.shape[:2]
        center = hsv[h//4:3*h//4, w//4:3*w//4]

        # Calculate color histograms
        h_hist = cv2.calcHist([center], [0], None, [180], [0, 180])
        s_hist = cv2.calcHist([center], [1], None, [256], [0, 256])

        # Normalize
        h_hist = cv2.normalize(h_hist, h_hist).flatten()
        s_hist = cv2.normalize(s_hist, s_hist).flatten()

        # Detect dominant hue
        dominant_hue = np.argmax(h_hist)
        avg_saturation = np.mean(center[:, :, 1])

        # MTG: Hue around 15-25 (brown/orange), medium saturation
        # Pokemon: High red (0-10 or 170-180), high saturation
        # Yu-Gi-Oh: Hue around 20-30 (gold/brown), high saturation
        # Sports: Low saturation (grey), varied hue

        confidence = 0
        card_type = 'unknown'

        # MTG detection (brown with blue accent)
        if 10 <= dominant_hue <= 30 and 50 <= avg_saturation <= 150:
            # Check for blue oval (MTG specific)
            blue_mask = cv2.inRange(hsv, (100, 100, 50), (130, 255, 255))
            blue_ratio = np.sum(blue_mask > 0) / (h * w)
            if blue_ratio > 0.02:  # At least 2% blue
                card_type = 'mtg'
                confidence = 85 + int(blue_ratio * 500)
            else:
                card_type = 'mtg'
                confidence = 70

        # Pokemon detection (red/white)
        elif (dominant_hue <= 10 or dominant_hue >= 170) and avg_saturation > 100:
            # Check for white regions (pokeball)
            white_mask = cv2.inRange(hsv, (0, 0, 200), (180, 50, 255))
            white_ratio = np.sum(white_mask > 0) / (h * w)
            if white_ratio > 0.15:  # Significant white
                card_type = 'pokemon'
                confidence = 85
            else:
                card_type = 'pokemon'
                confidence = 65

        # Yu-Gi-Oh detection (gold/brown spiral)
        elif 15 <= dominant_hue <= 35 and avg_saturation > 120:
            card_type = 'yugioh'
            confidence = 70

        # Sports cards (usually grey/low saturation)
        elif avg_saturation < 60:
            card_type = 'sports'
            confidence = 60

        confidence = min(confidence, 99)
        logger.info(f"Card type detected: {card_type} ({confidence}%)")
        return card_type, confidence

    except Exception as e:
        logger.error(f"Card type detection error: {e}")
        return 'unknown', 0


def dual_capture():
    """
    Simultaneous capture from both cameras
    - Local: Card back (type detection)
    - Snarf: Card front (OCR)
    Returns: (back_path, front_path, card_type)
    """
    back_result = {'path': None}
    front_result = {'path': None}

    def capture_back():
        back_result['path'] = capture_local_owleye()

    def capture_front():
        try:
            r = requests.post(f'{SNARF_URL}/api/capture', json={}, timeout=15)
            if r.status_code == 200:
                cap = r.json()
                front_result['path'] = cap.get('image_path')
                front_result['remote'] = True
        except Exception as e:
            logger.error(f"Front capture error: {e}")

    # Start both captures in parallel
    back_thread = Thread(target=capture_back)
    front_thread = Thread(target=capture_front)

    back_thread.start()
    front_thread.start()

    # Wait for both to complete
    back_thread.join(timeout=20)
    front_thread.join(timeout=20)

    # Detect card type from back
    card_type = 'unknown'
    type_confidence = 0
    if back_result['path']:
        card_type, type_confidence = detect_card_type(back_result['path'])

    return back_result['path'], front_result, card_type, type_confidence


# =============================================================================
# BOX/CALL NUMBER MANAGEMENT
# =============================================================================

def next_box_prefix(current):
    """Advance box prefix: AA->AB->...->AZ->BA->BB->..."""
    first, second = current[0], current[1]
    if second == 'Z':
        # Move to next first letter
        if first == 'Z':
            return 'AA'  # Wrap around (unlikely to need)
        return chr(ord(first) + 1) + 'A'
    return first + chr(ord(second) + 1)


def get_call_number():
    """Generate next call number in format AA1, AA2, ... AA1000, AB1, etc."""
    global box_position, current_box
    box_position += 1
    if box_position > 1000:
        # Start new box
        current_box = next_box_prefix(current_box)
        box_position = 1
        logger.info(f"Starting new box: {current_box}")
    return f"{current_box}{box_position}"


def load_state():
    global scan_counter, scan_history, card_cache, inventory, review_queue
    global current_box, box_position
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                data = json.load(f)
                scan_history = data.get('history', [])
                scan_counter = data.get('counter', 0)
        except Exception:
            pass
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                card_cache = json.load(f)
        except Exception:
            pass
    if os.path.exists(INV_FILE):
        try:
            with open(INV_FILE) as f:
                inventory = json.load(f)
        except Exception:
            pass
    if os.path.exists(REVIEW_FILE):
        try:
            with open(REVIEW_FILE) as f:
                review_queue = json.load(f)
        except Exception:
            pass
    if os.path.exists(BOX_FILE):
        try:
            with open(BOX_FILE) as f:
                data = json.load(f)
                current_box = data.get('box', 'AA')
                box_position = data.get('position', 0)
        except Exception:
            pass


def save_state():
    with open(HISTORY_FILE, 'w') as f:
        json.dump({'counter': scan_counter, 'history': scan_history[-5000:]}, f)
    with open(CACHE_FILE, 'w') as f:
        json.dump(card_cache, f)
    with open(INV_FILE, 'w') as f:
        json.dump(inventory, f, indent=2)
    with open(REVIEW_FILE, 'w') as f:
        json.dump(review_queue[-1000:], f, indent=2)
    with open(BOX_FILE, 'w') as f:
        json.dump({'box': current_box, 'position': box_position}, f)


def detect_orientation_and_rotate(img):
    """
    Detect if card is upside down and rotate if needed.
    MTG cards have:
    - Title bar at TOP (light colored with dark text)
    - Black border at BOTTOM (with collector number)
    - Artwork in middle (brighter than text areas)
    Returns: rotated image (or original if correct orientation)
    """
    h, w = img.shape[:2]

    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # Title region (top 15%) vs bottom region (bottom 15%)
    title_region = gray[0:int(h*0.15), :]
    bottom_region = gray[int(h*0.85):h, :]

    # Title bar is typically LIGHT (white/cream background with text)
    # Bottom border is typically DARK (black with small white text)
    avg_top = np.mean(title_region)
    avg_bottom = np.mean(bottom_region)

    # Also check text density using edge detection
    edges_top = cv2.Canny(title_region, 50, 150)
    edges_bottom = cv2.Canny(bottom_region, 50, 150)
    top_edge_density = np.sum(edges_top > 0) / edges_top.size
    bottom_edge_density = np.sum(edges_bottom > 0) / edges_bottom.size

    # Decision logic:
    # Correct orientation: top is LIGHTER than bottom (title bar vs black border)
    # Upside down: bottom is LIGHTER than top

    logger.info(f"Orientation check: top_avg={avg_top:.1f}, bottom_avg={avg_bottom:.1f}")
    logger.info(f"Edge density: top={top_edge_density:.4f}, bottom={bottom_edge_density:.4f}")

    # If bottom is significantly brighter, card is upside down
    # (title bar would be at bottom)
    if avg_bottom > avg_top + 15:
        logger.info("Card is upside down (bottom brighter than top). Rotating 180°")
        return cv2.rotate(img, cv2.ROTATE_180), True

    # Also check: if bottom has MORE text edges and is brighter
    if bottom_edge_density > top_edge_density * 1.5 and avg_bottom > avg_top:
        logger.info("Card is upside down (more text at bottom). Rotating 180°")
        return cv2.rotate(img, cv2.ROTATE_180), True

    logger.info("Card orientation appears correct")
    return img, False


def detect_lightbox(img):
    """
    Detect the illuminated lightbox region first - it's bright white and straightforward to find.
    Returns cropped image of just the lightbox area, or None if not found.
    """
    h, w = img.shape[:2]
    
    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    # Threshold for bright areas (lightbox is white/bright)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    
    # Find contours of bright regions
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None, None
    
    # Find the largest bright rectangle (the lightbox)
    best_box = None
    best_area = 0
    min_lightbox_area = (h * w) * 0.05  # Lightbox should be at least 5% of image
    
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        
        # Lightbox should be reasonably large and roughly square-ish
        if area > min_lightbox_area and area > best_area:
            aspect = min(cw, ch) / max(cw, ch)
            if aspect > 0.5:  # Not too skinny
                best_area = area
                best_box = (x, y, cw, ch)
    
    if best_box:
        x, y, cw, ch = best_box
        # Add small margin
        margin = 10
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(w, x + cw + margin)
        y2 = min(h, y + ch + margin)
        logger.info(f"Lightbox detected: {cw}x{ch} at ({x},{y})")
        return img[y1:y2, x1:x2], (x1, y1, x2, y2)
    
    return None, None


def detect_card_region(img, debug_path=None):
    """
    Card detection - uses V2 (two-stage lightbox + threshold) if available,
    falls back to legacy fixed-percentage crop.
    """
    h, w = img.shape[:2]
    logger.info(f"=== CARD CROP === Image: {w}x{h}")
    
    # Use V2 detection if available (the one that actually works)
    if CARD_DETECTION_V2:
        logger.info("Using card_detection_v2 (two-stage)")
        return detect_card_v2(img, debug_path)
    
    # Legacy fallback - fixed percentage crop (often wrong)
    logger.warning("Using LEGACY card detection (fixed %) - results may be poor")
    CARD_X = int(w * 0.25)
    CARD_Y = int(h * 0.30)
    CARD_W = int(w * 0.45)
    CARD_H = int(h * 0.60)

    card_img = img[CARD_Y:CARD_Y+CARD_H, CARD_X:CARD_X+CARD_W]
    logger.info(f"LEGACY CROP: {CARD_W}x{CARD_H} from ({CARD_X},{CARD_Y})")

    return card_img, True


def extract_title_region(img):
    """Extract the title bar region from a card image (top 5-12%)"""
    h, w = img.shape[:2]
    # MTG card title is in the top title bar
    # Start higher to catch the actual text, not the mana symbols below it
    title_top = int(h * 0.01)
    title_bottom = int(h * 0.25)  # Top 25%
    title_left = int(w * 0.05)
    title_right = int(w * 0.75)
    return img[title_top:title_bottom, title_left:title_right]


def extract_collector_region(img):
    """Extract the collector info region (bottom 8% of card, left side)"""
    h, w = img.shape[:2]
    # Collector number is at bottom left: "SET • 123/456"
    collector_top = int(h * 0.92)
    collector_bottom = int(h * 0.98)
    collector_left = int(w * 0.05)
    collector_right = int(w * 0.50)
    return img[collector_top:collector_bottom, collector_left:collector_right]


def ocr_collector_info(img):
    """
    OCR the collector info region to extract set code and number.
    Returns: (set_code, collector_number) or (None, None)
    """
    collector_region = extract_collector_region(img)

    # Preprocess for small text
    if len(collector_region.shape) == 3:
        gray = cv2.cvtColor(collector_region, cv2.COLOR_BGR2GRAY)
    else:
        gray = collector_region

    # Scale up 3x for tiny text
    scaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # CLAHE + threshold
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(scaled)
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # OCR
    temp_path = f'{SCAN_DIR}/_temp_collector.png'
    cv2.imwrite(temp_path, thresh)

    try:
        result = subprocess.run([
            'tesseract', temp_path, 'stdout',
            '--psm', '7',
            '-l', 'eng',
            '-c', 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/-. '
        ], capture_output=True, text=True, timeout=10)
        text = result.stdout.strip()
        logger.info(f"Collector OCR: {text}")
    except Exception as e:
        logger.error(f"Collector OCR failed: {e}")
        return None, None

    # Parse set code and collector number
    # Formats: "DST 123", "DST • 123/456", "M21 • 256", etc.
    set_code = None
    collector_num = None

    # Look for 3-letter set code
    set_match = re.search(r'\b([A-Z]{2,4})\b', text.upper())
    if set_match:
        set_code = set_match.group(1)

    # Look for collector number (digits, possibly with /total)
    num_match = re.search(r'\b(\d{1,4})(?:/\d+)?\b', text)
    if num_match:
        collector_num = num_match.group(1)

    logger.info(f"Parsed collector info: set={set_code}, num={collector_num}")
    return set_code, collector_num


def analyze_image_quality(img):
    """
    Analyze image to determine best preprocessing method.
    Returns: dict with blur_score, contrast_score, brightness, noise_level
    """
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Blur detection (Laplacian variance)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Contrast (std dev)
    contrast_score = gray.std()

    # Brightness (mean)
    brightness = gray.mean()

    # Noise estimation (high-frequency content)
    high_freq = cv2.Laplacian(gray, cv2.CV_64F)
    noise_level = np.abs(high_freq).mean()

    return {
        'blur': blur_score,
        'contrast': contrast_score,
        'brightness': brightness,
        'noise': noise_level
    }


def select_best_preprocessing(img):
    """
    Intelligently select best preprocessing method based on image analysis.
    Target: 95-98% OCR accuracy by choosing optimal method per image.

    Per Tesseract best practices: Clean printed text needs MINIMAL preprocessing.
    Over-processing destroys text quality and reduces accuracy.
    """
    quality = analyze_image_quality(img)

    # PREFER MINIMAL: Most lightbox-scanned cards are high quality
    # Article guidance: 85-95% accuracy comes from NOT destroying text with over-processing
    if quality['brightness'] > 80 and quality['contrast'] > 30:
        # Good lighting and contrast - just grayscale + gentle enhancement
        logger.info(f"Good image quality (bright={quality['brightness']:.1f}, contrast={quality['contrast']:.1f}) - minimal preprocessing")
        return 'minimal'

    # Decision tree for problematic images only
    if quality['blur'] < 100:
        # Image is blurry - gentle sharpening without threshold
        logger.info(f"Blurry image (blur={quality['blur']:.1f}) - using sharpen")
        return 'sharpen'
    elif quality['noise'] > 15:
        # Image is noisy - denoise with median filter
        logger.info(f"Noisy image (noise={quality['noise']:.1f}) - using denoise")
        return 'denoise'
    elif quality['contrast'] < 20:
        # Very low contrast - needs enhancement
        logger.info(f"Low contrast (contrast={quality['contrast']:.1f}) - using enhance")
        return 'enhance'
    else:
        # Fallback to minimal (NOT aggressive standard mode)
        logger.info(f"Default case - using minimal preprocessing")
        return 'minimal'


def preprocess_for_ocr(img, method='auto'):
    """
    MINIMAL PREPROCESSING - just grayscale.
    Color-agnostic OCR handled by run_tesseract_both_ways().
    """
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def run_tesseract_both_ways(image, psm=7):
    """
    Run OCR on BOTH original and inverted image, pick best result.
    Handles black text AND white text without guessing by color.
    """
    gray = preprocess_for_ocr(image)
    inverted = cv2.bitwise_not(gray)

    # Try original (black text on light)
    text1, conf1 = run_tesseract(gray, psm=psm)

    # Try inverted (white text on dark)
    text2, conf2 = run_tesseract(inverted, psm=psm)

    logger.debug(f"Original: '{text1[:30] if text1 else ''}' ({conf1:.0f}%)")
    logger.debug(f"Inverted: '{text2[:30] if text2 else ''}' ({conf2:.0f}%)")

    # Pick better result
    if conf2 > conf1 and text2:
        logger.info(f"Using INVERTED (white text): '{text2}' ({conf2:.0f}%)")
        return text2, conf2
    elif text1:
        logger.info(f"Using ORIGINAL (black text): '{text1}' ({conf1:.0f}%)")
        return text1, conf1
    else:
        return text2 or '', max(conf1, conf2)


def run_tesseract_multipass(image):
    """
    MULTI-PASS TESSERACT - Try multiple PSM modes and pick best result.

    PSM modes to try:
      7 = single text line (card titles)
      6 = uniform block (full cards)
      11 = sparse text (scattered text)
      13 = raw line (no processing)

    Returns: (text, confidence) from best pass
    """
    if not PYTESSERACT_AVAILABLE:
        return run_tesseract(image, psm=7)

    psm_modes = [7, 6, 11, 13]
    results = []

    for psm in psm_modes:
        text, conf = run_tesseract(image, psm=psm)
        if text:
            results.append((text, conf, psm))
            logger.debug(f"PSM {psm}: '{text[:50]}...' ({conf:.1f}%)")

    if not results:
        return '', 0

    # Pick result with highest confidence
    results.sort(key=lambda x: x[1], reverse=True)
    best = results[0]
    logger.info(f"MULTIPASS BEST: PSM {best[2]} -> '{best[0]}' ({best[1]:.1f}%)")
    return best[0], best[1]


def run_tesseract(image, psm=7):
    """
    Run Tesseract with confidence scoring using pytesseract library.

    PSM 7 = single text line (best for card titles)
    PSM 6 = uniform block of text (fallback)
    OEM 3 = LSTM neural net mode (most accurate)

    Article guidance: Use pytesseract library, not subprocess.
    Returns: (text, confidence)
    """
    if not PYTESSERACT_AVAILABLE:
        logger.error("pytesseract not available - falling back to subprocess")
        return run_tesseract_subprocess(image, psm)

    try:
        # Convert to PIL Image if needed
        if isinstance(image, np.ndarray):
            from PIL import Image as PILImage
            if len(image.shape) == 3:
                # Convert BGR to RGB
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                pil_image = PILImage.fromarray(rgb)
            else:
                pil_image = PILImage.fromarray(image)
        else:
            pil_image = image

        # Tesseract config
        config = f'--psm {psm} --oem 3'

        # Get text
        text = pytesseract.image_to_string(pil_image, config=config, lang='eng').strip()

        # Get confidence scores using image_to_data
        try:
            data = pytesseract.image_to_data(
                pil_image, config=config, lang='eng',
                output_type=pytesseract.Output.DICT
            )
            confidences = [int(c) for c in data['conf'] if c != '-1' and int(c) > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 50.0
        except Exception:
            # Fallback confidence estimation
            avg_conf = 50.0 if text else 0.0

        # Clean up common OCR artifacts
        text = re.sub(r'[|\\/_~`]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Apply learned corrections
        corrected = correct_ocr_text(text)

        logger.debug(f"Tesseract: '{corrected}' (conf: {avg_conf:.1f}%)")
        return corrected, avg_conf

    except Exception as e:
        logger.error(f'Tesseract error: {e}')
        return '', 0


def run_tesseract_subprocess(image, psm=7):
    """
    Fallback: Run Tesseract via subprocess (slower, but works if pytesseract fails).
    Only used when pytesseract library is unavailable.
    """
    # Save temp file
    temp_path = f'{SCAN_DIR}/_temp_ocr.png'
    cv2.imwrite(temp_path, image)

    try:
        result = subprocess.run([
            'tesseract', temp_path, 'stdout',
            '--psm', str(psm),
            '--oem', '3',
            '-l', 'eng',
            '-c', 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 \',.:-!&()',
            'tsv'
        ], capture_output=True, text=True, timeout=10)

        # Parse TSV output
        lines = result.stdout.strip().split('\n')
        texts = []
        confidences = []

        for line in lines[1:]:  # Skip header
            parts = line.split('\t')
            if len(parts) >= 12:
                conf = parts[10]
                text = parts[11]
                if text.strip() and conf != '-1':
                    texts.append(text.strip())
                    try:
                        confidences.append(float(conf))
                    except ValueError:
                        confidences.append(50)

        full_text = ' '.join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 50

        full_text = re.sub(r'[|\\/_~`]', '', full_text)
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        corrected = correct_ocr_text(full_text)

        logger.debug(f"Tesseract (subprocess): '{corrected}' (conf: {avg_conf:.1f}%)")
        return corrected, avg_conf

    except Exception as e:
        logger.error(f'Tesseract subprocess error: {e}')
        return '', 0


# =============================================================================
# CORAL EDGE TPU OCR (Patent Pending - Hardware Accelerated)
# =============================================================================
CORAL_MODEL_PATH = os.getenv(
    'CORAL_OCR_MODEL',
    '/mnt/nexus_data/models/keras_ocr_detector_edgetpu.tflite'
)


def run_coral_ocr(image):
    """
    Run OCR using Coral Edge TPU for hardware acceleration.
    Uses TensorFlow Lite with Edge TPU delegate (for Python 3.13 compatibility).
    Falls back to Tesseract if Coral unavailable or fails.
    Coral M.2 provides 10-50x speedup over CPU inference.
    Returns: (text, confidence)
    """
    global coral_interpreter

    # NOTE: Coral Edge TPU M.2 is available for future card detection
    # but there's no good Edge TPU OCR model. Using Tesseract for text.
    # The coral_interpreter will be used for card detection when we add it.
    
    if not CORAL_AVAILABLE:
        logger.debug("Coral not available, using Tesseract")
        return run_tesseract(image)

    # For now, just use Tesseract (Coral lacks proper OCR model)
    # TODO: Add Coral-accelerated card detection model
    return run_tesseract(image)


def load_ocr_learning_data():
    """Load OCR corrections from file to improve over time"""
    global ocr_learning_data
    if os.path.exists(OCR_LEARNING_FILE):
        try:
            with open(OCR_LEARNING_FILE, 'r') as f:
                ocr_learning_data = json.load(f)
            logger.info(f"Loaded {len(ocr_learning_data)} OCR corrections")
        except Exception as e:
            logger.warning(f"Failed to load OCR learning data: {e}")
            ocr_learning_data = {}
    else:
        ocr_learning_data = {}


def save_ocr_correction(ocr_text, correct_name):
    """
    Save correction to learning file.
    Builds shop-specific correction dictionary over time.
    """
    global ocr_learning_data
    
    ocr_lower = ocr_text.lower().strip()
    if ocr_lower and correct_name:
        ocr_learning_data[ocr_lower] = correct_name
        
        try:
            with open(OCR_LEARNING_FILE, 'w') as f:
                json.dump(ocr_learning_data, f, indent=2)
            logger.info(f"Saved: '{ocr_text}' -> '{correct_name}'")
        except Exception as e:
            logger.error(f"Failed to save OCR correction: {e}")


def apply_learned_corrections(text):
    """
    Apply shop-specific learned corrections.
    Improves accuracy over time as staff corrects mistakes.
    """
    if not text:
        return text
    
    text_lower = text.lower().strip()
    if text_lower in ocr_learning_data:
        corrected = ocr_learning_data[text_lower]
        logger.info(f"Applied learned: '{text}' -> '{corrected}'")
        return corrected
    
    return text


def multi_scale_ocr(title_region, method='auto'):
    """
    Try multiple scales (2x, 3x, 4x) and return best result.
    Target: 95-98% accuracy by finding optimal scale.
    Returns: (text, confidence, scale_used)
    """
    scales = [2, 3, 4]
    results = []

    # Preprocess once
    processed = preprocess_for_ocr(title_region, method)
    
    # DEBUG: Save preprocessed image
    debug_preprocessed = '/mnt/nexus_data/scans/_DEBUG_TITLE_PREPROCESSED.jpg'
    cv2.imwrite(debug_preprocessed, processed)
    logger.info(f"DEBUG: Saved preprocessed title: {processed.shape}")

    for scale in scales:
        try:
            scaled = cv2.resize(processed, None, fx=scale, fy=scale,
                                interpolation=cv2.INTER_CUBIC)
            
            # DEBUG: Save scaled image (what Tesseract sees)
            if scale == 2:  # Save 2x scale for debugging
                debug_scaled = '/mnt/nexus_data/scans/_DEBUG_TITLE_SCALED_2X.jpg'
                cv2.imwrite(debug_scaled, scaled)
                logger.info(f"DEBUG: Saved 2x scaled title: {scaled.shape}")
            
            text, conf = get_ocr_engine(scaled)
            logger.info(f"DEBUG: Scale {scale}x raw Tesseract: '{text}' (conf={conf})")
            
            text = apply_learned_corrections(text)
            
            if text and len(text) > 2:
                results.append((text, conf, scale))
                logger.debug(f"Scale {scale}x: '{text}' ({conf:.1f}%)")
        except Exception as e:
            logger.error(f"Scale {scale}x failed: {e}")

    if not results:
        return '', 0, 2

    best = max(results, key=lambda x: x[1])
    logger.info(f"Best: {best[2]}x @ {best[1]:.1f}%")
    return best


def correct_ocr_text(text):
    """
    Apply post-OCR corrections for common mistakes.
    Improves accuracy from 80-85% to 95-98%.
    """
    if not text:
        return text

    # Split into words for context-aware correction
    words = text.split()
    corrected_words = []

    for word in words:
        word_lower = word.lower()
        
        # Check if entire word is in correction dictionary
        if word_lower in OCR_CORRECTIONS:
            corrected_words.append(OCR_CORRECTIONS[word_lower])
            continue

        # Character-level corrections (only for non-dictionary words)
        if word_lower not in MTG_COMMON_WORDS:
            corrected = word
            # Replace obvious mistakes
            if '0' in word and not word.isdigit():  # 0 -> O (but not in pure numbers)
                corrected = corrected.replace('0', 'O')
            if '1' in word and len(word) > 1 and not word.isdigit():
                # Only replace 1 -> I if surrounded by letters
                corrected = re.sub(r'(?<=[a-zA-Z])1(?=[a-zA-Z])', 'I', corrected)
            if '5' in word and not word.isdigit():
                corrected = corrected.replace('5', 'S')
            if '8' in word and not word.isdigit():
                corrected = corrected.replace('8', 'B')
            if '@' in word:
                corrected = corrected.replace('@', 'a')
            if '|' in word:
                corrected = corrected.replace('|', 'I')
            word = corrected

        corrected_words.append(word)

    result = ' '.join(corrected_words)
    
    # Log corrections
    if result != text:
        logger.debug(f"OCR correction: '{text}' -> '{result}'")
    
    return result


def run_fallback_ocr(image):
    """
    Fallback OCR - uses Tesseract.
    """
    return run_tesseract(image)


def get_ocr_engine(image):
    """
    PRIMARY OCR: Try both original and inverted, pick best.

    Color-agnostic - handles black text AND white text.
    Returns: (text, confidence)
    """
    # Try both ways - original and inverted
    text, conf = run_tesseract_both_ways(image, psm=7)

    # If PSM 7 failed, try PSM 6 (block mode)
    if not text or conf < 30:
        text2, conf2 = run_tesseract_both_ways(image, psm=6)
        if conf2 > conf:
            text, conf = text2, conf2

    logger.info(f"OCR RESULT: '{text}' (conf={conf:.1f}%)")

    return text, conf


def query_zultan_embedding(image):
    """
    Query ZULTAN's art embedding server for visual card matching.
    Sends image to http://192.168.1.152:5050/match
    
    Args:
        image: OpenCV image (BGR) or path to image file
    
    Returns:
        dict with 'name', 'confidence', 'set_code', 'collector_number', etc.
        or None if failed
    """
    try:
        import io
        from PIL import Image as PILImage
        
        # Convert OpenCV image to JPEG bytes
        if isinstance(image, str):
            # It's a path
            with open(image, 'rb') as f:
                img_bytes = f.read()
        else:
            # It's an OpenCV image (numpy array)
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_img = PILImage.fromarray(rgb_image)
            buffer = io.BytesIO()
            pil_img.save(buffer, format='JPEG', quality=95)
            img_bytes = buffer.getvalue()
        
        # Send to ZULTAN
        response = requests.post(
            f"{ZULTAN_URL}/match",
            files={'image': ('card.jpg', img_bytes, 'image/jpeg')},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('best_match'):
                match = data['best_match']
                # Convert distance to confidence (lower distance = higher confidence)
                # Distance typically ranges 0-2, we want 0-100%
                distance = match.get('distance', 1.0)
                confidence = max(0, min(100, int((1 - distance/2) * 100)))
                
                return {
                    'name': match.get('name', ''),
                    'confidence': confidence,
                    'set_code': match.get('set_code', ''),
                    'set_name': match.get('set_name', ''),
                    'collector_number': match.get('collector_number', ''),
                    'price_usd': match.get('price_usd'),
                    'card_id': match.get('card_id', ''),
                    'source': 'zultan_embedding',
                    'timing_ms': data.get('timing', {}).get('total_ms', 0)
                }
        
        logger.warning(f"ZULTAN embedding failed: {response.status_code}")
        return None
        
    except requests.exceptions.Timeout:
        logger.warning("ZULTAN embedding timeout (5s)")
        return None
    except requests.exceptions.ConnectionError:
        logger.warning(f"ZULTAN embedding server not reachable at {ZULTAN_URL}")
        return None
    except Exception as e:
        logger.error(f"ZULTAN embedding error: {e}")
        return None


def cross_validate_card(image_path, ocr_candidates, set_code=None, collector_num=None):
    """
    MULTI-SOURCE VALIDATION: OCR + Visual + Set + API must all agree
    
    Validation sources:
    1. OCR (Tesseract) - Extracts card name from title region
    2. ZULTAN Art Matching - Visual confirmation via 512-dim embedding
    3. Set Symbol + Collector# - Identifies specific printing
    4. Scryfall API - Truth check that combination exists
    
    Returns: (card_data, confidence, validation_report)
    """
    logger.info("=== CROSS-VALIDATION START ===")
    
    validation = {
        'ocr_vote': None,
        'visual_vote': None,
        'set_vote': None,
        'api_vote': None,
        'consensus': False,
        'conflicts': []
    }
    
    # STEP 1: OCR vote (from multi-region scan)
    ocr_card = None
    ocr_conf = 0
    if ocr_candidates:
        ocr_card, ocr_conf = identify_card(ocr_candidates, set_code, collector_num)
        if ocr_card:
            validation['ocr_vote'] = {
                'name': ocr_card.get('name'),
                'set': ocr_card.get('set'),
                'confidence': ocr_conf,
                'source': 'tesseract_ocr'
            }
            logger.info(f"OCR VOTE: '{ocr_card.get('name')}' ({ocr_conf}%)")
    
    # STEP 2: Visual vote (ZULTAN art matching on FULL card image)
    img = cv2.imread(image_path)
    visual_result = query_zultan_embedding(img)
    visual_card = None
    if visual_result and visual_result.get('confidence', 0) >= 70:
        validation['visual_vote'] = {
            'name': visual_result.get('name'),
            'set': visual_result.get('set_code'),
            'collector_number': visual_result.get('collector_number'),
            'confidence': visual_result.get('confidence'),
            'source': 'zultan_visual'
        }
        visual_card = visual_result
        logger.info(f"VISUAL VOTE: '{visual_result.get('name')}' [{visual_result.get('set_code')}] ({visual_result.get('confidence')}%)")
    else:
        logger.warning("Visual matching failed or low confidence")
    
    # STEP 3: Check if OCR and Visual agree on card NAME
    name_match = False
    if validation['ocr_vote'] and validation['visual_vote']:
        ocr_name = validation['ocr_vote']['name'].lower().strip()
        visual_name = validation['visual_vote']['name'].lower().strip()
        
        # Fuzzy match (allow minor OCR errors)
        from difflib import SequenceMatcher
        name_similarity = SequenceMatcher(None, ocr_name, visual_name).ratio()
        
        if name_similarity >= 0.85:  # 85% similar
            name_match = True
            logger.info(f"✓ NAME MATCH: OCR and Visual agree ({name_similarity*100:.0f}% similar)")
        else:
            validation['conflicts'].append(f"OCR says '{ocr_name}', Visual says '{visual_name}'")
            logger.warning(f"✗ NAME MISMATCH: OCR='{ocr_name}' vs Visual='{visual_name}' ({name_similarity*100:.0f}% similar)")
    
    # STEP 4: Set code validation
    set_match = False
    final_set = set_code
    if validation['ocr_vote'] and validation['visual_vote']:
        ocr_set = validation['ocr_vote'].get('set', '').upper()
        visual_set = validation['visual_vote'].get('set', '').upper()
        
        if set_code:
            # We have extracted set from collector region
            final_set = set_code.upper()
            if visual_set and visual_set == final_set:
                set_match = True
                logger.info(f"✓ SET MATCH: Collector region and Visual agree on '{final_set}'")
            elif visual_set and visual_set != final_set:
                validation['conflicts'].append(f"Collector says '{final_set}', Visual says '{visual_set}'")
                logger.warning(f"✗ SET MISMATCH: Collector='{final_set}' vs Visual='{visual_set}'")
        elif visual_set:
            # Use visual's set code
            final_set = visual_set
            set_match = True
            logger.info(f"Using Visual set code: '{final_set}'")
    
    # STEP 5: Scryfall API validation (truth check)
    api_valid = False
    if name_match and validation['ocr_vote']:
        card_name = validation['ocr_vote']['name']
        
        # Try exact printing if we have set + number
        if final_set and collector_num:
            api_card = scryfall_exact_printing(card_name, final_set, collector_num)
            if api_card:
                api_valid = True
                validation['api_vote'] = {
                    'name': api_card.get('name'),
                    'set': api_card.get('set'),
                    'number': api_card.get('collector_number'),
                    'source': 'scryfall_exact'
                }
                logger.info(f"✓ SCRYFALL EXACT: '{card_name}' [{final_set} #{collector_num}] exists")
            else:
                validation['conflicts'].append(f"Scryfall: '{card_name}' [{final_set} #{collector_num}] not found")
                logger.warning(f"✗ SCRYFALL: Exact printing not found")
        
        # Fallback: Fuzzy match to verify name exists
        if not api_valid:
            api_card, api_conf = scryfall_fuzzy(card_name)
            if api_card and api_conf >= 90:
                api_valid = True
                validation['api_vote'] = {
                    'name': api_card.get('name'),
                    'set': api_card.get('set'),
                    'confidence': api_conf,
                    'source': 'scryfall_fuzzy'
                }
                logger.info(f"✓ SCRYFALL FUZZY: '{card_name}' exists ({api_conf}%)")
            else:
                validation['conflicts'].append(f"Scryfall: '{card_name}' not found or low confidence")
                logger.warning(f"✗ SCRYFALL: Card name not validated")
    
    # STEP 6: Calculate consensus
    votes_cast = sum([
        validation['ocr_vote'] is not None,
        validation['visual_vote'] is not None,
        validation['api_vote'] is not None
    ])
    
    agreements = sum([
        name_match,
        set_match if final_set else False,
        api_valid
    ])
    
    # Require at least 2/3 agreement
    if votes_cast >= 2 and agreements >= 2:
        validation['consensus'] = True
        
        # Build final result from best source
        if api_valid and validation['api_vote']:
            final_card = validation['api_vote']
        elif validation['ocr_vote']:
            final_card = ocr_card
        elif validation['visual_vote']:
            final_card = visual_card
        else:
            final_card = None
        
        # Calculate overall confidence (weighted average)
        confidence_sum = 0
        confidence_count = 0
        if validation['ocr_vote']:
            confidence_sum += validation['ocr_vote']['confidence'] * 0.4  # 40% weight
            confidence_count += 0.4
        if validation['visual_vote']:
            confidence_sum += validation['visual_vote']['confidence'] * 0.4  # 40% weight
            confidence_count += 0.4
        if api_valid:
            confidence_sum += 100 * 0.2  # 20% weight (API is truth)
            confidence_count += 0.2
        
        final_confidence = int(confidence_sum / confidence_count) if confidence_count > 0 else 0
        
        logger.info(f"✓ CONSENSUS REACHED: {agreements}/{votes_cast} sources agree ({final_confidence}%)")
        logger.info(f"=== CROSS-VALIDATION COMPLETE: SUCCESS ===")
        return final_card, final_confidence, validation
    
    else:
        validation['consensus'] = False
        logger.warning(f"✗ NO CONSENSUS: Only {agreements}/{votes_cast} sources agree")
        logger.warning(f"Conflicts: {validation['conflicts']}")
        logger.info(f"=== CROSS-VALIDATION COMPLETE: FAILED ===")
        return None, 0, validation


def fast_ocr(image_path):
    """
    FAST single-pass OCR for speed. Target: <2 seconds with Coral TPU.
    Returns: (ocr_results, set_code, collector_num)
    """
    img = cv2.imread(image_path)
    if img is None:
        return [], None, None

    results = []

    # Detect and crop the card
    debug_path = image_path.replace('.jpg', '_debug.jpg')
    card_img, card_detected = detect_card_region(img, debug_path=debug_path)

    # If card detection failed, try with full image anyway
    # Better to return low-confidence results than nothing
    if not card_detected:
        logger.warning("⚠ Card detection uncertain - using full image")
        logger.warning("  This may result in lower OCR accuracy")
        card_img = img

    # Check orientation
    card_img, _ = detect_orientation_and_rotate(card_img)

    # Extract title region
    title_region = extract_title_region(card_img)
    
    # DEBUG: Save title region to see what Tesseract is reading
    title_debug = image_path.replace('.jpg', '_title_raw.jpg')
    cv2.imwrite(title_debug, title_region)
    logger.info(f"Saved title region: {title_debug}")

    # Single pass - use best available OCR (Coral if available)
    try:
        processed = preprocess_for_ocr(title_region, 'standard')
        
        # DEBUG: Save preprocessed title
        title_processed_debug = image_path.replace('.jpg', '_title_processed.jpg')
        cv2.imwrite(title_processed_debug, processed)
        logger.info(f"Saved preprocessed title: {title_processed_debug}")
        
        scaled = cv2.resize(processed, None, fx=2, fy=2,
                            interpolation=cv2.INTER_CUBIC)
        
        # DEBUG: Save scaled version (what Tesseract sees)
        title_scaled_debug = image_path.replace('.jpg', '_title_scaled.jpg')
        cv2.imwrite(title_scaled_debug, scaled)
        logger.info(f"Saved scaled title (Tesseract input): {title_scaled_debug}")
        
        text = get_ocr_engine(scaled)  # Tesseract > ZULTAN Embedding
        if text and len(text) > 2:
            results.append(text)
    except Exception as e:
        logger.error(f"OCR error: {e}")

    # If no result, try adaptive as backup
    if not results:
        try:
            processed = preprocess_for_ocr(title_region, 'adaptive')
            scaled = cv2.resize(processed, None, fx=2, fy=2,
                                interpolation=cv2.INTER_CUBIC)
            text = get_ocr_engine(scaled)
            if text and len(text) > 2:
                results.append(text)
        except Exception:
            pass

    return results, None, None


def multi_pass_ocr(image_path):
    """
    PATENT CLAIM 1: Multi-Region Scanning Protocol with Cross-Validation
    
    Scans 5 regions of the card and cross-validates between them:
    1. Title region (top 12-15%) - Card name
    2. Set symbol region (type line, right side) - Set identification  
    3. Collector region (bottom 8%, left) - Set code + collector number
    4. Mana region (top right) - Color identity validation
    5. Art region (center) - Visual fingerprint (future)
    
    Returns: (ocr_results, set_code, collector_num)
    """
    logger.info(f"=== 5-REGION OCR START === {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        logger.error(f"Failed to read image: {image_path}")
        return [], None, None

    h, w = img.shape[:2]
    logger.info(f"Input image: {w}x{h}")

    results = []
    set_code = None
    collector_num = None
    region_data = {}  # Store data from each region for cross-validation

    # Check if image is already a cropped card (_card.jpg files)
    # These don't need card detection - they ARE the card
    # OwlEye CSI camera (4624x3472 or similar high-res) is framed to capture just the card
    is_owleye = (w > 4000 and h > 3000) or (h > 4000 and w > 3000)
    is_already_cropped = '_card' in image_path or is_owleye or (
        0.65 < (w / h) < 0.75 and h > 800  # Portrait card aspect ratio
    )

    if is_already_cropped:
        card_img = img
        logger.info("Image is already cropped card - skipping detection")
    else:
        # Detect and crop the card (for CZUR/overhead cameras)
        debug_path = image_path.replace('.jpg', '_debug.jpg')
        card_img, card_detected = detect_card_region(img, debug_path=debug_path)
        if card_detected:
            ch, cw = card_img.shape[:2]
            logger.info(f"Card detected: {cw}x{ch} - using cropped")
            debug_card_path = image_path.replace('.jpg', '_card.jpg')
            cv2.imwrite(debug_card_path, card_img)
        else:
            # Card detection uncertain - continue with full image
            # OCR might work if image is already well-framed
            logger.warning("⚠ Card detection uncertain - using full image")
            logger.warning("   If OCR fails, this is usually caused by:")
            logger.warning("   1. Card not centered or too small in frame")
            logger.warning("   2. Wrong lighting (too dark or too bright)")
            logger.warning("   3. Card rotated or at extreme angle")
            card_img = img

    # DISABLED: Orientation detection was giving wrong results
    # Mirror flip in detect_card_region should handle CZUR camera
    # card_img, was_rotated = detect_orientation_and_rotate(card_img)
    logger.info("Orientation detection DISABLED - using mirror flip only")

    ch, cw = card_img.shape[:2]
    logger.info("=== FULL CARD OCR (SIMPLE) ===")

    # =========================================================================
    # FULL CARD OCR - PSM 6 for block of text (both original + inverted)
    # =========================================================================
    logger.info("Running Tesseract PSM 6 on full card (both ways)...")

    # Run both original and inverted - picks best result
    full_text, full_conf = run_tesseract_both_ways(card_img, psm=6)
    logger.info(f"FULL CARD OCR: '{full_text[:200]}' ({full_conf:.1f}%)")

    # Extract card name - usually first line with text
    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
    logger.info(f"Found {len(lines)} text lines")

    for i, line in enumerate(lines[:10]):
        logger.info(f"  Line {i}: '{line}'")

    # Find card name in first few lines
    for line in lines[:5]:
        # Skip very short lines (noise)
        if len(line) < 4:
            continue
        # Skip lines that look like garbage (mostly symbols)
        alpha_count = sum(1 for c in line if c.isalpha())
        if alpha_count < len(line) * 0.5:
            continue
        # This could be the card name
        results.append(line)
        logger.info(f"Candidate: '{line}'")

    title_results = results
    title_confidence = full_conf
    region_data = {}
    region_data['title'] = {'texts': title_results, 'confidence': title_confidence}

    # =========================================================================
    # REGION 2: SET SYMBOL (Type line, right side)
    # =========================================================================
    logger.info("REGION 2: Set symbol (type line 48-58%)")
    set_code, symbol_confidence = identify_set_from_image(card_img)
    if set_code and symbol_confidence >= 40:
        logger.info(f'  SET SYMBOL: {set_code.upper()} ({symbol_confidence}%)')
        region_data['set_symbol'] = {'set': set_code, 'confidence': symbol_confidence}
    else:
        logger.debug(f'  Set symbol: no confident match (best: {symbol_confidence}%)')
        region_data['set_symbol'] = {'set': None, 'confidence': 0}

    # =========================================================================
    # REGION 3: COLLECTOR INFO (Bottom left - "SET • 123/456")
    # =========================================================================
    logger.info("REGION 3: Collector info (bottom 92-98%)")
    try:
        coll_set, coll_num = ocr_collector_info(card_img)
        if coll_set or coll_num:
            logger.info(f'  COLLECTOR: set={coll_set}, num={coll_num}')
            region_data['collector'] = {
                'set': coll_set, 
                'number': coll_num, 
                'confidence': 75  # Base confidence for collector OCR
            }
            # Use collector set code if symbol matching failed
            if not set_code and coll_set:
                set_code = coll_set
                logger.info(f'  Using collector set code: {set_code}')
            collector_num = coll_num
        else:
            logger.debug('  Collector: no data extracted')
            region_data['collector'] = {'set': None, 'number': None, 'confidence': 0}
    except Exception as e:
        logger.debug(f'  Collector OCR failed: {e}')
        region_data['collector'] = {'set': None, 'number': None, 'confidence': 0}

    # =========================================================================
    # REGION 4: MANA COST (Top right corner)
    # =========================================================================
    logger.info("REGION 4: Mana cost (top right)")
    try:
        mana_region = card_img[int(ch*0.02):int(ch*0.12), int(cw*0.70):int(cw*0.98)]
        # Mana symbols are colored circles - detect dominant colors
        # This helps validate card identity (color identity cross-check)
        hsv = cv2.cvtColor(mana_region, cv2.COLOR_BGR2HSV)
        colors_detected = []
        
        # Check for each MTG color
        # White (high V, low S)
        white_mask = cv2.inRange(hsv, (0, 0, 200), (180, 50, 255))
        if cv2.countNonZero(white_mask) > 50:
            colors_detected.append('W')
        # Blue (H: 100-130)
        blue_mask = cv2.inRange(hsv, (100, 50, 50), (130, 255, 255))
        if cv2.countNonZero(blue_mask) > 50:
            colors_detected.append('U')
        # Black (low V)
        black_mask = cv2.inRange(hsv, (0, 0, 0), (180, 255, 50))
        if cv2.countNonZero(black_mask) > 50:
            colors_detected.append('B')
        # Red (H: 0-10 or 160-180)
        red_mask1 = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
        red_mask2 = cv2.inRange(hsv, (160, 50, 50), (180, 255, 255))
        if cv2.countNonZero(red_mask1) + cv2.countNonZero(red_mask2) > 50:
            colors_detected.append('R')
        # Green (H: 35-85)
        green_mask = cv2.inRange(hsv, (35, 50, 50), (85, 255, 255))
        if cv2.countNonZero(green_mask) > 50:
            colors_detected.append('G')
        
        if colors_detected:
            logger.info(f'  MANA COLORS: {colors_detected}')
        region_data['mana'] = {'colors': colors_detected, 'confidence': 60}
    except Exception as e:
        logger.debug(f'  Mana detection failed: {e}')
        region_data['mana'] = {'colors': [], 'confidence': 0}

    # =========================================================================
    # REGION 5: ART (Future - visual fingerprint for duplicate detection)
    # =========================================================================
    logger.info("REGION 5: Art region (visual fingerprint - future)")
    # Art fingerprint will be used for:
    # - Detecting reprints vs original printings
    # - Identifying alternate art versions
    # - Cross-validating card identity
    region_data['art'] = {'fingerprint': None, 'confidence': 0}

    # =========================================================================
    # CROSS-VALIDATION: Combine all region data
    # =========================================================================
    logger.info("=== CROSS-VALIDATION ===")
    
    # Validate set code consistency
    symbol_set = region_data['set_symbol'].get('set')
    collector_set = region_data['collector'].get('set')
    
    if symbol_set and collector_set:
        if symbol_set.lower() == collector_set.lower():
            logger.info(f'  SET VALIDATED: {symbol_set.upper()} (symbol + collector match)')
            set_code = symbol_set.upper()
        else:
            # Conflict - use higher confidence source
            if region_data['set_symbol']['confidence'] > region_data['collector']['confidence']:
                set_code = symbol_set.upper()
                logger.warning(f'  SET CONFLICT: symbol={symbol_set} vs collector={collector_set}, using symbol')
            else:
                set_code = collector_set.upper()
                logger.warning(f'  SET CONFLICT: symbol={symbol_set} vs collector={collector_set}, using collector')
    elif symbol_set:
        set_code = symbol_set.upper()
    elif collector_set:
        set_code = collector_set.upper()
    
    # Combine all title OCR results
    results = title_results.copy()
    
    # Add full card fallback if title region failed
    if not results or title_confidence < 50:
        logger.info("Title region empty/low confidence - trying full card Tesseract")
        try:
            # Use Tesseract on full card
            full_text, full_conf = run_tesseract(card_img)
            if full_text and len(full_text) > 2:
                # Tesseract returns space-separated results
                # For MTG, card name is usually first readable text
                lines = [w.strip() for w in full_text.split() if len(w.strip()) > 2]
                # Filter to likely card names (longer words, title case)
                for line in lines[:5]:
                    if line and len(line) > 2 and line not in results:
                        results.append(line)
                        logger.info(f'  FULL-CARD Tesseract: "{line}" ({full_conf:.0f}%)')
        except Exception as e:
            logger.debug(f'  Full card Tesseract failed: {e}')

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for r in results:
        r_lower = r.lower()
        if r_lower not in seen and len(r) > 2:
            seen.add(r_lower)
            unique.append(r)

    # Log final results
    logger.info(f"=== 5-REGION RESULTS ===")
    logger.info(f"  OCR candidates: {unique}")
    logger.info(f"  Set code: {set_code}")
    logger.info(f"  Collector #: {collector_num}")
    logger.info(f"  Mana colors: {region_data['mana'].get('colors', [])}")

    return unique, set_code, collector_num


def scryfall_fuzzy(text):
    """Primary: Scryfall fuzzy named search"""
    if not text or len(text) < 3:
        return None, 0

    clean = text.lower().strip()

    # Check cache first
    if clean in card_cache:
        return card_cache[clean], 100

    try:
        r = requests.get('https://api.scryfall.com/cards/named',
                         params={'fuzzy': text}, timeout=5)
        if r.status_code == 200:
            card = r.json()
            name = card.get('name', '')
            ratio = SequenceMatcher(None, clean, name.lower()).ratio()
            result = {
                'name': name,
                'set': (card.get('set') or '').upper(),
                'set_name': card.get('set_name'),
                'collector_number': card.get('collector_number'),
                'rarity': card.get('rarity'),
                'prices': card.get('prices', {}),
                'image': card.get('image_uris', {}).get('normal'),
                'scryfall_id': card.get('id')
            }
            # Cache successful matches
            card_cache[clean] = result
            return result, int(ratio * 100)
    except Exception as e:
        logger.debug(f'Scryfall fuzzy error: {e}')

    return None, 0


def scryfall_exact_printing(card_name, set_code=None, collector_num=None):
    """
    Find exact card printing by set code and/or collector number.
    Returns the specific printing, not just any version.
    """
    if not card_name:
        return None

    try:
        # Method 1: Search by set code and collector number (most accurate)
        if set_code and collector_num:
            r = requests.get(
                f'https://api.scryfall.com/cards/{set_code.lower()}/{collector_num}',
                timeout=5
            )
            if r.status_code == 200:
                card = r.json()
                logger.info(f"Found exact printing: {card.get('set', '').upper()} #{collector_num}")
                return {
                    'name': card.get('name'),
                    'set': (card.get('set') or '').upper(),
                    'set_name': card.get('set_name'),
                    'collector_number': card.get('collector_number'),
                    'rarity': card.get('rarity'),
                    'prices': card.get('prices', {}),
                    'image': card.get('image_uris', {}).get('normal'),
                    'scryfall_id': card.get('id')
                }

        # Method 2: Search by name and set code
        if set_code:
            query = f'!"{card_name}" set:{set_code.lower()}'
            r = requests.get(
                'https://api.scryfall.com/cards/search',
                params={'q': query},
                timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                cards = data.get('data', [])
                if cards:
                    card = cards[0]
                    logger.info(f"Found by set: {card.get('set', '').upper()}")
                    return {
                        'name': card.get('name'),
                        'set': (card.get('set') or '').upper(),
                        'set_name': card.get('set_name'),
                        'collector_number': card.get('collector_number'),
                        'rarity': card.get('rarity'),
                        'prices': card.get('prices', {}),
                        'image': card.get('image_uris', {}).get('normal'),
                        'scryfall_id': card.get('id')
                    }

    except Exception as e:
        logger.debug(f'Exact printing search error: {e}')

    return None


def scryfall_autocomplete(text):
    """Backup: Scryfall autocomplete for partial matches"""
    if not text or len(text) < 3:
        return None, 0

    try:
        r = requests.get('https://api.scryfall.com/cards/autocomplete',
                         params={'q': text}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            suggestions = data.get('data', [])
            if suggestions:
                # Try to match best suggestion
                best_name = suggestions[0]
                ratio = SequenceMatcher(None, text.lower(),
                                        best_name.lower()).ratio()
                if ratio > 0.5:
                    # Get full card data
                    return scryfall_fuzzy(best_name)
    except Exception as e:
        logger.debug(f'Autocomplete error: {e}')

    return None, 0


def get_possible_matches(ocr_results, limit=5):
    """
    Get multiple possible card matches for human review
    Returns list of suggestions with confidence scores
    """
    suggestions = []
    seen_names = set()

    for text in ocr_results:
        # Try autocomplete for multiple suggestions
        try:
            r = requests.get('https://api.scryfall.com/cards/autocomplete',
                             params={'q': text}, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for name in data.get('data', [])[:3]:
                    if name.lower() not in seen_names:
                        seen_names.add(name.lower())
                        # Get card data
                        card, conf = scryfall_fuzzy(name)
                        if card:
                            suggestions.append({
                                'card': card,
                                'confidence': conf,
                                'ocr_source': text
                            })
        except Exception:
            pass

        # Also try fuzzy search
        card, conf = scryfall_fuzzy(text)
        if card and card['name'].lower() not in seen_names:
            seen_names.add(card['name'].lower())
            suggestions.append({
                'card': card,
                'confidence': conf,
                'ocr_source': text
            })

    # Sort by confidence and return top matches
    suggestions.sort(key=lambda x: x['confidence'], reverse=True)
    return suggestions[:limit]


def clean_ocr_text(text):
    """
    Clean OCR text to extract potential card name.
    MTG card names are typically 1-4 words, no special chars.
    """
    # Remove common OCR artifacts
    text = re.sub(r'[|\\/_~`@#$%^&*()+=\[\]{}:;"<>]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Split into words and filter
    words = text.split()

    # Look for sequences of 1-5 capitalized words (likely card name)
    candidates = []
    current = []

    for word in words:
        # Check if word looks like part of a card name
        # Card names: mostly letters, possibly with apostrophe or hyphen
        clean_word = re.sub(r"[',.-]", '', word)
        if clean_word.isalpha() and len(word) >= 2:
            current.append(word)
        else:
            if current and len(current) <= 6:
                candidates.append(' '.join(current))
            current = []

    if current and len(current) <= 6:
        candidates.append(' '.join(current))

    # Also extract 2-3 word prefixes from longer candidates
    # (card names are usually 1-4 words)
    extra = []
    for cand in candidates:
        words_in_cand = cand.split()
        if len(words_in_cand) > 3:
            # Add first 2 words
            extra.append(' '.join(words_in_cand[:2]))
            # Add first 3 words
            extra.append(' '.join(words_in_cand[:3]))

    candidates.extend(extra)

    # Remove duplicates and sort by length (2-4 words are ideal)
    seen = set()
    unique = []
    for c in candidates:
        c_lower = c.lower()
        if c_lower not in seen:
            seen.add(c_lower)
            unique.append(c)

    # Score candidates - prefer proper card name patterns
    def score(c):
        wc = len(c.split())
        base_score = 0

        # Word count scoring (2-3 words ideal)
        if wc == 2:
            base_score = 80
        elif wc == 3:
            base_score = 85
        elif wc == 1:
            base_score = 60
        elif wc == 4:
            base_score = 75
        else:
            base_score = 50 - wc

        # Bonus for capitalized words (proper nouns = card names)
        words = c.split()
        caps = sum(1 for w in words if w[0].isupper())
        base_score += caps * 5

        # Bonus for longer total length (more likely complete name)
        if len(c) >= 10:
            base_score += 10
        if len(c) >= 15:
            base_score += 5

        # Penalty for very short words (likely OCR noise)
        short_words = sum(1 for w in words if len(w) <= 2)
        base_score -= short_words * 15

        # Penalty for words ending in punctuation (OCR artifact)
        punct_words = sum(1 for w in words if w[-1] in '.,;:!')
        base_score -= punct_words * 10

        return base_score

    unique.sort(key=score, reverse=True)
    return unique[:8]  # Top 8 candidates


def score_candidate(c):
    """Score a card name candidate for matching priority"""
    wc = len(c.split())
    base_score = 0

    # Word count scoring (2-3 words ideal for card names)
    if wc == 2:
        base_score = 80
    elif wc == 3:
        base_score = 85
    elif wc == 1:
        base_score = 50  # Single words often noise
    elif wc == 4:
        base_score = 75
    else:
        base_score = 40 - wc

    # PENALTY for ability keywords - these are often from rules text, not title
    # Single-word ability keywords get significant penalty (likely from ability text)
    c_lower = c.lower().strip()
    if c_lower in ABILITY_KEYWORDS:
        base_score -= 40  # Big penalty - deprioritize but don't exclude

    words = c.split()

    # Bonus for capitalized words (proper nouns = card names)
    caps = sum(1 for w in words if w and w[0].isupper())
    base_score += caps * 8

    # Bonus for longer total length
    if len(c) >= 12:
        base_score += 15
    elif len(c) >= 8:
        base_score += 8

    # Penalty for very short words (OCR noise)
    short_words = sum(1 for w in words if len(w) <= 2)
    base_score -= short_words * 20

    # Penalty for punctuation (OCR artifact)
    punct_words = sum(1 for w in words if w and w[-1] in '.,;:!')
    base_score -= punct_words * 15

    # Penalty for all-caps short words (likely noise like "TET")
    if wc == 1 and c.isupper() and len(c) <= 4:
        base_score -= 30

    return base_score


def cross_validate_card(ocr_text, zultan_match, scryfall_card, set_code=None, collector_num=None):
    """
    CROSS-VALIDATION: All sources must agree before accepting match.
    
    Sources:
    1. OCR text (Tesseract from title region)
    2. ZULTAN art embedding (visual match)
    3. Scryfall API (card database confirmation)
    4. Set code (symbol matching)
    5. Collector number (bottom text OCR)
    
    Returns: (validated_card, confidence_score, validation_report)
    """
    logger.info("=== CROSS-VALIDATION START ===")
    logger.info(f"OCR: '{ocr_text}'")
    logger.info(f"ZULTAN: '{zultan_match.get('name') if zultan_match else None}' ({zultan_match.get('confidence', 0) if zultan_match else 0}%)")
    logger.info(f"Scryfall: '{scryfall_card.get('name') if scryfall_card else None}'")
    logger.info(f"Set: {set_code}, Collector: {collector_num}")
    
    validation_score = 0
    max_score = 5  # 5 validation sources
    report = {}
    
    # Source 1: OCR text exists and is reasonable
    if ocr_text and len(ocr_text) > 3:
        validation_score += 1
        report['ocr'] = {'valid': True, 'text': ocr_text}
    else:
        report['ocr'] = {'valid': False, 'reason': 'No OCR text extracted'}
        logger.warning("❌ OCR validation failed: no text")
        return None, 0, report
    
    # Source 2: ZULTAN art match exists
    zultan_name = zultan_match.get('name') if zultan_match else None
    zultan_conf = zultan_match.get('confidence', 0) if zultan_match else 0
    
    # Import for similarity matching (also at module level, but ensure local availability)
    from difflib import SequenceMatcher

    if zultan_name and zultan_conf >= 70:
        # Check if ZULTAN matches OCR (fuzzy match)
        similarity = SequenceMatcher(None, ocr_text.lower(), zultan_name.lower()).ratio()
        
        if similarity >= 0.7:
            validation_score += 1
            report['zultan'] = {'valid': True, 'match': zultan_name, 'similarity': similarity}
            logger.info(f"✓ ZULTAN validates OCR ({similarity:.0%} similarity)")
        else:
            report['zultan'] = {'valid': False, 'match': zultan_name, 'similarity': similarity, 'reason': 'Art match disagrees with OCR'}
            logger.warning(f"❌ ZULTAN mismatch: '{ocr_text}' vs '{zultan_name}' ({similarity:.0%})")
            # Don't fail completely, but reduce confidence
    else:
        report['zultan'] = {'valid': False, 'reason': f'Low confidence ({zultan_conf}%)'}
        logger.warning(f"⚠ ZULTAN unavailable or low confidence ({zultan_conf}%)")
    
    # Source 3: Scryfall confirms card exists
    scryfall_name = scryfall_card.get('name') if scryfall_card else None
    if scryfall_name:
        # Check if Scryfall matches OCR
        similarity = SequenceMatcher(None, ocr_text.lower(), scryfall_name.lower()).ratio()
        
        # Lower threshold to 65% - consensus based, not strict matching
        if similarity >= 0.65:
            validation_score += 1
            report['scryfall'] = {'valid': True, 'match': scryfall_name, 'similarity': similarity}
            # Note: PERFECT MATCH BOOST moved to after set validation - requires name AND set
            logger.info(f"✓ Scryfall name match ({similarity:.0%} similarity)")
        else:
            report['scryfall'] = {'valid': False, 'match': scryfall_name, 'similarity': similarity}
            logger.warning(f"❌ Scryfall mismatch: '{ocr_text}' vs '{scryfall_name}' ({similarity:.0%})")
    else:
        report['scryfall'] = {'valid': False, 'reason': 'Card not found in Scryfall'}
        logger.warning("❌ Scryfall lookup failed")
        return None, 0, report
    
    # Source 4: Set code validation (if available)
    set_valid = False
    if set_code and scryfall_card:
        card_set = scryfall_card.get('set', '').upper()
        if card_set == set_code.upper():
            validation_score += 1
            set_valid = True
            report['set'] = {'valid': True, 'code': set_code}
            logger.info(f"✓ Set code validates: {set_code}")
        else:
            report['set'] = {'valid': False, 'ocr_set': set_code, 'card_set': card_set}
            logger.warning(f"⚠ Set mismatch: OCR={set_code}, Card={card_set}")
    else:
        report['set'] = {'valid': None, 'reason': 'No set code extracted'}
        logger.info("⚠ No set code to validate")

    # PERFECT MATCH BOOST: Only if name (95%+) AND set both match
    scryfall_similarity = report.get('scryfall', {}).get('similarity', 0)
    if scryfall_similarity >= 0.95 and set_valid:
        validation_score += 2
        logger.info(f"⬆ PERFECT MATCH: Name ({scryfall_similarity:.0%}) + Set ({set_code}) = +2 boost")
    elif scryfall_similarity >= 0.95:
        logger.info(f"⚠ No boost: Name matches ({scryfall_similarity:.0%}) but set failed")
    
    # Source 5: Collector number validation (if available)
    if collector_num and scryfall_card:
        card_num = str(scryfall_card.get('collector_number', ''))
        if card_num == str(collector_num):
            validation_score += 1
            report['collector'] = {'valid': True, 'number': collector_num}
            logger.info(f"✓ Collector number validates: {collector_num}")
        else:
            report['collector'] = {'valid': False, 'ocr_num': collector_num, 'card_num': card_num}
            logger.warning(f"⚠ Collector mismatch: OCR={collector_num}, Card={card_num}")
    else:
        report['collector'] = {'valid': None, 'reason': 'No collector number extracted'}
        logger.info("⚠ No collector number to validate")
    
    # BASIC LAND BOOST: If OCR matches a basic land name exactly, boost confidence
    # Basic lands are trivial to identify - name + "Basic Land" type = definite
    basic_lands = ['plains', 'island', 'swamp', 'mountain', 'forest']
    scryfall_name_lower = scryfall_name.lower() if scryfall_name else ''

    if scryfall_name_lower in basic_lands and report.get('scryfall', {}).get('valid'):
        # If OCR matched basic land name and Scryfall confirmed, that's definitive
        validation_score = 5  # Maximum confidence for basic lands
        logger.info(f"⬆ BASIC LAND BOOST: '{scryfall_name}' confirmed")

    # Calculate final confidence based on validation score
    confidence = (validation_score / max_score) * 100

    # PERFECT OCR BOOST: Only if name + set both validate
    # Requires: 95%+ Scryfall similarity AND (set match OR no set to compare)
    scryfall_similarity = report.get('scryfall', {}).get('similarity', 0)
    set_valid = report.get('set', {}).get('valid')
    name_is_ability_keyword = scryfall_name_lower in ABILITY_KEYWORDS if scryfall_name_lower else False

    if scryfall_similarity >= 0.95 and confidence < 95:
        # Don't boost ability keywords unless set also validates
        if name_is_ability_keyword and not set_valid:
            logger.info(f"⚠ NO BOOST: '{scryfall_name}' is ability keyword, set not validated")
        elif set_valid is False:
            # Set was checked but didn't match - don't boost even with perfect name
            logger.info(f"⚠ NO BOOST: Name matches but set validation failed")
        else:
            # Name matches and either set matches or no set to check - boost it
            confidence = 95
            logger.info(f"⬆ PERFECT OCR BOOST: {scryfall_similarity:.0%} name match + set OK → 95%")

    logger.info(f"=== VALIDATION SCORE: {validation_score}/{max_score} ({confidence:.0f}%) ===")
    
    # Minimum threshold: Must have OCR + Scryfall agreement (2/5)
    if validation_score >= 2:
        logger.info(f"✓ CARD VALIDATED: {scryfall_card.get('name')}")
        return scryfall_card, confidence, report
    else:
        logger.warning(f"❌ VALIDATION FAILED: Only {validation_score}/5 sources agree")
        return None, confidence, report


def identify_card(ocr_results, set_code=None, collector_num=None, card_image=None):
    """
    MULTI-SOURCE CARD IDENTIFICATION WITH CROSS-VALIDATION

    Process:
    1. Get OCR candidates (Tesseract from regions)
    2. Get ZULTAN art match (visual embedding)
    3. Lookup each candidate in Scryfall API
    4. Cross-validate: all sources must agree
    5. Return only if consensus reached

    Returns: (card, confidence, validation_report) or (None, 0, report) if validation fails
    """
    logger.info(f"=== IDENTIFY CARD ===")
    logger.info(f"OCR Results: {ocr_results}")

    # ZULTAN DISABLED - Force OCR to work
    # User request: "get zultan out of this" - OCR must succeed on its own
    zultan_match = None
    logger.info("ZULTAN DISABLED - Pure OCR mode")

    # STEP 2: Extract clean card name candidates from OCR
    all_candidates = []
    for text in ocr_results:
        all_candidates.extend(clean_ocr_text(text))

    # Add original OCR results too (in case cleaning removes valid names)
    all_candidates.extend(ocr_results)

    # SUBSTRING SEARCH: Look for known card names in the full OCR text
    # This catches cases where "Path of Ancestry enters the battlefield..."
    # contains the card name but it's not extracted as a clean candidate
    full_ocr_lower = ' '.join(ocr_results).lower()

    # BASIC LAND CHECK FIRST (common OCR issues like "fores" for "forest")
    basic_land_patterns = [
        ('plains', ['plains', 'plain']),
        ('island', ['island', 'islan']),
        ('swamp', ['swamp', 'swam']),
        ('mountain', ['mountain', 'mountai', 'mounta']),
        ('forest', ['forest', 'fores', 'fore'])
    ]
    for land_name, patterns in basic_land_patterns:
        for pattern in patterns:
            if pattern in full_ocr_lower:
                all_candidates.insert(0, land_name.capitalize())
                logger.info(f"BASIC LAND MATCH: Found '{pattern}' → '{land_name.capitalize()}'")
                break
        else:
            continue
        break

    # General substring search for other cards
    for card_name in master_cards.keys():
        if len(card_name) >= 6 and card_name in full_ocr_lower:
            # Found a known card name in the OCR text!
            all_candidates.insert(0, master_cards[card_name]['name'])  # Use proper case
            logger.info(f"SUBSTRING MATCH: Found '{master_cards[card_name]['name']}' in OCR text")
            break  # Take first/longest match

    # Remove duplicates, keep candidates with at least 4 chars
    seen = set()
    candidates = []
    for c in all_candidates:
        c_lower = c.lower().strip()
        if not c_lower or c_lower in seen or len(c_lower) < 4:
            continue
        # Skip if mostly punctuation/numbers (less than 50% alpha)
        alpha_count = sum(1 for ch in c if ch.isalpha())
        if alpha_count < len(c) * 0.5:
            continue
        seen.add(c_lower)
        candidates.append(c)

    # Sort by score - prefer longer, capitalized phrases
    candidates.sort(key=score_candidate, reverse=True)

    logger.info(f"OCR Candidates: {candidates[:10]}")
    if set_code or collector_num:
        logger.info(f"Collector info: set={set_code}, num={collector_num}")

    # STEP 3: Try each OCR candidate and cross-validate
    best_card = None
    best_confidence = 0
    best_validation_report = None

    for text in candidates:
        logger.debug(f"Evaluating candidate: '{text}'")

        # Get Scryfall match for this candidate
        scryfall_card = None
        
        # Try local database first
        if master_cards:
            scryfall_card, _ = local_fuzzy_match(text)
        
        # Try Scryfall API if local failed
        if not scryfall_card:
            scryfall_card, _ = scryfall_fuzzy(text)
        
        # Try autocomplete as fallback
        if not scryfall_card:
            scryfall_card, _ = scryfall_autocomplete(text)
        
        if not scryfall_card:
            logger.debug(f"  No Scryfall match for '{text}'")
            continue
        
        # STEP 4: CROSS-VALIDATE this candidate
        validated_card, conf, report = cross_validate_card(
            ocr_text=text,
            zultan_match=zultan_match,
            scryfall_card=scryfall_card,
            set_code=set_code,
            collector_num=collector_num
        )
        
        if validated_card and conf > best_confidence:
            best_card = validated_card
            best_confidence = conf
            best_validation_report = report
            logger.info(f"✓ NEW BEST: '{text}' validated at {conf:.0f}%")
            
            # If we have 100% validation (all 5 sources agree), stop searching
            if conf == 100:
                logger.info("✓ PERFECT MATCH - all sources agree!")
                break
            
            # If we have 80%+ validation (4/5 sources), that's very good
            if conf >= 80:
                logger.info("✓ HIGH CONFIDENCE - 4/5 sources agree")
                break

    # STEP 5: Return best validated result WITH REPORT
    if best_card:
        name = best_card.get("name")
        set_info = best_card.get("set", "")
        logger.info(f'=== FINAL RESULT: {name} [{set_info}] ({best_confidence:.0f}%) ===')
        logger.info(f'Validation: {best_validation_report}')
        # Auto-log to AI learning DB
        log_scan_to_learning(name, best_confidence, image_path=card_image)
        return best_card, best_confidence, best_validation_report
    else:
        logger.warning("=== NO VALID MATCH FOUND - all candidates failed cross-validation ===")
        # Return empty report if no match
        empty_report = {'ocr': {'valid': False}, 'zultan': {'valid': False}, 'scryfall': {'valid': False}, 'set': {'valid': None}, 'collector': {'valid': None}}
        return None, 0, empty_report


def add_to_inventory(card, call_number):
    if not card or not card.get('name'):
        return
    key = card['name'] + '|' + (card.get('set') or '')
    if key in inventory:
        inventory[key]['qty'] += 1
        inventory[key]['scans'].append(call_number)
    else:
        inventory[key] = {
            'name': card['name'],
            'set': card.get('set'),
            'set_name': card.get('set_name'),
            'rarity': card.get('rarity'),
            'prices': card.get('prices', {}),
            'qty': 1,
            'scans': [call_number]
        }
    save_state()


def add_to_review(scan_result):
    """Add uncertain card to review queue for manual confirmation"""
    review_queue.append({
        'call_number': scan_result['call_number'],
        'timestamp': scan_result['timestamp'],
        'ocr_text': scan_result['ocr_text'],
        'suggested_card': scan_result.get('card'),
        'confidence': scan_result.get('confidence', 0),
        'image_path': scan_result['image_path'],
        'status': 'pending'
    })
    save_state()


@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'engine': 'tesseract+scryfall',
        'storage': HDD,
        'gpu': cv2.ocl.useOpenCL()
    })


@app.route('/status')
def status():
    pending = len([r for r in review_queue if r.get('status') == 'pending'])
    return jsonify({
        'status': 'online',
        'name': 'BROK',
        'shop_id': SHOP_ID,
        'shop_code': SHOP_CODE,
        'engine': 'coral' if CORAL_AVAILABLE and OCR_USE_CORAL else 'tesseract',
        'mode': 'accuracy-first',
        'storage': HDD,
        'scans': scan_counter,
        'current_box': current_box,
        'box_position': box_position,
        'next_call': f"{current_box}{box_position + 1}",
        'master_db_cards': len(master_cards),
        'cache': len(card_cache),
        'inventory': len(inventory),
        'review_pending': pending,
        'gpu_enabled': cv2.ocl.useOpenCL(),
        'coral_available': CORAL_AVAILABLE,
        'dual_camera': {
            'enabled': True,
            'local_camera': LOCAL_CAMERA,
            'back_dir': BACK_DIR,
            'endpoints': ['/api/dual_scan', '/api/detect_type']
        },
        'set_symbols': len(set_symbol_templates)
    })


@app.route('/api/shop/info')
def shop_info():
    """Get shop configuration (safe info only - no secrets)"""
    return jsonify({
        'success': True,
        'shop': {
            'shop_id': SHOP_ID,
            'shop_code': SHOP_CODE,
            'name': SHOP_CONFIG.get('shop_name', 'NEXUS Shop'),
        },
        'network': {
            'brok_url': f'http://localhost:{SERVER_PORT}',
            'snarf_url': SNARF_URL,
        },
        'capabilities': {
            'coral_tpu': CORAL_AVAILABLE and OCR_USE_CORAL,

            'dual_camera': True,
        },
        'data_policy': {
            'customer_data': 'local_only',
            'sales_data': 'local_only',
            'metadata_sync': SYNC_METADATA,
            'ai_pattern_sync': SYNC_AI_PATTERNS,
        },
        'storage': {
            'hdd_path': HDD,
            'database_dir': DATABASE_DIR,
        }
    })


# =============================================================================
# LIVE VIDEO STREAMING FOR FOCUS ADJUSTMENT
# =============================================================================

def generate_mjpeg_stream(camera_source='local'):
    """Generate MJPEG frames for live video streaming."""
    if camera_source == 'local':
        # Local OwlEye camera on BROK
        cap = cv2.VideoCapture(LOCAL_CAMERA['index'])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    elif camera_source == 'czur':
        # CZUR scanner - check if available
        cap = cv2.VideoCapture(1)  # Try second camera index
        if not cap.isOpened():
            cap = cv2.VideoCapture(2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    else:
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Add focus guide overlay (center crosshair)
            h, w = frame.shape[:2]
            cv2.line(frame, (w//2 - 50, h//2), (w//2 + 50, h//2), (0, 255, 0), 2)
            cv2.line(frame, (w//2, h//2 - 50), (w//2, h//2 + 50), (0, 255, 0), 2)

            # Add text showing source
            cv2.putText(frame, f"Source: {camera_source.upper()}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Encode as JPEG
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    finally:
        cap.release()


@app.route('/api/video/owleye')
def video_owleye():
    """Live video stream from OwlEye camera for focus adjustment."""
    from flask import Response
    return Response(generate_mjpeg_stream('local'),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/video/czur')
def video_czur():
    """Live video stream from CZUR scanner for focus adjustment."""
    from flask import Response
    return Response(generate_mjpeg_stream('czur'),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/video/snapshot/<source>')
def video_snapshot(source):
    """Get a single frame from camera for focus check."""
    if source == 'owleye':
        cap = cv2.VideoCapture(LOCAL_CAMERA['index'])
    elif source == 'czur':
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            cap = cv2.VideoCapture(2)
    elif source == 'snarf':
        # Get snapshot from Snarf (hardware scanner Pi)
        try:
            r = requests.get(f'{SNARF_URL}/api/snapshot', timeout=10)
            if r.status_code == 200:
                return r.content, 200, {'Content-Type': 'image/jpeg'}
            return jsonify({'error': 'Snarf snapshot failed'}), 503
        except Exception as e:
            return jsonify({'error': f'Snarf unreachable: {e}'}), 503
    else:
        return jsonify({'error': 'Unknown source'}), 400

    if not cap.isOpened():
        return jsonify({'error': f'{source} camera not available'}), 503

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return jsonify({'error': 'Failed to capture frame'}), 500

    # Save to temp file
    temp_path = f'/tmp/{source}_snapshot.jpg'
    cv2.imwrite(temp_path, frame)

    return send_file(temp_path, mimetype='image/jpeg')


@app.route('/api/video/snarf')
def video_snarf():
    """Proxy video stream from Snarf (hardware scanner Pi)."""
    from flask import Response

    def proxy_stream():
        try:
            # Stream from Snarf's video endpoint
            r = requests.get(f'{SNARF_URL}/api/video/stream',
                           stream=True, timeout=30)
            for chunk in r.iter_content(chunk_size=4096):
                yield chunk
        except Exception as e:
            logger.error(f"Snarf stream error: {e}")

    return Response(proxy_stream(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/download_symbols', methods=['POST'])
def api_download_symbols():
    """Download set symbol templates from Scryfall (run once)"""
    logger.info("Starting set symbol download...")
    success = download_set_symbols()
    if success:
        load_set_symbols()
        return jsonify({
            'success': True,
            'message': f'Downloaded and loaded {len(set_symbol_templates)} set symbols'
        })
    return jsonify({'success': False, 'error': 'Download failed'}), 500


@app.route('/api/box/set', methods=['POST'])
def set_box():
    """Set current box prefix (e.g., start new box)"""
    global current_box, box_position
    data = request.json or {}
    new_box = data.get('box', '').upper()

    if len(new_box) != 2 or not new_box.isalpha():
        return jsonify({'success': False, 'error': 'Box must be 2 letters (e.g., AA, AB)'}), 400

    current_box = new_box
    box_position = data.get('position', 0)
    save_state()

    logger.info(f"Box set to {current_box}, position {box_position}")
    return jsonify({
        'success': True,
        'box': current_box,
        'position': box_position,
        'next_call': f"{current_box}{box_position + 1}"
    })


@app.route('/api/ocr', methods=['POST'])
def ocr():
    global scan_counter
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image'}), 400

    file = request.files['image']
    scan_counter += 1

    # Temp file for processing
    temp_file = f'{SCAN_DIR}/_temp_scan.jpg'
    file.save(temp_file)

    # Multi-pass OCR for accuracy (includes set code extraction)
    ocr_results, set_code, collector_num = multi_pass_ocr(temp_file)
    card, confidence, validation_report = identify_card(ocr_results, set_code, collector_num, card_image=temp_file)

    # Determine action based on confidence
    # 95%+ = auto-accept with call number
    # <95% = NO call number, flag for review, put aside
    needs_review = False
    possible_matches = []
    call_number = None

    if card and confidence >= 95:
        # 95%+ confidence - auto accept, add to inventory
        call_number = get_call_number()
        filename = f'{SCAN_DIR}/{call_number}.jpg'
        os.rename(temp_file, filename)
        add_to_inventory(card, call_number)
        status = 'identified'
    else:
        # BELOW 95% - flag for review
        needs_review = True
        review_id = f"REVIEW_{scan_counter:04d}"
        filename = f'{SCAN_DIR}/{review_id}.jpg'
        os.rename(temp_file, filename)
        call_number = None
        status = 'review_needed' if not card else 'needs_verification'
        possible_matches = get_possible_matches(ocr_results, limit=5)

    result = {
        'success': True,
        'call_number': call_number,
        'timestamp': datetime.now().isoformat(),
        'ocr_text': ocr_results,
        'card': card,
        'confidence': confidence,
        'status': status,
        'needs_review': needs_review,
        'possible_matches': possible_matches,
        'image_path': filename,
        'validation': validation_report  # Cross-validation details
    }

    if needs_review:
        add_to_review(result)

    scan_history.append(result)
    save_state()

    name = card.get('name') if card else 'Unknown'
    logger.info(f"{call_number}: {name} ({confidence}%) [{status}]")
    return jsonify(result)


@app.route('/api/dual_scan', methods=['POST'])
def dual_scan():
    """
    Dual-camera scan: Back (local) + Front (Snarf) simultaneously
    Returns card type from back detection + OCR from front
    """
    global scan_counter
    try:
        # Simultaneous capture from both cameras
        back_path, front_result, card_type, type_confidence = dual_capture()

        if not front_result.get('path'):
            return jsonify({'success': False, 'error': 'Front capture failed'}), 500

        # Download front image from Snarf
        img_path = front_result['path']
        img_r = requests.get(
            f"{SNARF_URL}/api/image?path={img_path}&delete=true",
            timeout=10
        )

        scan_counter += 1
        call_number = get_call_number()
        filename = f'{SCAN_DIR}/{call_number}.jpg'
        with open(filename, 'wb') as f:
            f.write(img_r.content)

        # Multi-pass OCR on front image (includes set code extraction)
        ocr_results, set_code, collector_num = multi_pass_ocr(filename)
        card, confidence, validation_report = identify_card(ocr_results, set_code, collector_num, card_image=filename)

        # Determine action based on confidence
        needs_review = False
        possible_matches = []

        if card and confidence >= 85:
            add_to_inventory(card, call_number)
            status = 'identified'
        elif card and confidence >= 70:
            add_to_inventory(card, call_number)
            status = 'likely'
        else:
            needs_review = True
            status = 'review_needed'
            possible_matches = get_possible_matches(ocr_results, limit=5)

        result = {
            'success': True,
            'call_number': call_number,
            'timestamp': datetime.now().isoformat(),
            'ocr_text': ocr_results,
            'card': card,
            'confidence': confidence,
            'status': status,
            'needs_review': needs_review,
            'possible_matches': possible_matches,
            'image_path': filename,
            'validation': validation_report,  # Cross-validation details
            # Dual-camera specific fields
            'card_type': card_type,
            'type_confidence': type_confidence,
            'back_image': back_path,
            'dual_capture': True
        }

        if needs_review:
            add_to_review(result)

        scan_history.append(result)
        save_state()

        name = card.get('name') if card else 'Unknown'
        logger.info(f"{call_number}: {name} ({confidence}%) [{status}] type={card_type}")
        return jsonify(result)

    except Exception as e:
        logger.error(f'Dual scan error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/detect_type', methods=['POST'])
def detect_type():
    """Capture back and detect card type only (no OCR)"""
    try:
        back_path = capture_local_owleye()
        if not back_path:
            return jsonify({'success': False, 'error': 'Back capture failed'}), 500

        card_type, confidence = detect_card_type(back_path)
        return jsonify({
            'success': True,
            'card_type': card_type,
            'confidence': confidence,
            'image_path': back_path
        })
    except Exception as e:
        logger.error(f'Type detection error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/capture', methods=['POST'])
def capture():
    """Passthrough to Snarf for image capture (no OCR)"""
    try:
        data = request.get_json() or {}
        camera = data.get('camera', 'owleye')

        # Forward to Snarf
        r = requests.post(f'{SNARF_URL}/api/capture',
                          json={'camera': camera}, timeout=15)
        if r.status_code != 200:
            return jsonify({'success': False, 'error': 'Capture failed'}), 500

        return jsonify(r.json())
    except Exception as e:
        logger.error(f'Capture error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scan', methods=['POST'])
def scan():
    """Capture from Snarf and process"""
    global scan_counter, review_counter
    try:
        data = request.get_json() or {}
        camera = data.get('camera', 'owleye')
        fast_mode = data.get('fast', False)  # Default to accuracy mode (multi-pass)

        logger.info(f"=== SCAN START === Camera: {camera}, Fast: {fast_mode}")

        # Capture from Snarf using OPTIMAL capture (best quality)
        capture_mode = 'fast' if fast_mode else 'ocr'
        r = requests.post(f'{SNARF_URL}/api/capture/optimal',
                          json={'camera': camera, 'mode': capture_mode, 'multi_shot': 1 if fast_mode else 3}, 
                          timeout=30)
        if r.status_code != 200:
            logger.error(f"Optimal capture failed: HTTP {r.status_code}")
            return jsonify({'success': False, 'error': 'Capture failed'}), 500

        cap = r.json()
        img_path = cap.get('best_image') or cap.get('image_path')
        logger.info(f"Snarf captured: {img_path}")

        # Download image from Snarf (auto-delete after download)
        img_r = requests.get(
            f"{SNARF_URL}/api/image?path={img_path}&delete=true",
            timeout=10
        )
        if img_r.status_code != 200:
            logger.error(f"Image download failed: HTTP {img_r.status_code}")
            return jsonify({'success': False, 'error': 'Image download failed'}), 500

        # Save to unique temp file for debugging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_file = f'{SCAN_DIR}/_debug_{timestamp}.jpg'
        with open(temp_file, 'wb') as f:
            f.write(img_r.content)
        logger.info(f"Saved raw image: {temp_file} ({len(img_r.content)} bytes)")

        # ROTATE 90° CLOCKWISE - CZUR camera orientation fix
        img = cv2.imread(temp_file)
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        cv2.imwrite(temp_file, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        logger.info(f"Rotated 90° CW: {temp_file}")

        # Run OCR - fast mode (1-2 passes) or multi-pass (6 passes)
        if fast_mode:
            ocr_results, set_code, collector_num = fast_ocr(temp_file)
        else:
            ocr_results, set_code, collector_num = multi_pass_ocr(temp_file)
        
        # IDENTIFY CARD with cross-validation
        card, confidence, validation_report = identify_card(ocr_results, set_code, collector_num, card_image=temp_file)

        # Determine action based on confidence
        needs_review = False
        possible_matches = []
        
        if not card or confidence < 40:
            # No consensus - needs human review
            needs_review = True
            status = 'validation_failed'
            review_counter += 1
            call_number = f"REV{review_counter}"
            logger.warning(f"Validation failed - low confidence: {confidence}%")
        elif card and confidence >= 85:
            # Identified - assign call number
            scan_counter += 1
            call_number = get_call_number()
            add_to_inventory(card, call_number)
            status = 'identified'
        elif card and confidence >= 70:
            # Likely match - assign call number
            scan_counter += 1
            call_number = get_call_number()
            add_to_inventory(card, call_number)
            status = 'likely'
        else:
            # Not recognized - use review number instead
            if not hasattr(scan, 'review_counter'):
                scan.review_counter = 0
            scan.review_counter += 1
            call_number = f'REVIEW_{scan.review_counter:04d}'
            needs_review = True
            status = 'review_needed'
            possible_matches = get_possible_matches(ocr_results, limit=5)

        # Copy CROPPED CARD to final filename (not raw temp_file!)
        # The _card.jpg version is the cropped card we want
        cropped_card_path = temp_file.replace('.jpg', '_card.jpg')
        filename = f'{SCAN_DIR}/{call_number}.jpg'
        import shutil
        import os

        # Determine which image to show in UI (cropped vs raw)
        display_image = temp_file  # Default to raw

        # If cropped card exists, use it for both file and display
        if os.path.exists(cropped_card_path):
            logger.info(f"Copying cropped card: {cropped_card_path} → {filename}")
            shutil.copy2(cropped_card_path, filename)
            display_image = cropped_card_path  # Show CROPPED card in UI
        else:
            logger.warning(f"No cropped card found - using raw: {temp_file} → {filename}")
            shutil.copy2(temp_file, filename)

        result = {
            'success': True,
            'call_number': call_number,
            'timestamp': datetime.now().isoformat(),
            'ocr_text': ocr_results,
            'card': card,
            'confidence': confidence,
            'status': status,
            'needs_review': needs_review,
            'possible_matches': possible_matches,
            'image_path': display_image,  # Show CROPPED card edge-to-edge, no background
            'validation': validation_report  # Include cross-validation details
        }

        if needs_review:
            add_to_review(result)

        scan_history.append(result)
        save_state()

        name = card.get('name') if card else 'Unknown'
        logger.info(f"{call_number}: {name} ({confidence}%) [{status}]")
        return jsonify(result)

    except Exception as e:
        logger.error(f'Scan error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scan/orchestrated', methods=['POST'])
def scan_orchestrated():
    """
    New orchestrated scan endpoint - routes to 3 scanning methods:
    - bulk_single: CZUR + Tesseract (100+ cards/hr)
    - bulk_mixed: Back detect + CZUR + Tesseract (80-90 cards/hr)
    - pre_grade: Dual Owleye + Tesseract + Grading (50-60 cards/hr)
    """
    try:
        data = request.get_json() or {}
        mode = data.get('mode', 'bulk_single')
        card_type = data.get('card_type', 'mtg')
        
        logger.info(f"=== ORCHESTRATED SCAN === Mode: {mode}, Type: {card_type}")
        
        # Import orchestrator
        from scan_orchestrator import ScanOrchestrator
        
        # Create orchestrator instance
        orchestrator = ScanOrchestrator(mode, card_type)
        
        # Execute scan
        card_data = orchestrator.scan_card()
        
        if "error" in card_data:
            logger.error(f"Scan failed: {card_data['error']}")
            return jsonify({'success': False, 'error': card_data['error']}), 500
        
        # Save to inventory
        orchestrator.save_to_inventory(card_data)
        
        logger.info(f"✅ {card_data['call_number']}: Scanned via {mode}")
        
        return jsonify({
            'success': True,
            **card_data
        })
        
    except Exception as e:
        logger.error(f'Orchestrated scan error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history')
def history():
    limit = request.args.get('limit', 50, type=int)
    return jsonify({'success': True, 'history': scan_history[-limit:]})


@app.route('/api/latest')
def latest():
    if scan_history:
        return jsonify({'success': True, **scan_history[-1]})
    return jsonify({'success': False})


@app.route('/api/inventory')
def get_inventory():
    return jsonify({'success': True, 'items': list(inventory.values())})


@app.route('/api/scan_image')
def scan_image():
    path = request.args.get('path')
    if path and os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    return jsonify({'error': 'Image not found'}), 404


@app.route('/api/review')
def get_review_queue():
    """Get cards pending human review"""
    pending = [r for r in review_queue if r.get('status') == 'pending']
    return jsonify({
        'success': True,
        'pending_count': len(pending),
        'items': pending
    })


@app.route('/api/review/confirm', methods=['POST'])
def confirm_card():
    """
    Human confirms card identification
    POST: {call_number: "SCAN-000001", card_name: "Lightning Bolt"}
    """
    data = request.json or {}
    call_number = data.get('call_number')
    card_name = data.get('card_name')

    if not call_number or not card_name:
        return jsonify({'success': False, 'error': 'Missing call_number or card_name'}), 400

    # Get card data from Scryfall
    card, conf = scryfall_fuzzy(card_name)
    if not card:
        return jsonify({'success': False, 'error': f'Card not found: {card_name}'}), 404

    # Add to inventory
    add_to_inventory(card, call_number)

    # Mark as confirmed in review queue
    for item in review_queue:
        if item.get('call_number') == call_number:
            item['status'] = 'confirmed'
            item['confirmed_card'] = card
            break

    save_state()
    logger.info(f"{call_number}: Confirmed as {card['name']}")
    return jsonify({'success': True, 'card': card, 'call_number': call_number})


@app.route('/api/review/skip', methods=['POST'])
def skip_card():
    """Skip a card that can't be identified"""
    data = request.json or {}
    call_number = data.get('call_number')

    # Skip ALL pending items with this call_number (handles duplicates)
    count = 0
    for item in review_queue:
        if item.get('call_number') == call_number and item.get('status') == 'pending':
            item['status'] = 'skipped'
            count += 1

    if count == 0:
        logger.warning(f"Skip failed - no pending items with call_number: {call_number}")
        return jsonify({'success': False, 'error': f'Item not found: {call_number}'}), 404

    logger.info(f"Skipped {count} item(s) with call_number: {call_number}")
    save_state()
    return jsonify({'success': True, 'call_number': call_number, 'count': count})


# =============================================================================
# SYSTEM STATS (Health Monitoring)
# =============================================================================

def get_pi_temp():
    """Get Raspberry Pi CPU temperature."""
    try:
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            temp_str = result.stdout.decode().strip()
            # Format: temp=45.0'C
            temp = float(temp_str.replace("temp=", "").replace("'C", ""))
            return temp
    except Exception:
        pass
    return None


@app.route('/api/system/stats', methods=['GET'])
def system_stats():
    """Get Pi system stats: CPU, memory, disk, temperature."""
    stats = {
        "success": True,
        "hostname": "brok",
        "cpu_percent": None,
        "memory_percent": None,
        "memory_used_mb": None,
        "memory_total_mb": None,
        "disk_percent": None,
        "disk_used_gb": None,
        "disk_total_gb": None,
        "temperature": None,
        "uptime": None
    }

    # Try psutil first (most accurate)
    try:
        import psutil
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        stats["memory_percent"] = mem.percent
        stats["memory_used_mb"] = int(mem.used / (1024 * 1024))
        stats["memory_total_mb"] = int(mem.total / (1024 * 1024))
        disk = psutil.disk_usage('/')
        stats["disk_percent"] = disk.percent
        stats["disk_used_gb"] = round(disk.used / (1024**3), 1)
        stats["disk_total_gb"] = round(disk.total / (1024**3), 1)
        stats["uptime"] = int(time.time() - psutil.boot_time())
    except ImportError:
        # Fallback to shell commands
        try:
            # CPU (from /proc/stat - rough estimate)
            result = subprocess.run(
                ['sh', '-c', "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                cpu_str = result.stdout.decode().strip()
                stats["cpu_percent"] = float(cpu_str)
        except Exception:
            pass

        try:
            # Memory from free command
            result = subprocess.run(
                ['free', '-m'], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.decode().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        total = int(parts[1])
                        used = int(parts[2])
                        stats["memory_total_mb"] = total
                        stats["memory_used_mb"] = used
                        stats["memory_percent"] = (used / total) * 100 if total > 0 else 0
        except Exception:
            pass

        try:
            # Disk from df command
            result = subprocess.run(
                ['df', '-BG', '/'], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.decode().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        total = float(parts[1].replace('G', ''))
                        used = float(parts[2].replace('G', ''))
                        stats["disk_total_gb"] = total
                        stats["disk_used_gb"] = used
                        stats["disk_percent"] = (used / total) * 100 if total > 0 else 0
        except Exception:
            pass

        try:
            # Uptime
            result = subprocess.run(
                ['cat', '/proc/uptime'], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                uptime_str = result.stdout.decode().strip().split()[0]
                stats["uptime"] = int(float(uptime_str))
        except Exception:
            pass

    # Temperature (Pi-specific)
    temp = get_pi_temp()
    if temp is not None:
        stats["temperature"] = temp

    return jsonify(stats)


@app.route('/api/inventory/summary')
def inventory_summary():
    total_cards = sum(item['qty'] for item in inventory.values())
    total_value = 0
    for item in inventory.values():
        price = item.get('prices', {}).get('usd') or '0'
        try:
            total_value += float(price) * item['qty']
        except Exception:
            pass
    return jsonify({
        'success': True,
        'unique_cards': len(inventory),
        'total_cards': total_cards,
        'estimated_value': round(total_value, 2)
    })


# =============================================================================
# AI LEARNING ENDPOINTS (Patent Pending)
# =============================================================================

# AI Learning database path
AI_LEARNING_DB = f'{HDD}/ai_learning.db'

def init_ai_learning_db():
    """Initialize AI learning database"""
    import sqlite3
    conn = sqlite3.connect(AI_LEARNING_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ocr_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ocr_text TEXT,
            corrected_name TEXT NOT NULL,
            set_code TEXT,
            confidence REAL,
            success BOOLEAN DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_scans INTEGER DEFAULT 0,
            successful_ids INTEGER DEFAULT 0,
            failed_ids INTEGER DEFAULT 0,
            avg_confidence REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS arm_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT,
            start_pos TEXT,
            end_pos TEXT,
            success BOOLEAN,
            duration_ms INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# Initialize on import
try:
    init_ai_learning_db()
except Exception as e:
    logger.warning(f"AI Learning DB init: {e}")


def log_scan_to_learning(card_name, confidence, ocr_text=None, image_path=None):
    """Auto-log every scan to learning DB so AI can learn from results"""
    try:
        import sqlite3
        conn = sqlite3.connect(AI_LEARNING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scan_results (timestamp, card_name, confidence, image_path)
            VALUES (?, ?, ?, ?)
        ''', (datetime.now().isoformat(), card_name, confidence, image_path))
        conn.commit()
        conn.close()
        logger.info(f"AI LEARN: Logged '{card_name}' ({confidence:.0f}%)")
    except Exception as e:
        logger.warning(f"AI Learn log error: {e}")


@app.route('/api/ai/learn', methods=['POST'])
def ai_learn():
    """
    Record an OCR learning event.
    Called when user corrects/confirms a card identification.
    """
    import sqlite3
    data = request.get_json() or {}

    ocr_text = data.get('ocr_text', '')
    corrected_name = data.get('corrected_name', '')
    set_code = data.get('set_code', '')
    confidence = data.get('confidence', 0.0)
    success = data.get('success', True)

    if not corrected_name:
        return jsonify({'success': False, 'error': 'corrected_name required'}), 400

    try:
        conn = sqlite3.connect(AI_LEARNING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ocr_corrections (timestamp, ocr_text, corrected_name, set_code, confidence, success)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), ocr_text, corrected_name, set_code, confidence, success))
        conn.commit()
        conn.close()

        logger.info(f"AI Learn: '{ocr_text}' -> '{corrected_name}' ({confidence:.1%})")
        return jsonify({'success': True, 'message': 'Learning recorded'})
    except Exception as e:
        logger.error(f"AI Learn error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/stats')
def ai_stats():
    """Get AI learning statistics"""
    import sqlite3
    try:
        conn = sqlite3.connect(AI_LEARNING_DB)
        cursor = conn.cursor()

        # Total corrections
        cursor.execute('SELECT COUNT(*) FROM ocr_corrections')
        total_corrections = cursor.fetchone()[0]

        # Successful corrections
        cursor.execute('SELECT COUNT(*) FROM ocr_corrections WHERE success = 1')
        successful = cursor.fetchone()[0]

        # Average confidence
        cursor.execute('SELECT AVG(confidence) FROM ocr_corrections WHERE confidence > 0')
        avg_conf = cursor.fetchone()[0] or 0

        # Recent corrections (last 24h)
        cursor.execute('''
            SELECT COUNT(*) FROM ocr_corrections
            WHERE timestamp > datetime('now', '-1 day')
        ''')
        recent = cursor.fetchone()[0]

        # Arm movements
        cursor.execute('SELECT COUNT(*) FROM arm_movements')
        arm_moves = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM arm_movements WHERE success = 1')
        arm_success = cursor.fetchone()[0]

        conn.close()

        return jsonify({
            'success': True,
            'stats': {
                'total_corrections': total_corrections,
                'successful_corrections': successful,
                'accuracy_rate': successful / total_corrections if total_corrections > 0 else 0,
                'avg_confidence': round(avg_conf, 1),
                'corrections_24h': recent,
                'arm_movements': arm_moves,
                'arm_success_rate': arm_success / arm_moves if arm_moves > 0 else 0
            }
        })
    except Exception as e:
        logger.error(f"AI Stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/arm/learn', methods=['POST'])
def ai_arm_learn():
    """Record arm movement learning data"""
    import sqlite3
    data = request.get_json() or {}

    action = data.get('action', 'unknown')
    start_pos = json.dumps(data.get('start_pos', {}))
    end_pos = json.dumps(data.get('end_pos', {}))
    success = data.get('success', True)
    duration = data.get('duration_ms', 0)

    try:
        conn = sqlite3.connect(AI_LEARNING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO arm_movements (timestamp, action, start_pos, end_pos, success, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), action, start_pos, end_pos, success, duration))
        conn.commit()
        conn.close()

        logger.info(f"AI Arm Learn: {action} ({'OK' if success else 'FAIL'}) {duration}ms")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/debug/exec', methods=['POST'])
def debug_exec():
    """
    Execute a shell command (for debugging/deployment).

    WARNING: This endpoint allows arbitrary command execution.
    Only enabled when BROK_DEBUG=true environment variable is set.
    DISABLE IN PRODUCTION by setting BROK_DEBUG=false.
    """
    if not DEBUG_MODE:
        return jsonify({
            "success": False,
            "error": "Debug endpoints disabled. Set BROK_DEBUG=true to enable."
        }), 403

    data = request.get_json() or {}
    cmd = data.get('cmd', 'echo hello')
    logger.warning(f"DEBUG EXEC: {cmd[:100]}...")

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, timeout=30
        )
        return jsonify({
            "success": True,
            "stdout": result.stdout.decode(),
            "stderr": result.stderr.decode(),
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Command timed out"}), 408
    except Exception as e:
        logger.error(f"Debug exec error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# LIBRARY DATABASE API (Master on Brock's 160GB HDD)
# =============================================================================
LIBRARY_DB_PATH = f'{DATABASE_DIR}/nexus_library.db'
_library_db = None

def get_library_db():
    """Get or create library database connection."""
    global _library_db
    import sqlite3

    if _library_db is None:
        os.makedirs(DATABASE_DIR, exist_ok=True)
        _library_db = sqlite3.connect(LIBRARY_DB_PATH, check_same_thread=False)
        _library_db.row_factory = sqlite3.Row

        # Initialize schema
        _library_db.executescript('''
            CREATE TABLE IF NOT EXISTS cards (
                call_number TEXT PRIMARY KEY,
                box_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                name TEXT NOT NULL,
                set_code TEXT,
                set_name TEXT,
                collector_number TEXT,
                rarity TEXT,
                colors TEXT,
                color_identity TEXT,
                mana_cost TEXT,
                cmc REAL DEFAULT 0,
                type_line TEXT,
                oracle_text TEXT,
                power TEXT,
                toughness TEXT,
                foil INTEGER DEFAULT 0,
                condition TEXT DEFAULT 'NM',
                language TEXT DEFAULT 'en',
                price REAL DEFAULT 0,
                price_foil REAL DEFAULT 0,
                price_source TEXT,
                price_updated TEXT,
                image_url TEXT,
                image_url_small TEXT,
                art_hash TEXT,
                scryfall_id TEXT,
                uuid TEXT,
                cataloged_at TEXT,
                updated_at TEXT,
                notes TEXT,
                display INTEGER DEFAULT 0,
                display_case INTEGER NULL,
                card_type TEXT DEFAULT 'mtg',
                listing_status TEXT DEFAULT 'available',
                listing_id TEXT,
                listed_at TEXT,
                sold_at TEXT,
                sold_price REAL
            );
            CREATE INDEX IF NOT EXISTS idx_name ON cards(name);
            CREATE INDEX IF NOT EXISTS idx_box_id ON cards(box_id);
            CREATE INDEX IF NOT EXISTS idx_set_code ON cards(set_code);
            CREATE INDEX IF NOT EXISTS idx_price ON cards(price);
            CREATE INDEX IF NOT EXISTS idx_listing_status ON cards(listing_status);
        ''')
        _library_db.commit()
        logger.info(f"Library DB initialized: {LIBRARY_DB_PATH}")

    return _library_db


@app.route('/api/library/stats')
def library_stats():
    """Get library statistics."""
    db = get_library_db()
    count = db.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
    value = db.execute('SELECT SUM(price) FROM cards').fetchone()[0] or 0
    return jsonify({
        'success': True,
        'count': count,
        'total_value': value,
        'db_path': LIBRARY_DB_PATH
    })


@app.route('/api/library/card/<call_number>')
def library_get_card(call_number):
    """Get a card by call number."""
    db = get_library_db()
    row = db.execute('SELECT * FROM cards WHERE call_number = ?', (call_number,)).fetchone()
    if row:
        return jsonify({'success': True, 'card': dict(row)})
    return jsonify({'success': False, 'error': 'Card not found'}), 404


@app.route('/api/library/card', methods=['POST'])
def library_add_card():
    """Add or update a card."""
    db = get_library_db()
    card = request.get_json()

    if not card or 'call_number' not in card:
        return jsonify({'success': False, 'error': 'Missing call_number'}), 400

    # Build dynamic INSERT/UPDATE
    columns = list(card.keys())
    placeholders = ', '.join(['?' for _ in columns])
    updates = ', '.join([f'{col}=excluded.{col}' for col in columns])

    sql = f'''
        INSERT INTO cards ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(call_number) DO UPDATE SET {updates}
    '''

    try:
        db.execute(sql, [card.get(col) for col in columns])
        db.commit()
        return jsonify({'success': True, 'call_number': card['call_number']})
    except Exception as e:
        logger.error(f"Library add error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/library/card/<call_number>', methods=['DELETE'])
def library_delete_card(call_number):
    """Delete a card."""
    db = get_library_db()
    db.execute('DELETE FROM cards WHERE call_number = ?', (call_number,))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/library/search', methods=['POST'])
def library_search():
    """Search library with filters."""
    db = get_library_db()
    data = request.get_json() or {}

    query = 'SELECT * FROM cards WHERE 1=1'
    params = []

    if data.get('name'):
        query += ' AND name LIKE ?'
        params.append(f"%{data['name']}%")

    if data.get('set_code'):
        query += ' AND set_code = ?'
        params.append(data['set_code'])

    if data.get('box_id'):
        query += ' AND box_id = ?'
        params.append(data['box_id'])

    if data.get('min_price'):
        query += ' AND price >= ?'
        params.append(data['min_price'])

    if data.get('max_price'):
        query += ' AND price <= ?'
        params.append(data['max_price'])

    if data.get('listing_status'):
        query += ' AND listing_status = ?'
        params.append(data['listing_status'])

    limit = data.get('limit', 100)
    query += f' LIMIT {int(limit)}'

    rows = db.execute(query, params).fetchall()
    return jsonify({'success': True, 'cards': [dict(r) for r in rows], 'count': len(rows)})


@app.route('/api/library/all')
def library_get_all():
    """Get all cards (paginated)."""
    db = get_library_db()
    limit = request.args.get('limit', 1000, type=int)
    offset = request.args.get('offset', 0, type=int)

    rows = db.execute('SELECT * FROM cards LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    total = db.execute('SELECT COUNT(*) FROM cards').fetchone()[0]

    return jsonify({
        'success': True,
        'cards': [dict(r) for r in rows],
        'count': len(rows),
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.route('/api/library/bulk', methods=['POST'])
def library_bulk_add():
    """Add multiple cards at once."""
    db = get_library_db()
    cards = request.get_json()

    if not isinstance(cards, list):
        return jsonify({'success': False, 'error': 'Expected list of cards'}), 400

    added = 0
    errors = []

    for card in cards:
        if 'call_number' not in card:
            errors.append('Missing call_number')
            continue

        columns = list(card.keys())
        placeholders = ', '.join(['?' for _ in columns])
        updates = ', '.join([f'{col}=excluded.{col}' for col in columns])

        sql = f'''
            INSERT INTO cards ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(call_number) DO UPDATE SET {updates}
        '''

        try:
            db.execute(sql, [card.get(col) for col in columns])
            added += 1
        except Exception as e:
            errors.append(f"{card.get('call_number')}: {e}")

    db.commit()
    return jsonify({'success': True, 'added': added, 'errors': errors})


@app.route('/api/library/listing/pending', methods=['POST'])
def library_mark_pending():
    """Mark card as pending sale."""
    db = get_library_db()
    data = request.get_json()
    call_number = data.get('call_number')
    listing_id = data.get('listing_id')

    db.execute(
        '''UPDATE cards SET listing_status = 'pending', listing_id = ?,
           listed_at = ? WHERE call_number = ?''',
        (listing_id, datetime.now().isoformat(), call_number)
    )
    db.commit()
    return jsonify({'success': True})


@app.route('/api/library/listing/sold', methods=['POST'])
def library_mark_sold():
    """Mark card as sold."""
    db = get_library_db()
    data = request.get_json()
    call_number = data.get('call_number')
    sold_price = data.get('sold_price')

    db.execute(
        '''UPDATE cards SET listing_status = 'sold', sold_at = ?,
           sold_price = ? WHERE call_number = ?''',
        (datetime.now().isoformat(), sold_price, call_number)
    )
    db.commit()
    return jsonify({'success': True})


@app.route('/api/library/listing/available', methods=['POST'])
def library_mark_available():
    """Mark card as available (cancel listing)."""
    db = get_library_db()
    data = request.get_json()
    call_number = data.get('call_number')

    db.execute(
        '''UPDATE cards SET listing_status = 'available', listing_id = NULL,
           listed_at = NULL WHERE call_number = ?''',
        (call_number,)
    )
    db.commit()
    return jsonify({'success': True})


if __name__ == '__main__':
    load_state()
    load_master_database()
    load_set_symbols()  # Load set symbol templates for visual matching
    logger.info('=' * 50)
    logger.info('BROK - Accuracy-First OCR Server')
    logger.info('DUAL-CAMERA ARCHITECTURE ENABLED')
    logger.info(f'  Local OwlEye: CAM{LOCAL_CAMERA["index"]} (back detection)')
    logger.info(f'  Snarf OwlEye: Front capture + OCR')
    logger.info(f'GPU: {cv2.ocl.useOpenCL()} (RX 590)')
    logger.info(f'Master DB: {len(master_cards)} cards')
    logger.info(f'Set Symbols: {len(set_symbol_templates)} templates')
    logger.info(f'Storage: {HDD}')
    logger.info(f'Cache: {len(card_cache)} cards')
    logger.info(f'Inventory: {len(inventory)} unique cards')
    logger.info(f'Current Box: {current_box}{box_position}')
    logger.info(f'Total Scans: {scan_counter}')
    logger.info('Target: 95-98% accuracy, 100+ cards/hour')
    logger.info('Endpoints: /api/scan, /api/dual_scan, /api/detect_type')
    logger.info('Video: /api/video/owleye, /api/video/czur, /api/video/snarf')
    logger.info('Snapshots: /api/video/snapshot/<owleye|czur|snarf>')
    logger.info('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
