#!/usr/bin/env python3
"""
SNARF - Scanner Control Server (Patent Pending)
NEXUS V2 Collectibles Management System
Copyright 2025-2026 Kevin Caracozza - All Rights Reserved
Patent Filed: November 27, 2025

Hardware Configuration (Feb 2026):
  ESP32 (/dev/ttyUSB0):
    - Base stepper: TB6600 - DIR 18/19, PUL 33/25
    - Lightbox: WS2812B (17 LEDs, GPIO 27)
    - PCA9685 servo controller:
      Ch 0: Shoulder servo
      Ch 1: Wrist servo
      Ch 3: Elbow servo
      Ch 5: Solenoid relay
      Ch 6: Vacuum relay

  Arduino Micro (/dev/ttyACM0):
    - Ch1: Pin 5 (60 LEDs)
    - Ch2: Pin 6 (48 LEDs)

  Cameras:
    - OwlEye 64MP (CSI): Primary scanner, grading, high-res capture
    - CZUR (USB): Bulk document scanning
    - Webcam (USB): Motion detection, case monitoring

Multi-Pass Capture Protocol (Patent Claims 3, 10, 12):
  1. Motion detect via webcam → card presence
  2. Back scan → card type identification (MTG/Pokemon/Sports)
  3. Flat scan (top ring) → OCR-optimized lighting
  4. Surface scan (side rings) → grading-optimized lighting
  5. Foil scan (rainbow sweep) → holographic detection
  6. Best frame selection → forward to Brok OCR server
"""

import os
import json
import time
import logging
import subprocess
from io import BytesIO
from datetime import datetime
from threading import Thread, Event

import cv2
import numpy as np
import serial
import requests
from flask import Flask, jsonify, request, send_file, Response

# Optional picamera2 for CSI cameras on Pi 5
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None

# =============================================================================
# CONFIGURATION (Environment Variables with Defaults)
# =============================================================================
# Network
BROK_URL = os.getenv('NEXUS_BROK_URL', 'http://192.168.1.174:5000')
SERVER_PORT = int(os.getenv('SNARF_PORT', '5001'))
RELAY_URL = os.getenv('NEXUS_RELAY_URL', 'https://narwhal-council-relay.kcaracozza.workers.dev')
SCANNER_ID = 'snarf'  # Scanner identifier for relay

# Serial Ports
LED_PORT = os.getenv('SNARF_LED_PORT', '/dev/ttyUSB0')
ARM_PORT = os.getenv('SNARF_ARM_PORT', '/dev/ttyUSB0')  # Same as LED
RING_PORT = os.getenv('SNARF_RING_PORT', '/dev/ttyACM0')
BAUD = 115200

# Directories
SCAN_DIR = os.getenv('SNARF_SCAN_DIR', '/home/nexus1/scans')
SETTINGS_DIR = os.getenv('SNARF_SETTINGS_DIR', '/home/nexus1')

# Hardware Constants
NUM_SERVOS = 8
NUM_LED_CH = 2  # Arduino Micro: CH1 (60 LEDs pin 5), CH2 (48 LEDs pin 6)
DEFAULT_SERVO_ANGLE = 90
SERIAL_TIMEOUT = 2.0
SERIAL_READ_DELAY = 0.1

# Debug mode (enables /api/debug/* endpoints - DISABLE IN PRODUCTION)
DEBUG_MODE = os.getenv('SNARF_DEBUG', 'false').lower() == 'true'

# =============================================================================
# FLASK APP SETUP
# =============================================================================
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("SNARF")

# =============================================================================
# CAMERA CONFIGURATION
# =============================================================================
# Device mapping (v4l2-ctl --list-devices):
#   HD Web Camera: /dev/video8, /dev/video9
#   CZUR USB HD MIC: /dev/video0, /dev/video11
#   CSI cameras via rp1-cfe: /dev/video0-7
CAMERAS = {
    'owleye': {'type': 'csi', 'index': 0, 'resolution': (4624, 3472)},
    'czur': {'type': 'usb', 'device': '/dev/video2', 'resolution': (3264, 2448)},
    'webcam': {'type': 'usb', 'device': '/dev/video0', 'resolution': (1920, 1080)},
}

# Ensure directories exist
os.makedirs(SCAN_DIR, exist_ok=True)
os.makedirs(SETTINGS_DIR, exist_ok=True)

# =============================================================================
# RELAY PUSH - Jaques Eyes
# =============================================================================
def push_to_relay(camera, scan_result=None, card_detected=False, ocr_text=None, frame_base64=None):
    """
    Push scan result to Narwhal Council Relay so Jaques can see it.
    Non-blocking - failures are logged but don't interrupt scanning.

    If frame_base64 is None but scan_result is a file path, will auto-encode the image.
    """
    try:
        # Auto-encode image if file path provided but no base64
        if frame_base64 is None and scan_result and os.path.isfile(scan_result):
            try:
                import base64
                with open(scan_result, 'rb') as f:
                    img_data = f.read()
                    # Create thumbnail for relay (max 800px wide to keep payload small)
                    import cv2
                    import numpy as np
                    nparr = np.frombuffer(img_data, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img is not None:
                        h, w = img.shape[:2]
                        if w > 800:
                            scale = 800 / w
                            img = cv2.resize(img, (800, int(h * scale)))
                        _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        frame_base64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"
                        logger.info(f"Auto-encoded {scan_result} for relay ({len(frame_base64)//1024}KB)")
            except Exception as e:
                logger.warning(f"Failed to auto-encode image for relay: {e}")

        payload = {
            'scanner': SCANNER_ID,
            'camera': camera,
            'card_detected': card_detected,
            'scan_result': scan_result,
            'ocr_text': ocr_text,
            'frame': frame_base64,  # Include actual image data for Jaques to see
        }
        # Push asynchronously via thread
        def _push():
            try:
                resp = requests.post(
                    f'{RELAY_URL}/camera/push',
                    json=payload,
                    timeout=5
                )
                if resp.ok:
                    logger.info(f"Relay push OK: {camera}")
                else:
                    logger.warning(f"Relay push failed: {resp.status_code}")
            except Exception as e:
                logger.debug(f"Relay push error (non-fatal): {e}")
        Thread(target=_push, daemon=True).start()
    except Exception as e:
        logger.debug(f"Relay push setup error: {e}")


def check_relay_requests():
    """
    Poll relay for pending capture requests from Jaques.
    Returns request dict or None.
    """
    try:
        resp = requests.get(f'{RELAY_URL}/camera/requests/{SCANNER_ID}', timeout=3)
        if resp.ok:
            data = resp.json()
            if data.get('pending_request'):
                return data.get('request')
    except Exception as e:
        logger.debug(f"Relay request check error: {e}")
    return None


def push_file_listing():
    """
    Push scan file listing to relay so Jaques can browse files.
    """
    try:
        if not os.path.exists(SCAN_DIR):
            return

        files = []
        for filename in os.listdir(SCAN_DIR):
            filepath = os.path.join(SCAN_DIR, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'camera': 'owleye' if 'owleye' in filename.lower() else
                             'czur' if 'czur' in filename.lower() else
                             'webcam' if 'webcam' in filename.lower() else 'unknown',
                    'url': f'http://192.168.1.172:5001/scans/{filename}'
                })

        # Sort by modified time, newest first
        files.sort(key=lambda x: x['modified'], reverse=True)
        files = files[:100]  # Limit to 100 files

        # Generate thumbnails for recent images (last 10)
        thumbnails = {}
        for f in files[:10]:
            if f['filename'].lower().endswith(('.jpg', '.jpeg', '.png')):
                try:
                    filepath = os.path.join(SCAN_DIR, f['filename'])
                    img = cv2.imread(filepath)
                    if img is not None:
                        # Resize to thumbnail (200px width)
                        h, w = img.shape[:2]
                        new_w = 200
                        new_h = int(h * new_w / w)
                        thumb = cv2.resize(img, (new_w, new_h))
                        # Encode to base64
                        _, buffer = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        import base64
                        thumb_b64 = base64.b64encode(buffer).decode('utf-8')
                        thumbnails[f['filename']] = {
                            'metadata': f,
                            'thumbnail': f'data:image/jpeg;base64,{thumb_b64}'
                        }
                except Exception as e:
                    logger.debug(f"Thumbnail error for {f['filename']}: {e}")

        # Push to relay
        resp = requests.post(
            f'{RELAY_URL}/files/push',
            json={
                'scanner': SCANNER_ID,
                'files': files,
                'thumbnails': thumbnails
            },
            timeout=10
        )
        if resp.ok:
            logger.info(f"File listing pushed: {len(files)} files, {len(thumbnails)} thumbnails")
        else:
            logger.warning(f"File listing push failed: {resp.status_code}")
    except Exception as e:
        logger.debug(f"File listing push error: {e}")


# =============================================================================
# STATE VARIABLES
# =============================================================================
# 8-DOF arm+lift servo positions
# Channels: 0=Base, 1=Shoulder, 2=Elbow, 3=WristRoll, 4=WristPitch,
#           5=Grip/Vacuum, 6=LiftShoulder, 7=LiftTilt
arm_angles = [DEFAULT_SERVO_ANGLE] * NUM_SERVOS
arm_angles[5] = 0  # Vacuum off
arm_angles[6] = 0  # Lift down
base_angle = 0  # Base stepper position in degrees

# Arm preset file (JSON, persists across restarts)
ARM_PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'arm_presets.json')

# Default presets matching ESP32 firmware home position
DEFAULT_ARM_PRESETS = {
    'home':   {"shoulder": 115, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 29, "base": 0},
    'scan':   {"shoulder": 60, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 120, "base": 0},
    'pickup': {"shoulder": 45, "wrist_yaw": 98, "wrist_pitch": 60, "elbow": 127, "base": 0},
    'eject':  {"shoulder": 115, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 29, "base": 90},
    'stack':  {"shoulder": 115, "wrist_yaw": 98, "wrist_pitch": 108, "elbow": 29, "base": 180},
}

def load_arm_presets():
    """Load arm presets from JSON file, fall back to defaults."""
    if os.path.exists(ARM_PRESETS_FILE):
        try:
            with open(ARM_PRESETS_FILE, 'r') as f:
                presets = json.load(f)
            logger.info(f"Loaded {len(presets)} arm presets from {ARM_PRESETS_FILE}")
            return presets
        except Exception as e:
            logger.error(f"Failed to load arm presets: {e}")
    return dict(DEFAULT_ARM_PRESETS)

def save_arm_presets(presets):
    """Save arm presets to JSON file."""
    try:
        with open(ARM_PRESETS_FILE, 'w') as f:
            json.dump(presets, f, indent=2)
        logger.info(f"Saved {len(presets)} arm presets to {ARM_PRESETS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save arm presets: {e}")
        return False

arm_presets = load_arm_presets()

# Servo calibration settings (per joint)
servo_settings = {
    'trim': [0] * NUM_SERVOS,
    'min': [0] * NUM_SERVOS,
    'max': [180] * NUM_SERVOS,
    'expo': [0] * NUM_SERVOS
}

# LED channel settings (Arduino Micro: CH1=60 LEDs, CH2=48 LEDs)
led_settings = {
    'brightness': [255] * NUM_LED_CH,
    'enabled': [1] * NUM_LED_CH
}

# Motion detection state
motion_event = Event()
last_motion_frame = None
card_present = False

# Auto-scan state
autoscan_running = False
autoscan_thread = None
last_scan_result = None

# LED Feedback patterns (ch1=60 LEDs, ch2=48 LEDs)
LED_PATTERNS = {
    'ready': {'ch1': (0, 50, 0), 'ch2': (0, 0, 0)},      # Dim green = ready
    'scanning': {'ch1': (0, 0, 255), 'ch2': (0, 0, 255)},  # Blue pulse
    'success': {'ch1': (0, 255, 0), 'ch2': (0, 255, 0)},   # Green flash
    'fail': {'ch1': (255, 0, 0), 'ch2': (255, 0, 0)},      # Red flash
    'motion': {'ch1': (255, 255, 0), 'ch2': (0, 0, 0)},    # Yellow = motion detected
}


def send_to_esp(port, command):
    try:
        with serial.Serial(port, BAUD, timeout=2) as ser:
            ser.write(f"{command}\n".encode())
            time.sleep(0.1)
            response = ser.readline().decode().strip()
            logger.info(f"ESP32 [{port}]: {command} -> {response}")
            return response or "OK"
    except Exception as e:
        logger.error(f"Serial error on {port}: {e}")
        return None


def leds_off():
    """Turn off all LEDs. ESP32 expects light off and RG 0 0 0 (robo_arm_clean.ino)."""
    send_to_esp(LED_PORT, "light off")
    send_to_esp(LED_PORT, "RG 0 0 0")


# Current focus position (reciprocal distance: 0=infinity, ~9=11cm for card scanning)
current_lens_position = 9.0  # Calibrated for NEXUS scanner (~11cm card distance)

# =============================================================================
# LOCKED CAMERA SETTINGS FOR CONSISTENT IMAGING (95%+ accuracy target)
# =============================================================================
# These settings ensure every capture is identical - no auto-anything
CAMERA_LOCKED_SETTINGS = {
    'shutter': 10000,      # Fixed shutter speed in microseconds (10ms)
    'gain': 1.5,           # Fixed analog gain (1.0-16.0, lower = less noise)
    'awb': 'tungsten',     # Fixed white balance (tungsten for LED lighting)
    'brightness': 0.0,     # No brightness adjustment (-1.0 to 1.0)
    'contrast': 1.0,       # Normal contrast (0.0 to 2.0)
    'saturation': 1.0,     # Normal saturation (0.0 to 2.0)
    'sharpness': 1.5,      # Slight sharpening for OCR (0.0 to 2.0)
    'denoise': 'off',      # No denoising (preserves detail for grading)
    'settle_time': 0.3,    # Seconds to wait for card to stop moving
}


