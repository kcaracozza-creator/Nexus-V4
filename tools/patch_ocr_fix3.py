#!/usr/bin/env python3
"""
Patch 3: Fix run_ocr to:
1. Invert dark-background name regions (MTG card dark frame)
2. Use PSM 6 on text box only (lower 45% of card), not full card with art
3. Always upscale name region to at least 120px height
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

# ─────────────────────────────────────────────────────────────
# Replace the region-based OCR + full-card OCR section
# Find the block starting at "# --- REGION-BASED OCR"
# ─────────────────────────────────────────────────────────────

old_section = '''        # --- REGION-BASED OCR: crop specific card areas ---
        # MTG card layout (portrait, standard frame):
        #   Name:     top 3-8% height, 7-75% width
        #   Type:     ~57-63% height, 7-75% width
        #   Set/Num:  bottom 93-98% height
        # Multiple crop candidates per region (cards vary slightly in border size)
        region_candidates = {
            'name': [
                (int(h*0.03), int(h*0.08), int(w*0.07), int(w*0.70)),
                (int(h*0.02), int(h*0.10), int(w*0.05), int(w*0.75)),
                (int(h*0.04), int(h*0.09), int(w*0.08), int(w*0.72)),
            ],
            'type': [
                (int(h*0.56), int(h*0.62), int(w*0.07), int(w*0.75)),
                (int(h*0.55), int(h*0.63), int(w*0.05), int(w*0.80)),
                (int(h*0.565), int(h*0.625), int(w*0.07), int(w*0.75)),
            ],
            'set_num': [
                (int(h*0.92), int(h*0.98), int(w*0.05), int(w*0.95)),
                (int(h*0.90), int(h*0.99), int(w*0.03), int(w*0.97)),
            ],
        }

        results = {}
        for region_name, candidates in region_candidates.items():
            best_text = ''
            best_conf = 0
            for (y1, y2, x1, x2) in candidates:
                crop = img[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                # Scale up small regions for better OCR
                min_h = 60
                if crop.shape[0] < min_h:
                    scale = min_h / crop.shape[0]
                    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

                # Run OCR on raw color crop — thresholding hurts more than it helps
                config = r'--oem 3 --psm 7'
                text = pytesseract.image_to_string(crop, config=config).strip()
                data = pytesseract.image_to_data(crop, config=config, output_type=pytesseract.Output.DICT)
                confs = [int(c) for c in data['conf'] if int(c) > 0]
                avg_conf = sum(confs) / len(confs) if confs else 0

                # Keep the best result across candidates
                if avg_conf > best_conf and len(text) > len(best_text):
                    best_text = text
                    best_conf = avg_conf
                elif not best_text and text:
                    best_text = text
                    best_conf = avg_conf

                # If we got a good result, no need to try more candidates
                if avg_conf > 70 and len(text) >= 3:
                    break

            results[region_name] = {'text': best_text, 'confidence': round(best_conf, 1)}

        # Full-card OCR: run directly on the raw BGR image (no threshold — kills accuracy)
        # tesseract handles the image internally; extra preprocessing hurts more than helps
        full_text = pytesseract.image_to_string(img, config=r'--oem 3 --psm 6')
        full_data = pytesseract.image_to_data(img, config=r'--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
        full_confs = [int(c) for c in full_data['conf'] if int(c) > 0]
        full_avg = sum(full_confs) / len(full_confs) if full_confs else 0'''

new_section = '''        # --- REGION-BASED OCR: crop specific card areas ---
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
        full_text_combined = full_text + '\n' + sparse_text'''

if old_section in content:
    content = content.replace(old_section, new_section, 1)
    print("Fix applied: run_ocr dark-frame inversion + text-box-only PSM 6 + sparse PSM 11")
else:
    print("ERROR: target section not found")
    # Try to identify where it starts
    idx = content.find("# --- REGION-BASED OCR: crop specific card areas ---")
    print(f"  Section start found at char {idx}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Also update the references to full_text to use full_text_combined
# ─────────────────────────────────────────────────────────────

# The line that picks the name from full text should use full_text_combined
old_fulltext_ref = '''        # Pick card name: prefer region crop if confidence > 50, else search full text
        name_result = results.get('name', {})
        card_name = ''
        name_conf = 0
        if isinstance(name_result, dict) and name_result.get('confidence', 0) > 50:
            card_name = name_result['text']
            name_conf = name_result['confidence']
        else:
            # Search all lines from full-card OCR for best card name candidate
            # A card name is: 2-40 chars, mostly alphabetic, appears in top portion of output
            lines = [l.strip() for l in full_text.split('\\n') if l.strip()]'''

new_fulltext_ref = '''        # Pick card name: prefer region crop if confidence > 50, else search full text
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

if old_fulltext_ref in content:
    content = content.replace(old_fulltext_ref, new_fulltext_ref, 1)
    print("Fix 2: full_text_combined used for name line search")
else:
    print("WARNING: full_text reference not found, skipping")

# Update set_text extraction to use full_text_combined
old_set_ref = "        all_text = set_text + '\\n' + full_text"
new_set_ref = "        all_text = set_text + '\\n' + full_text_combined"

if old_set_ref in content:
    content = content.replace(old_set_ref, new_set_ref, 1)
    print("Fix 3: set text extraction uses full_text_combined")

# Update the return value to expose full_text (combined)
old_return = "            'full_text': full_text,"
new_return = "            'full_text': full_text_combined,"

if old_return in content:
    content = content.replace(old_return, new_return, 1)
    print("Fix 4: return full_text_combined as full_text")

with open(SERVER, "w") as f:
    f.write(content)

print("All OCR fixes applied successfully")
