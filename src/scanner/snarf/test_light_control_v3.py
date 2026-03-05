#!/usr/bin/env python3
"""
Test script for NEXUS Light Control V3
Verifies USB serial communication with ESP32 light controller
"""

import sys
import time
from light_control_v3 import LightControlV3


def main():
    print("=" * 60)
    print("NEXUS Light Control V3 - Communication Test")
    print("=" * 60)
    print()

    # Initialize light controller
    print("[1/5] Initializing light controller...")
    lights = LightControlV3()

    # Connect to ESP32
    print("[2/5] Connecting to ESP32 via USB...")
    if not lights.connect():
        print("✗ ERROR: Failed to connect to ESP32")
        print("\nTroubleshooting:")
        print("- Check USB cable connection")
        print("- Verify ESP32 firmware is uploaded")
        print("- Check that no other program is using the serial port")
        sys.exit(1)

    print("✓ Connected successfully")
    print()

    try:
        # Test STATUS command
        print("[3/5] Testing STATUS command...")
        status = lights.get_status()
        if status:
            print(f"✓ Status: {status}")
        else:
            print("✗ WARNING: No status response")
        print()

        # Test LIGHTS_ON command
        print("[4/5] Testing LIGHTS_ON command...")
        if lights.lights_on():
            print("✓ Lights turned ON")
        else:
            print("✗ ERROR: Failed to turn lights on")
        time.sleep(2)
        print()

        # Test LIGHTS_OFF command
        print("[5/5] Testing LIGHTS_OFF command...")
        if lights.lights_off():
            print("✓ Lights turned OFF")
        else:
            print("✗ ERROR: Failed to turn lights off")
        print()

        # Blink test
        print("[BONUS] Running blink test (5 cycles)...")
        for i in range(5):
            print(f"  Cycle {i+1}/5...")
            lights.lights_on()
            time.sleep(0.3)
            lights.lights_off()
            time.sleep(0.3)
        print("✓ Blink test complete")
        print()

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test stopped by user")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
    finally:
        # Always disconnect cleanly
        print("\nDisconnecting...")
        lights.disconnect()

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
