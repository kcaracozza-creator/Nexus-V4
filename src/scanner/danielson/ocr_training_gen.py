#!/usr/bin/env python3
"""
NEXUS OCR Training Data Generator — Produces augmented ground-truth pairs
for Tesseract 5.x fine-tuning from Scryfall card images.
"""
import os
import cv2
import sqlite3
import numpy as np
import random
import argparse
import functools
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm


class NexusOCRGen:
    def __init__(self, db_path, out_dir):
        self.db = sqlite3.connect(db_path)
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        # Standard MTG Name Bar ROI (Normalized % of card)
        self.ROI = {'y1': 0.045, 'y2': 0.11, 'x1': 0.07, 'x2': 0.93}

    def _add_noise(self, img):
        """Simulates Arducam sensor noise (Salt & Pepper)."""
        prob = random.uniform(0.001, 0.005)
        thres = 1 - prob
        for i in range(img.shape[0]):
            for j in range(img.shape[1]):
                rdn = random.random()
                if rdn < prob:
                    img[i][j] = 0
                elif rdn > thres:
                    img[i][j] = 255
        return img

    def _apply_glare(self, img):
        """Simulates a radial LED hotspot that erases character edges."""
        h, w = img.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        cx, cy = random.randint(0, w), random.randint(0, h)
        cv2.circle(mask, (cx, cy), random.randint(30, 80), 255, -1)
        mask = cv2.GaussianBlur(mask, (71, 71), 0)
        glare = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        return cv2.addWeighted(img, 1.0, glare, random.uniform(0.5, 0.9), 0)

    def _binarize_pipeline(self, img):
        """Exact mirror of the DANIELSON production binarization."""
        # 4x Upscale for Tesseract 5.0 stability
        img = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        # Red-channel isolation
        red = img[:, :, 2]
        # CLAHE contrast stretch (Silver Wall fix)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(red)
        # Otsu binarization
        _, binary = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def _process_card(self, card_row):
        """Worker function for parallel processing."""
        name, img_path = card_row
        img = cv2.imread(img_path)
        if img is None:
            return

        h, w = img.shape[:2]
        crop = img[int(h * self.ROI['y1']):int(h * self.ROI['y2']),
                    int(w * self.ROI['x1']):int(w * self.ROI['x2'])]

        for i in range(4):  # 4 variants per card
            aug = crop.copy()

            # Sharpness 47.9 / Blur simulation
            if i > 0:
                k = random.choice([3, 5, 7])
                aug = cv2.GaussianBlur(aug, (k, k), 0)

            # Noise injection (Sensor Grain)
            if i == 1:
                aug = self._add_noise(aug)

            # Glare Hotspot (Foil simulation)
            if i == 2:
                aug = self._apply_glare(aug)

            # Perspective Warp / Rotation Jitter
            if i == 3:
                rows, cols = aug.shape[:2]
                pts1 = np.float32([[0, 0], [cols, 0], [0, rows], [cols, rows]])
                shift = rows * 0.05
                pts2 = pts1 + np.float32(
                    [[random.uniform(-shift, shift), random.uniform(-shift, shift)] for _ in range(4)]
                )
                M = cv2.getPerspectiveTransform(pts1, pts2)
                aug = cv2.warpPerspective(aug, M, (cols, rows), borderMode=cv2.BORDER_REPLICATE)

            final = self._binarize_pipeline(aug)

            safe_name = "".join([c for c in name if c.isalnum() or c == ' ']).rstrip()
            file_id = f"nexus_{safe_name.replace(' ', '_')}_var{i}"
            cv2.imwrite(os.path.join(self.out_dir, f"{file_id}.tif"), final)
            with open(os.path.join(self.out_dir, f"{file_id}.gt.txt"), "w", encoding="utf-8") as f:
                f.write(name)

    def generate(self, count=5000, hard_mode=False):
        query = "SELECT name, image_path FROM cards"
        if hard_mode:
            query += " WHERE name LIKE '%l%' OR name LIKE '%i%' OR name LIKE '%t%' OR name LIKE '%''%'"

        cards = self.db.execute(query + f" LIMIT {count}").fetchall()

        with ProcessPoolExecutor() as executor:
            func = functools.partial(self._process_card)
            list(tqdm(executor.map(func, cards), total=len(cards), desc="Blasting MTG Training Data"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to nexus_cards.db")
    parser.add_argument("--out", required=True, help="Output ground-truth directory")
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--hard-mode", action="store_true")
    args = parser.parse_args()

    gen = NexusOCRGen(args.db, args.out)
    gen.generate(count=args.count, hard_mode=args.hard_mode)
