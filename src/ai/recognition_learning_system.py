#!/usr/bin/env python3
"""
AI Recognition Learning System
Learns from user corrections to improve accuracy over time
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
import re


class RecognitionLearningSystem:
    """
    Learns from user corrections to improve card recognition
    
    Features:
    - Common OCR error patterns (l→I, 0→O, etc.)
    - User-specific corrections (shop owner preferences)
    - Confidence boosting for previously corrected cards
    - Auto-fix known typos
    """
    
    def __init__(self, corrections_file: str):
        """
        Initialize learning system
        
        Args:
            corrections_file: Path to recognition_corrections.json
        """
        self.corrections_file = corrections_file
        self.corrections = []
        self.error_patterns = defaultdict(int)  # wrong → correct mapping
        self.typo_fixes = {}  # Common OCR typos → fixes
        self.card_overrides = {}  # Specific cards user always corrects
        
        # Load existing corrections
        self.load_corrections()
        
        # Analyze patterns
        self.analyze_patterns()
    
    def load_corrections(self):
        """Load correction history from JSON"""
        if os.path.exists(self.corrections_file):
            try:
                with open(self.corrections_file, 'r') as f:
                    self.corrections = json.load(f)
                print(f"[LEARNING] Loaded {len(self.corrections)} corrections")
            except Exception as e:
                print(f"[WARNING] Failed to load corrections: {e}")
                self.corrections = []
        else:
            self.corrections = []
    
    def add_correction(self, original: str, corrected: str, confidence: float):
        """
        Add a new correction and update patterns
        
        Args:
            original: What AI recognized
            corrected: What user corrected to
            confidence: Original confidence score
        """
        correction = {
            'timestamp': datetime.now().isoformat(),
            'original': original,
            'corrected': corrected,
            'confidence': confidence
        }
        
        self.corrections.append(correction)
        
        # Save to file
        try:
            with open(self.corrections_file, 'w') as f:
                json.dump(self.corrections, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Failed to save correction: {e}")
        
        # Update patterns
        self.analyze_patterns()
    
    def analyze_patterns(self):
        """Analyze corrections to find common patterns"""
        if not self.corrections:
            return
        
        # Clear existing patterns
        self.error_patterns = defaultdict(int)
        self.card_overrides = {}
        
        # Count how many times each correction was made
        correction_counts = Counter()
        for corr in self.corrections:
            orig = corr['original'].lower()
            fixed = corr['corrected'].lower()
            if orig != fixed:
                correction_counts[(orig, fixed)] += 1
        
        # Build error patterns (if corrected 2+ times, it's a pattern)
        for (original, corrected), count in correction_counts.items():
            if count >= 2:
                self.error_patterns[original] = corrected
                self.card_overrides[original] = corrected
        
        # Analyze character-level typos
        self._analyze_character_errors()
        
        print(f"[LEARNING] Found {len(self.error_patterns)} correction patterns")
        print(f"[LEARNING] Found {len(self.typo_fixes)} typo fixes")
    
    def _analyze_character_errors(self):
        """Analyze character-level OCR errors"""
        self.typo_fixes = {}
        
        for corr in self.corrections:
            original = corr['original'].lower()
            corrected = corr['corrected'].lower()
            
            if len(original) != len(corrected):
                continue  # Skip different length words
            
            # Find character differences
            for i, (o_char, c_char) in enumerate(zip(original, corrected)):
                if o_char != c_char:
                    # Found a character error
                    context_key = f"{o_char}→{c_char}"
                    if context_key not in self.typo_fixes:
                        self.typo_fixes[context_key] = 1
                    else:
                        self.typo_fixes[context_key] += 1
        
        # Keep only patterns that occur 3+ times
        self.typo_fixes = {k: v for k, v in self.typo_fixes.items() if v >= 3}
    
    def apply_learned_corrections(self, text: str) -> str:
        """
        Apply learned corrections to improve recognition
        
        Args:
            text: Raw OCR text
            
        Returns:
            Corrected text with learned patterns applied
        """
        corrected = text
        
        # Apply exact card overrides first
        text_lower = text.lower()
        if text_lower in self.card_overrides:
            corrected = self.card_overrides[text_lower]
            print(f"[LEARNING] Applied override: {text} → {corrected}")
            return corrected
        
        # Apply common typo fixes
        for pattern, count in self.typo_fixes.items():
            if '→' in pattern:
                wrong, right = pattern.split('→')
                corrected = corrected.replace(wrong, right)
        
        # Apply error patterns
        for wrong, right in self.error_patterns.items():
            if wrong in corrected.lower():
                corrected = corrected.lower().replace(wrong, right)
                print(f"[LEARNING] Applied pattern: {text} → {corrected}")
        
        return corrected
    
    def boost_confidence(self, card_name: str, base_confidence: float) -> float:
        """
        Boost confidence if this card was previously corrected correctly
        
        Args:
            card_name: Recognized card name
            base_confidence: Original confidence score
            
        Returns:
            Boosted confidence (max 0.99)
        """
        card_lower = card_name.lower()
        
        # Check if this exact card was previously corrected
        for corr in self.corrections:
            if corr['corrected'].lower() == card_lower:
                # This card was confirmed before - boost confidence
                boost = 0.10  # +10% confidence
                boosted = min(base_confidence + boost, 0.99)
                if boosted > base_confidence:
                    print(f"[LEARNING] Boosted confidence: {base_confidence:.2%} → {boosted:.2%}")
                return boosted
        
        return base_confidence
    
    def get_common_mistakes(self, limit: int = 10) -> List[Dict]:
        """
        Get most common recognition mistakes
        
        Args:
            limit: Max number of mistakes to return
            
        Returns:
            List of {original, corrected, count} dicts
        """
        mistake_counts = Counter()
        
        for corr in self.corrections:
            orig = corr['original']
            fixed = corr['corrected']
            if orig.lower() != fixed.lower():
                mistake_counts[(orig, fixed)] += 1
        
        results = []
        for (original, corrected), count in mistake_counts.most_common(limit):
            results.append({
                'original': original,
                'corrected': corrected,
                'count': count
            })
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get learning statistics"""
        if not self.corrections:
            return {
                'total_corrections': 0,
                'unique_patterns': 0,
                'typo_fixes': 0,
                'avg_confidence': 0.0,
                'improvement_rate': 0.0
            }
        
        # Count corrections that improved low confidence
        improved = sum(1 for c in self.corrections if c['confidence'] < 0.80)
        
        # Average confidence of corrected scans
        avg_conf = sum(c['confidence'] for c in self.corrections) / len(self.corrections)
        
        return {
            'total_corrections': len(self.corrections),
            'unique_patterns': len(self.error_patterns),
            'typo_fixes': len(self.typo_fixes),
            'avg_confidence': avg_conf,
            'improvement_rate': improved / len(self.corrections) if self.corrections else 0.0,
            'common_mistakes': self.get_common_mistakes(5)
        }
    
    def export_training_data(self, output_file: str):
        """
        Export corrections as training data for future AI model improvements
        
        Args:
            output_file: Path to save training data CSV
        """
        import csv
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Original', 'Corrected', 'Confidence', 'Pattern'])
                
                for corr in self.corrections:
                    orig = corr['original']
                    fixed = corr['corrected']
                    pattern = 'exact' if orig == fixed else 'correction'
                    
                    writer.writerow([
                        corr['timestamp'],
                        orig,
                        fixed,
                        corr['confidence'],
                        pattern
                    ])
            
            print(f"[LEARNING] Exported {len(self.corrections)} corrections to {output_file}")
        except Exception as e:
            print(f"[ERROR] Failed to export training data: {e}")


