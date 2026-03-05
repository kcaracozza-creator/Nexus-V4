#!/usr/bin/env python3
"""
NEXUS Meta Analyzer
===================
Analyzes metagame trends and predicts format shifts for MTG.
Provides investment recommendations and budget deck opportunities.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json


@dataclass
class Archetype:
    """Represents a deck archetype in the metagame"""
    name: str
    meta_share: float = 0.0
    win_rate: float = 0.5
    tier: str = "Tier 2"
    key_cards: List[str] = field(default_factory=list)


@dataclass
class MetaPrediction:
    """Prediction results from meta analysis"""
    timestamp: datetime = field(default_factory=datetime.now)
    emerging_archetypes: List[Dict] = field(default_factory=list)
    declining_archetypes: List[Dict] = field(default_factory=list)
    stable_archetypes: List[Dict] = field(default_factory=list)
    key_card_impacts: List[Dict] = field(default_factory=list)
    investment_opportunities: List[Dict] = field(default_factory=list)
    confidence_score: float = 0.0


class MetaAnalyzer:
    """
    Analyzes metagame data to predict format shifts and identify opportunities.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize meta analyzer with optional data directory"""
        self.data_dir = data_dir or Path(__file__).parent / "meta_data"
        self.data_dir.mkdir(exist_ok=True)

        self.meta_history: Dict = {'predictions': [], 'accuracy_scores': []}
        self.format_data: Dict[str, Dict] = {}

        self._load_meta_history()

    def _load_meta_history(self) -> None:
        """Load historical meta predictions"""
        history_file = self.data_dir / "meta_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    self.meta_history = json.load(f)
            except Exception:
                pass

    def _save_meta_history(self) -> None:
        """Save meta history to file"""
        history_file = self.data_dir / "meta_history.json"
        try:
            with open(history_file, 'w') as f:
                json.dump(self.meta_history, f, indent=2)
        except Exception:
            pass

    def predict_meta_shifts(self, format_name: str = "Standard") -> MetaPrediction:
        """
        Predict upcoming metagame shifts based on current trends.

        Args:
            format_name: The format to analyze (Standard, Modern, etc.)

        Returns:
            MetaPrediction with emerging/declining archetypes and investment tips
        """
        prediction = MetaPrediction()

        # Sample emerging archetypes (would be from real data)
        prediction.emerging_archetypes = [
            {'name': 'Domain Zoo', 'confidence': 0.75, 'expected_share': 12.0},
            {'name': 'Mono-Black Midrange', 'confidence': 0.68, 'expected_share': 8.5},
            {'name': 'Azorius Soldiers', 'confidence': 0.62, 'expected_share': 6.0}
        ]

        # Sample declining archetypes
        prediction.declining_archetypes = [
            {'name': 'Esper Control', 'confidence': 0.70, 'expected_share': 5.0},
            {'name': 'Mono-Red Aggro', 'confidence': 0.55, 'expected_share': 7.0}
        ]

        # Key card impacts
        prediction.key_card_impacts = [
            {'name': 'Teferi, Time Raveler', 'impact': 'High', 'trend': 'Declining', 'price_change': -15},
            {'name': 'Lightning Bolt', 'impact': 'Medium', 'trend': 'Stable', 'price_change': 0},
            {'name': 'Counterspell', 'impact': 'High', 'trend': 'Rising', 'price_change': +25},
            {'name': 'Force of Will', 'impact': 'Critical', 'trend': 'Stable', 'price_change': 0},
            {'name': 'Ragavan, Nimble Pilferer', 'impact': 'High', 'trend': 'Rising', 'price_change': +35}
        ]

        # Investment opportunities (cards likely to spike)
        prediction.investment_opportunities = [
            {'name': 'Ragavan, Nimble Pilferer', 'confidence': 0.85, 'potential_gain': '+40%'},
            {'name': 'Ledger Shredder', 'confidence': 0.72, 'potential_gain': '+60%'},
            {'name': 'Fable of the Mirror-Breaker', 'confidence': 0.68, 'potential_gain': '+30%'}
        ]

        # Calculate confidence score
        prediction.confidence_score = self._calculate_prediction_confidence(format_name)

        # Save prediction
        self.meta_history['predictions'].append({
            'format': format_name,
            'timestamp': prediction.timestamp.isoformat(),
            'confidence': prediction.confidence_score,
            'emerging_count': len(prediction.emerging_archetypes),
            'declining_count': len(prediction.declining_archetypes)
        })
        self._save_meta_history()

        return prediction

    def _get_enabler_cards(self, trend: str) -> List[str]:
        """Get key enabler cards for a trend"""
        enablers = {
            'Artifacts': ['Urza, Lord High Artificer', 'Karn, the Great Creator', 'Mox Opal'],
            'Enchantments': ["Enchantress's Presence", 'Sterling Grove', 'Sigil of the Empty Throne'],
            'Planeswalkers': ['The Wanderer', 'Narset, Parter of Veils', 'Karn Liberated'],
            'Cascade': ['Bloodbraid Elf', 'Shardless Agent', 'Violent Outburst'],
            'Free Spells': ['Force of Will', 'Force of Negation', 'Solitude'],
            'Prison': ['Chalice of the Void', 'Trinisphere', 'Blood Moon'],
            'Tribal': ['Cavern of Souls', 'Collected Company', 'Aether Vial']
        }
        return enablers.get(trend, ['Generic synergy cards'])

    def _calculate_prediction_confidence(self, format_name: str) -> float:
        """Calculate confidence in predictions based on historical accuracy"""
        base_confidence = 0.60

        # Adjust based on format stability
        stability_bonus = {
            'Legacy': 0.20,    # More stable
            'Modern': 0.10,    # Moderately stable
            'Standard': -0.10,  # Less stable (rotation)
            'Commander': 0.15  # Stable (no rotation)
        }.get(format_name, 0)

        # Historical accuracy bonus (would use real data)
        recent_predictions = self.meta_history.get('accuracy_scores', [])[-10:]
        if recent_predictions:
            avg_accuracy = sum(recent_predictions) / len(recent_predictions)
            history_bonus = (avg_accuracy - 0.5) * 0.2  # Max +/-10%
        else:
            history_bonus = 0

        confidence = base_confidence + stability_bonus + history_bonus
        return max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

    def get_budget_opportunities(self, format_name: str = "Standard",
                                 max_budget: float = 30.0,
                                 limit: int = 5) -> List[Dict]:
        """
        Find budget deck opportunities in meta

        Args:
            format_name: Format to search
            max_budget: Maximum deck cost
            limit: Maximum number of results

        Returns:
            List of budget-friendly competitive archetypes
        """
        # Budget-friendly archetypes
        budget_archetypes = [
            {
                'name': 'Mono-Red Aggro',
                'cost': 25.00,
                'win_rate': 0.52,
                'tier': 'Tier 1.5',
                'key_cards': ['Monastery Swiftspear', 'Lightning Bolt', 'Lava Spike'],
                'strategy': 'Fast aggressive strategy with cheap burn spells'
            },
            {
                'name': 'Mono-Blue Tempo',
                'cost': 28.00,
                'win_rate': 0.49,
                'tier': 'Tier 2',
                'key_cards': ['Delver of Secrets', 'Counterspell', 'Ninja of the Deep Hours'],
                'strategy': 'Counter and tempo plays with cheap creatures'
            },
            {
                'name': 'Pauper Elves',
                'cost': 22.00,
                'win_rate': 0.51,
                'tier': 'Tier 1',
                'key_cards': ['Llanowar Elves', 'Elvish Mystic', 'Lead the Stampede'],
                'strategy': 'Explosive tribal synergy with mana acceleration'
            }
        ]

        opportunities = []
        for archetype in budget_archetypes:
            if archetype['cost'] <= max_budget:
                opportunities.append(archetype)
                if len(opportunities) >= limit:
                    break

        return opportunities[:limit]

    def analyze_meta_share(self, format_name: str) -> Dict[str, float]:
        """
        Get current meta share distribution

        Returns:
            Dict mapping archetype names to meta share percentages
        """
        format_info = self.format_data.get(format_name, {})
        archetypes = format_info.get('top_archetypes', [])

        return {arch.name: arch.meta_share for arch in archetypes}

    def get_format_health_score(self, format_name: str) -> float:
        """
        Calculate format health score (diversity metric)
        Higher is better (more diverse meta)

        Returns:
            Score from 0.0 to 1.0
        """
        meta_shares = self.analyze_meta_share(format_name)

        if not meta_shares:
            return 0.5

        # Calculate diversity using inverse Herfindahl index
        herfindahl = sum(share ** 2 for share in meta_shares.values())

        # Normalize: perfect diversity (20 equal decks) = 0.05, monopoly = 1.0
        # Convert to 0-1 scale where 1 is best
        diversity_score = 1.0 - min(herfindahl, 1.0)

        return diversity_score


if __name__ == "__main__":
    analyzer = MetaAnalyzer()
    print("Meta Analyzer initialized")

    prediction = analyzer.predict_meta_shifts("Modern")
    print(f"\nMeta prediction confidence: {prediction.confidence_score:.2%}")
    print(f"Emerging archetypes: {len(prediction.emerging_archetypes)}")
    print(f"Declining archetypes: {len(prediction.declining_archetypes)}")
