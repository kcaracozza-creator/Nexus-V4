#!/usr/bin/env python3
"""
Patch 4: Add card deskewing in adaptive_capture after the 90° rotation.
Uses minAreaRect on the card's outer border to measure and correct tilt.
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

# ─────────────────────────────────────────────────────────────
# Find the block after auto-rotate and before saving crop_path
# We'll add deskewing AFTER the 90° CW rotation
# ─────────────────────────────────────────────────────────────

old_block = '''        # Auto-rotate if card is landscape (any time width > height, rotate to portrait)
        ch_crop, cw_crop = cropped.shape[:2]
        if cw_crop > ch_crop:
            cropped = cv2.rotate(cropped, cv2.ROTATE_90_CLOCKWISE)
            logger.info(f"[ADAPTIVE] Rotated 90 CW: {cropped.shape[1]}x{cropped.shape[0]}")

        crop_path = image_path.replace(".jpg", "_cropped.jpg")'''

new_block = '''        # Auto-rotate if card is landscape (any time width > height, rotate to portrait)
        ch_crop, cw_crop = cropped.shape[:2]
        if cw_crop > ch_crop:
            cropped = cv2.rotate(cropped, cv2.ROTATE_90_CLOCKWISE)
            logger.info(f"[ADAPTIVE] Rotated 90 CW: {cropped.shape[1]}x{cropped.shape[0]}")

        # Deskew: correct any remaining tilt so text lines are horizontal
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
            logger.warning(f"[ADAPTIVE] Deskew failed: {_de}")

        crop_path = image_path.replace(".jpg", "_cropped.jpg")'''

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    print("Deskew patch applied")
else:
    print("ERROR: target block not found")
    idx = content.find("# Auto-rotate if card is landscape")
    print(f"  Auto-rotate block at char: {idx}")
    sys.exit(1)

with open(SERVER, "w") as f:
    f.write(content)

print("Done")
