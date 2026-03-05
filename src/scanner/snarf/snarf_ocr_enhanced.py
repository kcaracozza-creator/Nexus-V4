#!/usr/bin/env python3
"""
SNARF Enhanced OCR with EasyOCR GPU + Tesseract Fallback
Optimized for Magic: The Gathering card recognition
"""
import os
import re
import cv2
import logging
import numpy as np
from typing import Dict, Optional, Tuple

# Try GPU-accelerated EasyOCR first
try:
    import easyocr
    GPU_AVAILABLE = True
    reader = easyocr.Reader(['en'], gpu=True, verbose=False)
    logging.info("✅ EasyOCR GPU initialized")
except Exception as e:
    GPU_AVAILABLE = False
    logging.warning(f"⚠️  EasyOCR GPU unavailable: {e}")

# Tesseract fallback
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.error("❌ Tesseract not available")


def extract_set_collector_gpu(img_path: str) -> Tuple[Optional[str], Optional[str], float]:
    """Extract set code and collector number using EasyOCR GPU"""
    try:
        img = cv2.imread(img_path)
        if img is None:
            return None, None, 0.0
        
        h, w = img.shape[:2]
        # Bottom-left region for set/collector (e.g., "LTR 245/281")
        region = img[int(h*0.92):h, 0:int(w*0.30)]
        
        # EasyOCR on region
        results = reader.readtext(region, detail=1)
        
        # Find set/collector pattern
        for (bbox, text, conf) in results:
            match = re.search(r'([A-Z0-9]{2,4})\s*(\d+)/(\d+)', text, re.IGNORECASE)
            if match:
                set_code = match.group(1).upper()
                collector_num = match.group(2)
                confidence = conf * 100
                return set_code, collector_num, confidence
        
        return None, None, 0.0
        
    except Exception as e:
        logging.error(f"EasyOCR GPU error: {e}")
        return None, None, 0.0


def extract_set_collector_cpu(img_path: str) -> Tuple[Optional[str], Optional[str], float]:
    """Extract set code and collector number using Tesseract (fallback)"""
    try:
        img = cv2.imread(img_path)
        if img is None:
            return None, None, 0.0
        
        h, w = img.shape[:2]
        region = img[int(h*0.92):h, 0:int(w*0.30)]
        
        # Upscale for better OCR
        region = cv2.resize(region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # Tesseract OCR
        text = pytesseract.image_to_string(region, config='--psm 7').strip()
        
        # Find pattern
        match = re.search(r'([A-Z0-9]{2,4})\s*(\d+)/(\d+)', text, re.IGNORECASE)
        if match:
            return match.group(1).upper(), match.group(2), 90.0
        
        return None, None, 0.0
        
    except Exception as e:
        logging.error(f"Tesseract error: {e}")
        return None, None, 0.0


def extract_card_name_gpu(img_path: str) -> Tuple[Optional[str], float]:
    """Extract card name using EasyOCR GPU"""
    try:
        img = cv2.imread(img_path)
        if img is None:
            return None, 0.0
        
        h, w = img.shape[:2]
        # Top region for card name
        region = img[int(h*0.02):int(h*0.08), int(w*0.05):int(w*0.80)]
        
        results = reader.readtext(region, detail=1)
        
        if results:
            # Take highest confidence result
            best = max(results, key=lambda x: x[2])
            text = best[1].strip()
            conf = best[2] * 100
            
            if len(text) >= 3:
                return text, conf
        
        return None, 0.0
        
    except Exception as e:
        logging.error(f"EasyOCR GPU name error: {e}")
        return None, 0.0


def extract_card_name_cpu(img_path: str) -> Tuple[Optional[str], float]:
    """Extract card name using Tesseract (fallback)"""
    try:
        img = cv2.imread(img_path)
        if img is None:
            return None, 0.0
        
        h, w = img.shape[:2]
        region = img[int(h*0.02):int(h*0.08), int(w*0.05):int(w*0.80)]
        region = cv2.resize(region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        text = pytesseract.image_to_string(region, config='--psm 7').strip()
        
        if text and len(text) >= 3:
            return text, 85.0
        
        return None, 0.0
        
    except Exception as e:
        logging.error(f"Tesseract name error: {e}")
        return None, 0.0


def ocr_pipeline(img_path: str) -> Dict:
    """
    Complete OCR pipeline with GPU acceleration + CPU fallback
    
    Returns:
        {
            'set_code': str or None,
            'collector_number': str or None,
            'card_name': str or None,
            'set_confidence': float,
            'name_confidence': float,
            'overall_confidence': float,
            'approved': bool,
            'method': 'gpu' or 'cpu'
        }
    """
    method = 'unknown'
    
    # Try GPU first
    if GPU_AVAILABLE:
        set_code, coll_num, set_conf = extract_set_collector_gpu(img_path)
        card_name, name_conf = extract_card_name_gpu(img_path)
        method = 'gpu'
    # Fallback to CPU
    elif TESSERACT_AVAILABLE:
        set_code, coll_num, set_conf = extract_set_collector_cpu(img_path)
        card_name, name_conf = extract_card_name_cpu(img_path)
        method = 'cpu'
    else:
        return {
            'error': 'No OCR engine available',
            'set_code': None,
            'collector_number': None,
            'card_name': None,
            'set_confidence': 0.0,
            'name_confidence': 0.0,
            'overall_confidence': 0.0,
            'approved': False,
            'method': 'none'
        }
    
    # Calculate overall confidence
    if set_conf > 0 and name_conf > 0:
        overall = (set_conf + name_conf) / 2
    else:
        overall = max(set_conf, name_conf)
    
    return {
        'set_code': set_code,
        'collector_number': coll_num,
        'card_name': card_name,
        'set_confidence': round(set_conf, 2),
        'name_confidence': round(name_conf, 2),
        'overall_confidence': round(overall, 2),
        'approved': overall >= 95.0,
        'method': method
    }


# Main execution for testing
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 snarf_ocr_enhanced.py <image_path>")
        sys.exit(1)
    
    img_path = sys.argv[1]
    result = ocr_pipeline(img_path)
    
    print("="*60)
    print("SNARF ENHANCED OCR RESULT")
    print("="*60)
    for key, value in result.items():
        print(f"{key:20s}: {value}")
    print("="*60)
