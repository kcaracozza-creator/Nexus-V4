#!/usr/bin/env python3
"""
NEXUS Vision Pipeline — Capture, OCR, CLAHE, Consensus Gate.
Full scan pipeline for card recognition on the scanner station.
"""
import cv2
import numpy as np
import subprocess
import os
import time
import sqlite3
import atexit
from dataclasses import dataclass


# --- CONFIGURATION & ROIs ---
@dataclass
class Config:
    DEVICE = "/dev/video0"
    DB_PATH = "./nexus_cards.db"
    # ROI: [y1, y2, x1, x2] as percentages
    NAME_ROI = [0.045, 0.11, 0.07, 0.93]
    MANA_ROI = [0.030, 0.09, 0.75, 0.96]
    CONFIDENCE_THRESHOLD = 0.92
    CONSENSUS_BONUS = 0.05


GOLDEN_SETTINGS = [
    "auto_exposure=1",
    "exposure_time_absolute=150",
    "gain=800",
    "brightness=30",
    "contrast=50",
    "saturation=50",
    "focus_absolute=580",
    "white_balance_automatic=1",
]


# --- HARDWARE & V4L2 RECOVERY ---
def restore_camera_hardware():
    """Forces the Arducam into the 'Luxknight' tuned state."""
    print("--- Blasting Arducam Hardware Reset ---")
    for cmd in GOLDEN_SETTINGS:
        subprocess.run(["v4l2-ctl", "-d", Config.DEVICE, "-c", cmd], capture_output=True)


def get_v4l2_capture():
    """Opens Arducam using the explicit YUYV V4L2 backend."""
    cap = cv2.VideoCapture(Config.DEVICE, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap


# --- CORE VISION PIPELINE ---
def process_ocr_region(frame):
    """The Red-Channel Binarization + CLAHE + 4x Upscale Pipeline."""
    h, w = frame.shape[:2]
    y1, y2, x1, x2 = [int(v * h if i < 2 else v * w) for i, v in enumerate(Config.NAME_ROI)]
    crop = frame[y1:y2, x1:x2]

    # 1. 4x Upscale for Tesseract 5.5
    upscaled = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

    # 2. Red-Channel Isolation (The 'Slime' Fix)
    red = upscaled[:, :, 2]

    # 3. Digital Gain (compensate missing brightness)
    red = cv2.multiply(red, np.array([1.2], dtype=np.float64))
    red = np.clip(red, 0, 255).astype(np.uint8)

    # 4. CLAHE (The 'Silver Wall' Fix)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(red)

    # 5. Morphology Close (The 'Slime' Thickener)
    kernel = np.ones((2, 2), np.uint8)
    morphed = cv2.morphologyEx(contrast, cv2.MORPH_CLOSE, kernel)

    # 6. Otsu Binarization
    _, binary = cv2.threshold(morphed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def booth_killer_crop(frame):
    """Central 800x500 crop — deletes white diffusion walls."""
    h, w = frame.shape[:2]
    cy, cx = h // 2, w // 2
    return frame[cy - 250:cy + 250, cx - 400:cx + 400]


# --- 3-SIGNAL CONSENSUS GATE ---
def evaluate_consensus(ocr_name, faiss_name, color_signal, oracle_signal):
    """The Triad of Truth: Blocks 'Cities' and 'Skerries'."""
    score = 0
    signals = []

    if ocr_name.lower() == faiss_name.lower():
        score += 0.90 + Config.CONSENSUS_BONUS
        signals.append("CONVERGENCE")

    if color_signal:
        score += 0.05
        signals.append("COLOR")

    if oracle_signal:
        score += 0.05
        signals.append("ORACLE")

    success = score >= Config.CONFIDENCE_THRESHOLD and len(signals) >= 2
    return success, score, signals


# --- MAIN EXECUTION LOOP ---
def run_nexus_scan():
    restore_camera_hardware()
    cap = get_v4l2_capture()

    @atexit.register
    def cleanup():
        cap.release()
        print("--- Camera Handle Released Gracefully ---")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("USB Hang Detected. Resetting...")
            break

        # Booth killer crop
        frame = booth_killer_crop(frame)

        # Prepare OCR crop
        ocr_ready = process_ocr_region(frame)

        print(f"Frame Processed. Brightness: {np.mean(frame):.1f}")

        cv2.imshow("Nexus Direct YUYV Stream", ocr_ready)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


if __name__ == "__main__":
    run_nexus_scan()
