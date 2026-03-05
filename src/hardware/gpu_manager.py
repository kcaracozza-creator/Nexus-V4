#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU Acceleration Manager for Nexus Card System
Handles eGPU detection, CUDA configuration, and AI model optimization
"""

import os
import platform
from typing import Optional, Dict, Any

class GPUManager:
    """
    Manages GPU resources for AI card recognition and image processing
    Supports integrated GPUs, discrete GPUs, and external GPUs (eGPU)
    """
    
    def __init__(self, config=None):
        """Initialize GPU manager with configuration"""
        self.config = config
        self.gpu_available = False
        self.egpu_detected = False
        self.device_name = "CPU"
        self.device_id = None
        self.cuda_available = False
        self.rocm_available = False  # AMD ROCm support
        self.tensorflow_gpu = False
        self.torch_gpu = False
        self.gpu_vendor = "unknown"  # nvidia, amd, intel
        
        # Detect available GPU frameworks
        self._detect_frameworks()
        
        # Detect and configure GPU
        self._detect_gpu()
    
    def _detect_frameworks(self):
        """Detect which GPU frameworks are available"""
        # Check for PyTorch (CUDA or ROCm)
        try:
            import torch
            
            # Check for CUDA (NVIDIA)
            if torch.cuda.is_available():
                self.torch_gpu = True
                self.cuda_available = True
                self.gpu_vendor = "nvidia"
                print(f"✅ PyTorch CUDA available: {torch.cuda.get_device_name(0)}")
            
            # Check for ROCm (AMD)
            elif hasattr(torch, 'hip') and torch.hip.is_available():
                self.torch_gpu = True
                self.rocm_available = True
                self.gpu_vendor = "amd"
                print(f"✅ PyTorch ROCm available (AMD GPU)")
            
            # Check device properties for AMD
            if self.torch_gpu and not self.cuda_available:
                try:
                    device_name = torch.cuda.get_device_name(0)  # Works with ROCm too
                    if "AMD" in device_name or "Radeon" in device_name:
                        self.gpu_vendor = "amd"
                        self.rocm_available = True
                        print(f"   Device: {device_name}")
                except:
                    pass
                    
        except ImportError:
            print("ℹ️ PyTorch not installed")
        
        # Check for TensorFlow GPU (supports both CUDA and ROCm)
        try:
            import tensorflow as tf
            gpus = tf.config.list_physical_devices('GPU')
            self.tensorflow_gpu = len(gpus) > 0
            if self.tensorflow_gpu:
                print(f"✅ TensorFlow GPU available: {len(gpus)} device(s)")
                for gpu in gpus:
                    print(f"   - {gpu.name}")
                    if "AMD" in str(gpu.name) or "ROCM" in str(gpu.name):
                        self.gpu_vendor = "amd"
                        self.rocm_available = True
        except ImportError:
            print("ℹ️ TensorFlow not installed")
        except Exception as e:
            print(f"⚠️ TensorFlow GPU check failed: {e}")
        
        # Check for DirectML (Windows AMD/Intel fallback)
        if platform.system() == "Windows" and not (self.cuda_available or self.rocm_available):
            try:
                import torch_directml
                self.torch_gpu = True
                print("✅ DirectML available (Windows GPU acceleration)")
            except ImportError:
                pass
        
        # Set overall GPU availability
        if not self.cuda_available and not self.rocm_available:
            if self.tensorflow_gpu or self.torch_gpu:
                # Some GPU detected but not CUDA/ROCm
                self.cuda_available = True  # Generic GPU flag
    
    def _detect_gpu(self):
        """Detect available GPUs including eGPU"""
        if not self.cuda_available:
            print("ℹ️ No CUDA-capable GPU detected, using CPU")
            return
        
        # Check for eGPU (usually shows as secondary device)
        if self.torch_gpu:
            import torch
            num_gpus = torch.cuda.device_count()
            
            print(f"\n🎮 GPU DETECTION")
            print(f"{'='*60}")
            print(f"Total CUDA devices: {num_gpus}")
            
            for i in range(num_gpus):
                device_props = torch.cuda.get_device_properties(i)
                device_name = torch.cuda.get_device_name(i)
                total_memory = device_props.total_memory / 1024**3  # GB
                
                print(f"\nDevice {i}: {device_name}")
                print(f"  Memory: {total_memory:.2f} GB")
                print(f"  Compute Capability: {device_props.major}.{device_props.minor}")
                
                # Check if this might be an eGPU (heuristic: higher device index)
                if i > 0:
                    print(f"  🔌 Likely External GPU (eGPU)")
                    self.egpu_detected = True
            
            print(f"{'='*60}\n")
            
            # Auto-select best GPU
            self.device_id = self._select_best_gpu()
            if self.device_id is not None:
                self.gpu_available = True
                self.device_name = torch.cuda.get_device_name(self.device_id)
                print(f"✅ Selected GPU: {self.device_name} (cuda:{self.device_id})")
    
    def _select_best_gpu(self) -> Optional[int]:
        """Select the best available GPU"""
        if not self.torch_gpu:
            return None
        
        import torch
        
        # Check config preference
        if self.config:
            gpu_device = self.config.get('hardware.gpu_device', 'auto')
            if gpu_device != 'auto':
                # User specified device (e.g., "cuda:0", "cuda:1")
                if gpu_device.startswith('cuda:'):
                    device_id = int(gpu_device.split(':')[1])
                    if device_id < torch.cuda.device_count():
                        return device_id
        
        # Auto-select: prefer eGPU (if detected), otherwise device 0
        num_gpus = torch.cuda.device_count()
        
        if num_gpus == 0:
            return None
        
        # If eGPU detected, prefer it (usually device 1)
        if self.egpu_detected and num_gpus > 1:
            # Select the device with most memory (eGPU usually has more)
            max_memory = 0
            best_device = 0
            
            for i in range(num_gpus):
                props = torch.cuda.get_device_properties(i)
                if props.total_memory > max_memory:
                    max_memory = props.total_memory
                    best_device = i
            
            return best_device
        
        # Default to first device
        return 0
    
    def get_device_string(self) -> str:
        """Get device string for PyTorch/TensorFlow"""
        if self.gpu_available and self.device_id is not None:
            return f"cuda:{self.device_id}"
        return "cpu"
    
    def configure_tensorflow(self):
        """Configure TensorFlow GPU settings"""
        if not self.tensorflow_gpu:
            return
        
        try:
            import tensorflow as tf
            
            # Get physical GPUs
            gpus = tf.config.list_physical_devices('GPU')
            if not gpus:
                return
            
            # Enable memory growth to avoid OOM
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            
            # Set memory limit if configured
            if self.config:
                memory_fraction = self.config.get('hardware.gpu_memory_fraction', 0.9)
                memory_limit = int(tf.config.experimental.get_memory_info(gpus[0])['total'] * memory_fraction)
                
                tf.config.set_logical_device_configuration(
                    gpus[self.device_id if self.device_id is not None else 0],
                    [tf.config.LogicalDeviceConfiguration(memory_limit=memory_limit)]
                )
            
            # Enable mixed precision if configured
            if self.config and self.config.get('hardware.enable_mixed_precision', True):
                from tensorflow.keras import mixed_precision
                mixed_precision.set_global_policy('mixed_float16')
                print("✅ TensorFlow mixed precision enabled (FP16)")
            
            print("✅ TensorFlow GPU configured")
            
        except Exception as e:
            print(f"⚠️ TensorFlow GPU configuration failed: {e}")
    
    def configure_pytorch(self):
        """Configure PyTorch GPU settings"""
        if not self.torch_gpu:
            return
        
        try:
            import torch
            
            # Set default device
            if self.gpu_available and self.device_id is not None:
                torch.cuda.set_device(self.device_id)
            
            # Enable cuDNN benchmark for optimal performance
            torch.backends.cudnn.benchmark = True
            
            # Enable TF32 on Ampere GPUs for faster training
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            
            # Set memory allocator
            if hasattr(torch.cuda, 'empty_cache'):
                torch.cuda.empty_cache()
            
            print("✅ PyTorch GPU configured")
            
        except Exception as e:
            print(f"⚠️ PyTorch GPU configuration failed: {e}")
    
    def get_optimal_batch_size(self, base_batch_size: int = 32) -> int:
        """Get optimal batch size based on available GPU memory"""
        if not self.gpu_available:
            return base_batch_size // 4  # Reduce for CPU
        
        if self.torch_gpu:
            import torch
            if self.device_id is not None:
                props = torch.cuda.get_device_properties(self.device_id)
                memory_gb = props.total_memory / 1024**3
                
                # Scale batch size based on GPU memory
                if memory_gb >= 24:  # High-end GPU (RTX 4090, A6000)
                    return base_batch_size * 4
                elif memory_gb >= 16:  # Mid-high (RTX 4080)
                    return base_batch_size * 2
                elif memory_gb >= 8:  # Mid (RTX 4060 Ti)
                    return base_batch_size
                else:  # Entry-level
                    return base_batch_size // 2
        
        return base_batch_size
    
    def optimize_opencv(self):
        """Optimize OpenCV for GPU acceleration"""
        try:
            import cv2
            
            # Check for CUDA support in OpenCV
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                print(f"✅ OpenCV CUDA available: {cv2.cuda.getCudaEnabledDeviceCount()} device(s)")
                
                # Set CUDA device
                if self.device_id is not None:
                    cv2.cuda.setDevice(self.device_id)
                
                return True
            else:
                print("ℹ️ OpenCV built without CUDA support")
                return False
                
        except Exception as e:
            print(f"ℹ️ OpenCV GPU check: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get GPU status information"""
        status = {
            'gpu_available': self.gpu_available,
            'egpu_detected': self.egpu_detected,
            'device_name': self.device_name,
            'device_string': self.get_device_string(),
            'cuda_available': self.cuda_available,
            'pytorch_available': self.torch_gpu,
            'tensorflow_available': self.tensorflow_gpu
        }
        
        if self.torch_gpu and self.device_id is not None:
            import torch
            props = torch.cuda.get_device_properties(self.device_id)
            status['memory_gb'] = props.total_memory / 1024**3
            status['compute_capability'] = f"{props.major}.{props.minor}"
        
        return status
    
    def print_status(self):
        """Print GPU status summary"""
        status = self.get_status()
        
        print("\n" + "="*60)
        print("GPU ACCELERATION STATUS")
        print("="*60)
        print(f"GPU Available: {'✅ Yes' if status['gpu_available'] else '❌ No'}")
        print(f"Device: {status['device_name']}")
        print(f"Device String: {status['device_string']}")
        
        if status['egpu_detected']:
            print("🔌 External GPU (eGPU) detected!")
        
        if status.get('memory_gb'):
            print(f"GPU Memory: {status['memory_gb']:.2f} GB")
        
        if status.get('compute_capability'):
            print(f"Compute Capability: {status['compute_capability']}")
        
        print(f"\nFramework Support:")
        print(f"  PyTorch CUDA: {'✅' if status['pytorch_available'] else '❌'}")
        print(f"  TensorFlow GPU: {'✅' if status['tensorflow_available'] else '❌'}")
        print("="*60 + "\n")


if __name__ == "__main__":
    # Demo GPU detection
    from config_manager import get_config
    
    print("🎮 Nexus Card System - GPU Manager Demo\n")
    
    config = get_config()
    gpu_manager = GPUManager(config)
    
    gpu_manager.print_status()
    
    # Configure frameworks
    gpu_manager.configure_pytorch()
    gpu_manager.configure_tensorflow()
    gpu_manager.optimize_opencv()
    
    print(f"\n💡 Recommended batch size: {gpu_manager.get_optimal_batch_size()}")
