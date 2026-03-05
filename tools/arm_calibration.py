#!/usr/bin/env python3
"""
NEXUS Robo V3 - Physical Coordinate Calibration Tool
=====================================================
Run this on SNARF (or locally with SSH tunnel) before the first real-world deployment.

Jog the arm manually to each of the 3 physical locations, then record:
  1. SCANNER  - where to pick up cards from the CZUR scanner bed
  2. LIGHTBOX - center of the photography light box
  3. SORT_BIN - where to drop sorted cards

Outputs: arm_calibration.json  (loaded automatically by arm_controller.py)

Usage:
  python arm_calibration.py [--esp32 http://192.168.1.218] [--dry-run]

Patent Pending - Kevin Caracozza
"""

import argparse
import json
import os
import sys
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("[WARN] requests not installed — running in dry-run / manual entry mode")

# ─── Default config ───────────────────────────────────────────────────────────
DEFAULT_ESP32       = "http://192.168.1.219:8218"  # DANIELSON serial bridge
DEFAULT_SNARF_PROXY = "http://192.168.1.219:5001"  # Fallback: DANIELSON main server

# ─── Narwhal relay telemetry ───────────────────────────────────────────────────
RELAY_URL    = "https://narwhal-council-relay.kcaracozza.workers.dev"
RELAY_HEADERS = {
    "CF-Access-Client-Id":     "6afc4a83861b2228b337c20f3fb216ad.access",
    "CF-Access-Client-Secret": "8e8c83f04c278cdf70c849b24256382b3c3215d6c23219605dc7f08147591a1d",
    "User-Agent":              "NEXUS-ARM-CAL/1.0",
}

def relay_push(node: str, joints: list, x: float, y: float, skipped=False):
    """Push calibration node telemetry to Narwhal relay → NICHOLAS sees it live."""
    if not HAS_REQUESTS:
        return
    msg = (
        f"[ARM-CAL] Node {node} {'SKIPPED' if skipped else 'RECORDED'} | "
        f"joints={joints} | XY≈({x:+.0f},{y:+.0f})mm"
    ) if not skipped else f"[ARM-CAL] Node {node} SKIPPED"
    payload = {
        "senderId":    "MENDEL",
        "recipientId": "NICHOLAS",
        "content":     msg,
    }
    try:
        requests.post(f"{RELAY_URL}/api/send_message",
                      json=payload, headers=RELAY_HEADERS, timeout=4)
    except Exception as e:
        print(f"  [WARN] Relay push failed: {e}")

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "src", "scanner", "snarf", "arm_calibration.json")

# Joint limits (must match arm_controller.py)
JOINT_LIMITS = {
    0: (0,   180),   # Base
    1: (30,  150),   # Shoulder  (hardware: -30°..+90° mapped to 30..150 servo)
    2: (30,  150),   # Elbow
    3: (0,   180),   # Wrist Roll
    4: (30,  150),   # Wrist Pitch
}
HOME_POSITION = [90, 90, 90, 90, 90]

# Arm segment lengths (mm) — update to match actual hardware
L1 = 80    # Base-to-shoulder
L2 = 100   # Shoulder-to-elbow
L3 = 100   # Elbow-to-wrist
L4 = 50    # Wrist-to-tip


# ─── FK: approximate XY from joint angles ─────────────────────────────────────
def forward_kinematics_xy(joints):
    """
    Rough 2D forward kinematics (ignores Z plane tilt).
    Returns (x_mm, y_mm) in arm base frame.
    """
    import math
    base_rad    = math.radians(joints[0] - 90)   # 90° = forward
    shoulder_rad = math.radians(joints[1] - 90)  # 90° = vertical
    elbow_rad    = math.radians(joints[2] - 90)

    # Horizontal reach of upper/lower arm
    reach = (L2 * math.cos(shoulder_rad) +
             L3 * math.cos(shoulder_rad + elbow_rad))

    x_mm = reach * math.cos(base_rad)
    y_mm = reach * math.sin(base_rad)
    return round(x_mm, 1), round(y_mm, 1)


