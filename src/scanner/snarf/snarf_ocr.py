#!/usr/bin/env python3
"""
NEXUS OCR Module for Snarf
Patent Claim 1: Multi-Region Scanning Protocol with Cross-Validation

Moved from Brock to Snarf Feb 10 2026.
CZUR captures → Snarf OCRs → Brock does Coral AI recognition.
"""

import os
import re
import cv2
import subprocess
import logging
import numpy as np

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

logger = logging.getLogger('SNARF_OCR')

# =============================================================================
# CONFIGURATION
# =============================================================================
SET_SYMBOLS_DIR = '/home/nexus1/set_symbols'
SCAN_DIR = '/home/nexus1/scans'
os.makedirs(SCAN_DIR, exist_ok=True)

# Set symbol templates (loaded on first use)
set_symbol_templates = {}

# =============================================================================
# OCR CORRECTIONS
# =============================================================================
OCR_CORRECTIONS = {
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

MTG_COMMON_WORDS = {
    'the', 'of', 'and', 'to', 'from', 'with', 'for', 'by',
    'dragon', 'angel', 'demon', 'beast', 'wizard', 'knight',
    'lightning', 'bolt', 'fire', 'storm', 'path', 'exile',
    'sword', 'shield', 'lord', 'queen', 'king', 'mage',
    'dark', 'light', 'shadow', 'sun', 'moon', 'star',
    'power', 'might', 'force', 'rage', 'fury', 'wrath'
}


# =============================================================================
# SET SYMBOL MATCHING
# =============================================================================

def load_set_symbols():
    """Load set symbol templates into memory for matching"""
    global set_symbol_templates

    if not os.path.exists(SET_SYMBOLS_DIR):
        return False

    count = 0
    for f in os.listdir(SET_SYMBOLS_DIR):
        if f.endswith('.png'):
            set_code = f[:-4]
            img_path = os.path.join(SET_SYMBOLS_DIR, f)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                set_symbol_templates[set_code] = img
                count += 1

    logger.info(f"Loaded {count} set symbol templates")
    return count > 0


def extract_set_symbol_region(card_img):
    """Extract the set symbol region from a card image."""
    h, w = card_img.shape[:2]
    aspect_ratio = w / h

    if aspect_ratio > 1.5:
        y1 = int(h * 0.48)
        y2 = int(h * 0.58)
        x1 = int(w * 0.42)
        x2 = int(w * 0.58)
    else:
        y1 = int(h * 0.48)
        y2 = int(h * 0.58)
        x1 = int(w * 0.88)
        x2 = int(w * 0.98)

    return card_img[y1:y2, x1:x2]


def isolate_symbol_from_region(region):
    """Find and isolate the set symbol from the type line region."""
    if region is None or region.size == 0:
        return None

    if len(region.shape) == 3:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    else:
        gray = region.copy()

    h, w = gray.shape
    type_line_region = gray[int(h * 0.5):, int(w * 0.75):]

    if type_line_region.size < 100:
        return None

    thresh = cv2.adaptiveThreshold(
        type_line_region, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 21, 5
    )

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return type_line_region

    rh, rw = type_line_region.shape
    best_contour = None
    best_score = 0

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)

        min_area = rh * rw * 0.02
        max_area = rh * rw * 0.6

        if area < min_area or area > max_area:
            continue

        aspect = cw / ch if ch > 0 else 0
        if aspect < 0.4 or aspect > 2.5:
            continue

        size_score = area / max_area
        aspect_score = 1.0 - abs(1.0 - aspect) * 0.3
        edge_score = 1.0 if (x > 2 and y > 2) else 0.5

        score = size_score * aspect_score * edge_score

        if score > best_score:
            best_score = score
            best_contour = cnt

    if best_contour is None:
        return type_line_region

    x, y, cw, ch = cv2.boundingRect(best_contour)
    pad = 3
    x = max(0, x - pad)
    y = max(0, y - pad)
    cw = min(rw - x, cw + 2 * pad)
    ch = min(rh - y, ch + 2 * pad)

    symbol = type_line_region[y:y+ch, x:x+cw]
    return symbol if symbol.size > 50 else type_line_region


