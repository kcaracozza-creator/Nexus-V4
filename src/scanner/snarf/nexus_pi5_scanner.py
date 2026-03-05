#!/usr/bin/env python3
"""
NEXUS Pi5 Scanner - Universal Card Scanner (Patent Pending)
NEXUS V2 Collectibles Management System
Copyright 2025-2026 Kevin Caracozza - All Rights Reserved
Patent Filed: November 27, 2025

Multi-Camera Scanner for Pi5:
  - OwlEye 64MP (CSI): High-resolution card scanning, grading
  - CZUR Scanner (USB): Bulk document scanning
  - USB Webcam: Motion detection, monitoring

Hardware Control:
  - ESP32: Lightbox LEDs, Logo ring, PCA9685 servo control
  - Arduino Micro: 3x scanner ring LEDs

Server Architecture:
  - Flask API for remote control
  - Integration with Brok (192.168.1.174:5000) for OCR
  - WebSocket support for real-time updates
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Thread, Event, Lock
from io import BytesIO
import signal

import cv2
import numpy as np
import serial
import serial.tools.list_ports
import requests
from flask import Flask, jsonify, request, send_file, Response

# Optional picamera2 for CSI cameras
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None

# =============================================================================
# CONFIGURATION
# =============================================================================
class ScannerConfig:
    """Configuration for Pi5 scanner"""

    # Network
    BROK_URL = os.getenv('NEXUS_BROK_URL', 'http://192.168.1.174:5000')
    SERVER_HOST = os.getenv('SCANNER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('SCANNER_PORT', '5001'))

    # Hardware Serial Ports
    ESP32_PORT = os.getenv('ESP32_PORT', '/dev/ttyUSB0')
    ARDUINO_PORT = os.getenv('ARDUINO_PORT', '/dev/ttyACM0')
    BAUD = 115200

    # Directories
    SCAN_DIR = os.getenv('SCAN_DIR', '/home/nexus1/scans')
    CACHE_DIR = os.getenv('CACHE_DIR', '/home/nexus1/cache')
    CONFIG_FILE = os.getenv('CONFIG_FILE', '/home/nexus1/scanner_config.json')

    # Camera Indices (v4l2)
    OWLEYE_INDEX = 0  # CSI camera via rp1-cfe
    CZUR_INDEX = 10   # CZUR USB camera
    WEBCAM_INDEX = 8  # HD Web Camera

    # Scanning Defaults
    DEFAULT_CAMERA = 'owleye'
    SCAN_RESOLUTION = (3840, 2160)  # 4K for OwlEye
    CZUR_RESOLUTION = (1920, 1080)  # 1080p for CZUR
    WEBCAM_RESOLUTION = (1280, 720)  # 720p for webcam

    # Lighting Profiles
    LIGHT_PROFILES = {
        'ocr': {'r': 255, 'g': 255, 'b': 255, 'w': 255},  # White for OCR
        'grading': {'r': 255, 'g': 250, 'b': 240, 'w': 200},  # Warm white
        'foil': {'r': 0, 'g': 0, 'b': 0, 'w': 0},  # Off for foil detection
        'off': {'r': 0, 'g': 0, 'b': 0, 'w': 0}
    }

    # OCR Settings
    OCR_TIMEOUT = 30
    MIN_CONFIDENCE = 70

    @classmethod
    def load_from_file(cls, filepath):
        """Load config from JSON file"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(cls, key.upper()):
                        setattr(cls, key.upper(), value)
        return cls

# =============================================================================
# LOGGING SETUP
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/nexus_scanner.log')
    ]
)
logger = logging.getLogger("Pi5Scanner")