# ─── ESP32 comms ──────────────────────────────────────────────────────────────
class ArmProxy:
    def __init__(self, url, dry_run=False):
        self.url     = url.rstrip("/")
        self.dry_run = dry_run
        self.joints  = HOME_POSITION.copy()

    def ping(self):
        if self.dry_run:
            return True
        try:
            r = requests.get(f"{self.url}/api/arm/status", timeout=2)
            return r.status_code == 200
        except Exception as e:
            print(f"  [ERROR] Cannot reach ESP32 at {self.url}: {e}")
            return False

    def get_joints(self):
        """Fetch current joint angles from ESP32"""
        if self.dry_run:
            return self.joints[:]
        try:
            r = requests.get(f"{self.url}/api/arm/status", timeout=2)
            if r.status_code == 200:
                data = r.json()
                self.joints = data.get("joints", self.joints)
                return self.joints[:]
        except Exception as e:
            print(f"  [WARN] Could not fetch joints: {e}")
        return self.joints[:]

    def move_joints(self, joints):
        """Send joint angles to ESP32"""
        clamped = [
            max(JOINT_LIMITS[i][0], min(JOINT_LIMITS[i][1], v))
            for i, v in enumerate(joints)
        ]
        if self.dry_run:
            self.joints = clamped
            print(f"  [DRY-RUN] move → {clamped}")
            return True
        try:
            r = requests.post(
                f"{self.url}/api/arm/move",
                json={"joints": clamped},
                timeout=3
            )
            if r.status_code == 200:
                self.joints = clamped
                return True
        except Exception as e:
            print(f"  [ERROR] Move failed: {e}")
        return False

    def set_vacuum(self, on: bool):
        if self.dry_run:
            print(f"  [DRY-RUN] vacuum={'ON' if on else 'OFF'}")
            return
        try:
            requests.post(f"{self.url}/api/arm/vacuum", json={"on": on}, timeout=2)
        except Exception:
            pass


# ─── Interactive jogging ───────────────────────────────────────────────────────
JOG_STEP = {
    "small":  2.0,
    "medium": 5.0,
    "large": 15.0,
}

JOG_HELP = """
  Joint jog  : 0+ 0- 1+ 1- 2+ 2- 3+ 3- 4+ 4- (joint# + direction)
  Step size  : ss / sm / sl  (small=2° / medium=5° / large=15°)
  Home       : home
  Status     : st
  Vacuum     : von / voff
  Record pos : record
  Skip pos   : skip
  Quit       : quit
"""


