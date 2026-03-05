#!/usr/bin/env python3
"""
Enhanced Camera Hardware Optimization for MTTGG
Optimizes Nikon DSLR integration and camera performance
"""

import os
import sys
import subprocess
import time
import threading
from pathlib import Path
import json


class CameraOptimizer:
    """Advanced camera hardware optimizer"""
    
    def __init__(self):
        self.camera_methods = {}
        self.active_camera = None
        self.camera_settings = {}
        self.performance_stats = {}
        self.optimization_enabled = True
        
    def initialize_camera_systems(self):
        """Initialize all camera detection methods with optimization"""
        print("📷 Initializing optimized camera systems...")
        
        # Method 1: Nikon DSLR via gphoto2 (Linux/Mac)
        self._setup_gphoto2_optimized()
        
        # Method 2: Nikon DSLR via DigiCamControl (Windows)
        self._setup_digicam_optimized()
        
        # Method 3: OpenCV DirectShow (Universal)
        self._setup_opencv_optimized()
        
        # Method 4: Nikon SDK (if available)
        self._setup_nikon_sdk()
        
        return self._select_best_camera()
    
    def _setup_gphoto2_optimized(self):
        """Setup optimized gphoto2 for Nikon DSLRs"""
        try:
            # Check if gphoto2 is available
            result = subprocess.run(['gphoto2', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                print("✅ gphoto2 available")
                
                # Optimized gphoto2 configuration
                self.camera_methods['gphoto2'] = {
                    'available': True,
                    'priority': 1,  # Highest priority for DSLRs
                    'type': 'DSLR',
                    'capture_method': self._gphoto2_capture_optimized,
                    'settings': {
                        'iso': 'auto',
                        'aperture': 'auto',
                        'shutter': '1/60',
                        'quality': 'JPEG_FINE',
                        'image_format': 'JPEG',
                        'focus_mode': 'auto',
                        'metering_mode': 'matrix'
                    }
                }
                
                # Detect connected cameras
                camera_list = self._detect_gphoto2_cameras()
                self.camera_methods['gphoto2']['cameras'] = camera_list
                
            else:
                print("⚠️ gphoto2 not available")
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"⚠️ gphoto2 setup failed: {e}")
            self.camera_methods['gphoto2'] = {'available': False}
    
    def _setup_digicam_optimized(self):
        """Setup optimized DigiCamControl for Windows"""
        try:
            # Common DigiCamControl paths
            digicam_paths = [
                r"C:\Program Files (x86)\digiCamControl\CameraControl.exe",
                r"C:\Program Files\digiCamControl\CameraControl.exe",
                r"E:\MTTGG\DigiCamControl\CameraControl.exe"
            ]
            
            digicam_path = None
            for path in digicam_paths:
                if os.path.exists(path):
                    digicam_path = path
                    break
            
            if digicam_path:
                print(f"✅ DigiCamControl found at: {digicam_path}")
                
                self.camera_methods['digicam'] = {
                    'available': True,
                    'priority': 2,
                    'type': 'DSLR',
                    'path': digicam_path,
                    'capture_method': self._digicam_capture_optimized,
                    'settings': {
                        'iso': 'auto',
                        'aperture': 'f/5.6',
                        'shutter': '1/60',
                        'quality': 'JPEG_FINE',
                        'focus_mode': 'single',
                        'white_balance': 'auto'
                    }
                }
                
                # Test DigiCamControl connection
                self._test_digicam_connection()
                
            else:
                print("⚠️ DigiCamControl not found")
                
        except Exception as e:
            print(f"⚠️ DigiCamControl setup failed: {e}")
            self.camera_methods['digicam'] = {'available': False}
    
    def _setup_opencv_optimized(self):
        """Setup optimized OpenCV camera capture"""
        try:
            import cv2
            
            print("✅ OpenCV available")
            
            self.camera_methods['opencv'] = {
                'available': True,
                'priority': 3,
                'type': 'Webcam',
                'capture_method': self._opencv_capture_optimized,
                'settings': {
                    'width': 1920,
                    'height': 1080,
                    'fps': 30,
                    'format': 'MJPG',
                    'auto_exposure': 0.25,
                    'brightness': 0,
                    'contrast': 32,
                    'saturation': 64
                }
            }
            
            # Detect available cameras
            available_cameras = self._detect_opencv_cameras()
            self.camera_methods['opencv']['cameras'] = available_cameras
            
        except ImportError:
            print("⚠️ OpenCV not available")
            self.camera_methods['opencv'] = {'available': False}
        except Exception as e:
            print(f"⚠️ OpenCV setup failed: {e}")
            self.camera_methods['opencv'] = {'available': False}
    
    def _setup_nikon_sdk(self):
        """Setup Nikon SDK if available (advanced)"""
        try:
            # Check for Nikon SDK
            nikon_sdk_paths = [
                r"C:\Program Files\Nikon\Nikon SDK",
                r"C:\Program Files (x86)\Nikon\Nikon SDK",
                r"E:\MTTGG\Nikon_SDK"
            ]
            
            sdk_available = any(os.path.exists(path) for path in nikon_sdk_paths)
            
            if sdk_available:
                print("✅ Nikon SDK detected")
                
                self.camera_methods['nikon_sdk'] = {
                    'available': True,
                    'priority': 0,  # Highest priority if available
                    'type': 'DSLR_SDK',
                    'capture_method': self._nikon_sdk_capture,
                    'settings': {
                        'iso': 'auto',
                        'aperture': 'auto',
                        'shutter': 'auto',
                        'quality': 'RAW+JPEG',
                        'focus_mode': 'AF-S',
                        'metering_mode': 'matrix'
                    }
                }
            else:
                print("ℹ️ Nikon SDK not available")
                
        except Exception as e:
            print(f"⚠️ Nikon SDK setup failed: {e}")
            self.camera_methods['nikon_sdk'] = {'available': False}
    
    def _detect_gphoto2_cameras(self):
        """Detect cameras via gphoto2"""
        try:
            result = subprocess.run(['gphoto2', '--auto-detect'], 
                                  capture_output=True, text=True, timeout=10)
            
            cameras = []
            for line in result.stdout.split('\\n'):
                if 'usb:' in line.lower():
                    cameras.append(line.strip())
            
            print(f"📷 Found {len(cameras)} gphoto2 cameras")
            return cameras
            
        except Exception as e:
            print(f"⚠️ Camera detection failed: {e}")
            return []
    
    def _detect_opencv_cameras(self):
        """Detect cameras via OpenCV"""
        try:
            import cv2
            
            cameras = []
            for i in range(5):  # Check first 5 camera indices
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    cameras.append(f"Camera {i}")
                    cap.release()
            
            print(f"📷 Found {len(cameras)} OpenCV cameras")
            return cameras
            
        except Exception as e:
            print(f"⚠️ OpenCV camera detection failed: {e}")
            return []
    
    def _test_digicam_connection(self):
        """Test DigiCamControl connection"""
        try:
            digicam_path = self.camera_methods['digicam']['path']
            
            # Test with a simple command
            result = subprocess.run([digicam_path, '/c', 'list'], 
                                  capture_output=True, text=True, timeout=10)
            
            if 'camera' in result.stdout.lower():
                print("✅ DigiCamControl camera connected")
                return True
            else:
                print("⚠️ No DigiCamControl camera detected")
                return False
                
        except Exception as e:
            print(f"⚠️ DigiCamControl test failed: {e}")
            return False
    
    def _select_best_camera(self):
        """Select the best available camera method"""
        available_methods = [(name, info) for name, info in self.camera_methods.items() 
                           if info.get('available', False)]
        
        if not available_methods:
            print("❌ No cameras available")
            return None
        
        # Sort by priority (lower number = higher priority)
        available_methods.sort(key=lambda x: x[1].get('priority', 99))
        
        best_method, best_info = available_methods[0]
        self.active_camera = best_method
        
        print(f"🎯 Selected camera method: {best_method} ({best_info['type']})")
        return best_method
    
    def _gphoto2_capture_optimized(self, output_path):
        """Optimized gphoto2 capture"""
        try:
            start_time = time.time()
            
            # Optimized gphoto2 command
            cmd = [
                'gphoto2',
                '--capture-image-and-download',
                '--filename', output_path,
                '--force-overwrite'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            capture_time = time.time() - start_time
            self._record_performance('gphoto2', capture_time, result.returncode == 0)
            
            if result.returncode == 0:
                print(f"✅ gphoto2 capture success ({capture_time:.2f}s)")
                return True
            else:
                print(f"❌ gphoto2 capture failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("⏱️ gphoto2 capture timeout")
            return False
        except Exception as e:
            print(f"❌ gphoto2 capture error: {e}")
            return False
    
    def _digicam_capture_optimized(self, output_path):
        """Optimized DigiCamControl capture"""
        try:
            start_time = time.time()
            
            digicam_path = self.camera_methods['digicam']['path']
            
            # Optimized DigiCamControl command
            cmd = [
                digicam_path,
                '/c', 'capture',
                '/filename', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            
            capture_time = time.time() - start_time
            self._record_performance('digicam', capture_time, result.returncode == 0)
            
            if result.returncode == 0 and os.path.exists(output_path):
                print(f"✅ DigiCamControl capture success ({capture_time:.2f}s)")
                return True
            else:
                print(f"❌ DigiCamControl capture failed")
                return False
                
        except Exception as e:
            print(f"❌ DigiCamControl capture error: {e}")
            return False
    
    def _opencv_capture_optimized(self, output_path):
        """Optimized OpenCV capture"""
        try:
            import cv2
            
            start_time = time.time()
            
            # Use first available camera
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                print("❌ Cannot open camera")
                return False
            
            # Set optimal settings
            settings = self.camera_methods['opencv']['settings']
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings['width'])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings['height'])
            cap.set(cv2.CAP_PROP_FPS, settings['fps'])
            
            # Capture frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                # Save image
                cv2.imwrite(output_path, frame)
                
                capture_time = time.time() - start_time
                self._record_performance('opencv', capture_time, True)
                
                print(f"✅ OpenCV capture success ({capture_time:.2f}s)")
                return True
            else:
                print("❌ OpenCV capture failed")
                return False
                
        except Exception as e:
            print(f"❌ OpenCV capture error: {e}")
            return False
    
    def _nikon_sdk_capture(self, output_path):
        """Nikon SDK capture (placeholder for advanced implementation)"""
        print("🔧 Nikon SDK capture - Advanced implementation required")
        return False
    
    def _record_performance(self, method, capture_time, success):
        """Record performance statistics"""
        if method not in self.performance_stats:
            self.performance_stats[method] = {
                'total_captures': 0,
                'successful_captures': 0,
                'failed_captures': 0,
                'avg_capture_time': 0,
                'times': []
            }
        
        stats = self.performance_stats[method]
        stats['total_captures'] += 1
        
        if success:
            stats['successful_captures'] += 1
            stats['times'].append(capture_time)
            stats['avg_capture_time'] = sum(stats['times']) / len(stats['times'])
        else:
            stats['failed_captures'] += 1
    
    def capture_image_optimized(self, output_path="captured_image.jpg"):
        """Optimized image capture using best available method"""
        if not self.active_camera:
            print("❌ No camera available")
            return False
        
        method_info = self.camera_methods[self.active_camera]
        capture_method = method_info['capture_method']
        
        print(f"📸 Capturing with {self.active_camera}...")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        return capture_method(output_path)
    
    def optimize_for_card_scanning(self):
        """Optimize camera settings specifically for card scanning"""
        print("🎯 Optimizing for card scanning...")
        
        if self.active_camera == 'gphoto2':
            # Optimal settings for card photography
            settings = {
                'iso': '100',  # Low ISO for less noise
                'aperture': 'f/8',  # Sweet spot for most lenses
                'shutter': '1/125',  # Fast enough to avoid camera shake
                'focus_mode': 'single',
                'metering_mode': 'matrix'
            }
            self._apply_gphoto2_settings(settings)
            
        elif self.active_camera == 'digicam':
            # DigiCamControl optimization
            settings = {
                'iso': '100',
                'aperture': 'f/8',
                'shutter': '1/125',
                'quality': 'JPEG_FINE',
                'focus_mode': 'single'
            }
            self._apply_digicam_settings(settings)
            
        elif self.active_camera == 'opencv':
            # OpenCV optimization for card scanning
            self._optimize_opencv_for_cards()
    
    def _apply_gphoto2_settings(self, settings):
        """Apply settings to gphoto2 camera"""
        try:
            for setting, value in settings.items():
                cmd = ['gphoto2', f'--set-config', f'{setting}={value}']
                subprocess.run(cmd, capture_output=True, timeout=5)
            print("✅ gphoto2 settings applied")
        except Exception as e:
            print(f"⚠️ gphoto2 settings error: {e}")
    
    def _apply_digicam_settings(self, settings):
        """Apply settings to DigiCamControl"""
        try:
            digicam_path = self.camera_methods['digicam']['path']
            
            for setting, value in settings.items():
                cmd = [digicam_path, '/c', 'set', setting, value]
                subprocess.run(cmd, capture_output=True, timeout=5)
            print("✅ DigiCamControl settings applied")
        except Exception as e:
            print(f"⚠️ DigiCamControl settings error: {e}")
    
    def _optimize_opencv_for_cards(self):
        """Optimize OpenCV settings for card scanning"""
        try:
            import cv2
            
            # Test capture to set optimal settings
            cap = cv2.VideoCapture(0)
            
            if cap.isOpened():
                # Set high resolution
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                
                # Set manual exposure for consistent lighting
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                cap.set(cv2.CAP_PROP_EXPOSURE, -4)  # Adjust as needed
                
                # Set other properties
                cap.set(cv2.CAP_PROP_CONTRAST, 32)
                cap.set(cv2.CAP_PROP_SATURATION, 64)
                cap.set(cv2.CAP_PROP_BRIGHTNESS, 0)
                
                cap.release()
                print("✅ OpenCV settings optimized for cards")
            
        except Exception as e:
            print(f"⚠️ OpenCV optimization error: {e}")
    
    def get_performance_report(self):
        """Get camera performance report"""
        return {
            'active_camera': self.active_camera,
            'available_methods': list(self.camera_methods.keys()),
            'performance_stats': self.performance_stats,
            'optimization_enabled': self.optimization_enabled
        }
    
    def run_camera_benchmark(self):
        """Run camera performance benchmark"""
        print("🏃 Running camera benchmark...")
        
        if not self.active_camera:
            print("❌ No camera available for benchmark")
            return
        
        test_captures = 5
        temp_dir = Path("E:/MTTGG/temp")
        temp_dir.mkdir(exist_ok=True)
        
        total_time = 0
        successful = 0
        
        for i in range(test_captures):
            output_path = temp_dir / f"benchmark_{i}.jpg"
            
            start = time.time()
            success = self.capture_image_optimized(str(output_path))
            end = time.time()
            
            if success:
                successful += 1
                total_time += (end - start)
                
                # Clean up
                if output_path.exists():
                    output_path.unlink()
        
        if successful > 0:
            avg_time = total_time / successful
            success_rate = successful / test_captures * 100
            
            print(f"📊 Benchmark Results:")
            print(f"   Camera: {self.active_camera}")
            print(f"   Successful: {successful}/{test_captures} ({success_rate:.1f}%)")
            print(f"   Average time: {avg_time:.2f}s")
            print(f"   Captures/minute: {60/avg_time:.1f}")
        else:
            print("❌ Benchmark failed - no successful captures")


# Global camera optimizer instance
_camera_optimizer = None

def get_camera_optimizer():
    """Get global camera optimizer instance"""
    global _camera_optimizer
    if _camera_optimizer is None:
        _camera_optimizer = CameraOptimizer()
        _camera_optimizer.initialize_camera_systems()
        _camera_optimizer.optimize_for_card_scanning()
    return _camera_optimizer

def capture_card_image_optimized(output_path="card_scan.jpg"):
    """Optimized card capture function"""
    optimizer = get_camera_optimizer()
    return optimizer.capture_image_optimized(output_path)

def get_camera_status():
    """Get current camera status"""
    optimizer = get_camera_optimizer()
    return optimizer.get_performance_report()


if __name__ == "__main__":
    # Test camera optimization
    print("📷 Testing Camera Hardware Optimization")
    print("=" * 50)
    
    optimizer = CameraOptimizer()
    optimizer.initialize_camera_systems()
    
    if optimizer.active_camera:
        print(f"✅ Camera ready: {optimizer.active_camera}")
        
        # Run benchmark
        optimizer.run_camera_benchmark()
        
        # Show performance report
        report = optimizer.get_performance_report()
        print(f"\\n📊 Performance Report:")
        print(f"Active Camera: {report['active_camera']}")
        print(f"Available Methods: {', '.join(report['available_methods'])}")
        
    else:
        print("❌ No cameras available")
        print("💡 Check camera connections and drivers")