#!/usr/bin/env python3
"""Camera health monitor — detects hardware desync and restores golden config."""
import subprocess

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

def restore_camera_settings(device="/dev/video0"):
    for cmd in GOLDEN_SETTINGS:
        subprocess.run(["v4l2-ctl", "-d", device, "-c", cmd], capture_output=True)

def check_camera_health(device="/dev/video0"):
    result = subprocess.check_output(["v4l2-ctl", "-d", device, "-C", "brightness"]).decode().strip()
    current_brightness = int(result.split(":")[-1].strip())
    print(f"Current brightness: {current_brightness}")
    if current_brightness < 20:
        restore_camera_settings(device)
        print("Hardware desync detected. Restored Golden Config.")
    else:
        print("Camera health OK.")

if __name__ == "__main__":
    check_camera_health()
