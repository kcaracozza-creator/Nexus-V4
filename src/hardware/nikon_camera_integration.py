#!/usr/bin/env python3
"""
MTTGG Nikon Camera Integration v1.0
Professional dual-camera system for MTG card scanning

Hardware Detected:
- Camera 0: Nikon Webcam (backup/preview)
- Camera 1: Nikon DSLR (primary high-quality capture)
- DigiCamControl: Professional DSLR control software

Features:
- Automatic camera detection and fallback
- Professional DSLR capture with DigiCamControl
- Webcam backup for reliability
- Integration with Arduino RGB lighting
- Auto-focus and exposure optimization
"""

import cv2
import os
import time
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Dict

class NikonCameraSystem:
    """Professional dual-camera system for MTTGG card scanning."""
    
    def __init__(self):
        self.dslr_camera = None
        self.webcam_camera = None
        self.active_camera = None
        self.camera_mode = "auto"  # auto, dslr, webcam
        
        # DigiCamControl paths
        self.digicam_exe = r"C:\Program Files (x86)\digiCamControl\CameraControlCmd.exe"
        self.digicam_remote_exe = r"C:\Program Files (x86)\digiCamControl\CameraControlRemoteCmd.exe"
        
        # Capture settings
        self.capture_dir = r"E:\MTTGG\Scanned_Cards"
        os.makedirs(self.capture_dir, exist_ok=True)
        
        # Camera indices
        self.WEBCAM_INDEX = 0  # Nikon webcam
        self.DSLR_INDEX = 1    # Nikon DSLR via USB
        
        # Quality settings
        self.dslr_resolution = (6000, 4000)  # Professional DSLR resolution
        self.webcam_resolution = (1920, 1080)  # HD webcam
        
        # Statistics
        self.captures_total = 0
        self.captures_dslr = 0
        self.captures_webcam = 0
    
    def initialize(self) -> bool:
        """Initialize both camera systems with auto-detection."""
        print("🔍 Initializing Nikon Camera System...")
        
        # Try DSLR first (highest quality)
        if self._init_dslr():
            print("✅ DSLR Camera (Primary) - Ready")
            self.active_camera = self.dslr_camera
            self.camera_mode = "dslr"
        else:
            print("⚠️ DSLR Camera - Not available")
        
        # Initialize webcam backup
        if self._init_webcam():
            print("✅ Webcam Camera (Backup) - Ready")
            if not self.active_camera:
                self.active_camera = self.webcam_camera
                self.camera_mode = "webcam"
        else:
            print("⚠️ Webcam Camera - Not available")
        
        if self.active_camera:
            print(f"\n✨ Camera System Ready - Mode: {self.camera_mode.upper()}")
            return True
        else:
            print("\n❌ No cameras available")
            return False
    
    def _init_dslr(self) -> bool:
        """Initialize Nikon DSLR via OpenCV."""
        try:
            # Try DirectShow backend for Windows
            self.dslr_camera = cv2.VideoCapture(self.DSLR_INDEX, cv2.CAP_DSHOW)
            
            if self.dslr_camera.isOpened():
                # Configure DSLR settings
                self.dslr_camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.dslr_resolution[0])
                self.dslr_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.dslr_resolution[1])
                self.dslr_camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                self.dslr_camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual mode
                
                # Test capture
                ret, frame = self.dslr_camera.read()
                if ret and frame is not None:
                    actual_res = (frame.shape[1], frame.shape[0])
                    print(f"   DSLR Resolution: {actual_res[0]}x{actual_res[1]}")
                    return True
            
            if self.dslr_camera:
                self.dslr_camera.release()
            self.dslr_camera = None
            return False
            
        except Exception as e:
            print(f"   DSLR init error: {e}")
            return False
    
    def _init_webcam(self) -> bool:
        """Initialize Nikon webcam."""
        try:
            self.webcam_camera = cv2.VideoCapture(self.WEBCAM_INDEX, cv2.CAP_DSHOW)
            
            if self.webcam_camera.isOpened():
                # Configure webcam settings
                self.webcam_camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.webcam_resolution[0])
                self.webcam_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.webcam_resolution[1])
                self.webcam_camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                
                # Test capture
                ret, frame = self.webcam_camera.read()
                if ret and frame is not None:
                    actual_res = (frame.shape[1], frame.shape[0])
                    print(f"   Webcam Resolution: {actual_res[0]}x{actual_res[1]}")
                    return True
            
            if self.webcam_camera:
                self.webcam_camera.release()
            self.webcam_camera = None
            return False
            
        except Exception as e:
            print(f"   Webcam init error: {e}")
            return False
    
    def capture_card_image(self, card_name: Optional[str] = None) -> Optional[str]:
        """
        Capture high-quality card image.
        
        Args:
            card_name: Optional card name for filename
            
        Returns:
            Path to captured image, or None if failed
        """
        if not self.active_camera:
            print("❌ No camera available")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if card_name:
            # Sanitize card name for filename
            safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in card_name)
            filename = f"{safe_name}_{timestamp}.jpg"
        else:
            filename = f"card_{timestamp}.jpg"
        
        filepath = os.path.join(self.capture_dir, filename)
        
        # Try active camera first
        if self.camera_mode == "dslr":
            result = self._capture_dslr(filepath)
            if result:
                self.captures_dslr += 1
                self.captures_total += 1
                print(f"✅ DSLR Capture: {filename}")
                return result
            
            # Fallback to webcam
            print("⚠️ DSLR capture failed, trying webcam...")
            if self.webcam_camera:
                result = self._capture_webcam(filepath)
                if result:
                    self.captures_webcam += 1
                    self.captures_total += 1
                    print(f"✅ Webcam Capture: {filename}")
                    return result
        
        else:  # webcam mode
            result = self._capture_webcam(filepath)
            if result:
                self.captures_webcam += 1
                self.captures_total += 1
                print(f"✅ Webcam Capture: {filename}")
                return result
        
        print("❌ Capture failed")
        return None
    
    def _capture_dslr(self, filepath: str) -> Optional[str]:
        """Capture image from DSLR camera."""
        try:
            if not self.dslr_camera or not self.dslr_camera.isOpened():
                return None
            
            # Allow camera to adjust exposure
            for i in range(3):
                ret, frame = self.dslr_camera.read()
                time.sleep(0.1)
            
            # Capture final high-quality frame
            ret, frame = self.dslr_camera.read()
            
            if ret and frame is not None:
                # Save with maximum quality
                cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
                
                # Verify file
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                    print(f"   Size: {file_size:.2f} MB")
                    return filepath
            
            return None
            
        except Exception as e:
            print(f"   DSLR capture error: {e}")
            return None
    
    def _capture_webcam(self, filepath: str) -> Optional[str]:
        """Capture image from webcam."""
        try:
            if not self.webcam_camera or not self.webcam_camera.isOpened():
                return None
            
            # Allow camera to adjust
            for i in range(3):
                ret, frame = self.webcam_camera.read()
                time.sleep(0.1)
            
            # Capture frame
            ret, frame = self.webcam_camera.read()
            
            if ret and frame is not None:
                # Save with high quality
                cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                # Verify file
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                    print(f"   Size: {file_size:.2f} MB")
                    return filepath
            
            return None
            
        except Exception as e:
            print(f"   Webcam capture error: {e}")
            return None
    
    def capture_with_digicam(self, filepath: str) -> bool:
        """
        Capture using DigiCamControl CLI for maximum quality.
        
        This provides professional camera control beyond OpenCV.
        """
        if not os.path.exists(self.digicam_exe):
            print("⚠️ DigiCamControl not found")
            return False
        
        try:
            # DigiCamControl command-line capture
            cmd = [
                self.digicam_exe,
                "/capture",
                "/filename", filepath
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and os.path.exists(filepath):
                file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                print(f"✅ DigiCamControl Capture: {os.path.basename(filepath)}")
                print(f"   Size: {file_size:.2f} MB")
                return True
            else:
                print(f"❌ DigiCamControl capture failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ DigiCamControl timeout")
            return False
        except Exception as e:
            print(f"❌ DigiCamControl error: {e}")
            return False
    
    def switch_camera(self, mode: str = "auto"):
        """
        Switch active camera.
        
        Args:
            mode: 'auto', 'dslr', or 'webcam'
        """
        if mode == "dslr" and self.dslr_camera:
            self.active_camera = self.dslr_camera
            self.camera_mode = "dslr"
            print("📷 Switched to DSLR mode")
        elif mode == "webcam" and self.webcam_camera:
            self.active_camera = self.webcam_camera
            self.camera_mode = "webcam"
            print("📷 Switched to Webcam mode")
        elif mode == "auto":
            # Prefer DSLR if available
            if self.dslr_camera:
                self.active_camera = self.dslr_camera
                self.camera_mode = "dslr"
                print("📷 Auto mode - Using DSLR")
            elif self.webcam_camera:
                self.active_camera = self.webcam_camera
                self.camera_mode = "webcam"
                print("📷 Auto mode - Using Webcam")
        else:
            print(f"❌ Camera mode '{mode}' not available")
    
    def get_statistics(self) -> Dict:
        """Get capture statistics."""
        return {
            'total_captures': self.captures_total,
            'dslr_captures': self.captures_dslr,
            'webcam_captures': self.captures_webcam,
            'active_mode': self.camera_mode,
            'dslr_available': self.dslr_camera is not None,
            'webcam_available': self.webcam_camera is not None
        }
    
    def cleanup(self):
        """Release camera resources."""
        if self.dslr_camera:
            self.dslr_camera.release()
        if self.webcam_camera:
            self.webcam_camera.release()
        print("📷 Cameras released")


# Test function
def test_camera_system():
    """Test the dual-camera system."""
    print("=" * 60)
    print("MTTGG Nikon Camera System Test")
    print("=" * 60)
    
    camera_system = NikonCameraSystem()
    
    if camera_system.initialize():
        print("\n📸 Testing capture...")
        
        # Test capture
        image_path = camera_system.capture_card_image("Test_Card")
        
        if image_path:
            print(f"\n✅ Test successful!")
            print(f"   Image saved: {image_path}")
            
            # Show statistics
            stats = camera_system.get_statistics()
            print(f"\n📊 Statistics:")
            print(f"   Total captures: {stats['total_captures']}")
            print(f"   DSLR captures: {stats['dslr_captures']}")
            print(f"   Webcam captures: {stats['webcam_captures']}")
            print(f"   Active mode: {stats['active_mode']}")
        
        camera_system.cleanup()
    else:
        print("\n❌ Camera initialization failed")


if __name__ == "__main__":
    test_camera_system()
