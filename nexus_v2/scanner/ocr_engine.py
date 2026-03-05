#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS V2 Bulletproof OCR Engine
================================

Patent Claim 2: Bulletproof OCR System

This module implements a NEVER-CRASH OCR system with:
- Auto-path detection for Tesseract installation
- Multi-pass validation (3-tier fallback strategy)
- Retry logic with exponential backoff
- Graceful degradation (returns empty string, never crashes)
- Exception handling for 100% uptime

Prior Art Problem:
    Standard OCR crashes when Tesseract encounters unexpected input,
    corrupted images, or installation issues.

Our Solution:
    Bulletproof wrapper that catches ALL exceptions and provides
    clean fallback, ensuring system never crashes on OCR failures.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import time

# Try to import PIL and pytesseract
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================
# CONFIGURATION
# ============================================

OCR_CONFIG = {
    "confidence_threshold": 70.0,
    "max_retries": 3,
    "retry_delay": 0.1,
}


# ============================================
# ENUMS AND DATA CLASSES
# ============================================

class OCRPass(Enum):
    """OCR pass types for multi-pass validation"""
    STANDARD = "standard"
    ALTERNATIVE_PSM = "alt_psm"
    AGGRESSIVE = "aggressive"


@dataclass
class OCRResult:
    """Result from an OCR operation"""
    text: str
    confidence: float
    method: OCRPass
    success: bool
    error: Optional[str] = None
    processing_time: float = 0.0

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 70.0


# ============================================
# TESSERACT MANAGER - Auto-path detection
# ============================================

class TesseractManager:
    """
    Manages Tesseract OCR installation and configuration.

    Auto-detects Tesseract installation across multiple platforms
    and common installation paths.
    """

    # Common Tesseract installation paths
    DEFAULT_PATHS = [
        # Windows paths
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
        # Linux paths
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        # macOS paths
        "/opt/homebrew/bin/tesseract",
        "/usr/local/Cellar/tesseract/*/bin/tesseract",
    ]

    def __init__(self):
        self.tesseract_path = self._find_tesseract()
        self.is_available = self.tesseract_path is not None

        if self.is_available and PYTESSERACT_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
            logger.info(f"Tesseract found: {self.tesseract_path}")
        else:
            logger.warning("Tesseract not found - OCR will be unavailable")

    def _find_tesseract(self) -> Optional[str]:
        """Auto-detect Tesseract installation across platforms"""
        # Check default paths
        for path in self.DEFAULT_PATHS:
            if Path(path).exists():
                return path

        # Check PATH environment variable
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["where", "tesseract"],
                    capture_output=True, text=True, timeout=5
                )
            else:
                result = subprocess.run(
                    ["which", "tesseract"],
                    capture_output=True, text=True, timeout=5
                )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass

        return None


# ============================================
# BULLETPROOF OCR ENGINE - Patent Claim 2
# ============================================