def get_best_frame(device, count=5, width=1920, height=1080):
    """Capture multiple frames, return the one with least glare.

    Args:
        device: Video device path (e.g., '/dev/video0')
        count: Number of frames to capture
        width, height: Capture resolution

    Returns:
        Best frame (numpy array) or None if capture failed
    """
    try:
        # Convert device path to index for cv2
        if isinstance(device, str) and '/dev/video' in device:
            dev_num = int(device.replace('/dev/video', ''))
        else:
            dev_num = int(device) if device else 0

        camera = cv2.VideoCapture(dev_num)
        camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)  # auto exposure
        # Warmup at low res for speed, then switch to full res
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not camera.isOpened():
            logger.error(f"Could not open camera {device}")
            return None

        # Let auto-exposure settle at low res (fast)
        for _ in range(20):
            camera.read()
            time.sleep(0.05)

        # Switch to full resolution for actual capture
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        time.sleep(0.2)
        camera.read()  # flush one frame at new res

        frames = []
        for i in range(count):
            ret, frame = camera.read()
            if ret and frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                glare_score = np.sum(gray > 250)  # Count blown pixels
                frames.append((glare_score, frame))
                time.sleep(0.05)  # Small delay between captures

        camera.release()

        if not frames:
            logger.warning("No valid frames captured")
            return None

        # Sort by glare (lowest first), return cleanest frame
        frames.sort(key=lambda x: x[0])
        logger.info(f"Best frame glare: {frames[0][0]}, worst: {frames[-1][0]}")
        return frames[0][1]

    except Exception as e:
        logger.error(f"get_best_frame failed: {e}")
        return None


def capture_owleye(camera=0, width=4624, height=3472, suffix="", autofocus=False, lens_position=None, locked=True):
    """Capture from OwlEye 64MP camera using rpicam-still

    Args:
        camera: CSI camera index (0 or 1)
        width, height: Resolution
        suffix: Filename suffix
        autofocus: Use auto-focus (slower, may not work well for fixed distance)
        lens_position: Manual focus position (0=infinity, ~6.5=15cm for cards)
        locked: Use locked settings for consistent imaging (default True)
    """
    global current_lens_position
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{SCAN_DIR}/owleye{camera}_{timestamp}{suffix}.jpg"

    # Wait for card to settle before capture
    if locked:
        time.sleep(CAMERA_LOCKED_SETTINGS['settle_time'])

    try:
        cmd = [
            'rpicam-still',
            '--camera', str(camera),
            '-o', filename,
            '--width', str(width),
            '--height', str(height),
            '-n'
        ]

        # LOCKED MODE: Use fixed settings for consistent imaging
        if locked:
            settings = CAMERA_LOCKED_SETTINGS
            cmd.extend([
                '--shutter', str(settings['shutter']),
                '--gain', str(settings['gain']),
                '--awb', settings['awb'],
                '--brightness', str(settings['brightness']),
                '--contrast', str(settings['contrast']),
                '--saturation', str(settings['saturation']),
                '--sharpness', str(settings['sharpness']),
                '--denoise', settings['denoise'],
                '-t', '300',
                '--lens-position', str(lens_position or current_lens_position)
            ])
            logger.info(f"OwlEye {camera}: LOCKED mode (consistent imaging)")
        # Focus control - prefer manual lens position for consistent scanning
        elif lens_position is not None:
            cmd.extend(['-t', '300', '--lens-position', str(lens_position)])
        elif autofocus:
            cmd.extend([
                '-t', '1500',
                '--autofocus-mode', 'auto',
                '--autofocus-on-capture'
            ])
        else:
            # Use stored lens position for manual focus
            cmd.extend([
                '-t', '300',
                '--lens-position', str(current_lens_position)
            ])

        result = subprocess.run(cmd, capture_output=True, timeout=15)

        if os.path.exists(filename):
            # OwlEye is mounted upside-down - rotate 180 degrees
            try:
                img = cv2.imread(filename)
                if img is not None:
                    img = cv2.rotate(img, cv2.ROTATE_180)
                    cv2.imwrite(filename, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    logger.info(f"OwlEye {camera} captured + rotated 180°: {filename}")
                else:
                    logger.warning(f"OwlEye {camera} captured but couldn't read for rotation: {filename}")
            except Exception as rot_err:
                logger.warning(f"OwlEye rotation failed (using as-is): {rot_err}")
            return filename
        else:
            logger.error(f"OwlEye {camera} failed: {result.stderr.decode()}")
            return None
    except Exception as e:
        logger.error(f"OwlEye {camera} error: {e}")
        return None


def capture_usb(device='/dev/video0', width=1920, height=1080, suffix="", autofocus=True, cam_name=None):
    """Capture from USB camera (webcam or CZUR)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Determine camera name from device or passed name
    if not cam_name:
        cam_name = "czur" if "video2" in device else "webcam"
    filename = f"{SCAN_DIR}/{cam_name}_{timestamp}{suffix}.jpg"

    try:
        # All USB cameras use fswebcam (handles exposure properly)
        # -S skips frames to let auto-exposure settle
        skip = 20 if 'czur' in cam_name.lower() else 10
        cmd = [
            'fswebcam',
            '-d', device,
            '--no-banner',
            '-r', f'{width}x{height}',
            '-S', str(skip),
            filename
        ]
        logger.info(f"USB capture: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if not os.path.exists(filename):
            logger.error(f"USB capture failed: {result.stderr.decode() if result.stderr else 'no output'}")
            return None
        logger.info(f"USB captured: {filename} ({os.path.getsize(filename)} bytes)")
        return filename

    except Exception as e:
        logger.error(f"USB capture error: {e}")
        return None


def set_led_ch(ch, r, g, b):
    """Set LED channel color - Arduino Micro (ch=1 or 2)"""
    cmd = f"CH{ch}:{r}:{g}:{b}"
    return send_to_esp(RING_PORT, cmd)


def set_all_leds(ch1=(0,0,0), ch2=(0,0,0)):
    """Set both LED channels at once"""
    set_led_ch(1, *ch1)
    time.sleep(0.05)
    set_led_ch(2, *ch2)


def rainbow_sweep(duration=1.0, steps=10):
    """Sweep rainbow colors across LED channels for foil detection"""
    colors = [
        (255, 0, 0),    # Red
        (255, 127, 0),  # Orange
        (255, 255, 0),  # Yellow
        (0, 255, 0),    # Green
        (0, 255, 255),  # Cyan
        (0, 0, 255),    # Blue
        (127, 0, 255),  # Purple
    ]
    delay = duration / (len(colors) * 2)

    for color in colors:
        set_led_ch(1, *color)
        time.sleep(delay)
        set_led_ch(2, *color)
        time.sleep(delay)


def detect_motion(frame1, frame2, threshold=5000):
    """Detect motion between two frames"""
    if frame1 is None or frame2 is None:
        return False

    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

    # Compute difference
    diff = cv2.absdiff(gray1, gray2)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

    # Count changed pixels
    changed = np.sum(thresh > 0)
    return changed > threshold


def calculate_sharpness(image_path):
    """Calculate image sharpness using Laplacian variance"""
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        return laplacian.var()
    except:
        return 0


def select_best_image(images):
    """Select the sharpest image from a list"""
    if not images:
        return None

    best = None
    best_score = 0

    for img_path in images:
        if img_path and os.path.exists(img_path):
            score = calculate_sharpness(img_path)
            if score > best_score:
                best_score = score
                best = img_path

    return best


# =============================================================================
# LED FEEDBACK SYSTEM
# =============================================================================

def led_feedback(pattern_name, duration=0.5, flash_count=1):
    """Display LED feedback pattern"""
    try:
        pattern = LED_PATTERNS.get(pattern_name, LED_PATTERNS['ready'])

        for _ in range(flash_count):
            set_all_leds(pattern['ch1'], pattern['ch2'])
            time.sleep(duration / flash_count if flash_count > 1 else duration)
            if flash_count > 1:
                send_to_esp(RING_PORT, "OFF")
                time.sleep(0.1)

        # Return to ready state after feedback
        if pattern_name in ['success', 'fail']:
            time.sleep(0.2)
            ready = LED_PATTERNS['ready']
            set_all_leds(ready['ch1'], ready['ch2'])
    except Exception as e:
        logger.error(f"LED feedback error: {e}")


def led_scanning_pulse():
    """Blue pulsing animation during scan"""
    for brightness in range(0, 255, 50):
        set_all_leds((0, 0, brightness), (0, 0, brightness))
        time.sleep(0.05)
    for brightness in range(255, 0, -50):
        set_all_leds((0, 0, brightness), (0, 0, brightness))
        time.sleep(0.05)


# =============================================================================
# CAMERA FAILOVER SYSTEM
# =============================================================================

def capture_owleye_with_failover(width=4624, height=3472, suffix=""):
    """Capture from OwlEye 0, fall back to OwlEye 1 on failure"""
    # Try primary camera
    filename = capture_owleye(0, width, height, suffix)
    if filename:
        return filename, 0

    # Failover to secondary
    logger.warning("OwlEye 0 failed, trying OwlEye 1")
    filename = capture_owleye(1, width, height, suffix)
    if filename:
        return filename, 1

    # Both failed - try CZUR as last resort
    logger.warning("Both OwlEye cameras failed, trying CZUR")
    czur_config = CAMERAS['czur']
    filename = capture_usb(czur_config['device'], *czur_config['resolution'], suffix)
    if filename:
        return filename, 'czur'

    return None, None


# =============================================================================
# WEBCAM MOTION TRIGGER SYSTEM
# =============================================================================

def get_webcam_frame():
    """Capture a single frame from webcam for motion detection"""
    try:
        cap = cv2.VideoCapture(CAMERAS['webcam']['device'])
        if not cap.isOpened():
            # Try numeric index if device path fails
            cap = cv2.VideoCapture(2)  # Usually webcam is index 2

        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                return frame
    except Exception as e:
        logger.error(f"Webcam frame error: {e}")
    return None


def motion_monitor_loop():
    """Background thread that monitors webcam for motion and triggers scan"""
    global autoscan_running, last_motion_frame, card_present, last_scan_result

    logger.info("Motion monitor started - place card to auto-scan")
    led_feedback('ready')

    settle_frames = 0
    required_settle = 3  # Frames of stillness before scanning

    while autoscan_running:
        try:
            frame = get_webcam_frame()
            if frame is None:
                time.sleep(0.5)
                continue

            if last_motion_frame is not None:
                motion = detect_motion(last_motion_frame, frame, threshold=8000)

                if motion:
                    # Motion detected - card being placed
                    settle_frames = 0
                    if not card_present:
                        logger.info("Motion detected - waiting for card to settle")
                        led_feedback('motion', duration=0.2)
                else:
                    # No motion - card might be settled
                    settle_frames += 1

                    if settle_frames >= required_settle and not card_present:
                        # Card has settled - check if something is actually there
                        # (compare to baseline to see if card present)
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        mean_brightness = np.mean(gray)

                        # If brightness changed significantly, card is present
                        if mean_brightness > 30:  # Adjust threshold as needed
                            card_present = True
                            logger.info("Card settled - initiating auto-scan!")

                            # Execute full scan sequence
                            try:
                                led_feedback('scanning', duration=0.3)
                                result = capture_full_sequence_with_feedback()
                                last_scan_result = result

                                if result['success']:
                                    led_feedback('success', duration=0.5, flash_count=2)
                                    logger.info(f"Auto-scan complete: {result['best']}")

                                    # Send to Brok for OCR
                                    send_to_brok(result['best'])
                                else:
                                    led_feedback('fail', duration=0.5, flash_count=3)
                                    logger.error("Auto-scan failed")
                            except Exception as e:
                                logger.error(f"Auto-scan error: {e}")
                                led_feedback('fail', duration=0.5, flash_count=3)

                            # Wait for card removal
                            time.sleep(1)

                    elif settle_frames > 10 and card_present:
                        # Check if card was removed (motion stopped but card might be gone)
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        mean_brightness = np.mean(gray)
                        if mean_brightness < 25:  # Card removed
                            card_present = False
                            settle_frames = 0
                            logger.info("Card removed - ready for next")
                            led_feedback('ready')

            last_motion_frame = frame.copy()
            time.sleep(0.2)  # Check 5 times per second

        except Exception as e:
            logger.error(f"Motion monitor error: {e}")
            time.sleep(1)

    logger.info("Motion monitor stopped")
    leds_off()


def send_to_brok(image_path):
    """Send best image to Brok for OCR processing"""
    try:
        import requests

        # Read image as base64
        import base64
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode()

        response = requests.post(
            f"{BROK_URL}/api/ocr",
            json={"image": image_data, "filename": os.path.basename(image_path)},
            timeout=30
        )

        if response.ok:
            result = response.json()
            logger.info(f"Brok OCR result: {result.get('card_name', 'Unknown')}")
            return result
        else:
            logger.error(f"Brok OCR failed: {response.status_code}")
    except Exception as e:
        logger.error(f"Brok communication error: {e}")
    return None


def capture_full_sequence_with_feedback(camera=0):
    """Full capture sequence with LED feedback"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        'timestamp': timestamp,
        'images': {},
        'best': None,
        'success': False,
        'camera_used': None
    }

    try:
        # === PASS 1: FLAT SCAN (OCR) ===
        logger.info("Pass 1: Flat scan (top ring)")
        set_all_leds(ch1=(255, 255, 255), ch2=(0, 0, 0))
        time.sleep(0.2)

        flat_img, cam_used = capture_owleye_with_failover(suffix="_flat")
        results['images']['flat'] = flat_img
        results['camera_used'] = cam_used

        # === PASS 2: SURFACE SCAN (GRADING) ===
        logger.info("Pass 2: Surface scan (side rings)")
        set_all_leds(ch1=(255, 255, 255), ch2=(255, 255, 255))
        time.sleep(0.2)

        surface_img, _ = capture_owleye_with_failover(suffix="_surface")
        results['images']['surface'] = surface_img

        # === PASS 3: FOIL SCAN (HOLOGRAPHIC) ===
        logger.info("Pass 3: Foil scan (rainbow sweep)")
        foil_frames = []

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
        for i, color in enumerate(colors):
            set_all_leds(ch1=color, ch2=color)
            time.sleep(0.15)
            foil_img, _ = capture_owleye_with_failover(suffix=f"_foil{i}")
            if foil_img:
                foil_frames.append(foil_img)

        results['images']['foil_frames'] = foil_frames

        # === LIGHTS OFF ===
        leds_off()

        # === SELECT BEST IMAGE ===
        all_images = [flat_img, surface_img] + foil_frames
        results['best'] = select_best_image(all_images)
        results['success'] = results['best'] is not None

        # Calculate sharpness scores
        results['sharpness'] = {
            'flat': calculate_sharpness(flat_img) if flat_img else 0,
            'surface': calculate_sharpness(surface_img) if surface_img else 0,
        }

        logger.info(f"Full sequence complete. Best: {results['best']}")

    except Exception as e:
        logger.error(f"Full sequence error: {e}")
        leds_off()

    return results


