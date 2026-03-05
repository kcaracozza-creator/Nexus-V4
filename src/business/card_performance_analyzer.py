#!/usr/bin/env python3
"""
Card Performance Analyzer - Deep analysis of individual card effectiveness
Uses match tracking data to identify high/low performers and synergies
"""

import json
import os
from collections import defaultdict
import statistics


class CardPerformanceAnalyzer:
    """Analyze individual card performance from match history"""
    
    def __init__(self, match_tracker):
        self.tracker = match_tracker
        self.card_data = match_tracker.match_history['card_stats']
        
    def get_card_score(self, card_name, min_appearances=3):
        """
        Calculate a comprehensive performance score for a card
        
        Score factors:
        - Win rate (70% weight)
        - Appearance frequency (20% weight)
        - Consistency (10% weight)
        """
        if card_name not in self.card_data:
            return 0.0
        
        stats = self.card_data[card_name]
        
        if stats['appearances'] < min_appearances:
            return 0.0
        
        # Win rate component (0-100 normalized to 0-1)
        win_rate_score = stats['win_rate'] / 100.0
        
        # Frequency component (how often it appears)
        max_appearances = max(s['appearances'] for s in self.card_data.values())
        frequency_score = stats['appearances'] / max_appearances if max_appearances > 0 else 0
        
        # Consistency (variance in performance)
        consistency_score = self._calculate_consistency(card_name)
        
        # Weighted total
        total_score = (
            win_rate_score * 0.70 +
            frequency_score * 0.20 +
            consistency_score * 0.10
        ) * 100
        
        return total_score
    
    def _calculate_consistency(self, card_name):
        """Calculate how consistently a card performs"""
        # Get all matches with this card
        matches_with_card = [
            m for m in self.tracker.match_history['matches']
            if card_name in m['deck_list']
        ]
        
        if len(matches_with_card) < 3:
            return 0.5  # Neutral score for insufficient data
        
        # Calculate win rate in recent matches vs overall
        recent_matches = matches_with_card[-10:]  # Last 10 matches
        recent_wins = sum(1 for m in recent_matches if m['result'] == 'win')
        recent_wr = recent_wins / len(recent_matches)
        
        overall_wr = self.card_data[card_name]['win_rate'] / 100.0
        
        # Consistency = how close recent performance is to overall
        consistency = 1.0 - abs(recent_wr - overall_wr)
        return consistency
    
    def identify_mvp_cards(self, min_appearances=5, limit=20):
        """
        Identify MVP (Most Valuable Player) cards
        These are cards that consistently contribute to wins
        """
        mvp_cards = []
        
        for card, stats in self.card_data.items():
            if stats['appearances'] < min_appearances:
                continue
            
            score = self.get_card_score(card, min_appearances)
            
            mvp_cards.append({
                'card': card,
                'score': score,
                'win_rate': stats['win_rate'],
                'appearances': stats['appearances'],
                'wins': stats['wins']
            })
        
        # Sort by score descending
        mvp_cards.sort(key=lambda x: x['score'], reverse=True)
        
        return mvp_cards[:limit]
    
    def identify_underperformers(self, min_appearances=5, max_win_rate=35, limit=20):
        """
        Identify underperforming cards that should be cut
        """
        underperformers = []
        
        for card, stats in self.card_data.items():
            if stats['appearances'] < min_appearances:
                continue
            
            if stats['win_rate'] <= max_win_rate:
                underperformers.append({
                    'card': card,
                    'win_rate': stats['win_rate'],
                    'appearances': stats['appearances'],
                    'losses': stats['losses']
                })
        
        # Sort by win rate ascending
        underperformers.sort(key=lambda x: x['win_rate'])
        
        return underperformers[:limit]
    
    def analyze_card_synergies(self, card_name, min_co_appearances=3):
        """
        Find cards that perform well when played with this card
        """
        synergies = defaultdict(lambda: {'together_wins': 0, 'together_losses': 0})
        
        # Find matches with this card
        matches_with_card = [
            m for m in self.tracker.match_history['matches']
            if card_name in m['deck_list']
        ]
        
        for match in matches_with_card:
            result = match['result']
            
            # Count co-occurrences
            for other_card in match['deck_list']:
                if other_card != card_name:
                    if result == 'win':
                        synergies[other_card]['together_wins'] += 1
                    else:
                        synergies[other_card]['together_losses'] += 1
        
        # Calculate synergy scores
        synergy_list = []
        for other_card, stats in synergies.items():
            total = stats['together_wins'] + stats['together_losses']
            
            if total < min_co_appearances:
                continue
            
            together_wr = (stats['together_wins'] / total) * 100
            
            # Compare to card's solo performance
            solo_wr = self.card_data.get(other_card, {}).get('win_rate', 50)
            
            synergy_bonus = together_wr - solo_wr
            
            synergy_list.append({
                'card': other_card,
                'together_win_rate': together_wr,
                'solo_win_rate': solo_wr,
                'synergy_bonus': synergy_bonus,
                'co_appearances': total
            })
        
        # Sort by synergy bonus
        synergy_list.sort(key=lambda x: x['synergy_bonus'], reverse=True)
        
        return synergy_list[:10]
    
    def analyze_card_by_matchup(self, card_name):
        """Analyze how a card performs against different opponent archetypes"""
        matchup_data = defaultdict(lambda: {'wins': 0, 'losses': 0})
        
        matches_with_card = [
            m for m in self.tracker.match_history['matches']
            if card_name in m['deck_list']
        ]
        
        for match in matches_with_card:
            opponent = match['opponent_deck']
            
            if match['result'] == 'win':
                matchup_data[opponent]['wins'] += 1
            else:
                matchup_data[opponent]['losses'] += 1
        
        # Calculate win rates
        matchup_analysis = []
        for opponent, stats in matchup_data.items():
            total = stats['wins'] + stats['losses']
            wr = (stats['wins'] / total) * 100
            
            matchup_analysis.append({
                'opponent': opponent,
                'win_rate': wr,
                'record': f"{stats['wins']}-{stats['losses']}",
                'matches': total
            })
        
        matchup_analysis.sort(key=lambda x: x['win_rate'], reverse=True)
        return matchup_analysis
    
    def get_replacement_suggestions(self, card_name, count=5):
        """
        Suggest replacement cards based on similar role but better performance
        """
        if card_name not in self.card_data:
            return []
        
        target_stats = self.card_data[card_name]
        target_wr = target_stats['win_rate']
        
        # Find cards with better win rate
        better_cards = []
        
        for other_card, stats in self.card_data.items():
            if other_card == card_name:
                continue
            
            if stats['win_rate'] > target_wr and stats['appearances'] >= 3:
                improvement = stats['win_rate'] - target_wr
                
                better_cards.append({
                    'card': other_card,
                    'win_rate': stats['win_rate'],
                    'improvement': improvement,
                    'appearances': stats['appearances']
                })
        
        better_cards.sort(key=lambda x: x['improvement'], reverse=True)
        return better_cards[:count]
    
    def generate_deck_optimization_report(self, deck_name):
        """Generate comprehensive optimization report for a deck"""
        deck_stats = self.tracker.match_history['deck_stats'].get(deck_name)
        
        if not deck_stats:
            return None
        
        # Get deck's card list from most recent match
        recent_match = None
        for match in reversed(self.tracker.match_history['matches']):
            if match['deck_name'] == deck_name:
                recent_match = match
                break
        
        if not recent_match:
            return None
        
        deck_list = recent_match['deck_list']
        
        report = {
            'deck_name': deck_name,
            'current_stats': deck_stats,
            'mvp_cards': [],
            'cards_to_cut': [],
            'suggested_additions': [],
            'optimization_score': 0.0
        }
        
        # Identify MVPs in this deck
        for card in set(deck_list):
            if card in self.card_data:
                stats = self.card_data[card]
                if stats['appearances'] >= 3 and stats['win_rate'] > 55:
                    report['mvp_cards'].append({
                        'card': card,
                        'win_rate': stats['win_rate']
                    })
        
        # Identify cards to cut
        for card in set(deck_list):
            if card in self.card_data:
                stats = self.card_data[card]
                if stats['appearances'] >= 3 and stats['win_rate'] < 40:
                    report['cards_to_cut'].append({
                        'card': card,
                        'win_rate': stats['win_rate'],
                        'replacements': self.get_replacement_suggestions(card, 3)
                    })
        
        # Calculate optimization score
        if report['mvp_cards']:
            avg_mvp_wr = statistics.mean([c['win_rate'] for c in report['mvp_cards']])
            report['optimization_score'] = avg_mvp_wr
        
        return report
    
    def print_card_analysis(self, card_name):
        """Print detailed analysis for a specific card"""
        if card_name not in self.card_data:
            print(f"❌ No data found for {card_name}")
            return
        
        stats = self.card_data[card_name]
        score = self.get_card_score(card_name)
        
        print("\n" + "="*60)
        print(f"🎴 CARD ANALYSIS: {card_name}")
        print("="*60)
        
        print(f"\n📊 Performance Statistics:")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Record: {stats['wins']}-{stats['losses']}")
        print(f"   Appearances: {stats['appearances']} matches")
        print(f"   Performance Score: {score:.1f}/100")
        
        # Grade
        if score >= 80:
            grade = "🌟 S-Tier (MVP)"
        elif score >= 65:
            grade = "⭐ A-Tier (Strong)"
        elif score >= 50:
            grade = "✅ B-Tier (Good)"
        elif score >= 35:
            grade = "⚠️  C-Tier (Mediocre)"
        else:
            grade = "❌ D-Tier (Cut)"
        
        print(f"   Grade: {grade}")
        
        # Synergies
        synergies = self.analyze_card_synergies(card_name, min_co_appearances=2)
        if synergies:
            print(f"\n🔗 Best Synergies:")
            for i, syn in enumerate(synergies[:5], 1):
                print(f"   {i}. {syn['card']}: +{syn['synergy_bonus']:.1f}% win rate")
        
        # Matchup analysis
        matchups = self.analyze_card_by_matchup(card_name)
        if matchups:
            print(f"\n⚔️  Matchup Performance:")
            for matchup in matchups[:3]:
                print(f"   vs {matchup['opponent']}: {matchup['win_rate']:.1f}% "
                      f"({matchup['record']})")
        
        # Recommendations
        if stats['win_rate'] < 40:
            replacements = self.get_replacement_suggestions(card_name, 3)
            if replacements:
                print(f"\n💡 Consider Replacing With:")
                for rep in replacements:
                    print(f"   • {rep['card']}: {rep['win_rate']:.1f}% WR "
                          f"(+{rep['improvement']:.1f}% improvement)")
        
        print()


if __name__ == '__main__':
    # Example usage
    from match_tracker import MatchTracker
    
    tracker = MatchTracker('match_history.json')
    analyzer = CardPerformanceAnalyzer(tracker)
    
    # Show MVP cards
    mvps = analyzer.identify_mvp_cards(min_appearances=3, limit=10)
    
    print("\n⭐ MVP CARDS:")
    for i, mvp in enumerate(mvps, 1):
        print(f"{i}. {mvp['card']}: Score {mvp['score']:.1f} "
              f"({mvp['win_rate']:.1f}% WR in {mvp['appearances']} matches)")
    
    # Show underperformers
    underperformers = analyzer.identify_underperformers(min_appearances=3)
    
    if underperformers:
        print(f"\n❌ UNDERPERFORMING CARDS:")
        for card in underperformers[:5]:
            print(f"• {card['card']}: {card['win_rate']:.1f}% WR "
                  f"({card['losses']} losses in {card['appearances']} matches)")
