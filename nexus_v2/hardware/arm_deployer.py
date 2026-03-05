#!/usr/bin/env python3
"""
NEXUS Arm Deployer - Waypoint Controller
=========================================
Talks directly to ESP32 v4.1 firmware over serial.
JSON commands, no binary packets, no RL model needed.

Run on DANIELSON (192.168.1.219) or any machine with USB to ESP32.

Usage:
  python arm_deployer.py                # Interactive menu
  python arm_deployer.py --calibrate    # Calibrate waypoints
  python arm_deployer.py --sort         # Run sort cycle
  python arm_deployer.py --test         # Test all positions
  python arm_deployer.py --home         # Just go home

Hardware (ESP32 v4.1 PCA9685) — VERIFIED 2/27/2026:
  CMD CH 1 → Shoulder servo (MG995)     PCA CH0
  CMD CH 2 → Card Rotate servo (MG90)   PCA CH1  ← was labeled "elbow"
  CMD CH 3 → Wrist Tilt servo (MG90)    PCA CH2
  CMD CH 4 → Elbow servo (MG995)        PCA CH3  ← was labeled "wrist 2"
  CMD CH 5 → Vacuum pump relay          PCA CH4
  CMD CH 6 → Solenoid release relay     PCA CH5
  GPIO 32  → Base stepper PUL+
  GPIO 33  → Base stepper DIR+

Patent Pending - Kevin Caracozza
"""

import json
import time
import sys
import os
from pathlib import Path

# ── Serial setup ─────────────────────────────────────────────────────────────
try:
    import serial
    import serial.tools.list_ports
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False
    print("pyserial not installed. Run: pip install pyserial")

# ── Config ───────────────────────────────────────────────────────────────────
BAUD = 115200
WAYPOINT_FILE = Path(__file__).parent / "arm_waypoints.json"

# Default waypoints — servo angles (0-180, 90=center) + base step position
# These get overwritten when you calibrate. DON'T hand-edit, use --calibrate.
DEFAULT_WAYPOINTS = {
    "home": {
        "base_steps": 0,
        "shoulder": 90, "card_rotate": 90, "wrist_tilt": 90, "elbow": 90,
        "note": "Safe resting position, all centered"
    },
    "above_intake": {
        "base_steps": 0,
        "shoulder": 70, "card_rotate": 90, "wrist_tilt": 90, "elbow": 120,
        "note": "Hovering above card intake area"
    },
    "intake_grab": {
        "base_steps": 0,
        "shoulder": 85, "card_rotate": 90, "wrist_tilt": 90, "elbow": 130,
        "note": "Lowered onto card for vacuum pickup"
    },
    "above_lightbox": {
        "base_steps": 300,
        "shoulder": 65, "card_rotate": 90, "wrist_tilt": 90, "elbow": 110,
        "note": "Hovering above lightbox/photobox"
    },
    "on_lightbox": {
        "base_steps": 300,
        "shoulder": 80, "card_rotate": 90, "wrist_tilt": 90, "elbow": 125,
        "note": "Card placed on lightbox for photo"
    },
    "above_bin1": {
        "base_steps": -400,
        "shoulder": 65, "card_rotate": 90, "wrist_tilt": 90, "elbow": 110,
        "note": "Above sort bin 1 (high value)"
    },
    "drop_bin1": {
        "base_steps": -400,
        "shoulder": 80, "card_rotate": 90, "wrist_tilt": 90, "elbow": 125,
        "note": "Lowered into bin 1 for release"
    },
    "above_bin2": {
        "base_steps": -600,
        "shoulder": 65, "card_rotate": 90, "wrist_tilt": 90, "elbow": 110,
        "note": "Above sort bin 2 (bulk)"
    },
    "drop_bin2": {
        "base_steps": -600,
        "shoulder": 80, "card_rotate": 90, "wrist_tilt": 90, "elbow": 125,
        "note": "Lowered into bin 2 for release"
    },
}

# Servo safe limits — won't send anything outside these
SERVO_LIMITS = {
    "shoulder":     (20, 160),
    "elbow":        (20, 160),
    "card_rotate":  (0, 180),
    "wrist_tilt":   (0, 180),
}

# Stepper config
STEPPER_MAX_STEPS = 15000     # Absolute max from home (safety)
STEPPER_DEFAULT_SPEED = 800   # Microseconds per pulse (lower = faster)


