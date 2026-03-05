"""
NEXUS Robot Arm Control
=======================
Telnet control for ESP32 arm at 192.168.1.218

Trained positions from Zultan simulation.
"""

import socket
import time

ARM_IP = "192.168.1.218"
ARM_PORT = 23

# Trained positions [base_steps, shoulder_steps, wrist, grabber, elbow]
# Note: steppers use step counts, servos use degrees
POSITIONS = {
    "home": {"shoulder": 0, "base": 0, "wrist": 90, "grabber": 90, "elbow": 90},
    "pickup": {"shoulder": -500, "base": 0, "wrist": 45, "grabber": 90, "elbow": 120},
    "scan": {"shoulder": -800, "base": 0, "wrist": 30, "grabber": 90, "elbow": 135},
    "drop_value": {"shoulder": 0, "base": 500, "wrist": 90, "grabber": 90, "elbow": 90},
    "drop_bulk": {"shoulder": 0, "base": -500, "wrist": 90, "grabber": 90, "elbow": 90},
}


class ArmController:
    """Control NEXUS arm via telnet"""

    def __init__(self, ip=ARM_IP, port=ARM_PORT):
        self.ip = ip
        self.port = port
        self.sock = None
        self.connected = False

    def connect(self):
        """Connect to arm"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            time.sleep(0.3)
            # Read welcome message
            self.sock.recv(1024)
            self.connected = True
            print(f"Connected to arm at {self.ip}:{self.port}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from arm"""
        if self.sock:
            self.sock.close()
            self.sock = None
        self.connected = False

    def send(self, cmd):
        """Send command and get response"""
        if not self.connected:
            if not self.connect():
                return None
        try:
            self.sock.send(f"{cmd}\n".encode())
            time.sleep(0.1)
            try:
                return self.sock.recv(1024).decode(errors='ignore')
            except socket.timeout:
                return ""
        except Exception as e:
            print(f"Send error: {e}")
            self.connected = False
            return None

    def shoulder(self, steps):
        """Move shoulder stepper (+ = up/CW, - = down/CCW)"""
        return self.send(f"shoulder {steps}")

    def base(self, steps):
        """Move base stepper via TB6600 (+ = CW, - = CCW)"""
        return self.send(f"base {steps}")

    def wrist(self, angle):
        """Set wrist servo angle (0-180)"""
        return self.send(f"wrist {angle}")

    def grabber(self, angle):
        """Set grabber servo angle (0-180)"""
        return self.send(f"grabber {angle}")

    def elbow(self, angle):
        """Set elbow servo angle (0-180)"""
        return self.send(f"elbow {angle}")

    def grab(self):
        """Activate vacuum to grab card"""
        return self.send("grab")

    def release(self):
        """Release card (vacuum off + solenoid pulse)"""
        return self.send("release")

    def home(self):
        """Go to home position"""
        return self.send("home")

    def go_to(self, position_name):
        """Move to named position"""
        if position_name not in POSITIONS:
            print(f"Unknown position: {position_name}")
            return False

        pos = POSITIONS[position_name]
        print(f"Moving to {position_name}...")

        # Move servos first (fast)
        self.wrist(pos["wrist"])
        self.grabber(pos["grabber"])
        self.elbow(pos["elbow"])
        time.sleep(0.3)

        # Move steppers (slower)
        self.shoulder(pos["shoulder"])
        self.base(pos["base"])

        # Wait for steppers to complete
        time.sleep(1)
        print(f"At {position_name}")
        return True

    def pick_card(self):
        """Pick up card from scanner"""
        self.go_to("pickup")
        time.sleep(0.5)
        self.grab()
        time.sleep(0.3)
        return True

    def drop_card(self, valuable=False):
        """Drop card to appropriate bin"""
        position = "drop_value" if valuable else "drop_bulk"
        self.go_to(position)
        time.sleep(0.3)
        self.release()
        time.sleep(0.2)
        self.go_to("home")
        return True

    def sort_cycle(self, valuable=False):
        """Complete pick-sort cycle"""
        self.pick_card()
        time.sleep(0.2)
        self.drop_card(valuable)
        return True


def test_arm():
    """Test arm movement"""
    arm = ArmController()
    if not arm.connect():
        return

    print("\n=== ARM TEST ===")

    # Home
    print("Going home...")
    arm.home()
    time.sleep(1)

    # Test positions
    for pos in ["pickup", "scan", "drop_value", "drop_bulk", "home"]:
        print(f"\nTesting: {pos}")
        arm.go_to(pos)
        time.sleep(1)

    # Test grab/release
    print("\nTesting grab...")
    arm.grab()
    time.sleep(1)
    arm.release()

    print("\n=== TEST COMPLETE ===")
    arm.disconnect()


if __name__ == "__main__":
    test_arm()
