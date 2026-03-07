#!/usr/bin/env python3
"""Camera hang recovery — kills holders, resets USB bus, restores golden settings."""
import subprocess
import time

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

def restore_camera_hardware(device="/dev/video0"):
    for cmd in GOLDEN_SETTINGS:
        subprocess.run(["v4l2-ctl", "-d", device, "-c", cmd], capture_output=True)

def reset_camera(device="/dev/video0"):
    print("--- Camera Hang Detected. Initiating Recovery... ---")
    # 1. Force kill any process holding the camera
    subprocess.run(["sudo", "fuser", "-k", device])

    # 2. Reset the USB bus
    lsusb_out = subprocess.check_output(["lsusb"]).decode()
    for line in lsusb_out.split('\n'):
        if "Arducam" in line:
            parts = line.split()
            bus, dev = parts[1], parts[3].strip(':')
            subprocess.run(["sudo", "usbreset", f"/dev/bus/usb/{bus}/{dev}"])
            break

    time.sleep(2)
    restore_camera_hardware(device)
    print("Recovery complete.")

if __name__ == "__main__":
    reset_camera()