# =============================================================================
# HARDWARE CONTROLLERS
# =============================================================================
class ESP32Controller:
    """
    Control ESP32 hardware:
    - WS2814 RGBW lightbox (17 LEDs)
    - NeoPixel logo ring (16 LEDs)
    - PCA9685 servo controller (8 channels)
    - Relay control
    """

    def __init__(self, port=None, baudrate=115200):
        self.port = port or ScannerConfig.ESP32_PORT
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.lock = Lock()

    def connect(self):
        """Connect to ESP32"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)  # Wait for ESP32 reset

            # Clear startup messages
            while self.serial.in_waiting:
                self.serial.readline()

            self.connected = True
            logger.info(f"ESP32 connected on {self.port}")
            return True
        except Exception as e:
            logger.error(f"ESP32 connection failed: {e}")
            self.connected = False
            return False

    def send_command(self, command, wait_response=True):
        """Send command to ESP32"""
        if not self.connected:
            return None

        with self.lock:
            try:
                self.serial.write(f"{command}\n".encode())
                self.serial.flush()

                if wait_response:
                    time.sleep(0.1)
                    responses = []
                    while self.serial.in_waiting:
                        line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            responses.append(line)
                    return responses
                return True
            except Exception as e:
                logger.error(f"ESP32 command error: {e}")
                return None

    def set_lightbox(self, r, g, b, w):
        """Set RGBW lightbox color"""
        return self.send_command(f"LIGHT:{r},{g},{b},{w}")

    def set_logo_ring(self, r, g, b):
        """Set RGB logo ring color"""
        return self.send_command(f"LOGO:{r},{g},{b}")

    def set_servo(self, channel, angle):
        """Set servo angle (0-180)"""
        return self.send_command(f"SERVO:{channel},{angle}")

    def set_relay(self, state):
        """Set relay state (0/1)"""
        return self.send_command(f"RELAY:{int(state)}")

    def lights_off(self):
        """Turn off all lights"""
        self.set_lightbox(0, 0, 0, 0)
        self.set_logo_ring(0, 0, 0)

    def disconnect(self):
        """Close connection"""
        if self.serial:
            self.lights_off()
            self.serial.close()
            self.connected = False


class ArduinoController:
    """
    Control Arduino Micro:
    - 3x NeoPixel scanner rings (16 LEDs each)
    - Pins 5, 6, 7
    """

    def __init__(self, port=None, baudrate=115200):
        self.port = port or ScannerConfig.ARDUINO_PORT
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.lock = Lock()

    def connect(self):
        """Connect to Arduino"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)  # Wait for Arduino reset

            # Clear startup messages
            while self.serial.in_waiting:
                self.serial.readline()

            self.connected = True
            logger.info(f"Arduino connected on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Arduino connection failed: {e}")
            self.connected = False
            return False

    def send_command(self, command):
        """Send command to Arduino"""
        if not self.connected:
            return None

        with self.lock:
            try:
                self.serial.write(f"{command}\n".encode())
                self.serial.flush()
                time.sleep(0.05)

                responses = []
                while self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        responses.append(line)
                return responses
            except Exception as e:
                logger.error(f"Arduino command error: {e}")
                return None

    def set_ring(self, ring_id, r, g, b):
        """Set individual ring color (0-2)"""
        return self.send_command(f"RING:{ring_id},{r},{g},{b}")

    def set_all_rings(self, r, g, b):
        """Set all rings to same color"""
        return self.send_command(f"ALL:{r},{g},{b}")

    def rings_off(self):
        """Turn off all rings"""
        return self.set_all_rings(0, 0, 0)

    def disconnect(self):
        """Close connection"""
        if self.serial:
            self.rings_off()
            self.serial.close()
            self.connected = False


