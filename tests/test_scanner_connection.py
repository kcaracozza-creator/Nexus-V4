#!/usr/bin/env python3
"""
Test Arduino scanner connection
"""
import serial
import serial.tools.list_ports
import time

def test_arduino_connection():
    print("=== ARDUINO SCANNER CONNECTION TEST ===")
    print()
    
    # List available ports
    ports = serial.tools.list_ports.comports()
    print("Available COM ports:")
    for p in ports:
        print(f"  {p.device} - {p.description}")
    print()
    
    # Test COM1 connection
    print("Testing COM1 connection:")
    try:
        ser = serial.Serial('COM1', 9600, timeout=2)
        print("✅ COM1 opened successfully")
        
        # Send test command
        test_cmd = b"test\n"
        ser.write(test_cmd)
        print(f"📤 Sent: {test_cmd}")
        
        # Wait for response
        time.sleep(1)
        if ser.in_waiting > 0:
            response = ser.readline().decode().strip()
            print(f"📥 Received: {response}")
        else:
            print("⏳ No response from Arduino")
        
        ser.close()
        print("✅ Connection test complete")
        
    except Exception as e:
        print(f"❌ COM1 connection failed: {e}")

if __name__ == "__main__":
    test_arduino_connection()