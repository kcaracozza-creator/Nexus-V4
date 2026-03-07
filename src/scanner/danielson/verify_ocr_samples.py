#!/usr/bin/env python3
"""Verify generated OCR training samples — displays .tif + ground truth for QA."""
import os
import cv2
import random
import glob


def verify_samples(data_dir, num_samples=5):
    tifs = glob.glob(os.path.join(data_dir, "*.tif"))

    if not tifs:
        print(f"No .tif files found in {data_dir}. Check your generation path.")
        return

    samples = random.sample(tifs, min(num_samples, len(tifs)))

    print(f"\n--- Verifying {len(samples)} Samples ---")
    for tif_path in samples:
        img = cv2.imread(tif_path)

        gt_path = tif_path.replace(".tif", ".gt.txt")
        with open(gt_path, 'r', encoding='utf-8') as f:
            label = f.read().strip()

        print(f"File: {os.path.basename(tif_path)}")
        print(f"Ground Truth: '{label}'")

        display_img = cv2.resize(img, (800, 100)) if img.shape[1] > 800 else img
        cv2.imshow("Nexus OCR Verification", display_img)

        key = cv2.waitKey(0)
        if key == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    verify_samples("./ocr_train_data")