def demonstrate_learning_system():
    """Demonstrate the learning system capabilities"""
    import tempfile
    
    # Create temp corrections file
    temp_file = os.path.join(tempfile.gettempdir(), "demo_corrections.json")
    
    # Initialize system
    system = RecognitionLearningSystem(temp_file)
    
    # Simulate corrections
    print("\n=== Simulating User Corrections ===")
    
    corrections = [
        ("Lighning Bolt", "Lightning Bolt", 0.75),  # Typo
        ("Lighning Bolt", "Lightning Bolt", 0.72),  # Same typo again
        ("Lighning Bolt", "Lightning Bolt", 0.78),  # Learning!
        ("Counterspel", "Counterspell", 0.80),
        ("Counterspel", "Counterspell", 0.82),
        ("B1ack Lotus", "Black Lotus", 0.65),  # 1→l error
        ("B1ack Lotus", "Black Lotus", 0.68),
    ]
    
    for orig, fixed, conf in corrections:
        print(f"  Correcting: {orig} → {fixed} (confidence: {conf:.0%})")
        system.add_correction(orig, fixed, conf)
    
    # Show learned patterns
    print("\n=== Learned Patterns ===")
    for wrong, right in system.error_patterns.items():
        print(f"  {wrong} → {right}")
    
    # Test auto-correction
    print("\n=== Testing Auto-Correction ===")
    test_cases = ["Lighning Bolt", "Counterspel", "B1ack Lotus"]
    for test in test_cases:
        corrected = system.apply_learned_corrections(test)
        print(f"  {test} → {corrected}")
    
    # Test confidence boosting
    print("\n=== Testing Confidence Boosting ===")
    boosted = system.boost_confidence("Lightning Bolt", 0.75)
    print(f"  Lightning Bolt: 75% → {boosted:.0%}")
    
    # Show statistics
    print("\n=== Learning Statistics ===")
    stats = system.get_statistics()
    print(f"  Total corrections: {stats['total_corrections']}")
    print(f"  Unique patterns: {stats['unique_patterns']}")
    print(f"  Average confidence: {stats['avg_confidence']:.0%}")
    print(f"  Improvement rate: {stats['improvement_rate']:.0%}")
    
    print("\n  Top mistakes:")
    for mistake in stats['common_mistakes']:
        print(f"    {mistake['original']} → {mistake['corrected']} ({mistake['count']}x)")
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    print("\n✅ Learning system demonstration complete!")


if __name__ == "__main__":
    demonstrate_learning_system()
