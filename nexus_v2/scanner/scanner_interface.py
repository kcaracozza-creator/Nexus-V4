"""
NEXUS Scanner Interface
Communicates with standalone scanner device over network
Scanner Device: 192.168.1.219 (Raspberry Pi 5 with camera + Arduino)
"""

import requests
import json
import logging
from pathlib import Path
from datetime import datetime
import time
import sys
import os

logger = logging.getLogger(__name__)

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from config.config_manager import config
    from config.logging_manager import log_info, log_error, log_scanner_event
except ImportError:
    config = None
    # Fallback logging functions using proper logger
    def log_info(msg): logger.info(msg)
    def log_error(msg, exc_info=False): logger.error(msg, exc_info=exc_info)
    def log_scanner_event(event, details=None): logger.info(f"SCANNER: {event} - {details}")

class ScannerInterface:
    """Interface to communicate with network scanner device"""
    
    def __init__(self, scanner_ip=None, scanner_port=None):
        # Use configuration manager if available, otherwise fall back to defaults
        if config:
            self.scanner_ip = scanner_ip or config.get_scanner_ip()
            self.scanner_port = scanner_port or config.get_scanner_port()
        else:
            self.scanner_ip = scanner_ip or "192.168.1.219"
            self.scanner_port = scanner_port or 5001
            
        self.scanner_url = f"http://{self.scanner_ip}:{self.scanner_port}"
        self.last_scan = None
        self.connected = False
        
        # Log initialization
        log_info(f"Scanner interface initialized for {self.scanner_ip}:{self.scanner_port}")
        
    def check_connection(self):
        """Check if scanner device is online and ready"""
        log_scanner_event("Connection check", f"Checking {self.scanner_url}")
        try:
            response = requests.get(f"{self.scanner_url}/status", timeout=2)
            if response.status_code == 200:
                data = response.json()
                self.connected = True
                log_scanner_event("Connection success", f"Scanner online at {self.scanner_ip}")
                return {
                    'online': True,
                    'camera': data.get('camera_ready', False),
                    'arduino': data.get('arduino_connected', False),
                    'message': 'Scanner ready'
                }
        except requests.exceptions.RequestException as e:
            self.connected = False
            log_error(f"Scanner connection failed: {str(e)}")
            return {
                'online': False,
                'camera': False,
                'arduino': False,
                'message': f'Scanner offline: {str(e)}'
            }
    
    def scan_card(self):
        """Request scanner to capture and identify a card"""
        try:
            # Send scan request to scanner device
            response = requests.post(
                f"{self.scanner_url}/scan",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                self.last_scan = result
                
                return {
                    'success': True,
                    'card_name': result.get('card_name', 'Unknown'),
                    'set_code': result.get('set_code', ''),
                    'confidence': result.get('confidence', 0),
                    'image_path': result.get('image_path', ''),
                    'timestamp': result.get('timestamp', datetime.now().isoformat())
                }
            else:
                return {
                    'success': False,
                    'error': f'Scanner error: {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Scanner timeout - device may be busy'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }
    
    def set_lights(self, on=True, brightness=200, color=(255, 255, 255)):
        """Control scanner lighting"""
        try:
            response = requests.post(
                f"{self.scanner_url}/api/lights",
                json={
                    'state': 'on' if on else 'off',
                    'brightness': brightness,
                    'r': color[0] if isinstance(color, (list, tuple)) else 255,
                    'g': color[1] if isinstance(color, (list, tuple)) else 255,
                    'b': color[2] if isinstance(color, (list, tuple)) else 255
                },
                timeout=2
            )
            return response.status_code == 200
        except:
            return False
    
    def test_scanner(self):
        """Run scanner test sequence"""
        try:
            response = requests.get(f"{self.scanner_url}/test", timeout=5)
            return response.status_code == 200
        except:
            return False

# Global scanner instance
_scanner = None

def get_scanner():
    """Get or create scanner interface"""
    global _scanner
    if _scanner is None:
        _scanner = ScannerInterface()
    return _scanner
