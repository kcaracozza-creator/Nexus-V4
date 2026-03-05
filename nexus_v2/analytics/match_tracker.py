#!/usr/bin/env python3
"""
Match Tracker - Record and analyze gameplay results for AI learning
Tracks wins/losses, deck performance, and card effectiveness
"""

import json
import os
from datetime import datetime
from collections import defaultdict
import statistics


class MatchTracker:
    """Track match results and deck performance for AI learning"""
    
    def __init__(self, data_file='match_history.json'):
        self.data_file = data_file
        self.match_history = self.load_history()
        
    def load_history(self):
        """Load match history from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Error loading match history: {e}")
                return {'matches': [], 'deck_stats': {}, 'card_stats': {}}
        else:
            return {'matches': [], 'deck_stats': {}, 'card_stats': {}}
    
    def save_history(self):
        """Save match history to JSON file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.match_history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error saving match history: {e}")
            return False
    
    def record_match(self, deck_name, deck_list, opponent_deck, 
                     result, format_type, strategy, turns=0, notes=''):
        """
        Record a match result
        
        Args:
            deck_name: Name of your deck
            deck_list: List of cards in your deck
            opponent_deck: Opponent's deck archetype
            result: 'win' or 'loss'
            format_type: Commander, Standard, Modern, etc.
            strategy: aggro, control, combo, midrange, etc.
            turns: Number of turns the game lasted
            notes: Additional notes about the match
        """
        match_id = len(self.match_history['matches']) + 1
        
        match_data = {
            'match_id': match_id,
            'timestamp': datetime.now().isoformat(),
            'deck_name': deck_name,
            'deck_list': deck_list,
            'opponent_deck': opponent_deck,
            'result': result,
            'format': format_type,
            'strategy': strategy,
            'turns': turns,
            'notes': notes
        }
        
        self.match_history['matches'].append(match_data)
        
        # Update deck statistics
        self._update_deck_stats(deck_name, result, format_type, strategy)
        
        # Update card statistics
        self._update_card_stats(deck_list, result)
        
        self.save_history()
        
        print(f"✅ Match recorded: {deck_name} vs {opponent_deck} - {result.upper()}")
        return match_id
    
    def _update_deck_stats(self, deck_name, result, format_type, strategy):
        """Update win/loss statistics for a deck"""
        if deck_name not in self.match_history['deck_stats']:
            self.match_history['deck_stats'][deck_name] = {
                'wins': 0,
                'losses': 0,
                'format': format_type,
                'strategy': strategy,
                'win_rate': 0.0,
                'total_matches': 0
            }
        
        stats = self.match_history['deck_stats'][deck_name]
        
        if result == 'win':
            stats['wins'] += 1
        else:
            stats['losses'] += 1
        
        stats['total_matches'] = stats['wins'] + stats['losses']
        stats['win_rate'] = (stats['wins'] / stats['total_matches']) * 100
    
    def _update_card_stats(self, deck_list, result):
        """Update win/loss statistics for each card"""
        for card in deck_list:
            if card not in self.match_history['card_stats']:
                self.match_history['card_stats'][card] = {
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0.0,
                    'appearances': 0
                }
            
            stats = self.match_history['card_stats'][card]
            
            if result == 'win':
                stats['wins'] += 1
            else:
                stats['losses'] += 1
            
            stats['appearances'] = stats['wins'] + stats['losses']
            stats['win_rate'] = (stats['wins'] / stats['appearances']) * 100
    
    def get_deck_performance(self, deck_name):
        """Get performance statistics for a specific deck"""
        return self.match_history['deck_stats'].get(deck_name, None)
    
    def get_card_performance(self, card_name):
        """Get performance statistics for a specific card"""
        return self.match_history['card_stats'].get(card_name, None)
    
    def get_top_performing_cards(self, min_appearances=5, limit=50):
        """
        Get top performing cards by win rate
        
        Args:
            min_appearances: Minimum matches to be considered
            limit: Maximum number of cards to return
        """
        eligible_cards = [
            (card, stats) for card, stats in self.match_history['card_stats'].items()
            if stats['appearances'] >= min_appearances
        ]
        
        # Sort by win rate descending
        sorted_cards = sorted(eligible_cards, 
                            key=lambda x: x[1]['win_rate'], 
                            reverse=True)
        
        return sorted_cards[:limit]
    
    def get_worst_performing_cards(self, min_appearances=5, limit=50):
        """Get worst performing cards by win rate"""
        eligible_cards = [
            (card, stats) for card, stats in self.match_history['card_stats'].items()
            if stats['appearances'] >= min_appearances
        ]
        
        # Sort by win rate ascending
        sorted_cards = sorted(eligible_cards, 
                            key=lambda x: x[1]['win_rate'])
        
        return sorted_cards[:limit]
    
    def get_format_performance(self, format_type):
        """Get overall performance statistics for a format"""
        format_matches = [
            m for m in self.match_history['matches'] 
            if m['format'] == format_type
        ]
        
        if not format_matches:
            return None
        
        wins = sum(1 for m in format_matches if m['result'] == 'win')
        losses = len(format_matches) - wins
        win_rate = (wins / len(format_matches)) * 100
        
        avg_turns = statistics.mean([m['turns'] for m in format_matches if m['turns'] > 0])
        
        return {
            'total_matches': len(format_matches),
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_turns': avg_turns
        }
    
    def get_strategy_performance(self, strategy):
        """Get performance statistics for a strategy"""
        strategy_matches = [
            m for m in self.match_history['matches']
            if m['strategy'] == strategy
        ]
        
        if not strategy_matches:
            return None
        
        wins = sum(1 for m in strategy_matches if m['result'] == 'win')
        losses = len(strategy_matches) - wins
        win_rate = (wins / len(strategy_matches)) * 100
        
        return {
            'total_matches': len(strategy_matches),
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate
        }
    
    def get_learning_insights(self):
        """Generate learning insights from match history"""
        insights = {
            'total_matches': len(self.match_history['matches']),
            'overall_win_rate': 0.0,
            'best_format': None,
            'best_strategy': None,
            'top_cards': [],
            'cards_to_cut': [],
            'recommendations': []
        }
        
        if not self.match_history['matches']:
            return insights
        
        # Overall win rate
        total_wins = sum(1 for m in self.match_history['matches'] if m['result'] == 'win')
        insights['overall_win_rate'] = (total_wins / insights['total_matches']) * 100
        
        # Best format
        formats = set(m['format'] for m in self.match_history['matches'])
        format_performance = {
            fmt: self.get_format_performance(fmt) 
            for fmt in formats
        }
        insights['best_format'] = max(format_performance.items(), 
                                     key=lambda x: x[1]['win_rate'])[0]
        
        # Best strategy
        strategies = set(m['strategy'] for m in self.match_history['matches'])
        strategy_performance = {
            strat: self.get_strategy_performance(strat)
            for strat in strategies
        }
        insights['best_strategy'] = max(strategy_performance.items(),
                                       key=lambda x: x[1]['win_rate'])[0]
        
        # Top performing cards
        insights['top_cards'] = self.get_top_performing_cards(min_appearances=3, limit=20)
        
        # Worst performing cards (candidates for removal)
        insights['cards_to_cut'] = self.get_worst_performing_cards(min_appearances=3, limit=10)
        
        # Generate recommendations
        if insights['overall_win_rate'] < 50:
            insights['recommendations'].append(
                f"Consider switching to {insights['best_strategy']} strategy "
                f"(current best performing)"
            )
        
        if len(insights['cards_to_cut']) > 0:
            insights['recommendations'].append(
                f"Consider replacing underperforming cards "
                f"(win rate < 40%)"
            )
        
        return insights
    
    def export_training_data(self, output_file='training_data.json'):
        """Export match history in format suitable for ML training"""
        training_data = []
        
        for match in self.match_history['matches']:
            # Create feature vector for each match
            features = {
                'format': match['format'],
                'strategy': match['strategy'],
                'deck_composition': self._analyze_deck_composition(match['deck_list']),
                'turns': match['turns'],
                'opponent_archetype': match['opponent_deck']
            }
            
            label = 1 if match['result'] == 'win' else 0
            
            training_data.append({
                'features': features,
                'label': label
            })
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(training_data, f, indent=2)
            print(f"✅ Exported {len(training_data)} training samples to {output_file}")
            return True
        except Exception as e:
            print(f"❌ Error exporting training data: {e}")
            return False
    
    def _analyze_deck_composition(self, deck_list):
        """Analyze deck composition for ML features"""
        # Count card types (would need card type data)
        composition = {
            'total_cards': len(deck_list),
            'unique_cards': len(set(deck_list)),
            'avg_copies': len(deck_list) / len(set(deck_list)) if deck_list else 0
        }
        return composition
    
    def print_summary(self):
        """Print a summary of tracking statistics"""
        print("\n" + "="*60)
        print("📊 MATCH TRACKING SUMMARY")
        print("="*60)
        
        total_matches = len(self.match_history['matches'])
        if total_matches == 0:
            print("No matches recorded yet.")
            return
        
        total_wins = sum(1 for m in self.match_history['matches'] if m['result'] == 'win')
        overall_wr = (total_wins / total_matches) * 100
        
        print(f"\n📈 Overall Statistics:")
        print(f"   Total Matches: {total_matches}")
        print(f"   Wins: {total_wins}")
        print(f"   Losses: {total_matches - total_wins}")
        print(f"   Win Rate: {overall_wr:.1f}%")
        
        print(f"\n🎴 Cards Tracked: {len(self.match_history['card_stats'])}")
        print(f"🎯 Decks Tracked: {len(self.match_history['deck_stats'])}")
        
        # Show top 5 performing cards
        top_cards = self.get_top_performing_cards(min_appearances=3, limit=5)
        if top_cards:
            print(f"\n⭐ Top Performing Cards:")
            for i, (card, stats) in enumerate(top_cards, 1):
                print(f"   {i}. {card}: {stats['win_rate']:.1f}% WR "
                      f"({stats['wins']}-{stats['losses']})")
        
        print()


if __name__ == '__main__':
    # Example usage
    tracker = MatchTracker()
    
    # Example: Record a match
    example_deck = [
        'Lightning Bolt', 'Monastery Swiftspear', 'Goblin Guide',
        'Mountain', 'Mountain', 'Mountain'
    ] * 10  # Simplified 60-card deck
    
    tracker.record_match(
        deck_name='Mono-Red Burn',
        deck_list=example_deck,
        opponent_deck='UW Control',
        result='win',
        format_type='Modern',
        strategy='aggro',
        turns=7,
        notes='Fast aggro win before they stabilized'
    )
    
    tracker.print_summary()
    
    insights = tracker.get_learning_insights()
    print(f"\n🤖 AI Learning Insights:")
    print(f"   Best Format: {insights['best_format']}")
    print(f"   Best Strategy: {insights['best_strategy']}")
