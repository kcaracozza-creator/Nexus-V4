"""
NEXUS Universal Card Scanner
============================
Patent-aligned 5-step scanning process supporting all TCG types.

5-STEP PROCESS:
    Step 1: Edge Detection - Crop card from background
    Step 2: Back Scan - Card type identification (MTG/Pokemon/Yu-Gi-Oh/etc.)
    Step 3: Art Validation - Art embedding → 512-dim vector (bulletproof ID)
    Step 4: OCR - Extract text for card identification
    Step 5: Cross-Reference - Combine OCR + Art vector → 99%+ accuracy

3 MODES:
    - Single TCG: User specifies type, skip Step 2 (fastest)
    - Bulk: Any TCG possible, Step 2 required
    - Pregrading: Full process + defect analysis (TBA)

Author: NEXUS Team
Copyright: Caracozza Enterprises - Patent Protected
"""

import cv2
import numpy as np
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ScanMode(Enum):
    """Scanning operation modes"""
    SINGLE_TCG = "single_tcg"    # User specifies type - skip back scan (fastest)
    BULK = "bulk"                # Mixed cards - back scan required
    PREGRADING = "pregrading"   # Full inspection + defect analysis


class CardType(Enum):
    """Supported trading card game types"""
    MTG = "mtg"
    POKEMON = "pokemon"
    YUGIOH = "yugioh"
    SPORTS = "sports"
    ONE_PIECE = "one_piece"
    LORCANA = "lorcana"
    FLESH_AND_BLOOD = "flesh_and_blood"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass
class ScanResult:
    """Complete scan result with all extracted data"""
    # Identity
    card_id: str = ""
    card_name: str = ""
    card_type: CardType = CardType.UNKNOWN
    
    # Set/Edition info
    set_code: str = ""
    set_name: str = ""
    collector_number: str = ""
    
    # Confidence scores
    art_confidence: float = 0.0
    ocr_confidence: float = 0.0
    overall_confidence: float = 0.0
    
    # Match details
    art_match_id: str = ""
    art_match_distance: float = 999.0
    ocr_matches: List[Dict] = field(default_factory=list)
    cross_reference_passed: bool = False
    
    # Metadata (from database lookup)
    metadata: Dict[str, Any] = field(default_factory=dict)
    all_printings: List[Dict] = field(default_factory=list)
    
    # Pricing
    price_usd: float = 0.0
    price_source: str = ""
    
    # Grading (for pregrading mode)
    grade_estimate: Optional[float] = None
    defects: List[Dict] = field(default_factory=list)
    
    # Debug/timing
    scan_time_ms: float = 0.0
    step_times: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Success flags
    success: bool = False
    needs_verification: bool = True


