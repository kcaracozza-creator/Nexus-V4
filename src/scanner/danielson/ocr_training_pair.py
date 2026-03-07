#!/usr/bin/env python3
"""
Single OCR training pair generator — domain randomization for Tesseract fine-tuning.
Simulates Arducam sensor conditions: blur, noise, glare, skew, red-channel binarization.
"""
import cv2
import numpy as np
import random


def generate_ocr_training_pair(scryfall_img, card_name):
    """Generate an augmented binarized name-bar crop paired with ground truth text."""
    h, w = scryfall_img.shape[:2]

    # 1. Pipeline Mirroring: Crop the exact Name Bar ROI
    y1, y2 = int(h * 0.04), int(h * 0.12)
    x1, x2 = int(w * 0.07), int(w * 0.78)
    name_bar = scryfall_img[y1:y2, x1:x2]

    # 2. Domain Randomization (The "Real World" Junk)
    # Simulate the "47.9 Sharpness" Luxknight blur
    blur_k = random.choice([3, 5, 7])
    name_bar = cv2.GaussianBlur(name_bar, (blur_k, blur_k), 0)

    # Simulate Gold Frame/Artifact bleed (Value/Brightness shifts)
    brightness = random.uniform(0.7, 1.3)
    name_bar = cv2.convertScaleAbs(name_bar, alpha=brightness, beta=0)

    # 3. The Red-Channel Binarization (The Secret Sauce)
    red_channel = name_bar[:, :, 2]
    _, binary = cv2.threshold(red_channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 4. Perspective/Rotation Skew (The Orientation Fix Stress-Test)
    rows, cols = binary.shape
    M = cv2.getRotationMatrix2D((cols / 2, rows / 2), random.uniform(-2, 2), 1)
    binary = cv2.warpAffine(binary, M, (cols, rows), borderMode=cv2.BORDER_REPLICATE)

    return binary, card_name