# =============================================================================
# MULTI-PASS CAPTURE SYSTEM (Patent Claims 3, 10, 12)
# =============================================================================

def capture_full_sequence(camera=0):
    """
    Execute full multi-pass capture sequence:
    1. Flat scan (top ring) - OCR optimized
    2. Surface scan (side rings) - Grading optimized
    3. Foil scan (rainbow sweep) - Holographic detection
    Returns dict with all captured images
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        'timestamp': timestamp,
        'images': {},
        'best': None,
        'success': False
    }

    try:
        # === PASS 1: FLAT SCAN (OCR) ===
        logger.info("Pass 1: Flat scan (top ring)")
        set_all_leds(ch1=(255, 255, 255), ch2=(0, 0, 0))
        time.sleep(0.2)  # Let lights stabilize

        flat_img = capture_owleye(camera, suffix="_flat")
        results['images']['flat'] = flat_img

        # === PASS 2: SURFACE SCAN (GRADING) ===
        logger.info("Pass 2: Surface scan (side rings)")
        set_all_leds(ch1=(255, 255, 255), ch2=(255, 255, 255))
        time.sleep(0.2)

        surface_img = capture_owleye(camera, suffix="_surface")
        results['images']['surface'] = surface_img

        # === PASS 3: FOIL SCAN (HOLOGRAPHIC) ===
        logger.info("Pass 3: Foil scan (rainbow sweep)")
        foil_frames = []

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
        for i, color in enumerate(colors):
            set_all_leds(ch1=color, ch2=color)
            time.sleep(0.15)
            foil_img = capture_owleye(camera, suffix=f"_foil{i}")
            if foil_img:
                foil_frames.append(foil_img)

        results['images']['foil_frames'] = foil_frames

        # === LIGHTS OFF ===
        leds_off()

        # === SELECT BEST IMAGE ===
        all_images = [flat_img, surface_img] + foil_frames
        results['best'] = select_best_image(all_images)
        results['success'] = results['best'] is not None

        # Calculate sharpness scores
        results['sharpness'] = {
            'flat': calculate_sharpness(flat_img) if flat_img else 0,
            'surface': calculate_sharpness(surface_img) if surface_img else 0,
        }

        logger.info(f"Full sequence complete. Best: {results['best']}")

    except Exception as e:
        logger.error(f"Full sequence error: {e}")
        leds_off()  # Safety: lights off on error

    return results


@app.route('/status')
def status():
    return jsonify({
        "status": "online",
        "name": "SNARF",
        "role": "scanner",
        "cameras": list(CAMERAS.keys()),
        "esp32_lightbox": LED_PORT,
        "esp32_arm": ARM_PORT,
        "arduino_leds": RING_PORT,
        "features": ["multi_pass", "motion_detect", "foil_scan", "best_select"],
        "video_streams": ["/api/video/stream", "/api/video/owleye", "/api/video/czur"]
    })


# =============================================================================
# LIVE VIDEO STREAMING FOR FOCUS ADJUSTMENT
# =============================================================================

def generate_video_stream(camera_name='owleye'):
    """Generate MJPEG video stream for live preview."""
    cam_config = CAMERAS.get(camera_name)
    if not cam_config:
        return

    # Open camera
    if cam_config['type'] == 'csi':
        cap = cv2.VideoCapture(cam_config['index'])
    else:
        cap = cv2.VideoCapture(cam_config['device'])

    if not cap.isOpened():
        logger.error(f"Failed to open camera: {camera_name}")
        return

    # Set resolution (lower for streaming)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Add focus guide crosshair
            h, w = frame.shape[:2]
            cv2.line(frame, (w//2-50, h//2), (w//2+50, h//2), (0, 255, 0), 2)
            cv2.line(frame, (w//2, h//2-50), (w//2, h//2+50), (0, 255, 0), 2)

            # Add camera name
            cv2.putText(frame, f"SNARF: {camera_name}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Encode as JPEG
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    finally:
        cap.release()


@app.route('/api/video/stream')
def video_stream():
    """Default video stream (owleye)."""
    from flask import Response
    camera = request.args.get('camera', 'owleye')
    return Response(generate_video_stream(camera),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/video/owleye')
def video_owleye():
    """Live stream from OwlEye camera."""
    from flask import Response
    return Response(generate_video_stream('owleye'),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/video/czur')
def video_czur():
    """Live stream from CZUR scanner."""
    from flask import Response
    return Response(generate_video_stream('czur'),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/snapshot')
def api_snapshot():
    """Get single frame snapshot from camera."""
    camera_name = request.args.get('camera', 'owleye')
    cam_config = CAMERAS.get(camera_name)

    if not cam_config:
        return jsonify({'error': f'Unknown camera: {camera_name}'}), 400

    # Open camera
    if cam_config['type'] == 'csi':
        cap = cv2.VideoCapture(cam_config['index'])
    else:
        cap = cv2.VideoCapture(cam_config['device'])

    if not cap.isOpened():
        return jsonify({'error': f'Camera {camera_name} not available'}), 503

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return jsonify({'error': 'Failed to capture'}), 500

    # Save and return
    path = f'/tmp/{camera_name}_snapshot.jpg'
    cv2.imwrite(path, frame)
    return send_file(path, mimetype='image/jpeg')


@app.route('/api/image', methods=['GET'])
def get_image():
    """Get image file, optionally delete after send."""
    path = request.args.get('path')
    delete_after = request.args.get('delete', 'false').lower() == 'true'

    if path and os.path.exists(path):
        response = send_file(path, mimetype='image/jpeg')
        # Delete after sending if requested (auto-cleanup)
        if delete_after and '/scans/' in path:
            try:
                os.remove(path)
                logger.info(f"Auto-cleanup: deleted {path}")
            except Exception as e:
                logger.warning(f"Failed to delete {path}: {e}")
        return response
    return jsonify({"error": "Image not found"}), 404


@app.route('/api/scans/cleanup', methods=['POST'])
def cleanup_scans():
    """Delete old scans from SD card to free space."""
    data = request.json or {}
    max_age_hours = data.get('max_age_hours', 24)
    dry_run = data.get('dry_run', False)

    scan_dir = os.path.expanduser('~/scans')
    deleted = []
    errors = []

    if os.path.exists(scan_dir):
        now = time.time()
        for f in os.listdir(scan_dir):
            fpath = os.path.join(scan_dir, f)
            if os.path.isfile(fpath):
                age_hours = (now - os.path.getmtime(fpath)) / 3600
                if age_hours > max_age_hours:
                    if dry_run:
                        deleted.append(f)
                    else:
                        try:
                            os.remove(fpath)
                            deleted.append(f)
                        except Exception as e:
                            errors.append(f"{f}: {e}")

    return jsonify({
        "success": True,
        "deleted": deleted,
        "count": len(deleted),
        "errors": errors,
        "dry_run": dry_run
    })


@app.route('/scans/<path:filename>')
def serve_scan_file(filename):
    """Serve scan files directly - Jaques file access."""
    filepath = os.path.join(SCAN_DIR, filename)
    if os.path.isfile(filepath):
        return send_file(filepath)
    return jsonify({"error": "File not found"}), 404


@app.route('/api/scans/list', methods=['GET'])
def list_scan_files_api():
    """List scan files - Jaques file access."""
    limit = request.args.get('limit', 50, type=int)
    filter_type = request.args.get('filter', 'all')

    if not os.path.exists(SCAN_DIR):
        return jsonify({"success": False, "error": "Scan directory not found"})

    files = []
    for filename in os.listdir(SCAN_DIR):
        filepath = os.path.join(SCAN_DIR, filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            f = {
                'filename': filename,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'url': f'/scans/{filename}'
            }

            # Apply filter
            if filter_type == 'images':
                if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    continue
            elif filter_type == 'today':
                today = datetime.now().strftime('%Y%m%d')
                if today not in filename:
                    continue

            files.append(f)

    # Sort by modified time, newest first
    files.sort(key=lambda x: x['modified'], reverse=True)
    files = files[:limit]

    return jsonify({
        "success": True,
        "count": len(files),
        "files": files
    })


@app.route('/api/capture', methods=['POST'])
def capture():
    """Single-shot capture from any camera"""
    data = request.json or {}
    camera = data.get('camera', 'owleye')  # Accept short names: owleye, czur, webcam
    camera_name = data.get('camera_name', None)  # Full name: owleye, czur, webcam
    width = data.get('width', 4624)
    height = data.get('height', 3472)
    autofocus = data.get('autofocus', True)

    # Map short camera names to full names
    if not camera_name:
        if camera == 'owleye':
            camera_name = 'owleye'
        elif camera in CAMERAS:
            camera_name = camera

    # If camera_name specified, use that
    if camera_name and camera_name in CAMERAS:
        cam_config = CAMERAS[camera_name]
        if cam_config['type'] == 'usb':
            filename = capture_usb(cam_config['device'], *cam_config['resolution'], autofocus=autofocus, cam_name=camera_name)
        else:
            filename = capture_owleye(cam_config['index'], *cam_config['resolution'], autofocus=autofocus)
    else:
        filename = capture_owleye(0, width, height, autofocus=autofocus)

    if filename:
        result = {
            "success": True,
            "image_path": filename,
            "camera": camera_name or f"owleye{camera}",
            "resolution": f"{width}x{height}"
        }
        # Push to relay for Jaques
        push_to_relay(
            camera=result['camera'],
            scan_result=result,
            card_detected=True  # Assume card present on capture request
        )
        return jsonify(result)
    return jsonify({"success": False, "error": "Capture failed"}), 500


@app.route('/api/capture/full', methods=['POST'])
def capture_full():
    """
    Multi-pass capture sequence (Patent Claims 3, 10, 12)
    Returns: flat scan, surface scan, foil frames, best image
    """
    data = request.json or {}
    camera = data.get('camera', 0)

    results = capture_full_sequence(camera)
    return jsonify(results)


@app.route('/api/capture/usb', methods=['POST'])
def capture_usb_endpoint():
    """Capture from USB camera (CZUR or webcam)"""
    data = request.json or {}
    device = data.get('device', '/dev/video0')  # CZUR default
    width = data.get('width', 1920)
    height = data.get('height', 1080)

    filename = capture_usb(device, width, height)
    if filename:
        return jsonify({
            "success": True,
            "image_path": filename,
            "device": device,
            "resolution": f"{width}x{height}"
        })
    return jsonify({"success": False, "error": "Capture failed"}), 500


@app.route('/api/capture/czur', methods=['POST'])
def capture_czur_endpoint():
    """Capture from CZUR scanner - CZUR handles crop/exposure/focus
    Snarf verifies good read before passing to Brock for OCR"""
    data = request.json or {}
    width = data.get('width', 3264)
    height = data.get('height', 2448)

    czur_config = CAMERAS['czur']
    device = czur_config['device']

    # Turn on LED matrix at full brightness (default is 50/255 = too dim)
    send_to_esp(RING_PORT, "BRIGHT:255")
    time.sleep(0.05)
    set_all_leds(ch1=(255, 255, 255), ch2=(0, 0, 0))
    time.sleep(0.15)  # Let LEDs stabilize

    logger.info(f"CZUR capture: {device} at {width}x{height}")
    filename = capture_usb(device, width, height, cam_name='czur')

    # LEDs off after capture
    set_all_leds(ch1=(0, 50, 0), ch2=(0, 0, 0))  # Dim green = ready

    if not filename:
        return jsonify({
            "success": False,
            "error": f"CZUR capture failed (device: {device})"
        }), 500

    # Verify good read - check image isn't blank/dark/blurry
    try:
        img = cv2.imread(filename)
        if img is None:
            return jsonify({"success": False, "error": "Image file unreadable"}), 500

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(gray.mean())
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        file_size = os.path.getsize(filename)

        good_read = True
        issues = []

        # Too dark
        if mean_brightness < 30:
            good_read = False
            issues.append(f"too dark (brightness={mean_brightness:.0f})")
        # Too bright / blown out
        if mean_brightness > 240:
            good_read = False
            issues.append(f"blown out (brightness={mean_brightness:.0f})")
        # Too blurry
        if sharpness < 10:
            good_read = False
            issues.append(f"too blurry (sharpness={sharpness:.1f})")
        # Too small (probably failed capture)
        if file_size < 5000:
            good_read = False
            issues.append(f"file too small ({file_size} bytes)")

        logger.info(f"CZUR verify: {w}x{h}, brightness={mean_brightness:.0f}, "
                    f"sharpness={sharpness:.1f}, size={file_size}, good={good_read}")

        # Include inline base64 card image so Brock doesn't need separate download
        import base64 as b64mod
        card_b64 = None
        if good_read:
            try:
                # Crop to card region in lightbox
                if h >= 2448 and w >= 3264:
                    card_region = img[792:1875, 1008:2295]
                else:
                    card_region = img
                _, buffer = cv2.imencode('.jpg', card_region,
                                         [cv2.IMWRITE_JPEG_QUALITY, 90])
                card_b64 = b64mod.b64encode(buffer).decode('utf-8')
                logger.info(f"Inline b64: {len(card_b64)} chars")
            except Exception as be:
                logger.warning(f"Base64 encode failed: {be}")

        return jsonify({
            "success": True,
            "good_read": good_read,
            "issues": issues,
            "image_path": filename,
            "card_image_b64": card_b64,
            "device": device,
            "resolution": f"{w}x{h}",
            "quality": {
                "brightness": round(mean_brightness, 1),
                "sharpness": round(sharpness, 1),
                "file_size": file_size
            }
        })

    except Exception as e:
        logger.error(f"CZUR verify failed: {e}")
        return jsonify({
            "success": True,
            "good_read": False,
            "issues": [str(e)],
            "image_path": filename,
            "device": device,
            "resolution": f"{width}x{height}"
        })


# =============================================================================
# CZUR CAPTURE + OCR (Snarf does OCR, Brock does Coral AI recognition)
# =============================================================================

try:
    from snarf_ocr_enhanced import ocr_pipeline
    from snarf_ocr import multi_pass_ocr  # Keep for backward compat
    OCR_AVAILABLE = True
    logger.info("Enhanced OCR module loaded successfully")
except ImportError as e:
    OCR_AVAILABLE = False
    logger.warning(f"OCR module not available: {e}")


@app.route('/api/capture/czur/ocr', methods=['POST'])
def capture_czur_ocr():
    """Capture from CZUR + run OCR on Snarf.
    CZUR handles crop/exposure/focus.
    Snarf verifies good read + runs 5-region OCR.
    Returns OCR results for Brock to do Coral AI recognition."""
    if not OCR_AVAILABLE:
        return jsonify({"success": False, "error": "OCR module not available on Snarf"}), 500

    data = request.json or {}
    width = data.get('width', 3264)
    height = data.get('height', 2448)

    czur_config = CAMERAS['czur']
    device = czur_config['device']

    logger.info(f"CZUR capture+OCR: {device} at {width}x{height}")
    filename = capture_usb(device, width, height, cam_name='czur')

    if not filename:
        return jsonify({"success": False, "error": "CZUR capture failed"}), 500

    # Verify good read - check CARD AREA not full frame
    img = cv2.imread(filename)
    if img is None:
        return jsonify({"success": False, "error": "Image unreadable"}), 500

    h, w_img = img.shape[:2]
    # Crop to lightbox/card area for quality check (full frame is mostly dark)
    if h >= 2448 and w_img >= 3264:
        card_region = img[792:1875, 1008:2295]
    else:
        card_region = img
    gray = cv2.cvtColor(card_region, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(gray.mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    issues = []
    if mean_brightness < 30:
        issues.append(f"too dark ({mean_brightness:.0f})")
    if mean_brightness > 240:
        issues.append(f"blown out ({mean_brightness:.0f})")
    if sharpness < 10:
        issues.append(f"too blurry ({sharpness:.1f})")

    if issues:
        logger.warning(f"Image quality issues: {issues}")
        return jsonify({
            "success": True,
            "good_read": False,
            "issues": issues,
            "image_path": filename,
            "ocr_results": [],
            "set_code": None,
            "collector_num": None
        })

    # Run 5-region OCR
    logger.info("Running multi_pass_ocr...")
    ocr_results, set_code, collector_num, region_data = multi_pass_ocr(filename)

    logger.info(f"OCR complete: {len(ocr_results)} results, set={set_code}, collector={collector_num}")

    return jsonify({
        "success": True,
        "good_read": True,
        "image_path": filename,
        "resolution": f"{w_img}x{h}",
        "quality": {
            "brightness": round(mean_brightness, 1),
            "sharpness": round(sharpness, 1)
        },
        "ocr_results": ocr_results,
        "set_code": set_code,
        "collector_num": collector_num,
        "region_data": region_data
    })


# =============================================================================
# STANDALONE OCR (for parallel pipeline - image already captured)
# =============================================================================

@app.route('/api/ocr', methods=['POST'])
def ocr_endpoint():
    """Run Enhanced OCR (EasyOCR GPU + Tesseract) on an image.
    Used by pipeline: Coral art match + OCR simultaneously."""
    if not OCR_AVAILABLE:
        return jsonify({"success": False, "error": "OCR module not available"}), 500

    data = request.json or {}
    image_path = data.get('image_path')
    use_legacy = data.get('use_legacy', False)  # Option to use old OCR

    if not image_path or not os.path.exists(image_path):
        return jsonify({"success": False, "error": "Image not found"}), 400

    logger.info(f"OCR request: {image_path} (legacy={use_legacy})")
    
    if use_legacy:
        # Use old multi-pass OCR
        ocr_results, set_code, collector_num, region_data = multi_pass_ocr(image_path)
        return jsonify({
            "success": True,
            "method": "legacy",
            "ocr_results": ocr_results,
            "set_code": set_code,
            "collector_num": collector_num,
            "region_data": region_data
        })
    else:
        # Use new enhanced OCR pipeline
        result = ocr_pipeline(image_path)
        logger.info(f"Enhanced OCR: {result.get('method')} method, "
                    f"confidence={result.get('overall_confidence')}%")
        
        return jsonify({
            "success": True,
            **result
        })


# =============================================================================
# FOCUS CONTROL ENDPOINTS
# =============================================================================

@app.route('/api/focus', methods=['GET'])
def get_focus():
    """Get current focus position"""
    return jsonify({
        "success": True,
        "lens_position": current_lens_position,
        "description": "0=infinity, 2=50cm, 5=20cm, 6.5=15cm, 10=10cm"
    })


@app.route('/api/focus', methods=['POST'])
def set_focus():
    """Set manual focus position

    Lens position values (reciprocal distance in meters):
        0 = infinity
        2 = 50cm
        5 = 20cm
        6.5 = ~15cm (ideal for card scanning)
        10 = 10cm
        "default" = hyperfocal
    """
    global current_lens_position
    data = request.json or {}
    position = data.get('position', 6.5)

    if position == 'default':
        current_lens_position = 'default'
    else:
        try:
            current_lens_position = float(position)
        except:
            return jsonify({"success": False, "error": "Invalid position"}), 400

    return jsonify({
        "success": True,
        "lens_position": current_lens_position,
        "message": f"Focus set to {current_lens_position}"
    })


@app.route('/api/focus/test', methods=['POST'])
def focus_test():
    """Capture test image at specified focus position"""
    data = request.json or {}
    position = data.get('position', current_lens_position)

    filename = capture_owleye(0, 4624, 3472, suffix="_focus_test", lens_position=position)

    if filename:
        # Calculate sharpness for feedback
        sharpness = calculate_sharpness(filename)
        return jsonify({
            "success": True,
            "image_path": filename,
            "lens_position": position,
            "sharpness": sharpness
        })
    return jsonify({"success": False, "error": "Capture failed"}), 500


@app.route('/api/focus/calibrate', methods=['POST'])
def focus_calibrate():
    """Auto-calibrate focus by testing multiple positions and selecting sharpest"""
    global current_lens_position

    positions = [4.0, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    results = []

    logger.info("Starting focus calibration...")

    for pos in positions:
        filename = capture_owleye(0, 2312, 1736, suffix=f"_cal_{pos}", lens_position=pos)
        if filename:
            sharpness = calculate_sharpness(filename)
            results.append({"position": pos, "sharpness": sharpness, "image": filename})
            logger.info(f"  Position {pos}: sharpness = {sharpness:.2f}")
            # Clean up test image
            try:
                os.remove(filename)
            except:
                pass

    if results:
        # Find position with highest sharpness
        best = max(results, key=lambda x: x['sharpness'])
        current_lens_position = best['position']
        logger.info(f"Best focus: position {current_lens_position} (sharpness {best['sharpness']:.2f})")

        return jsonify({
            "success": True,
            "best_position": current_lens_position,
            "best_sharpness": best['sharpness'],
            "all_results": results
        })

    return jsonify({"success": False, "error": "Calibration failed"}), 500


# =============================================================================
# CARD BACK IDENTIFICATION (Auto-detect card type)
# =============================================================================

# Card type signatures for back identification
CARD_TYPE_SIGNATURES = {
    'mtg': {
        'name': 'Magic: The Gathering',
        'colors': {'brown': (10, 25), 'blue': (100, 130)},  # HSV hue ranges
        'database': 'scryfall'
    },
    'pokemon': {
        'name': 'Pokemon TCG',
        'colors': {'red': (0, 10), 'white': None},
        'database': 'pokemon_tcg'
    },
    'yugioh': {
        'name': 'Yu-Gi-Oh!',
        'colors': {'brown': (10, 25), 'dark': None},
        'database': 'yugioh'
    },
    'sports_topps': {
        'name': 'Topps Sports',
        'colors': {'red': (0, 10), 'blue': (100, 130), 'white': None},
        'database': 'sports',
        'brand': 'Topps'
    },
    'sports_panini': {
        'name': 'Panini Sports',
        'colors': {'silver': None, 'blue': (100, 130)},
        'database': 'sports',
        'brand': 'Panini'
    }
}


def identify_card_back(image_path):
    """Identify card type from back image using color analysis."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {'type': 'unknown', 'confidence': 0}

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = img.shape[:2]

        # Analyze dominant colors
        scores = {}

        for card_type, sig in CARD_TYPE_SIGNATURES.items():
            score = 0
            for color_name, hue_range in sig['colors'].items():
                if hue_range is None:
                    continue
                lower = np.array([hue_range[0], 50, 50])
                upper = np.array([hue_range[1], 255, 255])
                mask = cv2.inRange(hsv, lower, upper)
                ratio = np.sum(mask > 0) / mask.size
                if ratio > 0.05:
                    score += ratio
            scores[card_type] = score

        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0.1:
                sig = CARD_TYPE_SIGNATURES[best[0]]
                return {
                    'type': best[0],
                    'name': sig['name'],
                    'confidence': min(best[1] * 2, 0.95),
                    'database': sig['database'],
                    'brand': sig.get('brand')
                }

        return {'type': 'unknown', 'confidence': 0}
    except Exception as e:
        logger.error(f"Card back identification error: {e}")
        return {'type': 'unknown', 'confidence': 0, 'error': str(e)}


