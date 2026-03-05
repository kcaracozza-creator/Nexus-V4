"""
NEXUS Auto Sort
===============
Automated card scanning and sorting.

Flow:
1. Arm picks card from scanner
2. Camera scans card (via Brock/Snarf)
3. OCR identifies card + gets price
4. Arm sorts to value/bulk bin based on threshold
"""

import time
import requests
from .arm_control import ArmController

# Scanner APIs
BROCK_URL = "http://192.168.1.219:5001"  # OCR + AI (DANIELSON)
SNARF_URL = "http://192.168.1.219:5001"  # Hardware/Camera (DANIELSON)

# Sort threshold (cards above this go to value bin)
VALUE_THRESHOLD = 5.00  # $5+


class AutoSort:
    """Automated card sorting system"""

    def __init__(self, value_threshold=VALUE_THRESHOLD):
        self.arm = ArmController()
        self.threshold = value_threshold
        self.stats = {
            "scanned": 0,
            "value": 0,
            "bulk": 0,
            "errors": 0,
            "total_value": 0.0
        }

    def connect(self):
        """Connect to arm"""
        return self.arm.connect()

    def disconnect(self):
        """Disconnect from arm"""
        self.arm.disconnect()

    def scan_card(self):
        """Trigger scan and get card info"""
        try:
            # Trigger scan on Brock (primary OCR)
            r = requests.post(f"{BROCK_URL}/api/scan", timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "name": data.get("name", "Unknown"),
                    "set": data.get("set", ""),
                    "price": data.get("price", 0.0),
                    "confidence": data.get("confidence", 0.0)
                }
        except Exception as e:
            print(f"Scan error: {e}")
        return None

    def sort_card(self, card_info):
        """Sort card based on value"""
        if card_info is None:
            # Unknown card - send to bulk
            self.arm.drop_card(valuable=False)
            self.stats["errors"] += 1
            return False

        price = card_info.get("price", 0.0)
        name = card_info.get("name", "Unknown")
        valuable = price >= self.threshold

        print(f"  {name}: ${price:.2f} -> {'VALUE' if valuable else 'BULK'}")

        self.arm.drop_card(valuable=valuable)

        # Update stats
        self.stats["scanned"] += 1
        self.stats["total_value"] += price
        if valuable:
            self.stats["value"] += 1
        else:
            self.stats["bulk"] += 1

        return True

    def sort_cycle(self):
        """Single pick-scan-sort cycle"""
        print("\n--- Sort Cycle ---")

        # Pick card
        print("Picking card...")
        self.arm.pick_card()
        time.sleep(0.5)

        # Move to scan position
        print("Scanning...")
        self.arm.go_to("scan")
        time.sleep(0.3)

        # Scan
        card_info = self.scan_card()

        # Sort
        self.sort_card(card_info)

        return card_info

    def run(self, count=None, continuous=False):
        """Run sorting loop"""
        print("=" * 40)
        print("NEXUS Auto Sort")
        print(f"Value threshold: ${self.threshold:.2f}")
        print("=" * 40)

        if not self.connect():
            print("Failed to connect to arm")
            return

        try:
            i = 0
            while True:
                self.sort_cycle()
                i += 1

                # Print stats every 10 cards
                if i % 10 == 0:
                    self.print_stats()

                # Check exit conditions
                if count and i >= count:
                    break
                if not continuous:
                    input("Press Enter for next card (Ctrl+C to stop)...")

        except KeyboardInterrupt:
            print("\nStopping...")

        finally:
            self.arm.home()
            self.disconnect()
            self.print_stats()

    def print_stats(self):
        """Print sorting statistics"""
        s = self.stats
        print(f"\n--- Stats ---")
        print(f"Scanned: {s['scanned']}")
        print(f"Value: {s['value']} | Bulk: {s['bulk']} | Errors: {s['errors']}")
        print(f"Total value: ${s['total_value']:.2f}")
        if s['scanned'] > 0:
            avg = s['total_value'] / s['scanned']
            print(f"Average: ${avg:.2f}/card")


def main():
    """Run auto sort"""
    import argparse
    parser = argparse.ArgumentParser(description="NEXUS Auto Sort")
    parser.add_argument("-n", "--count", type=int, help="Number of cards to sort")
    parser.add_argument("-t", "--threshold", type=float, default=5.0, help="Value threshold ($)")
    parser.add_argument("-c", "--continuous", action="store_true", help="Run continuously")
    args = parser.parse_args()

    sorter = AutoSort(value_threshold=args.threshold)
    sorter.run(count=args.count, continuous=args.continuous)


if __name__ == "__main__":
    main()
