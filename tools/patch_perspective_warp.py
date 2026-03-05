#!/usr/bin/env python3
"""
Patch 7: Replace adaptive_capture brightness-threshold + boundingRect + rotate + deskew
with a call to the existing detect_and_crop_card() (Canny edge + perspective warp).
Also:
- Reject card-type words from OCR name region
- Raise Stage 2.5 OCR name similarity threshold 70% -> 85%
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

# ─────────────────────────────────────────────────────────────
# Fix 1: Replace the brightness threshold + bounding rect +
#         auto-rotate + deskew in adaptive_capture with
#         detect_and_crop_card() perspective warp
# ─────────────────────────────────────────────────────────────

old_detect = """            # Find card via brightness thresholding
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
            import numpy as _np
            _dh, _dw = cropped.shape[:2]
            _gray_d = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            _edges_d = cv2.Canny(_gray_d, 30, 200, apertureSize=3)
            _lines_d = cv2.HoughLinesP(_edges_d, 1, _np.pi/180, threshold=200,
                                        minLineLength=int(_dh*0.2), maxLineGap=30)
            if _lines_d is not None:
                _vert_angles = []
                for _l in _lines_d:
                    _x1, _y1, _x2, _y2 = _l[0]
                    _dx, _dy = _x2-_x1, _y2-_y1
                    if abs(_dy) > abs(_dx):  # near-vertical line
                        _ang = _np.degrees(_np.arctan2(_dy, _dx))
                        # normalize to deviation from vertical
                        _dev = _ang + 90 if _ang < 0 else _ang - 90
                        _vert_angles.append(_dev)
                if _vert_angles:
                    _tilt = float(_np.median(_vert_angles))
                    if 0.5 < abs(_tilt) < 20:
                        _center = (_dw // 2, _dh // 2)
                        _M = cv2.getRotationMatrix2D(_center, _tilt, 1.0)
                        cropped = cv2.warpAffine(cropped, _M, (_dw, _dh), borderMode=cv2.BORDER_REPLICATE)
                        logger.info(f"[ADAPTIVE] Deskewed {_tilt:.1f}° (Hough): {_dw}x{_dh}")
        except Exception as _de:
            logger.warning(f"[ADAPTIVE] Deskew failed: {_de}")"""

new_detect = """            # Canny edge detection + 4-corner perspective warp via detect_and_crop_card()
            # Handles any card orientation/tilt and removes all background
            card_img = detect_and_crop_card(cropped)
            if card_img is not None:
                cropped = card_img
                logger.info(f"[ADAPTIVE] Perspective warp: {cropped.shape[1]}x{cropped.shape[0]}")
                cv2.imwrite(os.path.join(SCAN_DIR, "debug_card_rect.jpg"), cropped)
            else:
                logger.warning("[ADAPTIVE] Edge detection failed, using full lightbox crop")
        else:
            logger.warning("[ADAPTIVE] No LIGHTBOX_FIXED set, using full frame")"""

if old_detect in content:
    content = content.replace(old_detect, new_detect, 1)
    print("Fix 1 applied: perspective warp replaces brightness threshold + bounding rect + deskew")
else:
    print("ERROR: Fix 1 target not found")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Fix 2: Reject card-type words from OCR name region result
# Insert after the name priority logic in run_ocr
# ─────────────────────────────────────────────────────────────

old_type_check = "        # Priority 1: ability text pattern match (self-referential card name)\n        if _ability_name and len(_ability_name) >= 3:"

new_type_check = """        # Reject name region result if it's a known card type word
        _type_stopwords = {'creature', 'instant', 'sorcery', 'artifact', 'enchantment',
                           'planeswalker', 'land', 'battle', 'tribal', 'legendary', 'basic'}
        _nr = results.get('name', {})
        if isinstance(_nr, dict) and _nr.get('text', '').strip().lower() in _type_stopwords:
            logger.info(f"[OCR] Name region returned type word '{_nr['text']}', discarding")
            results['name'] = {'text': '', 'confidence': 0}

        # Priority 1: ability text pattern match (self-referential card name)
        if _ability_name and len(_ability_name) >= 3:"""

if old_type_check in content:
    content = content.replace(old_type_check, new_type_check, 1)
    print("Fix 2 applied: card-type word rejection for name region")
else:
    print("ERROR: Fix 2 target not found")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Fix 3: Raise Stage 2.5 OCR name fast-path threshold 70% -> 85%
# ─────────────────────────────────────────────────────────────

old_thresh = "                    if _xsim >= 70:"
new_thresh = "                    if _xsim >= 85:"

if old_thresh in content:
    content = content.replace(old_thresh, new_thresh, 1)
    print("Fix 3 applied: Stage 2.5 OCR name threshold 70% -> 85%")
else:
    print("ERROR: Fix 3 target not found")
    sys.exit(1)

with open(SERVER, "w") as f:
    f.write(content)

import subprocess
r = subprocess.run(['python3', '-c', f'import py_compile; py_compile.compile("{SERVER}", doraise=True)'],
                   capture_output=True, text=True)
if r.returncode == 0:
    print("Syntax OK")
else:
    print(f"SYNTAX ERROR: {r.stderr}")
    sys.exit(1)

print("All patches applied")
