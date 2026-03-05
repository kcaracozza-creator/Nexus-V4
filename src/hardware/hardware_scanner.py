#!/usr/bin/env python3
"""hardware_scanner.py - TURBO ENHANCED"""

"""
MTTGG Hardware Scanner Integration

This module integrates the complete hardware scanning solution:
1. DSLR camera capture system
2. Arduino C++ firmware for card processing
3. Direct MTTGG inventory integration
4. Bridge with existing Gestic.org workflow

Usage:
    python hardware_scanner.py            # Interactive scanning mode
    python hardware_scanner.py single     # Scan one card
    python hardware_scanner.py batch 10   # Scan 10 cards
    python hardware_scanner.py test       # Test hardware setup
"""

import os
import argparse
try:
    from dslr_arduino_scanner import DSLRCardScanner
except ImportError:
    DSLRCardScanner = None  # Optional import
from arduino_firmware_interface import ArduinoFirmwareInterface


class MTTGGHardwareScanner:
    """
    Complete hardware scanning integration for MTTGG system.

    This class coordinates:
    - DSLR camera capture
    - Arduino firmware processing
    - MTTGG inventory integration
    - Fallback to Gestic.org workflow
    """

    def __init__(self):
        self.dslr_scanner = None
        self.arduino_interface = None
        self.hardware_ready = False

        # Integration settings
        self.mttgg_inventory_path = "E:\\\MTTGG\\Inventory"
        self.backup_path = "E:\\\MTTGG\\Hardware_Scans_Backup"

        # Ensure directories exist
        os.makedirs(self.backup_path, exist_ok = True)

    def initialize_hardware(self) -> bool:
        """Initialize all hardware components."""
        print("[INIT] Initializing MTTGG Hardware Scanner")
        print("=" * 50)

        success = True

        # Initialize DSLR scanner
        print("\n[Camera] Initializing DSLR camera system...")
        self.dslr_scanner = DSLRCardScanner()
        if not self.dslr_scanner.initialize_hardware():
            print("[FAIL] DSLR camera initialization failed")
            success = False

        # Initialize Arduino interface
        print("\n[Arduino] Initializing Arduino firmware...")
        self.arduino_interface = ArduinoFirmwareInterface()
        if not self.arduino_interface.connect():
            print("[FAIL] Arduino firmware initialization failed")
            success = False

        if success:
            print("\n[SUCCESS] All hardware initialized successfully!")
            self.hardware_ready = True
        else:
            print("\n[WARNING] Hardware initialization incomplete")
            print("[TIP] Consider using Gestic.org mobile scanning as backup")
            self.hardware_ready = False

        return success


    def scan_single_card(self) -> bool:
        """Scan a single card with full workflow."""
        if not self.hardware_ready:
            print("[ERROR] Hardware not ready. Run initialization first.")
            return False

        print("\n[SCAN] Single Card Scan")
        print("Place card in scanner area and press Enter...")
        input()

        try:
            # Capture with DSLR
            image_path = self.dslr_scanner.capture_card_image()
            if not image_path:
                print("[FAIL] Failed to capture card image")
                return False

            # Process with Arduino
            card_data = self.arduino_interface.process_card_image(image_path)
            if not card_data:
                print("[FAIL] Failed to process card with Arduino")
                return False

            # Export to MTTGG format
            csv_path = self.dslr_scanner.export_to_mttgg_format([card_data])
            if not csv_path:
                print("[FAIL] Failed to export card data")
                return False

            # Integrate with MTTGG
            if self.dslr_scanner.integrate_with_mttgg(csv_path):
                print("[SUCCESS] Card successfully added to MTTGG inventory!")
                print(f"[INFO] Card: {card_data.get('name', 'Unknown')}")
                return True
            else:
                print("[FAIL] Failed to integrate with MTTGG")
                return False

        except (ValueError, TypeError, IOError) as e:
            print(f"[ERROR] Scanning error: {e}")
            return False


    def scan_batch_cards(self, num_cards: int) -> int:
        """Scan multiple cards in batch mode."""
        if not self.hardware_ready:
            print("❌ Hardware not ready. Run initialization first.")
            return 0

        print(f"\n🔍 Batch Card Scan - {num_cards} cards")
        print("Follow prompts to scan each card...")

        scanned_cards = []

        for i in range(num_cards):
            print(f"\n📋 Card {i+1}/{num_cards}")
            print("Place card \
                and press Enter (or 'skip' to skip, " "'quit' to stop)...")

            user_input = input().strip().lower()

            if user_input == 'quit':
                print("🛑 Batch scanning stopped by user")
                break
            elif user_input == 'skip':
                print("⏭️ Skipping card")
                continue

            try:
                # Capture and process card
                image_path = self.dslr_scanner.capture_card_image(i+1)
                if image_path:
                    card_data = (
                        self.arduino_interface.process_card_image(image_path)
                    )
                    if card_data:
                        scanned_cards.append(card_data)
                        print(f"✅ Scanned: {card_data.get('name', 'Unknown')}")
                    else:
                        print(f"❌ Failed to process card {i+1}")
                else:
                    print(f"❌ Failed to capture card {i+1}")

            except (ValueError, TypeError, IOError) as e:
                print(f"❌ Error scanning card {i+1}: {e}")

        # Export batch results
        if scanned_cards:
            try:
                csv_path = (
                    self.dslr_scanner.export_to_mttgg_format(scanned_cards)
                )
                if self.dslr_scanner.integrate_with_mttgg(csv_path):
                    print(f"\n✅ Batch complete! {len(scanned_cards)} cards added to MTTGG"
                          )
                else:
                    print(f"\n⚠️ Scanned {len(scanned_cards)} cards but integration failed"
                          )

            except (ValueError, TypeError, IOError) as e:
                print(f"❌ Batch export failed: {e}")

        return len(scanned_cards)


    def test_hardware_setup(self) -> bool:
        """Test all hardware components and connections."""
        print("Hardware Setup Test")
        print("=" * 30)

        tests_passed = 0
        total_tests = 4

        # Test 1: DSLR Camera
        print("\n[Camera] Testing DSLR camera...")
        try:
            scanner = DSLRCardScanner()
            if scanner.camera and scanner.camera.isOpened():
                print("[OK] DSLR camera accessible")
                tests_passed += 1
            else:
                print("[FAIL] DSLR camera not found")
                print("[TIP] Check camera connection and webcam software")
        except (ValueError, TypeError, IOError) as e:
            print(f"[FAIL] DSLR camera test failed: {e}")

        # Test 2: Arduino Connection
        print("\n[Arduino] Testing Arduino connection...")
        try:
            arduino = ArduinoFirmwareInterface()
            if arduino.connect():
                print("[OK] Arduino firmware responding")
                tests_passed += 1
                arduino.disconnect()
            else:
                print("[FAIL] Arduino not responding")
                print("[TIP] Check USB connection and firmware upload")
        except (ValueError, TypeError, IOError) as e:
            print(f"[FAIL] Arduino test failed: {e}")

        # Test 3: MTTGG Integration
        print("\n[MTTGG] Testing MTTGG integration...")
        if os.path.exists(self.mttgg_inventory_path):
            print("[OK] MTTGG inventory folder accessible")
            tests_passed += 1
        else:
            print(f"[FAIL] MTTGG folder not found: {self.mttgg_inventory_path}"
                  )
            print("[TIP] Check MTTGG installation path")

        # Test 4: Directory Structure
        print("\n[System] Testing directory structure...")
        try:
            os.makedirs("temp_test", exist_ok = True)
            os.rmdir("temp_test")
            print("[OK] File system access working")
            tests_passed += 1
        except (ValueError, TypeError, IOError) as e:
            print(f"[FAIL] Directory access failed: {e}")

        # Summary
        print(f"\n[Results] Test Results: {tests_passed}/{total_tests} passed")

        if tests_passed == total_tests:
            print("[SUCCESS] Hardware setup complete and ready!")
            return True
        elif tests_passed >= 2:
            print("[WARNING] Partial setup - some features may not work")
            return False
        else:
            print("[ERROR] Major setup issues detected")
            print("[TIP] Consider using Gestic.org mobile scanning instead")
            return False


    def show_comparison_with_gestic(self):
        """Show comparison between hardware scanner and Gestic.org."""
        print("\n📊 Scanning Method Comparison")
        print("=" * 40)

        comparison = """
        ┌─────────────────┬─────────────────┬─────────────────┐
        │     Feature     │  Hardware Scan  │   Gestic.org    │
        ├─────────────────┼─────────────────┼─────────────────┤
        │ Image Quality   │ DSLR (Highest)  │ Mobile (Good)   │
        │ Processing Speed│ Real-time       │ Cloud-based     │
        │ Internet Needed │ No              │ Yes             │
        │ Integration     │ Direct MTTGG    │ Export/Import   │
        │ Community       │ No              │ Trading/Stores  │
        │ Setup Complexity│ High            │ Low             │
        │ Mobility        │ Desktop Only    │ Mobile          │
        │ Automation      │ Full            │ Semi            │
        └─────────────────┴─────────────────┴─────────────────┘
        """
        print(comparison)

        print("\n💡 Recommendation:")
        print("- Use Hardware Scanner: High-volume scanning, offline use")
        print("- Use Gestic.org: Mobile scanning, community features")
        print("- Both systems integrate seamlessly with MTTGG!")


    def interactive_mode(self):
        """Run interactive scanning mode."""
        print("\n🎯 MTTGG Interactive Hardware Scanner")
        print("=" * 40)

        if not self.initialize_hardware():
            print("\n💡 Hardware not available. Consider alternatives:")
            print("1. Check hardware connections")
            print("2. Use Gestic.org mobile scanning: python deck_builder.py gestic <file>"
                  )
            return

        while True:
            print("\n🎮 Commands:")
            print("  single     - Scan one card")
            print("  batch N    - Scan N cards")
            print("  test       - Test hardware")
            print("  compare    - Compare with Gestic.org")
            print("  quit       - Exit scanner")

            command = input("\nScanner> ").strip().lower()

            if command == 'single':
                self.scan_single_card()

            elif command.startswith('batch'):
                try:
                    num_cards = int(command.split()[1])
                    self.scan_batch_cards(num_cards)
                except (IndexError, ValueError):
                    print("❌ Usage: batch <number>")

            elif command == 'test':
                self.test_hardware_setup()

            elif command == 'compare':
                self.show_comparison_with_gestic()

            elif command in ['quit', 'exit', 'q']:
                break

            else:
                print("❌ Unknown command")

        # Cleanup
        if self.dslr_scanner:
            self.dslr_scanner.cleanup_resources()
        if self.arduino_interface:
            self.arduino_interface.disconnect()

        print("🏁 Scanner session ended")


