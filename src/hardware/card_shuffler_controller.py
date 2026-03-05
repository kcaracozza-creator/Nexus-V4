#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Card Shuffler/Sorter Controller
Controls roller feed mechanism + XY axis + 4-bin sorting system
"""

import serial
import time
from xy_scanner_controller import XYScannerController
from typing import Optional, Dict

class CardShufflerController:
    """
    Complete automation:
    1. Roller feed dispenses card from hopper
    2. XY carriage picks up card
    3. Moves to camera position
    4. AI scans/identifies card
    5. XY drops into one of 4 sorting bins
    """
    
    # Servo positions
    ROLLER_SERVO_PIN = 9
    STOPPER_SERVO_PIN = 10
    
    ROLLER_FEED_ANGLE = 90   # Servo angle to dispense card
    ROLLER_IDLE_ANGLE = 0     # Servo idle position
    
    STOPPER_OPEN = 180        # Release card
    STOPPER_CLOSED = 0        # Hold card stack
    
    # XY positions (in mm)
    PICKUP_POSITION = (20, 20)      # Where roller drops card
    SCAN_POSITION = (190, 190)      # Under camera (center)
    
    # 4 sorting bins
    BIN_POSITIONS = {
        'commons': (350, 50),       # Bin 1: Common/bulk cards
        'uncommons': (350, 150),    # Bin 2: Uncommon
        'rares': (350, 250),        # Bin 3: Rare/Mythic
        'valuable': (350, 350)      # Bin 4: High value ($5+)
    }
    
    def __init__(self, arduino_port='COM4', xy_port='COM5'):
        """Initialize shuffler and XY controller"""
        self.arduino = serial.Serial(arduino_port, 115200, timeout=2)
        time.sleep(2)  # Arduino reset
        
        # Initialize XY scanner
        self.xy = XYScannerController(port=xy_port)
        self.xy.home()
        
        # Card tracking
        self.cards_processed = 0
        self.bin_counts = {
            'commons': 0,
            'uncommons': 0,
            'rares': 0,
            'valuable': 0
        }
        
        print("✅ Card Shuffler/Sorter initialized")
        self._init_servos()
    
    def _init_servos(self):
        """Initialize servos to idle positions"""
        self._set_servo(self.ROLLER_SERVO_PIN, self.ROLLER_IDLE_ANGLE)
        self._set_servo(self.STOPPER_SERVO_PIN, self.STOPPER_CLOSED)
        time.sleep(0.5)
    
    def _set_servo(self, pin: int, angle: int):
        """Set servo to specific angle"""
        command = f"SERVO {pin} {angle}\n"
        self.arduino.write(command.encode())
        time.sleep(0.3)  # Allow servo to move
    
    def _send_command(self, cmd: str) -> str:
        """Send command to Arduino and get response"""
        self.arduino.write(f"{cmd}\n".encode())
        time.sleep(0.1)
        
        if self.arduino.in_waiting:
            return self.arduino.readline().decode().strip()
        return ""
    
    def dispense_card(self) -> bool:
        """
        Dispense one card from hopper using roller mechanism
        Returns True if card dispensed successfully
        """
        print("🎴 Dispensing card from hopper...")
        
        # Open stopper to release one card
        self._set_servo(self.STOPPER_SERVO_PIN, self.STOPPER_OPEN)
        time.sleep(0.2)
        
        # Activate roller to feed card
        self._set_servo(self.ROLLER_SERVO_PIN, self.ROLLER_FEED_ANGLE)
        time.sleep(0.5)  # Time for card to feed through
        
        # Stop roller
        self._set_servo(self.ROLLER_SERVO_PIN, self.ROLLER_IDLE_ANGLE)
        
        # Close stopper to hold remaining stack
        self._set_servo(self.STOPPER_SERVO_PIN, self.STOPPER_CLOSED)
        
        # Check if card detected at pickup position
        card_detected = self._check_card_sensor()
        
        if card_detected:
            print("   ✅ Card dispensed")
            return True
        else:
            print("   ⚠️ No card detected - hopper empty?")
            return False
    
    def _check_card_sensor(self) -> bool:
        """Check if card is present at pickup position"""
        response = self._send_command("CARD_DETECT")
        return "DETECTED" in response
    
    def pickup_card(self) -> bool:
        """
        Move XY carriage to pickup position and grab card
        Uses vacuum suction or gripper mechanism
        """
        print("🤏 Picking up card...")
        
        # Move to pickup position
        self.xy.move_to(*self.PICKUP_POSITION, speed=self.xy.RAPID_SPEED)
        time.sleep(0.2)
        
        # Activate vacuum/gripper
        self._send_command("GRIPPER_ON")
        time.sleep(0.3)
        
        # Lift card slightly
        # (Assumes Z-axis servo or mechanism)
        self._send_command("LIFT_CARD")
        time.sleep(0.2)
        
        print("   ✅ Card picked up")
        return True
    
    def scan_card(self, camera_callback) -> Optional[Dict]:
        """
        Move card to scan position and capture image
        Returns card data from AI recognition
        """
        print("📸 Scanning card...")
        
        # Move to camera position (center)
        self.xy.move_to(*self.SCAN_POSITION, speed=self.xy.SCAN_SPEED)
        time.sleep(0.2)  # Settle
        
        # Lower card into focus plane
        self._send_command("LOWER_CARD")
        time.sleep(0.3)
        
        # Trigger camera capture and AI recognition
        if camera_callback:
            card_data = camera_callback()
            print(f"   ✅ Identified: {card_data.get('name', 'Unknown')}")
            return card_data
        
        return None
    
    def sort_card(self, card_data: Dict) -> bool:
        """
        Determine bin and drop card
        Sorting logic based on rarity and price
        """
        # Determine target bin
        rarity = card_data.get('rarity', 'common').lower()
        price = card_data.get('price', 0.0)
        
        if price >= 5.0:
            bin_name = 'valuable'
        elif 'mythic' in rarity or 'rare' in rarity:
            bin_name = 'rares'
        elif 'uncommon' in rarity:
            bin_name = 'uncommons'
        else:
            bin_name = 'commons'
        
        print(f"📦 Sorting to {bin_name} bin...")
        
        # Lift card for transport
        self._send_command("LIFT_CARD")
        time.sleep(0.2)
        
        # Move to bin position
        bin_pos = self.BIN_POSITIONS[bin_name]
        self.xy.move_to(*bin_pos, speed=self.xy.RAPID_SPEED)
        time.sleep(0.3)
        
        # Release card into bin
        self._send_command("GRIPPER_OFF")
        time.sleep(0.2)
        
        # Update count
        self.bin_counts[bin_name] += 1
        
        print(f"   ✅ Dropped into {bin_name} ({self.bin_counts[bin_name]} cards)")
        return True
    
    def process_single_card(self, camera_callback) -> bool:
        """
        Complete workflow for one card:
        Dispense → Pick → Scan → Sort
        """
        print(f"\n{'='*60}")
        print(f"Processing Card #{self.cards_processed + 1}")
        print(f"{'='*60}")
        
        # 1. Dispense from hopper
        if not self.dispense_card():
            print("❌ No cards in hopper")
            return False
        
        # 2. Pick up card
        if not self.pickup_card():
            print("❌ Failed to pick up card")
            return False
        
        # 3. Scan and identify
        card_data = self.scan_card(camera_callback)
        if not card_data:
            print("❌ Failed to identify card")
            # Default to commons bin
            card_data = {'rarity': 'common', 'price': 0.0, 'name': 'Unknown'}
        
        # 4. Sort into bin
        self.sort_card(card_data)
        
        # 5. Return to home for next card
        self.xy.move_to(0, 0, speed=self.xy.RAPID_SPEED)
        
        self.cards_processed += 1
        
        print(f"\n✅ Card #{self.cards_processed} complete!")
        return True
    
    def process_full_deck(self, camera_callback, max_cards=100):
        """
        Process entire deck automatically
        Stops when hopper is empty or max_cards reached
        """
        print(f"\n{'='*60}")
        print(f"🤖 AUTOMATED DECK PROCESSING")
        print(f"{'='*60}")
        print(f"Max cards: {max_cards}")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        
        for i in range(max_cards):
            success = self.process_single_card(camera_callback)
            
            if not success:
                print("\n⚠️ Hopper empty or error - stopping")
                break
            
            # Brief pause between cards
            time.sleep(0.5)
        
        duration = time.time() - start_time
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Total Cards: {self.cards_processed}")
        print(f"Duration: {duration:.1f}s")
        print(f"Speed: {self.cards_processed / (duration / 60):.1f} cards/minute")
        print(f"\nBin Distribution:")
        for bin_name, count in self.bin_counts.items():
            print(f"  {bin_name.capitalize()}: {count}")
        print(f"{'='*60}\n")
        
        return self.cards_processed
    
    def emergency_stop(self):
        """Emergency stop all motion"""
        print("🛑 EMERGENCY STOP")
        self.xy.emergency_stop()
        self._send_command("GRIPPER_OFF")
        self._init_servos()
    
    def close(self):
        """Cleanup and close connections"""
        self.xy.close()
        self.arduino.close()
        print("✅ Shuffler/Sorter closed")


def main():
    """Test the automated system"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Card Shuffler/Sorter')
    parser.add_argument('--arduino-port', default='COM4', help='Arduino port for servos')
    parser.add_argument('--xy-port', default='COM5', help='XY controller port')
    parser.add_argument('--max-cards', type=int, default=100, help='Max cards to process')
    parser.add_argument('--test-single', action='store_true', help='Test single card')
    
    args = parser.parse_args()
    
    # Dummy camera callback for testing
    def dummy_camera():
        import random
        rarities = ['common', 'uncommon', 'rare', 'mythic']
        prices = [0.1, 0.5, 2.0, 10.0]
        
        return {
            'name': f'Test Card {random.randint(1, 1000)}',
            'rarity': random.choice(rarities),
            'price': random.choice(prices),
            'captured': True
        }
    
    # Initialize system
    shuffler = CardShufflerController(
        arduino_port=args.arduino_port,
        xy_port=args.xy_port
    )
    
    try:
        if args.test_single:
            # Test one card
            shuffler.process_single_card(dummy_camera)
        else:
            # Process full deck
            shuffler.process_full_deck(dummy_camera, max_cards=args.max_cards)
    
    finally:
        shuffler.close()


if __name__ == "__main__":
    main()