class CameraManager:
    """
    Manage multiple cameras:
    - OwlEye 64MP (CSI) - Picamera2
    - CZUR Scanner (USB) - OpenCV
    - Webcam (USB) - OpenCV
    """

    def __init__(self):
        self.cameras = {}
        self.active_camera = None

    def init_owleye(self):
        """Initialize OwlEye CSI camera"""
        if not PICAMERA2_AVAILABLE:
            logger.warning("picamera2 not available - OwlEye disabled")
            return False

        try:
            picam = Picamera2(ScannerConfig.OWLEYE_INDEX)
            config = picam.create_still_configuration(
                main={"size": ScannerConfig.SCAN_RESOLUTION}
            )
            picam.configure(config)
            picam.start()
            time.sleep(1)  # Camera warmup

            self.cameras['owleye'] = {
                'type': 'picamera2',
                'device': picam,
                'resolution': ScannerConfig.SCAN_RESOLUTION
            }
            logger.info("OwlEye 64MP initialized")
            return True
        except Exception as e:
            logger.error(f"OwlEye init failed: {e}")
            return False

    def init_czur(self):
        """Initialize CZUR USB scanner"""
        try:
            cap = cv2.VideoCapture(ScannerConfig.CZUR_INDEX)
            if not cap.isOpened():
                raise Exception("CZUR camera failed to open")

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, ScannerConfig.CZUR_RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ScannerConfig.CZUR_RESOLUTION[1])

            self.cameras['czur'] = {
                'type': 'opencv',
                'device': cap,
                'resolution': ScannerConfig.CZUR_RESOLUTION
            }
            logger.info("CZUR scanner initialized")
            return True
        except Exception as e:
            logger.error(f"CZUR init failed: {e}")
            return False

    def init_webcam(self):
        """Initialize USB webcam"""
        try:
            cap = cv2.VideoCapture(ScannerConfig.WEBCAM_INDEX)
            if not cap.isOpened():
                raise Exception("Webcam failed to open")

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, ScannerConfig.WEBCAM_RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ScannerConfig.WEBCAM_RESOLUTION[1])

            self.cameras['webcam'] = {
                'type': 'opencv',
                'device': cap,
                'resolution': ScannerConfig.WEBCAM_RESOLUTION
            }
            logger.info("Webcam initialized")
            return True
        except Exception as e:
            logger.error(f"Webcam init failed: {e}")
            return False

    def capture(self, camera_name):
        """Capture image from specified camera"""
        if camera_name not in self.cameras:
            logger.error(f"Camera '{camera_name}' not initialized")
            return None

        cam = self.cameras[camera_name]

        try:
            if cam['type'] == 'picamera2':
                # OwlEye via picamera2
                frame = cam['device'].capture_array()
                # Convert RGB to BGR for OpenCV compatibility
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return frame

            elif cam['type'] == 'opencv':
                # CZUR/Webcam via OpenCV
                ret, frame = cam['device'].read()
                if ret:
                    return frame
                return None

        except Exception as e:
            logger.error(f"Capture error on {camera_name}: {e}")
            return None

    def release_all(self):
        """Release all cameras"""
        for name, cam in self.cameras.items():
            try:
                if cam['type'] == 'picamera2':
                    cam['device'].stop()
                elif cam['type'] == 'opencv':
                    cam['device'].release()
                logger.info(f"Released {name}")
            except Exception as e:
                logger.error(f"Error releasing {name}: {e}")

        self.cameras.clear()

