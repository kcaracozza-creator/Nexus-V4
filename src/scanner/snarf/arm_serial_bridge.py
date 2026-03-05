#!/usr/bin/env python3
"""
NEXUS Robo V3 - ARM Serial Bridge
===================================
Runs on SNARF. Translates HTTP API calls from arm_controller.py / arm_calibration.py
into USB serial JSON commands sent to the ARM ESP32 on /dev/ttyUSB0.

Exposes the same HTTP API the ESP32 would serve over WiFi:
  GET  /api/arm/status          → returns current joint angles + vacuum state
  POST /api/arm/move            → body: {"joints": [j0,j1,j2,j3,j4]}
  POST /api/arm/vacuum          → body: {"on": true/false}
  GET  /api/arm/home            → move to home position
  GET  /health                  → bridge health check

Run:
  python3 arm_serial_bridge.py [--port /dev/ttyUSB0] [--baud 115200] [--http-port 8218]

arm_controller.py / arm_calibration.py should point to:
  http://192.168.1.172:8218

Patent Pending - Kevin Caracozza
"""

import argparse
import json
import logging
import sys
import threading
import time

try:
    import serial
except ImportError:
    print("[FATAL] pyserial not installed. Run: pip3 install pyserial --break-system-packages")
    sys.exit(1)

try:
    from flask import Flask, jsonify, request
except ImportError:
    print("[FATAL] flask not installed. Run: pip3 install flask --break-system-packages")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD        = 115200
DEFAULT_HTTP_PORT   = 8218

HOME_JOINTS = [90, 90, 90, 90, 90]

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("arm-bridge")

app = Flask(__name__)

# ─── Serial manager ───────────────────────────────────────────────────────────
class SerialBridge:
    def __init__(self, port, baud):
        self.port    = port
        self.baud    = baud
        self._ser    = None
        self._lock   = threading.Lock()
        self._state  = {
            "joints":  HOME_JOINTS[:],
            "vacuum":  False,
            "connected": False,
        }

    def connect(self):
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=2)
            time.sleep(2)   # ESP32 boot settle
            self._state["connected"] = True
            log.info(f"Connected to ESP32 on {self.port} @ {self.baud}")
            return True
        except Exception as e:
            log.error(f"Serial connect failed: {e}")
            return False

    def _send(self, cmd: dict) -> dict:
        """Send JSON command, return JSON response. Thread-safe."""
        if not self._ser or not self._ser.is_open:
            return {"ok": False, "error": "not connected"}

        payload = json.dumps(cmd) + "\n"
        with self._lock:
            try:
                self._ser.reset_input_buffer()
                self._ser.write(payload.encode())
                time.sleep(0.15)
                raw = self._ser.readline().decode(errors="ignore").strip()
                if raw:
                    return json.loads(raw)
                # ESP32 may not echo — treat silence as OK for move/vacuum
                return {"ok": True, "silent": True}
            except json.JSONDecodeError:
                return {"ok": True, "raw": raw}
            except Exception as e:
                log.warning(f"Serial error: {e}")
                return {"ok": False, "error": str(e)}

    def get_status(self) -> dict:
        resp = self._send({"cmd": "status"})
        if resp.get("ok") and "joints" in resp:
            self._state["joints"] = resp["joints"]
            self._state["vacuum"] = resp.get("vacuum", False)
        return {
            "ok":        True,
            "joints":    self._state["joints"],
            "vacuum":    self._state["vacuum"],
            "connected": self._state["connected"],
            "bridge":    "serial",
            "port":      self.port,
        }

    def move_joints(self, joints: list) -> dict:
        resp = self._send({"cmd": "move", "joints": joints})
        if resp.get("ok", True):  # treat silent as ok
            self._state["joints"] = joints[:]
        return {"ok": True, "joints": joints}

    def set_vacuum(self, on: bool) -> dict:
        resp = self._send({"cmd": "vacuum", "on": on})
        self._state["vacuum"] = on
        return {"ok": True, "vacuum": on}

    def home(self) -> dict:
        return self.move_joints(HOME_JOINTS[:])


# Global bridge instance (set in main)
bridge: SerialBridge = None


# ─── HTTP routes (same API as ESP32 WiFi server) ──────────────────────────────
@app.route("/health")
def health():
    return jsonify({
        "status":    "ok",
        "bridge":    "arm-serial-bridge",
        "connected": bridge._state["connected"],
        "port":      bridge.port,
    })


@app.route("/api/arm/status")
def arm_status():
    return jsonify(bridge.get_status())


@app.route("/api/arm/move", methods=["POST"])
def arm_move():
    data = request.get_json(force=True)
    joints = data.get("joints")
    if not joints or len(joints) != 5:
        return jsonify({"ok": False, "error": "need joints[5]"}), 400
    return jsonify(bridge.move_joints(joints))


@app.route("/api/arm/vacuum", methods=["POST"])
def arm_vacuum():
    data = request.get_json(force=True)
    on = bool(data.get("on", False))
    return jsonify(bridge.set_vacuum(on))


@app.route("/api/arm/home")
def arm_home():
    return jsonify(bridge.home())


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    global bridge

    parser = argparse.ArgumentParser(description="NEXUS ARM Serial Bridge")
    parser.add_argument("--port",      default=DEFAULT_SERIAL_PORT)
    parser.add_argument("--baud",      default=DEFAULT_BAUD, type=int)
    parser.add_argument("--http-port", default=DEFAULT_HTTP_PORT, type=int)
    args = parser.parse_args()

    bridge = SerialBridge(args.port, args.baud)

    print(f"\n  NEXUS ARM Serial Bridge")
    print(f"  Serial : {args.port} @ {args.baud}")
    print(f"  HTTP   : http://0.0.0.0:{args.http_port}")
    print(f"  Use this URL in arm_calibration.py / arm_controller.py:\n")
    print(f"    http://192.168.1.172:{args.http_port}\n")

    if not bridge.connect():
        print("  [WARN] Serial not available — bridge running in offline mode")
        print("         Commands will be accepted but not sent to hardware.\n")
    else:
        print("  ESP32 connected.\n")

    app.run(host="0.0.0.0", port=args.http_port, threaded=True)


if __name__ == "__main__":
    main()
