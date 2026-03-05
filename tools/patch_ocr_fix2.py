#!/usr/bin/env python3
"""
Patch 2: Fix soverlap >= 2 bug and add OCR word count tracking in adaptive_capture.
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

# ─────────────────────────────────────────────────────────────
# Fix 1: soverlap >= 2 → soverlap >= 1 with word-in-name check
# ─────────────────────────────────────────────────────────────
old1 = '                        if soverlap >= 2:'
new1 = '                        if soverlap >= 1 and sword.lower() in sname.lower():'

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("Fix 1 applied: soverlap >= 2 → >= 1 with word-in-name check")
else:
    print("ERROR: Fix 1 target not found")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Fix 2: Add OCR word count tracking in adaptive_capture
# In the adaptive_capture function, add best_ocr_words = 0 and
# replace sharpness-only tracking with OCR-word-count tracking
# ─────────────────────────────────────────────────────────────

# Find "best_sharpness = 0" in adaptive_capture (line ~1889) — there are 2 occurrences,
# we want the second one (in adaptive_capture, not in the other function around line 976).
# Replace the entire multi-frame tracking block.

old2 = '''    best_frame = None
    best_path = None
    best_sharpness = 0

    for attempt in range(1, max_attempts + 1):'''

new2 = '''    best_frame = None
    best_path = None
    best_sharpness = 0
    best_ocr_words = 0

    for attempt in range(1, max_attempts + 1):'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("Fix 2a applied: added best_ocr_words = 0")
else:
    print("ERROR: Fix 2a target not found")
    sys.exit(1)

# Replace the best-frame tracking and early-return logic
# Old: tracks only sharpness, returns on quality.passed
# New: also tracks OCR word count, returns early on good OCR
old3 = '''        quality = assess_image_quality(cropped)
        logger.info(f"[ADAPTIVE] Attempt {attempt}: sharpness={quality['sharpness_val']}, "
                     f"brightness={quality['mean_brightness']}, glare={quality['glare_pct']}%%, "
                     f"passed={quality['passed']}")

        if quality['sharpness_val'] > best_sharpness:
            best_sharpness = quality['sharpness_val']
            best_frame = cropped
            best_path = image_path

        if quality['passed']:
            logger.info(f"[ADAPTIVE] Quality passed on attempt {attempt}")
            return {
                "image_path": image_path,
                "quality": quality,
                "attempts": attempt,
            }

        logger.info("[ADAPTIVE] Waiting for CZUR to settle...")
        time.sleep(3.0)'''

new3 = '''        quality = assess_image_quality(cropped)
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
        time.sleep(3.0)'''

if old3 in content:
    content = content.replace(old3, new3, 1)
    print("Fix 2b applied: OCR word count tracking in adaptive_capture")
else:
    print("ERROR: Fix 2b target not found")
    sys.exit(1)

with open(SERVER, "w") as f:
    f.write(content)

print("All patches applied successfully")