# ══════════════════════════════════════════════════════════════════════════════
# ARM DEPLOYER CLASS
# ══════════════════════════════════════════════════════════════════════════════

class ArmDeployer:
    """
    Waypoint controller for NEXUS arm.
    Sends JSON commands to ESP32 v4.1 over serial.
    """

    def __init__(self, port=None):
        self.ser = None
        self.port = port
        self.connected = False
        self.base_position = 0   # Track stepper position (no encoder feedback)
        self.waypoints = {}
        self._load_waypoints()

    # ── Connection ────────────────────────────────────────────────────────

    def find_esp32(self):
        """Auto-detect ESP32 serial port"""
        if not SERIAL_OK:
            return None

        # Check common names first
        common = ["/dev/nexus_arm", "/dev/ttyUSB0", "/dev/ttyUSB1",
                  "/dev/ttyACM0", "COM3", "COM4", "COM5", "COM6"]
        for p in common:
            try:
                s = serial.Serial(p, BAUD, timeout=2)
                s.write(b'{"cmd":"ping"}\n')
                time.sleep(0.3)
                resp = s.read(s.in_waiting or 1).decode(errors='ignore')
                if "pong" in resp or "nexus_arm" in resp:
                    s.close()
                    return p
                s.close()
            except:
                continue

        # Scan all ports
        for p in serial.tools.list_ports.comports():
            if "CP210" in (p.description or "") or "CH340" in (p.description or "") \
               or "USB" in (p.description or ""):
                try:
                    s = serial.Serial(p.device, BAUD, timeout=2)
                    s.write(b'{"cmd":"ping"}\n')
                    time.sleep(0.3)
                    resp = s.read(s.in_waiting or 1).decode(errors='ignore')
                    if "pong" in resp or "nexus_arm" in resp:
                        s.close()
                        return p.device
                    s.close()
                except:
                    continue
        return None

    def connect(self):
        """Connect to ESP32"""
        if not SERIAL_OK:
            print("ERROR: pyserial not installed")
            return False

        port = self.port or self.find_esp32()
        if not port:
            print("ERROR: Can't find ESP32. Is it plugged in?")
            print("  Try: python arm_deployer.py --port COM5")
            return False

        try:
            self.ser = serial.Serial(port, BAUD, timeout=2)
            time.sleep(2)  # ESP32 reboot on connect
            # Flush boot garbage
            self.ser.reset_input_buffer()
            # Ping
            resp = self._cmd({"cmd": "ping"})
            if resp and "pong" in str(resp):
                self.port = port
                self.connected = True
                print(f"Connected: {port}")
                return True
            else:
                print(f"Connected to {port} but no pong. Response: {resp}")
                self.connected = True  # Might still work
                return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Close serial"""
        if self.ser:
            self.ser.close()
        self.connected = False

    # ── Low-level commands ────────────────────────────────────────────────

    def _cmd(self, obj, wait=0.15):
        """Send JSON command, return parsed response"""
        if not self.ser:
            return None
        try:
            raw = json.dumps(obj) + "\n"
            self.ser.write(raw.encode())
            time.sleep(wait)
            if self.ser.in_waiting:
                resp = self.ser.read(self.ser.in_waiting).decode(errors='ignore').strip()
                # Could be multiple lines — grab last JSON
                for line in reversed(resp.split('\n')):
                    line = line.strip()
                    if line.startswith('{'):
                        try:
                            return json.loads(line)
                        except:
                            pass
                return resp
            return None
        except Exception as e:
            print(f"CMD error: {e}")
            return None

    def set_servo(self, channel, angle):
        """Set servo angle with safety clamp. Channel 1-4."""
        names = {1: "shoulder", 2: "card_rotate", 3: "wrist_tilt", 4: "elbow"}
        name = names.get(channel, f"ch{channel}")
        lo, hi = SERVO_LIMITS.get(name, (0, 180))
        safe = max(lo, min(hi, int(angle)))
        if safe != int(angle):
            print(f"  CLAMPED {name}: {angle}° → {safe}° (limit {lo}-{hi})")
        return self._cmd({"cmd": "servo", "channel": channel, "angle": safe})

    def move_base(self, target_steps, speed=None):
        """Move base stepper to absolute position (tracked in software)."""
        speed = speed or STEPPER_DEFAULT_SPEED
        # Safety fence
        target_steps = max(-STEPPER_MAX_STEPS, min(STEPPER_MAX_STEPS, target_steps))
        delta = target_steps - self.base_position
        if delta == 0:
            return
        direction = 1 if delta > 0 else -1
        steps = abs(delta)
        print(f"  Base: {self.base_position} → {target_steps} ({steps} steps, dir={direction})")
        # Send in chunks of 500 for responsiveness
        while steps > 0:
            chunk = min(steps, 500)
            self._cmd({"cmd": "move_base", "steps": chunk, "dir": direction, "speed": speed},
                      wait=chunk * speed * 2 / 1_000_000 + 0.1)
            steps -= chunk
            self.base_position += chunk * direction

    def vacuum_on(self):
        """Engage vacuum suction: pump ON, solenoid CLOSED (hold)"""
        self._cmd({"cmd": "relay", "channel": 5, "state": 1})  # Pump ON
        self._cmd({"cmd": "relay", "channel": 6, "state": 0})  # Solenoid closed = hold
        time.sleep(0.3)  # Let suction build

    def vacuum_off(self):
        """Release card: solenoid OPEN (vent), then pump OFF"""
        self._cmd({"cmd": "relay", "channel": 6, "state": 1})  # Solenoid open = release
        time.sleep(0.2)  # Let pressure vent
        self._cmd({"cmd": "relay", "channel": 5, "state": 0})  # Pump OFF
        self._cmd({"cmd": "relay", "channel": 6, "state": 0})  # Solenoid back to default

    def lightbox(self, r=255, g=255, b=255):
        """Turn on lightbox LEDs"""
        self._cmd({"cmd": "lightbox", "r": r, "g": g, "b": b})

    def lightbox_off(self):
        """Turn off lightbox"""
        self._cmd({"cmd": "lightbox_off"})

    def home(self):
        """Send ESP32 home command + reset base tracking"""
        print(">> HOME")
        self._cmd({"cmd": "home"})
        # If base isn't at 0, move it back
        if self.base_position != 0:
            self.move_base(0)
        self.base_position = 0
        time.sleep(0.5)

    def emergency_stop(self):
        """Kill everything"""
        self._cmd({"cmd": "stop"})
        self._cmd({"cmd": "relay", "channel": 5, "state": 0})
        self._cmd({"cmd": "relay", "channel": 6, "state": 0})
        print("!! EMERGENCY STOP !!")

    # ── Waypoint movement ─────────────────────────────────────────────────

    def goto(self, name, speed=0.03):
        """
        Move to named waypoint with interpolated servo motion.
        speed = seconds between interpolation steps (lower = faster)
        """
        if name not in self.waypoints:
            print(f"Unknown waypoint: {name}")
            print(f"Available: {list(self.waypoints.keys())}")
            return False

        wp = self.waypoints[name]
        print(f">> {name}")

        # Move base stepper (not interpolated — stepper handles its own speed)
        target_base = wp.get("base_steps", 0)
        if target_base != self.base_position:
            self.move_base(target_base)

        # Interpolate servos for smooth motion
        # Read current targets (we don't have encoder feedback, so track in software)
        target = {
            "shoulder": wp["shoulder"],
            "card_rotate": wp["card_rotate"],
            "wrist_tilt": wp["wrist_tilt"],
            "elbow": wp["elbow"],
        }

        # Just send directly — servos are analog, they smooth themselves
        for ch, name_key in [(1, "shoulder"), (2, "card_rotate"), (3, "wrist_tilt"), (4, "elbow")]:
            self.set_servo(ch, target[name_key])
            time.sleep(speed)

        # Let servos settle
        time.sleep(0.3)
        return True

    # ── Sort Cycle (the whole point) ──────────────────────────────────────

    def sort_cycle(self, bin_name="bin1", photo_callback=None):
        """
        Full card sort cycle:
          1. Pick card from intake
          2. Place on lightbox for photo
          3. (optional: trigger camera)
          4. Pick back up from lightbox
          5. Place in sort bin
          6. Return home

        photo_callback: function called when card is on lightbox.
                        Should trigger camera capture and return True/False.
                        If None, waits 2 seconds instead.
        """
        above_bin = f"above_{bin_name}"
        drop_bin = f"drop_{bin_name}"

        if above_bin not in self.waypoints or drop_bin not in self.waypoints:
            print(f"Bin '{bin_name}' not calibrated. Need '{above_bin}' and '{drop_bin}' waypoints.")
            return False

        print("=" * 50)
        print("SORT CYCLE START")
        print("=" * 50)

        # 1. Go to intake position
        self.goto("home")
        self.goto("above_intake")
        self.goto("intake_grab")

        # 2. Vacuum pick
        print(">> VACUUM ON — picking card")
        self.vacuum_on()
        time.sleep(0.5)  # Let suction grip

        # 3. Lift
        self.goto("above_intake")

        # 4. Move to lightbox
        self.lightbox(255, 255, 255)  # White light for photo
        self.goto("above_lightbox")
        self.goto("on_lightbox")

        # 5. Release card onto lightbox
        print(">> Releasing card on lightbox")
        self.vacuum_off()
        time.sleep(0.3)

        # 6. Retract so camera has clear view
        self.goto("above_lightbox")

        # 7. Photo capture
        if photo_callback:
            print(">> Triggering camera...")
            photo_callback()
        else:
            print(">> Waiting 2s for photo (no callback set)...")
            time.sleep(2)

        # 8. Pick card back up from lightbox
        self.goto("on_lightbox")
        print(">> VACUUM ON — picking from lightbox")
        self.vacuum_on()
        time.sleep(0.5)

        # 9. Lift from lightbox
        self.goto("above_lightbox")
        self.lightbox_off()

        # 10. Move to sort bin
        self.goto(above_bin)
        self.goto(drop_bin)

        # 11. Release into bin
        print(f">> Releasing card into {bin_name}")
        self.vacuum_off()
        time.sleep(0.3)

        # 12. Retract and go home
        self.goto(above_bin)
        self.goto("home")

        print("=" * 50)
        print("SORT CYCLE COMPLETE")
        print("=" * 50)
        return True

    def quick_sort(self, bin_name="bin1"):
        """Skip lightbox — straight from intake to bin (fast mode)"""
        above_bin = f"above_{bin_name}"
        drop_bin = f"drop_{bin_name}"

        print(">> QUICK SORT (no photo)")
        self.goto("home")
        self.goto("above_intake")
        self.goto("intake_grab")
        self.vacuum_on()
        time.sleep(0.5)
        self.goto("above_intake")
        self.goto(above_bin)
        self.goto(drop_bin)
        self.vacuum_off()
        time.sleep(0.3)
        self.goto(above_bin)
        self.goto("home")
        print(">> QUICK SORT DONE")
        return True

    # ── Waypoint management ───────────────────────────────────────────────

    def _load_waypoints(self):
        """Load waypoints from file, or use defaults"""
        if WAYPOINT_FILE.exists():
            try:
                with open(WAYPOINT_FILE) as f:
                    self.waypoints = json.load(f)
                print(f"Loaded {len(self.waypoints)} waypoints from {WAYPOINT_FILE.name}")
                return
            except:
                pass
        self.waypoints = dict(DEFAULT_WAYPOINTS)
        print(f"Using {len(self.waypoints)} default waypoints (not calibrated!)")

    def save_waypoints(self):
        """Save current waypoints to file"""
        with open(WAYPOINT_FILE, 'w') as f:
            json.dump(self.waypoints, f, indent=2)
        print(f"Saved {len(self.waypoints)} waypoints to {WAYPOINT_FILE.name}")

    def set_waypoint(self, name, shoulder, elbow, card_rotate, wrist_tilt, base_steps=None, note=""):
        """Record a waypoint"""
        self.waypoints[name] = {
            "base_steps": base_steps if base_steps is not None else self.base_position,
            "shoulder": shoulder,
            "elbow": elbow,
            "card_rotate": card_rotate,
            "wrist_tilt": wrist_tilt,
            "note": note,
        }
        print(f"Waypoint '{name}' set: S={shoulder} E={elbow} R={card_rotate} T={wrist_tilt} B={self.waypoints[name]['base_steps']}")

    # ── Calibration mode ──────────────────────────────────────────────────

    def calibrate(self):
        """
        Interactive calibration. Jog joints, save positions.
        This is how you teach the arm where things are.
        """
        print("\n" + "=" * 60)
        print("  NEXUS ARM CALIBRATION MODE")
        print("  Jog joints → position arm → save waypoint")
        print("=" * 60)
        print()
        print("Commands:")
        print("  s <angle>   — Shoulder (ch1, 20-160)")
        print("  e <angle>   — Elbow (ch4, 20-160)")
        print("  r <angle>   — Card rotate (ch2, 0-180)")
        print("  t <angle>   — Wrist tilt (ch3, 0-180)")
        print("  b <steps>   — Base stepper (relative, + or -)")
        print("  bz          — Zero base position counter")
        print("  v on/off    — Vacuum on/off")
        print("  l on/off    — Lightbox on/off")
        print("  home        — Go to home")
        print("  save <name> — Save current position as waypoint")
        print("  goto <name> — Go to saved waypoint")
        print("  list        — List all waypoints")
        print("  test        — Test all waypoints in sequence")
        print("  done        — Save and exit calibration")
        print()

        # Track current servo positions (start at home = 90)
        cur = {"shoulder": 90, "elbow": 90, "card_rotate": 90, "wrist_tilt": 90}

        while True:
            try:
                raw = input(f"[B:{self.base_position:+d} S:{cur['shoulder']} E:{cur['elbow']} R:{cur['card_rotate']} T:{cur['wrist_tilt']}] > ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw:
                continue
            parts = raw.split()
            cmd = parts[0].lower()

            try:
                if cmd == "s" and len(parts) > 1:
                    a = int(parts[1])
                    self.set_servo(1, a)
                    cur["shoulder"] = a

                elif cmd == "e" and len(parts) > 1:
                    a = int(parts[1])
                    self.set_servo(4, a)
                    cur["elbow"] = a

                elif cmd == "r" and len(parts) > 1:
                    a = int(parts[1])
                    self.set_servo(2, a)
                    cur["card_rotate"] = a

                elif cmd == "t" and len(parts) > 1:
                    a = int(parts[1])
                    self.set_servo(3, a)
                    cur["wrist_tilt"] = a

                elif cmd == "b" and len(parts) > 1:
                    steps = int(parts[1])
                    target = self.base_position + steps
                    self.move_base(target)

                elif cmd == "bz":
                    self.base_position = 0
                    print("Base position zeroed")

                elif cmd == "v":
                    if len(parts) > 1 and parts[1].lower() in ("on", "1"):
                        self.vacuum_on()
                        print("Vacuum ON")
                    else:
                        self.vacuum_off()
                        print("Vacuum OFF")

                elif cmd == "l":
                    if len(parts) > 1 and parts[1].lower() in ("on", "1"):
                        self.lightbox()
                        print("Lightbox ON")
                    else:
                        self.lightbox_off()
                        print("Lightbox OFF")

                elif cmd == "home":
                    self.home()
                    cur = {"shoulder": 90, "elbow": 90, "card_rotate": 90, "wrist_tilt": 90}

                elif cmd == "save" and len(parts) > 1:
                    name = parts[1]
                    note = " ".join(parts[2:]) if len(parts) > 2 else ""
                    self.set_waypoint(name, cur["shoulder"], cur["elbow"],
                                     cur["card_rotate"], cur["wrist_tilt"], note=note)
                    self.save_waypoints()

                elif cmd == "goto" and len(parts) > 1:
                    self.goto(parts[1])
                    # Update cur from waypoint
                    wp = self.waypoints.get(parts[1], {})
                    cur["shoulder"] = wp.get("shoulder", cur["shoulder"])
                    cur["elbow"] = wp.get("elbow", cur["elbow"])
                    cur["card_rotate"] = wp.get("card_rotate", cur["card_rotate"])
                    cur["wrist_tilt"] = wp.get("wrist_tilt", cur["wrist_tilt"])

                elif cmd == "list":
                    print(f"\n{'Name':<20} {'Base':>6} {'Shldr':>6} {'Elbow':>6} {'Rot':>6} {'Tilt':>6}  Note")
                    print("-" * 80)
                    for n, w in self.waypoints.items():
                        print(f"{n:<20} {w['base_steps']:>+6d} {w['shoulder']:>6} {w['elbow']:>6} "
                              f"{w['card_rotate']:>6} {w['wrist_tilt']:>6}  {w.get('note','')}")
                    print()

                elif cmd == "test":
                    print("Testing all waypoints...")
                    for name in self.waypoints:
                        self.goto(name)
                        time.sleep(1)
                    self.home()
                    print("Test complete")

                elif cmd in ("done", "quit", "exit", "q"):
                    self.save_waypoints()
                    break

                elif cmd == "stop":
                    self.emergency_stop()

                else:
                    print(f"Unknown: {raw}")

            except ValueError as e:
                print(f"Bad value: {e}")
            except Exception as e:
                print(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="NEXUS Arm Deployer — Waypoint Controller")
    parser.add_argument("--port", help="Serial port (auto-detect if omitted)")
    parser.add_argument("--calibrate", action="store_true", help="Enter calibration mode")
    parser.add_argument("--sort", action="store_true", help="Run one sort cycle")
    parser.add_argument("--quick", action="store_true", help="Quick sort (no photo)")
    parser.add_argument("--bin", default="bin1", help="Sort bin name (default: bin1)")
    parser.add_argument("--test", action="store_true", help="Test all waypoints")
    parser.add_argument("--home", action="store_true", help="Just go home")
    parser.add_argument("--loop", type=int, help="Run N sort cycles")
    parser.add_argument("--dry", action="store_true", help="Dry run — print commands, don't send")
    args = parser.parse_args()

    arm = ArmDeployer(port=args.port)

    if not arm.connect():
        print("\nCouldn't connect. Check USB cable and try again.")
        print("Available ports:")
        if SERIAL_OK:
            for p in serial.tools.list_ports.comports():
                print(f"  {p.device} — {p.description}")
        sys.exit(1)

    try:
        if args.home:
            arm.home()

        elif args.calibrate:
            arm.calibrate()

        elif args.test:
            print("Testing all waypoints in sequence...")
            arm.home()
            for name in arm.waypoints:
                if name == "home":
                    continue
                arm.goto(name)
                time.sleep(1.5)
            arm.home()
            print("All waypoints tested.")

        elif args.sort:
            arm.sort_cycle(bin_name=args.bin)

        elif args.quick:
            arm.quick_sort(bin_name=args.bin)

        elif args.loop:
            print(f"Running {args.loop} sort cycles to {args.bin}...")
            for i in range(args.loop):
                print(f"\n── Cycle {i+1}/{args.loop} ──")
                arm.sort_cycle(bin_name=args.bin)
                time.sleep(1)
            print(f"\nDone. {args.loop} cards sorted.")

        else:
            # Interactive menu
            print("\n  NEXUS ARM DEPLOYER")
            print("  ─────────────────")
            print("  1) Home")
            print("  2) Calibrate waypoints")
            print("  3) Sort cycle (with photo)")
            print("  4) Quick sort (no photo)")
            print("  5) Test all positions")
            print("  6) Loop sort cycles")
            print("  7) Manual jog")
            print("  0) Exit\n")

            while True:
                try:
                    choice = input(">> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if choice == "1":
                    arm.home()
                elif choice == "2":
                    arm.calibrate()
                elif choice == "3":
                    b = input("Bin (bin1/bin2): ").strip() or "bin1"
                    arm.sort_cycle(bin_name=b)
                elif choice == "4":
                    b = input("Bin (bin1/bin2): ").strip() or "bin1"
                    arm.quick_sort(bin_name=b)
                elif choice == "5":
                    arm.home()
                    for name in arm.waypoints:
                        if name != "home":
                            arm.goto(name)
                            time.sleep(1.5)
                    arm.home()
                elif choice == "6":
                    n = int(input("How many cycles? ") or "5")
                    b = input("Bin (bin1/bin2): ").strip() or "bin1"
                    for i in range(n):
                        print(f"\n── Cycle {i+1}/{n} ──")
                        arm.sort_cycle(bin_name=b)
                        time.sleep(1)
                elif choice == "7":
                    arm.calibrate()
                elif choice in ("0", "q", "quit", "exit"):
                    break
                else:
                    print("Pick 0-7")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        arm.vacuum_off()
        arm.home()
        arm.disconnect()
        print("Disconnected. Done.")


if __name__ == "__main__":
    main()
