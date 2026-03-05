"""
NEXUS Card Condition Assessment
Automated image-based condition analysis (1-10 scale).
Analyzes centering, corners, edges, and surface.

IMPORTANT: This is automated condition assessment only.
NEXUS does NOT perform professional grading (PSA, BGS, CGC, etc.).
Results are for informational use and do not constitute a professional grade.
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional
import json
from datetime import datetime
from pathlib import Path


CONDITION_ASSESSMENT_DISCLAIMER = (
    "NEXUS performs automated condition assessment only. "
    "This is NOT professional grading (PSA, BGS, CGC, etc.). "
    "For professional grading, submit to PSA, BGS, or CGC directly."
)


class CardGradingAnalyzer:
    """
    Automated condition assessment for trading cards (1-10 scale).
    NOT compatible with or equivalent to PSA/BGS/CGC professional grading.
    Results are machine-generated estimates for informational use only.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize grading analyzer
        
        Args:
            config_path: Path to grading configuration JSON
        """
        self.config = self._load_config(config_path)
        
        # Standard card dimensions (in pixels at 300 DPI scan)
        self.STANDARD_WIDTH = 750  # 2.5 inches @ 300 DPI
        self.STANDARD_HEIGHT = 1050  # 3.5 inches @ 300 DPI
        
        # Grading thresholds (percentage of perfection)
        self.GRADE_THRESHOLDS = {
            10: 99.5,  # Gem Mint
            9: 95.0,   # Mint
            8: 90.0,   # NM-MT
            7: 85.0,   # NM
            6: 80.0,   # EX-MT
            5: 75.0,   # EX
            4: 70.0,   # VG-EX
            3: 60.0,   # VG
            2: 50.0,   # Good
            1: 0.0     # Poor
        }
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load grading configuration"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Default configuration
        return {
            'centering_weight': 0.30,
            'corners_weight': 0.25,
            'edges_weight': 0.20,
            'surface_weight': 0.25,
            'min_card_area': 50000,  # Minimum pixels for valid card detection
            'corner_sample_size': 50,  # Pixels to sample at each corner
            'edge_sample_width': 20   # Pixels to sample along edges
        }
    
    def analyze_card(self, image: np.ndarray) -> Dict:
        """
        Complete card grading analysis
        
        Args:
            image: OpenCV image (BGR format) of card
            
        Returns:
            Dict containing:
                - overall_grade: 1-10 scale
                - centering_score: 0-100
                - corners_score: 0-100
                - edges_score: 0-100
                - surface_score: 0-100
                - sub_grades: dict of individual component grades
                - confidence: 0-1 (how confident the AI is)
                - timestamp: when analysis was performed
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'confidence': 0.0
        }
        
        # Detect card boundaries
        card_contour = self._detect_card_boundary(image)
        if card_contour is None:
            results['error'] = 'Card boundary not detected'
            results['overall_grade'] = 0
            return results
        
        # Analyze each grading component
        centering_score = self._analyze_centering(image, card_contour)
        corners_score = self._analyze_corners(image, card_contour)
        edges_score = self._analyze_edges(image, card_contour)
        surface_score = self._analyze_surface(image, card_contour)
        
        # Calculate weighted overall score
        overall_score = (
            centering_score * self.config['centering_weight'] +
            corners_score * self.config['corners_weight'] +
            edges_score * self.config['edges_weight'] +
            surface_score * self.config['surface_weight']
        )
        
        # Convert score to 1-10 grade
        overall_grade = self._score_to_grade(overall_score)
        
        # Calculate sub-grades
        sub_grades = {
            'centering': self._score_to_grade(centering_score),
            'corners': self._score_to_grade(corners_score),
            'edges': self._score_to_grade(edges_score),
            'surface': self._score_to_grade(surface_score)
        }
        
        # Confidence based on image quality and detection clarity
        confidence = self._calculate_confidence(image, card_contour)
        
        results.update({
            'overall_grade': overall_grade,
            'overall_score': round(overall_score, 2),
            'centering_score': round(centering_score, 2),
            'corners_score': round(corners_score, 2),
            'edges_score': round(edges_score, 2),
            'surface_score': round(surface_score, 2),
            'sub_grades': sub_grades,
            'confidence': round(confidence, 3),
            'grade_label': self._get_grade_label(overall_grade),
            'disclaimer': CONDITION_ASSESSMENT_DISCLAIMER
        })
        
        return results
    
    def _detect_card_boundary(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect card edges and return contour
        
        Args:
            image: Input image
            
        Returns:
            Contour points of card boundary, or None if not found
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Edge detection
        edges = cv2.Canny(blurred, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Find largest rectangular contour (likely the card)
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Verify it's large enough to be a card
        area = cv2.contourArea(largest_contour)
        if area < self.config['min_card_area']:
            return None
        
        # Approximate to rectangle
        epsilon = 0.02 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        # Should have 4 corners for a card
        if len(approx) == 4:
            return approx
        
        return largest_contour
    
    def _analyze_centering(self, image: np.ndarray, contour: np.ndarray) -> float:
        """
        Analyze card centering (front image position on card)
        
        Args:
            image: Card image
            contour: Card boundary contour
            
        Returns:
            Centering score 0-100 (100 = perfectly centered)
        """
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        
        # Expected center
        expected_center_x = w / 2
        expected_center_y = h / 2
        
        # Convert to grayscale for border detection
        gray = cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
        
        # Detect border (usually darker region around card image)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Find content area (non-border)
        content_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not content_contours:
            # No clear border detected, assume perfect centering
            return 100.0
        
        # Get largest content area
        content_contour = max(content_contours, key=cv2.contourArea)
        cx, cy, cw, ch = cv2.boundingRect(content_contour)
        
        # Actual center
        actual_center_x = cx + cw / 2
        actual_center_y = cy + ch / 2
        
        # Calculate offset percentages
        x_offset_pct = abs(actual_center_x - expected_center_x) / w * 100
        y_offset_pct = abs(actual_center_y - expected_center_y) / h * 100
        
        # Perfect centering = 0% offset
        # Allow up to 5% offset for Gem Mint (10)
        # PSA 10 standard: 60/40 or better (max 10% offset)
        max_offset = max(x_offset_pct, y_offset_pct)
        
        if max_offset <= 1.0:
            return 100.0  # Perfect
        elif max_offset <= 5.0:
            return 99.0   # Gem Mint range
        elif max_offset <= 10.0:
            return 95.0   # Mint range
        else:
            # Linear decay from 95 to 0 as offset increases
            score = max(0, 95 - (max_offset - 10) * 5)
            return score
    
    def _analyze_corners(self, image: np.ndarray, contour: np.ndarray) -> float:
        """
        Analyze corner sharpness and wear
        
        Args:
            image: Card image
            contour: Card boundary contour
            
        Returns:
            Corner score 0-100 (100 = sharp corners, no wear)
        """
        # Get corner regions
        x, y, w, h = cv2.boundingRect(contour)
        sample_size = self.config['corner_sample_size']
        
        corners = [
            image[y:y+sample_size, x:x+sample_size],  # Top-left
            image[y:y+sample_size, x+w-sample_size:x+w],  # Top-right
            image[y+h-sample_size:y+h, x:x+sample_size],  # Bottom-left
            image[y+h-sample_size:y+h, x+w-sample_size:x+w]  # Bottom-right
        ]
        
        corner_scores = []
        
        for corner_img in corners:
            if corner_img.size == 0:
                continue
            
            # Convert to grayscale
            gray = cv2.cvtColor(corner_img, cv2.COLOR_BGR2GRAY)
            
            # Detect edges (sharp corners have strong edges)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.count_nonzero(edges) / edges.size
            
            # Calculate variance (wear shows as smoothed/blurred areas)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Combine metrics
            # High edge density + high variance = sharp corner
            corner_score = (edge_density * 50) + (min(variance / 100, 1.0) * 50)
            corner_scores.append(min(corner_score, 100))
        
        if not corner_scores:
            return 50.0  # Default if detection fails
        
        # Average all four corners
        return np.mean(corner_scores)
    
    def _analyze_edges(self, image: np.ndarray, contour: np.ndarray) -> float:
        """
        Analyze edge quality (whitening, chipping)
        
        Args:
            image: Card image
            contour: Card boundary contour
            
        Returns:
            Edge score 0-100 (100 = pristine edges)
        """
        x, y, w, h = cv2.boundingRect(contour)
        edge_width = self.config['edge_sample_width']
        
        # Sample edges (top, right, bottom, left)
        edges_to_sample = [
            image[y:y+edge_width, x:x+w],  # Top edge
            image[y:y+h, x+w-edge_width:x+w],  # Right edge
            image[y+h-edge_width:y+h, x:x+w],  # Bottom edge
            image[y:y+h, x:x+edge_width]  # Left edge
        ]
        
        edge_scores = []
        
        for edge_img in edges_to_sample:
            if edge_img.size == 0:
                continue
            
            # Convert to HSV for better white detection
            hsv = cv2.cvtColor(edge_img, cv2.COLOR_BGR2HSV)
            
            # Detect whitening (high value, low saturation)
            white_mask = cv2.inRange(hsv, (0, 0, 200), (180, 30, 255))
            whitening_pct = np.count_nonzero(white_mask) / white_mask.size * 100
            
            # Less whitening = better score
            edge_score = max(0, 100 - whitening_pct * 2)
            edge_scores.append(edge_score)
        
        if not edge_scores:
            return 50.0
        
        return np.mean(edge_scores)
    
    def _analyze_surface(self, image: np.ndarray, contour: np.ndarray) -> float:
        """
        Analyze surface for scratches, dents, print defects
        
        Args:
            image: Card image
            contour: Card boundary contour
            
        Returns:
            Surface score 0-100 (100 = flawless surface)
        """
        # Get card region
        x, y, w, h = cv2.boundingRect(contour)
        card_region = image[y:y+h, x:x+w]
        
        # Convert to grayscale
        gray = cv2.cvtColor(card_region, cv2.COLOR_BGR2GRAY)
        
        # Analyze texture uniformity (scratches disrupt uniformity)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        difference = cv2.absdiff(gray, blur)
        defect_density = np.mean(difference)
        
        # Lower defect density = better surface
        surface_score = max(0, 100 - defect_density)
        
        # Analyze lighting reflections (surface dents create irregular reflections)
        # This is simplified - production version would use multi-angle lighting
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient = np.sqrt(sobel_x**2 + sobel_y**2)
        smoothness = 100 - min(np.std(gradient) / 10, 100)
        
        # Combine metrics
        return (surface_score * 0.6 + smoothness * 0.4)
    
    def _score_to_grade(self, score: float) -> int:
        """
        Convert percentage score to 1-10 grade
        
        Args:
            score: Percentage score 0-100
            
        Returns:
            Grade 1-10
        """
        for grade, threshold in sorted(self.GRADE_THRESHOLDS.items(), reverse=True):
            if score >= threshold:
                return grade
        return 1
    
    def _calculate_confidence(self, image: np.ndarray, contour: np.ndarray) -> float:
        """
        Calculate confidence in grading result
        
        Args:
            image: Card image
            contour: Card boundary contour
            
        Returns:
            Confidence 0-1
        """
        factors = []
        
        # Image resolution
        height, width = image.shape[:2]
        resolution_score = min((width * height) / (self.STANDARD_WIDTH * self.STANDARD_HEIGHT), 1.0)
        factors.append(resolution_score)
        
        # Contour quality (how well card boundary was detected)
        contour_area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        bbox_area = w * h
        fill_ratio = contour_area / bbox_area if bbox_area > 0 else 0
        factors.append(fill_ratio)
        
        # Lighting uniformity (good lighting = better analysis)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        lighting_std = np.std(gray)
        lighting_score = max(0, 1 - (lighting_std / 255))
        factors.append(lighting_score)
        
        return np.mean(factors)
    
    def _get_grade_label(self, grade: int) -> str:
        """Get text label for numeric grade"""
        labels = {
            10: "Gem Mint",
            9: "Mint",
            8: "Near Mint-Mint",
            7: "Near Mint",
            6: "Excellent-Mint",
            5: "Excellent",
            4: "Very Good-Excellent",
            3: "Very Good",
            2: "Good",
            1: "Poor"
        }
        return labels.get(grade, f"Grade {grade}")
    
    def save_grading_report(self, results: Dict, output_path: str):
        """
        Save grading results to JSON file
        
        Args:
            results: Grading analysis results
            output_path: Path to save JSON report
        """
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
    
    def generate_certificate_data(
        self,
        results: Dict,
        card_name: str,
        image_sha256: str = '',
        scanner_serial: str = '',
    ) -> Dict:
        """
        Generate certification data for QR code / blockchain.

        Returns observational condition indicators only — no numeric grade,
        no grade label. The overall score is intentionally omitted so this
        record cannot be mistaken for a professional grade.
        """
        import hashlib

        cert_data = f"{card_name}_{results['timestamp']}_{image_sha256}"
        cert_id = hashlib.sha256(cert_data.encode()).hexdigest()[:16]

        return {
            'certificate_id': cert_id,
            'item_name': card_name,
            'condition_indicators': {
                'centering': results['centering_score'],
                'corners':   results['corners_score'],
                'edges':     results['edges_score'],
                'surface':   results['surface_score'],
            },
            'scan_timestamp': results['timestamp'],
            'ai_confidence': results['confidence'],
            'system': 'NEXUS Scan & Identification v1.0',
            'image_hash': image_sha256,
            'scanner_id': scanner_serial,
            'verification_url': f'https://nexus-cards.com/verify/{cert_id}',
            'disclaimer': (
                'Condition indicators are observational data points. '
                'This certificate does not constitute a grade or appraisal.'
            ),
        }


# Example usage
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python card_grading_analyzer.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        sys.exit(1)
    
    # Analyze card
    analyzer = CardGradingAnalyzer()
    results = analyzer.analyze_card(image)
    
    # Print results
    print("\n" + "="*50)
    print("NEXUS CARD CONDITION ASSESSMENT")
    print("="*50)
    print(f"Condition Score: {results['overall_grade']}/10 - {results['grade_label']}")
    print(f"Analysis Confidence: {results['confidence']*100:.1f}%")
    print(f"\nComponent Scores:")
    print(f"  Centering: {results['centering_score']:.1f}/100")
    print(f"  Corners:   {results['corners_score']:.1f}/100")
    print(f"  Edges:     {results['edges_score']:.1f}/100")
    print(f"  Surface:   {results['surface_score']:.1f}/100")
    print(f"\nAnalyzed: {results['timestamp']}")
    print(f"\nNOTE: {CONDITION_ASSESSMENT_DISCLAIMER}")
    print("="*50 + "\n")
    
    # Save report
    report_path = image_path.replace('.jpg', '_grading_report.json').replace('.png', '_grading_report.json')
    analyzer.save_grading_report(results, report_path)
    print(f"Full report saved to: {report_path}")