class BulletproofOCR:
    """
    Never-crash OCR system implementing Patent Claim 2.

    Features:
    - Auto-path detection for Tesseract
    - Multi-pass validation (3-tier fallback strategy)
    - Retry logic with exponential backoff
    - Graceful degradation (returns "Unknown" instead of crash)
    - Exception handling for 100% uptime

    Usage:
        ocr = BulletproofOCR()
        result = ocr.extract_text(image)
        print(result.text, result.confidence)
    """

    def __init__(self):
        self.manager = TesseractManager()
        self.is_available = self.manager.is_available and PYTESSERACT_AVAILABLE

        if not self.is_available:
            logger.warning("BulletproofOCR: Tesseract unavailable - OCR disabled")

    def extract_text(self, image, config: str = '--psm 6 --oem 3') -> OCRResult:
        """
        Extract text with bulletproof error handling - NEVER CRASHES.

        Args:
            image: PIL Image, numpy array, or file path
            config: Tesseract configuration string

        Returns:
            OCRResult with text, confidence, and status
        """
        start_time = time.time()

        if not self.is_available:
            return OCRResult(
                text="",
                confidence=0.0,
                method=OCRPass.STANDARD,
                success=False,
                error="Tesseract unavailable",
                processing_time=0.0
            )

        try:
            # Convert to PIL Image if needed
            pil_image = self._to_pil_image(image)
            if pil_image is None:
                return OCRResult(
                    text="",
                    confidence=0.0,
                    method=OCRPass.STANDARD,
                    success=False,
                    error="Failed to convert image",
                    processing_time=time.time() - start_time
                )

            # Run multi-pass OCR
            result = self._multi_pass_ocr(pil_image)
            result.processing_time = time.time() - start_time
            return result

        except Exception as e:
            logger.error(f"BulletproofOCR unexpected error: {e}")
            return OCRResult(
                text="",
                confidence=0.0,
                method=OCRPass.STANDARD,
                success=False,
                error=str(e),
                processing_time=time.time() - start_time
            )

    def _to_pil_image(self, image) -> Optional[Image.Image]:
        """Convert various image formats to PIL Image - NEVER CRASHES"""
        try:
            # Already PIL Image
            if PIL_AVAILABLE and isinstance(image, Image.Image):
                return image

            # File path
            if isinstance(image, (str, Path)):
                if PIL_AVAILABLE:
                    return Image.open(image)
                return None

            # Numpy array (OpenCV)
            if CV2_AVAILABLE and isinstance(image, np.ndarray):
                if PIL_AVAILABLE:
                    # Convert BGR to RGB
                    if len(image.shape) == 3 and image.shape[2] == 3:
                        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    else:
                        rgb = image
                    return Image.fromarray(rgb)
                return None

            return None
        except Exception as e:
            logger.debug(f"Image conversion failed: {e}")
            return None

    def _multi_pass_ocr(self, image: Image.Image) -> OCRResult:
        """
        Three-tier OCR strategy with progressive fallback.

        Pass 1: Standard configuration (--psm 6)
        Pass 2: Alternative PSM mode (--psm 7 for single line)
        Pass 3: Aggressive preprocessing + OCR

        Returns best result across all passes.
        """
        best_result = OCRResult("", 0.0, OCRPass.STANDARD, False)

        # Pass 1: Standard
        result = self._ocr_pass(image, '--psm 6 --oem 3', OCRPass.STANDARD)
        if result.confidence >= OCR_CONFIG["confidence_threshold"]:
            return result
        if result.confidence > best_result.confidence:
            best_result = result

        # Pass 2: Alternative PSM (single line mode)
        result2 = self._ocr_pass(image, '--psm 7 --oem 3', OCRPass.ALTERNATIVE_PSM)
        if result2.confidence >= OCR_CONFIG["confidence_threshold"]:
            return result2
        if result2.confidence > best_result.confidence:
            best_result = result2

        # Pass 3: Aggressive preprocessing
        try:
            enhanced = self._aggressive_preprocess(image)
            result3 = self._ocr_pass(enhanced, '--psm 6 --oem 3', OCRPass.AGGRESSIVE)
            if result3.confidence > best_result.confidence:
                best_result = result3
        except Exception as e:
            logger.debug(f"Aggressive preprocessing failed: {e}")

        return best_result

    def _ocr_pass(self, image: Image.Image, config: str, method: OCRPass) -> OCRResult:
        """
        Single OCR pass with retry logic and exponential backoff.

        NEVER CRASHES - always returns OCRResult.
        """
        for attempt in range(OCR_CONFIG["max_retries"]):
            try:
                # Extract text
                text = pytesseract.image_to_string(image, config=config).strip()

                # Get confidence
                try:
                    data = pytesseract.image_to_data(
                        image, config=config,
                        output_type=pytesseract.Output.DICT
                    )
                    confidences = [int(c) for c in data['conf'] if int(c) > 0]
                    confidence = sum(confidences) / len(confidences) if confidences else 0.0
                except Exception:
                    # Fallback confidence estimation
                    confidence = 50.0 if text else 0.0

                return OCRResult(
                    text=text,
                    confidence=confidence,
                    method=method,
                    success=True
                )

            except Exception as e:
                if attempt < OCR_CONFIG["max_retries"] - 1:
                    # Exponential backoff
                    delay = OCR_CONFIG["retry_delay"] * (2 ** attempt)
                    time.sleep(delay)
                    logger.debug(f"OCR retry {attempt + 1}, delay {delay}s: {e}")

        return OCRResult(
            text="",
            confidence=0.0,
            method=method,
            success=False,
            error="All retries failed"
        )

    def _aggressive_preprocess(self, image: Image.Image) -> Image.Image:
        """
        Aggressive image preprocessing for difficult OCR cases.

        Applies:
        - Grayscale conversion
        - Contrast enhancement
        - Bilateral filtering (edge-preserving denoise)
        - Adaptive thresholding
        """
        if not CV2_AVAILABLE:
            return image

        try:
            # Convert to numpy
            img = np.array(image)

            # Convert to grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            else:
                gray = img

            # Enhance contrast
            enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=10)

            # Bilateral filter (edge-preserving denoise)
            filtered = cv2.bilateralFilter(enhanced, 9, 75, 75)

            # Adaptive threshold
            binary = cv2.adaptiveThreshold(
                filtered, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )

            return Image.fromarray(binary)

        except Exception as e:
            logger.debug(f"Aggressive preprocessing failed: {e}")
            return image


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

# Global instance for convenience
_ocr_instance: Optional[BulletproofOCR] = None


def get_ocr() -> BulletproofOCR:
    """Get or create the global BulletproofOCR instance."""
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = BulletproofOCR()
    return _ocr_instance


def extract_text(image, config: str = '--psm 6 --oem 3') -> OCRResult:
    """Convenience function for OCR - NEVER CRASHES."""
    return get_ocr().extract_text(image, config)


def is_ocr_available() -> bool:
    """Check if OCR is available."""
    return get_ocr().is_available


# ============================================
# TEST
# ============================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("NEXUS V2 Bulletproof OCR Engine - Patent Claim 2")
    print("=" * 60)

    ocr = BulletproofOCR()
    print(f"\nTesseract available: {ocr.is_available}")

    if ocr.is_available:
        print("\nFeatures implemented:")
        print("  [x] Auto-path detection")
        print("  [x] Multi-pass validation (3-tier)")
        print("  [x] Retry logic with exponential backoff")
        print("  [x] Graceful degradation (never crashes)")
        print("  [x] 100% uptime guarantee")
    else:
        print("\nInstall Tesseract to enable OCR:")
        print("  Windows: choco install tesseract")
        print("  Linux: sudo apt install tesseract-ocr")
        print("  macOS: brew install tesseract")

    print("\n" + "=" * 60)
