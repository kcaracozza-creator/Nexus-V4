"""
SIMPLE CAMERA SCANNER
Works with any DirectShow camera - no fancy bullshit
"""

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime


class SimpleCameraScanner:
    """Dead simple camera scanner - just capture and OCR"""
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.camera = None
        self.last_frame = None
        
    def initialize(self):
        """Connect to camera"""
        try:
            self.camera = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.camera.isOpened():
                return False
            
            # Set resolution
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            # Test capture
            ret, frame = self.camera.read()
            if not ret:
                self.camera.release()
                return False
            
            print(f"✅ Camera {self.camera_index} initialized: {frame.shape}")
            return True
            
        except Exception as e:
            print(f"❌ Camera init failed: {e}")
            return False
    
    def get_frame(self):
        """Get current camera frame"""
        if not self.camera or not self.camera.isOpened():
            return None
        
        ret, frame = self.camera.read()
        if ret:
            self.last_frame = frame
            return frame
        return None
    
    def capture_card(self, save_path=None):
        """Capture a card image"""
        frame = self.get_frame()
        if frame is None:
            return None
        
        # Auto-save if path provided
        if save_path:
            cv2.imwrite(str(save_path), frame)
            print(f"💾 Saved: {save_path}")
        
        return frame
    
    def show_preview(self, window_name="Camera Preview"):
        """Show live preview (press Q to quit, SPACE to capture)"""
        if not self.camera or not self.camera.isOpened():
            print("❌ Camera not initialized")
            return
        
        captured_frames = []
        
        while True:
            frame = self.get_frame()
            if frame is None:
                break
            
            # Show frame
            cv2.imshow(window_name, frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                # Capture
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"card_{timestamp}.jpg"
                cv2.imwrite(filename, frame)
                captured_frames.append(filename)
                print(f"📸 Captured: {filename}")
        
        cv2.destroyAllWindows()
        return captured_frames
    
    def release(self):
        """Release camera"""
        if self.camera:
            self.camera.release()
            print("🔌 Camera released")


def test_scanner():
    """Test the scanner"""
    print("\n" + "="*60)
    print("SIMPLE CAMERA SCANNER TEST")
    print("="*60)
    
    # Try camera 0 (webcam)
    print("\n📷 Testing Camera 0...")
    scanner = SimpleCameraScanner(camera_index=0)
    if scanner.initialize():
        print("✅ Camera 0 working")
        
        # Capture test image
        test_path = "E:/MTTGG/test_capture_cam0.jpg"
        frame = scanner.capture_card(save_path=test_path)
        if frame is not None:
            print(f"✅ Test image saved: {test_path}")
            print(f"   Resolution: {frame.shape[1]}x{frame.shape[0]}")
        
        scanner.release()
    else:
        print("❌ Camera 0 failed")
    
    # Try camera 1 (DSLR)
    print("\n📷 Testing Camera 1...")
    scanner = SimpleCameraScanner(camera_index=1)
    if scanner.initialize():
        print("✅ Camera 1 working")
        
        # Capture test image
        test_path = "E:/MTTGG/test_capture_cam1.jpg"
        frame = scanner.capture_card(save_path=test_path)
        if frame is not None:
            print(f"✅ Test image saved: {test_path}")
            print(f"   Resolution: {frame.shape[1]}x{frame.shape[0]}")
        
        scanner.release()
    else:
        print("❌ Camera 1 failed")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_scanner()