# =============================================================================
# SCANNER ORCHESTRATOR
# =============================================================================
class ScannerOrchestrator:
    """
    Main scanner logic - coordinates cameras, lighting, and OCR
    Implements multi-pass capture protocol (Patent Claims 3, 10, 12)
    """

    def __init__(self):
        self.esp32 = ESP32Controller()
        self.arduino = ArduinoController()
        self.cameras = CameraManager()
        self.brok_url = ScannerConfig.BROK_URL

        self.scan_count = 0
        self.scan_dir = Path(ScannerConfig.SCAN_DIR)
        self.scan_dir.mkdir(parents=True, exist_ok=True)

        self.initialized = False

    def initialize(self):
        """Initialize all hardware"""
        logger.info("=== NEXUS Pi5 Scanner Initializing ===")

        # Connect ESP32
        if not self.esp32.connect():
            logger.warning("ESP32 not connected - lighting disabled")

        # Connect Arduino
        if not self.arduino.connect():
            logger.warning("Arduino not connected - ring LEDs disabled")

        # Initialize cameras
        self.cameras.init_owleye()
        self.cameras.init_czur()
        self.cameras.init_webcam()

        if not self.cameras.cameras:
            logger.error("No cameras initialized!")
            return False

        # Test lights
        logger.info("Testing lighting system...")
        self.set_lighting_profile('ocr')
        time.sleep(0.5)
        self.set_lighting_profile('off')

        self.initialized = True
        logger.info("=== Scanner Ready ===")
        return True

    def set_lighting_profile(self, profile_name):
        """Set lighting based on profile"""
        if profile_name not in ScannerConfig.LIGHT_PROFILES:
            logger.error(f"Unknown profile: {profile_name}")
            return False

        profile = ScannerConfig.LIGHT_PROFILES[profile_name]

        # Set lightbox
        if self.esp32.connected:
            self.esp32.set_lightbox(
                profile['r'], profile['g'], profile['b'], profile['w']
            )

        # Set scanner rings
        if self.arduino.connected:
            self.arduino.set_all_rings(
                profile['r'], profile['g'], profile['b']
            )

        return True

    def scan_card(self, camera='owleye', mode='ocr'):
        """
        Scan a card with specified camera and mode

        Args:
            camera: 'owleye', 'czur', or 'webcam'
            mode: 'ocr', 'grading', 'foil'

        Returns:
            dict with scan results and OCR data
        """
        self.scan_count += 1
        logger.info(f"Scan #{self.scan_count} - Camera: {camera}, Mode: {mode}")

        # Set lighting for mode
        self.set_lighting_profile(mode)
        time.sleep(0.2)  # Let camera adjust

        # Capture image
        frame = self.cameras.capture(camera)

        if frame is None:
            logger.error("Capture failed!")
            self.set_lighting_profile('off')
            return {'error': 'Capture failed'}

        # Save image
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"scan_{timestamp}_{camera}_{mode}.jpg"
        filepath = self.scan_dir / filename
        cv2.imwrite(str(filepath), frame)
        logger.info(f"Saved: {filepath}")

        # Turn lights off
        self.set_lighting_profile('off')

        # Send to Brok for OCR (if mode is ocr)
        if mode == 'ocr':
            logger.info("Sending to Brok for OCR...")
            ocr_result = self.send_to_brok(filepath)

            return {
                'success': True,
                'scan_id': self.scan_count,
                'filename': filename,
                'filepath': str(filepath),
                'camera': camera,
                'mode': mode,
                'ocr': ocr_result
            }

        return {
            'success': True,
            'scan_id': self.scan_count,
            'filename': filename,
            'filepath': str(filepath),
            'camera': camera,
            'mode': mode
        }

    def send_to_brok(self, image_path):
        """Send image to Brok server for OCR"""
        try:
            with open(image_path, 'rb') as f:
                files = {'image': f}
                response = requests.post(
                    f"{self.brok_url}/api/ocr",
                    files=files,
                    timeout=ScannerConfig.OCR_TIMEOUT
                )

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f"Brok error: {response.status_code}"}

        except Exception as e:
            logger.error(f"Brok request failed: {e}")
            return {'error': str(e)}

    def multi_pass_scan(self):
        """
        Execute multi-pass capture protocol
        1. Motion detection
        2. Back scan (type detection)
        3. Flat scan (OCR)
        4. Surface scan (grading)
        5. Foil scan (holographic detection)
        """
        logger.info("Starting multi-pass scan protocol...")

        results = {
            'motion': None,
            'back': None,
            'flat': None,
            'surface': None,
            'foil': None,
            'best_result': None
        }

        # 1. Motion detection (webcam)
        if 'webcam' in self.cameras.cameras:
            logger.info("Pass 1: Motion detection")
            results['motion'] = self.scan_card('webcam', 'ocr')

        # 2. Back scan for type detection
        logger.info("Pass 2: Back scan")
        # TODO: Implement card back detection

        # 3. Flat scan for OCR
        logger.info("Pass 3: Flat scan (OCR)")
        results['flat'] = self.scan_card('owleye', 'ocr')

        # 4. Surface scan for grading
        logger.info("Pass 4: Surface scan (grading)")
        results['surface'] = self.scan_card('owleye', 'grading')

        # 5. Foil scan
        logger.info("Pass 5: Foil detection")
        results['foil'] = self.scan_card('owleye', 'foil')

        # Select best result
        if results['flat'] and 'ocr' in results['flat']:
            results['best_result'] = results['flat']['ocr']

        return results

    def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down scanner...")
        self.set_lighting_profile('off')
        self.esp32.disconnect()
        self.arduino.disconnect()
        self.cameras.release_all()
        logger.info("Scanner shutdown complete")

# =============================================================================
# FLASK API SERVER
# =============================================================================
app = Flask(__name__)
scanner = None  # Global scanner instance

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'scanner_initialized': scanner.initialized if scanner else False,
        'cameras': list(scanner.cameras.cameras.keys()) if scanner else [],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """
    Scan a card
    POST body: {"camera": "owleye", "mode": "ocr"}
    """
    if not scanner or not scanner.initialized:
        return jsonify({'error': 'Scanner not initialized'}), 500

    data = request.get_json() or {}
    camera = data.get('camera', 'owleye')
    mode = data.get('mode', 'ocr')

    result = scanner.scan_card(camera, mode)
    return jsonify(result)

