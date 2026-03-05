#!/usr/bin/env python3
"""
Similar Card Detection System
Handles cards with similar/identical names (reprints, promos, alternate art, etc.)
"""

import re
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from collections import defaultdict


class SimilarCardDetector:
    """
    Detects and disambiguates similar card names
    
    Handles:
    - Reprints (same card, different sets)
    - Promos (promo versions vs regular)
    - Alternate art (borderless, extended art, etc.)
    - Similar names (Lightning Bolt vs Lightning Strike)
    """
    
    def __init__(self, card_database: Dict):
        """
        Initialize detector
        
        Args:
            card_database: Dict mapping card names to card data
        """
        self.card_database = card_database
        self.similar_groups = defaultdict(list)
        self._build_similarity_index()
    
    def _build_similarity_index(self):
        """Build index of similar card names"""
        # Group cards by base name (removing set indicators, promo markers, etc.)
        for card_name in self.card_database.keys():
            base_name = self._get_base_name(card_name)
            self.similar_groups[base_name].append(card_name)
        
        # Keep only groups with 2+ variants
        self.similar_groups = {
            k: v for k, v in self.similar_groups.items() if len(v) > 1
        }
        
        print(f"[SIMILAR] Found {len(self.similar_groups)} card groups with variants")
    
    def _get_base_name(self, card_name: str) -> str:
        """
        Extract base card name (remove set/promo indicators)
        
        Examples:
            "Lightning Bolt (M11)" → "lightning bolt"
            "Lightning Bolt [Promo]" → "lightning bolt"
            "Lightning Bolt - Borderless" → "lightning bolt"
        """
        # Remove parentheses (set codes)
        name = re.sub(r'\([^)]*\)', '', card_name)
        
        # Remove brackets (promo markers)
        name = re.sub(r'\[[^\]]*\]', '', name)
        
        # Remove dashes and everything after (variant descriptions)
        name = name.split('-')[0]
        name = name.split('//')[0]  # Split cards
        
        # Clean and normalize
        name = name.strip().lower()
        
        return name
    
    def find_similar_cards(self, card_name: str, threshold: float = 0.85) -> List[Dict]:
        """
        Find cards with similar names
        
        Args:
            card_name: Card name to check
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            List of similar cards with similarity scores
        """
        results = []
        card_lower = card_name.lower()
        
        # Check exact base name matches first
        base_name = self._get_base_name(card_name)
        if base_name in self.similar_groups:
            variants = self.similar_groups[base_name]
            for variant in variants:
                if variant.lower() != card_lower:  # Don't include exact match
                    results.append({
                        'name': variant,
                        'similarity': 1.0,
                        'type': 'variant',
                        'reason': 'Same base card, different version'
                    })
        
        # Check fuzzy similar names
        for db_name in self.card_database.keys():
            if db_name.lower() == card_lower:
                continue  # Skip exact match
            
            # Calculate similarity
            similarity = SequenceMatcher(None, card_lower, db_name.lower()).ratio()
            
            if similarity >= threshold:
                # Determine relationship type
                rel_type = self._determine_relationship(card_name, db_name)
                
                results.append({
                    'name': db_name,
                    'similarity': similarity,
                    'type': rel_type,
                    'reason': self._explain_similarity(card_name, db_name, rel_type)
                })
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return results
    
    def _determine_relationship(self, name1: str, name2: str) -> str:
        """Determine relationship between two similar cards"""
        base1 = self._get_base_name(name1)
        base2 = self._get_base_name(name2)
        
        if base1 == base2:
            return 'variant'
        
        # Check for common word patterns
        words1 = set(name1.lower().split())
        words2 = set(name2.lower().split())
        common_words = words1 & words2
        
        if len(common_words) >= 2:
            return 'related'
        
        return 'similar'
    
    def _explain_similarity(self, name1: str, name2: str, rel_type: str) -> str:
        """Generate human-readable explanation of similarity"""
        if rel_type == 'variant':
            # Check specific variant types
            if 'promo' in name1.lower() or 'promo' in name2.lower():
                return 'Promo vs regular version'
            elif 'foil' in name1.lower() or 'foil' in name2.lower():
                return 'Foil vs non-foil'
            elif any(x in name1.lower() + name2.lower() for x in ['borderless', 'extended', 'showcase']):
                return 'Alternate art version'
            else:
                return 'Different printing/set'
        
        elif rel_type == 'related':
            return 'Related card (similar effect or name)'
        
        else:
            return 'Similar name'
    
    def needs_disambiguation(self, card_name: str) -> bool:
        """
        Check if card name needs user disambiguation
        
        Returns True if multiple versions exist
        """
        base_name = self._get_base_name(card_name)
        return base_name in self.similar_groups and len(self.similar_groups[base_name]) > 1
    
    def get_disambiguation_options(self, card_name: str) -> List[Dict]:
        """
        Get all versions/variants for user to choose from
        
        Returns:
            List of variants with metadata for display
        """
        base_name = self._get_base_name(card_name)
        
        if base_name not in self.similar_groups:
            return []
        
        variants = self.similar_groups[base_name]
        options = []
        
        for variant in variants:
            card_data = self.card_database.get(variant, {})
            
            # Extract variant info
            variant_type = self._extract_variant_type(variant)
            set_code = self._extract_set_code(variant)
            
            options.append({
                'name': variant,
                'variant_type': variant_type,
                'set': set_code,
                'type': card_data.get('type', ''),
                'colors': card_data.get('colors', ''),
                'display_name': self._format_display_name(variant, variant_type, set_code)
            })
        
        return options
    
    def _extract_variant_type(self, card_name: str) -> str:
        """Extract variant type from card name"""
        name_lower = card_name.lower()
        
        if 'promo' in name_lower:
            return 'Promo'
        elif 'borderless' in name_lower:
            return 'Borderless'
        elif 'extended' in name_lower:
            return 'Extended Art'
        elif 'showcase' in name_lower:
            return 'Showcase'
        elif 'foil' in name_lower:
            return 'Foil'
        else:
            return 'Regular'
    
    def _extract_set_code(self, card_name: str) -> str:
        """Extract set code from card name"""
        # Look for parentheses with set code
        match = re.search(r'\(([A-Z0-9]{3,})\)', card_name)
        if match:
            return match.group(1)
        return 'Unknown'
    
    def _format_display_name(self, name: str, variant_type: str, set_code: str) -> str:
        """Format card name for display in disambiguation dialog"""
        base = self._get_base_name(name).title()
        
        parts = [base]
        
        if variant_type != 'Regular':
            parts.append(f"[{variant_type}]")
        
        if set_code != 'Unknown':
            parts.append(f"({set_code})")
        
        return ' '.join(parts)
    
    def get_most_common_version(self, card_name: str) -> Optional[str]:
        """
        Get the most common/standard version of a card
        
        Prioritizes: Regular > Promo > Borderless > Others
        """
        base_name = self._get_base_name(card_name)
        
        if base_name not in self.similar_groups:
            return card_name
        
        variants = self.similar_groups[base_name]
        
        # Score each variant (lower = more common)
        scored = []
        for variant in variants:
            score = 0
            variant_lower = variant.lower()
            
            # Regular versions score lowest (most common)
            if 'promo' in variant_lower:
                score += 10
            if 'borderless' in variant_lower:
                score += 20
            if 'extended' in variant_lower:
                score += 20
            if 'showcase' in variant_lower:
                score += 20
            if 'foil' in variant_lower:
                score += 5
            
            scored.append((score, variant))
        
        # Return lowest scoring (most common) variant
        scored.sort()
        return scored[0][1] if scored else card_name


