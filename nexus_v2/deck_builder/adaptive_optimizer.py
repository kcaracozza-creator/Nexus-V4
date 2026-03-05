#!/usr/bin/env python3
"""
Adaptive Deck Optimizer - Connects static AI optimizer with match learning.
Makes deck recommendations adaptive based on actual match results.
"""

import os
import sys
from collections import defaultdict

# Import existing AI optimizer
try:
    from ai_deck_optimizer import AdvancedDeckOptimizer, AIMetaAnalyzer
    OPTIMIZER_AVAILABLE = True
except ImportError:
    print("⚠️ ai_deck_optimizer not available")
    OPTIMIZER_AVAILABLE = False

# Import match learning system
try:
    from match_tracker import MatchTracker
    from card_performance_analyzer import CardPerformanceAnalyzer
    LEARNING_AVAILABLE = True
except ImportError:
    print("⚠️ Match learning system not available")
    LEARNING_AVAILABLE = False


class AdaptiveDeckOptimizer:
    """
    Enhanced deck optimizer that learns from actual match results
    Combines static AI analysis with adaptive learning from gameplay
    """
    
    def __init__(self, static_optimizer=None, match_tracker=None, card_analyzer=None):
        """
        Initialize adaptive optimizer
        
        Args:
            static_optimizer: AdvancedDeckOptimizer instance (meta analysis)
            match_tracker: MatchTracker instance (match history)
            card_analyzer: CardPerformanceAnalyzer instance (card stats)
        """
        self.static_optimizer = static_optimizer
        self.match_tracker = match_tracker or (MatchTracker() if LEARNING_AVAILABLE else None)
        self.card_analyzer = card_analyzer or (
            CardPerformanceAnalyzer(self.match_tracker) if LEARNING_AVAILABLE and self.match_tracker else None
        )
        
        # Weight factors for combining static and adaptive recommendations
        self.static_weight = 0.4  # Weight for meta-based recommendations
        self.adaptive_weight = 0.6  # Weight for your actual results
        
    def optimize_deck(self, deck_list, format_type="Commander", strategy="balanced"):
        """
        Optimize deck using both static analysis and adaptive learning
        
        Args:
            deck_list: List of card names in current deck
            format_type: Format (Commander, Modern, etc.)
            strategy: Deck strategy (aggro, control, etc.)
            
        Returns:
            dict with optimization recommendations
        """
        recommendations = {
            'format': format_type,
            'strategy': strategy,
            'cards_to_remove': [],
            'cards_to_add': [],
            'synergy_improvements': [],
            'meta_considerations': [],
            'personal_performance': {}
        }
        
        # Get static meta analysis
        if self.static_optimizer:
            try:
                static_recs = self.static_optimizer.optimize_deck(
                    deck_list, format_type, strategy
                )
                recommendations['meta_considerations'] = static_recs.get('meta_analysis', [])
            except Exception as e:
                print(f"⚠️ Static analysis failed: {e}")
        
        # Get adaptive recommendations from YOUR match history
        if self.card_analyzer and self.match_tracker:
            try:
                # Check if we have enough data
                stats = self.match_tracker.get_statistics()
                
                if stats['total_matches'] >= 5:
                    # Generate optimization report based on YOUR results
                    adaptive_report = self.card_analyzer.generate_deck_optimization_report(deck_list)
                    
                    # Cards to remove (underperformers in YOUR games)
                    for card in adaptive_report.get('cards_to_remove', [])[:5]:
                        card_stats = self.card_analyzer.get_card_score(card)
                        recommendations['cards_to_remove'].append({
                            'card': card,
                            'reason': f"Low win rate in your games: {card_stats.get('win_rate', 0):.1f}%",
                            'games_played': card_stats.get('games_played', 0),
                            'win_rate': card_stats.get('win_rate', 0),
                            'source': 'adaptive'
                        })
                    
                    # Cards to add (high performers in YOUR games)
                    for card in adaptive_report.get('cards_to_add', [])[:5]:
                        card_stats = self.card_analyzer.get_card_score(card)
                        recommendations['cards_to_add'].append({
                            'card': card,
                            'reason': f"High win rate in your games: {card_stats.get('win_rate', 0):.1f}%",
                            'games_played': card_stats.get('games_played', 0),
                            'win_rate': card_stats.get('win_rate', 0),
                            'source': 'adaptive'
                        })
                    
                    # Synergy improvements
                    synergies = self.card_analyzer.analyze_card_synergies(deck_list)
                    recommendations['synergy_improvements'] = synergies[:3]
                    
                    # Personal performance summary
                    recommendations['personal_performance'] = {
                        'total_matches': stats['total_matches'],
                        'win_rate': stats['win_rate'],
                        'data_quality': 'Good' if stats['total_matches'] >= 10 else 'Limited'
                    }
                else:
                    recommendations['personal_performance'] = {
                        'total_matches': stats['total_matches'],
                        'message': f"Need {5 - stats['total_matches']} more matches for adaptive recommendations"
                    }
                    
            except Exception as e:
                print(f"⚠️ Adaptive analysis failed: {e}")
                import traceback
                traceback.print_exc()
        
        return recommendations
    
    def get_best_cards_for_strategy(self, strategy, format_type="Commander", top_n=10):
        """
        Get best cards for a strategy based on YOUR actual results
        
        Args:
            strategy: Deck strategy (aggro, control, etc.)
            format_type: Format
            top_n: Number of cards to return
            
        Returns:
            List of (card_name, win_rate, games_played) tuples
        """
        if not self.card_analyzer or not self.match_tracker:
            return []
        
        try:
            # Get MVP cards from your games
            mvp_cards = self.card_analyzer.identify_mvp_cards(top_n=top_n * 2)
            
            # Filter by strategy if possible (would need strategy tagging in match data)
            # For now, return top performers
            results = []
            for card, score in mvp_cards[:top_n]:
                card_stats = self.card_analyzer.get_card_score(card)
                results.append((
                    card,
                    card_stats.get('win_rate', 0),
                    card_stats.get('games_played', 0)
                ))
            
            return results
        except Exception as e:
            print(f"⚠️ Could not get best cards: {e}")
            return []
    
    def suggest_deck_for_meta(self, format_type="Commander", strategy="balanced", collection=None):
        """
        Suggest optimal deck combining meta analysis and personal performance
        
        Args:
            format_type: Format
            strategy: Strategy
            collection: Available cards (dict of card_name: count)
            
        Returns:
            dict with deck suggestion
        """
        suggestion = {
            'format': format_type,
            'strategy': strategy,
            'recommended_deck': [],
            'reasoning': []
        }
        
        # Get cards that perform well for YOU
        personal_best = self.get_best_cards_for_strategy(strategy, format_type, top_n=20)
        
        if personal_best:
            suggestion['reasoning'].append(
                f"Based on YOUR {len(personal_best)} best performing cards"
            )
            suggestion['recommended_deck'] = [card for card, _, _ in personal_best]
        
        # Add meta considerations if available
        if self.static_optimizer:
            try:
                meta_deck = self.static_optimizer.build_optimal_deck(
                    collection or {}, format_type, strategy
                )
                suggestion['reasoning'].append("Enhanced with current meta analysis")
                
                # Blend personal best with meta recommendations
                if personal_best:
                    # Weight personal performance higher
                    for card in meta_deck[:10]:
                        if card not in suggestion['recommended_deck']:
                            suggestion['recommended_deck'].append(card)
                else:
                    # No personal data, use meta
                    suggestion['recommended_deck'] = meta_deck
            except Exception as e:
                print(f"⚠️ Meta analysis failed: {e}")
        
        return suggestion
    
    def adjust_weights(self, static_weight=None, adaptive_weight=None):
        """
        Adjust weights for combining static and adaptive recommendations
        
        Args:
            static_weight: Weight for meta-based recommendations (0-1)
            adaptive_weight: Weight for personal results (0-1)
        """
        if static_weight is not None:
            self.static_weight = max(0, min(1, static_weight))
        
        if adaptive_weight is not None:
            self.adaptive_weight = max(0, min(1, adaptive_weight))
        
        # Normalize to sum to 1
        total = self.static_weight + self.adaptive_weight
        if total > 0:
            self.static_weight /= total
            self.adaptive_weight /= total
    
    def get_optimization_summary(self, deck_list):
        """
        Get a quick summary of optimization opportunities
        
        Args:
            deck_list: List of card names
            
        Returns:
            str summary
        """
        if not self.card_analyzer or not self.match_tracker:
            return "Match learning system not available"
        
        stats = self.match_tracker.get_statistics()
        
        if stats['total_matches'] < 5:
            return f"Record {5 - stats['total_matches']} more matches to unlock adaptive optimization"
        
        report = self.card_analyzer.generate_deck_optimization_report(deck_list)
        
        summary = f"📊 OPTIMIZATION SUMMARY\n"
        summary += f"Matches analyzed: {stats['total_matches']}\n"
        summary += f"Overall win rate: {stats['win_rate']:.1f}%\n\n"
        
        remove_count = len(report.get('cards_to_remove', []))
        add_count = len(report.get('cards_to_add', []))
        
        summary += f"💡 Found {remove_count} underperforming cards\n"
        summary += f"✨ Identified {add_count} high-performing alternatives\n"
        
        return summary


# Convenience function
def create_adaptive_optimizer(static_optimizer=None):
    """Create an adaptive optimizer with all systems initialized"""
    if not LEARNING_AVAILABLE:
        print("⚠️ Match learning system not available - using static optimizer only")
        return None
    
    match_tracker = MatchTracker()
    card_analyzer = CardPerformanceAnalyzer(match_tracker)
    
    return AdaptiveDeckOptimizer(
        static_optimizer=static_optimizer,
        match_tracker=match_tracker,
        card_analyzer=card_analyzer
    )


if __name__ == "__main__":
    print("🧠 Adaptive Deck Optimizer")
    print("=" * 60)
    print("\nThis system combines:")
    print("  • Static meta analysis (what's good in the format)")
    print("  • Adaptive learning (what works for YOU)")
    print("\nThe more matches you record, the better the recommendations!")
    print("\n✅ Import this into NEXUS to enhance deck building")
