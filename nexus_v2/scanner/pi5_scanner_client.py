#!/usr/bin/env python3
"""
Pi5 Scanner Client for NEXUS V2
Communicates with the new Pi5 Scanner REST API
Provides unified interface for card scanning with multi-camera support
"""

import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class Pi5ScannerClient:
    """
    Client for communicating with Pi5 Scanner REST API

    Connects to the new scanner running on Snarf (192.168.1.219:5001)
    Provides methods for:
    - Card scanning with multiple cameras
    - Lighting control
    - Image capture
    - Multi-pass scan protocol
    """

    def __init__(self, scanner_url: str = "http://192.168.1.219:5001"):
        """
        Initialize Pi5 scanner client

        Args:
            scanner_url: Base URL of the scanner API
        """
        self.scanner_url = scanner_url.rstrip('/')
        self.session = requests.Session()
        self.connected = False
        self._last_scan = None

    def connect(self) -> bool:
        """
        Test connection to scanner

        Returns:
            bool: True if scanner is reachable
        """
        try:
            response = self.session.get(
                f"{self.scanner_url}/health",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.connected = data.get('status') == 'ok'
                logger.info(f"Scanner connected: {data}")
                return self.connected
            else:
                logger.error(f"Scanner health check failed: {response.status_code}")
                self.connected = False
                return False
        except Exception as e:
            logger.error(f"Scanner connection failed: {e}")
            self.connected = False
            return False

    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get scanner status

        Returns:
            dict: Scanner status with cameras, hardware, and scan count
        """
        try:
            response = self.session.get(
                f"{self.scanner_url}/api/status",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return None

    def scan_card(
        self,
        camera: str = "czur",
        mode: str = "ocr",
        timeout: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Scan a card

        Args:
            camera: Camera to use ('owleye', 'czur', 'webcam')
            mode: Scan mode ('ocr', 'grading', 'foil')
            timeout: Request timeout in seconds

        Returns:
            dict: Scan result with OCR data, filename, etc.
        """
        try:
            response = self.session.post(
                f"{self.scanner_url}/api/scan",
                json={"camera": camera, "mode": mode},
                timeout=timeout
            )

            if response.status_code == 200:
                result = response.json()
                self._last_scan = result
                logger.info(f"Scan complete: {result.get('filename')}")
                return result
            else:
                logger.error(f"Scan failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Scan request failed: {e}")
            return None

    def multi_pass_scan(self, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """
        Execute multi-pass scan protocol

        Performs:
        1. Motion detection
        2. Back scan (type detection)
        3. Flat scan (OCR)
        4. Surface scan (grading)
        5. Foil scan (holographic detection)

        Args:
            timeout: Request timeout in seconds

        Returns:
            dict: Results from all passes with best_result selected
        """
        try:
            response = self.session.post(
                f"{self.scanner_url}/api/multi_scan",
                timeout=timeout
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            logger.error(f"Multi-pass scan failed: {e}")
            return None

    def set_lighting(self, profile: str) -> bool:
        """
        Set lighting profile

        Args:
            profile: Lighting profile ('ocr', 'grading', 'foil', 'off')

        Returns:
            bool: True if successful
        """
        try:
            response = self.session.post(
                f"{self.scanner_url}/api/lights",
                json={"profile": profile},
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to set lighting: {e}")
            return False

    def set_custom_lighting(
        self,
        r: int = 0,
        g: int = 0,
        b: int = 0,
        w: int = 0
    ) -> bool:
        """
        Set custom RGBW lighting

        Args:
            r: Red (0-255)
            g: Green (0-255)
            b: Blue (0-255)
            w: White (0-255)

        Returns:
            bool: True if successful
        """
        try:
            response = self.session.post(
                f"{self.scanner_url}/api/lights",
                json={"lightbox": {"r": r, "g": g, "b": b, "w": w}},
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to set custom lighting: {e}")
            return False

    def capture_image(self, camera: str = "owleye") -> Optional[bytes]:
        """
        Capture raw image without processing

        Args:
            camera: Camera to use ('owleye', 'czur', 'webcam')

        Returns:
            bytes: Image data (JPEG), or None if failed
        """
        try:
            response = self.session.get(
                f"{self.scanner_url}/api/capture/{camera}",
                timeout=15
            )

            if response.status_code == 200:
                return response.content
            return None

        except Exception as e:
            logger.error(f"Image capture failed: {e}")
            return None

    def get_cameras(self) -> List[str]:
        """
        Get list of available cameras

        Returns:
            list: Camera names
        """
        status = self.get_status()
        if status:
            return status.get('cameras', [])
        return []

    def is_hardware_connected(self) -> Dict[str, bool]:
        """
        Check hardware connection status

        Returns:
            dict: Hardware connection states
        """
        status = self.get_status()
        if status:
            return {
                'esp32': status.get('esp32_connected', False),
                'arduino': status.get('arduino_connected', False),
                'initialized': status.get('initialized', False)
            }
        return {
            'esp32': False,
            'arduino': False,
            'initialized': False
        }

    def lights_on(self) -> bool:
        """Turn lights on (OCR profile)"""
        return self.set_lighting('ocr')

    def lights_off(self) -> bool:
        """Turn lights off"""
        return self.set_lighting('off')

    def get_last_scan(self) -> Optional[Dict[str, Any]]:
        """Get last scan result"""
        return self._last_scan


def create_scanner_client(config=None) -> Pi5ScannerClient:
    """
    Factory function to create scanner client from config

    Args:
        config: ConfigManager instance with scanner settings

    Returns:
        Pi5ScannerClient: Configured scanner client
    """
    if config:
        # Handle both old dict-style and new ConfigManager
        if hasattr(config, 'scanner'):
            # New ConfigManager style
            scanner_url = config.scanner.snarf_url
        elif hasattr(config, 'get'):
            # Old dict-style config
            scanner_ip = config.get('scanner.scanner_ip', '192.168.1.219')
            scanner_port = config.get('scanner.scanner_port', 5001)
            scanner_url = f"http://{scanner_ip}:{scanner_port}"
        else:
            scanner_url = "http://192.168.1.219:5001"
    else:
        scanner_url = "http://192.168.1.219:5001"

    return Pi5ScannerClient(scanner_url)
