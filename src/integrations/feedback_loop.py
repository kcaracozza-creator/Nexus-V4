#!/usr/bin/env python3
"""
AI Feedback Loop - Continuous learning system that improves from every match
Automatically updates deck building weights and strategies based on results
"""

import json
import os
from datetime import datetime
from collections import defaultdict


class AIFeedbackLoop:
    """
    Continuous learning system that adapts deck building based on match results
    """
    
    def __init__(self, match_tracker, card_analyzer, ml_optimizer=None):
        self.tracker = match_tracker
        self.analyzer = card_analyzer
        self.ml_optimizer = ml_optimizer
        
        # Learning parameters (automatically adjusted)
        self.weights_file = 'ai_weights.json'
        self.weights = self.load_weights()
        
        # Performance thresholds for auto-adjustment
        self.win_rate_target = 55.0  # Target win rate
        self.learning_rate = 0.05    # How fast to adapt
        
    def load_weights(self):
        """Load AI weights from file"""
        if os.path.exists(self.weights_file):
            try:
                with open(self.weights_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Error loading weights: {e}")
        
        # Default weights
        return {
            'card_selection': {
                'win_rate': 0.70,      # Prefer high win-rate cards
                'synergy': 0.20,       # Consider card synergies
                'versatility': 0.10    # Balance for different matchups
            },
            'strategy_preference': {
                'aggro': 1.0,
                'control': 1.0,
                'combo': 1.0,
                'midrange': 1.0,
                'tempo': 1.0
            },
            'format_adaptation': {
                'Commander': 1.0,
                'Brawl': 1.0,
                'Standard': 1.0,
                'Modern': 1.0,
                'Pioneer': 1.0,
                'Legacy': 1.0,
                'Vintage': 1.0,
                'Pauper': 1.0
            },
            'learning_stats': {
                'total_updates': 0,
                'last_update': None,
                'avg_win_rate': 50.0
            }
        }
    
    def save_weights(self):
        """Save AI weights to file"""
        try:
            with open(self.weights_file, 'w', encoding='utf-8') as f:
                json.dump(self.weights, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error saving weights: {e}")
            return False
    
    def process_match_result(self, match_id):
        """
        Process a match result and update AI weights
        Called automatically after each match
        """
        matches = self.tracker.match_history['matches']
        
        if match_id > len(matches):
            print(f"❌ Invalid match ID: {match_id}")
            return False
        
        match = matches[match_id - 1]
        
        print(f"\n🤖 AI Learning from Match #{match_id}...")
        
        # Update strategy weights
        self._update_strategy_weights(match)
        
        # Update format weights
        self._update_format_weights(match)
        
        # Update card selection criteria
        self._update_card_selection_weights(match)
        
        # Update learning stats
        self.weights['learning_stats']['total_updates'] += 1
        self.weights['learning_stats']['last_update'] = datetime.now().isoformat()
        
        # Calculate current average win rate
        total_matches = len(matches)
        total_wins = sum(1 for m in matches if m['result'] == 'win')
        self.weights['learning_stats']['avg_win_rate'] = (total_wins / total_matches) * 100
        
        self.save_weights()
        
        print(f"✅ AI weights updated (Update #{self.weights['learning_stats']['total_updates']})")
        print(f"   Current Win Rate: {self.weights['learning_stats']['avg_win_rate']:.1f}%")
        
        return True
    
    def _update_strategy_weights(self, match):
        """Adjust strategy preferences based on match outcome"""
        strategy = match['strategy']
        result = match['result']
        
        if result == 'win':
            # Increase weight for winning strategy
            adjustment = self.learning_rate
        else:
            # Decrease weight for losing strategy
            adjustment = -self.learning_rate
        
        current_weight = self.weights['strategy_preference'][strategy]
        new_weight = max(0.5, min(2.0, current_weight + adjustment))
        
        self.weights['strategy_preference'][strategy] = new_weight
        
        print(f"   Strategy '{strategy}': {current_weight:.3f} → {new_weight:.3f}")
    
    def _update_format_weights(self, match):
        """Adjust format preferences based on match outcome"""
        format_type = match['format']
        result = match['result']
        
        if result == 'win':
            adjustment = self.learning_rate * 0.5  # Smaller adjustment for formats
        else:
            adjustment = -self.learning_rate * 0.5
        
        current_weight = self.weights['format_adaptation'][format_type]
        new_weight = max(0.5, min(2.0, current_weight + adjustment))
        
        self.weights['format_adaptation'][format_type] = new_weight
    
    def _update_card_selection_weights(self, match):
        """Adjust card selection criteria based on match outcome"""
        result = match['result']
        deck_list = match['deck_list']
        
        # Calculate deck's average card performance
        avg_card_wr = 0
        card_count = 0
        
        for card in set(deck_list):
            if card in self.analyzer.card_data:
                stats = self.analyzer.card_data[card]
                if stats['appearances'] >= 2:
                    avg_card_wr += stats['win_rate']
                    card_count += 1
        
        if card_count > 0:
            avg_card_wr /= card_count
            
            # If high-win-rate cards led to win, increase win_rate weight
            if result == 'win' and avg_card_wr > 55:
                self.weights['card_selection']['win_rate'] += self.learning_rate * 0.3
                self.weights['card_selection']['win_rate'] = min(0.9, self.weights['card_selection']['win_rate'])
            
            # If low-win-rate cards led to loss, increase synergy weight
            elif result == 'loss' and avg_card_wr < 45:
                self.weights['card_selection']['synergy'] += self.learning_rate * 0.3
                self.weights['card_selection']['synergy'] = min(0.5, self.weights['card_selection']['synergy'])
        
        # Normalize weights to sum to 1.0
        total = sum(self.weights['card_selection'].values())
        for key in self.weights['card_selection']:
            self.weights['card_selection'][key] /= total
    
    def auto_retrain_ml_model(self, min_new_matches=10):
        """
        Automatically retrain ML model when enough new data is available
        """
        if self.ml_optimizer is None:
            return False
        
        total_matches = len(self.tracker.match_history['matches'])
        last_training = self.weights['learning_stats'].get('last_ml_training', 0)
        
        new_matches = total_matches - last_training
        
        if new_matches >= min_new_matches:
            print(f"\n🔄 Auto-retraining ML model ({new_matches} new matches)...")
            
            success = self.ml_optimizer.train_model()
            
            if success:
                self.weights['learning_stats']['last_ml_training'] = total_matches
                self.ml_optimizer.save_model()
                self.save_weights()
                print("✅ ML model retrained and saved!")
                return True
        
        return False
    
    def get_adaptive_card_weights(self, format_type, strategy):
        """
        Get current card selection weights adapted for format and strategy
        """
        base_weights = self.weights['card_selection'].copy()
        
        # Apply format multiplier
        format_mult = self.weights['format_adaptation'].get(format_type, 1.0)
        
        # Apply strategy multiplier
        strategy_mult = self.weights['strategy_preference'].get(strategy, 1.0)
        
        # Combined multiplier
        combined_mult = (format_mult + strategy_mult) / 2.0
        
        # Adjust weights
        for key in base_weights:
            base_weights[key] *= combined_mult
        
        # Normalize
        total = sum(base_weights.values())
        for key in base_weights:
            base_weights[key] /= total
        
        return base_weights
    
    def generate_learning_report(self):
        """Generate a comprehensive learning report"""
        stats = self.weights['learning_stats']
        
        print("\n" + "="*60)
        print("🤖 AI LEARNING REPORT")
        print("="*60)
        
        print(f"\n📊 Learning Statistics:")
        print(f"   Total Updates: {stats['total_updates']}")
        print(f"   Current Win Rate: {stats['avg_win_rate']:.1f}%")
        print(f"   Target Win Rate: {self.win_rate_target:.1f}%")
        
        if stats['avg_win_rate'] >= self.win_rate_target:
            print(f"   Status: ✅ Target achieved!")
        else:
            gap = self.win_rate_target - stats['avg_win_rate']
            print(f"   Status: 📈 {gap:.1f}% below target")
        
        # Strategy preferences
        print(f"\n🎯 Strategy Preferences (Learned):")
        strategies = sorted(self.weights['strategy_preference'].items(),
                          key=lambda x: x[1], reverse=True)
        for strategy, weight in strategies:
            bar = "█" * int(weight * 20)
            print(f"   {strategy:12s}: {weight:.2f} {bar}")
        
        # Format adaptations
        print(f"\n🎴 Format Adaptations (Learned):")
        formats = sorted(self.weights['format_adaptation'].items(),
                        key=lambda x: x[1], reverse=True)
        for fmt, weight in formats[:5]:  # Top 5
            bar = "█" * int(weight * 20)
            print(f"   {fmt:12s}: {weight:.2f} {bar}")
        
        # Card selection weights
        print(f"\n📋 Card Selection Criteria:")
        for criterion, weight in self.weights['card_selection'].items():
            percentage = weight * 100
            print(f"   {criterion:15s}: {percentage:5.1f}%")
        
        print()
    
    def suggest_next_deck(self):
        """
        Use learned weights to suggest the best deck configuration
        """
        # Find best performing format
        best_format = max(self.weights['format_adaptation'].items(),
                         key=lambda x: x[1])[0]
        
        # Find best performing strategy
        best_strategy = max(self.weights['strategy_preference'].items(),
                           key=lambda x: x[1])[0]
        
        # Get format performance data
        format_perf = self.tracker.get_format_performance(best_format)
        strategy_perf = self.tracker.get_strategy_performance(best_strategy)
        
        print("\n" + "="*60)
        print("💡 AI RECOMMENDATION: Next Deck to Build")
        print("="*60)
        
        print(f"\n🎯 Suggested Format: {best_format}")
        if format_perf:
            print(f"   Your Record: {format_perf['wins']}-{format_perf['losses']} "
                  f"({format_perf['win_rate']:.1f}% WR)")
        
        print(f"\n🎲 Suggested Strategy: {best_strategy}")
        if strategy_perf:
            print(f"   Your Record: {strategy_perf['wins']}-{strategy_perf['losses']} "
                  f"({strategy_perf['win_rate']:.1f}% WR)")
        
        # Get top performing cards
        top_cards = self.analyzer.identify_mvp_cards(min_appearances=3, limit=10)
        
        if top_cards:
            print(f"\n⭐ Include These MVP Cards:")
            for i, mvp in enumerate(top_cards[:10], 1):
                print(f"   {i:2d}. {mvp['card']:30s} "
                      f"({mvp['win_rate']:.1f}% WR)")
        
        print()
        
        return {
            'format': best_format,
            'strategy': best_strategy,
            'mvp_cards': [c['card'] for c in top_cards[:10]]
        }
    
    def continuous_learning_cycle(self):
        """
        Run a full continuous learning cycle
        - Process recent matches
        - Update weights
        - Retrain ML model if needed
        - Generate report
        """
        print("\n" + "="*60)
        print("🔄 CONTINUOUS LEARNING CYCLE")
        print("="*60)
        
        matches = self.tracker.match_history['matches']
        
        if not matches:
            print("❌ No matches to learn from")
            return
        
        # Process any unprocessed matches
        last_processed = self.weights['learning_stats'].get('last_processed_match', 0)
        new_matches = len(matches) - last_processed
        
        if new_matches > 0:
            print(f"\n📚 Processing {new_matches} new matches...")
            
            for i in range(last_processed + 1, len(matches) + 1):
                self.process_match_result(i)
            
            self.weights['learning_stats']['last_processed_match'] = len(matches)
            self.save_weights()
        
        # Auto-retrain ML model
        if self.ml_optimizer:
            self.auto_retrain_ml_model(min_new_matches=10)
        
        # Generate report
        self.generate_learning_report()
        
        # Suggest next deck
        self.suggest_next_deck()


if __name__ == '__main__':
    # Example usage
    from match_tracker import MatchTracker
    from card_performance_analyzer import CardPerformanceAnalyzer
    
    try:
        from ml_deck_optimizer import MLDeckOptimizer, SKLEARN_AVAILABLE
    except ImportError:
        MLDeckOptimizer = None
        SKLEARN_AVAILABLE = False
    
    tracker = MatchTracker('match_history.json')
    analyzer = CardPerformanceAnalyzer(tracker)
    
    ml_opt = None
    if SKLEARN_AVAILABLE and MLDeckOptimizer:
        ml_opt = MLDeckOptimizer(tracker, analyzer)
    
    feedback_loop = AIFeedbackLoop(tracker, analyzer, ml_opt)
    
    # Run continuous learning
    feedback_loop.continuous_learning_cycle()
