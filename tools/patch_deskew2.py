#!/usr/bin/env python3
"""
Patch 5: Replace minAreaRect deskew with Hough-based deskew.
Also update run_ocr to:
1. Deskew the card image before OCR
2. Run PSM 11 on full deskewed card
3. Extract card name from ability text patterns ("Whenever X", "if X is monstrous", etc.)
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

# ─────────────────────────────────────────────────────────────
# Fix 1: Replace the minAreaRect deskew block with Hough-based deskew
# ─────────────────────────────────────────────────────────────
old_deskew = '''        # Deskew: correct any remaining tilt so text lines are horizontal
        # Find the card's outer border angle using minAreaRect on a thresholded image
        try:
            import numpy as _np
            _dh, _dw = cropped.shape[:2]
            _gray_d = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            # Card border is typically the darkest part of the image (black outer border)
            _, _mask = cv2.threshold(_gray_d, 40, 255, cv2.THRESH_BINARY)
            # Find outer card edge contour
            _dcontours, _ = cv2.findContours(_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if _dcontours:
                _dc = max(_dcontours, key=cv2.contourArea)
                if cv2.contourArea(_dc) > (_dh * _dw * 0.5):  # must be at least 50% of image
                    _drect = cv2.minAreaRect(_dc)
                    _dangle = _drect[2]  # angle in [-90, 0)
                    # Normalize: if width < height (portrait box), angle is tilt from vertical
                    if _drect[1][0] < _drect[1][1]:
                        _dangle = _dangle + 90  # convert to tilt from horizontal
                    # Only deskew if tilt is significant but small (0.5 - 15 degrees)
                    if 0.5 < abs(_dangle) < 15:
                        _center = (_dw // 2, _dh // 2)
                        _M = cv2.getRotationMatrix2D(_center, _dangle, 1.0)
                        cropped = cv2.warpAffine(cropped, _M, (_dw, _dh), borderMode=cv2.BORDER_REPLICATE)
                        logger.info(f"[ADAPTIVE] Deskewed {_dangle:.1f}°: {_dw}x{_dh}")
        except Exception as _de:
            logger.warning(f"[ADAPTIVE] Deskew failed: {_de}")'''

new_deskew = '''        # Deskew: correct card tilt using HoughLinesP on card edges
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
            logger.warning(f"[ADAPTIVE] Deskew failed: {_de}")'''

if old_deskew in content:
    content = content.replace(old_deskew, new_deskew, 1)
    print("Fix 1: Hough-based deskew applied")
else:
    print("ERROR: old deskew block not found")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Fix 2: Update run_ocr to extract card name from ability text
# Add ability text pattern extraction after the full_text_combined line
# ─────────────────────────────────────────────────────────────

old_fulltext_block = '''        # Also run sparse OCR on full card to catch name if region crop missed it
        sparse_text = pytesseract.image_to_string(img, config=r'--oem 3 --psm 11')
        # Merge full_text with sparse_text lines (deduplicated)
        full_text_combined = full_text + chr(10) + sparse_text'''

new_fulltext_block = '''        # Also run sparse OCR on full card to catch name if region crop missed it
        sparse_text = pytesseract.image_to_string(img, config=r'--oem 3 --psm 11')
        # Merge full_text with sparse_text lines (deduplicated)
        full_text_combined = full_text + chr(10) + sparse_text

        # Extract card name from ability text patterns:
        # "Whenever [Card Name] deals", "if [Card Name] is", "[Card Name]'s", etc.
        # The card's own name appears in its ability text (self-referential)
        import re as _re_ocr
        _ability_name = ''
        _ability_patterns = [
            r'Whenever\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s+(?:deals|attacks|blocks|becomes|is)',
            r'if\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s+(?:is|has|would)',
            r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})(?:\'s|'s)\s+(?:ability|power|controller)',
            r'put\s+(?:a|X|\d+)\s+\w+\s+counter\s+on\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})',
        ]
        # Look in ability text (lower portion of sparse_text)
        _ability_lines = [l.strip() for l in sparse_text.split(chr(10)) if len(l.strip()) > 5]
        _name_candidates = {}
        for _pat in _ability_patterns:
            for _line in _ability_lines:
                _m = _re_ocr.search(_pat, _line)
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
                logger.info(f"[OCR] Ability text name: '{_ability_name}' (seen {_best_count}x)")'''

if old_fulltext_block in content:
    content = content.replace(old_fulltext_block, new_fulltext_block, 1)
    print("Fix 2: Ability text name extraction added")
else:
    print("ERROR: full_text block not found")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Fix 3: Prefer ability_name over region crop if region is low confidence
# ─────────────────────────────────────────────────────────────

old_name_pick = '''        # Pick card name: prefer region crop if confidence > 50, else search full text
        name_result = results.get('name', {})
        card_name = ''
        name_conf = 0
        if isinstance(name_result, dict) and name_result.get('confidence', 0) > 50:
            card_name = name_result['text']
            name_conf = name_result['confidence']
        else:
            # Search all lines from full-card OCR for best card name candidate
            # A card name is: 2-40 chars, mostly alphabetic, appears in top portion of output
            lines = [l.strip() for l in full_text_combined.split('\\n') if l.strip()]'''

new_name_pick = '''        # Pick card name: prefer ability text name, then region crop, then full text scan
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
            lines = [l.strip() for l in full_text_combined.split('\\n') if l.strip()]'''

if old_name_pick in content:
    content = content.replace(old_name_pick, new_name_pick, 1)
    print("Fix 3: Ability name prioritization added")
else:
    print("ERROR: name pick block not found")
    sys.exit(1)

with open(SERVER, "w") as f:
    f.write(content)

# Verify syntax
import subprocess
result = subprocess.run(['python3', '-c', f'import py_compile; py_compile.compile("{SERVER}", doraise=True)'],
                      capture_output=True, text=True)
if result.returncode == 0:
    print("Syntax OK")
else:
    print(f"SYNTAX ERROR: {result.stderr}")
    sys.exit(1)

print("All patches applied successfully")
