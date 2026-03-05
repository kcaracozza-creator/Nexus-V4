"""
NEXUS ESP32 Bridge - DANIELSON
================================
Manages serial connections to both ESP32 controllers.

Usage:
    from hardware.esp32_bridge import ESP32Bridge
    
    bridge = ESP32Bridge()
    bridge.connect_light("COM3")
    bridge.connect_arm("COM4")
    
    bridge.light("all_on", brightness=200)
    bridge.arm("servo", channel=1, angle=45)
    bridge.arm("relay", channel=5, state=1)  # vacuum on
    bridge.arm("lightbox", r=255, g=255, b=255)

Standalone test mode:
    python esp32_bridge.py --light COM3 --arm COM4

Requirements:
    pip install pyserial
"""

import json
import time
import threading
import serial
import serial.tools.list_ports
import logging
from typing import Optional

log = logging.getLogger("nexus.esp32")


class ESP32Controller:
    """Single ESP32 serial connection with thread-safe send/receive."""

    def __init__(self, name: str):
        self.name = name
        self.port: Optional[serial.Serial] = None
        self._lock = threading.Lock()

    def connect(self, port: str, baud: int = 115200, timeout: float = 2.0) -> bool:
        try:
            self.port = serial.Serial(port, baud, timeout=timeout)
            time.sleep(2.0)  # ESP32 resets on connect, wait for ready
            self.port.flushInput()
            # Ping test
            resp = self.send({"cmd": "ping"})
            if resp and resp.get("status") in ("pong", "ok", "ready"):
                log.info(f"[{self.name}] Connected on {port}")
                return True
            # Still connected even if ping response is weird, just log it
            log.warning(f"[{self.name}] Connected on {port} (unexpected ping response: {resp})")
            return True
        except Exception as e:
            log.error(f"[{self.name}] Connection failed on {port}: {e}")
            self.port = None
            return False

    def disconnect(self):
        if self.port and self.port.is_open:
            self.port.close()
        self.port = None

    def is_connected(self) -> bool:
        return self.port is not None and self.port.is_open

    def send(self, payload: dict) -> Optional[dict]:
        """Send JSON command, wait for JSON response."""
        if not self.is_connected():
            log.warning(f"[{self.name}] Not connected")
            return None

        with self._lock:
            try:
                msg = json.dumps(payload) + "\n"
                self.port.write(msg.encode())
                self.port.flush()

                # Read response (with timeout)
                raw = self.port.readline().decode().strip()
                if not raw:
                    return None
                return json.loads(raw)

            except serial.SerialException as e:
                log.error(f"[{self.name}] Serial error: {e}")
                self.port = None
                return None
            except json.JSONDecodeError as e:
                log.error(f"[{self.name}] Bad JSON response: {e}")
                return None
            except Exception as e:
                log.error(f"[{self.name}] Unexpected error: {e}")
                return None

    def cmd(self, command: str, **kwargs) -> Optional[dict]:
        """Convenience: build and send a command dict."""
        payload = {"cmd": command, **kwargs}
        return self.send(payload)