@app.route('/api/scan/back', methods=['POST'])
def scan_back():
    """
    Scan card back to identify card type before front scan.

    This enables automatic database routing:
    - MTG → Scryfall
    - Pokemon → Pokemon TCG API
    - Sports → Sports card database
    """
    data = request.json or {}
    camera = data.get('camera', 0)

    # Capture back image
    logger.info("Scanning card back for type identification...")
    set_all_leds(ch1=(255, 255, 255), ch2=(0, 0, 0))
    time.sleep(0.2)

    back_img = capture_owleye(camera, 2312, 1736, suffix="_back")

    leds_off()

    if not back_img:
        return jsonify({"success": False, "error": "Back capture failed"}), 500

    # Identify card type
    result = identify_card_back(back_img)

    return jsonify({
        "success": True,
        "image_path": back_img,
        "card_type": result
    })


@app.route('/api/scan/full_with_type', methods=['POST'])
def scan_full_with_type():
    """
    Complete scan workflow:
    1. Scan back → Identify card type
    2. Flip card (manual or arm)
    3. Scan front with multi-pass
    4. Route to appropriate database
    """
    data = request.json or {}
    camera = data.get('camera', 0)
    auto_flip = data.get('auto_flip', False)

    results = {
        'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
        'card_type': None,
        'back_image': None,
        'front_images': {},
        'best_front': None,
        'success': False
    }

    try:
        # === STEP 1: BACK SCAN ===
        logger.info("Step 1: Scanning card back...")
        led_feedback('scanning', duration=0.2)

        set_all_leds(ch1=(255, 255, 255), ch2=(0, 0, 0))
        time.sleep(0.2)

        back_img = capture_owleye(camera, 2312, 1736, suffix="_back")
        results['back_image'] = back_img

        if back_img:
            card_type = identify_card_back(back_img)
            results['card_type'] = card_type
            logger.info(f"Identified card type: {card_type.get('name', 'unknown')}")

        # === STEP 2: WAIT FOR FLIP (or auto-flip) ===
        if auto_flip:
            # Use arm to flip card (future feature)
            logger.info("Step 2: Auto-flip not implemented, waiting for manual flip")

        # Signal user to flip
        set_all_leds(ch1=(255, 255, 0), ch2=(255, 255, 0))  # Yellow = flip
        time.sleep(2)  # Wait for flip

        # === STEP 3: FRONT SCAN (Multi-pass) ===
        logger.info("Step 3: Scanning front (multi-pass)...")
        front_results = capture_full_sequence(camera)

        results['front_images'] = front_results.get('images', {})
        results['best_front'] = front_results.get('best')
        results['sharpness'] = front_results.get('sharpness', {})

        # === STEP 4: SUCCESS ===
        if results['best_front']:
            results['success'] = True
            led_feedback('success', duration=0.5, flash_count=2)

            # Include database routing info
            if results['card_type']:
                results['database'] = results['card_type'].get('database', 'unknown')
        else:
            led_feedback('fail', duration=0.5, flash_count=3)

    except Exception as e:
        logger.error(f"Full scan error: {e}")
        led_feedback('fail', duration=0.5, flash_count=3)
        results['error'] = str(e)

    return jsonify(results)


@app.route('/api/card_types', methods=['GET'])
def get_card_types():
    """List supported card types and their signatures."""
    types = {}
    for key, sig in CARD_TYPE_SIGNATURES.items():
        types[key] = {
            'name': sig['name'],
            'database': sig['database'],
            'brand': sig.get('brand')
        }
    return jsonify({"card_types": types})


@app.route('/api/led', methods=['POST'])
def led_control():
    """Control individual LED channel (1 or 2)"""
    data = request.json or {}
    ch = data.get('ch', 1)
    r = data.get('r', 255)
    g = data.get('g', 255)
    b = data.get('b', 255)

    result = set_led_ch(ch, r, g, b)
    if result:
        return jsonify({"success": True, "ch": ch, "color": [r, g, b]})
    return jsonify({"success": False}), 500


@app.route('/api/leds', methods=['POST'])
def leds_control():
    """Control both LED channels at once"""
    data = request.json or {}
    ch1 = tuple(data.get('ch1', [0, 0, 0]))
    ch2 = tuple(data.get('ch2', [0, 0, 0]))

    set_all_leds(ch1, ch2)
    return jsonify({
        "success": True,
        "leds": {"ch1": ch1, "ch2": ch2}
    })


