#!/usr/bin/env python3
"""NEXUS OCR Training Data Generator

Generates Tesseract-compatible training pairs (.tif + .gt.txt) from Scryfall
card images using the exact same binarization pipeline as danielson_server.py.

Usage:
    python ocr_training_gen.py --db /path/to/nexus_cards.db --out ./train_data --count 5000
    python ocr_training_gen.py --db /path/to/nexus_cards.db --out ./train_data --hard-mode

Runs on ZULTAN (has the DB + network access to Scryfall).
"""

import argparse
import cv2
import numpy as np
import os
import random
import requests
import sqlite3
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from typing import Tuple, Optional, List

# ── MTG Name Region (matches danielson_server.py CARD_PROFILES) ──────────
# (y1_pct, y2_pct, x1_pct, x2_pct) of card image
MTG_NAME_REGION = (0.07, 0.12, 0.04, 0.78)

# ── Augmentation parameters ──────────────────────────────────────────────
AUG_BLUR_KERNELS = [1, 3, 5, 7]          # Gaussian blur (1=none)
AUG_BRIGHTNESS = (0.6, 1.4)               # Scale factor range
AUG_ROTATION_DEG = (-3, 3)                # Slight tilt
AUG_GLARE_PROB = 0.3                       # 30% chance of glare hotspot
AUG_GLARE_INTENSITY = (0.3, 0.8)          # Glare opacity range
AUG_NOISE_PROB = 0.2                       # 20% chance of salt-pepper noise
AUG_PERSPECTIVE_PROB = 0.25               # 25% chance of perspective warp
AUG_CONTRAST_STRETCH_PROB = 0.35          # 35% chance of CLAHE contrast stretch
AUG_SHADOW_PROB = 0.15                    # 15% chance of arm shadow strip
AUG_VARIANTS_PER_CARD = 4                 # How many augmented versions per name

# Scryfall rate limit: 75ms between requests
SCRYFALL_DELAY = 0.08


def crop_name_region(img: np.ndarray,
                     region: Tuple[float, float, float, float] = MTG_NAME_REGION,
                     min_height: int = 40) -> np.ndarray:
    """Crop the name bar from a card image using fractional coordinates."""
    h, w = img.shape[:2]
    y1 = int(h * region[0])
    y2 = int(h * region[1])
    x1 = int(w * region[2])
    x2 = int(w * region[3])
    crop = img[y1:y2, x1:x2]
    if crop.shape[0] < min_height:
        # Upscale if too small
        scale = min_height / max(crop.shape[0], 1)
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return crop


def binarize_red_channel(img: np.ndarray) -> np.ndarray:
    """Red-channel binarization — exact match to danielson_server._binarize().

    Red channel + THRESH_BINARY (no invert) handles MTG colored frames:
    - Orange/gold bg → high R → white
    - Dark text → low R → black
    """
    if len(img.shape) == 2:
        gray = img
    else:
        _, _, r_ch = cv2.split(img)
        gray = r_ch

    # Upscale 4x for better OCR (matches pipeline)
    up = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    _, bw = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Adaptive fallback if too many connected components (textured bg)
    n_labels, _ = cv2.connectedComponents(cv2.bitwise_not(bw))
    if n_labels > 50:
        bw = cv2.adaptiveThreshold(up, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 10)
    return bw


def add_glare_hotspot(img: np.ndarray,
                      intensity: float = 0.5,
                      radius_frac: float = 0.3) -> np.ndarray:
    """Simulate a circular glare hotspot on the name bar.

    Mimics lightbox reflection hitting glossy card surface.
    """
    h, w = img.shape[:2]
    # Random center position (biased toward center-right where glare typically hits)
    cx = random.randint(int(w * 0.3), int(w * 0.9))
    cy = random.randint(int(h * 0.2), int(h * 0.8))
    radius = int(min(h, w) * radius_frac * random.uniform(0.5, 1.5))

    # Create white elliptical hotspot
    glare = np.zeros_like(img)
    axes = (radius, int(radius * random.uniform(0.4, 1.0)))
    angle = random.uniform(0, 180)
    cv2.ellipse(glare, (cx, cy), axes, angle, 0, 360, (255, 255, 255) if len(img.shape) == 3 else 255, -1)

    # Gaussian blur the glare for soft edges
    glare = cv2.GaussianBlur(glare, (31, 31), 15)

    # Blend
    result = cv2.addWeighted(img, 1.0, glare, intensity, 0)
    return result


