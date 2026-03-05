#!/usr/bin/env python3
"""
NEXUS Arm Remote Calibration Helper
Run on DANIELSON — controlled via SSH from Windows.
Moves one joint at a time, prints state, waits for next command via stdin.
"""
import serial
import json
import time
import sys

PORT = "/dev/nexus_arm"
BAUD = 115200

class ArmCal:
    def __init__(self):
        self.ser = serial.Serial(PORT, BAUD, timeout=2)
        time.sleep(2)
        self.ser.reset_input_buffer()
        # Current state
        self.base = 0
        self.shoulder = 90
        self.elbow = 90
        self.wrist1 = 90
        self.wrist2 = 90
        self.vacuum = False
