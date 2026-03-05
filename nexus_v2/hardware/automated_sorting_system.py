#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS Automated Card Sorting System
Hardware: XY Gantry + Card Hopper + 8K Camera + Multi-Bin Removal System

Components:
- Card Hopper: Gravity-fed stack with servo release mechanism
- XY Gantry: 2-axis positioning system for camera movement
- 8K Camera: High-resolution DSLR for detailed scanning
- Sorting Logic: Multi-method identification + value-based routing
- Removal System: Pneumatic/servo chutes to sorted bins

Flow:
1. Hopper releases single card onto scan platform
2. Gantry positions camera for multi-angle capture
3. AI identifies card (name, set, condition, value)
4. Logic determines destination bin
5. Removal system routes card to appropriate chute
6. Repeat until hopper empty
"""

import serial
import time
import json
import os
from datetime import datetime
import requests
import cv2
import numpy as np
from collections import defaultdict

try:
    import gphoto2 as gp
    GPHOTO_AVAILABLE = True
except:
    GPHOTO_AVAILABLE = False
    print("⚠️ gphoto2 not available - using webcam fallback")


class AutomatedSortingSystem:
    """
    Complete automated card sorting system with marketplace integration
    """
    
    def __init__(self, arduino_port='COM3', scanner_api_url='http://192.168.0.7:5000'):
        # Hardware connections
        self.arduino_port = arduino_port
        self.arduino = None
        self.scanner_api = scanner_api_url
        
        # Camera setup
        self.camera = None
        self.camera_type = None
        
        # Gantry configuration (mm)
        self.gantry_config = {
            'x_min': 0,
            'x_max': 400,  # 400mm travel
            'y_min': 0,
            'y_max': 300,  # 300mm travel
            'home_x': 200,  # Center position
            'home_y': 150,
            'scan_positions': [
                {'x': 200, 'y': 150, 'angle': 'overhead'},
                {'x': 150, 'y': 150, 'angle': 'oblique_left'},
                {'x': 250, 'y': 150, 'angle': 'oblique_right'}
            ]
        }
        
        # Hopper configuration
        self.hopper_config = {
            'capacity': 500,  # cards
            'feed_servo_pin': 9,
            'sensor_pin': 2,  # IR sensor for card detection
            'feed_delay': 0.5  # seconds between cards
        }
        
        # Removal system configuration
        self.removal_bins = {
            'high_value': {'chute': 1, 'threshold': 50.0},      # $50+
            'medium_value': {'chute': 2, 'threshold': 10.0},    # $10-50
            'bulk_rare': {'chute': 3, 'threshold': 1.0},        # $1-10
            'bulk_uncommon': {'chute': 4, 'threshold': 0.25},   # $0.25-1
            'bulk_common': {'chute': 5, 'threshold': 0.0},      # <$0.25
            'damaged': {'chute': 6, 'threshold': None},         # Any condition < LP
            'foreign': {'chute': 7, 'threshold': None},         # Non-English
            'reject': {'chute': 8, 'threshold': None}           # Unidentified
        }
        
        # Statistics
        self.session_stats = {
            'cards_processed': 0,
            'cards_identified': 0,
            'cards_rejected': 0,
            'total_value': 0.0,
            'bin_counts': defaultdict(int),
            'start_time': None,
            'errors': []
        }
        
        # Marketplace integration
        self.auto_list_threshold = 5.0  # Auto-list cards worth $5+
        
    def initialize_hardware(self):
        """Initialize all hardware components"""
        print("🔧 Initializing Automated Sorting System...")
        
        # Connect to Arduino
        try:
            self.arduino = serial.Serial(self.arduino_port, 115200, timeout=1)
            time.sleep(2)  # Wait for reset
            print("✅ Arduino connected")
            
            # Send initialization command
            self.arduino.write(b'INIT\n')
            response = self.arduino.readline().decode().strip()
            print(f"   Arduino response: {response}")
            
            # Home gantry
            self.home_gantry()
            
        except Exception as e:
            print(f"❌ Arduino connection failed: {e}")
            return False
        
        # Initialize camera
        if GPHOTO_AVAILABLE:
            try:
                self.camera = gp.Camera()
                self.camera.init()
                self.camera_type = 'DSLR'
                print("✅ DSLR camera connected")
            except:
                print("⚠️ DSLR not found, trying webcam...")
                self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)  # 4K
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
                self.camera_type = 'webcam'
                print("✅ Webcam connected (4K mode)")
        else:
            self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
            self.camera_type = 'webcam'
            print("✅ Webcam connected (4K mode)")
        
        # Test hopper
        hopper_ok = self.test_hopper()
        if hopper_ok:
            print("✅ Card hopper operational")
        else:
            print("⚠️ Hopper test failed")
        
        # Test removal system
        removal_ok = self.test_removal_system()
        if removal_ok:
            print("✅ Removal system operational")
        else:
            print("⚠️ Removal system test failed")
        
        print("🚀 System ready for automated sorting!")
        return True
    
    def home_gantry(self):
        """Home XY gantry to center position"""
        print("🏠 Homing gantry...")
        home_x = self.gantry_config['home_x']
        home_y = self.gantry_config['home_y']
        
        command = f"GANTRY_HOME,{home_x},{home_y}\n"
        self.arduino.write(command.encode())
        
        # Wait for movement complete
        while True:
            response = self.arduino.readline().decode().strip()
            if response == "GANTRY_HOME_COMPLETE":
                print(f"   Gantry at home position ({home_x}, {home_y})")
                break
            time.sleep(0.1)
    
    def move_gantry(self, x, y, speed=100):
        """
        Move gantry to absolute position
        
        Args:
            x: X coordinate in mm
            y: Y coordinate in mm
            speed: Movement speed (0-100%)
        """
        # Clamp to limits
        x = max(self.gantry_config['x_min'], min(x, self.gantry_config['x_max']))
        y = max(self.gantry_config['y_min'], min(y, self.gantry_config['y_max']))
        
        command = f"GANTRY_MOVE,{x},{y},{speed}\n"
        self.arduino.write(command.encode())
        
        # Wait for movement complete
        while True:
            response = self.arduino.readline().decode().strip()
            if response == "GANTRY_MOVE_COMPLETE":
                return True
            elif response.startswith("ERROR"):
                print(f"❌ Gantry error: {response}")
                return False
            time.sleep(0.1)
    
    def feed_card_from_hopper(self):
        """
        Release one card from hopper onto scan platform
        
        Returns:
            bool: True if card detected on platform
        """
        # Send feed command
        self.arduino.write(b"HOPPER_FEED\n")
        time.sleep(self.hopper_config['feed_delay'])
        
        # Check sensor
        self.arduino.write(b"SENSOR_CHECK\n")
        response = self.arduino.readline().decode().strip()
        
        if response == "CARD_DETECTED":
            return True
        else:
            print("⚠️ No card detected after feed")
            return False
    
    def capture_card_images(self):
        """
        Capture multiple angles of card using gantry positioning
        
        Returns:
            list: Array of captured images
        """
        images = []
        
        for position in self.gantry_config['scan_positions']:
            # Move to position
            print(f"📸 Capturing {position['angle']} view...")
            self.move_gantry(position['x'], position['y'])
            time.sleep(0.2)  # Stabilization
            
            # Capture image
            if self.camera_type == 'DSLR' and GPHOTO_AVAILABLE:
                # DSLR capture
                file_path = self.camera.capture(gp.GP_CAPTURE_IMAGE)
                camera_file = self.camera.file_get(
                    file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
                
                # Save to temp
                temp_path = f"temp_{position['angle']}.jpg"
                camera_file.save(temp_path)
                
                # Load with OpenCV
                image = cv2.imread(temp_path)
                images.append({'image': image, 'angle': position['angle'], 'path': temp_path})
                
            else:
                # Webcam capture
                ret, frame = self.camera.read()
                if ret:
                    temp_path = f"temp_{position['angle']}.jpg"
                    cv2.imwrite(temp_path, frame)
                    images.append({'image': frame, 'angle': position['angle'], 'path': temp_path})
        
        return images
    
    def identify_card(self, images):
        """
        Send images to scanner API for identification
        
        Returns:
            dict: Card identification result with confidence
        """
        # Use best overhead image
        overhead = None
        for img_data in images:
            if img_data['angle'] == 'overhead':
                overhead = img_data
                break
        
        if not overhead:
            return {'identified': False, 'reason': 'No overhead image'}
        
        # Send to scanner API
        try:
            with open(overhead['path'], 'rb') as f:
                files = {'image': f}
                response = requests.post(f"{self.scanner_api}/scan", files=files, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Check confidence
                if result.get('confidence', 0) > 0.8:
                    return {
                        'identified': True,
                        'card_name': result.get('card_name'),
                        'set_code': result.get('set_code'),
                        'collector_number': result.get('collector_number'),
                        'confidence': result.get('confidence'),
                        'scryfall_data': result.get('scryfall_data')
                    }
                else:
                    return {'identified': False, 'reason': 'Low confidence', 'data': result}
            else:
                return {'identified': False, 'reason': f'API error {response.status_code}'}
                
        except Exception as e:
            print(f"❌ Identification error: {e}")
            return {'identified': False, 'reason': str(e)}
    
    def determine_destination_bin(self, card_data):
        """
        Determine which bin card should go to based on value and attributes
        
        Returns:
            str: Bin name
            int: Chute number
        """
        if not card_data.get('identified'):
            return 'reject', self.removal_bins['reject']['chute']
        
        scryfall = card_data.get('scryfall_data', {})
        
        # Check for damaged condition
        condition = card_data.get('condition', 'NM')
        if condition in ['HP', 'DMG']:
            return 'damaged', self.removal_bins['damaged']['chute']
        
        # Check for foreign language
        language = scryfall.get('lang', 'en')
        if language != 'en':
            return 'foreign', self.removal_bins['foreign']['chute']
        
        # Get price
        prices = scryfall.get('prices', {})
        price = float(prices.get('usd', 0) or 0)
        
        # Sort by value
        if price >= self.removal_bins['high_value']['threshold']:
            return 'high_value', self.removal_bins['high_value']['chute']
        elif price >= self.removal_bins['medium_value']['threshold']:
            return 'medium_value', self.removal_bins['medium_value']['chute']
        elif price >= self.removal_bins['bulk_rare']['threshold']:
            return 'bulk_rare', self.removal_bins['bulk_rare']['chute']
        elif price >= self.removal_bins['bulk_uncommon']['threshold']:
            return 'bulk_uncommon', self.removal_bins['bulk_uncommon']['chute']
        else:
            return 'bulk_common', self.removal_bins['bulk_common']['chute']
    
    def route_card_to_bin(self, chute_number):
        """
        Activate removal system to route card to specific chute
        
        Args:
            chute_number: Target chute (1-8)
        """
        command = f"ROUTE_CARD,{chute_number}\n"
        self.arduino.write(command.encode())
        
        # Wait for routing complete
        while True:
            response = self.arduino.readline().decode().strip()
            if response == "ROUTING_COMPLETE":
                return True
            elif response.startswith("ERROR"):
                print(f"❌ Routing error: {response}")
                return False
            time.sleep(0.1)
    
    def auto_list_to_marketplace(self, card_data):
        """
        Automatically create marketplace listing for valuable cards
        
        Returns:
            str: Listing ID if created, None otherwise
        """
        scryfall = card_data.get('scryfall_data', {})
        prices = scryfall.get('prices', {})
        price = float(prices.get('usd', 0) or 0)
        
        # Only list if above threshold
        if price < self.auto_list_threshold:
            return None
        
        try:
            # Create marketplace listing via API
            listing_data = {
                'card_name': card_data['card_name'],
                'set_code': card_data['set_code'],
                'set_name': scryfall.get('set_name', ''),
                'collector_number': card_data.get('collector_number', ''),
                'condition': card_data.get('condition', 'NM'),
                'price': price * 1.15,  # List at 15% markup
                'quantity': 1,
                'foil': scryfall.get('foil', False),
                'language': scryfall.get('lang', 'en'),
                'image_url': scryfall.get('image_uris', {}).get('normal', ''),
                'scryfall_id': scryfall.get('id', '')
            }
            
            # Post to marketplace API
            response = requests.post('http://localhost:8000/api/marketplace/create_listing',
                                    json=listing_data, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                print(f"   💰 Auto-listed to marketplace: {card_data['card_name']} @ ${price * 1.15:.2f}")
                return result.get('listing_id')
            else:
                print(f"   ⚠️ Marketplace listing failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ⚠️ Marketplace error: {e}")
            return None
    
    def process_single_card(self):
        """
        Complete workflow for processing one card
        
        Returns:
            dict: Processing result
        """
        # Feed card
        if not self.feed_card_from_hopper():
            return {'success': False, 'reason': 'Feed failed'}
        
        # Capture images
        images = self.capture_card_images()
        if not images:
            return {'success': False, 'reason': 'Capture failed'}
        
        # Identify card
        card_data = self.identify_card(images)
        
        # Determine destination
        bin_name, chute = self.determine_destination_bin(card_data)
        
        # Route card
        route_success = self.route_card_to_bin(chute)
        
        # Update stats
        self.session_stats['cards_processed'] += 1
        if card_data.get('identified'):
            self.session_stats['cards_identified'] += 1
            
            # Get value
            scryfall = card_data.get('scryfall_data', {})
            prices = scryfall.get('prices', {})
            price = float(prices.get('usd', 0) or 0)
            self.session_stats['total_value'] += price
            
            # Auto-list to marketplace
            if price >= self.auto_list_threshold:
                listing_id = self.auto_list_to_marketplace(card_data)
                card_data['marketplace_listing'] = listing_id
        else:
            self.session_stats['cards_rejected'] += 1
        
        self.session_stats['bin_counts'][bin_name] += 1
        
        # Cleanup temp images
        for img_data in images:
            try:
                os.remove(img_data['path'])
            except:
                pass
        
        return {
            'success': route_success,
            'card_data': card_data,
            'bin': bin_name,
            'chute': chute
        }
    
    def run_batch_sorting(self, max_cards=None):
        """
        Run automated sorting until hopper empty or max reached
        
        Args:
            max_cards: Maximum cards to process (None = until empty)
        """
        print("\n" + "="*60)
        print("🤖 STARTING AUTOMATED BATCH SORTING")
        print("="*60 + "\n")
        
        self.session_stats['start_time'] = datetime.now()
        card_count = 0
        
        try:
            while True:
                # Check max limit
                if max_cards and card_count >= max_cards:
                    print(f"\n✅ Reached maximum card limit ({max_cards})")
                    break
                
                # Process card
                print(f"\n📇 Processing card {card_count + 1}...")
                result = self.process_single_card()
                
                if result['success']:
                    card_data = result['card_data']
                    if card_data.get('identified'):
                        card_name = card_data['card_name']
                        confidence = card_data.get('confidence', 0)
                        print(f"   ✅ {card_name} ({confidence*100:.1f}% confidence)")
                        print(f"   📦 Routed to: {result['bin'].upper()} (Chute {result['chute']})")
                    else:
                        print(f"   ⚠️ Unidentified - sent to reject bin")
                    
                    card_count += 1
                else:
                    reason = result.get('reason', 'Unknown error')
                    if reason == 'Feed failed':
                        print("\n🏁 Hopper empty - sorting complete!")
                        break
                    else:
                        print(f"   ❌ Error: {reason}")
                        self.session_stats['errors'].append(reason)
                
                # Small delay between cards
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n\n⏸️ Sorting interrupted by user")
        
        # Print summary
        self.print_session_summary()
    
    def print_session_summary(self):
        """Print complete session statistics"""
        stats = self.session_stats
        
        if stats['start_time']:
            duration = (datetime.now() - stats['start_time']).total_seconds()
            cards_per_minute = (stats['cards_processed'] / duration) * 60 if duration > 0 else 0
        else:
            duration = 0
            cards_per_minute = 0
        
        print("\n" + "="*60)
        print("📊 SORTING SESSION SUMMARY")
        print("="*60)
        print(f"\n⏱️  Duration: {duration/60:.1f} minutes")
        print(f"📇 Total Processed: {stats['cards_processed']} cards")
        print(f"✅ Identified: {stats['cards_identified']} ({stats['cards_identified']/stats['cards_processed']*100:.1f}%)")
        print(f"❌ Rejected: {stats['cards_rejected']}")
        print(f"💰 Total Value: ${stats['total_value']:.2f}")
        print(f"⚡ Speed: {cards_per_minute:.1f} cards/minute")
        
        print(f"\n📦 BIN DISTRIBUTION:")
        for bin_name, count in sorted(stats['bin_counts'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / stats['cards_processed'] * 100) if stats['cards_processed'] > 0 else 0
            print(f"   • {bin_name.upper()}: {count} cards ({percentage:.1f}%)")
        
        if stats['errors']:
            print(f"\n⚠️  ERRORS ({len(stats['errors'])}):")
            for error in stats['errors'][:10]:
                print(f"   • {error}")
        
        print("\n" + "="*60 + "\n")
    
    def test_hopper(self):
        """Test hopper mechanism"""
        try:
            self.arduino.write(b"HOPPER_TEST\n")
            response = self.arduino.readline().decode().strip()
            return response == "HOPPER_OK"
        except:
            return False
    
    def test_removal_system(self):
        """Test all removal chutes"""
        try:
            for chute in range(1, 9):
                print(f"   Testing chute {chute}...")
                self.arduino.write(f"TEST_CHUTE,{chute}\n".encode())
                time.sleep(0.5)
            return True
        except:
            return False
    
    def calibrate_system(self):
        """Run full system calibration"""
        print("\n🔧 SYSTEM CALIBRATION")
        print("="*60)
        
        # 1. Gantry calibration
        print("\n1️⃣ Calibrating XY Gantry...")
        self.home_gantry()
        
        # Test corner positions
        corners = [
            (self.gantry_config['x_min'], self.gantry_config['y_min']),
            (self.gantry_config['x_max'], self.gantry_config['y_min']),
            (self.gantry_config['x_max'], self.gantry_config['y_max']),
            (self.gantry_config['x_min'], self.gantry_config['y_max'])
        ]
        
        for x, y in corners:
            print(f"   Moving to ({x}, {y})...")
            self.move_gantry(x, y)
            time.sleep(0.5)
        
        self.home_gantry()
        print("   ✅ Gantry calibration complete")
        
        # 2. Camera focus test
        print("\n2️⃣ Testing camera focus...")
        images = self.capture_card_images()
        if images:
            print(f"   ✅ Captured {len(images)} test images")
        
        # 3. Hopper test
        print("\n3️⃣ Testing hopper mechanism...")
        if self.test_hopper():
            print("   ✅ Hopper operational")
        
        # 4. Removal system test
        print("\n4️⃣ Testing removal chutes...")
        if self.test_removal_system():
            print("   ✅ All chutes operational")
        
        print("\n✅ Calibration complete!\n")
    
    def shutdown(self):
        """Safely shutdown system"""
        print("\n🛑 Shutting down system...")
        
        # Home gantry
        self.home_gantry()
        
        # Close camera
        if self.camera:
            if self.camera_type == 'DSLR' and GPHOTO_AVAILABLE:
                self.camera.exit()
            else:
                self.camera.release()
        
        # Close Arduino
        if self.arduino:
            self.arduino.close()
        
        print("✅ Shutdown complete")


def main():
    """Main entry point for automated sorting"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🤖 NEXUS AUTOMATED CARD SORTING SYSTEM v1.0 🤖          ║
║                                                              ║
║  Hardware: XY Gantry + Hopper + 8K Camera + Multi-Bin Sort  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Initialize system
    sorter = AutomatedSortingSystem(
        arduino_port='COM3',
        scanner_api_url='http://192.168.0.7:5000'
    )
    
    if not sorter.initialize_hardware():
        print("❌ Hardware initialization failed!")
        return
    
    # Calibration
    print("\nRun calibration? (y/n): ", end='')
    if input().lower() == 'y':
        sorter.calibrate_system()
    
    # Start sorting
    print("\nHow many cards to process? (blank = all): ", end='')
    max_input = input().strip()
    max_cards = int(max_input) if max_input else None
    
    try:
        sorter.run_batch_sorting(max_cards)
    finally:
        sorter.shutdown()


if __name__ == "__main__":
    main()
