#!/usr/bin/env python3
"""
MTG Scanner Client for Ubuntu
Lightweight client that captures card images and sends to NEXUS server
Handles: Camera, Arduino lighting, network communication
"""

import cv2
import serial
import serial.tools.list_ports
import time
import requests
import json
import os
from datetime import datetime
from pathlib import Path


class ArduinoController:
    """Control NeoPixel lighting via Arduino"""
    
    def __init__(self, port=None, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.arduino = None
        self.connected = False
    
    def find_arduino(self):
        """Search for Arduino on available ports"""
        print("Searching for Arduino...")
        
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Look for Arduino identifiers
            if 'Arduino' in port.description or 'CH340' in port.description or 'USB' in port.description:
                print(f"  Trying {port.device} - {port.description}")
                try:
                    test_serial = serial.Serial(port.device, self.baudrate, timeout=2)
                    time.sleep(2)  # Wait for reset
                    
                    # Clear buffer
                    while test_serial.in_waiting:
                        test_serial.readline()
                    
                    # Send STATUS command to verify it's our Arduino
                    test_serial.write(b"STATUS\n")
                    test_serial.flush()
                    time.sleep(0.2)
                    
                    response = ""
                    while test_serial.in_waiting:
                        line = test_serial.readline().decode('utf-8', errors='ignore').strip()
                        response += line
                    
                    # Check if we got Arduino response
                    if "STATUS" in response or "SCOOBY" in response or "OK:" in response:
                        print(f"✓ Found Arduino on {port.device}")
                        self.port = port.device
                        self.arduino = test_serial
                        self.connected = True
                        return True
                    else:
                        test_serial.close()
                        
                except Exception as e:
                    print(f"  Failed: {e}")
                    continue
        
        print("✗ No Arduino found")
        return False
        
    def connect(self):
        """Connect to Arduino"""
        # If port specified, try that first
        if self.port:
            try:
                self.arduino = serial.Serial(self.port, self.baudrate, timeout=2)
                time.sleep(2)  # Wait for Arduino reset
                
                # Clear startup messages
                while self.arduino.in_waiting:
                    self.arduino.readline()
                
                self.connected = True
                print(f"✓ Arduino connected on {self.port}")
                return True
            except Exception as e:
                print(f"✗ Arduino connection failed on {self.port}: {e}")
                self.connected = False
        
        # Otherwise, search for it
        return self.find_arduino()
    
    def send_command(self, command):
        """Send command to Arduino"""
        if not self.connected:
            return False
        
        try:
            self.arduino.write(f"{command}\n".encode())
            self.arduino.flush()
            time.sleep(0.1)
            
            # Read response
            responses = []
            while self.arduino.in_waiting:
                resp = self.arduino.readline().decode('utf-8', 
                                                      errors='ignore').strip()
                if resp:
                    responses.append(resp)
            
            return responses
        except Exception as e:
            print(f"Arduino command error: {e}")
            return False
    
    def lights_on(self):
        """Turn lights on"""
        return self.send_command("ON")
    
    def lights_off(self):
        """Turn lights off"""
        return self.send_command("OFF")
    
    def set_brightness(self, value):
        """Set brightness 0-255"""
        return self.send_command(f"B{value}")
    
    def set_color(self, r, g, b):
        """Set RGB color"""
        return self.send_command(f"C{r},{g},{b}")
    
    def test(self):
        """Run rainbow test"""
        return self.send_command("TEST")
    
    def status(self):
        """Get status"""
        return self.send_command("STATUS")
    
    def disconnect(self):
        """Close Arduino connection"""
        if self.arduino:
            self.arduino.close()
            self.connected = False


class CameraController:
    """Control USB camera for card capture"""
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.camera = None
        self.connected = False
        
    def connect(self):
        """Open camera connection"""
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            if not self.camera.isOpened():
                raise Exception("Camera failed to open")
            
            # Set resolution (adjust as needed)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            self.connected = True
            print(f"✓ Camera connected (index {self.camera_index})")
            return True
        except Exception as e:
            print(f"✗ Camera connection failed: {e}")
            self.connected = False
            return False
    
    def capture_frame(self):
        """Capture single frame"""
        if not self.connected:
            return None
        
        ret, frame = self.camera.read()
        if ret:
            return frame
        return None
    
    def save_image(self, frame, filepath):
        """Save frame to file"""
        return cv2.imwrite(filepath, frame)
    
    def disconnect(self):
        """Release camera"""
        if self.camera:
            self.camera.release()
            self.connected = False


class NexusClient:
    """Client for communicating with NEXUS server"""
    
    def __init__(self, server_url, api_key=None):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'X-API-Key': api_key})
    
    def ping(self):
        """Check if NEXUS server is reachable"""
        try:
            response = self.session.get(f"{self.server_url}/api/ping", 
                                       timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Server ping failed: {e}")
            return False
    
    def identify_card(self, image_path):
        """Send card image to NEXUS for identification"""
        try:
            with open(image_path, 'rb') as f:
                files = {'image': f}
                response = self.session.post(
                    f"{self.server_url}/api/identify",
                    files=files,
                    timeout=30
                )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f"Server error: {response.status_code}"}
        
        except Exception as e:
            return {'error': f"Request failed: {e}"}
    
    def add_to_collection(self, card_data):
        """Add identified card to collection"""
        try:
            response = self.session.post(
                f"{self.server_url}/api/collection/add",
                json=card_data,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Add to collection failed: {e}")
            return False


class ScannerStation:
    """Main scanner station controller"""
    
    def __init__(self, config_path='scanner_config.json'):
        self.config = self.load_config(config_path)
        self.arduino = ArduinoController(
            port=self.config.get('arduino_port', '/dev/ttyACM0')
        )
        self.camera = CameraController(
            camera_index=self.config.get('camera_index', 0)
        )
        self.nexus = NexusClient(
            server_url=self.config.get('nexus_server', 
                                      'http://localhost:5000'),
            api_key=self.config.get('api_key')
        )
        
        self.scan_count = 0
        self.temp_dir = Path(self.config.get('temp_dir', '/tmp/scanner'))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Default config
            return {
                'arduino_port': '/dev/ttyACM0',
                'camera_index': 0,
                'nexus_server': 'http://192.168.1.152:8000',
                'api_key': None,
                'temp_dir': '/tmp/scanner'
            }
    
    def initialize(self):
        """Initialize all hardware"""
        print("\n" + "="*60)
        print("MTG SCANNER STATION - Initializing...")
        print("="*60)
        
        # Connect Arduino
        if not self.arduino.connect():
            return False
        
        # Connect Camera
        if not self.camera.connect():
            return False
        
        # Check NEXUS server
        print("Checking NEXUS server connection...")
        if self.nexus.ping():
            print("✓ NEXUS server connected")
        else:
            print("⚠ NEXUS server not reachable - working offline")
        
        # Test lights
        print("Testing lighting system...")
        self.arduino.set_color(0, 255, 0)  # Green
        time.sleep(0.5)
        self.arduino.lights_off()
        
        print("\n✓ Scanner station ready!")
        print("="*60 + "\n")
        return True
    
    def scan_card(self):
        """Perform card scan"""
        self.scan_count += 1
        print(f"\n[Scan #{self.scan_count}] Starting...")
        
        # Turn on scanning lights (white, bright)
        self.arduino.set_color(255, 255, 255)
        self.arduino.set_brightness(255)
        time.sleep(0.2)  # Let camera adjust
        
        # Capture image
        print("  Capturing image...")
        frame = self.camera.capture_frame()
        
        if frame is None:
            print("  ✗ Capture failed!")
            self.arduino.set_color(255, 0, 0)  # Red for error
            time.sleep(1)
            self.arduino.lights_off()
            return None
        
        # Save temporary image
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = self.temp_dir / f"scan_{timestamp}.jpg"
        self.camera.save_image(frame, str(temp_path))
        print(f"  Saved: {temp_path}")
        
        # Send to NEXUS for identification
        print("  Sending to NEXUS for identification...")
        self.arduino.set_color(255, 255, 0)  # Yellow for processing
        
        result = self.nexus.identify_card(str(temp_path))
        
        if 'error' in result:
            print(f"  ✗ Error: {result['error']}")
            self.arduino.set_color(255, 0, 0)  # Red for error
            time.sleep(2)
            self.arduino.lights_off()
            return None
        
        # Success!
        card_name = result.get('name', 'Unknown')
        set_code = result.get('set', 'UNK')
        confidence = result.get('confidence', 0)
        
        print(f"  ✓ Identified: {card_name} ({set_code})")
        print(f"    Confidence: {confidence:.1f}%")
        
        # Green for success
        self.arduino.set_color(0, 255, 0)
        time.sleep(1.5)
        self.arduino.lights_off()
        
        # Add to collection
        if self.nexus.add_to_collection(result):
            print("  ✓ Added to collection")
        
        return result
    
    def run(self):
        """Main scanner loop"""
        if not self.initialize():
            print("✗ Initialization failed!")
            return
        
        print("\nScanner ready - Press ENTER to scan, 'q' to quit")
        
        try:
            while True:
                user_input = input("> ").strip().lower()
                
                if user_input == 'q':
                    break
                elif user_input == 't':
                    # Test lights
                    self.arduino.test()
                elif user_input == 's':
                    # Status
                    status = self.arduino.status()
                    if status:
                        print("\n".join(status))
                else:
                    # Scan card
                    self.scan_card()
        
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        print("Cleaning up...")
        self.arduino.lights_off()
        self.arduino.disconnect()
        self.camera.disconnect()
        print("✓ Scanner shutdown complete")


def main():
    """Entry point"""
    scanner = ScannerStation()
    scanner.run()


if __name__ == '__main__':
    main()