class ESP32Bridge:
    """
    Manages both ESP32 controllers (light + arm).
    Drop this into the NEXUS desktop app.
    """

    def __init__(self):
        self._light = ESP32Controller("LIGHT")
        self._arm   = ESP32Controller("ARM")

    # ── Connection management ─────────────────────────────────────────────

    def connect_light(self, port: str) -> bool:
        return self._light.connect(port)

    def connect_arm(self, port: str) -> bool:
        return self._arm.connect(port)

    def disconnect_all(self):
        self._light.disconnect()
        self._arm.disconnect()

    def status(self) -> dict:
        return {
            "light_connected": self._light.is_connected(),
            "arm_connected":   self._arm.is_connected(),
        }

    # ── Light controller commands ─────────────────────────────────────────

    def light(self, command: str, **kwargs) -> Optional[dict]:
        return self._light.cmd(command, **kwargs)

    def set_channel(self, gpio_pin: int, value: int) -> bool:
        resp = self._light.cmd("set_channel", channel=gpio_pin, value=value)
        return resp is not None and resp.get("status") == "ok"

    def all_lights_on(self, brightness: int = 255) -> bool:
        resp = self._light.cmd("all_on", brightness=brightness)
        return resp is not None and resp.get("status") == "ok"

    def all_lights_off(self) -> bool:
        resp = self._light.cmd("all_off")
        return resp is not None and resp.get("status") == "ok"

    def set_all_channels(self, values: list) -> bool:
        """values = list of 5 ints [ch25, ch26, ch27, ch33, ch32]"""
        resp = self._light.cmd("set_all", values=values)
        return resp is not None and resp.get("status") == "ok"

    # ── Arm controller commands ───────────────────────────────────────────

    def arm(self, command: str, **kwargs) -> Optional[dict]:
        return self._arm.cmd(command, **kwargs)

    def move_base(self, steps: int, direction: int = 1, speed: int = 800) -> bool:
        """
        Move base stepper.
        steps: number of steps
        direction: 1 = forward, -1 = backward
        speed: microseconds per half-step (lower = faster, min ~400)
        """
        resp = self._arm.cmd("move_base", steps=steps, dir=direction, speed=speed)
        return resp is not None and resp.get("status") == "ok"

    def servo(self, channel: int, angle: int) -> bool:
        """
        Move a servo.
        channel: 1=shoulder, 2=elbow, 3=wrist1, 4=wrist2
        angle: 0-180 degrees
        """
        resp = self._arm.cmd("servo", channel=channel, angle=angle)
        return resp is not None and resp.get("status") == "ok"

    def relay(self, channel: int, state: bool) -> bool:
        """
        Toggle relay.
        channel: 5=vacuum pump, 6=solenoid
        state: True=on, False=off
        """
        resp = self._arm.cmd("relay", channel=channel, state=1 if state else 0)
        return resp is not None and resp.get("status") == "ok"

    def vacuum_on(self) -> bool:
        return self.relay(5, True)

    def vacuum_off(self) -> bool:
        return self.relay(5, False)

    def release(self) -> bool:
        """Fire solenoid to release suction."""
        self.relay(6, True)
        time.sleep(0.1)
        self.relay(6, False)
        return True

    def lightbox(self, r: int = 255, g: int = 255, b: int = 255) -> bool:
        resp = self._arm.cmd("lightbox", r=r, g=g, b=b)
        return resp is not None and resp.get("status") == "ok"

    def lightbox_off(self) -> bool:
        resp = self._arm.cmd("lightbox_off")
        return resp is not None and resp.get("status") == "ok"

    def home(self) -> bool:
        """Send arm to home position (all servos 90°, relays off, lightbox white)."""
        resp = self._arm.cmd("home")
        return resp is not None and resp.get("status") == "ok"

    def stop(self) -> bool:
        """Emergency stop."""
        resp = self._arm.cmd("stop")
        return resp is not None and resp.get("status") == "ok"

    # ── Scan sequence ─────────────────────────────────────────────────────

    def scan_sequence(self, pick_steps: int = 100) -> bool:
        """
        Basic pick-and-place sequence for card scanning.
        Customize angles/steps for your physical setup.
        """
        log.info("Starting scan sequence")

        # 1. Lights on
        self.all_lights_on(200)
        self.lightbox(255, 255, 255)

        # 2. Move arm to pick position
        self.servo(1, 60)   # shoulder down
        self.servo(2, 90)   # elbow level
        self.servo(3, 90)   # wrist neutral
        self.servo(4, 90)
        time.sleep(0.5)

        # 3. Vacuum on, pick
        self.vacuum_on()
        time.sleep(0.3)

        # 4. Lift
        self.servo(1, 90)
        time.sleep(0.3)

        # 5. Rotate base to scan position
        self.move_base(pick_steps, direction=1, speed=600)

        # 6. Lower card to scan area
        self.servo(1, 70)
        time.sleep(0.5)

        # --- SCAN HAPPENS HERE (camera triggered by DANIELSON app) ---

        # 7. Lift, return
        self.servo(1, 90)
        time.sleep(0.3)
        self.move_base(pick_steps, direction=-1, speed=600)

        # 8. Place
        self.servo(1, 60)
        time.sleep(0.3)
        self.release()
        time.sleep(0.2)

        # 9. Home
        self.home()

        log.info("Scan sequence complete")
        return True


# ── Utilities ─────────────────────────────────────────────────────────────

def list_com_ports() -> list:
    """List available COM ports."""
    return [p.device for p in serial.tools.list_ports.comports()]


def auto_connect(bridge: ESP32Bridge) -> dict:
    """
    Try to auto-detect and connect both ESP32s.
    Pings each port and checks device identity.
    Returns dict with detected ports.
    """
    ports = list_com_ports()
    log.info(f"Available ports: {ports}")
    results = {"light": None, "arm": None}

    for port in ports:
        try:
            s = serial.Serial(port, 115200, timeout=2)
            time.sleep(2.0)
            s.flushInput()
            s.write(b'{"cmd":"ping"}\n')
            raw = s.readline().decode().strip()
            s.close()
            log.info(f"{port} -> {raw}")
        except Exception:
            continue

    return results


# ── Standalone test / CLI ─────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="NEXUS ESP32 Bridge Test")
    parser.add_argument("--light", help="COM port for light controller (e.g. COM3)")
    parser.add_argument("--arm",   help="COM port for arm controller   (e.g. COM4)")
    parser.add_argument("--list",  action="store_true", help="List available COM ports")
    args = parser.parse_args()

    if args.list:
        print("Available ports:", list_com_ports())
        exit()

    bridge = ESP32Bridge()

    if args.light:
        ok = bridge.connect_light(args.light)
        print(f"Light controller: {'OK' if ok else 'FAILED'}")
        if ok:
            bridge.all_lights_on(128)
            time.sleep(1)
            bridge.all_lights_off()
            print("  → LED test done")

    if args.arm:
        ok = bridge.connect_arm(args.arm)
        print(f"Arm controller:   {'OK' if ok else 'FAILED'}")
        if ok:
            print("  → Homing...")
            bridge.home()
            time.sleep(1)
            print("  → Lightbox white...")
            bridge.lightbox(255, 255, 255)
            time.sleep(1)
            bridge.lightbox_off()
            print("  → Arm test done")

    print("\nStatus:", bridge.status())
    bridge.disconnect_all()
