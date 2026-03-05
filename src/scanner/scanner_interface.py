"""
NEXUS Scanner Interface
Communicates with standalone scanner device over network
Scanner Device: 192.168.0.7 (Ubuntu with camera + Arduino)
"""

import requests
import json
from pathlib import Path
from datetime import datetime
import time

class ScannerInterface:
    """Interface to communicate with network scanner device"""
    
    def __init__(self, scanner_ip="192.168.0.7", scanner_port=5001):
        self.scanner_url = f"http://{scanner_ip}:{scanner_port}"
        self.last_scan = None
        self.connected = False
        
    def check_connection(self):
        """Check if scanner device is online and ready"""
        try:
            response = requests.get(f"{self.scanner_url}/status", timeout=2)
            if response.status_code == 200:
                data = response.json()
                self.connected = True
                return {
                    'online': True,
                    'camera': data.get('camera_ready', False),
                    'arduino': data.get('arduino_connected', False),
                    'message': 'Scanner ready'
                }
        except requests.exceptions.RequestException as e:
            self.connected = False
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
                f"{self.scanner_url}/lights",
                json={
                    'on': on,
                    'brightness': brightness,
                    'color': color
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
