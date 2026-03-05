"""
NEXUS V2 - Multi-Region Cross-Validation System
Patent Claim 1: Multi-Region Scanning Protocol with Cross-Validation
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

@dataclass
class RegionScanData:
    """Data from a single card region scan"""
    region_name: str
    name: str = ""
    set_code: str = ""
    collector_number: str = ""
    confidence: float = 0.0
    raw_text: str = ""
    coordinates: tuple = (0, 0, 0, 0)  # x1, y1, x2, y2

class MultiRegionValidator:
    """Cross-validation system for multi-region card scanning"""
    
    def __init__(self, min_confidence_threshold=0.7):
        self.min_confidence_threshold = min_confidence_threshold
        self.region_weights = {
            'title_region': 1.0,      # Name region is most important
            'set_region': 0.8,        # Set info is very important  
            'number_region': 0.9,     # Collector number is crucial
            'mana_region': 0.6,       # Mana cost is helpful but not critical
            'text_region': 0.5        # Rules text is useful for validation
        }
    
    def cross_validate_regions(self, region_data_list: List[RegionScanData]) -> Dict[str, Any]:
        """
        Cross-validate OCR results from multiple regions for maximum accuracy
        
        Args:
            region_data_list: List of RegionScanData from different card regions
            
        Returns:
            Dict with best consensus results and confidence scores
        """
        if not region_data_list:
            return self._empty_result()
        
        # Group data by field type
        names = self._extract_field_data(region_data_list, 'name')
        set_codes = self._extract_field_data(region_data_list, 'set_code')
        numbers = self._extract_field_data(region_data_list, 'collector_number')
        
        # Find consensus for each field
        consensus_name = self._find_consensus(names, 'name')
        consensus_set = self._find_consensus(set_codes, 'set_code')
        consensus_number = self._find_consensus(numbers, 'collector_number')
        
        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence([
            consensus_name, consensus_set, consensus_number
        ])
        
        # Detect any conflicts or anomalies
        conflicts = self._detect_conflicts(region_data_list)
        
        return {
            'name': consensus_name['value'],
            'set_code': consensus_set['value'],
            'collector_number': consensus_number['value'],
            'confidence': overall_confidence,
            'name_confidence': consensus_name['confidence'],
            'set_confidence': consensus_set['confidence'],
            'number_confidence': consensus_number['confidence'],
            'conflicts_detected': len(conflicts) > 0,
            'conflicts': conflicts,
            'regions_scanned': len(region_data_list),
            'validation_passed': overall_confidence >= self.min_confidence_threshold
        }
    
    def _extract_field_data(self, region_data_list: List[RegionScanData], field: str) -> List[Dict]:
        """Extract field data from all regions"""
        field_data = []
        for region in region_data_list:
            value = getattr(region, field, '')
            if value and value.strip():
                field_data.append({
                    'value': value.strip(),
                    'confidence': region.confidence,
                    'region': region.region_name,
                    'weight': self.region_weights.get(region.region_name, 0.5)
                })
        return field_data
    
    def _find_consensus(self, field_data: List[Dict], field_type: str) -> Dict[str, Any]:
        """Find the best consensus value for a field across regions"""
        if not field_data:
            return {'value': '', 'confidence': 0.0, 'source_regions': []}
        
        # Group similar values
        value_groups = {}
        for item in field_data:
            best_match = None
            best_similarity = 0.0
            
            # Find best matching group
            for existing_value in value_groups.keys():
                similarity = SequenceMatcher(None, item['value'].lower(), existing_value.lower()).ratio()
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = existing_value
            
            # Group with existing if similar enough, otherwise create new group
            if best_match and best_similarity >= 0.8:
                value_groups[best_match].append(item)
            else:
                value_groups[item['value']] = [item]
        
        # Find best group based on weighted confidence
        best_group = None
        best_score = 0.0
        
        for value, items in value_groups.items():
            # Calculate weighted score for this group
            weighted_score = 0.0
            total_weight = 0.0
            
            for item in items:
                weight = item['weight'] * item['confidence']
                weighted_score += weight
                total_weight += item['weight']
            
            if total_weight > 0:
                group_score = weighted_score / total_weight
                
                # Bonus for multiple regions agreeing
                if len(items) > 1:
                    group_score *= (1.0 + (len(items) - 1) * 0.1)
                
                if group_score > best_score:
                    best_score = group_score
                    best_group = (value, items)
        
        if best_group:
            value, items = best_group
            source_regions = [item['region'] for item in items]
            return {
                'value': value,
                'confidence': min(best_score, 1.0),
                'source_regions': source_regions,
                'agreement_count': len(items)
            }
        
        # Fallback to first item
        first_item = field_data[0]
        return {
            'value': first_item['value'],
            'confidence': first_item['confidence'] * 0.5,  # Reduced confidence for no consensus
            'source_regions': [first_item['region']],
            'agreement_count': 1
        }
    
    def _calculate_overall_confidence(self, consensus_results: List[Dict]) -> float:
        """Calculate overall confidence from individual field consensus"""
        if not consensus_results:
            return 0.0
        
        # Weight different fields by importance
        field_weights = [0.4, 0.3, 0.3]  # name, set, number
        
        total_weighted_confidence = 0.0
        total_weight = 0.0
        
        for i, result in enumerate(consensus_results[:3]):  # Only use first 3
            if i < len(field_weights) and result['value']:
                weight = field_weights[i]
                confidence = result['confidence']
                
                # Bonus for multiple region agreement
                if result.get('agreement_count', 1) > 1:
                    confidence *= 1.2
                
                total_weighted_confidence += confidence * weight
                total_weight += weight
        
        if total_weight > 0:
            return min(total_weighted_confidence / total_weight, 1.0)
        
        return 0.0
    
    def _detect_conflicts(self, region_data_list: List[RegionScanData]) -> List[Dict]:
        """Detect conflicts between regions that may indicate scanning issues"""
        conflicts = []
        
        # Check for major discrepancies in name field
        names = [region.name for region in region_data_list if region.name]
        if len(set(names)) > len(names) * 0.5:  # More than 50% different
            conflicts.append({
                'type': 'name_conflict',
                'description': 'Multiple different names detected across regions',
                'values': list(set(names))
            })
        
        # Check for confidence drops
        confidences = [region.confidence for region in region_data_list]
        if confidences and max(confidences) - min(confidences) > 0.3:
            conflicts.append({
                'type': 'confidence_variance',
                'description': 'Large confidence variance between regions',
                'range': f"{min(confidences):.2f} - {max(confidences):.2f}"
            })
        
        return conflicts
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'name': '',
            'set_code': '',
            'collector_number': '',
            'confidence': 0.0,
            'name_confidence': 0.0,
            'set_confidence': 0.0,
            'number_confidence': 0.0,
            'conflicts_detected': False,
            'conflicts': [],
            'regions_scanned': 0,
            'validation_passed': False
        }
    
    def validate_scan_quality(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the overall scan quality and provide recommendations
        
        Args:
            validation_result: Result from cross_validate_regions
            
        Returns:
            Quality assessment with recommendations
        """
        quality_score = validation_result['confidence']
        recommendations = []
        
        if quality_score < 0.5:
            recommendations.append("Poor scan quality - consider rescanning")
        elif quality_score < 0.7:
            recommendations.append("Fair scan quality - manual verification recommended")
        elif quality_score < 0.9:
            recommendations.append("Good scan quality")
        else:
            recommendations.append("Excellent scan quality")
        
        if validation_result['conflicts_detected']:
            recommendations.append("Conflicts detected between regions - review manually")
        
        if validation_result['regions_scanned'] < 3:
            recommendations.append("Consider scanning more regions for better accuracy")
        
        return {
            'quality_grade': self._get_quality_grade(quality_score),
            'quality_score': quality_score,
            'recommendations': recommendations,
            'requires_manual_review': quality_score < 0.7 or validation_result['conflicts_detected'],
            'passed_validation': validation_result['validation_passed']
        }
    
    def _get_quality_grade(self, score: float) -> str:
        """Convert confidence score to quality grade"""
        if score >= 0.9:
            return "A"
        elif score >= 0.8:
            return "B"
        elif score >= 0.7:
            return "C"
        elif score >= 0.5:
            return "D"
        else:
            return "F"