@app.route('/api/rainbow', methods=['POST'])
def rainbow():
    """Execute rainbow sweep for foil detection"""
    data = request.json or {}
    duration = data.get('duration', 1.0)

    rainbow_sweep(duration)
    leds_off()
    return jsonify({"success": True, "duration": duration})


@app.route('/api/lights', methods=['POST'])
def lights():
    data = request.json or {}
    state = data.get('state')
    ch = data.get('ch')
    brightness = data.get('brightness')
    color = data.get('color', {})
    # Check for direct RGB values OR nested color object
    r = color.get('r', data.get('r'))
    g = color.get('g', data.get('g'))
    b = color.get('b', data.get('b'))
    has_rgb = r is not None or g is not None or b is not None
    # Default to white if RGB requested but values missing
    if has_rgb:
        r = r if r is not None else 255
        g = g if g is not None else 255
        b = b if b is not None else 255

    if state == 'off':
        # ESP32 lightbox off, Arduino Micro both channels off
        send_to_esp(LED_PORT, "light off")
        result = send_to_esp(RING_PORT, "OFF")
        cmd = "off"
    elif brightness is not None:
        # Arduino Micro global brightness
        cmd = f"BRIGHT:{brightness}"
        result = send_to_esp(RING_PORT, cmd)
    elif ch is not None:
        # Specific channel -> Arduino Micro (1 or 2)
        cmd = f"CH{ch}:{r or 255}:{g or 255}:{b or 255}"
        result = send_to_esp(RING_PORT, cmd)
    elif state == 'on' or has_rgb:
        # ESP32 lightbox + both Micro channels
        send_to_esp(LED_PORT, f"light #{r:02x}{g:02x}{b:02x}")
        send_to_esp(RING_PORT, f"CH1:{r}:{g}:{b}")
        result = send_to_esp(RING_PORT, f"CH2:{r}:{g}:{b}")
        cmd = f"RGB:{r}:{g}:{b}"
    else:
        # Turn on all white
        send_to_esp(LED_PORT, "light white")
        send_to_esp(RING_PORT, "CH1:255:255:255")
        result = send_to_esp(RING_PORT, "CH2:255:255:255")
        cmd = "ON"

    if result:
        return jsonify({"success": True, "command": cmd, "response": result})
    return jsonify({"success": False, "error": "Serial failed"}), 500


@app.route('/api/lights/test', methods=['POST'])
def lights_test():
    # ESP32 expects: test
    result = send_to_esp(LED_PORT, "test")
    return jsonify({
        "success": bool(result),
        "response": result
    })


# =============================================================================
# INDIVIDUAL LIGHT CHANNEL ENDPOINTS
# =============================================================================

@app.route('/api/lights/lightbox', methods=['POST'])
def lights_lightbox():
    """Set lightbox color (ESP32 WS2812B strip, GPIO 27)"""
    data = request.json or {}
    r, g, b = data.get('r', 255), data.get('g', 255), data.get('b', 255)
    # ESP32 expects: light <color> or light #RRGGBB (nexus_arm_controller.ino)
    cmd = f"light #{r:02x}{g:02x}{b:02x}"
    result = send_to_esp(LED_PORT, cmd)
    return jsonify({"success": bool(result)})


@app.route('/api/lights/lightbox/off', methods=['POST'])
def lights_lightbox_off():
    """Turn off lightbox (ESP32 GPIO 27)"""
    result = send_to_esp(LED_PORT, "light off")
    return jsonify({"success": bool(result)})


@app.route('/api/lights/logo', methods=['POST'])
def lights_logo():
    """Logo ring removed - hardware has no logo LEDs (Feb 2026)"""
    return jsonify({"success": False, "error": "Logo LEDs not installed"})


@app.route('/api/lights/logo/off', methods=['POST'])
def lights_logo_off():
    """Logo ring removed - hardware has no logo LEDs (Feb 2026)"""
    return jsonify({"success": False, "error": "Logo LEDs not installed"})


@app.route('/api/lights/ch/<int:num>', methods=['POST'])
def lights_ch(num):
    """Set LED channel color (Arduino Micro CH1=60 LEDs, CH2=48 LEDs)"""
    if num < 1 or num > 2:
        return jsonify({"success": False, "error": "Channel must be 1-2"}), 400
    data = request.json or {}
    r, g, b = data.get('r', 255), data.get('g', 255), data.get('b', 255)
    cmd = f"CH{num}:{r}:{g}:{b}"
    result = send_to_esp(RING_PORT, cmd)
    return jsonify({"success": bool(result)})


@app.route('/api/lights/ch/<int:num>/off', methods=['POST'])
def lights_ch_off(num):
    """Turn off LED channel"""
    if num < 1 or num > 2:
        return jsonify({"success": False, "error": "Channel must be 1-2"}), 400
    cmd = f"CH{num}:0:0:0"
    result = send_to_esp(RING_PORT, cmd)
    return jsonify({"success": bool(result)})


@app.route('/api/arm/jog', methods=['POST'])
def arm_jog():
    """Jog a servo by degrees. UI sends: shoulder, wyaw, wpitch, elbow."""
    global arm_angles
    data = request.json or {}
    cmd = data.get('cmd', 'shoulder')
    degrees = data.get('degrees', 0)

    # Map UI cmd -> (arm_angles index, ESP32 serial command)
    cmd_map = {
        'shoulder': (0, 'shoulder'),
        'wyaw':     (1, 'wrist_yaw'),
        'wpitch':   (2, 'wrist_pitch'),
        'elbow':    (3, 'elbow'),
    }

    if cmd in cmd_map:
        idx, esp_cmd = cmd_map[cmd]
        arm_angles[idx] = max(0, min(180, arm_angles[idx] + degrees))
        esp_full_cmd = f"{esp_cmd} {arm_angles[idx]}"
        result = send_to_esp(ARM_PORT, esp_full_cmd)
        if result:
            return jsonify({
                "success": True,
                "angles": {
                    "shoulder": arm_angles[0], "wyaw": arm_angles[1],
                    "wpitch": arm_angles[2], "elbow": arm_angles[3]
                }
            })
    return jsonify({"success": False}), 400


@app.route('/api/arm/position', methods=['GET'])
def arm_position():
    return jsonify({"success": True, "angles": arm_angles})


@app.route('/api/arm/set', methods=['POST'])
def arm_set():
    """Set a single joint to absolute angle (from slider). UI sends: shoulder, wyaw, wpitch, elbow."""
    global arm_angles
    data = request.json or {}
    cmd = data.get('cmd', 'shoulder')
    angle = data.get('angle', 90)
    angle = max(0, min(180, angle))

    # Map UI cmd -> (arm_angles index, ESP32 serial command)
    cmd_map = {
        'shoulder': (0, 'shoulder'),
        'wyaw':     (1, 'wrist_yaw'),
        'wpitch':   (2, 'wrist_pitch'),
        'elbow':    (3, 'elbow'),
    }

    if cmd in cmd_map:
        idx, esp_cmd = cmd_map[cmd]
        arm_angles[idx] = angle
        result = send_to_esp(ARM_PORT, f"{esp_cmd} {angle}")
        return jsonify({"success": bool(result), "cmd": cmd, "angle": angle})
    return jsonify({"success": False, "error": "Invalid cmd"}), 400


@app.route('/api/arm/preset', methods=['POST'])
def arm_preset():
    """Move arm to preset position. All 4 servos + base stepper from JSON presets."""
    global arm_angles, base_angle
    data = request.json or {}
    position = data.get('position', 'home')

    if position not in arm_presets:
        return jsonify({"success": False, "error": f"Unknown preset: {position}"}), 400

    p = arm_presets[position]
    # Send all 4 servo commands
    arm_angles[0] = p.get('shoulder', 90)
    arm_angles[1] = p.get('wrist_yaw', 90)
    arm_angles[2] = p.get('wrist_pitch', 90)
    arm_angles[3] = p.get('elbow', 90)
    send_to_esp(ARM_PORT, f"shoulder {arm_angles[0]}")
    send_to_esp(ARM_PORT, f"wrist_yaw {arm_angles[1]}")
    send_to_esp(ARM_PORT, f"wrist_pitch {arm_angles[2]}")
    send_to_esp(ARM_PORT, f"elbow {arm_angles[3]}")
    # Move base stepper if preset has a base angle
    if 'base' in p:
        base_angle = p['base']
        send_to_esp(ARM_PORT, f"b_angle {base_angle}")
    return jsonify({
        "success": True,
        "position": position,
        "angles": {
            "shoulder": arm_angles[0], "wyaw": arm_angles[1],
            "wpitch": arm_angles[2], "elbow": arm_angles[3],
            "base": base_angle
        }
    })


@app.route('/api/arm/preset/save', methods=['POST'])
def arm_preset_save():
    """Save current arm position as a named preset."""
    data = request.json or {}
    name = data.get('name', '').strip().lower()
    if not name:
        return jsonify({"success": False, "error": "No preset name"}), 400

    arm_presets[name] = {
        "shoulder": arm_angles[0],
        "wrist_yaw": arm_angles[1],
        "wrist_pitch": arm_angles[2],
        "elbow": arm_angles[3],
        "base": base_angle
    }
    saved = save_arm_presets(arm_presets)
    return jsonify({"success": saved, "preset": name, "angles": arm_presets[name]})


@app.route('/api/arm/presets', methods=['GET'])
def arm_presets_list():
    """List all saved arm presets."""
    return jsonify({"success": True, "presets": arm_presets})


# =============================================================================
# STEPPER BASE CONTROL (TB6600 - DIR 18/19, PUL 33/25)
# =============================================================================

@app.route('/api/stepper/angle', methods=['POST'])
def stepper_angle():
    """Move base stepper to specific angle. Shoulder is servo on PCA ch1."""
    global base_angle
    data = request.json or {}
    angle = data.get('angle', 90)
    angle = max(0, min(180, int(angle)))
    base_angle = angle
    cmd = f"b_angle {angle}"
    result = send_to_esp(ARM_PORT, cmd)
    return jsonify({"success": "OK" in str(result), "angle": angle, "response": result})


@app.route('/api/stepper/cw', methods=['POST'])
def stepper_cw():
    """Move base stepper clockwise by steps"""
    data = request.json or {}
    steps = data.get('steps', data.get('degrees', 100))
    cmd = f"base {steps}"
    result = send_to_esp(ARM_PORT, cmd)
    success = result and ("Done" in str(result) or "OK" in str(result))
    return jsonify({"success": success, "steps": steps, "response": result})


@app.route('/api/stepper/ccw', methods=['POST'])
def stepper_ccw():
    """Move base stepper counter-clockwise by steps"""
    data = request.json or {}
    steps = data.get('steps', data.get('degrees', 100))
    cmd = f"base -{steps}"
    result = send_to_esp(ARM_PORT, cmd)
    success = result and ("Done" in str(result) or "OK" in str(result))
    return jsonify({"success": success, "steps": steps, "response": result})


@app.route('/api/stepper/zero', methods=['POST'])
def stepper_zero():
    """Reset base stepper position tracking to 0."""
    global arm_angles
    arm_angles[0] = 0
    cmd = "b_angle 0"
    result = send_to_esp(ARM_PORT, cmd)
    success = result and ("Done" in str(result) or "OK" in str(result))
    return jsonify({"success": success, "response": result})


@app.route('/api/stepper/speed', methods=['POST'])
def stepper_speed():
    """Set step delay (NOT IMPLEMENTED - hardcoded in ESP32 firmware as 800us)"""
    # ESP32 firmware has stepDelay = 800 microseconds hardcoded
    # No runtime command to change this - would need firmware update
    return jsonify({"success": False, "error": "Speed control not implemented in ESP32 firmware", "current_delay_us": 800})


@app.route('/api/stepper/microstep', methods=['POST'])
def stepper_microstep():
    """Set microstepping (NOT IMPLEMENTED - hardcoded in ESP32 firmware as 16)"""
    # ESP32 firmware has MICROSTEP = 16 hardcoded
    # No runtime command to change this - would need firmware update
    return jsonify({"success": False, "error": "Microstep control not implemented in ESP32 firmware", "current_microstep": 16})


@app.route('/api/stepper/home', methods=['POST'])
def stepper_home():
    """Home all arm components"""
    result = send_to_esp(ARM_PORT, "home")
    return jsonify({"success": bool(result), "response": result})


@app.route('/api/stepper/left', methods=['POST'])
def stepper_left():
    """Move base stepper to left position (0 degrees)"""
    result = send_to_esp(ARM_PORT, "b_angle 0")
    return jsonify({"success": bool(result), "angle": 0, "response": result})


@app.route('/api/stepper/right', methods=['POST'])
def stepper_right():
    """Move base stepper to right position (180 degrees)"""
    result = send_to_esp(ARM_PORT, "b_angle 180")
    return jsonify({"success": bool(result), "angle": 180, "response": result})


@app.route('/api/stepper/status', methods=['GET'])
def stepper_status():
    """Get arm status"""
    result = send_to_esp(ARM_PORT, "status")
    return jsonify({"success": True, "response": result})


# =============================================================================
# VACUUM CONTROL ENDPOINTS (PCA9685 ch9=solenoid, ch10=pump)
# =============================================================================

@app.route('/api/vacuum/on', methods=['POST'])
def vacuum_on():
    """Turn on vacuum pump (PCA ch6)"""
    result = send_to_esp(ARM_PORT, "vacuum on")
    return jsonify({"success": "OK" in str(result), "vacuum": "on", "response": result})


@app.route('/api/vacuum/off', methods=['POST'])
def vacuum_off():
    """Turn off vacuum pump (PCA ch6)"""
    result = send_to_esp(ARM_PORT, "vacuum off")
    return jsonify({"success": "OK" in str(result), "vacuum": "off", "response": result})


@app.route('/api/vacuum/pick', methods=['POST'])
def vacuum_pick():
    """Vacuum pick mode - pump on (suction)"""
    result = send_to_esp(ARM_PORT, "vacuum on")
    return jsonify({"success": "OK" in str(result), "vacuum": "pick", "response": result})


