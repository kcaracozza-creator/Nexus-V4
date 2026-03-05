#!/usr/bin/env python3
"""
AI Recognition Performance Tuning for MTTGG
Optimizes AI recognition speed and accuracy
"""

import time
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import queue
import cv2
import numpy as np
from pathlib import Path
import json
import pickle
import hashlib
from typing import Dict, List, Tuple, Optional


class PerformanceOptimizer:
    """AI recognition performance optimizer"""
    
    def __init__(self):
        self.cache_enabled = True
        self.parallel_processing = True
        self.gpu_acceleration = False
        self.optimization_level = "high"
        
        # Performance metrics
        self.recognition_times = []
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Caching system
        self.image_cache = {}
        self.recognition_cache = {}
        self.cache_max_size = 1000
        
        # Threading
        self.thread_pool_size = min(8, multiprocessing.cpu_count())
        self.thread_pool = None
        
        self.setup_optimization()
    
    def setup_optimization(self):
        """Setup performance optimizations"""
        print("⚡ Setting up AI performance optimization...")
        
        # Initialize thread pool
        self.thread_pool = ThreadPoolExecutor(max_workers=self.thread_pool_size)
        
        # Test GPU availability
        self.gpu_acceleration = self.test_gpu_acceleration()
        print(f"ℹ️ GPU acceleration {'available' if self.gpu_acceleration else 'not available'} - using {'GPU' if self.gpu_acceleration else 'CPU'} optimization")
        
        print(f"[OK] Optimization ready - GPU: {self.gpu_acceleration}, Threads: {self.thread_pool_size}")
    
    def get_performance_stats(self):
        """Get current performance statistics"""
        return {
            'gpu_acceleration': self.gpu_acceleration,
            'thread_pool_size': self.thread_pool_size,
            'optimization_level': self.optimization_level,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_ratio': self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            'avg_recognition_time': np.mean(self.recognition_times) if self.recognition_times else 0,
            'total_recognitions': len(self.recognition_times)
        }
    
    def test_gpu_acceleration(self):
        """Test if GPU acceleration is available"""
        try:
            import cv2
            # Test if CUDA is available
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                return True
        except:
            pass
        return False
        self.thread_pool = ThreadPoolExecutor(max_workers=self.thread_pool_size)
        
        # Check for GPU acceleration
        self.gpu_acceleration = self._check_gpu_support()
        
        # Setup image preprocessing optimizations
        self._setup_preprocessing_optimizations()
        
        # Load cached data
        self._load_performance_cache()
        
        print(f"[OK] Optimization ready - GPU: {self.gpu_acceleration}, Threads: {self.thread_pool_size}")
    
    def _check_gpu_support(self):
        """Check for GPU acceleration support"""
        try:
            # Check OpenCV GPU support
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                print("[OK] CUDA GPU acceleration available")
                return True
        except:
            pass
        
        try:
            # Check for other GPU libraries
            import torch
            if torch.cuda.is_available():
                print("[OK] PyTorch CUDA available")
                return True
        except ImportError:
            pass
        
        print("ℹ️ GPU acceleration not available - using CPU optimization")
        return False
    
    def _setup_preprocessing_optimizations(self):
        """Setup optimized image preprocessing"""
        # Pre-compile CV2 operations for better performance
        self.preprocessing_pipeline = [
            ('resize', self._optimized_resize),
            ('denoise', self._optimized_denoise), 
            ('enhance', self._optimized_enhance),
            ('normalize', self._optimized_normalize)
        ]
    
    def _optimized_resize(self, image, target_size=(800, 600)):
        """Optimized image resizing"""
        if self.gpu_acceleration:
            try:
                # GPU-accelerated resize
                gpu_image = cv2.cuda_GpuMat()
                gpu_image.upload(image)
                gpu_resized = cv2.cuda.resize(gpu_image, target_size)
                result = gpu_resized.download()
                return result
            except:
                pass
        
        # CPU-optimized resize
        return cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)
    
    def _optimized_denoise(self, image):
        """Optimized noise reduction"""
        if self.optimization_level == "high":
            return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
        elif self.optimization_level == "medium":
            return cv2.bilateralFilter(image, 9, 75, 75)
        else:
            # Light denoising for speed
            kernel = np.ones((3,3), np.uint8)
            return cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
    
    def _optimized_enhance(self, image):
        """Optimized image enhancement"""
        if self.optimization_level == "high":
            # CLAHE for adaptive histogram equalization
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            if len(image.shape) == 3:
                # Color image
                lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
                lab[:,:,0] = clahe.apply(lab[:,:,0])
                return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            else:
                # Grayscale
                return clahe.apply(image)
        else:
            # Simple contrast enhancement
            return cv2.convertScaleAbs(image, alpha=1.2, beta=10)
    
    def _optimized_normalize(self, image):
        """Optimized image normalization"""
        return cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)
    
    def preprocess_image_optimized(self, image_path):
        """Optimized image preprocessing pipeline"""
        start_time = time.time()
        
        # Check cache first
        image_hash = self._get_image_hash(image_path)
        if self.cache_enabled and image_hash in self.image_cache:
            self.cache_hits += 1
            return self.image_cache[image_hash]
        
        self.cache_misses += 1
        
        # Load image
        image = cv2.imread(str(image_path))
        if image is None:
            return None
        
        # Apply optimization pipeline
        processed = image.copy()
        
        for step_name, step_func in self.preprocessing_pipeline:
            try:
                processed = step_func(processed)
            except Exception as e:
                print(f"[WARN] Preprocessing step {step_name} failed: {e}")
        
        # Cache result
        if self.cache_enabled:
            self._cache_image(image_hash, processed)
        
        processing_time = time.time() - start_time
        self.recognition_times.append(processing_time)
        
        return processed
    
    def _get_image_hash(self, image_path):
        """Get hash for image caching"""
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return str(image_path)
    
    def _cache_image(self, image_hash, processed_image):
        """Cache processed image"""
        if len(self.image_cache) >= self.cache_max_size:
            # Remove oldest entries
            to_remove = list(self.image_cache.keys())[:100]
            for key in to_remove:
                del self.image_cache[key]
        
        self.image_cache[image_hash] = processed_image
    
    def batch_process_images(self, image_paths, batch_size=4):
        """Process multiple images in parallel"""
        if not self.parallel_processing:
            return [self.preprocess_image_optimized(path) for path in image_paths]
        
        results = []
        
        # Process in batches
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            
            # Submit batch to thread pool
            futures = [self.thread_pool.submit(self.preprocess_image_optimized, path) 
                      for path in batch]
            
            # Collect results
            batch_results = [future.result() for future in futures]
            results.extend(batch_results)
        
        return results
    
    def optimize_recognition_pipeline(self, recognition_function):
        """Optimize recognition function with caching and parallel processing"""
        
        def optimized_recognition(image_path, *args, **kwargs):
            start_time = time.time()
            
            # Check recognition cache
            cache_key = self._get_recognition_cache_key(image_path, args, kwargs)
            if self.cache_enabled and cache_key in self.recognition_cache:
                self.cache_hits += 1
                return self.recognition_cache[cache_key]
            
            self.cache_misses += 1
            
            # Preprocess image
            processed_image = self.preprocess_image_optimized(image_path)
            if processed_image is None:
                return None
            
            # Run recognition
            try:
                result = recognition_function(processed_image, *args, **kwargs)
                
                # Cache result
                if self.cache_enabled:
                    self._cache_recognition_result(cache_key, result)
                
                processing_time = time.time() - start_time
                self.recognition_times.append(processing_time)
                
                return result
                
            except Exception as e:
                print(f"[WARN] Recognition error: {e}")
                return None
        
        return optimized_recognition
    
    def _get_recognition_cache_key(self, image_path, args, kwargs):
        """Generate cache key for recognition results"""
        key_data = f"{image_path}_{args}_{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _cache_recognition_result(self, cache_key, result):
        """Cache recognition result"""
        if len(self.recognition_cache) >= self.cache_max_size:
            # Remove oldest entries
            to_remove = list(self.recognition_cache.keys())[:100]
            for key in to_remove:
                del self.recognition_cache[key]
        
        self.recognition_cache[cache_key] = result
    
    def get_performance_stats(self):
        """Get performance statistics"""
        if not self.recognition_times:
            return {
                'avg_processing_time': 0,
                'total_processed': 0,
                'cache_hit_rate': 0,
                'optimization_enabled': True
            }
        
        return {
            'avg_processing_time': sum(self.recognition_times) / len(self.recognition_times),
            'total_processed': len(self.recognition_times),
            'cache_hit_rate': (self.cache_hits / (self.cache_hits + self.cache_misses) * 100) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'gpu_acceleration': self.gpu_acceleration,
            'thread_pool_size': self.thread_pool_size,
            'optimization_level': self.optimization_level
        }
    
    def benchmark_recognition(self, test_images, recognition_function):
        """Benchmark recognition performance"""
        print("🏁 Running recognition benchmark...")
        
        if not test_images:
            print("[ERROR] No test images provided")
            return
        
        # Test without optimization
        print("Testing without optimization...")
        self.cache_enabled = False
        self.parallel_processing = False
        
        start_time = time.time()
        results_unoptimized = []
        for image in test_images:
            result = recognition_function(image)
            results_unoptimized.append(result)
        unoptimized_time = time.time() - start_time
        
        # Test with optimization
        print("Testing with optimization...")
        self.cache_enabled = True
        self.parallel_processing = True
        
        start_time = time.time()
        optimized_function = self.optimize_recognition_pipeline(recognition_function)
        results_optimized = []
        for image in test_images:
            result = optimized_function(image)
            results_optimized.append(result)
        optimized_time = time.time() - start_time
        
        # Calculate improvement
        speedup = unoptimized_time / optimized_time if optimized_time > 0 else 0
        
        print(f"\\n📊 Benchmark Results:")
        print(f"   Images processed: {len(test_images)}")
        print(f"   Unoptimized time: {unoptimized_time:.2f}s")
        print(f"   Optimized time: {optimized_time:.2f}s")
        print(f"   Speedup: {speedup:.2f}x")
        print(f"   Avg time per image: {optimized_time/len(test_images):.3f}s")
        
        return {
            'speedup': speedup,
            'unoptimized_time': unoptimized_time,
            'optimized_time': optimized_time,
            'images_processed': len(test_images)
        }
    
    def _load_performance_cache(self):
        """Load cached performance data"""
        cache_file = Path("E:/MTTGG/performance_cache.pkl")
        
        try:
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.recognition_cache = cache_data.get('recognition_cache', {})
                    print(f"[OK] Loaded {len(self.recognition_cache)} cached recognition results")
        except Exception as e:
            print(f"[WARN] Could not load performance cache: {e}")
    
    def save_performance_cache(self):
        """Save performance cache to disk"""
        cache_file = Path("E:/MTTGG/performance_cache.pkl")
        
        try:
            cache_data = {
                'recognition_cache': self.recognition_cache,
                'performance_stats': self.get_performance_stats()
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            print(f"[OK] Saved performance cache with {len(self.recognition_cache)} results")
            
        except Exception as e:
            print(f"[WARN] Could not save performance cache: {e}")
    
    def clear_cache(self):
        """Clear all caches"""
        self.image_cache.clear()
        self.recognition_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        print("🧹 Performance cache cleared")
    
    def set_optimization_level(self, level):
        """Set optimization level (low, medium, high)"""
        if level in ['low', 'medium', 'high']:
            self.optimization_level = level
            self._setup_preprocessing_optimizations()
            print(f"⚙️ Optimization level set to: {level}")
        else:
            print(f"[ERROR] Invalid optimization level: {level}")
    
    def shutdown(self):
        """Cleanup resources"""
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        
        self.save_performance_cache()
        print("[OK] Performance optimizer shutdown complete")


class AIRecognitionAccelerator:
    """Specialized accelerator for AI card recognition"""
    
    def __init__(self, performance_optimizer):
        self.optimizer = performance_optimizer
        self.card_templates = {}
        self.feature_extractors = {}
        self.setup_recognition_acceleration()
    
    def setup_recognition_acceleration(self):
        """Setup specialized card recognition acceleration"""
        print("🚀 Setting up AI recognition acceleration...")
        
        # Initialize feature extractors
        self._setup_feature_extractors()
        
        # Load card templates
        self._load_card_templates()
        
        # Setup recognition models
        self._setup_recognition_models()
        
        print("[OK] AI recognition acceleration ready")
    
    def _setup_feature_extractors(self):
        """Setup optimized feature extractors"""
        # SIFT features for card matching
        try:
            self.feature_extractors['sift'] = cv2.SIFT_create()
            print("[OK] SIFT feature extractor ready")
        except:
            print("[WARN] SIFT not available")
        
        # ORB features (faster alternative)
        try:
            self.feature_extractors['orb'] = cv2.ORB_create(nfeatures=1000)
            print("[OK] ORB feature extractor ready")
        except:
            print("[WARN] ORB not available")
        
        # Template matcher
        self.feature_extractors['template'] = cv2.TM_CCOEFF_NORMED
    
    def _load_card_templates(self):
        """Load card templates for fast matching"""
        template_dir = Path("E:/MTTGG/card_templates")
        
        if template_dir.exists():
            for template_file in template_dir.glob("*.jpg"):
                try:
                    template = cv2.imread(str(template_file), cv2.IMREAD_GRAYSCALE)
                    card_name = template_file.stem
                    self.card_templates[card_name] = template
                except Exception as e:
                    print(f"[WARN] Could not load template {template_file}: {e}")
            
            print(f"[OK] Loaded {len(self.card_templates)} card templates")
        else:
            print("ℹ️ No card templates directory found")
    
    def _setup_recognition_models(self):
        """Setup machine learning models for recognition"""
        # Placeholder for ML model initialization
        # This would load pre-trained models for card classification
        self.models_loaded = False
        print("ℹ️ ML models not implemented yet")
    
    def accelerated_card_recognition(self, image_path):
        """Accelerated card recognition pipeline"""
        start_time = time.time()
        
        # Preprocess image with optimization
        processed_image = self.optimizer.preprocess_image_optimized(image_path)
        if processed_image is None:
            return None
        
        # Convert to grayscale for feature matching
        if len(processed_image.shape) == 3:
            gray = cv2.cvtColor(processed_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = processed_image
        
        results = []
        
        # Method 1: Template matching (fastest)
        template_result = self._template_matching(gray)
        if template_result:
            results.append(('template', template_result))
        
        # Method 2: Feature matching (more robust)
        if 'sift' in self.feature_extractors:
            feature_result = self._feature_matching(gray)
            if feature_result:
                results.append(('features', feature_result))
        
        # Method 3: ML classification (most accurate, if available)
        if self.models_loaded:
            ml_result = self._ml_classification(processed_image)
            if ml_result:
                results.append(('ml', ml_result))
        
        processing_time = time.time() - start_time
        
        # Return best result
        if results:
            # Prioritize results by method reliability
            best_result = self._select_best_result(results)
            return {
                'card_name': best_result,
                'processing_time': processing_time,
                'methods_used': [method for method, _ in results],
                'confidence': self._calculate_confidence(results)
            }
        else:
            return {
                'card_name': 'Unknown',
                'processing_time': processing_time,
                'methods_used': [],
                'confidence': 0.0
            }
    
    def _template_matching(self, gray_image):
        """Fast template matching"""
        best_match = None
        best_score = 0
        
        for card_name, template in self.card_templates.items():
            try:
                # Resize template to match image scale
                h, w = template.shape
                img_h, img_w = gray_image.shape
                
                if h > img_h or w > img_w:
                    scale = min(img_h / h, img_w / w) * 0.8
                    new_h, new_w = int(h * scale), int(w * scale)
                    template = cv2.resize(template, (new_w, new_h))
                
                # Template matching
                result = cv2.matchTemplate(gray_image, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                if max_val > best_score and max_val > 0.7:  # Threshold for good match
                    best_score = max_val
                    best_match = card_name
                    
            except Exception as e:
                continue
        
        return best_match
    
    def _feature_matching(self, gray_image):
        """Feature-based matching"""
        if 'sift' not in self.feature_extractors:
            return None
        
        sift = self.feature_extractors['sift']
        
        # Extract features from input image
        try:
            kp1, des1 = sift.detectAndCompute(gray_image, None)
            
            if des1 is None:
                return None
            
            best_match = None
            best_score = 0
            
            for card_name, template in self.card_templates.items():
                try:
                    kp2, des2 = sift.detectAndCompute(template, None)
                    
                    if des2 is None:
                        continue
                    
                    # Match features
                    bf = cv2.BFMatcher()
                    matches = bf.knnMatch(des1, des2, k=2)
                    
                    # Apply ratio test
                    good_matches = []
                    for match_pair in matches:
                        if len(match_pair) == 2:
                            m, n = match_pair
                            if m.distance < 0.75 * n.distance:
                                good_matches.append(m)
                    
                    # Score based on number of good matches
                    score = len(good_matches) / len(kp1) if len(kp1) > 0 else 0
                    
                    if score > best_score and score > 0.1:  # Threshold for good match
                        best_score = score
                        best_match = card_name
                        
                except Exception as e:
                    continue
            
            return best_match
            
        except Exception as e:
            return None
    
    def _ml_classification(self, processed_image):
        """ML-based classification (placeholder)"""
        # This would use a trained model for card classification
        return None
    
    def _select_best_result(self, results):
        """Select best result from multiple methods"""
        # Priority order: ML > Features > Template
        method_priority = {'ml': 3, 'features': 2, 'template': 1}
        
        best_method = None
        best_priority = 0
        
        for method, result in results:
            priority = method_priority.get(method, 0)
            if priority > best_priority:
                best_priority = priority
                best_method = result
        
        return best_method
    
    def _calculate_confidence(self, results):
        """Calculate confidence score"""
        if not results:
            return 0.0
        
        # Simple confidence based on number of agreeing methods
        method_count = len(results)
        unique_results = len(set(result for _, result in results))
        
        # Higher confidence if multiple methods agree
        confidence = (method_count - unique_results + 1) / method_count
        return confidence


# Global performance optimizer
_performance_optimizer = None
_recognition_accelerator = None

def get_performance_optimizer():
    """Get global performance optimizer"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer

def get_recognition_accelerator():
    """Get global recognition accelerator"""
    global _recognition_accelerator
    if _recognition_accelerator is None:
        optimizer = get_performance_optimizer()
        _recognition_accelerator = AIRecognitionAccelerator(optimizer)
    return _recognition_accelerator

def optimized_card_recognition(image_path):
    """Optimized card recognition function"""
    accelerator = get_recognition_accelerator()
    return accelerator.accelerated_card_recognition(image_path)

def get_performance_stats():
    """Get current performance statistics"""
    optimizer = get_performance_optimizer()
    return optimizer.get_performance_stats()


if __name__ == "__main__":
    # Test performance optimization
    print("⚡ Testing AI Recognition Performance Tuning")
    print("=" * 50)
    
    optimizer = PerformanceOptimizer()
    accelerator = AIRecognitionAccelerator(optimizer)
    
    # Show configuration
    stats = optimizer.get_performance_stats()
    print(f"\\n⚙️ Configuration:")
    print(f"   GPU Acceleration: {stats['gpu_acceleration']}")
    print(f"   Thread Pool Size: {stats['thread_pool_size']}")
    print(f"   Optimization Level: {stats['optimization_level']}")
    
    print("\\n[OK] Performance tuning ready!")
    print("💡 Use optimized_card_recognition() for fast recognition")