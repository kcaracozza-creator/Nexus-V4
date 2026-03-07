#!/usr/bin/env python3
"""Arducam 48MP v4l2 settings manager — OCR-optimized configuration."""
import subprocess

def manage_arducam(video_device="/dev/video0"):
    print(f"--- Querying {video_device} Current Settings ---")

    try:
        controls = subprocess.check_output(["v4l2-ctl", "-d", video_device, "-l"]).decode()
        print(controls)
    except Exception as e:
        print(f"Error accessing camera: {e}")
        return

    print("\n--- Applying OCR-Optimized Settings ---")
    commands = [
        "focus_auto=0",
        "sharpness=50",
        "focus_absolute=400"
    ]

    for cmd in commands:
        subprocess.run(["v4l2-ctl", "-d", video_device, "-c", cmd])

    print("Settings updated. Re-test OCR now.")

if __name__ == "__main__":
    manage_arducam("/dev/video0")
