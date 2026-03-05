#!/usr/bin/env python3
"""
NEXUS V2 - Card Back Identifier (Patent Pending)

Identifies card type (MTG, Pokemon, Yu-Gi-Oh, Baseball, Football, etc.)
by analyzing the back of the card before front scan.

This enables automatic database routing:
- MTG backs → Scryfall API
- Pokemon backs → Pokemon TCG API
- Sports backs → Sports card databases
- Unknown → Manual selection

Card Back Signatures:
- MTG: Brown/tan with blue oval, "Deckmaster" text
- Pokemon: Red/white Pokeball pattern
- Yu-Gi-Oh: Brown spiral vortex pattern
- Topps Baseball: Topps logo, red/blue stripes
- Panini: Panini logo patterns
- Upper Deck: UD hologram/logo
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class CardTypeResult:
    """Result of card type identification."""
    card_type: str  # mtg, pokemon, yugioh, baseball, football, basketball, hockey, unknown
    confidence: float  # 0.0 - 1.0
    brand: Optional[str] = None  # Topps, Panini, Upper Deck, etc.
    details: Optional[Dict] = None


class CardBackIdentifier:
    """
    Identifies card type from back image using color analysis and pattern matching.
    """

    # Color signatures for different card backs (HSV ranges)
    CARD_SIGNATURES = {
        'mtg': {
            'name': 'Magic: The Gathering',
            'colors': {
                'brown_tan': [(10, 50, 80), (25, 180, 200)],  # Brown/tan background
                'blue_oval': [(100, 100, 100), (130, 255, 255)],  # Blue center oval
            },
            'aspect_ratio': (0.70, 0.72),  # Standard MTG ratio
            'database': 'scryfall'
        },
        'pokemon': {
            'name': 'Pokemon TCG',
            'colors': {
                'red': [(0, 150, 150), (10, 255, 255)],  # Red Pokeball
                'white': [(0, 0, 200), (180, 30, 255)],  # White center
            },
            'aspect_ratio': (0.70, 0.72),
            'database': 'pokemon_tcg'
        },
        'yugioh': {
            'name': 'Yu-Gi-Oh!',
            'colors': {
                'brown_spiral': [(10, 80, 60), (20, 200, 180)],  # Brown vortex
                'dark_center': [(0, 0, 0), (180, 255, 80)],  # Dark center
            },
            'aspect_ratio': (0.68, 0.70),
            'database': 'yugioh'
        },
        'topps_baseball': {
            'name': 'Topps Baseball',
            'colors': {
                'red_stripe': [(0, 150, 150), (10, 255, 255)],
                'blue_stripe': [(100, 150, 100), (130, 255, 255)],
                'white_bg': [(0, 0, 180), (180, 40, 255)],
            },
            'aspect_ratio': (0.70, 0.72),
            'database': 'sports_baseball',
            'brand': 'Topps'
        },
        'panini': {
            'name': 'Panini',
            'colors': {
                'silver': [(0, 0, 150), (180, 30, 220)],  # Silver/metallic
                'blue': [(100, 80, 100), (130, 255, 255)],
            },
            'aspect_ratio': (0.70, 0.72),
            'database': 'sports_multi',
            'brand': 'Panini'
        },
        'upper_deck': {
            'name': 'Upper Deck',
            'colors': {
                'hologram': [(0, 0, 100), (180, 60, 255)],  # Holographic area
            },
            'aspect_ratio': (0.70, 0.72),
            'database': 'sports_multi',
            'brand': 'Upper Deck'
        },
    }

    # Reference templates directory
    TEMPLATES_DIR = Path(__file__).parent / 'card_back_templates'

    def __init__(self):
        """Initialize card back identifier."""
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        """Load reference templates for template matching."""
        if not self.TEMPLATES_DIR.exists():
            self.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created templates directory: {self.TEMPLATES_DIR}")
            return

        for card_type in self.CARD_SIGNATURES.keys():
            template_path = self.TEMPLATES_DIR / f"{card_type}_back.jpg"
            if template_path.exists():
                template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
                if template is not None:
                    # Resize template to standard size for matching
                    template = cv2.resize(template, (200, 280))
                    self.templates[card_type] = template
                    logger.info(f"Loaded template: {card_type}")

    def identify(self, image: np.ndarray) -> CardTypeResult:
        """
        Identify card type from back image.

        Args:
            image: BGR image of card back

        Returns:
            CardTypeResult with card type and confidence
        """
        if image is None or image.size == 0:
            return CardTypeResult('unknown', 0.0)

        # Resize for consistent analysis
        h, w = image.shape[:2]
        if w > 400:
            scale = 400 / w
            image = cv2.resize(image, (400, int(h * scale)))

        # Try multiple identification methods
        results = {}

        # Method 1: Color histogram analysis
        color_result = self._analyze_colors(image)
        if color_result:
            results['color'] = color_result

        # Method 2: Template matching (if templates loaded)
        if self.templates:
            template_result = self._template_match(image)
            if template_result:
                results['template'] = template_result

        # Method 3: Pattern detection (specific patterns)
        pattern_result = self._detect_patterns(image)
        if pattern_result:
            results['pattern'] = pattern_result

        # Combine results
        return self._combine_results(results)

    def _analyze_colors(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Analyze color distribution to identify card type."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        best_match = None
        best_score = 0.0

        for card_type, signature in self.CARD_SIGNATURES.items():
            score = 0.0
            color_count = len(signature['colors'])

            for color_name, (lower, upper) in signature['colors'].items():
                lower = np.array(lower)
                upper = np.array(upper)
                mask = cv2.inRange(hsv, lower, upper)
                ratio = np.sum(mask > 0) / mask.size

                # Weight scores based on expected coverage
                if ratio > 0.05:  # At least 5% of image has this color
                    score += ratio

            # Normalize by number of colors
            score = score / color_count if color_count > 0 else 0

            if score > best_score:
                best_score = score
                best_match = card_type

        if best_match and best_score > 0.1:
            return (best_match, min(best_score * 2, 0.95))  # Scale confidence

        return None

    def _template_match(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Match against reference templates."""
        # Resize image to match template size
        test_img = cv2.resize(image, (200, 280))
        test_gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)

        best_match = None
        best_score = 0.0

        for card_type, template in self.templates.items():
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

            # Template matching
            result = cv2.matchTemplate(test_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_match = card_type

        if best_match and best_score > 0.5:
            return (best_match, best_score)

        return None

    def _detect_patterns(self, image: np.ndarray) -> Optional[Tuple[str, float]]:
        """Detect specific patterns (Pokeball, MTG oval, etc.)."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Detect circles (Pokeball pattern)
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, 1, 50,
            param1=50, param2=30, minRadius=30, maxRadius=100
        )

        if circles is not None and len(circles[0]) >= 1:
            # Check if circle is in center and has red/white colors
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            center_region = hsv[h//4:3*h//4, w//4:3*w//4]

            # Check for red
            red_mask = cv2.inRange(center_region, (0, 150, 150), (10, 255, 255))
            red_ratio = np.sum(red_mask > 0) / red_mask.size

            if red_ratio > 0.15:
                return ('pokemon', 0.8)

        # Detect oval shape (MTG back)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if len(contour) >= 5:
                ellipse = cv2.fitEllipse(contour)
                (cx, cy), (ma, MA), angle = ellipse

                # Check if ellipse is centered and oval-shaped
                if 0.3*w < cx < 0.7*w and 0.3*h < cy < 0.7*h:
                    aspect = min(ma, MA) / max(ma, MA) if max(ma, MA) > 0 else 0
                    if 0.5 < aspect < 0.8:  # Oval shape
                        # Check for MTG blue color
                        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                        blue_mask = cv2.inRange(hsv, (100, 100, 100), (130, 255, 255))
                        blue_ratio = np.sum(blue_mask > 0) / blue_mask.size

                        if blue_ratio > 0.05:
                            return ('mtg', 0.75)

        return None

    def _combine_results(self, results: Dict) -> CardTypeResult:
        """Combine results from multiple methods."""
        if not results:
            return CardTypeResult('unknown', 0.0)

        # Weighted voting
        votes = {}
        for method, (card_type, confidence) in results.items():
            weight = {
                'template': 1.5,  # Template matching is most reliable
                'pattern': 1.2,
                'color': 1.0
            }.get(method, 1.0)

            if card_type not in votes:
                votes[card_type] = 0.0
            votes[card_type] += confidence * weight

        # Find winner
        if votes:
            winner = max(votes.items(), key=lambda x: x[1])
            card_type = winner[0]
            confidence = min(winner[1] / 2, 0.98)  # Normalize

            signature = self.CARD_SIGNATURES.get(card_type, {})
            return CardTypeResult(
                card_type=card_type,
                confidence=confidence,
                brand=signature.get('brand'),
                details={
                    'database': signature.get('database', 'unknown'),
                    'full_name': signature.get('name', card_type),
                    'methods': list(results.keys())
                }
            )

        return CardTypeResult('unknown', 0.0)

    def identify_from_file(self, image_path: str) -> CardTypeResult:
        """Identify card type from image file."""
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Failed to load image: {image_path}")
            return CardTypeResult('unknown', 0.0)
        return self.identify(image)

    def add_template(self, card_type: str, image: np.ndarray) -> bool:
        """Add a reference template for a card type."""
        try:
            self.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            template_path = self.TEMPLATES_DIR / f"{card_type}_back.jpg"

            # Resize to standard size
            template = cv2.resize(image, (200, 280))
            cv2.imwrite(str(template_path), template)

            self.templates[card_type] = template
            logger.info(f"Added template for {card_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to add template: {e}")
            return False


# Singleton instance
_identifier = None


def get_identifier() -> CardBackIdentifier:
    """Get singleton identifier instance."""
    global _identifier
    if _identifier is None:
        _identifier = CardBackIdentifier()
    return _identifier


def identify_card_back(image_or_path) -> CardTypeResult:
    """
    Convenience function to identify card type.

    Args:
        image_or_path: Either numpy array (BGR) or path to image file

    Returns:
        CardTypeResult
    """
    identifier = get_identifier()
    if isinstance(image_or_path, str):
        return identifier.identify_from_file(image_or_path)
    return identifier.identify(image_or_path)


# Database routing
DATABASE_ROUTES = {
    'mtg': {
        'api': 'scryfall',
        'url': 'https://api.scryfall.com',
        'search_endpoint': '/cards/named'
    },
    'pokemon': {
        'api': 'pokemon_tcg',
        'url': 'https://api.pokemontcg.io/v2',
        'search_endpoint': '/cards'
    },
    'yugioh': {
        'api': 'ygoprodeck',
        'url': 'https://db.ygoprodeck.com/api/v7',
        'search_endpoint': '/cardinfo.php'
    },
    'topps_baseball': {
        'api': 'sports_card_db',
        'category': 'baseball'
    },
    'panini': {
        'api': 'sports_card_db',
        'category': 'multi'
    },
    'upper_deck': {
        'api': 'sports_card_db',
        'category': 'multi'
    }
}


def get_database_for_card(result: CardTypeResult) -> Dict:
    """Get appropriate database/API for identified card type."""
    if result.card_type in DATABASE_ROUTES:
        return DATABASE_ROUTES[result.card_type]
    return {'api': 'manual', 'category': 'unknown'}