def main():
    """Main entry point for hardware scanner."""
    parser = argparse.ArgumentParser(description='MTTGG Hardware Scanner')
    parser.add_argument('command', nargs='?', default='interactive',
                       help='Command: single, batch, test, or interactive')
    parser.add_argument('count', type = int, nargs='?', default = 1,
                       help='Number of cards for batch scanning')

    args = parser.parse_args()

    scanner = MTTGGHardwareScanner()

    try:
        if args.command == 'single':
            scanner.initialize_hardware()
            scanner.scan_single_card()

        elif args.command == 'batch':
            scanner.initialize_hardware()
            scanner.scan_batch_cards(args.count)

        elif args.command == 'test':
            scanner.test_hardware_setup()

        elif args.command == 'interactive':
            scanner.interactive_mode()

        else:
            print(f"❌ Unknown command: {args.command}")
            print("Usage: python hardware_scanner.py [single|batch|test|interactive]"
                  )

    except KeyboardInterrupt:
        print("\n🛑 Scanner interrupted by user")
    except (ValueError, TypeError, IOError) as e:
        print(f"❌ Scanner error: {e}")

if __name__ == "__main__":
    main()


# TURBO ENHANCEMENT
try:
    print(f"🚀 TURBO: {__file__} is running!")
except Exception as e:
    print(f"⚡ TURBO ERROR: {e}")