def jog_session(arm: ArmProxy, location_name: str):
    """
    Interactive session to jog arm to a physical location.
    Returns recorded joint angles, or None if skipped.
    """
    print(f"\n{'='*60}")
    print(f"  CALIBRATING: {location_name}")
    print(f"{'='*60}")
    print(f"  Jog the arm to the correct position, then type 'record'.")
    print(JOG_HELP)

    step_mode = "medium"
    joints = arm.get_joints()

    while True:
        # Show current state
        x, y = forward_kinematics_xy(joints)
        print(f"\r  Joints: [{', '.join(f'{j:6.1f}' for j in joints)}]  "
              f"≈ XY=({x:+.0f}mm, {y:+.0f}mm)  step={step_mode}  ", end="")

        try:
            cmd = input("\n  > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return None

        if not cmd:
            continue

        # Step size
        if cmd == "ss":
            step_mode = "small";  continue
        if cmd == "sm":
            step_mode = "medium"; continue
        if cmd == "sl":
            step_mode = "large";  continue

        # Home
        if cmd == "home":
            joints = HOME_POSITION.copy()
            arm.move_joints(joints)
            continue

        # Status
        if cmd == "st":
            joints = arm.get_joints()
            x, y = forward_kinematics_xy(joints)
            print(f"  Joints  : {joints}")
            print(f"  FK ~XY  : ({x:+.1f}mm, {y:+.1f}mm)")
            continue

        # Vacuum
        if cmd == "von":
            arm.set_vacuum(True);  continue
        if cmd == "voff":
            arm.set_vacuum(False); continue

        # Record
        if cmd == "record":
            joints = arm.get_joints()
            x, y = forward_kinematics_xy(joints)
            print(f"\n  ✓  Recorded {location_name}")
            print(f"     Joints : {joints}")
            print(f"     FK ~XY : ({x:+.1f}mm, {y:+.1f}mm)")
            return joints[:]

        # Skip
        if cmd == "skip":
            print(f"\n  --  Skipping {location_name}  --")
            return None

        if cmd == "quit":
            print("\n  Quit without saving.")
            sys.exit(0)

        # Joint jog: e.g. "0+" or "2-"
        if len(cmd) == 2 and cmd[0].isdigit() and cmd[1] in ("+", "-"):
            idx = int(cmd[0])
            if 0 <= idx <= 4:
                delta = JOG_STEP[step_mode] * (1 if cmd[1] == "+" else -1)
                joints[idx] = max(JOINT_LIMITS[idx][0],
                                  min(JOINT_LIMITS[idx][1], joints[idx] + delta))
                arm.move_joints(joints)
                continue

        print("  [?] Unknown command — type 'help' or see legend above.")


# ─── Manual coordinate entry (fallback) ───────────────────────────────────────
def manual_entry(location_name: str):
    """Prompt user to type in joint angles directly."""
    print(f"\n  Manual entry for {location_name}")
    print("  Enter 5 joint angles (deg) separated by spaces:")
    print("  [base  shoulder  elbow  wrist_roll  wrist_pitch]")
    while True:
        raw = input("  > ").strip()
        if not raw or raw.lower() == "skip":
            return None
        parts = raw.split()
        if len(parts) == 5:
            try:
                return [float(p) for p in parts]
            except ValueError:
                pass
        print("  Need exactly 5 numbers, e.g.: 90 75 110 90 90")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="NEXUS Arm Calibration Tool")
    parser.add_argument("--esp32",    default=DEFAULT_ESP32,
                        help=f"ESP32 URL (default: {DEFAULT_ESP32})")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Simulate without sending commands to ESP32")
    parser.add_argument("--output",   default=OUTPUT_FILE,
                        help="Output JSON file path")
    args = parser.parse_args()

    dry_run = args.dry_run or not HAS_REQUESTS

    print("\n" + "="*60)
    print("  NEXUS Robo V3 — Physical Coordinate Calibration")
    print("="*60)
    print(f"  ESP32     : {args.esp32}")
    print(f"  Output    : {args.output}")
    print(f"  Dry-run   : {dry_run}")

    arm = ArmProxy(args.esp32, dry_run=dry_run)

    # Ping
    if not dry_run:
        print(f"\n  Connecting to ESP32 at {args.esp32}...")
        if not arm.ping():
            print(f"  [WARN] Cannot reach {args.esp32}, trying SNARF proxy {DEFAULT_SNARF_PROXY}...")
            arm = ArmProxy(DEFAULT_SNARF_PROXY, dry_run=False)
            if not arm.ping():
                print("  [ERROR] No ESP32 reachable. Use --dry-run for manual entry mode.")
                print("          Re-run with --dry-run to enter coordinates manually.")
                choice = input("  Continue in manual entry mode? [y/N]: ").strip().lower()
                if choice != "y":
                    sys.exit(1)
                dry_run = True
                arm = ArmProxy(args.esp32, dry_run=True)
        else:
            print(f"  Connected!")

    # ── Calibrate 3 locations ──────────────────────────────────────────────
    locations = [
        ("SCANNER",  "Scanner pickup zone — position gripper over center of CZUR scan bed"),
        ("LIGHTBOX", "Light box center — position gripper over center of photography light box"),
        ("SORT_BIN", "Sort bin — position gripper over the card drop zone"),
    ]

    results = {}

    for key, description in locations:
        print(f"\n  NEXT: {description}")
        input("  Press ENTER when ready to jog...")

        if dry_run:
            joints = manual_entry(key)
        else:
            joints = jog_session(arm, key)

        if joints is not None:
            x, y = forward_kinematics_xy(joints)
            results[key] = {
                "joints":  joints,
                "approx_x_mm": x,
                "approx_y_mm": y,
            }
            print(f"  ✓  {key} saved — XY≈({x:+.0f}mm, {y:+.0f}mm)")
            relay_push(key, joints, x, y)
        else:
            print(f"  --  {key} skipped")
            relay_push(key, [], 0, 0, skipped=True)

    if not results:
        print("\n  No positions recorded. Nothing saved.")
        sys.exit(0)

    # ── Home arm ──────────────────────────────────────────────────────────
    print("\n  Returning arm to HOME position...")
    arm.set_vacuum(False)
    arm.move_joints(HOME_POSITION)
    time.sleep(1)
    print("  Done.")

    # ── Write JSON ────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    cal = {
        "calibration_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "esp32_url":        args.esp32,
        "locations":        results,
        "notes": (
            "Positions recorded on real hardware via arm_calibration.py. "
            "Load via arm_controller.py load_calibration()."
        )
    }
    with open(args.output, "w") as f:
        json.dump(cal, f, indent=2)

    print(f"\n  ✓  Calibration saved to: {args.output}")

    # ── Print summary & patch instructions ───────────────────────────────
    print("\n" + "="*60)
    print("  CALIBRATION SUMMARY")
    print("="*60)
    for key, data in results.items():
        print(f"  {key:10s}: joints={data['joints']}  XY≈({data['approx_x_mm']:+.0f}, {data['approx_y_mm']:+.0f})mm")

    print("\n  To apply in arm_controller.py:")
    if "LIGHTBOX" in results:
        lb = results["LIGHTBOX"]
        print(f"    lightbox_x = {lb['approx_x_mm']}, lightbox_y = {lb['approx_y_mm']}")
    if "SORT_BIN" in results:
        sb = results["SORT_BIN"]
        print(f"    bin_x      = {sb['approx_x_mm']}, bin_y      = {sb['approx_y_mm']}")
    if "SCANNER" in results:
        sc = results["SCANNER"]
        print(f"    (scanner pickup uses vision XY — record as reference/Z-height only)")
        print(f"    scanner_joints = {sc['joints']}")

    print("\n  OR arm_controller.py will auto-load arm_calibration.json if you add:")
    print("    controller.load_calibration('arm_calibration.json')")
    print("="*60)


if __name__ == "__main__":
    main()
