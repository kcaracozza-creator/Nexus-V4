#!/usr/bin/env python3
"""
NEXUS Robo V3 - Nacon Gamepad Arm Controller
==============================================
Runs on SNARF. Reads Nacon (or any evdev gamepad) and drives the ARM
via the serial bridge at http://localhost:8218.

Button / Axis Mapping (Nacon / DualShock layout):
  Left  Stick  X  →  Joint 0 (Base rotate)
  Left  Stick  Y  →  Joint 1 (Shoulder)
  Right Stick  Y  →  Joint 2 (Elbow)
  Right Stick  X  →  Joint 3 (Wrist Roll)
  D-Pad Up/Down   →  Joint 4 (Wrist Pitch)
  R2 (hold)       →  Vacuum ON
  L2 (hold)       →  Vacuum OFF
  Triangle / Y    →  Home position
  Square   / X    →  Record current position → push to relay
  Circle   / B    →  Skip current position
  Start           →  Save calibration JSON & exit
  Select          →  Print status

Usage:
  python3 arm_gamepad_controller.py [--bridge http://localhost:8218] [--output arm_calibration.json]

Patent Pending - Kevin Caracozza
"""

import argparse
import json
import math
import os
import sys
import time

try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
except ImportError:
    print("[FATAL] evdev not installed. Run: pip3 install evdev --break-system-packages")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[FATAL] requests not installed. Run: pip3 install requests --break-system-packages")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────
RELAY_URL    = "https://narwhal-council-relay.kcaracozza.workers.dev"
RELAY_HEADERS = {
    "CF-Access-Client-Id":     "6afc4a83861b2228b337c20f3fb216ad.access",
    "CF-Access-Client-Secret": "8e8c83f04c278cdf70c849b24256382b3c3215d6c23219605dc7f08147591a1d",
    "User-Agent":              "NEXUS-ARM-PAD/1.0",
}

JOINT_LIMITS = {
    0: (0,   180),   # Base
    1: (30,  150),   # Shoulder
    2: (30,  150),   # Elbow
    3: (0,   180),   # Wrist Roll
    4: (30,  150),   # Wrist Pitch
}
HOME = [90, 90, 90, 90, 90]

DEADZONE   = 0.12    # Ignore stick input below this fraction
JOG_RATE   = 3.0     # Degrees per 0.05s loop at full stick deflection
POLL_MS    = 50      # Loop period in ms

# evdev axis codes (standard Linux gamepad)
ABS_LX  = ecodes.ABS_X
ABS_LY  = ecodes.ABS_Y
ABS_RX  = ecodes.ABS_RX if hasattr(ecodes, 'ABS_RX') else ecodes.ABS_Z
ABS_RY  = ecodes.ABS_RY if hasattr(ecodes, 'ABS_RY') else ecodes.ABS_RZ
ABS_HAT_X = ecodes.ABS_HAT0X
ABS_HAT_Y = ecodes.ABS_HAT0Y

# Button codes (may vary — run `evtest` to check your Nacon)
BTN_TRIANGLE = ecodes.BTN_Y       # Home
BTN_SQUARE   = ecodes.BTN_X       # Record
BTN_CIRCLE   = ecodes.BTN_B       # Skip
BTN_CROSS    = ecodes.BTN_A       # unused
BTN_R2       = ecodes.BTN_TR2 if hasattr(ecodes, 'BTN_TR2') else ecodes.BTN_TR
BTN_L2       = ecodes.BTN_TL2 if hasattr(ecodes, 'BTN_TL2') else ecodes.BTN_TL
BTN_START    = ecodes.BTN_START
BTN_SELECT   = ecodes.BTN_SELECT


def find_gamepad():
    """Auto-detect first gamepad device."""
    for path in evdev.list_devices():
        dev = InputDevice(path)
        caps = dev.capabilities()
        if ecodes.EV_ABS in caps and ecodes.EV_KEY in caps:
            print(f"  Found gamepad: {dev.name} ({path})")
            return dev
    return None


def clamp_joint(idx, val):
    lo, hi = JOINT_LIMITS[idx]
    return max(lo, min(hi, val))


def axis_to_delta(raw, axis_info, deadzone=DEADZONE):
    """Normalise raw axis value to [-1, 1] with deadzone."""
    mn = axis_info.min
    mx = axis_info.max
    mid = (mx + mn) / 2
    rng = (mx - mn) / 2
    norm = (raw - mid) / rng if rng else 0
    if abs(norm) < deadzone:
        return 0.0
    return norm


def relay_status(msg):
    try:
        requests.post(f"{RELAY_URL}/api/send_message",
                      json={"senderId": "MENDEL", "recipientId": "NICHOLAS", "content": msg},
                      headers=RELAY_HEADERS, timeout=3)
    except Exception:
        pass


class ArmClient:
    def __init__(self, bridge_url):
        self.url    = bridge_url.rstrip("/")
        self.joints = HOME[:]

    def move(self, joints):
        try:
            r = requests.post(f"{self.url}/api/arm/move",
                              json={"joints": joints}, timeout=2)
            if r.status_code == 200:
                self.joints = joints[:]
                return True
        except Exception as e:
            print(f"  [move error] {e}")
        return False

    def vacuum(self, on):
        try:
            requests.post(f"{self.url}/api/arm/vacuum",
                          json={"on": on}, timeout=2)
        except Exception:
            pass

    def home(self):
        self.move(HOME[:])
        self.joints = HOME[:]