def demonstrate_similar_card_detection():
    """Demonstrate similar card detection"""
    
    # Mock card database
    mock_db = {
        'Lightning Bolt': {'type': 'Instant', 'colors': 'R'},
        'Lightning Bolt (M11)': {'type': 'Instant', 'colors': 'R'},
        'Lightning Bolt [Promo]': {'type': 'Instant', 'colors': 'R'},
        'Lightning Bolt - Borderless': {'type': 'Instant', 'colors': 'R'},
        'Lightning Strike': {'type': 'Instant', 'colors': 'R'},
        'Chain Lightning': {'type': 'Sorcery', 'colors': 'R'},
        'Black Lotus': {'type': 'Artifact', 'colors': ''},
        'Black Lotus (Alpha)': {'type': 'Artifact', 'colors': ''},
        'Black Lotus [Promo]': {'type': 'Artifact', 'colors': ''},
    }
    
    detector = SimilarCardDetector(mock_db)
    
    print("\n=== Testing Similar Card Detection ===\n")
    
    # Test 1: Find variants
    print("Test 1: Lightning Bolt variants")
    if detector.needs_disambiguation("Lightning Bolt"):
        options = detector.get_disambiguation_options("Lightning Bolt")
        for opt in options:
            print(f"  - {opt['display_name']} [{opt['variant_type']}]")
    
    # Test 2: Find similar cards
    print("\nTest 2: Cards similar to 'Lightning Bolt'")
    similar = detector.find_similar_cards("Lightning Bolt", threshold=0.7)
    for card in similar[:5]:
        print(f"  - {card['name']} ({card['similarity']:.0%}) - {card['reason']}")
    
    # Test 3: Get most common version
    print("\nTest 3: Most common version")
    common = detector.get_most_common_version("Lightning Bolt [Promo]")
    print(f"  Promo version → {common}")
    
    print("\n✅ Similar card detection demonstration complete!")


if __name__ == "__main__":
    demonstrate_similar_card_detection()