@app.route('/api/vacuum/drop', methods=['POST'])
def vacuum_drop():
    """Vacuum drop mode - vacuum off, solenoid pulse"""
    send_to_esp(ARM_PORT, "vacuum off")
    send_to_esp(ARM_PORT, "solenoid on")
    time.sleep(0.1)
    result = send_to_esp(ARM_PORT, "solenoid off")
    return jsonify({"success": "OK" in str(result), "vacuum": "drop", "response": result})


@app.route('/api/vacuum/grab', methods=['POST'])
def vacuum_grab():
    """Vacuum grab mode - alias for pick"""
    result = send_to_esp(ARM_PORT, "vacuum on")
    return jsonify({"success": "OK" in str(result), "vacuum": "grab", "response": result})


@app.route('/api/vacuum/release', methods=['POST'])
def vacuum_release():
    """Vacuum release mode - alias for drop"""
    send_to_esp(ARM_PORT, "vacuum off")
    send_to_esp(ARM_PORT, "solenoid on")
    time.sleep(0.1)
    result = send_to_esp(ARM_PORT, "solenoid off")
    return jsonify({"success": "OK" in str(result), "vacuum": "release", "response": result})


@app.route('/api/solenoid/on', methods=['POST'])
def solenoid_on():
    """Turn solenoid on (PCA ch5)"""
    result = send_to_esp(ARM_PORT, "solenoid on")
    return jsonify({"success": "OK" in str(result), "solenoid": "on", "response": result})


@app.route('/api/solenoid/off', methods=['POST'])
def solenoid_off():
    """Turn solenoid off (PCA ch5)"""
    result = send_to_esp(ARM_PORT, "solenoid off")
    return jsonify({"success": "OK" in str(result), "solenoid": "off", "response": result})


@app.route('/api/stepper/jog', methods=['POST'])
def stepper_jog():
    """Jog base stepper by steps. Shoulder is now a servo (use /api/arm/jog)."""
    data = request.json or {}
    steps = data.get('steps', 0)

    # ESP32 command: base <steps> (positive=CW, negative=CCW)
    cmd = f"base {steps}"
    result = send_to_esp(ARM_PORT, cmd)
    success = result and ("Done" in str(result) or "OK" in str(result))
    return jsonify({"success": success, "steps": steps, "response": result})


# stepper_home moved to line ~1647 to avoid duplicate route


@app.route('/api/vacuum/pulse', methods=['POST'])
def vacuum_pulse():
    """Pulse vacuum for specified duration (ms)"""
    data = request.json or {}
    duration = data.get('duration', 500)
    duration = max(1, min(5000, duration))

    send_to_esp(ARM_PORT, "vacuum on")
    time.sleep(duration / 1000.0)
    send_to_esp(ARM_PORT, "vacuum off")
    return jsonify({"success": True, "duration": duration})


# =============================================================================
# COMBINED CONTROL ENDPOINTS (for NEXUS V2 UI)
# =============================================================================

@app.route('/api/vacuum', methods=['POST'])
def vacuum_control():
    """Combined vacuum control endpoint (ESP32 VAC/SOL commands)"""
    data = request.json or {}
    state = data.get('state')
    pulse = data.get('pulse')
    action = data.get('action')  # pick, drop

    if action == 'pick':
        result = send_to_esp(ARM_PORT, "vacuum on")
        return jsonify({"success": "OK" in str(result), "action": "pick"})
    elif action == 'drop':
        send_to_esp(ARM_PORT, "vacuum off")
        send_to_esp(ARM_PORT, "solenoid on")
        time.sleep(0.1)
        result = send_to_esp(ARM_PORT, "solenoid off")
        return jsonify({"success": "OK" in str(result), "action": "drop"})
    elif pulse:
        duration = max(1, min(5000, int(pulse)))
        send_to_esp(ARM_PORT, "vacuum on")
        time.sleep(duration / 1000.0)
        send_to_esp(ARM_PORT, "vacuum off")
        return jsonify({"success": True, "action": "pulse", "duration": duration})
    elif state == 'on':
        result = send_to_esp(ARM_PORT, "vacuum on")
        return jsonify({"success": "OK" in str(result), "vacuum": "on"})
    elif state == 'off':
        result = send_to_esp(ARM_PORT, "vacuum off")
        return jsonify({"success": "OK" in str(result), "vacuum": "off"})
    else:
        return jsonify({"success": False, "error": "Specify state, pulse, or action"}), 400


@app.route('/api/lightbox', methods=['POST'])
def lightbox_control():
    """Combined lightbox control (ESP32 light command - nexus_arm_controller.ino)"""
    data = request.json or {}
    state = data.get('state')
    r = data.get('r', 255)
    g = data.get('g', 255)
    b = data.get('b', 255)

    # ESP32 format: light <color> or light #RRGGBB
    if state == 'off':
        cmd = "light off"
    else:
        cmd = f"light #{r:02x}{g:02x}{b:02x}"

    result = send_to_esp(LED_PORT, cmd)
    return jsonify({"success": bool(result), "command": cmd})


@app.route('/api/logo', methods=['POST'])
def logo_control():
    """Logo ring removed - hardware has no logo LEDs (Feb 2026)"""
    return jsonify({"success": False, "error": "Logo LEDs not installed"})


@app.route('/api/lights/mode', methods=['POST'])
def lights_mode():
    """Set LED scan mode (FLAT, SURFACE, FOIL, etc.)"""
    data = request.json or {}
    mode = data.get('mode', 'flat').upper()

    # Send mode command to ESP32
    cmd = f"MODE:{mode}"
    result = send_to_esp(LED_PORT, cmd)

    if result:
        return jsonify({"success": True, "mode": mode})
    return jsonify({"success": False, "error": "Serial failed"}), 500


@app.route('/api/fan', methods=['POST'])
def fan_control():
    """Control cooling fan speed (0-255)"""
    data = request.json or {}
    speed = data.get('speed')
    state = data.get('state')

    if state == 'on':
        speed = 255
    elif state == 'off':
        speed = 0
    elif speed is None:
        return jsonify({"success": False, "error": "Specify speed or state"}), 400

    speed = max(0, min(255, int(speed)))
    cmd = f"FAN:{speed}"
    result = send_to_esp(LED_PORT, cmd)

    if result:
        return jsonify({"success": True, "speed": speed})
    return jsonify({"success": False, "error": "Serial failed"}), 500


# =============================================================================
# LIFT ARM CONTROL (2-DOF: Shoulder ch6 + Tilt ch7)
# =============================================================================

@app.route('/api/lift/up', methods=['POST'])
def lift_up():
    """Raise shoulder servo (PCA ch1)"""
    result = send_to_esp(ARM_PORT, "shoulder 45")
    if result:
        return jsonify({"success": True, "lift": "up"})
    return jsonify({"success": False}), 500


@app.route('/api/lift/down', methods=['POST'])
def lift_down():
    """Lower shoulder servo (PCA ch1)"""
    result = send_to_esp(ARM_PORT, "shoulder 135")
    if result:
        return jsonify({"success": True, "lift": "down"})
    return jsonify({"success": False}), 500


@app.route('/api/lift/shoulder', methods=['POST'])
def lift_shoulder():
    """Set shoulder servo angle (PCA ch1)"""
    data = request.json or {}
    angle = max(0, min(180, data.get('angle', 90)))
    result = send_to_esp(ARM_PORT, f"shoulder {angle}")
    if result:
        return jsonify({"success": True, "shoulder": angle})
    return jsonify({"success": False}), 500


@app.route('/api/lift/tilt', methods=['POST'])
def lift_tilt():
    """Set elbow servo angle (PCA ch2)"""
    data = request.json or {}
    angle = max(0, min(180, data.get('angle', 90)))
    result = send_to_esp(ARM_PORT, f"elbow {angle}")
    if result:
        return jsonify({"success": True, "tilt": angle})
    return jsonify({"success": False}), 500


# =============================================================================
# ARM SEQUENCES
# =============================================================================

@app.route('/api/arm/pickup', methods=['POST'])
def arm_pickup_card():
    """Full pickup sequence: move to pickup, vacuum on"""
    # Move to pickup position (commands match robo_arm_clean.ino)
    send_to_esp(ARM_PORT, "b_angle 90")    # Base stepper
    send_to_esp(ARM_PORT, "shoulder 45")   # Shoulder servo (ch1)
    send_to_esp(ARM_PORT, "elbow 135")     # Elbow servo (ch3)
    send_to_esp(ARM_PORT, "wrist_yaw 90")  # Wrist yaw servo (ch1)
    time.sleep(0.5)

    # Turn on vacuum
    result = send_to_esp(ARM_PORT, "vacuum on")

    return jsonify({
        "success": bool(result),
        "action": "pickup",
        "vacuum": "on"
    })


@app.route('/api/arm/drop', methods=['POST'])
def arm_drop_card():
    """
    Full drop sequence: move to drop position, vacuum off
    """
    data = request.json or {}
    box = data.get('box', 0)  # Which box to drop into (future: multiple boxes)

    # Move to drop position (over the stack) - commands match robo_arm_clean.ino
    send_to_esp(ARM_PORT, "b_angle 135")    # Base stepper
    send_to_esp(ARM_PORT, "shoulder 90")    # Shoulder servo (ch1)
    send_to_esp(ARM_PORT, "elbow 90")       # Elbow servo (ch3)
    time.sleep(0.5)

    # Release card - vacuum off, solenoid pulse
    send_to_esp(ARM_PORT, "vacuum off")
    result = send_to_esp(ARM_PORT, "solenoid on")
    time.sleep(0.1)
    send_to_esp(ARM_PORT, "solenoid off")

    return jsonify({
        "success": bool(result),
        "action": "drop",
        "box": box,
        "vacuum": "off"
    })


# =============================================================================
# AUTOSCAN API ENDPOINTS
# =============================================================================

@app.route('/api/autoscan/start', methods=['POST'])
def autoscan_start():
    """Start hands-free motion-triggered scanning"""
    global autoscan_running, autoscan_thread, card_present, last_motion_frame

    if autoscan_running:
        return jsonify({"success": False, "error": "Autoscan already running"})

    # Reset state
    card_present = False
    last_motion_frame = None
    autoscan_running = True

    # Start background thread
    autoscan_thread = Thread(target=motion_monitor_loop, daemon=True)
    autoscan_thread.start()

    return jsonify({
        "success": True,
        "message": "Autoscan started - place card to scan",
        "led_feedback": "Green = ready, Yellow = motion, Blue = scanning, Green flash = success"
    })


@app.route('/api/autoscan/stop', methods=['POST'])
def autoscan_stop():
    """Stop motion-triggered scanning"""
    global autoscan_running

    if not autoscan_running:
        return jsonify({"success": False, "error": "Autoscan not running"})

    autoscan_running = False
    leds_off()

    return jsonify({"success": True, "message": "Autoscan stopped"})


@app.route('/api/autoscan/status', methods=['GET'])
def autoscan_status():
    """Get autoscan status and last result"""
    return jsonify({
        "running": autoscan_running,
        "card_present": card_present,
        "last_result": last_scan_result
    })


@app.route('/api/capture/full/feedback', methods=['POST'])
def capture_full_feedback():
    """
    Multi-pass capture with LED feedback (enhanced version)
    Returns: flat scan, surface scan, foil frames, best image
    """
    data = request.json or {}
    camera = data.get('camera', 0)

    results = capture_full_sequence_with_feedback(camera)
    return jsonify(results)


@app.route('/api/led/pattern', methods=['POST'])
def led_pattern():
    """Display a named LED pattern"""
    data = request.json or {}
    pattern = data.get('pattern', 'ready')
    duration = data.get('duration', 0.5)
    flash_count = data.get('flash_count', 1)

    if pattern not in LED_PATTERNS:
        return jsonify({
            "success": False,
            "error": f"Unknown pattern. Available: {list(LED_PATTERNS.keys())}"
        }), 400

    led_feedback(pattern, duration, flash_count)
    return jsonify({"success": True, "pattern": pattern})


# ============================================================
# DEBUG / FIRMWARE ENDPOINTS
# ============================================================

