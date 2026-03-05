#!/usr/bin/env python3
"""
NEXUS Arm Command Sender
Send a single JSON command to the arm via serial.
Usage: python3 arm_cmd.py '{"cmd":"servo","channel":1,"angle":90}'
       python3 arm_cmd.py home
       python3 arm_cmd.py servo 1 45
       python3 arm_cmd.py base 200 1
       python3 arm_cmd.py vacuum on
       python3 arm_cmd.py vacuum off
       python3 arm_cmd.py light on
       python3 arm_cmd.py light off
"""
import serial
import json
import time
import sys

PORT = "/dev/nexus_arm"
BAUD = 115200

def send(cmd_json):
    s = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(0.1)
    s.reset_input_buffer()
    raw = json.dumps(cmd_json) + "\n"
    s.write(raw.encode())
    time.sleep(0.3)
    resp = ""
    if s.in_waiting:
        resp = s.read(s.in_waiting).decode(errors='ignore').strip()
    s.close()
    return resp

def main():
    if len(sys.argv) < 2:
        print("Usage: arm_cmd.py <command> [args]")
        return

    cmd = sys.argv[1].lower()

    if cmd == "home":
        print(send({"cmd": "home"}))

    elif cmd == "ping":
        print(send({"cmd": "ping"}))

    elif cmd == "stop":
        print(send({"cmd": "stop"}))

    elif cmd == "servo" and len(sys.argv) >= 4:
        ch = int(sys.argv[2])
        angle = int(sys.argv[3])
        print(f"Servo ch{ch} → {angle}°")
        print(send({"cmd": "servo", "channel": ch, "angle": angle}))

    elif cmd == "base" and len(sys.argv) >= 3:
        steps = int(sys.argv[2])
        direction = int(sys.argv[3]) if len(sys.argv) > 3 else (1 if steps > 0 else -1)
        steps = abs(steps)
        speed = int(sys.argv[4]) if len(sys.argv) > 4 else 800
        print(f"Base: {steps} steps, dir={direction}, speed={speed}")
        print(send({"cmd": "move_base", "steps": steps, "dir": direction, "speed": speed}))

    elif cmd == "vacuum":
        if len(sys.argv) > 2 and sys.argv[2].lower() in ("on", "1"):
            print("Vacuum ON")
            print(send({"cmd": "relay", "channel": 5, "state": 1}))
        else:
            print("Vacuum OFF")
            send({"cmd": "relay", "channel": 6, "state": 1})  # vent
            time.sleep(0.2)
            send({"cmd": "relay", "channel": 5, "state": 0})  # pump off
            print(send({"cmd": "relay", "channel": 6, "state": 0}))  # solenoid off

    elif cmd == "light":
        if len(sys.argv) > 2 and sys.argv[2].lower() in ("on", "1"):
            print("Lightbox ON")
            print(send({"cmd": "lightbox", "r": 255, "g": 255, "b": 255}))
        else:
            print("Lightbox OFF")
            print(send({"cmd": "lightbox_off"}))

    elif cmd == "test":
        print("PCA test — each channel gets a pulse")
        s = serial.Serial(PORT, BAUD, timeout=2)
        time.sleep(0.1)
        s.reset_input_buffer()
        s.write(b'{"cmd":"pca_test"}\n')
        time.sleep(8)
        if s.in_waiting:
            print(s.read(s.in_waiting).decode(errors='ignore'))
        s.close()

    else:
        # Try raw JSON
        try:
            obj = json.loads(sys.argv[1])
            print(send(obj))
        except:
            print(f"Unknown command: {cmd}")
            print("Try: home, ping, servo <ch> <angle>, base <steps> [dir], vacuum on/off, light on/off")

if __name__ == "__main__":
    main()