def main():
    parser = argparse.ArgumentParser(description="NEXUS Nacon Arm Controller")
    parser.add_argument("--bridge",  default="http://localhost:8218")
    parser.add_argument("--output",  default="/home/nexus1/arm/src/scanner/snarf/arm_calibration.json")
    args = parser.parse_args()

    print("\n  NEXUS Robo V3 — Nacon Gamepad Controller")
    print("  Bridge :", args.bridge)
    print("  Output :", args.output)
    print()
    print("  Controls:")
    print("    L-Stick   → Base + Shoulder")
    print("    R-Stick   → Elbow + Wrist Roll")
    print("    D-Pad U/D → Wrist Pitch")
    print("    Triangle  → HOME")
    print("    Square    → RECORD position")
    print("    Circle    → SKIP position")
    print("    R2/L2     → Vacuum ON/OFF")
    print("    Start     → SAVE & EXIT")
    print()

    dev = find_gamepad()
    if not dev:
        print("[FATAL] No gamepad found. Connect Nacon and retry.")
        sys.exit(1)

    arm    = ArmClient(args.bridge)
    joints = HOME[:]
    arm.move(joints)

    caps    = dev.capabilities(absinfo=True)
    abs_map = {info[0]: info[1] for info in caps.get(ecodes.EV_ABS, [])}

    results       = {}
    locations     = ["SCANNER", "LIGHTBOX", "SORT_BIN"]
    loc_idx       = 0
    btn_state     = {}
    hat_state     = {ABS_HAT_X: 0, ABS_HAT_Y: 0}
    last_send     = 0

    print(f"  Current target: {locations[loc_idx]}")
    relay_status(f"[ARM-PAD] Gamepad connected. Calibrating {locations[loc_idx]}.")

    try:
        for event in dev.read_loop():
            now = time.time()

            # ── Button events ──────────────────────────────────────────────
            if event.type == ecodes.EV_KEY:
                btn = event.code
                val = event.value   # 1=down, 0=up

                if val == 1:  # button pressed

                    if btn == BTN_TRIANGLE:
                        joints = HOME[:]
                        arm.home()
                        print("  HOME")

                    elif btn == BTN_SQUARE:
                        # Record current node
                        if loc_idx < len(locations):
                            key = locations[loc_idx]
                            from arm_calibration import forward_kinematics_xy
                            x, y = forward_kinematics_xy(joints)
                            results[key] = {"joints": joints[:], "approx_x_mm": x, "approx_y_mm": y}
                            msg = f"[ARM-CAL] {key} RECORDED joints={joints} XY≈({x:+.0f},{y:+.0f})mm"
                            print(f"  ✓ {msg}")
                            relay_status(msg)
                            loc_idx += 1
                            if loc_idx < len(locations):
                                print(f"  Next: {locations[loc_idx]}")
                                relay_status(f"[ARM-PAD] Next target: {locations[loc_idx]}")
                            else:
                                print("  All positions recorded. Press START to save.")

                    elif btn == BTN_CIRCLE:
                        if loc_idx < len(locations):
                            key = locations[loc_idx]
                            relay_status(f"[ARM-CAL] {key} SKIPPED")
                            print(f"  Skipped {key}")
                            loc_idx += 1
                            if loc_idx < len(locations):
                                print(f"  Next: {locations[loc_idx]}")

                    elif btn == BTN_R2:
                        arm.vacuum(True)
                        print("  Vacuum ON")

                    elif btn == BTN_L2:
                        arm.vacuum(False)
                        print("  Vacuum OFF")

                    elif btn == BTN_SELECT:
                        print(f"  Joints: {joints}")

                    elif btn == BTN_START:
                        # Save and exit
                        if results:
                            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
                            cal = {
                                "calibration_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "source": "nacon_gamepad",
                                "locations": results,
                            }
                            with open(args.output, "w") as f:
                                json.dump(cal, f, indent=2)
                            print(f"  ✓ Saved: {args.output}")
                            relay_status(f"[ARM-CAL] COMPLETE. Saved {len(results)} nodes to {args.output}")
                        else:
                            print("  Nothing recorded.")
                        arm.vacuum(False)
                        arm.home()
                        break

            # ── Hat / D-pad ────────────────────────────────────────────────
            elif event.type == ecodes.EV_ABS and event.code in (ABS_HAT_X, ABS_HAT_Y):
                hat_state[event.code] = event.value

            # ── Continuous axis jogging (rate-limited send) ────────────────
            if now - last_send >= POLL_MS / 1000.0:
                last_send = now
                dirty = False

                for code, joint_idx in [
                    (ABS_LX, 0), (ABS_LY, 1),
                    (ABS_RY, 2), (ABS_RX, 3),
                ]:
                    if code in abs_map and event.type == ecodes.EV_ABS and event.code == code:
                        delta = axis_to_delta(event.value, abs_map[code])
                        if delta:
                            joints[joint_idx] = clamp_joint(joint_idx, joints[joint_idx] + delta * JOG_RATE)
                            dirty = True

                # D-pad → wrist pitch
                hat_y = hat_state.get(ABS_HAT_Y, 0)
                if hat_y != 0:
                    joints[4] = clamp_joint(4, joints[4] - hat_y * JOG_RATE)
                    dirty = True

                if dirty:
                    arm.move([round(j, 1) for j in joints])

    except KeyboardInterrupt:
        pass

    print("  Exiting gamepad controller.")
    arm.vacuum(False)
    arm.home()


if __name__ == "__main__":
    main()