@app.route('/api/debug/exec', methods=['POST'])
def debug_exec():
    """
    Execute a shell command (for debugging/deployment).

    WARNING: This endpoint allows arbitrary command execution.
    Only enabled when SNARF_DEBUG=true environment variable is set.
    DISABLE IN PRODUCTION by setting SNARF_DEBUG=false.
    """
    if not DEBUG_MODE:
        return jsonify({
            "success": False,
            "error": "Debug endpoints disabled. Set SNARF_DEBUG=true to enable."
        }), 403

    data = request.get_json() or {}
    cmd = data.get('cmd', 'echo hello')
    logger.warning(f"DEBUG EXEC: {cmd[:100]}...")

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, timeout=30
        )
        return jsonify({
            "success": True,
            "stdout": result.stdout.decode(),
            "stderr": result.stderr.decode(),
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Command timed out"}), 408
    except Exception as e:
        logger.error(f"Debug exec error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/debug/serial', methods=['POST'])
def debug_serial():
    """
    Send raw command to any serial port.
    Only enabled in DEBUG_MODE.
    """
    if not DEBUG_MODE:
        return jsonify({
            "success": False,
            "error": "Debug endpoints disabled."
        }), 403

    data = request.get_json() or {}
    port = data.get('port', ARM_PORT)
    cmd = data.get('cmd', 'STATUS')

    # Validate port is one of our known ports
    allowed_ports = [LED_PORT, ARM_PORT, RING_PORT]
    if port not in allowed_ports:
        return jsonify({
            "success": False,
            "error": f"Invalid port. Allowed: {allowed_ports}"
        }), 400

    result = send_to_esp(port, cmd)
    return jsonify({
        "success": bool(result),
        "response": result,
        "port": port,
        "cmd": cmd
    })


@app.route('/api/esp32/upload', methods=['POST'])
def esp32_upload():
    """Upload firmware to ESP32 via arduino-cli"""
    data = request.get_json() or {}
    sketch = data.get('sketch', '/home/pi/arm_controller/arm_controller.ino')
    port = data.get('port', '/dev/ttyUSB1')
    board = data.get('board', 'esp32:esp32:esp32')

    try:
        # Check if arduino-cli exists
        check = subprocess.run(['which', 'arduino-cli'], capture_output=True)
        if check.returncode != 0:
            return jsonify({"success": False, "error": "arduino-cli not installed"}), 500

        # Compile
        compile_cmd = ['arduino-cli', 'compile', '--fqbn', board, sketch]
        compile_result = subprocess.run(compile_cmd, capture_output=True, timeout=120)

        if compile_result.returncode != 0:
            return jsonify({
                "success": False,
                "stage": "compile",
                "error": compile_result.stderr.decode()
            }), 500

        # Upload
        upload_cmd = ['arduino-cli', 'upload', '-p', port, '--fqbn', board, sketch]
        upload_result = subprocess.run(upload_cmd, capture_output=True, timeout=60)

        if upload_result.returncode != 0:
            return jsonify({
                "success": False,
                "stage": "upload",
                "error": upload_result.stderr.decode()
            }), 500

        return jsonify({
            "success": True,
            "message": f"Uploaded {sketch} to {port}",
            "compile_output": compile_result.stdout.decode(),
            "upload_output": upload_result.stdout.decode()
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/esp32/flash_url', methods=['POST'])
def esp32_flash_url():
    """Fetch firmware from URL and flash to ESP32"""
    import urllib.request
    data = request.get_json() or {}
    url = data.get('url')
    port = data.get('port', '/dev/ttyUSB0')
    board = data.get('board', 'esp32:esp32:esp32')

    if not url:
        return jsonify({"success": False, "error": "url required"}), 400

    try:
        # Download firmware
        sketch_dir = '/tmp/esp32_flash'
        os.makedirs(sketch_dir, exist_ok=True)
        sketch_path = os.path.join(sketch_dir, 'firmware.ino')

        logger.info(f"Downloading firmware from {url}")
        urllib.request.urlretrieve(url, sketch_path)

        # Verify download
        if not os.path.exists(sketch_path):
            return jsonify({"success": False, "error": "Download failed"}), 500

        file_size = os.path.getsize(sketch_path)
        logger.info(f"Downloaded {file_size} bytes to {sketch_path}")

        # Compile
        logger.info("Compiling...")
        compile_cmd = ['arduino-cli', 'compile', '--fqbn', board, sketch_dir]
        compile_result = subprocess.run(compile_cmd, capture_output=True, timeout=120)

        if compile_result.returncode != 0:
            return jsonify({
                "success": False,
                "stage": "compile",
                "error": compile_result.stderr.decode()
            }), 500

        # Upload
        logger.info(f"Uploading to {port}...")
        upload_cmd = ['arduino-cli', 'upload', '-p', port, '--fqbn', board, sketch_dir]
        upload_result = subprocess.run(upload_cmd, capture_output=True, timeout=60)

        if upload_result.returncode != 0:
            return jsonify({
                "success": False,
                "stage": "upload",
                "error": upload_result.stderr.decode()
            }), 500

        return jsonify({
            "success": True,
            "message": f"Flashed firmware from {url} to {port}",
            "file_size": file_size,
            "compile_output": compile_result.stdout.decode(),
            "upload_output": upload_result.stdout.decode()
        })

    except Exception as e:
        logger.error(f"Flash URL failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/esp32/ports', methods=['GET'])
def esp32_ports():
    """List available serial ports"""
    try:
        result = subprocess.run(['ls', '-la', '/dev/ttyUSB*'], capture_output=True, shell=False)
        ports = result.stdout.decode().strip().split('\n') if result.returncode == 0 else []

        return jsonify({
            "success": True,
            "ports": ports,
            "led_port": LED_PORT,
            "arm_port": ARM_PORT
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# SERVO CALIBRATION ENDPOINTS
# =============================================================================

@app.route('/api/arm/servo/setting', methods=['POST'])
def servo_setting():
    """Set individual servo calibration setting"""
    global servo_settings
    data = request.json or {}
    joint = data.get('index', data.get('joint', 0))
    if isinstance(joint, str):
        name_map = {'shoulder': 0, 'wyaw': 1, 'wpitch': 2, 'elbow': 3}
        joint = name_map.get(joint, 0)
    setting_type = data.get('type', 'trim')
    value = data.get('value', 0)

    if joint < 0 or joint >= 8:
        return jsonify({"success": False, "error": "Joint must be 0-7"}), 400

    if setting_type not in servo_settings:
        return jsonify({"success": False, "error": f"Unknown setting type: {setting_type}"}), 400

    servo_settings[setting_type][joint] = value

    # Send to ESP32
    cmd = f"SERVO:{joint}:{setting_type.upper()}:{value}"
    result = send_to_esp(ARM_PORT, cmd)

    return jsonify({
        "success": bool(result),
        "joint": joint,
        "type": setting_type,
        "value": value
    })


@app.route('/api/arm/servo/settings', methods=['GET'])
def get_servo_settings():
    """Get all servo calibration settings"""
    return jsonify({
        "success": True,
        "settings": servo_settings
    })


@app.route('/api/arm/servo/save', methods=['POST'])
def save_servo_settings():
    """Save all servo settings to ESP32 EEPROM"""
    global servo_settings
    data = request.json or {}

    # Update local settings if provided
    if 'trim' in data:
        servo_settings['trim'] = data['trim'][:8]
    if 'min' in data:
        servo_settings['min'] = data['min'][:8]
    if 'max' in data:
        servo_settings['max'] = data['max'][:8]
    if 'expo' in data:
        servo_settings['expo'] = data['expo'][:8]

    # Send save command to ESP32
    # Format: SERVO:SAVE:trim0,trim1,...:min0,min1,...:max0,max1,...:expo0,expo1,...
    trim_str = ','.join(map(str, servo_settings['trim']))
    min_str = ','.join(map(str, servo_settings['min']))
    max_str = ','.join(map(str, servo_settings['max']))
    expo_str = ','.join(map(str, servo_settings['expo']))
    cmd = f"SERVO:SAVE:{trim_str}:{min_str}:{max_str}:{expo_str}"
    result = send_to_esp(ARM_PORT, cmd)

    return jsonify({
        "success": bool(result),
        "message": "Servo settings saved to ESP32"
    })


@app.route('/api/arm/servo/load', methods=['GET'])
def load_servo_settings():
    """Load servo settings from ESP32 EEPROM"""
    global servo_settings

    result = send_to_esp(ARM_PORT, "SERVO:LOAD")
    # ESP32 should respond with: OK:trim0,trim1,...:min0,min1,...:max0,max1,...:expo0,expo1,...
    if result and result.startswith("OK:"):
        try:
            parts = result.split(':')
            if len(parts) >= 5:
                servo_settings['trim'] = list(map(int, parts[1].split(',')))
                servo_settings['min'] = list(map(int, parts[2].split(',')))
                servo_settings['max'] = list(map(int, parts[3].split(',')))
                servo_settings['expo'] = list(map(int, parts[4].split(',')))
                return jsonify({
                    "success": True,
                    "settings": servo_settings
                })
        except Exception as e:
            logger.error(f"Failed to parse servo settings: {e}")

    return jsonify({
        "success": True,
        "settings": servo_settings,
        "note": "Using cached settings"
    })


@app.route('/api/arm/servo/test', methods=['POST'])
def servo_test():
    """Move servo to absolute angle for testing."""
    global arm_angles
    data = request.json or {}
    joint = data.get('joint', 0)
    if isinstance(joint, str):
        name_map = {'shoulder': 0, 'wyaw': 1, 'wpitch': 2, 'elbow': 3}
        joint = name_map.get(joint, 0)
    angle = data.get('angle', 90)

    if joint < 0 or joint >= 5:
        return jsonify({"success": False, "error": "Joint must be 0-4"}), 400

    angle = max(0, min(180, angle))
    arm_angles[joint] = angle

    # Map joint to ESP32 command (nexus_arm_controller.ino)
    joint_cmds = {
        0: f"b_angle {angle}",       # Base stepper (TB6600)
        1: f"shoulder {angle}",      # Shoulder servo (PCA ch1)
        2: f"wrist_yaw {angle}",     # Wrist yaw servo (PCA ch1)
        3: f"wrist_pitch {angle}",   # Wrist pitch servo (PCA ch2)
        4: f"elbow {angle}",         # Elbow servo (PCA ch3)
    }
    cmd = joint_cmds.get(joint, f"elbow {angle}")
    result = send_to_esp(ARM_PORT, cmd)

    return jsonify({
        "success": bool(result),
        "joint": joint,
        "angle": angle
    })


# =============================================================================
# LED CHANNEL CALIBRATION ENDPOINTS (Arduino Micro CH1/CH2)
# =============================================================================

@app.route('/api/lights/ch/setting', methods=['POST'])
def led_ch_setting():
    """Set LED channel calibration setting"""
    global led_settings
    data = request.json or {}
    ch = data.get('ch', 1)
    setting_type = data.get('type', 'brightness')
    value = data.get('value', 255)

    if ch < 1 or ch > 2:
        return jsonify({"success": False,
                        "error": "Channel must be 1-2"}), 400

    if setting_type not in led_settings:
        return jsonify({"success": False,
                        "error": f"Unknown: {setting_type}"}), 400

    led_settings[setting_type][ch - 1] = value

    cmd = f"BRIGHT:{value}"
    result = send_to_esp(RING_PORT, cmd)

    return jsonify({
        "success": bool(result),
        "ch": ch,
        "type": setting_type,
        "value": value
    })


@app.route('/api/lights/ch/settings', methods=['GET'])
def get_led_settings():
    """Get all LED channel calibration settings"""
    return jsonify({
        "success": True,
        "settings": led_settings
    })


# =============================================================================
# SYSTEM STATS ENDPOINT (Pi Health Monitoring)
# =============================================================================

def get_pi_temp():
    """Get Raspberry Pi CPU temperature."""
    try:
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            # Output: temp=45.0'C
            temp_str = result.stdout.decode().strip()
            temp = float(temp_str.replace("temp=", "").replace("'C", ""))
            return temp
    except Exception:
        pass
    return None


@app.route('/api/system/stats', methods=['GET'])
def system_stats():
    """Get Pi system stats: CPU, memory, disk, temperature."""
    stats = {
        "success": True,
        "hostname": "snarf",
        "cpu_percent": None,
        "memory_percent": None,
        "memory_used_mb": None,
        "memory_total_mb": None,
        "disk_percent": None,
        "disk_used_gb": None,
        "disk_total_gb": None,
        "temperature": None,
        "uptime": None
    }

    # Try psutil first (more accurate)
    try:
        import psutil
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        stats["memory_percent"] = mem.percent
        stats["memory_used_mb"] = round(mem.used / (1024 * 1024))
        stats["memory_total_mb"] = round(mem.total / (1024 * 1024))
        disk = psutil.disk_usage('/')
        stats["disk_percent"] = disk.percent
        stats["disk_used_gb"] = round(disk.used / (1024 * 1024 * 1024), 1)
        stats["disk_total_gb"] = round(disk.total / (1024 * 1024 * 1024), 1)
        # Uptime
        import time
        stats["uptime"] = int(time.time() - psutil.boot_time())
    except ImportError:
        # Fallback to shell commands
        try:
            # CPU from /proc/stat
            result = subprocess.run(
                "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'",
                shell=True, capture_output=True, timeout=5
            )
            if result.returncode == 0:
                stats["cpu_percent"] = float(result.stdout.decode().strip())
        except Exception:
            pass

        try:
            # Memory from free
            result = subprocess.run(['free', '-m'], capture_output=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.decode().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    stats["memory_total_mb"] = int(parts[1])
                    stats["memory_used_mb"] = int(parts[2])
                    stats["memory_percent"] = round(
                        (int(parts[2]) / int(parts[1])) * 100, 1
                    )
        except Exception:
            pass

        try:
            # Disk from df
            result = subprocess.run(['df', '-h', '/'], capture_output=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.decode().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    stats["disk_percent"] = int(parts[4].replace('%', ''))
        except Exception:
            pass

    # Temperature (Pi-specific)
    stats["temperature"] = get_pi_temp()

    return jsonify(stats)


# =============================================================================
# CAMERA CALIBRATION ENDPOINTS (For 95%+ Consistent Imaging)
# =============================================================================

@app.route('/api/camera/settings', methods=['GET'])
def get_camera_settings():
    """Get current locked camera settings"""
    return jsonify({
        "success": True,
        "settings": CAMERA_LOCKED_SETTINGS,
        "lens_position": current_lens_position
    })


@app.route('/api/camera/settings', methods=['POST'])
def update_camera_settings():
    """Update locked camera settings for calibration"""
    global CAMERA_LOCKED_SETTINGS, current_lens_position
    data = request.json or {}

    # Update individual settings
    for key in ['shutter', 'gain', 'brightness', 'contrast',
                'saturation', 'sharpness', 'settle_time']:
        if key in data:
            CAMERA_LOCKED_SETTINGS[key] = float(data[key])

    for key in ['awb', 'denoise']:
        if key in data:
            CAMERA_LOCKED_SETTINGS[key] = str(data[key])

    if 'lens_position' in data:
        current_lens_position = float(data['lens_position'])

    logger.info(f"Camera settings updated: {CAMERA_LOCKED_SETTINGS}")
    return jsonify({
        "success": True,
        "settings": CAMERA_LOCKED_SETTINGS,
        "lens_position": current_lens_position
    })


@app.route('/api/camera/test_consistency', methods=['POST'])
def test_consistency():
    """
    Take multiple shots of same scene to test imaging consistency.
    Returns stats on how similar the images are.
    """
    data = request.json or {}
    shots = data.get('shots', 5)
    camera = data.get('camera', 0)

    results = []
    for i in range(shots):
        filename = capture_owleye(
            camera=camera,
            suffix=f"_consistency_{i}",
            locked=True
        )
        if filename:
            # Get basic image stats
            try:
                img = cv2.imread(filename)
                if img is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    results.append({
                        'file': filename,
                        'mean': float(np.mean(gray)),
                        'std': float(np.std(gray)),
                        'min': int(np.min(gray)),
                        'max': int(np.max(gray))
                    })
            except Exception as e:
                logger.error(f"Image analysis error: {e}")

    if len(results) < 2:
        return jsonify({"success": False, "error": "Not enough images captured"})

    # Calculate consistency metrics
    means = [r['mean'] for r in results]
    stds = [r['std'] for r in results]

    consistency = {
        'shots': len(results),
        'mean_brightness': round(np.mean(means), 2),
        'brightness_variance': round(np.std(means), 4),
        'mean_contrast': round(np.mean(stds), 2),
        'contrast_variance': round(np.std(stds), 4),
        'consistent': np.std(means) < 1.0 and np.std(stds) < 0.5
    }

    logger.info(f"Consistency test: {consistency}")
    return jsonify({
        "success": True,
        "consistency": consistency,
        "images": results
    })


@app.route('/api/camera/focus_sweep', methods=['POST'])
def focus_sweep():
    """
    Sweep through focus positions to find optimal for card distance.
    Returns sharpness score at each position.
    """
    global current_lens_position
    data = request.json or {}
    start = data.get('start', 6.0)
    end = data.get('end', 12.0)
    steps = data.get('steps', 7)

    results = []
    step_size = (end - start) / (steps - 1)

    for i in range(steps):
        pos = start + (i * step_size)
        filename = capture_owleye(
            lens_position=pos,
            suffix=f"_focus_{pos:.1f}",
            locked=False  # Don't use locked for focus testing
        )
        if filename:
            try:
                img = cv2.imread(filename)
                if img is not None:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    # Laplacian variance = sharpness metric
                    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                    sharpness = laplacian.var()
                    results.append({
                        'lens_position': round(pos, 2),
                        'sharpness': round(sharpness, 2),
                        'file': filename
                    })
            except Exception as e:
                logger.error(f"Focus sweep error: {e}")

    if results:
        # Find best focus position
        best = max(results, key=lambda x: x['sharpness'])
        current_lens_position = best['lens_position']
        logger.info(f"Best focus: {best['lens_position']} (sharpness: {best['sharpness']})")

        return jsonify({
            "success": True,
            "results": results,
            "best": best,
            "new_lens_position": current_lens_position
        })

    return jsonify({"success": False, "error": "Focus sweep failed"})


# =============================================================================
# OPTIMAL CAPTURE - BEST IMAGE POSSIBLE (All Hardware Utilized)
# =============================================================================

@app.route('/api/capture/optimal', methods=['POST'])
def capture_optimal():
    """
    SCARF's Ultimate Capture - produces the BEST possible image using ALL hardware.
    
    Process:
    1. Wait for card to settle (motion detection)
    2. Optimize lighting (based on mode)
    3. Focus check/adjustment (if needed)
    4. Multi-exposure capture
    5. Select sharpest frame
    6. Return best image with quality metrics
    
    Modes:
    - 'ocr': Optimized for text recognition (flat lighting, high contrast)
    - 'grading': Optimized for surface analysis (side lighting, detail)
    - 'full': Multi-pass (flat + surface + foil) for comprehensive analysis
    - 'fast': Quick single shot with current settings
    
    POST JSON:
    {
        "mode": "ocr|grading|full|fast",
        "camera": "owleye|czur",
        "settle_time": 0.3,
        "multi_shot": 3,
        "check_focus": false
    }
    """
    data = request.json or {}
    mode = data.get('mode', 'ocr')
    camera = data.get('camera', 'owleye')
    settle_time = float(data.get('settle_time', 0.3))
    multi_shot = int(data.get('multi_shot', 3))
    check_focus = data.get('check_focus', False)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    result = {
        'success': False,
        'mode': mode,
        'timestamp': timestamp,
        'best_image': None,
        'all_images': [],
        'quality_metrics': {},
        'timing': {}
    }
    
    t_start = time.time()
    
    try:
        # === STEP 1: SETTLE TIME (let card stop moving) ===
        logger.info(f"Optimal capture: mode={mode}, settle={settle_time}s")
        time.sleep(settle_time)
        result['timing']['settle'] = settle_time
        
        # === STEP 2: OPTIMIZE LIGHTING ===
        t_light = time.time()
        if camera in ('czur', 'CZUR'):
            # CZUR: lightbox ON + rings ON = maximum illumination for OCR
            send_to_esp(LED_PORT, "light #ffffff")
            set_all_leds(ch1=(255, 255, 255), ch2=(255, 255, 255))
            logger.info("CZUR mode: ALL lights ON for maximum OCR visibility")
        else:
            send_to_esp(LED_PORT, "light off")
            if mode == 'ocr':
                set_all_leds(ch1=(255, 255, 255), ch2=(255, 255, 255))
            elif mode == 'grading':
                set_all_leds(ch1=(255, 255, 255), ch2=(255, 255, 255))
            elif mode == 'full':
                set_all_leds(ch1=(255, 255, 255), ch2=(0, 0, 0))
            else:
                set_all_leds(ch1=(200, 200, 200), ch2=(100, 100, 100))

        time.sleep(0.3)  # Let lights stabilize (lightbox needs longer)
        result['timing']['lighting'] = round((time.time() - t_light) * 1000, 1)
        
        # === STEP 3: FOCUS CHECK (optional) ===
        if check_focus:
            global current_lens_position  # Must declare at start of block
            t_focus = time.time()
            # Quick focus check - capture at 3 positions, pick best
            focus_results = []
            test_positions = [current_lens_position - 1, current_lens_position, current_lens_position + 1]
            for pos in test_positions:
                if 0 <= pos <= 15:
                    test_img = capture_owleye(lens_position=pos, suffix="_ftest", locked=False)
                    if test_img:
                        sharpness = calculate_sharpness(test_img)
                        focus_results.append({'pos': pos, 'sharpness': sharpness, 'file': test_img})
                        # Clean up test image
                        try:
                            os.remove(test_img)
                        except Exception:
                            pass
            
            if focus_results:
                best_focus = max(focus_results, key=lambda x: x['sharpness'])
                current_lens_position = best_focus['pos']
                result['quality_metrics']['focus_adjusted'] = current_lens_position
            
            result['timing']['focus_check'] = round((time.time() - t_focus) * 1000, 1)
        
        # === STEP 4: CAPTURE ===
        t_capture = time.time()
        captured_images = []
        
        if mode == 'full':
            # Full multi-pass sequence
            seq_result = capture_full_sequence_with_feedback()
            if seq_result['success']:
                captured_images = [seq_result['best']]
                result['all_images'] = seq_result['images']
                result['quality_metrics']['sharpness'] = seq_result.get('sharpness', {})
        else:
            # Multi-shot capture (take N shots, pick sharpest)
            for i in range(multi_shot):
                if camera == 'owleye':
                    img = capture_owleye(suffix=f"_opt{i}", locked=True)
                else:
                    cam_config = CAMERAS.get(camera, CAMERAS['czur'])
                    img = capture_usb(cam_config['device'], *cam_config['resolution'],
                                     suffix=f"_opt{i}", cam_name=camera)
                if img:
                    captured_images.append(img)
                time.sleep(0.1)  # Brief delay between shots
        
        result['timing']['capture'] = round((time.time() - t_capture) * 1000, 1)
        
        # === STEP 5: SELECT BEST IMAGE ===
        t_select = time.time()
        if captured_images:
            sharpness_scores = {}
            for img in captured_images:
                if img and os.path.exists(img):
                    score = calculate_sharpness(img)
                    sharpness_scores[img] = score
            
            if sharpness_scores:
                best_image = max(sharpness_scores.keys(), key=lambda x: sharpness_scores[x])
                result['best_image'] = best_image
                result['quality_metrics']['sharpness_scores'] = {
                    os.path.basename(k): round(v, 2) for k, v in sharpness_scores.items()
                }
                result['quality_metrics']['best_sharpness'] = round(sharpness_scores[best_image], 2)
                
                # Clean up non-best images (keep best only)
                for img in captured_images:
                    if img and img != best_image and os.path.exists(img):
                        try:
                            os.remove(img)
                        except:
                            pass
                
                result['success'] = True
        
        result['timing']['selection'] = round((time.time() - t_select) * 1000, 1)
        
        # === STEP 6: LIGHTS OFF ===
        leds_off()
        
        # Total time
        result['timing']['total_ms'] = round((time.time() - t_start) * 1000, 1)
        
        logger.info(f"Optimal capture complete: {result['best_image']} "
                   f"(sharpness: {result['quality_metrics'].get('best_sharpness', 'N/A')}, "
                   f"time: {result['timing']['total_ms']}ms)")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Optimal capture error: {e}")
        leds_off()  # Safety: lights off
        result['error'] = str(e)
        return jsonify(result), 500


@app.route('/api/capture/optimal/ocr', methods=['POST'])
def capture_optimal_ocr():
    """Quick endpoint for OCR-optimized capture"""
    data = request.json or {}
    data['mode'] = 'ocr'
    request.json = data
    return capture_optimal()


@app.route('/api/capture/optimal/grading', methods=['POST'])
def capture_optimal_grading():
    """Quick endpoint for grading-optimized capture"""
    data = request.json or {}
    data['mode'] = 'grading'
    request.json = data
    return capture_optimal()


def relay_poller():
    """
    Background thread that:
    1. Checks for capture requests from Jaques (every 5s)
    2. Pushes file listings to relay (every 60s)
    """
    logger.info("Starting relay poller thread (Jaques eyes integration)")
    file_push_counter = 0
    while True:
        try:
            # Check for pending capture requests
            req = check_relay_requests()
            if req:
                logger.info(f"Jaques requested capture: {req}")
                camera = req.get('camera', 'owleye')
                # Trigger capture
                if camera in CAMERAS:
                    cam_config = CAMERAS[camera]
                    if cam_config['type'] == 'usb':
                        filename = capture_usb(cam_config['device'], *cam_config['resolution'], cam_name=camera)
                    else:
                        filename = capture_owleye(cam_config['index'], *cam_config['resolution'])
                    if filename:
                        push_to_relay(
                            camera=camera,
                            scan_result={'image_path': filename, 'request_id': req.get('id')},
                            card_detected=True
                        )
                        logger.info(f"Fulfilled Jaques capture request: {camera}")

            # Push file listing every 60 seconds (12 iterations)
            file_push_counter += 1
            if file_push_counter >= 12:
                file_push_counter = 0
                Thread(target=push_file_listing, daemon=True).start()

        except Exception as e:
            logger.debug(f"Relay poller error: {e}")
        # Poll every 5 seconds
        time.sleep(5)



# SNARF OCR Endpoint
from snarf_ocr_enhanced import ocr_pipeline

@app.route('/api/ocr/set', methods=['POST'])
def ocr_set():
    data = request.json
    image_path = data.get('image_path')
    
    if not image_path:
        return jsonify({'error': 'image_path required'}), 400
        
    if not os.path.exists(image_path):
        return jsonify({'error': f'Image not found: {image_path}'}), 404
        
    result = ocr_pipeline(image_path)
    return jsonify(result)
\nif __name__ == '__main__':
    # Start relay poller in background
    relay_thread = Thread(target=relay_poller, daemon=True)
    relay_thread.start()

    logger.info("=" * 60)
    logger.info("SNARF - Scanner Control Server (Patent Pending)")
    logger.info("=" * 60)
    logger.info("Cameras:")
    for name, config in CAMERAS.items():
        logger.info(f"  - {name}: {config['type']} {config.get('device', config.get('index'))}")
    logger.info(f"Lights: {LED_PORT} (3 rings: top, left, right)")
    logger.info(f"Arm: {ARM_PORT} (6-DOF)")
    logger.info(f"Brok OCR: {BROK_URL}")
    logger.info(f"Relay: {RELAY_URL} (Jaques eyes)")
    logger.info("-" * 60)
    logger.info("Capture Endpoints:")
    logger.info("  POST /api/capture            - Single shot")
    logger.info("  POST /api/capture/full       - Multi-pass (flat+surface+foil)")
    logger.info("  POST /api/capture/full/feedback - Multi-pass with LED feedback")
    logger.info("  POST /api/capture/usb        - USB camera (CZUR/webcam)")
    logger.info("-" * 60)
    logger.info("Autoscan Endpoints (Hands-Free):")
    logger.info("  POST /api/autoscan/start     - Start motion-triggered scanning")
    logger.info("  POST /api/autoscan/stop      - Stop autoscan")
    logger.info("  GET  /api/autoscan/status    - Get status and last result")
    logger.info("-" * 60)
    logger.info("LED Endpoints:")
    logger.info("  POST /api/ring               - Individual ring control")
    logger.info("  POST /api/rings              - All rings at once")
    logger.info("  POST /api/rainbow            - Foil detection sweep")
    logger.info("  POST /api/led/pattern        - Named patterns (ready/scanning/success/fail)")
    logger.info("-" * 60)
    logger.info("Arm + Vacuum Endpoints:")
    logger.info("  POST /api/arm/jog            - Jog single joint")
    logger.info("  POST /api/arm/preset         - Move to preset (home/scan/eject/stack)")
    logger.info("  POST /api/arm/pickup         - Pickup sequence (move + vacuum on)")
    logger.info("  POST /api/arm/drop           - Drop sequence (move + vacuum off)")
    logger.info("  POST /api/vacuum/on          - Vacuum on (PCA ch5)")
    logger.info("  POST /api/vacuum/off         - Vacuum off")
    logger.info("  POST /api/vacuum/pulse       - Pulse vacuum (duration ms)")
    logger.info("  POST /api/lift/up            - Lift up")
    logger.info("  POST /api/lift/down          - Lift down")
    logger.info("  POST /api/lift/shoulder      - Lift shoulder angle (PCA ch6)")
    logger.info("  POST /api/lift/tilt          - Lift tilt angle (PCA ch7)")
    logger.info("-" * 60)
    logger.info("LED Feedback Guide:")
    logger.info("  Dim Green  = Ready for card")
    logger.info("  Yellow     = Motion detected")
    logger.info("  Blue       = Scanning in progress")
    logger.info("  Green x2   = Success!")
    logger.info("  Red x3     = Failed")
    logger.info("=" * 60)
    app.run(host='0.0.0.0', port=5001, debug=False)
