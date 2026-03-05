#!/usr/bin/env python3
"""
NEXUS Arm Teaching Tool
=======================
Record arm positions with camera frames for imitation learning.

Usage:
    python arm_teach.py

Commands:
    jog <servo> <+/->  - Move servo (0-4) by ±5 degrees
    set <servo> <deg>  - Set servo to specific angle
    save <name>        - Save current position + frame as demonstration
    list               - List saved demonstrations
    home               - Go to home position
    pickup             - Go to pickup preset
    view               - Open camera stream in browser
    vacuum on/off      - Toggle vacuum
    quit               - Exit

Patent Pending - Kevin Caracozza
"""

import json
import os
import webbrowser
from datetime import datetime

import requests

# Snarf server
SNARF_URL = "http://192.168.1.219:5001"
VISION_URL = "http://192.168.1.219:5001"

# Demo save location
DEMO_DIR = os.path.join(os.path.dirname(__file__), "demos")

# Servo names
SERVO_NAMES = ["base", "shoulder", "elbow", "wrist_roll", "wrist_pitch"]

# Presets
PRESETS = {
    "home": [90, 90, 90, 90, 90],
    "pickup": [90, 60, 120, 90, 60],
    "scan_pos": [90, 45, 135, 90, 45],
    "drop": [45, 90, 90, 90, 90],
}


def get_arm_position():
    """Get current arm servo angles"""
    try:
        r = requests.get(f"{SNARF_URL}/api/arm/position", timeout=2)
        if r.status_code == 200:
            data = r.json()
            return data.get("angles", [90]*5)[:5]  # First 5 are arm servos
    except Exception as e:
        print(f"Error getting position: {e}")
    return None


