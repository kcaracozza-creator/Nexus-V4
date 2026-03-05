#!/usr/bin/env python3
"""
AI Card Recognition System v2.0
Clean rebuild with OCR, fuzzy matching, and template support
"""

import cv2
import numpy as np
import os
import json
import re
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher
from collections import defaultdict

# Try to import optional dependencies
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    print("WARNING: pytesseract not available - OCR disabled")

try:
    from PIL import Image, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNING: PIL not available - image enhancement limited")

try:
    from fuzzywuzzy import fuzz, process
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False
    print("WARNING: fuzzywuzzy not available - using basic matching")

# Import learning system
try:
    from recognition_learning_system import RecognitionLearningSystem
    LEARNING_SYSTEM_AVAILABLE = True
except ImportError:
    LEARNING_SYSTEM_AVAILABLE = False
    print("INFO: Learning system not available - corrections won't improve AI")

# Import similar card detector
try:
    from similar_card_detector import SimilarCardDetector
    SIMILAR_DETECTOR_AVAILABLE = True
except ImportError:
    SIMILAR_DETECTOR_AVAILABLE = False
    print("INFO: Similar card detector not available")


class MTGCardRecognizer:
    """
    Magic: The Gathering Card Recognition System
    
    Features:
    - OCR-based text extraction
    - Fuzzy matching against card database
    - Image preprocessing and enhancement
    - Multi-method recognition with confidence scoring
    """
    
    def __init__(self, master_file_path: str, cache_dir: str = "E:/MTTGG/recognition_cache"):
        """
        Initialize card recognizer
        
        Args:
            master_file_path: Path to Master File.csv with card data
            cache_dir: Directory for caching recognition data
        """
        self.master_file_path = master_file_path
        self.cache_dir = cache_dir
        self.card_database = {}
        self.card_names_list = []
        self.recognition_stats = defaultdict(int)
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize learning system
        self.learning_system = None
        if LEARNING_SYSTEM_AVAILABLE:
            corrections_file = os.path.join(cache_dir, "recognition_corrections.json")
            self.learning_system = RecognitionLearningSystem(corrections_file)
            print(f"[OK] Learning system initialized")
        
        # Initialize similar card detector
        self.similar_detector = None
        
        # Load card database
        self.load_card_database()
        
        # Initialize similar detector after database is loaded
        if SIMILAR_DETECTOR_AVAILABLE and self.card_database:
            self.similar_detector = SimilarCardDetector(self.card_database)
            print(f"[OK] Similar card detector initialized")
        
        print(f"[OK] MTG Card Recognizer initialized")
        print(f"   Loaded {len(self.card_database)} unique cards")
        print(f"   OCR: {'Enabled' if PYTESSERACT_AVAILABLE else 'Disabled'}")
        print(f"   Fuzzy Match: {'Enabled' if FUZZYWUZZY_AVAILABLE else 'Basic'}")
        print(f"   Learning: {'Enabled' if self.learning_system else 'Disabled'}")
        print(f"   Variant Detection: {'Enabled' if self.similar_detector else 'Disabled'}")
    
    def load_card_database(self):
        """Load card names and data from Master File"""
        try:
            import csv
            with open(self.master_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('name', '').strip()
                    if name:
                        self.card_database[name.lower()] = {
                            'name': name,
                            'type': row.get('type', ''),
                            'colors': row.get('colors', ''),
                            'manaCost': row.get('manaCost', '')
                        }
                        self.card_names_list.append(name)
            
            print(f"[OK] Loaded {len(self.card_database)} cards from Master File")
        except FileNotFoundError:
            print(f"WARNING: Master File not found: {self.master_file_path}")
            print("   Using demo card database")
            self._load_demo_database()
    
    def _load_demo_database(self):
        """Load demo cards for testing without Master File"""
        demo_cards = [
            "Lightning Bolt", "Dark Ritual", "Counterspell", "Giant Growth",
            "Swords to Plowshares", "Black Lotus", "Ancestral Recall",
            "Sol Ring", "Mana Crypt", "Force of Will", "Demonic Tutor",
            "Path to Exile", "Fatal Push", "Brainstorm", "Ponder",
            "Thoughtseize", "Tarmogoyf", "Snapcaster Mage", "Jace, the Mind Sculptor"
        ]
        for card in demo_cards:
            self.card_database[card.lower()] = {
                'name': card,
                'type': 'Unknown',
                'colors': '',
                'manaCost': ''
            }
            self.card_names_list.append(card)
    
    def recognize_card(self, image, method='auto') -> Dict:
        """
        Recognize card from image
        
        Args:
            image: OpenCV image (numpy array) or path to image file
            method: 'ocr', 'template', 'hybrid', or 'auto'
        
        Returns:
            Dictionary with:
            - card_name: Matched card name
            - confidence: Confidence score (0.0-1.0)
            - method: Recognition method used
            - extracted_text: Raw OCR text (if applicable)
            - matches: Top 5 alternative matches
        """
        start_time = datetime.now()
        
        # Load image if path provided
        if isinstance(image, str):
            image = cv2.imread(image)
            if image is None:
                return self._error_result("Failed to load image")
        
        # Validate image
        if image is None or image.size == 0:
            return self._error_result("Invalid image")
        
        # Auto-select best method
        if method == 'auto':
            method = 'ocr' if PYTESSERACT_AVAILABLE else 'template'
        
        # Run recognition
        if method == 'ocr':
            result = self._recognize_ocr(image)
        elif method == 'template':
            result = self._recognize_template(image)
        elif method == 'hybrid':
            result = self._recognize_hybrid(image)
        else:
            return self._error_result(f"Unknown method: {method}")
        
        # Add metadata
        result['method'] = method
        result['processing_time'] = (datetime.now() - start_time).total_seconds()
        result['timestamp'] = datetime.now().isoformat()
        
        # Update stats
        self.recognition_stats['total_recognitions'] += 1
        self.recognition_stats[f'method_{method}'] += 1
        if result['confidence'] > 0.7:
            self.recognition_stats['high_confidence'] += 1
        
        return result
    
    def _recognize_ocr(self, image) -> Dict:
        """Recognize card using OCR text extraction"""
        if not PYTESSERACT_AVAILABLE:
            return self._error_result("OCR not available (pytesseract not installed)")
        
        try:
            # Preprocess image for OCR
            processed = self._preprocess_for_ocr(image)
            
            # Extract text
            config = '--psm 6 --oem 3'  # Assume uniform text block
            extracted_text = pytesseract.image_to_string(processed, config=config)
            
            # Clean and parse text
            cleaned_text = self._clean_ocr_text(extracted_text)
            
            # Find best match
            card_name, confidence, matches = self._find_best_match(cleaned_text)
            
            return {
                'card_name': card_name,
                'confidence': confidence,
                'extracted_text': extracted_text,
                'cleaned_text': cleaned_text,
                'matches': matches
            }
        
        except Exception as e:
            return self._error_result(f"OCR error: {e}")
    
    def _recognize_template(self, image) -> Dict:
        """Recognize card using visual template matching"""
        # This is a placeholder - full template matching would require
        # a database of card images which is large (~100GB for all cards)
        # For production, use OCR or external API (Scryfall image recognition)
        
        return self._error_result("Template matching not yet implemented - use OCR method")
    
    def _recognize_hybrid(self, image) -> Dict:
        """Combine multiple recognition methods"""
        results = []
        
        # Try OCR
        if PYTESSERACT_AVAILABLE:
            ocr_result = self._recognize_ocr(image)
            if ocr_result['confidence'] > 0.0:
                results.append(('ocr', ocr_result))
        
        # Try template (when implemented)
        # template_result = self._recognize_template(image)
        # results.append(('template', template_result))
        
        # Combine results (weighted average)
        if not results:
            return self._error_result("No recognition methods available")
        
        # For now, just return best result
        best_method, best_result = max(results, key=lambda x: x[1]['confidence'])
        best_result['method'] = f'hybrid_{best_method}'
        return best_result
    
    def _preprocess_for_ocr(self, image):
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Resize if too small (OCR works better on larger images)
        height, width = gray.shape
        if height < 500:
            scale = 800 / height
            new_width = int(width * scale)
            gray = cv2.resize(gray, (new_width, 800), interpolation=cv2.INTER_CUBIC)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
        
        # Sharpen
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        # Threshold
        _, binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def _clean_ocr_text(self, text: str) -> str:
        """Clean OCR text output"""
        # Remove special characters except spaces and apostrophes
        cleaned = re.sub(r"[^a-zA-Z0-9\s',\-]", '', text)
        
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Remove common OCR errors
        cleaned = cleaned.replace('|', 'I')
        cleaned = cleaned.replace('0', 'O')  # Context-dependent but helps
        
        # Apply learned corrections if available
        if self.learning_system:
            cleaned = self.learning_system.apply_learned_corrections(cleaned)
        
        return cleaned.strip()
    
    def _find_best_match(self, text: str) -> Tuple[str, float, List[Dict]]:
        """
        Find best matching card name from extracted text
        
        Returns:
            (card_name, confidence, top_5_matches)
        """
        if not text:
            return "Unknown", 0.0, []
        
        text_lower = text.lower()
        
        # Method 1: Exact substring match
        for card_name in self.card_names_list:
            if card_name.lower() in text_lower or text_lower in card_name.lower():
                return card_name, 0.95, self._get_alternatives(card_name)
        
        # Method 2: Fuzzy matching
        if FUZZYWUZZY_AVAILABLE:
            # Use fuzzywuzzy for better matching
            matches = process.extract(text, self.card_names_list, limit=5)
            if matches and matches[0][1] > 70:  # Score > 70
                best_match = matches[0][0]
                confidence = matches[0][1] / 100.0
                alternatives = [{'name': m[0], 'score': m[1]/100.0} for m in matches]
                return best_match, confidence, alternatives
        else:
            # Fallback to basic SequenceMatcher
            best_ratio = 0
            best_match = "Unknown"
            
            for card_name in self.card_names_list:
                ratio = SequenceMatcher(None, text_lower, card_name.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = card_name
            
            if best_ratio > 0.6:
                return best_match, best_ratio, self._get_alternatives(best_match)
        
        return "Unknown", 0.0, []
    
    def _get_alternatives(self, card_name: str, count: int = 5) -> List[Dict]:
        """Get alternative card matches"""
        if not FUZZYWUZZY_AVAILABLE:
            return [{'name': card_name, 'score': 1.0}]
        
        matches = process.extract(card_name, self.card_names_list, limit=count)
        return [{'name': m[0], 'score': m[1]/100.0} for m in matches]
    
    def _error_result(self, error_message: str) -> Dict:
        """Return error result"""
        return {
            'card_name': 'Unknown',
            'confidence': 0.0,
            'error': error_message,
            'extracted_text': '',
            'matches': []
        }
    
    def batch_recognize(self, image_paths: List[str]) -> List[Dict]:
        """Recognize multiple cards"""
        results = []
        for path in image_paths:
            result = self.recognize_card(path)
            results.append(result)
        return results
    
    def get_statistics(self) -> Dict:
        """Get recognition statistics"""
        return dict(self.recognition_stats)
    
    def save_recognition_cache(self, result: Dict, image_path: str):
        """Save recognition result to cache"""
        cache_file = os.path.join(self.cache_dir, 'recognition_cache.json')
        
        cache_data = {
            'image_path': image_path,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Load existing cache
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
            else:
                cache = []
            
            # Add new entry
            cache.append(cache_data)
            
            # Keep only last 1000 entries
            cache = cache[-1000:]
            
            # Save
            with open(cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
        
        except Exception as e:
            print(f"WARNING: Failed to save cache: {e}")


def test_recognition_system():
    """Test the recognition system"""
    print("\n🧪 TESTING MTG CARD RECOGNITION SYSTEM\n")
    print("=" * 60)
    
    # Initialize recognizer
    master_file = r"E:\Downloads\Master File.csv"
    recognizer = MTGCardRecognizer(master_file)
    
    print(f"\n📊 System Status:")
    print(f"   Cards loaded: {len(recognizer.card_database)}")
    print(f"   OCR available: {PYTESSERACT_AVAILABLE}")
    print(f"   Fuzzy matching: {FUZZYWUZZY_AVAILABLE}")
    
    # Test text matching
    print(f"\nTesting text matching...")
    test_texts = [
        "Lightning Bolt",
        "lighning bolt",  # Typo
        "dark ritual",
        "counterspel",  # Missing letter
        "Black Lotus",
        "ancestral recal"
    ]
    
    for text in test_texts:
        card_name, confidence, matches = recognizer._find_best_match(text)
        print(f"   '{text}' → '{card_name}' (confidence: {confidence:.2f})")
    
    print(f"\n[OK] Recognition system test complete!")
    print(f"\n💡 Usage:")
    print(f"   recognizer = MTGCardRecognizer(master_file_path)")
    print(f"   result = recognizer.recognize_card(image_or_path)")
    print(f"   print(result['card_name'], result['confidence'])")
    
    return recognizer


if __name__ == "__main__":
    test_recognition_system()
