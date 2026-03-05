"""
NEXUS Auto Scan
===============
Pick card from hopper, scan, place in box.

Flow:
1. Arm picks card from hopper
2. Move to scan position
3. Camera scans + OCR identifies
4. Arm places card in box
5. Repeat
"""

import time
import requests
from .arm_control import ArmController, POSITIONS

# Scanner API
BROCK_URL = "http://192.168.1.219:5001"

# Update positions for hopper/box workflow
POSITIONS.update({
    "hopper": {"shoulder": -600, "base": 0, "wrist": 60, "grabber": 90, "elbow": 130},
    "scan": {"shoulder": -300, "base": 0, "wrist": 90, "grabber": 90, "elbow": 90},
    "box": {"shoulder": -600, "base": 300, "wrist": 60, "grabber": 90, "elbow": 130},
})


class AutoScan:
    """Automated card scanning"""

    def __init__(self):
        self.arm = ArmController()
        self.scanned = 0
        self.total_value = 0.0

    def connect(self):
        return self.arm.connect()

    def disconnect(self):
        self.arm.disconnect()

    def scan_card(self):
        """Trigger scan and get card info"""
        try:
            r = requests.post(f"{BROCK_URL}/api/scan", timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"Scan error: {e}")
        return None

    def cycle(self):
        """Single scan cycle: hopper -> scan -> box"""
        # Pick from hopper
        print("Pick from hopper...")
        self.arm.go_to("hopper")
        time.sleep(0.3)
        self.arm.grab()
        time.sleep(0.3)

        # Move to scan
        print("Scanning...")
        self.arm.go_to("scan")
        time.sleep(0.5)

        # Scan
        card = self.scan_card()
        if card:
            name = card.get("name", "Unknown")
            price = card.get("price", 0.0)
            print(f"  -> {name} (${price:.2f})")
            self.scanned += 1
            self.total_value += price
        else:
            print("  -> Scan failed")

        # Place in box
        print("Place in box...")
        self.arm.go_to("box")
        time.sleep(0.3)
        self.arm.release()
        time.sleep(0.2)

        # Return to home
        self.arm.go_to("home")
        return card

    def run(self, count=None):
        """Run scan loop"""
        print("=" * 40)
        print("NEXUS Auto Scan")
        print("Hopper -> Scan -> Box")
        print("=" * 40)

        if not self.connect():
            print("Failed to connect to arm")
            return

        try:
            i = 0
            while True:
                print(f"\n--- Card {i+1} ---")
                self.cycle()
                i += 1

                if count and i >= count:
                    break

                # Brief pause between cards
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\nStopping...")

        finally:
            self.arm.home()
            self.disconnect()
            print(f"\nScanned: {self.scanned} cards")
            print(f"Total value: ${self.total_value:.2f}")


if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    scanner = AutoScan()
    scanner.run(count)