def set_arm_position(angles):
    """Set arm servo angles"""
    try:
        # Jog to position by setting each servo
        r = requests.post(
            f"{SNARF_URL}/api/arm/jog",
            json={"angles": angles},
            timeout=2
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Error setting position: {e}")
    return False


def jog_servo(servo_idx, delta):
    """Jog a single servo by delta degrees"""
    pos = get_arm_position()
    if pos is None:
        return False

    pos[servo_idx] = max(0, min(180, pos[servo_idx] + delta))
    return set_arm_position(pos)


def set_servo(servo_idx, angle):
    """Set a single servo to specific angle"""
    pos = get_arm_position()
    if pos is None:
        return False

    pos[servo_idx] = max(0, min(180, angle))
    return set_arm_position(pos)


def go_preset(name):
    """Move to preset position"""
    if name in PRESETS:
        return set_arm_position(PRESETS[name])
    print(f"Unknown preset: {name}")
    return False


def set_vacuum(on):
    """Control vacuum"""
    try:
        endpoint = "on" if on else "off"
        r = requests.post(f"{SNARF_URL}/api/vacuum/{endpoint}", timeout=2)
        return r.status_code == 200
    except Exception as e:
        print(f"Error setting vacuum: {e}")
    return False


def get_frame():
    """Capture frame from USB webcam via vision stream"""
    try:
        # Use vision API stream (port 5002) - USB webcam with card detection overlay
        r = requests.get(f"{VISION_URL}/api/vision/stream", stream=True, timeout=5)
        if r.status_code == 200:
            buffer = b""
            for chunk in r.iter_content(chunk_size=4096):
                buffer += chunk
                start = buffer.find(b'\xff\xd8')  # JPEG start
                end = buffer.find(b'\xff\xd9')    # JPEG end
                if start != -1 and end != -1 and end > start:
                    return buffer[start:end+2]
                if len(buffer) > 500000:  # Safety limit
                    break
    except Exception as e:
        print(f"Error getting frame: {e}")
    return None


def get_card_detection():
    """Get card detection from vision system"""
    try:
        r = requests.get(f"{VISION_URL}/api/vision/detection", timeout=2)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def save_demo(name):
    """Save demonstration: frame + arm position + optional card detection"""
    os.makedirs(DEMO_DIR, exist_ok=True)

    # Get current state
    pos = get_arm_position()
    if pos is None:
        print("Failed to get arm position")
        return False

    frame = get_frame()
    if frame is None:
        print("Failed to capture frame")
        return False

    card = get_card_detection()

    # Create demo record
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    demo_name = f"{name}_{timestamp}"

    # Save frame
    frame_path = os.path.join(DEMO_DIR, f"{demo_name}.jpg")
    with open(frame_path, "wb") as f:
        f.write(frame)

    # Save metadata
    meta = {
        "name": name,
        "timestamp": timestamp,
        "arm_angles": pos,
        "card_detection": card,
        "frame_file": f"{demo_name}.jpg"
    }

    meta_path = os.path.join(DEMO_DIR, f"{demo_name}.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved demo: {demo_name}")
    print(f"  Arm: {pos}")
    if card and card.get("detected"):
        print(f"  Card: X={card['x_mm']:.1f}mm Y={card['y_mm']:.1f}mm")

    return True


def list_demos():
    """List saved demonstrations"""
    if not os.path.exists(DEMO_DIR):
        print("No demos saved yet")
        return

    demos = [f for f in os.listdir(DEMO_DIR) if f.endswith(".json")]
    if not demos:
        print("No demos saved yet")
        return

    print(f"\nSaved demonstrations ({len(demos)}):")
    for demo_file in sorted(demos):
        meta_path = os.path.join(DEMO_DIR, demo_file)
        with open(meta_path) as f:
            meta = json.load(f)

        name = meta.get("name", "unknown")
        angles = meta.get("arm_angles", [])
        card = meta.get("card_detection", {})

        card_info = ""
        if card and card.get("detected"):
            card_info = f" | Card: ({card['x_mm']:.0f}, {card['y_mm']:.0f})"

        print(f"  {name}: {angles}{card_info}")


def open_stream():
    """Open USB webcam stream in browser (with card detection overlay)"""
    url = f"{VISION_URL}/api/vision/stream"
    print(f"Opening: {url}")
    webbrowser.open(url)


def print_status():
    """Print current arm status"""
    pos = get_arm_position()
    if pos:
        print("\nCurrent position:")
        for i, (name, angle) in enumerate(zip(SERVO_NAMES, pos)):
            print(f"  [{i}] {name:12}: {angle:3}°")
    else:
        print("Cannot read arm position")

    card = get_card_detection()
    if card and card.get("detected"):
        print(f"\nCard detected: X={card['x_mm']:.1f}mm Y={card['y_mm']:.1f}mm Angle={card['angle']:.1f}°")


def main():
    print("=" * 50)
    print("NEXUS Arm Teaching Tool")
    print("=" * 50)

    # Check connectivity
    try:
        r = requests.get(f"{SNARF_URL}/status", timeout=2)
        if r.status_code == 200:
            print(f"Connected to Snarf: {SNARF_URL}")
    except:
        print(f"WARNING: Cannot connect to Snarf at {SNARF_URL}")

    try:
        r = requests.get(f"{VISION_URL}/api/vision/detection", timeout=2)
        if r.status_code == 200:
            print(f"Connected to Vision: {VISION_URL}")
    except:
        print(f"WARNING: Vision system not available at {VISION_URL}")

    print_status()

    print("\nCommands:")
    print("  jog <0-4> <+/->   - Jog servo (e.g., 'jog 1 +' moves shoulder up)")
    print("  set <0-4> <deg>   - Set servo angle")
    print("  save <name>       - Save demo position")
    print("  list              - List saved demos")
    print("  home/pickup/scan  - Go to preset")
    print("  vacuum on/off     - Toggle vacuum")
    print("  view              - Open camera in browser")
    print("  status            - Show current state")
    print("  quit              - Exit")
    print()

    while True:
        try:
            cmd = input("> ").strip().lower()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0]

            if action == "quit" or action == "q":
                break

            elif action == "jog" and len(parts) >= 3:
                servo = int(parts[1])
                if servo < 0 or servo > 4:
                    print("Servo must be 0-4")
                    continue

                delta = 5 if "+" in parts[2] else -5
                if jog_servo(servo, delta):
                    pos = get_arm_position()
                    print(f"{SERVO_NAMES[servo]}: {pos[servo]}°")
                else:
                    print("Jog failed")

            elif action == "set" and len(parts) >= 3:
                servo = int(parts[1])
                angle = int(parts[2])
                if servo < 0 or servo > 4:
                    print("Servo must be 0-4")
                    continue

                if set_servo(servo, angle):
                    print(f"{SERVO_NAMES[servo]}: {angle}°")
                else:
                    print("Set failed")

            elif action == "save" and len(parts) >= 2:
                name = parts[1]
                save_demo(name)

            elif action == "list":
                list_demos()

            elif action in PRESETS:
                if go_preset(action):
                    print(f"Moved to {action}")
                else:
                    print("Move failed")

            elif action == "vacuum":
                on = len(parts) > 1 and parts[1] == "on"
                if set_vacuum(on):
                    print(f"Vacuum {'ON' if on else 'OFF'}")
                else:
                    print("Vacuum command failed")

            elif action == "view":
                open_stream()

            elif action == "status" or action == "s":
                print_status()

            else:
                print("Unknown command. Type 'quit' to exit.")

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")

    print("Goodbye!")


if __name__ == "__main__":
    main()