def match_set_symbol(card_img, top_n=5):
    """Match the set symbol using template matching, Hu moments, and contour matching."""
    if not set_symbol_templates:
        load_set_symbols()

    if not set_symbol_templates:
        return []

    region = extract_set_symbol_region(card_img)
    if region is None or region.size == 0:
        return []

    symbol = isolate_symbol_from_region(region)

    if symbol is None or symbol.size < 50:
        return []

    symbol_resized = cv2.resize(symbol, (32, 32))
    _, symbol_thresh = cv2.threshold(
        symbol_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    symbol_moments = cv2.HuMoments(cv2.moments(symbol_thresh)).flatten()
    symbol_contours, _ = cv2.findContours(
        symbol_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    symbol_contour = max(symbol_contours, key=cv2.contourArea) if symbol_contours else None

    matches = []

    for set_code, template in set_symbol_templates.items():
        try:
            template_resized = cv2.resize(template, (32, 32))
            _, template_thresh = cv2.threshold(
                template_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            result = cv2.matchTemplate(
                symbol_resized, template_resized, cv2.TM_CCOEFF_NORMED
            )
            template_score = (result[0][0] + 1) * 50

            hu_distance = cv2.matchShapes(
                symbol_thresh, template_thresh, cv2.CONTOURS_MATCH_I2, 0
            )
            hu_score = max(0, 100 - hu_distance * 100)

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

            combined = (template_score * 0.4 + hu_score * 0.3 + contour_score * 0.3)

            if combined > 35:
                matches.append((set_code, int(combined)))

        except Exception:
            continue

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[:top_n]


def identify_set_from_image(card_img):
    """Identify the set of a card from its image using symbol matching."""
    matches = match_set_symbol(card_img)
    if matches:
        return matches[0]
    return None, 0


# =============================================================================
# COLLECTOR INFO OCR
# =============================================================================

def extract_collector_region(img):
    """Extract the collector info region (bottom 8% of card, left side)"""
    h, w = img.shape[:2]
    collector_top = int(h * 0.92)
    collector_bottom = int(h * 0.98)
    collector_left = int(w * 0.05)
    collector_right = int(w * 0.50)
    return img[collector_top:collector_bottom, collector_left:collector_right]


def ocr_collector_info(img):
    """OCR the collector info region to extract set code and number."""
    collector_region = extract_collector_region(img)

    if len(collector_region.shape) == 3:
        gray = cv2.cvtColor(collector_region, cv2.COLOR_BGR2GRAY)
    else:
        gray = collector_region

    scaled = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

    adaptive = cv2.adaptiveThreshold(
        scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    best_text = ''
    for preproc_name, preproc_img in [('adaptive', adaptive), ('inverted', cv2.bitwise_not(scaled))]:
        for psm in [7, 6, 13]:
            try:
                text = pytesseract.image_to_string(
                    preproc_img, config=f'--psm {psm} --oem 3', lang='eng'
                ).strip()
                if text and len(text) > len(best_text):
                    best_text = text
            except Exception:
                pass

    logger.info(f"Collector OCR: {best_text}")

    # Also try bottom 15% of full card
    h, w = img.shape[:2]
    full_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    bottom_region = full_gray[int(h * 0.85):, :]
    bottom_scaled = cv2.resize(bottom_region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    bottom_adaptive = cv2.adaptiveThreshold(
        bottom_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )
    try:
        bottom_text = pytesseract.image_to_string(
            bottom_adaptive, config='--psm 6 --oem 3', lang='eng'
        ).strip()
        if bottom_text:
            best_text = best_text + ' ' + bottom_text
    except Exception:
        pass

    # Parse set code and collector number
    set_code = None
    collector_num = None
    text_upper = best_text.upper()

    pat1 = re.search(r'\b([A-Z]{2,4})\s*[·.]\s*(\d{1,4})/\d+', text_upper)
    if pat1:
        return pat1.group(1), pat1.group(2)

    pat2 = re.search(r'\b([A-Z]{3})\s+(\d{1,4})\b', text_upper)
    if pat2:
        return pat2.group(1), pat2.group(2)

    num_match = re.search(r'\b(\d{1,4})/\d+\b', text_upper)
    if num_match:
        collector_num = num_match.group(1)

    set_match = re.search(r'\b([A-Z]{2,4})\b', text_upper)
    if set_match:
        candidate = set_match.group(1)
        skip_words = {'THE', 'AND', 'FOR', 'YOU', 'MAY', 'PAY', 'CAN', 'HAS', 'ITS',
                      'WITH', 'THIS', 'EACH', 'DEAL', 'PSM', 'OCR', 'IMG'}
        if candidate not in skip_words:
            set_code = candidate

    return set_code, collector_num


# =============================================================================
# TESSERACT OCR ENGINE
# =============================================================================

def correct_ocr_text(text):
    """Apply post-OCR corrections for common mistakes."""
    if not text:
        return text

    words = text.split()
    corrected_words = []

    for word in words:
        word_lower = word.lower()

        if word_lower in OCR_CORRECTIONS:
            corrected_words.append(OCR_CORRECTIONS[word_lower])
            continue

        if word_lower not in MTG_COMMON_WORDS:
            corrected = word
            if '0' in word and not word.isdigit():
                corrected = corrected.replace('0', 'O')
            if '1' in word and len(word) > 1 and not word.isdigit():
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

    return ' '.join(corrected_words)


def preprocess_for_ocr(img, method='auto'):
    """Minimal preprocessing - just grayscale."""
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def run_tesseract(image, psm=7):
    """Run Tesseract with confidence scoring."""
    if not PYTESSERACT_AVAILABLE:
        return run_tesseract_subprocess(image, psm)

    try:
        if isinstance(image, np.ndarray):
            from PIL import Image as PILImage
            if len(image.shape) == 3:
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                pil_image = PILImage.fromarray(rgb)
            else:
                pil_image = PILImage.fromarray(image)
        else:
            pil_image = image

        config = f'--psm {psm} --oem 3'
        text = pytesseract.image_to_string(pil_image, config=config, lang='eng').strip()

        try:
            data = pytesseract.image_to_data(
                pil_image, config=config, lang='eng',
                output_type=pytesseract.Output.DICT
            )
            confidences = [int(c) for c in data['conf'] if c != '-1' and int(c) > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 50.0
        except Exception:
            avg_conf = 50.0 if text else 0.0

        text = re.sub(r'[|\\/_~`]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        corrected = correct_ocr_text(text)

        return corrected, avg_conf

    except Exception as e:
        logger.error(f'Tesseract error: {e}')
        return '', 0


def run_tesseract_subprocess(image, psm=7):
    """Fallback: Run Tesseract via subprocess."""
    temp_path = f'{SCAN_DIR}/_temp_ocr.png'
    cv2.imwrite(temp_path, image)

    try:
        result = subprocess.run([
            'tesseract', temp_path, 'stdout',
            '--psm', str(psm), '--oem', '3', '-l', 'eng',
            '-c', "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ',.:-!&()",
            'tsv'
        ], capture_output=True, text=True, timeout=10)

        lines = result.stdout.strip().split('\n')
        texts = []
        confidences = []

        for line in lines[1:]:
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
        return correct_ocr_text(full_text), avg_conf

    except Exception as e:
        logger.error(f'Tesseract subprocess error: {e}')
        return '', 0


def run_tesseract_both_ways(image, psm=7):
    """Run OCR on original, inverted, AND adaptive threshold in parallel, pick best.
    Pi 5 has 4 cores — run all 3 Tesseract calls simultaneously."""
    from concurrent.futures import ThreadPoolExecutor

    gray = preprocess_for_ocr(image)
    inverted = cv2.bitwise_not(gray)

    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    with ThreadPoolExecutor(max_workers=3) as pool:
        f1 = pool.submit(run_tesseract, gray, psm)
        f2 = pool.submit(run_tesseract, inverted, psm)
        f3 = pool.submit(run_tesseract, adaptive, psm)
        text1, conf1 = f1.result()
        text2, conf2 = f2.result()
        text3, conf3 = f3.result()

    candidates = [
        (text1, conf1, 'ORIGINAL'),
        (text2, conf2, 'INVERTED'),
        (text3, conf3, 'ADAPTIVE'),
    ]
    valid = [(t, c, label) for t, c, label in candidates if t]

    if not valid:
        return '', 0

    best_text, best_conf, best_label = max(valid, key=lambda x: x[1])
    logger.info(f"Using {best_label}: '{best_text[:50]}' ({best_conf:.0f}%)")
    return best_text, best_conf


# =============================================================================
# MULTI-PASS OCR (Patent Claim 1)
# =============================================================================

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

    # NO CROP - use raw image directly
    card_img = img
    logger.info("Using raw image directly - no card detection")

    # Orientation detection DISABLED
    logger.info("Orientation detection DISABLED")

    ch, cw = card_img.shape[:2]

    # =========================================================================
    # REGION 1: TITLE
    # =========================================================================
    logger.info("REGION 1: Title extraction")
    title_found = False
    for top_pct, bot_pct in [(0.02, 0.08), (0.03, 0.10), (0.01, 0.12), (0.00, 0.15)]:
        y1 = int(ch * top_pct)
        y2 = int(ch * bot_pct)
        x1 = int(cw * 0.05)
        x2 = int(cw * 0.80)
        title_strip = card_img[y1:y2, x1:x2]
        title_strip = cv2.resize(title_strip, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        title_text, title_conf = run_tesseract_both_ways(title_strip, psm=7)
        title_text = title_text.strip()
        if title_text and len(title_text) >= 3:
            alpha_count = sum(1 for c in title_text if c.isalpha())
            if alpha_count > len(title_text) * 0.4:
                results.append(title_text)
                logger.info(f"  TITLE: '{title_text}' ({title_conf:.1f}%) [{top_pct}-{bot_pct}]")
                title_found = True
                break
    if not title_found:
        logger.warning("  Title extraction failed at all crop heights")

    # =========================================================================
    # FULL CARD OCR - PSM 6 fallback
    # =========================================================================
    logger.info("FULL CARD OCR (PSM 6 fallback)...")
    full_text, full_conf = run_tesseract_both_ways(card_img, psm=6)
    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
    logger.info(f"Full card: {len(lines)} text lines, conf={full_conf:.1f}%")

    for line in lines[:5]:
        if len(line) < 4:
            continue
        alpha_count = sum(1 for c in line if c.isalpha())
        if alpha_count < len(line) * 0.5:
            continue
        if line not in results:
            results.append(line)

    title_results = results
    title_confidence = full_conf
    region_data = {}
    region_data['title'] = {'texts': title_results, 'confidence': title_confidence}

    # =========================================================================
    # REGIONS 2, 3, 4 in PARALLEL (all independent image crops)
    # Pi 5 has 4 cores — use them
    # =========================================================================
    from concurrent.futures import ThreadPoolExecutor

    def _region2_set_symbol(img):
        """REGION 2: Set symbol matching."""
        code, conf = identify_set_from_image(img)
        if code and conf >= 40:
            logger.info(f'  SET SYMBOL: {code.upper()} ({conf}%)')
            return {'set': code, 'confidence': conf}
        return {'set': None, 'confidence': 0}

    def _region3_collector(img):
        """REGION 3: Collector info OCR."""
        try:
            cset, cnum = ocr_collector_info(img)
            if cset or cnum:
                logger.info(f'  COLLECTOR: set={cset}, num={cnum}')
                return {'set': cset, 'number': cnum, 'confidence': 75}
        except Exception:
            pass
        return {'set': None, 'number': None, 'confidence': 0}

    def _region4_mana(img, h, w):
        """REGION 4: Mana cost color detection."""
        try:
            mana_region = img[int(h*0.02):int(h*0.12), int(w*0.70):int(w*0.98)]
            hsv = cv2.cvtColor(mana_region, cv2.COLOR_BGR2HSV)
            colors = []
            if cv2.countNonZero(cv2.inRange(hsv, (0, 0, 200), (180, 50, 255))) > 50:
                colors.append('W')
            if cv2.countNonZero(cv2.inRange(hsv, (100, 50, 50), (130, 255, 255))) > 50:
                colors.append('U')
            if cv2.countNonZero(cv2.inRange(hsv, (0, 0, 0), (180, 255, 50))) > 50:
                colors.append('B')
            r1 = cv2.countNonZero(cv2.inRange(hsv, (0, 50, 50), (10, 255, 255)))
            r2 = cv2.countNonZero(cv2.inRange(hsv, (160, 50, 50), (180, 255, 255)))
            if r1 + r2 > 50:
                colors.append('R')
            if cv2.countNonZero(cv2.inRange(hsv, (35, 50, 50), (85, 255, 255))) > 50:
                colors.append('G')
            if colors:
                logger.info(f'  MANA COLORS: {colors}')
            return {'colors': colors, 'confidence': 60}
        except Exception:
            return {'colors': [], 'confidence': 0}

    logger.info("REGIONS 2-4: Running in parallel")
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_set = pool.submit(_region2_set_symbol, card_img)
        f_coll = pool.submit(_region3_collector, card_img)
        f_mana = pool.submit(_region4_mana, card_img, ch, cw)

        region_data['set_symbol'] = f_set.result()
        region_data['collector'] = f_coll.result()
        region_data['mana'] = f_mana.result()

    # Extract set/collector from parallel results
    set_code = region_data['set_symbol'].get('set')
    coll_data = region_data['collector']
    if not set_code and coll_data.get('set'):
        set_code = coll_data['set']
    collector_num = coll_data.get('number')

    # =========================================================================
    # REGION 5: ART (future)
    # =========================================================================
    region_data['art'] = {'fingerprint': None, 'confidence': 0}

    logger.info(f"=== OCR COMPLETE === Results: {len(results)} candidates, set={set_code}, collector={collector_num}")

    return results, set_code, collector_num, region_data
