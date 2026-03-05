#!/usr/bin/env python3
"""
ML Deck Optimizer - Machine Learning powered deck building
Uses scikit-learn to learn from match history and build optimal decks
"""

import json
import os
import pickle
from collections import defaultdict, Counter
import random

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import LabelEncoder
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️  scikit-learn not installed. Install with: pip install scikit-learn")


class MLDeckOptimizer:
    """Machine Learning powered deck optimizer using match history"""
    
    def __init__(self, match_tracker, card_analyzer):
        self.tracker = match_tracker
        self.analyzer = card_analyzer
        self.model = None
        self.label_encoders = {}
        self.feature_names = []
        self.is_trained = False
        
        if SKLEARN_AVAILABLE:
            # Use Gradient Boosting for better performance
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
    
    def prepare_training_data(self):
        """
        Prepare training data from match history
        Returns: X (features), y (labels - win/loss)
        """
        if not SKLEARN_AVAILABLE:
            print("❌ scikit-learn required for ML training")
            return None, None
        
        matches = self.tracker.match_history['matches']
        
        if len(matches) < 10:
            print("⚠️  Need at least 10 matches for training")
            return None, None
        
        X = []
        y = []
        
        for match in matches:
            features = self._extract_features(match)
            label = 1 if match['result'] == 'win' else 0
            
            X.append(features)
            y.append(label)
        
        return np.array(X), np.array(y)
    
    def _extract_features(self, match):
        """
        Extract numerical features from a match for ML
        
        Features:
        - Deck composition (creatures, spells, lands)
        - Strategy type (encoded)
        - Format type (encoded)
        - Average card performance scores
        - Deck synergy score
        - Mana curve quality
        """
        deck_list = match['deck_list']
        
        # Basic composition
        total_cards = len(deck_list)
        unique_cards = len(set(deck_list))
        
        # Count card types (simplified - would need card type data)
        # For now, estimate based on collection
        estimated_creatures = int(total_cards * 0.35)  # ~35% creatures
        estimated_spells = int(total_cards * 0.30)     # ~30% spells
        estimated_lands = int(total_cards * 0.35)      # ~35% lands
        
        # Average card performance
        avg_card_score = self._calculate_avg_card_score(deck_list)
        
        # Strategy encoding
        strategy_map = {
            'aggro': 1, 'control': 2, 'combo': 3,
            'midrange': 4, 'tempo': 5, 'balanced': 3
        }
        strategy_encoded = strategy_map.get(match['strategy'], 3)
        
        # Format encoding
        format_map = {
            'Standard': 1, 'Modern': 2, 'Pioneer': 3,
            'Legacy': 4, 'Vintage': 5, 'Commander': 6,
            'Brawl': 7, 'Pauper': 8
        }
        format_encoded = format_map.get(match['format'], 1)
        
        # Game length (normalized)
        turns_normalized = min(match['turns'] / 20.0, 1.0) if match['turns'] > 0 else 0.5
        
        features = [
            total_cards,
            unique_cards,
            estimated_creatures,
            estimated_spells,
            estimated_lands,
            avg_card_score,
            strategy_encoded,
            format_encoded,
            turns_normalized
        ]
        
        self.feature_names = [
            'total_cards', 'unique_cards', 'creatures', 'spells', 'lands',
            'avg_card_score', 'strategy', 'format', 'turns_normalized'
        ]
        
        return features
    
    def _calculate_avg_card_score(self, deck_list):
        """Calculate average performance score of cards in deck"""
        scores = []
        
        for card in set(deck_list):
            score = self.analyzer.get_card_score(card, min_appearances=1)
            if score > 0:
                scores.append(score)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def train_model(self, test_size=0.2):
        """Train the ML model on match history"""
        if not SKLEARN_AVAILABLE:
            print("❌ scikit-learn not installed")
            return False
        
        X, y = self.prepare_training_data()
        
        if X is None or len(X) < 10:
            print("❌ Insufficient training data (need 10+ matches)")
            return False
        
        print(f"\n🤖 Training ML model on {len(X)} matches...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Train model
        self.model.fit(X_train, y_train)
        
        # Evaluate
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)
        
        # Cross-validation
        cv_scores = cross_val_score(self.model, X, y, cv=min(5, len(X)//2))
        
        print(f"✅ Model trained successfully!")
        print(f"   Training Accuracy: {train_score*100:.1f}%")
        print(f"   Testing Accuracy: {test_score*100:.1f}%")
        print(f"   Cross-Val Accuracy: {cv_scores.mean()*100:.1f}% "
              f"(±{cv_scores.std()*100:.1f}%)")
        
        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            print(f"\n📊 Feature Importance:")
            for name, importance in sorted(zip(self.feature_names, importances),
                                          key=lambda x: x[1], reverse=True):
                print(f"   {name}: {importance:.3f}")
        
        self.is_trained = True
        return True
    
    def predict_deck_win_probability(self, deck_list, format_type, strategy):
        """Predict win probability for a deck"""
        if not self.is_trained:
            print("⚠️  Model not trained yet")
            return 0.5
        
        # Create synthetic match for feature extraction
        synthetic_match = {
            'deck_list': deck_list,
            'format': format_type,
            'strategy': strategy,
            'turns': 10  # Average
        }
        
        features = self._extract_features(synthetic_match)
        features_array = np.array([features])
        
        # Get probability prediction
        if hasattr(self.model, 'predict_proba'):
            win_prob = self.model.predict_proba(features_array)[0][1]
        else:
            win_prob = self.model.predict(features_array)[0]
        
        return win_prob
    
    def optimize_deck(self, deck_list, card_pool, format_type, strategy, 
                     iterations=100):
        """
        Use ML to optimize a deck by trying card swaps
        
        Args:
            deck_list: Current deck
            card_pool: Available cards to swap in
            format_type: Commander, Standard, etc.
            strategy: aggro, control, etc.
            iterations: Number of optimization attempts
        """
        if not self.is_trained:
            print("❌ Model must be trained before optimization")
            return deck_list
        
        print(f"\n🔧 Optimizing deck using ML ({iterations} iterations)...")
        
        best_deck = deck_list.copy()
        best_score = self.predict_deck_win_probability(best_deck, format_type, strategy)
        
        print(f"   Starting win probability: {best_score*100:.1f}%")
        
        improvements = 0
        
        for i in range(iterations):
            # Try swapping a random card
            test_deck = best_deck.copy()
            
            # Remove random non-land card
            swap_idx = random.randint(0, len(test_deck) - 1)
            removed_card = test_deck.pop(swap_idx)
            
            # Add random card from pool
            available_pool = [c for c in card_pool if c not in test_deck]
            if not available_pool:
                continue
            
            new_card = random.choice(available_pool)
            test_deck.append(new_card)
            
            # Evaluate new deck
            test_score = self.predict_deck_win_probability(test_deck, format_type, strategy)
            
            # Keep if better
            if test_score > best_score:
                best_deck = test_deck
                best_score = test_score
                improvements += 1
                print(f"   Iteration {i+1}: Improved! Swapped {removed_card} → {new_card} "
                      f"(Win prob: {best_score*100:.1f}%)")
        
        print(f"\n✅ Optimization complete!")
        print(f"   Final win probability: {best_score*100:.1f}%")
        print(f"   Improvements made: {improvements}")
        
        return best_deck
    
    def suggest_deck_improvements(self, deck_name, top_n=10):
        """
        Use ML + analytics to suggest specific deck improvements
        """
        if not self.is_trained:
            print("⚠️  Training model first...")
            self.train_model()
        
        # Get deck stats
        deck_stats = self.tracker.match_history['deck_stats'].get(deck_name)
        if not deck_stats:
            print(f"❌ No data for deck '{deck_name}'")
            return []
        
        # Get most recent deck list
        recent_match = None
        for match in reversed(self.tracker.match_history['matches']):
            if match['deck_name'] == deck_name:
                recent_match = match
                break
        
        if not recent_match:
            return []
        
        deck_list = recent_match['deck_list']
        format_type = recent_match['format']
        strategy = recent_match['strategy']
        
        print(f"\n💡 ML-Powered Improvements for '{deck_name}'")
        print("="*60)
        
        # Current deck analysis
        current_prob = self.predict_deck_win_probability(deck_list, format_type, strategy)
        print(f"\n📊 Current Deck:")
        print(f"   Actual Win Rate: {deck_stats['win_rate']:.1f}%")
        print(f"   Predicted Win Probability: {current_prob*100:.1f}%")
        print(f"   Record: {deck_stats['wins']}-{deck_stats['losses']}")
        
        # Identify weak cards using card analyzer
        suggestions = []
        
        for card in set(deck_list):
            if card in self.analyzer.card_data:
                card_stats = self.analyzer.card_data[card]
                
                if card_stats['appearances'] >= 2 and card_stats['win_rate'] < 45:
                    # Find replacements
                    replacements = self.analyzer.get_replacement_suggestions(card, count=3)
                    
                    if replacements:
                        suggestions.append({
                            'cut': card,
                            'cut_wr': card_stats['win_rate'],
                            'add': replacements[0]['card'],
                            'add_wr': replacements[0]['win_rate'],
                            'improvement': replacements[0]['improvement']
                        })
        
        # Sort by potential improvement
        suggestions.sort(key=lambda x: x['improvement'], reverse=True)
        
        print(f"\n🔄 Suggested Card Swaps (Top {min(top_n, len(suggestions))}):")
        for i, sug in enumerate(suggestions[:top_n], 1):
            print(f"\n   {i}. Cut: {sug['cut']} ({sug['cut_wr']:.1f}% WR)")
            print(f"      Add: {sug['add']} ({sug['add_wr']:.1f}% WR)")
            print(f"      Expected Improvement: +{sug['improvement']:.1f}%")
        
        return suggestions
    
    def save_model(self, filename='ml_deck_model.pkl'):
        """Save trained model to file"""
        if not self.is_trained:
            print("❌ No trained model to save")
            return False
        
        try:
            with open(filename, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'feature_names': self.feature_names,
                    'label_encoders': self.label_encoders
                }, f)
            print(f"✅ Model saved to {filename}")
            return True
        except Exception as e:
            print(f"❌ Error saving model: {e}")
            return False
    
    def load_model(self, filename='ml_deck_model.pkl'):
        """Load trained model from file"""
        if not os.path.exists(filename):
            print(f"❌ Model file not found: {filename}")
            return False
        
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.feature_names = data['feature_names']
                self.label_encoders = data['label_encoders']
            self.is_trained = True
            print(f"✅ Model loaded from {filename}")
            return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False


if __name__ == '__main__':
    # Example usage
    if SKLEARN_AVAILABLE:
        from match_tracker import MatchTracker
        from card_performance_analyzer import CardPerformanceAnalyzer
        
        tracker = MatchTracker('match_history.json')
        analyzer = CardPerformanceAnalyzer(tracker)
        ml_optimizer = MLDeckOptimizer(tracker, analyzer)
        
        # Train model
        if len(tracker.match_history['matches']) >= 10:
            ml_optimizer.train_model()
            ml_optimizer.save_model()
        else:
            print("⚠️  Need at least 10 matches to train ML model")
    else:
        print("\n❌ scikit-learn not installed!")
        print("Install with: pip install scikit-learn numpy")
