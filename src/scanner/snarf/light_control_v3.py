#!/usr/bin/env python3
"""
NEXUS Light Control V3
======================
ESP32 LED/Light control for scanner photography via USB serial.

Hardware:
- ESP32 connected via USB to SNARF
- Controls camera lighting for light box photography

Serial Commands:
- LIGHTS_ON\n  - Turn on lights for photography
- LIGHTS_OFF\n - Turn off lights
- STATUS\n     - Get light status

Patent Pending - Kevin Caracozza
Version: 3.0 (Feb 2026)
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional


class LightControlV3:
    """Control ESP32 photography lights via USB serial"""

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        """
        Initialize light control.

        Args:
            port: Serial port (auto-detected if None)
            baudrate: Serial baud rate (default 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.lights_on = False

    def connect(self) -> bool:
        """
        Connect to ESP32 via USB serial.

        Returns:
            True if connected successfully
        """
        if self.port is None:
            # Auto-detect ESP32
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                # ESP32 typically shows as CP210x or CH340
                if any(x in p.description.upper() for x in ['CP210', 'CH340', 'USB', 'ESP32']):
                    self.port = p.device
                    print(f"[LIGHTS] Found ESP32 at {self.port}")
                    break

            if self.port is None:
                print("[LIGHTS] ERROR: ESP32 not found")
                print(f"[LIGHTS] Available ports: {[p.device for p in ports]}")
                return False

        try:
            print(f"[LIGHTS] Connecting to {self.port} @ {self.baudrate}...")
            self.serial = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)  # Wait for ESP32 boot/reset

            # Flush any startup messages
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            # Test connection
            status = self.get_status()
            if status is not None:
                self.connected = True
                print(f"[LIGHTS] Connected! Status: {status}")
                return True
            else:
                print("[LIGHTS] Connection test failed")
                return False

        except Exception as e:
            print(f"[LIGHTS] Connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from ESP32"""
        if self.serial and self.serial.is_open:
            self.lights_off()  # Turn off lights before disconnect
            self.serial.close()
        self.connected = False
        print("[LIGHTS] Disconnected")

    def send_command(self, cmd: str) -> Optional[str]:
        """
        Send command to ESP32.

        Args:
            cmd: Command string (without newline)

        Returns:
            Response string or None if error
        """
        if not self.connected:
            if not self.connect():
                return None

        try:
            # Send command
            self.serial.write(f"{cmd}\n".encode())
            time.sleep(0.1)

            # Read response
            if self.serial.in_waiting:
                response = self.serial.readline().decode('utf-8', errors='ignore').strip()
                return response
            return ""

        except Exception as e:
            print(f"[LIGHTS] Send error: {e}")
            self.connected = False
            return None

    def lights_on(self) -> bool:
        """
        Turn on photography lights.

        Returns:
            True if successful
        """
        response = self.send_command("LIGHTS_ON")
        if response is not None:
            self.lights_on = True
            print("[LIGHTS] ✓ Lights ON")
            return True
        else:
            print("[LIGHTS] ✗ Failed to turn on lights")
            return False

    def lights_off(self) -> bool:
        """
        Turn off photography lights.

        Returns:
            True if successful
        """
        response = self.send_command("LIGHTS_OFF")
        if response is not None:
            self.lights_on = False
            print("[LIGHTS] ✓ Lights OFF")
            return True
        else:
            print("[LIGHTS] ✗ Failed to turn off lights")
            return False

    def get_status(self) -> Optional[str]:
        """
        Get light status from ESP32.

        Returns:
            Status string or None if error
        """
        return self.send_command("STATUS")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# =============================================================================
# Standalone test
# =============================================================================

def test_lights():
    """Test light control"""
    print("=" * 60)
    print("NEXUS Light Control V3 - Test")
    print("=" * 60)

    with LightControlV3() as lights:
        if not lights.connected:
            print("ERROR: Could not connect to ESP32")
            return

        # Test sequence
        print("\nTest sequence:")

        print("\n1. Turn lights ON")
        lights.lights_on()
        time.sleep(2)

        print("\n2. Turn lights OFF")
        lights.lights_off()
        time.sleep(1)

        print("\n3. Blink test (3 times)")
        for i in range(3):
            print(f"   Blink {i+1}/3")
            lights.lights_on()
            time.sleep(0.5)
            lights.lights_off()
            time.sleep(0.5)

        print("\n4. Final status check")
        status = lights.get_status()
        print(f"   Status: {status}")

    print("\nTest complete!")


if __name__ == "__main__":
    test_lights()
