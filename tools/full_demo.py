#!/usr/bin/env python3
"""
NEXUS COMPLETE DEMO - ONE SHOT
Robot picks card → Scan → Identify → Place

This is the FULL end-to-end demo Kevin wants to see.
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nexus_v2.hardware.arm_controller import NexusArm
from nexus_v2.scanner.universal_card_router import identify_and_mint
import cv2
import requests


class FullNexusDemo:
    """Complete NEXUS demo - robot arm + scanner + identification"""

    def __init__(self, simulation=False):
        self.simulation = simulation

        # Initialize robot arm
        print("\n" + "="*60)
        print("INITIALIZING NEXUS COMPLETE DEMO")
        print("="*60)

        print("\n[1/3] Connecting to robot arm...")
        self.arm = NexusArm(simulation=simulation)
        if self.arm.connect():
            print("  ✓ Robot arm connected")
        else:
            print("  ⚠ Robot arm connection failed - continuing in simulation")
            self.simulation = True

        # Camera setup (using OpenCV for now)
        print("\n[2/3] Initializing camera...")
        if not simulation:
            self.camera = cv2.VideoCapture(0)
            if self.camera.isOpened():
                print("  ✓ Camera ready")
            else:
                print("  ⚠ Camera failed - using simulation")
                self.simulation = True
                self.camera = None
        else:
            self.camera = None

        # Scanner API
        print("\n[3/3] Checking scanner API...")
        self.scanner_api = "http://192.168.1.152:8000"
        try:
            r = requests.get(f"{self.scanner_api}/api/health", timeout=3)
            if r.status_code == 200:
                print(f"  ✓ Scanner API online at {self.scanner_api}")
            else:
                print("  ⚠ Scanner API not responding")
        except:
            print("  ⚠ Scanner API not reachable (offline mode)")

        print("\n" + "="*60)
        print("NEXUS READY - LET'S GO! 🚀")
        print("="*60)

    def capture_image(self, save_path="temp_scan.jpg"):
        """Capture image from camera"""
        if self.simulation:
            print("  [SIM] Capturing image...")
            # Use test image
            test_image = Path(__file__).parent.parent / "test_data" / "test_card.jpg"
            if test_image.exists():
                return str(test_image)
            else:
                print("  ⚠ No test image found, using placeholder")
                return None

        print("  📸 Capturing image...")
        ret, frame = self.camera.read()
        if ret:
            cv2.imwrite(save_path, frame)
            print(f"  ✓ Saved to {save_path}")
            return save_path
        else:
            print("  ✗ Capture failed")
            return None

    def identify_card(self, image_path):
        """Send image to NEXUS API for identification"""
        if self.simulation:
            print("  [SIM] Identifying card...")
            return {
                'success': True,
                'card': {
                    'name': 'Lightning Bolt',
                    'set_code': 'LEA',
                    'card_type': 'mtg',
                    'price_usd': 250.00,
                    'rarity': 'Common',
                    'confidence': 98
                },
                'confidence': 98
            }

        print("  🔍 Sending to NEXUS API...")
        try:
            with open(image_path, 'rb') as f:
                files = {'image': f}
                r = requests.post(
                    f"{self.scanner_api}/api/identify",
                    files=files,
                    timeout=30
                )

            if r.status_code == 200:
                result = r.json()
                print(f"  ✓ Identified: {result.get('name', 'Unknown')}")
                return result
            else:
                print(f"  ✗ API error: {r.status_code}")
                return None

        except Exception as e:
            print(f"  ✗ Identification failed: {e}")
            return None

    def determine_bin(self, card_result):
        """Determine which bin to place card in based on value"""
        if not card_result or not card_result.get('success'):
            return 8  # Reject bin

        card = card_result.get('card', {})
        price = card.get('price_usd', 0)

        if price >= 50:
            return 1  # High value bin
        elif price >= 10:
            return 2  # Medium value bin
        elif price >= 1:
            return 3  # Bulk rare bin
        elif price >= 0.25:
            return 4  # Bulk uncommon bin
        else:
            return 5  # Bulk common bin

    def run_demo(self):
        """RUN THE COMPLETE DEMO - ONE SHOT!"""

        print("\n" + "█"*60)
        print("█" + " "*58 + "█")
        print("█" + "  NEXUS COMPLETE DEMO - STARTING NOW!".center(58) + "█")
        print("█" + " "*58 + "█")
        print("█"*60)

        input("\nPress ENTER to start the demo...")

        try:
            # STEP 1: HOME POSITION
            print("\n" + "─"*60)
            print("STEP 1: MOVING TO HOME POSITION")
            print("─"*60)
            self.arm.home()
            time.sleep(1)

            # STEP 2: PICK UP CARD
            print("\n" + "─"*60)
            print("STEP 2: PICKING UP CARD FROM SCANNER")
            print("─"*60)
            success = self.arm.pick_from_scanner()
            if not success:
                print("  ✗ Failed to pick card - aborting demo")
                return False
            print("  ✓ Card picked up!")
            time.sleep(0.5)

            # STEP 3: MOVE TO SCAN POSITION
            print("\n" + "─"*60)
            print("STEP 3: POSITIONING FOR SCAN")
            print("─"*60)
            self.arm.goto_waypoint('scanner_above')
            time.sleep(0.5)

            # STEP 4: CAPTURE IMAGE
            print("\n" + "─"*60)
            print("STEP 4: CAPTURING CARD IMAGE")
            print("─"*60)
            image_path = self.capture_image()
            if not image_path:
                print("  ✗ Failed to capture image - aborting")
                return False
            time.sleep(0.5)

            # STEP 5: IDENTIFY CARD
            print("\n" + "─"*60)
            print("STEP 5: IDENTIFYING CARD")
            print("─"*60)
            result = self.identify_card(image_path)

            if result and result.get('success'):
                card = result['card']
                print(f"\n  ✅ CARD IDENTIFIED!")
                print(f"     Name: {card['name']}")
                print(f"     Set: {card.get('set_code', 'N/A')}")
                print(f"     Price: ${card.get('price_usd', 0):.2f}")
                print(f"     Confidence: {result['confidence']}%")

                # STEP 6: DETERMINE BIN
                print("\n" + "─"*60)
                print("STEP 6: ROUTING TO APPROPRIATE BIN")
                print("─"*60)
                bin_number = self.determine_bin(result)
                print(f"  → Routing to Bin #{bin_number}")

                # STEP 7: PLACE CARD IN BIN
                print("\n" + "─"*60)
                print(f"STEP 7: PLACING CARD IN BIN #{bin_number}")
                print("─"*60)
                self.arm.goto_waypoint('safe')  # Safe travel position
                success = self.arm.place_in_bin(bin_number)
                if success:
                    print(f"  ✓ Card placed in bin #{bin_number}!")
                else:
                    print(f"  ✗ Failed to place card")
                    return False

            else:
                print("  ✗ Card identification failed")
                print("  → Routing to reject bin")
                self.arm.place_in_bin(8)  # Reject bin

            # STEP 8: RETURN HOME
            print("\n" + "─"*60)
            print("STEP 8: RETURNING TO HOME POSITION")
            print("─"*60)
            self.arm.home()

            # DEMO COMPLETE!
            print("\n" + "█"*60)
            print("█" + " "*58 + "█")
            print("█" + "  DEMO COMPLETE! ✅".center(58) + "█")
            print("█" + " "*58 + "█")
            print("█"*60)

            if result and result.get('success'):
                card = result['card']
                print(f"\nScanned: {card['name']} - ${card.get('price_usd', 0):.2f}")
                print(f"Sorted to Bin #{bin_number}")

            return True

        except KeyboardInterrupt:
            print("\n\n⚠️ Demo interrupted by user")
            return False

        except Exception as e:
            print(f"\n\n✗ Demo failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # Cleanup
            if self.camera:
                self.camera.release()
            print("\n✓ Demo cleanup complete")

    def run_continuous(self):
        """Run continuous sorting loop"""
        print("\n" + "█"*60)
        print("█" + " "*58 + "█")
        print("█" + "  NEXUS CONTINUOUS MODE".center(58) + "█")
        print("█" + " "*58 + "█")
        print("█"*60)

        card_count = 0

        try:
            while True:
                card_count += 1
                print(f"\n\n{'='*60}")
                print(f"CARD #{card_count}")
                print(f"{'='*60}")

                input(f"\nPlace card on scanner, then press ENTER...")

                if not self.run_demo():
                    print("  ✗ Card failed - continuing...")

                print(f"\n  Total cards processed: {card_count}")

                again = input("\nSort another card? (y/n): ").strip().lower()
                if again != 'y':
                    break

        except KeyboardInterrupt:
            print("\n\n⚠️ Continuous mode stopped")

        print(f"\n✓ Session complete - processed {card_count} cards")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='NEXUS Complete Demo')
    parser.add_argument('--sim', action='store_true', help='Run in simulation mode')
    parser.add_argument('--continuous', action='store_true', help='Run continuous sorting')

    args = parser.parse_args()

    demo = FullNexusDemo(simulation=args.sim)

    if args.continuous:
        demo.run_continuous()
    else:
        demo.run_demo()


if __name__ == '__main__':
    main()