class UniversalScanner:
    """
    NEXUS Universal Card Scanner
    
    Implements the patent-protected 5-step scanning process
    with support for all major TCG types.
    """
    
    def __init__(
        self,
        models_dir: str = None,
        card_type_model: str = None,
        art_embedding_model: str = None,
        faiss_index_path: str = None,
        metadata_path: str = None,
        ocr_engine: str = "easyocr",
        confidence_threshold: float = 70.0,
    ):
        """
        Initialize Universal Scanner.
        
        Args:
            models_dir: Base directory for all models
            card_type_model: Path to card type classifier (.pt)
            art_embedding_model: Path to art embedding model (.pt)
            faiss_index_path: Path to FAISS index
            metadata_path: Path to card metadata JSON/DB
            ocr_engine: OCR engine to use ("easyocr", "tesseract", "paddleocr")
            confidence_threshold: Minimum confidence for auto-accept
        """
        self.models_dir = Path(models_dir) if models_dir else None
        self.confidence_threshold = confidence_threshold
        self.ocr_engine_name = ocr_engine
        
        # Model paths
        self.card_type_model_path = card_type_model
        self.art_embedding_model_path = art_embedding_model
        self.faiss_index_path = faiss_index_path
        self.metadata_path = metadata_path
        
        # Loaded components (lazy loading)
        self._card_type_classifier = None
        self._art_embedding_model = None
        self._faiss_index = None
        self._card_metadata = None
        self._ocr_reader = None
        
        # Stats
        self.scan_count = 0
        self.stats = {
            'total_scans': 0,
            'successful_scans': 0,
            'failed_scans': 0,
            'by_mode': {mode.value: 0 for mode in ScanMode},
            'by_type': {ct.value: 0 for ct in CardType},
            'avg_scan_time_ms': 0.0,
        }
        
        logger.info("UniversalScanner initialized")
    
    # =========================================================================
    # MAIN SCAN METHOD
    # =========================================================================
    
    def scan(
        self,
        front_image: np.ndarray,
        back_image: np.ndarray = None,
        mode: ScanMode = ScanMode.BULK,
        card_type: CardType = None,
    ) -> ScanResult:
        """
        Scan a card using the 5-step process.
        
        Args:
            front_image: Front of card (numpy array, BGR)
            back_image: Back of card (numpy array, BGR) - required for BULK mode
            mode: Scanning mode (SINGLE_TCG, BULK, PREGRADING)
            card_type: Card type (required for SINGLE_TCG mode)
            
        Returns:
            ScanResult with all extracted data
        """
        start_time = time.time()
        self.scan_count += 1
        self.stats['total_scans'] += 1
        self.stats['by_mode'][mode.value] += 1
        
        result = ScanResult()
        
        # Validate inputs
        if mode == ScanMode.SINGLE_TCG and card_type is None:
            result.errors.append("SINGLE_TCG mode requires card_type parameter")
            return result
            
        if mode in [ScanMode.BULK, ScanMode.PREGRADING] and back_image is None:
            result.errors.append(f"{mode.value} mode requires back_image")
            return result
        
        try:
            # =================================================================
            # STEP 1: EDGE DETECTION (Crop card from background)
            # =================================================================
            step1_start = time.time()
            
            cropped_front, crop_success = self._step1_edge_detection(front_image)
            
            result.step_times['step1_edge_detection'] = (time.time() - step1_start) * 1000
            
            if not crop_success:
                result.warnings.append("Edge detection failed, using original image")
                cropped_front = front_image
            
            # =================================================================
            # STEP 2: BACK SCAN (Card type identification)
            # =================================================================
            step2_start = time.time()
            
            if mode == ScanMode.SINGLE_TCG:
                # Skip back scan - user provided type
                result.card_type = card_type
                result.step_times['step2_back_scan'] = 0.0
                logger.debug(f"Step 2 SKIPPED - User specified: {card_type.value}")
            else:
                # Perform back scan for type detection
                detected_type, type_confidence = self._step2_back_scan(back_image)
                result.card_type = detected_type
                result.step_times['step2_back_scan'] = (time.time() - step2_start) * 1000
                logger.debug(f"Step 2 - Detected type: {detected_type.value} ({type_confidence:.1f}%)")
            
            self.stats['by_type'][result.card_type.value] += 1
            
            # =================================================================
            # STEP 3: ART VALIDATION (Embedding for bulletproof ID)
            # =================================================================
            step3_start = time.time()
            
            art_embedding, art_region = self._step3_art_validation(
                cropped_front, 
                result.card_type
            )
            
            result.step_times['step3_art_validation'] = (time.time() - step3_start) * 1000
            
            if art_embedding is None:
                result.warnings.append("Art embedding extraction failed")
            
            # =================================================================
            # STEP 4: OCR (Text extraction for card identification)
            # =================================================================
            step4_start = time.time()
            
            ocr_results = self._step4_ocr(cropped_front, result.card_type)
            
            result.step_times['step4_ocr'] = (time.time() - step4_start) * 1000
            result.ocr_matches = ocr_results.get('matches', [])
            result.ocr_confidence = ocr_results.get('confidence', 0.0)
            
            # =================================================================
            # STEP 5: CROSS-REFERENCE (Combine OCR + Art → 99%+ accuracy)
            # =================================================================
            step5_start = time.time()
            
            final_match = self._step5_cross_reference(
                art_embedding=art_embedding,
                ocr_results=ocr_results,
                card_type=result.card_type
            )
            
            result.step_times['step5_cross_reference'] = (time.time() - step5_start) * 1000
            
            # Populate result from final match
            if final_match:
                result.card_id = final_match.get('card_id', '')
                result.card_name = final_match.get('name', '')
                result.set_code = final_match.get('set_code', '')
                result.set_name = final_match.get('set_name', '')
                result.collector_number = final_match.get('collector_number', '')
                result.art_confidence = final_match.get('art_confidence', 0.0)
                result.art_match_id = final_match.get('art_match_id', '')
                result.art_match_distance = final_match.get('art_distance', 999.0)
                result.overall_confidence = final_match.get('overall_confidence', 0.0)
                result.cross_reference_passed = final_match.get('cross_ref_passed', False)
                result.metadata = final_match.get('metadata', {})
                result.all_printings = final_match.get('all_printings', [])
                result.price_usd = final_match.get('price_usd', 0.0)
                result.price_source = final_match.get('price_source', '')
            
            # =================================================================
            # PREGRADING MODE: Additional defect analysis
            # =================================================================
            if mode == ScanMode.PREGRADING:
                grade_start = time.time()
                
                grade_result = self._analyze_for_grading(cropped_front, art_region)
                
                result.grade_estimate = grade_result.get('grade_estimate')
                result.defects = grade_result.get('defects', [])
                result.step_times['pregrading_analysis'] = (time.time() - grade_start) * 1000
            
            # =================================================================
            # FINALIZE RESULT
            # =================================================================
            result.success = result.overall_confidence >= self.confidence_threshold
            result.needs_verification = not result.success
            
            if result.success:
                self.stats['successful_scans'] += 1
            else:
                self.stats['failed_scans'] += 1
                
        except Exception as e:
            logger.exception(f"Scan failed: {e}")
            result.errors.append(str(e))
            self.stats['failed_scans'] += 1
        
        # Calculate total scan time
        result.scan_time_ms = (time.time() - start_time) * 1000
        
        # Update running average
        n = self.stats['total_scans']
        old_avg = self.stats['avg_scan_time_ms']
        self.stats['avg_scan_time_ms'] = old_avg + (result.scan_time_ms - old_avg) / n
        
        logger.info(
            f"Scan #{self.scan_count} complete: {result.card_name or 'UNKNOWN'} "
            f"({result.overall_confidence:.1f}%) in {result.scan_time_ms:.0f}ms"
        )
        
        return result
    
    # =========================================================================
    # STEP IMPLEMENTATIONS
    # =========================================================================
    
    def _step1_edge_detection(
        self, 
        image: np.ndarray
    ) -> Tuple[np.ndarray, bool]:
        """
        STEP 1: Edge Detection - Crop card from background.
        
        Returns:
            (cropped_image, success)
        """
        logger.debug("Step 1: Edge Detection")
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Edge detection
            edges = cv2.Canny(blurred, 50, 150)
            
            # Dilate to connect edges
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=2)
            
            # Find contours
            contours, _ = cv2.findContours(
                edges, 
                cv2.RETR_EXTERNAL, 
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            if not contours:
                return image, False
            
            # Find largest rectangular contour (the card)
            best_contour = None
            best_area = 0
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 1000:  # Too small
                    continue
                    
                # Approximate to polygon
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                
                # Card should be roughly rectangular (4 corners)
                if len(approx) >= 4 and area > best_area:
                    best_area = area
                    best_contour = approx
            
            if best_contour is None:
                return image, False
            
            # Get bounding rectangle and crop
            x, y, w, h = cv2.boundingRect(best_contour)
            
            # Add small padding
            pad = 5
            x = max(0, x - pad)
            y = max(0, y - pad)
            w = min(image.shape[1] - x, w + 2 * pad)
            h = min(image.shape[0] - y, h + 2 * pad)
            
            cropped = image[y:y+h, x:x+w]
            
            # Validate aspect ratio (cards are ~2.5x3.5 inches = 0.71 ratio)
            aspect = w / h if h > 0 else 0
            expected_aspect = 2.5 / 3.5  # ~0.714
            
            if 0.5 < aspect < 0.9:  # Portrait orientation
                return cropped, True
            elif 1.1 < aspect < 2.0:  # Landscape - rotate
                cropped = cv2.rotate(cropped, cv2.ROTATE_90_CLOCKWISE)
                return cropped, True
            
            return cropped, True
            
        except Exception as e:
            logger.warning(f"Edge detection error: {e}")
            return image, False
    
    def _step2_back_scan(
        self, 
        back_image: np.ndarray
    ) -> Tuple[CardType, float]:
        """
        STEP 2: Back Scan - Identify card type from back of card.
        
        Returns:
            (CardType, confidence)
        """
        logger.debug("Step 2: Back Scan (Card Type Detection)")
        
        # Lazy load card type classifier
        if self._card_type_classifier is None:
            self._load_card_type_classifier()
        
        if self._card_type_classifier is None:
            logger.warning("Card type classifier not available, defaulting to MTG")
            return CardType.MTG, 50.0
        
        try:
            # Preprocess image for model
            img = cv2.cvtColor(back_image, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (224, 224))
            img = img.astype(np.float32) / 255.0
            
            # Normalize
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            img = (img - mean) / std
            
            # To tensor format: (1, 3, 224, 224)
            img = np.transpose(img, (2, 0, 1))
            img = np.expand_dims(img, 0)
            
            # Run inference
            import torch
            with torch.no_grad():
                tensor = torch.from_numpy(img).float()
                output = self._card_type_classifier(tensor)
                probs = torch.softmax(output, dim=1)
                confidence, predicted = torch.max(probs, 1)
            
            # Map index to CardType
            class_names = [
                'flesh_and_blood', 'lorcana', 'mtg', 'one_piece', 
                'pokemon', 'sports', 'yugioh'
            ]
            
            pred_idx = predicted.item()
            pred_conf = confidence.item() * 100
            
            if pred_idx < len(class_names):
                type_name = class_names[pred_idx]
                card_type = CardType(type_name)
            else:
                card_type = CardType.OTHER
            
            return card_type, pred_conf
            
        except Exception as e:
            logger.warning(f"Card type detection error: {e}")
            return CardType.UNKNOWN, 0.0
    
    def _step3_art_validation(
        self, 
        card_image: np.ndarray,
        card_type: CardType
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        STEP 3: Art Validation - Extract art region and generate embedding.
        
        Returns:
            (embedding_vector, art_region_image)
        """
        logger.debug("Step 3: Art Validation (Embedding)")
        
        # Lazy load art embedding model
        if self._art_embedding_model is None:
            self._load_art_embedding_model()
        
        if self._art_embedding_model is None:
            logger.warning("Art embedding model not available")
            return None, None
        
        try:
            h, w = card_image.shape[:2]
            
            # Extract art region based on card type
            # Different TCGs have different art placements
            if card_type in [CardType.MTG, CardType.LORCANA]:
                # MTG/Lorcana: Art is roughly top 40-65% of card, centered
                art_top = int(h * 0.12)
                art_bottom = int(h * 0.58)
                art_left = int(w * 0.08)
                art_right = int(w * 0.92)
                
            elif card_type == CardType.POKEMON:
                # Pokemon: Art is roughly top 20-55%
                art_top = int(h * 0.15)
                art_bottom = int(h * 0.55)
                art_left = int(w * 0.10)
                art_right = int(w * 0.90)
                
            elif card_type == CardType.YUGIOH:
                # Yu-Gi-Oh: Art is roughly top 25-55%
                art_top = int(h * 0.20)
                art_bottom = int(h * 0.55)
                art_left = int(w * 0.12)
                art_right = int(w * 0.88)
                
            else:
                # Default: Middle 50% of card
                art_top = int(h * 0.15)
                art_bottom = int(h * 0.60)
                art_left = int(w * 0.10)
                art_right = int(w * 0.90)
            
            # Crop art region
            art_region = card_image[art_top:art_bottom, art_left:art_right]
            
            # Preprocess for embedding model
            art_rgb = cv2.cvtColor(art_region, cv2.COLOR_BGR2RGB)
            art_resized = cv2.resize(art_rgb, (224, 224))
            art_normalized = art_resized.astype(np.float32) / 255.0
            
            # ImageNet normalization
            mean = np.array([0.485, 0.456, 0.406])
            std = np.array([0.229, 0.224, 0.225])
            art_normalized = (art_normalized - mean) / std
            
            # To tensor: (1, 3, 224, 224)
            art_tensor = np.transpose(art_normalized, (2, 0, 1))
            art_tensor = np.expand_dims(art_tensor, 0)
            
            # Generate embedding
            import torch
            with torch.no_grad():
                tensor = torch.from_numpy(art_tensor).float()
                embedding = self._art_embedding_model(tensor)
                embedding = embedding.numpy().flatten()
            
            # Normalize embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            return embedding, art_region
            
        except Exception as e:
            logger.warning(f"Art embedding error: {e}")
            return None, None
    
    def _step4_ocr(
        self, 
        card_image: np.ndarray,
        card_type: CardType
    ) -> Dict[str, Any]:
        """
        STEP 4: OCR - Extract text from card for identification.
        
        Returns:
            Dict with 'text', 'matches', 'confidence'
        """
        logger.debug("Step 4: OCR Text Extraction")
        
        # Lazy load OCR engine
        if self._ocr_reader is None:
            self._load_ocr_engine()
        
        result = {
            'text': '',
            'matches': [],
            'confidence': 0.0,
            'raw_results': []
        }
        
        if self._ocr_reader is None:
            logger.warning("OCR engine not available")
            return result
        
        try:
            h, w = card_image.shape[:2]
            
            # Extract text regions based on card type
            regions_to_scan = []
            
            if card_type in [CardType.MTG, CardType.LORCANA]:
                # Name: Top 12%
                regions_to_scan.append(('name', card_image[0:int(h*0.12), :]))
                # Type line: ~58-65%
                regions_to_scan.append(('type', card_image[int(h*0.58):int(h*0.65), :]))
                # Collector: Bottom 8%
                regions_to_scan.append(('collector', card_image[int(h*0.92):, :]))
                
            elif card_type == CardType.POKEMON:
                # Name: Top 15%
                regions_to_scan.append(('name', card_image[0:int(h*0.15), :]))
                # HP: Top right
                regions_to_scan.append(('hp', card_image[0:int(h*0.12), int(w*0.7):]))
                # Collector: Bottom
                regions_to_scan.append(('collector', card_image[int(h*0.90):, :]))
                
            elif card_type == CardType.YUGIOH:
                # Name: Top 15%
                regions_to_scan.append(('name', card_image[0:int(h*0.15), :]))
                # ATK/DEF: Bottom right (for monsters)
                regions_to_scan.append(('stats', card_image[int(h*0.88):, int(w*0.50):]))
                # Card ID: Bottom left corner
                regions_to_scan.append(('id', card_image[int(h*0.92):, 0:int(w*0.40)]))
                # Set code: Bottom center (above ID)
                regions_to_scan.append(('set', card_image[int(h*0.85):int(h*0.92), int(w*0.20):int(w*0.80)]))
                
            else:
                # Default: Just scan top 20% for name
                regions_to_scan.append(('name', card_image[0:int(h*0.20), :]))
            
            # OCR each region
            all_text = []
            
            for region_name, region_img in regions_to_scan:
                # Preprocess for OCR
                gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
                
                # Enhance contrast
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                
                # Scale up for better OCR
                scaled = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                
                # Run OCR
                ocr_results = self._ocr_reader.readtext(scaled, detail=1)
                
                for bbox, text, conf in ocr_results:
                    if conf > 0.3:  # Min confidence threshold
                        all_text.append(text)
                        result['raw_results'].append({
                            'region': region_name,
                            'text': text,
                            'confidence': conf
                        })
            
            result['text'] = ' '.join(all_text)
            
            # Calculate overall OCR confidence
            if result['raw_results']:
                confidences = [r['confidence'] for r in result['raw_results']]
                result['confidence'] = sum(confidences) / len(confidences) * 100
            
            return result
            
        except Exception as e:
            logger.warning(f"OCR error: {e}")
            return result
    
    def _step5_cross_reference(
        self,
        art_embedding: Optional[np.ndarray],
        ocr_results: Dict[str, Any],
        card_type: CardType
    ) -> Optional[Dict[str, Any]]:
        """
        STEP 5: Cross-Reference - Combine OCR + Art vector for 99%+ accuracy.
        
        Returns:
            Dict with matched card info or None
        """
        logger.debug("Step 5: Cross-Reference (OCR + Art)")
        
        result = None
        art_match = None
        ocr_match = None
        
        # Lazy load FAISS index and metadata
        if self._faiss_index is None:
            self._load_faiss_index()
        if self._card_metadata is None:
            self._load_card_metadata()
        
        # === Art-based matching (Primary - Bulletproof) ===
        if art_embedding is not None and self._faiss_index is not None:
            try:
                import faiss
                
                # Search FAISS index
                embedding = art_embedding.reshape(1, -1).astype(np.float32)
                distances, indices = self._faiss_index.search(embedding, k=5)
                
                if indices[0][0] != -1:
                    best_idx = indices[0][0]
                    best_dist = distances[0][0]
                    
                    # Get card ID from index
                    if hasattr(self, '_card_ids') and best_idx < len(self._card_ids):
                        art_match = {
                            'card_id': self._card_ids[best_idx],
                            'distance': float(best_dist),
                            'confidence': max(0, 100 - best_dist * 50)  # Convert distance to confidence
                        }
                        
            except Exception as e:
                logger.warning(f"FAISS search error: {e}")
        
        # === OCR-based matching (Secondary) ===
        if ocr_results.get('text') and self._card_metadata:
            try:
                ocr_text = ocr_results['text'].lower()
                
                # Simple text matching against card names
                best_match = None
                best_score = 0
                
                for card_id, card_info in self._card_metadata.items():
                    card_name = card_info.get('name', '').lower()
                    
                    # Check if card type matches
                    card_game = card_info.get('game', 'mtg')
                    if card_type.value != card_game:
                        continue
                    
                    # Simple fuzzy match
                    if card_name in ocr_text or ocr_text in card_name:
                        score = len(card_name)
                        if score > best_score:
                            best_score = score
                            best_match = {
                                'card_id': card_id,
                                'name': card_info.get('name'),
                                'confidence': min(90, 50 + score)
                            }
                
                ocr_match = best_match
                
            except Exception as e:
                logger.warning(f"OCR matching error: {e}")
        
        # === Cross-reference: Combine both methods ===
        cross_ref_passed = False
        
        if art_match and ocr_match:
            # Both methods found matches - check if they agree
            if art_match['card_id'] == ocr_match['card_id']:
                # Perfect agreement - high confidence
                cross_ref_passed = True
                overall_confidence = (art_match['confidence'] + ocr_match['confidence']) / 2 + 10
            else:
                # Disagreement - trust art embedding more (it's bulletproof)
                overall_confidence = art_match['confidence'] * 0.7 + ocr_match['confidence'] * 0.3
        elif art_match:
            # Art only - still pretty reliable
            overall_confidence = art_match['confidence'] * 0.9
        elif ocr_match:
            # OCR only - less reliable
            overall_confidence = ocr_match['confidence'] * 0.7
        else:
            # No matches
            overall_confidence = 0.0
        
        # Build final result
        primary_match = art_match or ocr_match
        
        if primary_match:
            card_id = primary_match['card_id']
            
            # Look up full metadata
            metadata = {}
            all_printings = []
            
            if self._card_metadata and card_id in self._card_metadata:
                metadata = self._card_metadata[card_id]
                
                # Get all printings if available
                oracle_id = metadata.get('oracle_id')
                if oracle_id and hasattr(self, '_oracle_to_printings'):
                    all_printings = self._oracle_to_printings.get(oracle_id, [])
            
            result = {
                'card_id': card_id,
                'name': metadata.get('name', primary_match.get('name', '')),
                'set_code': metadata.get('set', ''),
                'set_name': metadata.get('set_name', ''),
                'collector_number': metadata.get('collector_number', ''),
                'art_confidence': art_match['confidence'] if art_match else 0.0,
                'art_match_id': art_match['card_id'] if art_match else '',
                'art_distance': art_match['distance'] if art_match else 999.0,
                'ocr_confidence': ocr_match['confidence'] if ocr_match else 0.0,
                'overall_confidence': min(99.9, overall_confidence),
                'cross_ref_passed': cross_ref_passed,
                'metadata': metadata,
                'all_printings': all_printings,
                'price_usd': metadata.get('price_usd', 0.0),
                'price_source': metadata.get('price_source', ''),
            }
        
        return result
    
    def _analyze_for_grading(
        self, 
        card_image: np.ndarray,
        art_region: np.ndarray
    ) -> Dict[str, Any]:
        """
        PREGRADING: Analyze card for defects and estimate grade.
        
        TODO: Implement full grading analysis
        """
        logger.debug("Pregrading: Defect Analysis")
        
        # Placeholder - TBA
        return {
            'grade_estimate': None,
            'defects': [],
            'notes': 'Pregrading analysis not yet implemented'
        }
    
    # =========================================================================
    # MODEL LOADING (Lazy)
    # =========================================================================
    
    def _load_card_type_classifier(self):
        """Load card type classifier model"""
        if self.card_type_model_path is None:
            logger.warning("No card type model path specified")
            return
            
        try:
            import torch
            import torch.nn as nn
            from torchvision import models
            
            # Define model architecture (must match training)
            class CardTypeClassifier(nn.Module):
                def __init__(self, num_classes=7):
                    super().__init__()
                    self.backbone = models.mobilenet_v2(weights=None)
                    self.backbone.classifier = nn.Sequential(
                        nn.Dropout(0.2),
                        nn.Linear(1280, num_classes)
                    )
                
                def forward(self, x):
                    return self.backbone(x)
            
            model = CardTypeClassifier(num_classes=7)
            model.load_state_dict(torch.load(self.card_type_model_path, map_location='cpu'))
            model.eval()
            
            self._card_type_classifier = model
            logger.info(f"Loaded card type classifier from {self.card_type_model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load card type classifier: {e}")
    
    def _load_art_embedding_model(self):
        """Load art embedding model"""
        if self.art_embedding_model_path is None:
            logger.warning("No art embedding model path specified")
            return
            
        try:
            import torch
            import torch.nn as nn
            from torchvision import models
            
            # Define model architecture (must match training)
            class CardEmbeddingModel(nn.Module):
                def __init__(self, embedding_dim=512):
                    super().__init__()
                    mobilenet = models.mobilenet_v2(weights=None)
                    self.backbone = mobilenet.features
                    self.pool = nn.AdaptiveAvgPool2d(1)
                    self.embedding = nn.Sequential(
                        nn.Linear(1280, 1024),
                        nn.ReLU(),
                        nn.Dropout(0.3),
                        nn.Linear(1024, embedding_dim)
                    )
                
                def forward(self, x):
                    x = self.backbone(x)
                    x = self.pool(x)
                    x = x.view(x.size(0), -1)
                    x = self.embedding(x)
                    return x
            
            model = CardEmbeddingModel(embedding_dim=512)
            model.load_state_dict(torch.load(self.art_embedding_model_path, map_location='cpu'))
            model.eval()
            
            self._art_embedding_model = model
            logger.info(f"Loaded art embedding model from {self.art_embedding_model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load art embedding model: {e}")
    
    def _load_faiss_index(self):
        """Load FAISS index"""
        if self.faiss_index_path is None:
            logger.warning("No FAISS index path specified")
            return
            
        try:
            import faiss
            
            self._faiss_index = faiss.read_index(self.faiss_index_path)
            logger.info(f"Loaded FAISS index from {self.faiss_index_path}")
            
            # Try to load card IDs mapping
            ids_path = Path(self.faiss_index_path).parent / "card_ids.json"
            if ids_path.exists():
                import json
                with open(ids_path) as f:
                    self._card_ids = json.load(f)
                logger.info(f"Loaded {len(self._card_ids)} card IDs")
                
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
    
    def _load_card_metadata(self):
        """Load card metadata"""
        if self.metadata_path is None:
            logger.warning("No metadata path specified")
            return
            
        try:
            import json
            
            with open(self.metadata_path) as f:
                self._card_metadata = json.load(f)
            logger.info(f"Loaded metadata for {len(self._card_metadata)} cards")
            
            # Try to load oracle_to_printings
            printings_path = Path(self.metadata_path).parent / "oracle_to_printings.json"
            if printings_path.exists():
                with open(printings_path) as f:
                    self._oracle_to_printings = json.load(f)
                logger.info(f"Loaded oracle_to_printings mapping")
                
        except Exception as e:
            logger.error(f"Failed to load card metadata: {e}")
    
    def _load_ocr_engine(self):
        """Load OCR engine"""
        try:
            if self.ocr_engine_name == "easyocr":
                import easyocr
                self._ocr_reader = easyocr.Reader(['en'], gpu=False)
                logger.info("Loaded EasyOCR engine")
                
            elif self.ocr_engine_name == "tesseract":
                # Tesseract uses a different interface
                import pytesseract
                
                class TesseractWrapper:
                    def readtext(self, image, detail=1):
                        text = pytesseract.image_to_string(image)
                        return [([0,0,0,0], text, 0.8)]
                
                self._ocr_reader = TesseractWrapper()
                logger.info("Loaded Tesseract OCR engine")
                
            else:
                logger.warning(f"Unknown OCR engine: {self.ocr_engine_name}")
                
        except Exception as e:
            logger.error(f"Failed to load OCR engine: {e}")
    
    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================
    
    def scan_single(
        self, 
        front_image: np.ndarray, 
        card_type: CardType
    ) -> ScanResult:
        """
        Convenience method for Single TCG mode.
        Fastest scan - skips back scan.
        """
        return self.scan(
            front_image=front_image,
            back_image=None,
            mode=ScanMode.SINGLE_TCG,
            card_type=card_type
        )
    
    def scan_bulk(
        self, 
        front_image: np.ndarray, 
        back_image: np.ndarray
    ) -> ScanResult:
        """
        Convenience method for Bulk mode.
        Full scan including card type detection.
        """
        return self.scan(
            front_image=front_image,
            back_image=back_image,
            mode=ScanMode.BULK,
            card_type=None
        )
    
    def scan_pregrade(
        self, 
        front_image: np.ndarray, 
        back_image: np.ndarray
    ) -> ScanResult:
        """
        Convenience method for Pregrading mode.
        Full scan plus defect analysis.
        """
        return self.scan(
            front_image=front_image,
            back_image=back_image,
            mode=ScanMode.PREGRADING,
            card_type=None
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scanner statistics"""
        return self.stats.copy()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_scanner(
    models_dir: str = None,
    config: Dict[str, Any] = None
) -> UniversalScanner:
    """
    Factory function to create a configured UniversalScanner.
    
    Args:
        models_dir: Base directory containing all models
        config: Optional configuration dict
        
    Returns:
        Configured UniversalScanner instance
    """
    if models_dir is None:
        # Try default paths
        possible_paths = [
            Path(__file__).parent.parent.parent / "training" / "models",
            Path.home() / "training" / "models",
            Path("/home/nexus1/training/models"),
        ]
        
        for p in possible_paths:
            if p.exists():
                models_dir = str(p)
                break
    
    if models_dir:
        models_path = Path(models_dir)
        
        scanner = UniversalScanner(
            models_dir=models_dir,
            card_type_model=str(models_path / "card_type_classifier" / "card_type_classifier_best.pt"),
            art_embedding_model=str(models_path / "card_embedding_best.pt"),
            faiss_index_path=str(models_path / "faiss_index" / "faiss_index_flat.bin"),
            metadata_path=str(models_path.parent / "metadata" / "card_lookup.json"),
        )
    else:
        scanner = UniversalScanner()
    
    return scanner


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("NEXUS Universal Scanner - Test")
    print("=" * 60)
    print("\n5-Step Patent Process:")
    print("  1. Edge Detection - Crop card")
    print("  2. Back Scan - Card type ID")
    print("  3. Art Validation - Embedding (bulletproof)")
    print("  4. OCR - Text extraction")
    print("  5. Cross-Reference - 99%+ accuracy")
    print("\n3 Modes:")
    print("  - Single TCG: Skip step 2 (fastest)")
    print("  - Bulk: Full process")
    print("  - Pregrading: Full + defects (TBA)")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        # Test with provided image
        image_path = sys.argv[1]
        card_type = sys.argv[2] if len(sys.argv) > 2 else "mtg"
        
        print(f"\nTesting with: {image_path}")
        print(f"Card type: {card_type}")
        
        scanner = create_scanner()
        image = cv2.imread(image_path)
        
        if image is not None:
            result = scanner.scan_single(image, CardType(card_type))
            
            print(f"\nResult:")
            print(f"  Name: {result.card_name}")
            print(f"  Set: {result.set_code} ({result.set_name})")
            print(f"  Confidence: {result.overall_confidence:.1f}%")
            print(f"  Scan time: {result.scan_time_ms:.0f}ms")
            print(f"  Success: {result.success}")
        else:
            print(f"Error: Could not load image")
    else:
        print("\nUsage: python universal_scanner.py <image_path> [card_type]")
        print("  card_type: mtg, pokemon, yugioh, sports, etc.")
