#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Card Sorter - Full Pipeline
Hopper → XY Picker → Camera → 4-Bin Sorting System
"""

import serial
import time
import json
from typing import Tuple, List, Optional, Dict
from pathlib import Path
from enum import Enum

class SortBin(Enum):
    """Sorting destinations"""
    BIN_1 = 1  # High value / Rare
    BIN_2 = 2  # Medium value / Uncommon
    BIN_3 = 3  # Low value / Common
    BIN_4 = 4  # Reject / Damaged

class AutomatedCardSorter:
    """
    Fully automated card sorting system
    1. Dispenses card from hopper
    2. XY carriage picks up card with suction
    3. Moves to camera position
    4. AI identifies card
    5. Sorts to appropriate bin
    """
    
    # System specifications
    STEPS_PER_REV = 200
    MICROSTEPS = 16
    LEAD_SCREW_PITCH = 8.0  # Creality T8 4-start
    
    # Position definitions (in mm)
    POSITIONS = {
        'home': (0, 0),
        'dispenser': (50, 20),      # Pickup position from hopper
        'camera': (190, 190),        # Center under camera
        'bin_1': (320, 50),          # High value bin
        'bin_2': (320, 130),         # Medium value bin
        'bin_3': (320, 210),         # Low value bin
        'bin_4': (320, 290),         # Reject bin
    }
    
    # Movement speeds
    PICKUP_SPEED = 10.0      # mm/s - slow for pickup
    SCAN_SPEED = 30.0        # mm/s - medium for camera
    SORT_SPEED = 50.0        # mm/s - fast for drop-off
    
    # Vacuum/suction control
    VACUUM_PIN = 8           # Arduino pin for vacuum solenoid
    SUCTION_DELAY = 0.5      # seconds to establish suction
    RELEASE_DELAY = 0.3      # seconds to release card
    
    def __init__(self, port='COM4', baudrate=115200):
        """Initialize automated sorter"""
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.current_position = [0.0, 0.0]
        self.is_homed = False
        self.card_count = 0
        self.bin_counts = {bin: 0 for bin in SortBin}
        
        # Stats
        self.session_stats = {
            'total_scanned': 0,
            'successful_sorts': 0,
            'pickup_failures': 0,
            'scan_failures': 0,
            'start_time': None
        }
        
        self._connect()
    
    def _connect(self):
        """Connect to Arduino controller"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)
            print(f"✅ Connected to Automated Sorter on {self.port}")
            
            self._send_command("INIT")
            response = self._read_response()
            print(f"   Arduino: {response}")
            
        except serial.SerialException as e:
            print(f"❌ Failed to connect: {e}")
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
        while time.time() - start_time < timeout:
            if self.serial.in_waiting:
                return self.serial.readline().decode().strip()
            time.sleep(0.01)
        return ""
    
    def mm_to_steps(self, mm: float) -> int:
        """Convert mm to motor steps"""
        steps_per_mm = (self.STEPS_PER_REV * self.MICROSTEPS) / self.LEAD_SCREW_PITCH
        return int(mm * steps_per_mm)
    
    def home(self) -> bool:
        """Home XY carriage to origin"""
        print("🏠 Homing carriage...")
        self._send_command("HOME")
        
        response = self._read_response(timeout=30)
        if "HOMED" in response:
            self.current_position = [0.0, 0.0]
            self.is_homed = True
            print("✅ Homing complete")
            return True
        
        print(f"❌ Homing failed: {response}")
        return False
    
    def move_to(self, x: float, y: float, speed: float) -> bool:
        """Move carriage to absolute position"""
        if not self.is_homed:
            if not self.home():
                return False
        
        delta_x = x - self.current_position[0]
        delta_y = y - self.current_position[1]
        
        steps_x = self.mm_to_steps(delta_x)
        steps_y = self.mm_to_steps(delta_y)
        steps_speed = self.mm_to_steps(speed)
        
        command = f"MOVE {steps_x} {steps_y} {steps_speed}"
        self._send_command(command)
        
        response = self._read_response(timeout=30)
        if "DONE" in response:
            self.current_position = [x, y]
            return True
        
        return False
    
    def vacuum_on(self):
        """Activate vacuum pickup"""
        print("   🔌 Vacuum ON")
        self._send_command("VACUUM ON")
        time.sleep(self.SUCTION_DELAY)
    
    def vacuum_off(self):
        """Deactivate vacuum"""
        print("   🔌 Vacuum OFF")
        self._send_command("VACUUM OFF")
        time.sleep(self.RELEASE_DELAY)
    
    def dispense_card(self) -> bool:
        """
        Trigger hopper to dispense one card
        Returns True if card is ready for pickup
        """
        print("📤 Dispensing card from hopper...")
        self._send_command("DISPENSE")
        
        # Wait for dispenser response
        response = self._read_response(timeout=5)
        
        if "CARD_READY" in response:
            print("   ✅ Card dispensed")
            return True
        elif "HOPPER_EMPTY" in response:
            print("   ⚠️ Hopper empty!")
            return False
        else:
            print(f"   ❌ Dispense failed: {response}")
            return False
    
    def pickup_card(self) -> bool:
        """
        Move to dispenser and pick up card with vacuum
        """
        print("🤏 Picking up card...")
        
        # Move to pickup position
        x, y = self.POSITIONS['dispenser']
        if not self.move_to(x, y, self.PICKUP_SPEED):
            print("   ❌ Failed to reach pickup position")
            return False
        
        # Lower Z-axis (if you have Z-axis)
        # self._send_command("Z_DOWN")
        
        # Activate vacuum
        self.vacuum_on()
        
        # Check if card is picked up (vacuum sensor)
        self._send_command("CHECK_VACUUM")
        response = self._read_response()
        
        if "CARD_HELD" in response:
            print("   ✅ Card secured")
            # self._send_command("Z_UP")
            return True
        else:
            print("   ❌ Pickup failed - no vacuum")
            self.vacuum_off()
            self.session_stats['pickup_failures'] += 1
            return False
    
    def scan_card(self, camera_callback) -> Optional[Dict]:
        """
        Move card to camera position and scan
        """
        print("📸 Scanning card...")
        
        # Move to camera position
        x, y = self.POSITIONS['camera']
        if not self.move_to(x, y, self.SCAN_SPEED):
            print("   ❌ Failed to reach camera position")
            return None
        
        # Wait for vibrations to settle
        time.sleep(0.2)
        
        # Capture and recognize
        try:
            card_data = camera_callback()
            
            if card_data and 'name' in card_data:
                print(f"   ✅ Identified: {card_data['name']}")
                print(f"      Value: ${card_data.get('price', 0):.2f}")
                return card_data
            else:
                print("   ❌ Recognition failed")
                self.session_stats['scan_failures'] += 1
                return None
                
        except Exception as e:
            print(f"   ❌ Scan error: {e}")
            return None
    
    def determine_bin(self, card_data: Dict) -> SortBin:
        """
        Determine which bin to sort card into
        Based on card value, rarity, condition, etc.
        """
        price = card_data.get('price', 0)
        rarity = card_data.get('rarity', 'common')
        condition = card_data.get('condition', 'NM')
        
        # Sorting logic
        if price >= 50.0 or rarity in ['mythic', 'rare']:
            return SortBin.BIN_1  # High value
        elif price >= 5.0 or rarity == 'uncommon':
            return SortBin.BIN_2  # Medium value
        elif price >= 0.50 and condition in ['NM', 'LP']:
            return SortBin.BIN_3  # Low value
        else:
            return SortBin.BIN_4  # Reject / bulk
    
    def sort_to_bin(self, bin: SortBin) -> bool:
        """
        Move card to specified bin and release
        """
        bin_name = f'bin_{bin.value}'
        print(f"📦 Sorting to {bin_name.upper()}...")
        
        # Move to bin position
        x, y = self.POSITIONS[bin_name]
        if not self.move_to(x, y, self.SORT_SPEED):
            print(f"   ❌ Failed to reach {bin_name}")
            return False
        
        # Release card
        self.vacuum_off()
        
        # Update count
        self.bin_counts[bin] += 1
        print(f"   ✅ Sorted ({self.bin_counts[bin]} in {bin_name})")
        
        return True
    
    def process_single_card(self, camera_callback) -> bool:
        """
        Complete pipeline for one card:
        Dispense → Pickup → Scan → Sort
        """
        print(f"\n{'='*60}")
        print(f"🃏 PROCESSING CARD #{self.card_count + 1}")
        print(f"{'='*60}")
        
        # Step 1: Dispense from hopper
        if not self.dispense_card():
            print("⚠️ No more cards in hopper")
            return False
        
        # Step 2: Pick up card
        if not self.pickup_card():
            print("❌ Pickup failed - skipping card")
            return False
        
        # Step 3: Scan card
        card_data = self.scan_card(camera_callback)
        
        if not card_data:
            # Failed to recognize - sort to reject bin
            print("⚠️ Unrecognized card - sending to reject bin")
            self.sort_to_bin(SortBin.BIN_4)
            return False
        
        # Step 4: Determine bin
        target_bin = self.determine_bin(card_data)
        
        # Step 5: Sort to bin
        if self.sort_to_bin(target_bin):
            self.card_count += 1
            self.session_stats['total_scanned'] += 1
            self.session_stats['successful_sorts'] += 1
            
            # Store card data
            card_data['bin'] = target_bin.value
            card_data['timestamp'] = time.time()
            
            return True
        
        return False
    
    def run_batch(self, camera_callback, max_cards: int = None):
        """
        Process entire batch of cards
        Runs until hopper is empty or max_cards reached
        """
        print(f"\n{'='*60}")
        print(f"🚀 AUTOMATED BATCH SORTING")
        print(f"{'='*60}\n")
        
        if not self.is_homed:
            if not self.home():
                print("❌ Homing failed - cannot start batch")
                return
        
        self.session_stats['start_time'] = time.time()
        cards_processed = 0
        
        while True:
            # Check max cards limit
            if max_cards and cards_processed >= max_cards:
                print(f"\n✅ Reached max cards limit ({max_cards})")
                break
            
            # Process one card
            success = self.process_single_card(camera_callback)
            
            if success:
                cards_processed += 1
            else:
                # Check if hopper is empty
                if not self.dispense_card():
                    print("\n✅ Hopper empty - batch complete")
                    break
        
        # Return to home
        print("\n🏠 Returning to home position...")
        self.move_to(0, 0, self.SORT_SPEED)
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print session statistics"""
        duration = time.time() - self.session_stats['start_time']
        
        print(f"\n{'='*60}")
        print(f"📊 BATCH SUMMARY")
        print(f"{'='*60}")
        print(f"Total Cards Scanned: {self.session_stats['total_scanned']}")
        print(f"Successful Sorts: {self.session_stats['successful_sorts']}")
        print(f"Pickup Failures: {self.session_stats['pickup_failures']}")
        print(f"Scan Failures: {self.session_stats['scan_failures']}")
        print(f"Duration: {duration:.1f}s")
        print(f"Average: {duration/max(1, self.session_stats['total_scanned']):.2f}s per card")
        print(f"\n📦 Bin Breakdown:")
        for bin, count in self.bin_counts.items():
            print(f"   {bin.name}: {count} cards")
        print(f"{'='*60}\n")
    
    def close(self):
        """Shutdown system"""
        if self.is_homed:
            self.move_to(0, 0, self.SORT_SPEED)
        
        self.vacuum_off()
        
        if self.serial and self.serial.is_open:
            self.serial.close()
        
        print("✅ System shutdown complete")


def main():
    """Test automated sorter"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Card Sorter')
    parser.add_argument('--port', default='COM4', help='Serial port')
    parser.add_argument('--max-cards', type=int, help='Max cards to process')
    parser.add_argument('--test', action='store_true', help='Test mode (dummy camera)')
    
    args = parser.parse_args()
    
    # Initialize sorter
    sorter = AutomatedCardSorter(port=args.port)
    
    try:
        # Define camera callback
        if args.test:
            # Dummy camera for testing
            def dummy_camera():
                import random
                time.sleep(0.1)  # Simulate camera capture
                return {
                    'name': f'Test Card #{sorter.card_count + 1}',
                    'price': random.choice([0.25, 1.50, 5.00, 25.00, 100.00]),
                    'rarity': random.choice(['common', 'uncommon', 'rare', 'mythic']),
                    'condition': 'NM'
                }
            
            camera_callback = dummy_camera
        else:
            # Real camera - integrate with your existing system
            from mttgg_complete_system import MTTGGCompleteSystem
            # camera_callback = system.capture_and_recognize_card
            print("⚠️ Real camera integration needed")
            return
        
        # Run batch
        sorter.run_batch(camera_callback, max_cards=args.max_cards)
    
    finally:
        sorter.close()


if __name__ == "__main__":
    main()
