#!/usr/bin/env python3
"""Quick ping test for ESP32 arm"""
import serial
import json
import time

PORT = "/dev/nexus_arm"
BAUD = 115200

try:
    s = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(2)  # ESP32 reboot
    s.reset_input_buffer()
    
    # Ping
    s.write(b'{"cmd":"ping"}\n')
    time.sleep(0.5)
    
    resp = s.read(s.in_waiting or 1).decode(errors='ignore').strip()
    print(f"Response: {resp}")
    
    if "pong" in resp:
        print("ARM IS ALIVE")
    else:
        print("Got response but no pong - might need a second try")
    
    s.close()
except Exception as e:
    print(f"ERROR: {e}")