@app.route('/api/multi_scan', methods=['POST'])
def api_multi_scan():
    """Execute multi-pass scan protocol"""
    if not scanner or not scanner.initialized:
        return jsonify({'error': 'Scanner not initialized'}), 500

    result = scanner.multi_pass_scan()
    return jsonify(result)

@app.route('/api/lights', methods=['POST'])
def api_lights():
    """
    Control lights
    POST body: {"profile": "ocr"} or {"lightbox": {"r": 255, ...}}
    """
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    data = request.get_json() or {}

    if 'profile' in data:
        success = scanner.set_lighting_profile(data['profile'])
        return jsonify({'success': success})

    if 'lightbox' in data:
        lb = data['lightbox']
        scanner.esp32.set_lightbox(
            lb.get('r', 0), lb.get('g', 0), lb.get('b', 0), lb.get('w', 0)
        )
        return jsonify({'success': True})

    return jsonify({'error': 'Invalid request'}), 400

@app.route('/api/capture/<camera>', methods=['GET'])
def api_capture(camera):
    """Capture image without processing"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    frame = scanner.cameras.capture(camera)
    if frame is None:
        return jsonify({'error': f'Camera {camera} not available'}), 404

    # Encode as JPEG
    _, buffer = cv2.imencode('.jpg', frame)
    return send_file(
        BytesIO(buffer.tobytes()),
        mimetype='image/jpeg'
    )

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get scanner status"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    return jsonify({
        'initialized': scanner.initialized,
        'scan_count': scanner.scan_count,
        'cameras': list(scanner.cameras.cameras.keys()),
        'esp32_connected': scanner.esp32.connected,
        'arduino_connected': scanner.arduino.connected,
        'brok_url': scanner.brok_url
    })

# =============================================================================
# MAIN
# =============================================================================
def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("Interrupt received, shutting down...")
    if scanner:
        scanner.shutdown()
    sys.exit(0)

def main():
    """Main entry point"""
    global scanner

    parser = argparse.ArgumentParser(description='NEXUS Pi5 Scanner')
    parser.add_argument('--server', action='store_true', help='Run as Flask server')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('--config', type=str, help='Config file path')
    args = parser.parse_args()

    # Load config
    if args.config:
        ScannerConfig.load_from_file(args.config)
    elif os.path.exists(ScannerConfig.CONFIG_FILE):
        ScannerConfig.load_from_file(ScannerConfig.CONFIG_FILE)

    # Initialize scanner
    scanner = ScannerOrchestrator()
    signal.signal(signal.SIGINT, signal_handler)

    if not scanner.initialize():
        logger.error("Scanner initialization failed!")
        return 1

    if args.server:
        # Run as Flask server
        logger.info(f"Starting Flask server on {ScannerConfig.SERVER_HOST}:{ScannerConfig.SERVER_PORT}")
        app.run(
            host=ScannerConfig.SERVER_HOST,
            port=ScannerConfig.SERVER_PORT,
            debug=False
        )

    elif args.interactive:
        # Interactive mode
        logger.info("Interactive mode - Commands: scan, multi, lights, status, quit")

        try:
            while True:
                cmd = input("> ").strip().lower()

                if cmd == 'quit' or cmd == 'q':
                    break
                elif cmd == 'scan':
                    result = scanner.scan_card('owleye', 'ocr')
                    print(json.dumps(result, indent=2))
                elif cmd == 'multi':
                    result = scanner.multi_pass_scan()
                    print(json.dumps(result, indent=2))
                elif cmd == 'lights':
                    profile = input("Profile (ocr/grading/foil/off): ")
                    scanner.set_lighting_profile(profile)
                elif cmd == 'status':
                    print(f"Scan count: {scanner.scan_count}")
                    print(f"Cameras: {list(scanner.cameras.cameras.keys())}")
                else:
                    print("Unknown command")

        except KeyboardInterrupt:
            pass

        finally:
            scanner.shutdown()

    else:
        # Single scan and exit
        result = scanner.scan_card('owleye', 'ocr')
        print(json.dumps(result, indent=2))
        scanner.shutdown()

    return 0

if __name__ == '__main__':
    sys.exit(main())