def add_salt_pepper_noise(img: np.ndarray, amount: float = 0.01) -> np.ndarray:
    """Add salt-and-pepper noise to simulate sensor artifacts."""
    noisy = img.copy()
    # Salt
    n_salt = int(amount * img.size)
    coords = [np.random.randint(0, max(i - 1, 1), n_salt) for i in img.shape[:2]]
    noisy[coords[0], coords[1]] = 255
    # Pepper
    coords = [np.random.randint(0, max(i - 1, 1), n_salt) for i in img.shape[:2]]
    noisy[coords[0], coords[1]] = 0
    return noisy


def add_perspective_warp(img: np.ndarray, max_shift: float = 0.05) -> np.ndarray:
    """Slight perspective warp to simulate non-flat card/camera angle."""
    h, w = img.shape[:2]
    s = max_shift
    # Random corner shifts
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([
        [random.uniform(0, w * s), random.uniform(0, h * s)],
        [w - random.uniform(0, w * s), random.uniform(0, h * s)],
        [w - random.uniform(0, w * s), h - random.uniform(0, h * s)],
        [random.uniform(0, w * s), h - random.uniform(0, h * s)],
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def augment_name_crop(crop: np.ndarray) -> np.ndarray:
    """Apply domain randomization to a name bar crop BEFORE binarization.

    This simulates real-world conditions the camera produces:
    - Focus blur (sharpness 17-100 range)
    - Brightness variation (lightbox inconsistency)
    - Glare hotspots (glossy/foil cards)
    - Slight rotation (card not perfectly aligned)
    - Perspective warp (card curl or camera angle)
    - Sensor noise
    - CLAHE contrast stretch on red channel (silver/artifact frame text separation)
    - Arm shadow strip (simulates robotic arm shadow during fast scans)
    """
    aug = crop.copy()

    # 1. Blur (simulates defocus — the #1 OCR killer)
    k = random.choice(AUG_BLUR_KERNELS)
    if k > 1:
        aug = cv2.GaussianBlur(aug, (k, k), 0)

    # 2. Brightness shift (lightbox variation)
    brightness = random.uniform(*AUG_BRIGHTNESS)
    aug = cv2.convertScaleAbs(aug, alpha=brightness, beta=random.randint(-20, 20))

    # 3. Glare hotspot
    if random.random() < AUG_GLARE_PROB:
        intensity = random.uniform(*AUG_GLARE_INTENSITY)
        aug = add_glare_hotspot(aug, intensity=intensity)

    # 4. Salt-pepper noise
    if random.random() < AUG_NOISE_PROB:
        aug = add_salt_pepper_noise(aug, amount=random.uniform(0.005, 0.02))

    # 5. Slight rotation
    angle = random.uniform(*AUG_ROTATION_DEG)
    if abs(angle) > 0.5:
        h, w = aug.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        aug = cv2.warpAffine(aug, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    # 6. Perspective warp
    if random.random() < AUG_PERSPECTIVE_PROB:
        aug = add_perspective_warp(aug)

    # 7. CLAHE contrast stretch on RED channel (the binarization target)
    # Fixes silver/artifact frames where Otsu sees a "gray blob" and deletes text.
    # CLAHE works in local tiles so glare hotspots don't blow out the threshold.
    if random.random() < AUG_CONTRAST_STRETCH_PROB:
        clip = random.uniform(1.5, 4.0)
        grid = random.choice([4, 8])
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
        aug[:, :, 2] = clahe.apply(aug[:, :, 2])  # Red channel = index 2 in BGR

    # 8. Shadow cast (simulates arm shadow clipping name bar during fast moves)
    if random.random() < AUG_SHADOW_PROB:
        sh, sw = aug.shape[:2]
        shadow = np.ones((sh, sw), dtype=np.float32)
        # Diagonal shadow strip across name bar
        x_start = random.randint(0, int(sw * 0.6))
        x_width = random.randint(int(sw * 0.15), int(sw * 0.4))
        skew = random.uniform(-0.3, 0.3)
        for row in range(sh):
            frac = row / max(sh - 1, 1)
            x0 = int(x_start + skew * sw * frac)
            x1 = min(x0 + x_width, sw)
            x0 = max(x0, 0)
            shadow[row, x0:x1] = random.uniform(0.3, 0.7)
        shadow = cv2.GaussianBlur(shadow, (15, 15), 5)
        for c in range(3):
            aug[:, :, c] = (aug[:, :, c].astype(np.float32) * shadow).astype(np.uint8)

    return aug


def render_name_bar(name: str, width: int = 425, height: int = 40,
                    font_scale: float = 0.9) -> np.ndarray:
    """Render a card name as a synthetic name bar image.

    Produces a white background with dark text that mimics the MTG name bar
    appearance BEFORE binarization. This avoids Scryfall language issues
    and is instant (no API calls).
    """
    # Create white background with slight off-white variation (like real card stock)
    bg_val = random.randint(220, 245)
    img = np.full((height, width, 3), bg_val, dtype=np.uint8)

    # Add subtle frame-colored tint (simulates MTG frame colors)
    tint = random.choice([
        (bg_val, bg_val, bg_val),            # White frame
        (bg_val, bg_val - 15, bg_val - 30),  # Gold/orange frame (high red)
        (bg_val - 20, bg_val, bg_val - 10),  # Green frame
        (bg_val - 10, bg_val - 10, bg_val),  # Blue frame
        (bg_val - 5, bg_val - 15, bg_val),   # Black frame
        (bg_val - 25, bg_val - 15, bg_val),  # Red frame
    ])
    img[:, :] = tint

    # Dark text (near-black, slight variation)
    text_val = random.randint(10, 45)
    text_color = (text_val, text_val, text_val)

    # Use FONT_HERSHEY_SIMPLEX as base (closest to Beleren in OpenCV built-ins)
    font = random.choice([cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX])
    thickness = random.choice([1, 2])

    # Calculate text size and position
    (tw, th), baseline = cv2.getTextSize(name, font, font_scale, thickness)
    # If text is too wide, scale down
    if tw > width - 20:
        font_scale = font_scale * (width - 20) / tw
        (tw, th), baseline = cv2.getTextSize(name, font, font_scale, thickness)

    x = random.randint(5, max(10, width - tw - 10))
    y = int(height / 2 + th / 2)

    cv2.putText(img, name, (x, y), font, font_scale, text_color, thickness, cv2.LINE_AA)

    # Add thin border line at bottom (common on MTG name bars)
    if random.random() > 0.3:
        cv2.line(img, (0, height - 2), (width, height - 2),
                 (text_val + 20, text_val + 20, text_val + 20), 1)

    return img


def download_scryfall_image(url: str, retries: int = 2) -> Optional[np.ndarray]:
    """Download a card image from Scryfall API."""
    for attempt in range(retries + 1):
        try:
            # Scryfall image API — use 'normal' size (488x680)
            img_url = url.replace('?format=image', '?format=image&version=normal')
            resp = requests.get(img_url, timeout=10)
            if resp.status_code == 200:
                arr = np.frombuffer(resp.content, np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                return img
            elif resp.status_code == 429:
                time.sleep(1)  # rate limited, back off
        except Exception:
            pass
        time.sleep(SCRYFALL_DELAY)
    return None


def fetch_training_cards(db_path: str, count: int = 5000,
                         hard_mode: bool = False) -> List[dict]:
    """Pull card names + image URLs from bridge table.

    hard_mode: prioritize names with vertical stems, apostrophes,
    short names, and other OCR-hostile patterns.
    """
    conn = sqlite3.connect(db_path)

    # Deduplicate by oracle_id to get one unique English name per card concept
    # This avoids non-English printings polluting training data
    if hard_mode:
        hard_count = int(count * 0.4)
        easy_count = count - hard_count

        hard_query = """
            SELECT name, image_url, oracle_id FROM cards
            WHERE image_url IS NOT NULL AND image_url != ''
            AND name NOT LIKE '%//%'
            AND (
                name LIKE '%ll%' OR name LIKE '%tt%' OR name LIKE '%ff%'
                OR name LIKE '%ii%' OR name LIKE '%''%' OR name LIKE '%-%'
                OR LENGTH(name) <= 6 OR LENGTH(name) >= 25
                OR name LIKE '%,_%' ESCAPE '\\'
            )
            GROUP BY oracle_id
            ORDER BY RANDOM() LIMIT ?
        """
        hard_cards = conn.execute(hard_query, (hard_count,)).fetchall()

        easy_query = """
            SELECT name, image_url, oracle_id FROM cards
            WHERE image_url IS NOT NULL AND image_url != ''
            AND name NOT LIKE '%//%'
            GROUP BY oracle_id
            ORDER BY RANDOM() LIMIT ?
        """
        easy_cards = conn.execute(easy_query, (easy_count,)).fetchall()
        cards = hard_cards + easy_cards
    else:
        query = """
            SELECT name, image_url, oracle_id FROM cards
            WHERE image_url IS NOT NULL AND image_url != ''
            AND name NOT LIKE '%//%'
            GROUP BY oracle_id
            ORDER BY RANDOM() LIMIT ?
        """
        cards = conn.execute(query, (count,)).fetchall()

    conn.close()
    random.shuffle(cards)
    return [{'name': c[0], 'image_url': c[1]} for c in cards]


def _process_card_worker(args: tuple) -> Tuple[int, int]:
    """Worker function for ProcessPoolExecutor — generates variants for one card.

    Returns (success_count, failed_count).
    """
    card_name, image_url, index, output_dir, variants, use_scryfall = args

    name = card_name
    # Skip double-faced names
    if ' // ' in name:
        name = name.split(' // ')[0]
    if not name or len(name) < 2:
        return (0, 1)

    if use_scryfall:
        img = download_scryfall_image(image_url)
        if img is None:
            return (0, 1)
        crop = crop_name_region(img)
        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 20:
            return (0, 1)
    else:
        crop = render_name_bar(name)

    out = Path(output_dir)
    ok = 0
    for v in range(variants):
        if v == 0:
            aug = crop.copy()
        else:
            if not use_scryfall:
                crop = render_name_bar(name)
            aug = augment_name_crop(crop)

        bw = binarize_red_channel(aug)

        # Strip all Windows-illegal filename chars: " < > | ? * : / \ and others
        safe_name = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in name).strip('_')
        fname = f"{safe_name}_{index:05d}_v{v}"

        cv2.imwrite(str(out / f"{fname}.tif"), bw)
        with open(out / f"{fname}.gt.txt", 'w', encoding='utf-8') as f:
            f.write(name)
        ok += 1

    return (ok, 0)


def generate_training_data(db_path: str, output_dir: str, count: int = 5000,
                           hard_mode: bool = False, variants: int = AUG_VARIANTS_PER_CARD,
                           use_scryfall: bool = False, workers: int = 0):
    """Main generator: pull cards, render/download, augment, binarize, save.

    Default mode (render): Renders card names using OpenCV text rendering.
      - Instant (no API calls), guaranteed English, 100% label accuracy.
      - Produces augmented binarized name bars matching production pipeline.

    Scryfall mode (--scryfall): Downloads actual card images from Scryfall.
      - Slower (rate limited), may include non-English printings.
      - More realistic frame colors and font rendering.

    workers: Number of parallel processes (0 = auto = cpu_count).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    n_workers = workers or cpu_count()
    mode = "scryfall" if use_scryfall else "render"
    print(f"[GEN] Mode: {mode}")
    print(f"[GEN] Workers: {n_workers} (i9 cores)")
    print(f"[GEN] Fetching {count} cards from {db_path} (hard_mode={hard_mode})")
    cards = fetch_training_cards(db_path, count, hard_mode)
    print(f"[GEN] Got {len(cards)} unique cards, generating {variants} variants each")
    print(f"[GEN] Output: {out.absolute()}")
    print(f"[GEN] Expected pairs: ~{len(cards) * variants}")

    t0 = time.time()

    # Build work items
    work = [
        (card['name'], card.get('image_url', ''), i, str(out), variants, use_scryfall)
        for i, card in enumerate(cards)
    ]

    if use_scryfall:
        # Scryfall mode: sequential (rate limited, 75ms between requests)
        success = 0
        failed = 0
        for i, item in enumerate(work):
            ok, bad = _process_card_worker(item)
            success += ok
            failed += bad
            if (i + 1) % 500 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (len(work) - i - 1) / max(rate, 0.1)
                print(f"[GEN] {i + 1}/{len(work)} cards "
                      f"({success} pairs, {failed} failed, "
                      f"{rate:.1f} cards/s, ETA: {eta:.0f}s)")
            time.sleep(SCRYFALL_DELAY)
    else:
        # Render mode: FULL BLAST with ProcessPoolExecutor
        success = 0
        failed = 0
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_process_card_worker, item): i
                       for i, item in enumerate(work)}
            done = 0
            for future in as_completed(futures):
                ok, bad = future.result()
                success += ok
                failed += bad
                done += 1
                if done % 1000 == 0:
                    elapsed = time.time() - t0
                    rate = done / max(elapsed, 0.001)
                    eta = (len(work) - done) / max(rate, 0.1)
                    print(f"[GEN] {done}/{len(work)} cards "
                          f"({success} pairs, {failed} failed, "
                          f"{rate:.0f} cards/s, ETA: {eta:.0f}s)")

    elapsed = time.time() - t0
    print(f"\n[GEN] DONE: {success} training pairs in {output_dir} ({elapsed:.1f}s)")
    print(f"[GEN] Speed: {success / max(elapsed, 0.001):.0f} pairs/s across {n_workers} cores")
    print(f"[GEN] Failed: {failed}")
    print(f"[GEN] Next: run tesstrain to fine-tune Tesseract")
    print(f"[GEN]   make training MODEL_NAME=nexus_mtg START_MODEL=eng \\")
    print(f"[GEN]     TESSDATA=/usr/share/tesseract-ocr/5/tessdata \\")
    print(f"[GEN]     GROUND_TRUTH_DIR={out.absolute()}")

    return success


def main():
    parser = argparse.ArgumentParser(description='NEXUS OCR Training Data Generator')
    parser.add_argument('--db', required=True, help='Path to nexus_cards.db')
    parser.add_argument('--out', default='./ocr_train_data', help='Output directory')
    parser.add_argument('--count', type=int, default=5000, help='Number of unique cards')
    parser.add_argument('--variants', type=int, default=4, help='Augmented variants per card')
    parser.add_argument('--hard-mode', action='store_true',
                        help='Prioritize OCR-hostile names (vertical stems, apostrophes, etc)')
    parser.add_argument('--scryfall', action='store_true',
                        help='Download real Scryfall images instead of rendering (slower)')
    parser.add_argument('--workers', type=int, default=0,
                        help='Number of parallel processes (0 = auto = all cores)')
    args = parser.parse_args()

    generate_training_data(
        db_path=args.db,
        output_dir=args.out,
        count=args.count,
        hard_mode=args.hard_mode,
        variants=args.variants,
        use_scryfall=args.scryfall,
        workers=args.workers,
    )


if __name__ == '__main__':
    main()
