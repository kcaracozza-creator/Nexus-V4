#!/usr/bin/env python3
"""
OCR Debug Tool for DANIELSON
Saves debug images and shows exactly what Tesseract sees.

Usage:
    python ocr_debug.py /path/to/card_image.jpg
"""
import sys
import os
import cv2
import numpy as np

try:
    import pytesseract
except ImportError:
    print("ERROR: pytesseract not installed")
    sys.exit(1)

# MTG name region from CARD_PROFILES
NAME_REGION = (0.02, 0.10, 0.04, 0.78)  # y1, y2, x1, x2

def _binarize(gray: np.ndarray) -> np.ndarray:
    """Otsu binarize - same as danielson_server.py"""
    mean = gray.mean()
    if mean < 128:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bw


def debug_ocr(image_path: str):
    """Debug OCR on the name region of a card image."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Cannot read {image_path}")
        return
    
    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}")
    
    # Crop name region
    y1, y2, x1, x2 = NAME_REGION
    crop_y1, crop_y2 = int(h * y1), int(h * y2)
    crop_x1, crop_x2 = int(w * x1), int(w * x2)
    
    print(f"\nName region: y={crop_y1}:{crop_y2}, x={crop_x1}:{crop_x2}")
    print(f"Crop size: {crop_x2 - crop_x1}x{crop_y2 - crop_y1}")
    
    crop = img[crop_y1:crop_y2, crop_x1:crop_x2]
    if crop.size == 0:
        print("ERROR: Empty crop!")
        return
    
    # Save raw crop
    base = os.path.splitext(image_path)[0]
    debug_dir = os.path.dirname(image_path) or '.'
    
    cv2.imwrite(f"{debug_dir}/debug_1_crop_raw.jpg", crop)
    print(f"Saved: debug_1_crop_raw.jpg")
    
    # Upscale to 110px height (same as _crop_region min_height)
    ch = crop.shape[0]
    if ch < 110:
        scale = 110 / ch
        crop_upscaled = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        print(f"Upscaled {scale:.2f}x → {crop_upscaled.shape[1]}x{crop_upscaled.shape[0]}")
    else:
        crop_upscaled = crop
    
    cv2.imwrite(f"{debug_dir}/debug_2_crop_upscaled.jpg", crop_upscaled)
    print(f"Saved: debug_2_crop_upscaled.jpg")
    
    # Grayscale
    gray = cv2.cvtColor(crop_upscaled, cv2.COLOR_BGR2GRAY)
    print(f"Gray mean brightness: {gray.mean():.1f}")
    cv2.imwrite(f"{debug_dir}/debug_3_gray.jpg", gray)
    print(f"Saved: debug_3_gray.jpg")
    
    # Binarize
    bw = _binarize(gray)
    cv2.imwrite(f"{debug_dir}/debug_4_binarized.jpg", bw)
    print(f"Saved: debug_4_binarized.jpg")
    
    # Check binarization quality
    white_pct = (bw > 200).sum() / bw.size * 100
    black_pct = (bw < 50).sum() / bw.size * 100
    print(f"Binarization: {white_pct:.1f}% white, {black_pct:.1f}% black")
    
    # Run Tesseract with PSM 7 (single line)
    print("\n" + "="*60)
    print("OCR Results (PSM 7 - single line)")
    print("="*60)
    
    cfg = '--oem 3 --psm 7'
    text = pytesseract.image_to_string(bw, config=cfg).strip()
    data = pytesseract.image_to_data(bw, config=cfg, output_type=pytesseract.Output.DICT)
    
    print(f"\nimage_to_string result: {repr(text)}")
    
    # Show ALL boxes from image_to_data
    print(f"\nimage_to_data returned {len(data['text'])} boxes:")
    print("-" * 60)
    
    for i in range(len(data['text'])):
        txt = data['text'][i]
        conf = int(data['conf'][i])
        x, y, w_box, h_box = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
        
        # Show box regardless of text content
        marker = "✓" if txt.strip() else "✗"
        print(f"  [{i}] {marker} text={repr(txt):20s} conf={conf:3d}  box=({x},{y}) {w_box}x{h_box}")
    
    # Old confidence calc (buggy)
    old_confs = [int(c) for c in data['conf'] if int(c) > 0]
    old_avg = sum(old_confs) / len(old_confs) if old_confs else 0.0
    
    # Fixed confidence calc - only count boxes WITH text
    words_with_text = [
        (data['text'][i], int(data['conf'][i]))
        for i in range(len(data['text']))
        if data['text'][i].strip() and int(data['conf'][i]) > 0
    ]
    new_text = ' '.join(w[0] for w in words_with_text)
    new_avg = sum(w[1] for w in words_with_text) / len(words_with_text) if words_with_text else 0.0
    
    print("-" * 60)
    print(f"\nOLD CALC (buggy):  text={repr(text):20s}  conf={old_avg:.1f}%")
    print(f"NEW CALC (fixed):  text={repr(new_text):20s}  conf={new_avg:.1f}%")
    
    # Try alternative PSM modes
    print("\n" + "="*60)
    print("Trying alternative PSM modes...")
    print("="*60)
    
    for psm, desc in [(6, "block of text"), (8, "single word"), (11, "sparse text"), (13, "raw line")]:
        try:
            result = pytesseract.image_to_string(bw, config=f'--oem 3 --psm {psm}').strip()
            print(f"  PSM {psm} ({desc:15s}): {repr(result)}")
        except Exception as e:
            print(f"  PSM {psm}: ERROR - {e}")
    
    # Try on grayscale instead of binarized
    print("\n" + "="*60)
    print("Trying on GRAYSCALE (no binarization)...")
    print("="*60)
    
    for psm in [7, 6, 8]:
        try:
            result = pytesseract.image_to_string(gray, config=f'--oem 3 --psm {psm}').strip()
            print(f"  PSM {psm}: {repr(result)}")
        except Exception as e:
            print(f"  PSM {psm}: ERROR - {e}")
    
    # Try on raw color (no grayscale, no binarize)
    print("\n" + "="*60)
    print("Trying on RAW COLOR...")
    print("="*60)
    
    for psm in [7, 6, 8]:
        try:
            result = pytesseract.image_to_string(crop_upscaled, config=f'--oem 3 --psm {psm}').strip()
            print(f"  PSM {psm}: {repr(result)}")
        except Exception as e:
            print(f"  PSM {psm}: ERROR - {e}")
    
    # Draw boxes on crop for visualization
    debug_boxes = crop_upscaled.copy()
    for i in range(len(data['text'])):
        x, y, w_box, h_box = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
        if int(data['conf'][i]) > 0:
            color = (0, 255, 0) if data['text'][i].strip() else (0, 0, 255)
            cv2.rectangle(debug_boxes, (x, y), (x + w_box, y + h_box), color, 1)
    cv2.imwrite(f"{debug_dir}/debug_5_boxes.jpg", debug_boxes)
    print(f"\nSaved: debug_5_boxes.jpg (green=text, red=empty)")
    
    print("\n" + "="*60)
    print("DIAGNOSIS")
    print("="*60)
    
    if not text and old_avg > 50:
        print("⚠️  BUG CONFIRMED: Empty text but high confidence!")
        print("    Tesseract detected noise boxes but no actual words.")
        print("    The confidence calculation was counting empty-text boxes.")
    
    if white_pct > 95:
        print("⚠️  Binarization issue: Almost entirely white!")
        print("    Text might have been thresholded away.")
    
    if white_pct < 5:
        print("⚠️  Binarization issue: Almost entirely black!")
        print("    Background might have been thresholded wrong.")
    
    if 30 < white_pct < 70:
        print("✓  Binarization looks reasonable.")
    
    print("\nDebug images saved to:", debug_dir)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python ocr_debug.py /path/to/card_image.jpg")
        sys.exit(1)
    
    debug_ocr(sys.argv[1])
