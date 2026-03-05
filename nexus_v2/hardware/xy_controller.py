#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XY Axis Scanner Controller - Dual Lead Screw System
Controls automated card positioning with stepper motors
"""

import serial
import time
import json
from typing import Tuple, List, Optional
from pathlib import Path

class XYScannerController:
    """
    Controls XY axis scanner with dual lead screws
    Positions cards precisely for camera capture
    """
    
    # Scanner specifications - Creality X003EAOXL1 Kit
    STEPS_PER_REV = 200  # Standard NEMA 17 stepper (1.8° per step)
    MICROSTEPS = 16      # Microstepping (1/16 step)
    LEAD_SCREW_PITCH = 8.0  # mm per revolution (T8 4-start = 8mm lead)
    
    # Card dimensions (Magic: The Gathering standard)
    CARD_WIDTH = 63.5    # mm
    CARD_HEIGHT = 88.9   # mm
    CARD_SPACING = 2.0   # mm gap between cards
    
    # Scanner bed dimensions (for 400mm Creality screws)
    BED_WIDTH = 380.0    # mm (5 cards wide)
    BED_HEIGHT = 380.0   # mm (4 cards tall)
    
    # Movement speeds
    SCAN_SPEED = 20.0    # mm/s for scanning
    RAPID_SPEED = 50.0   # mm/s for rapid moves
    HOMING_SPEED = 10.0  # mm/s for homing
    
    # Acceleration
    ACCELERATION = 500.0  # mm/s²
    
    def __init__(self, port='COM4', baudrate=115200):
        """Initialize XY scanner controller"""
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.current_position = [0.0, 0.0]  # [x, y] in mm
        self.is_homed = False
        self.grid_positions = []
        
        # Connect to Arduino
        self._connect()
    
    def _connect(self):
        """Connect to Arduino controller"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)  # Wait for Arduino reset
            print(f"✅ Connected to XY Scanner on {self.port}")
            
            # Send initialization
            self._send_command("INIT")
            response = self._read_response()
            print(f"   Arduino: {response}")
            
        except serial.SerialException as e:
            print(f"❌ Failed to connect to XY Scanner: {e}")
            raise
    
    def _send_command(self, command: str):
        """Send command to Arduino"""
        if self.serial and self.serial.is_open:
            self.serial.write(f"{command}\n".encode())
            self.serial.flush()
    
    def _read_response(self, timeout=5.0) -> str:
        """Read response from Arduino"""
        if not self.serial or not self.serial.is_open:
            return ""
        
        start_time = time.time()
        response = ""
        
        while time.time() - start_time < timeout:
            if self.serial.in_waiting:
                response = self.serial.readline().decode().strip()
                break
            time.sleep(0.01)
        
        return response
    
    def mm_to_steps(self, mm: float) -> int:
        """Convert millimeters to motor steps"""
        steps_per_mm = (self.STEPS_PER_REV * self.MICROSTEPS) / self.LEAD_SCREW_PITCH
        return int(mm * steps_per_mm)
    
    def steps_to_mm(self, steps: int) -> float:
        """Convert motor steps to millimeters"""
        steps_per_mm = (self.STEPS_PER_REV * self.MICROSTEPS) / self.LEAD_SCREW_PITCH
        return steps / steps_per_mm
    
    def home(self) -> bool:
        """Home both axes to origin (0,0)"""
        print("🏠 Homing XY scanner...")
        
        # Send home command
        self._send_command(f"HOME {self.mm_to_steps(self.HOMING_SPEED)}")
        
        # Wait for homing to complete
        while True:
            response = self._read_response(timeout=30)
            
            if "HOMED" in response:
                self.current_position = [0.0, 0.0]
                self.is_homed = True
                print("✅ Homing complete")
                return True
            
            elif "ERROR" in response:
                print(f"❌ Homing failed: {response}")
                return False
            
            elif response:
                print(f"   {response}")
        
        return False
    
    def move_to(self, x: float, y: float, speed: float = None) -> bool:
        """
        Move to absolute position (x, y) in mm
        """
        if not self.is_homed:
            print("⚠️ Scanner not homed! Homing first...")
            if not self.home():
                return False
        
        # Check bounds
        if not (0 <= x <= self.BED_WIDTH and 0 <= y <= self.BED_HEIGHT):
            print(f"❌ Position ({x}, {y}) out of bounds")
            return False
        
        speed = speed or self.SCAN_SPEED
        
        # Calculate delta
        delta_x = x - self.current_position[0]
        delta_y = y - self.current_position[1]
        
        # Convert to steps
        steps_x = self.mm_to_steps(delta_x)
        steps_y = self.mm_to_steps(delta_y)
        steps_speed = self.mm_to_steps(speed)
        
        # Send move command: MOVE X Y SPEED
        command = f"MOVE {steps_x} {steps_y} {steps_speed}"
        self._send_command(command)
        
        # Wait for completion
        response = self._read_response(timeout=30)
        
        if "OK" in response or "DONE" in response:
            self.current_position = [x, y]
            return True
        else:
            print(f"❌ Move failed: {response}")
            return False
    
    def move_relative(self, dx: float, dy: float, speed: float = None) -> bool:
        """Move relative to current position"""
        target_x = self.current_position[0] + dx
        target_y = self.current_position[1] + dy
        return self.move_to(target_x, target_y, speed)
    
    def generate_grid_positions(self, cards_per_row: int = 5, cards_per_col: int = 4) -> List[Tuple[float, float]]:
        """
        Generate grid of card positions for batch scanning
        Default: 5x4 = 20 cards (optimized for Creality 400mm screws)
        Returns list of (x, y) coordinates in mm
        """
        positions = []
        
        x_start = 10.0  # 10mm margin from left
        y_start = 10.0  # 10mm margin from top
        
        for row in range(cards_per_col):
            for col in range(cards_per_row):
                x = x_start + col * (self.CARD_WIDTH + self.CARD_SPACING)
                y = y_start + row * (self.CARD_HEIGHT + self.CARD_SPACING)
                
                # Check if position is within bounds
                if x + self.CARD_WIDTH <= self.BED_WIDTH and y + self.CARD_HEIGHT <= self.BED_HEIGHT:
                    positions.append((x, y))
        
        self.grid_positions = positions
        print(f"📐 Generated {len(positions)} grid positions ({cards_per_row}x{cards_per_col})")
        
        return positions
    
    def scan_card_at_position(self, x: float, y: float, camera_callback=None) -> Optional[dict]:
        """
        Move to position and trigger camera capture
        """
        print(f"📍 Moving to ({x:.1f}, {y:.1f})...")
        
        if not self.move_to(x, y, self.SCAN_SPEED):
            return None
        
        # Wait for vibrations to settle
        time.sleep(0.2)
        
        # Trigger camera capture
        if camera_callback:
            print("📸 Capturing card...")
            result = camera_callback()
            return result
        
        return {'position': (x, y), 'timestamp': time.time()}
    
    def scan_grid(self, camera_callback=None, cards_per_row: int = 5, cards_per_col: int = 4) -> List[dict]:
        """
        Automated grid scan - moves through all positions and captures
        NOTE: For automated shuffler, use individual card processing instead
        """
        print(f"\n{'='*60}")
        print(f"🤖 AUTOMATED GRID SCAN")
        print(f"{'='*60}")
        print(f"Grid: {cards_per_row}x{cards_per_col} = {cards_per_row * cards_per_col} positions")
        print(f"⚠️  This mode assumes cards pre-loaded on grid")
        print(f"💡 For automated feed/sort, use CardShufflerController instead")
        print(f"{'='*60}\n")
        
        # Generate positions
        positions = self.generate_grid_positions(cards_per_row, cards_per_col)
        
        if not positions:
            print("❌ No valid positions generated")
            return []
        
        # Home first
        if not self.is_homed:
            if not self.home():
                return []
        
        # Scan each position
        results = []
        start_time = time.time()
        
        for i, (x, y) in enumerate(positions, 1):
            print(f"\n[{i}/{len(positions)}] Scanning position ({x:.1f}, {y:.1f})")
            
            result = self.scan_card_at_position(x, y, camera_callback)
            
            if result:
                result['position_index'] = i
                result['grid_position'] = (x, y)
                results.append(result)
                print(f"   ✅ Captured")
            else:
                print(f"   ❌ Failed")
        
        # Return to home
        print("\n🏠 Returning to home...")
        self.move_to(0, 0, self.RAPID_SPEED)
        
        duration = time.time() - start_time
        
        print(f"\n{'='*60}")
        print(f"📊 SCAN COMPLETE")
        print(f"{'='*60}")
        print(f"Positions scanned: {len(results)}/{len(positions)}")
        print(f"Duration: {duration:.1f}s")
        print(f"Average: {duration/len(positions):.2f}s per card")
        print(f"{'='*60}\n")
        
        return results
    
    def jog(self, direction: str, distance: float = 10.0):
        """
        Manual jog control
        direction: 'left', 'right', 'up', 'down'
        """
        moves = {
            'left': (-distance, 0),
            'right': (distance, 0),
            'up': (0, distance),
            'down': (0, -distance)
        }
        
        if direction in moves:
            dx, dy = moves[direction]
            return self.move_relative(dx, dy, self.RAPID_SPEED)
        
        return False
    
    def emergency_stop(self):
        """Emergency stop - halt all motion"""
        print("🛑 EMERGENCY STOP")
        self._send_command("STOP")
        response = self._read_response()
        print(f"   {response}")
    
    def get_status(self) -> dict:
        """Get current scanner status"""
        self._send_command("STATUS")
        response = self._read_response()
        
        return {
            'connected': self.serial and self.serial.is_open,
            'homed': self.is_homed,
            'position': self.current_position,
            'grid_positions': len(self.grid_positions),
            'arduino_status': response
        }
    
    def calibrate(self):
        """
        Calibration routine - measures actual movement vs commanded
        """
        print("\n🔧 CALIBRATION ROUTINE")
        print("=" * 60)
        print("This will move the scanner to test positions.")
        print("Measure actual movement and compare to commanded distance.")
        print("=" * 60)
        
        test_distance = 100.0  # mm
        
        # Home first
        if not self.home():
            print("❌ Homing failed")
            return
        
        # Test X axis
        print(f"\n📏 Testing X axis - Moving {test_distance}mm right...")
        input("Press Enter to start...")
        
        self.move_to(test_distance, 0, self.SCAN_SPEED)
        
        actual_x = float(input(f"Measure actual X movement (expected {test_distance}mm): "))
        x_error = actual_x - test_distance
        x_factor = actual_x / test_distance
        
        print(f"   Error: {x_error:+.2f}mm ({x_error/test_distance*100:+.1f}%)")
        print(f"   Correction factor: {x_factor:.4f}")
        
        # Test Y axis
        print(f"\n📏 Testing Y axis - Moving {test_distance}mm up...")
        self.move_to(0, 0, self.RAPID_SPEED)  # Return to origin
        time.sleep(1)
        
        input("Press Enter to start...")
        
        self.move_to(0, test_distance, self.SCAN_SPEED)
        
        actual_y = float(input(f"Measure actual Y movement (expected {test_distance}mm): "))
        y_error = actual_y - test_distance
        y_factor = actual_y / test_distance
        
        print(f"   Error: {y_error:+.2f}mm ({y_error/test_distance*100:+.1f}%)")
        print(f"   Correction factor: {y_factor:.4f}")
        
        # Save calibration
        calibration = {
            'x_factor': x_factor,
            'y_factor': y_factor,
            'x_error': x_error,
            'y_error': y_error,
            'test_distance': test_distance,
            'timestamp': time.time()
        }
        
        with open('xy_scanner_calibration.json', 'w') as f:
            json.dump(calibration, f, indent=2)
        
        print(f"\n✅ Calibration saved to xy_scanner_calibration.json")
        print(f"\nUpdate Arduino code with these correction factors:")
        print(f"  X_CORRECTION = {x_factor:.4f}")
        print(f"  Y_CORRECTION = {y_factor:.4f}")
        
        # Return home
        self.move_to(0, 0, self.RAPID_SPEED)
    
    def close(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            # Return to home before closing
            if self.is_homed:
                self.move_to(0, 0, self.RAPID_SPEED)
            
            self.serial.close()
            print("✅ XY Scanner connection closed")


def main():
    """Test XY scanner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='XY Scanner Controller')
    parser.add_argument('--port', default='COM4', help='Serial port')
    parser.add_argument('--calibrate', action='store_true', help='Run calibration')
    parser.add_argument('--test-grid', action='store_true', help='Test grid scan')
    parser.add_argument('--rows', type=int, default=4, help='Cards per row')
    parser.add_argument('--cols', type=int, default=2, help='Cards per column')
    
    args = parser.parse_args()
    
    # Initialize scanner
    scanner = XYScannerController(port=args.port)
    
    try:
        if args.calibrate:
            scanner.calibrate()
        
        elif args.test_grid:
            # Dummy camera callback
            def dummy_camera():
                print("   [Simulated camera capture]")
                time.sleep(0.5)
                return {'captured': True, 'timestamp': time.time()}
            
            scanner.scan_grid(camera_callback=dummy_camera, 
                            cards_per_row=args.rows, 
                            cards_per_col=args.cols)
        
        else:
            # Interactive mode
            print("\n🕹️  MANUAL CONTROL MODE")
            print("Commands: left, right, up, down, home, status, quit")
            
            if not scanner.is_homed:
                scanner.home()
            
            while True:
                cmd = input("\nCommand: ").strip().lower()
                
                if cmd in ['left', 'right', 'up', 'down']:
                    distance = float(input("Distance (mm, default 10): ") or "10")
                    scanner.jog(cmd, distance)
                
                elif cmd == 'home':
                    scanner.home()
                
                elif cmd == 'status':
                    status = scanner.get_status()
                    print(json.dumps(status, indent=2))
                
                elif cmd in ['quit', 'exit', 'q']:
                    break
                
                else:
                    print("Unknown command")
    
    finally:
        scanner.close()


if __name__ == "__main__":
    main()
