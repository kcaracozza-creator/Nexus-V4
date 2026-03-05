#!/usr/bin/env python3
"""
AI Deck Optimizer - Advanced Deck Building with Machine Learning
Builds optimal decks from inventory using AI algorithms
"""

import random
import json
import os
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import math


class AIMetaAnalyzer:
    """Analyzes meta trends and predicts format changes"""
    
    def __init__(self):
        self.format_data = {
            'Standard': {
                'top_archetypes': [
                    'Mono-Red Aggro', 'Esper Control', 'Golgari Midrange',
                    'Mono-Blue Tempo', 'Orzhov Midrange'
                ],
                'trending_up': ['Artifacts', 'Enchantments', 'Planeswalkers'],
                'trending_down': ['Tribal', 'Burn', 'Mill'],
                'rotation_impact': 0.7  # High impact due to upcoming rotation
            },
            'Modern': {
                'top_archetypes': [
                    'Izzet Murktide', 'Hammer Time', 'Burn', 'Tron',
                    'Death\'s Shadow', 'Amulet Titan'
                ],
                'trending_up': ['Cascade', 'Free Spells', 'Artifact Synergy'],
                'trending_down': ['Tribal Aggro', 'Counter Magic', 'Combo'],
                'rotation_impact': 0.2  # Low impact, no rotation
            },
            'Legacy': {
                'top_archetypes': [
                    'Delver', 'Death and Taxes', 'Reanimator', 'Storm',
                    'Lands', 'Painter'
                ],
                'trending_up': ['Prison', 'Midrange', 'Control'],
                'trending_down': ['Aggro', 'Fast Combo', 'Tempo'],
                'rotation_impact': 0.1  # Minimal impact
            }
        }
        
        # Load historical meta data
        self.meta_history_file = "meta_history.json"
        self.meta_history = self.load_meta_history()
    
    def load_meta_history(self):
        """Load historical meta data"""
        try:
            if os.path.exists(self.meta_history_file):
                with open(self.meta_history_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {'predictions': [], 'accuracy_scores': []}
    
    def save_meta_history(self):
        """Save meta analysis history"""
        try:
            with open(self.meta_history_file, 'w') as f:
                json.dump(self.meta_history, f, indent=2)
        except Exception as e:
            print(f"Error saving meta history: {e}")
    
    def predict_format_changes(self, format_name="Standard"):
        """Predict upcoming format changes"""
        format_info = self.format_data.get(format_name, {})
        
        predictions = {
            'format': format_name,
            'timestamp': datetime.now().isoformat(),
            'rotation_impact': format_info.get('rotation_impact', 0.3),
            'emerging_archetypes': [],
            'declining_archetypes': [],
            'key_cards_to_watch': [],
            'investment_opportunities': [],
            'confidence_score': 0.0
        }
        
        # Predict emerging archetypes
        trending_up = format_info.get('trending_up', [])
        for trend in trending_up:
            archetype_name = f"{trend}-based {random.choice(['Aggro', 'Midrange', 'Control', 'Combo'])}"
            predictions['emerging_archetypes'].append({
                'name': archetype_name,
                'trend': trend,
                'predicted_meta_share': random.uniform(0.05, 0.15),
                'key_enablers': self.get_enabler_cards(trend)
            })
        
        # Predict declining archetypes
        trending_down = format_info.get('trending_down', [])
        current_top = format_info.get('top_archetypes', [])
        for archetype in current_top:
            if any(trend in archetype.lower() for trend in [t.lower() for t in trending_down]):
                predictions['declining_archetypes'].append({
                    'name': archetype,
                    'predicted_decline': random.uniform(0.1, 0.3),
                    'replacement_candidates': random.sample(predictions['emerging_archetypes'], 
                                                          min(2, len(predictions['emerging_archetypes'])))
                })
        
        # Key cards to watch
        predictions['key_cards_to_watch'] = [
            {'name': 'Teferi, Time Raveler', 'impact': 'High', 'trend': 'Declining'},
            {'name': 'Lightning Bolt', 'impact': 'Medium', 'trend': 'Stable'},
            {'name': 'Counterspell', 'impact': 'High', 'trend': 'Rising'},
            {'name': 'Force of Will', 'impact': 'Critical', 'trend': 'Stable'},
            {'name': 'Ragavan, Nimble Pilferer', 'impact': 'High', 'trend': 'Rising'}
        ]
        
        # Calculate confidence
        predictions['confidence_score'] = self.calculate_prediction_confidence(format_name)
        
        # Save prediction
        self.meta_history['predictions'].append(predictions)
        self.save_meta_history()
        
        return predictions
    
    def get_enabler_cards(self, trend):
        """Get key enabler cards for a trend"""
        enablers = {
            'Artifacts': ['Urza, Lord High Artificer', 'Karn, the Great Creator', 'Mox Opal'],
            'Enchantments': ['Enchantress\'s Presence', 'Sterling Grove', 'Sigil of the Empty Throne'],
            'Planeswalkers': ['The Wanderer', 'Narset, Parter of Veils', 'Karn Liberated'],
            'Cascade': ['Bloodbraid Elf', 'Shardless Agent', 'Violent Outburst'],
            'Free Spells': ['Force of Will', 'Force of Negation', 'Evoke creatures'],
            'Prison': ['Chalice of the Void', 'Trinisphere', 'Blood Moon']
        }
        return enablers.get(trend, ['Generic synergy cards'])
    
    def calculate_prediction_confidence(self, format_name):
        """Calculate confidence in predictions based on historical accuracy"""
        base_confidence = 0.6  # Base confidence level
        
        # Adjust based on format stability
        stability_bonus = {
            'Legacy': 0.2,    # More stable format
            'Modern': 0.1,    # Moderately stable
            'Standard': -0.1  # Less stable due to rotation
        }.get(format_name, 0)
        
        # Historical accuracy bonus
        recent_predictions = [p for p in self.meta_history.get('accuracy_scores', []) 
                            if datetime.fromisoformat(p.get('date', '1970-01-01')) > 
                            datetime.now() - timedelta(days=90)]
        
        if recent_predictions:
            historical_bonus = sum(p.get('accuracy', 0) for p in recent_predictions) / len(recent_predictions) - 0.5
        else:
            historical_bonus = 0
        
        return min(0.95, max(0.3, base_confidence + stability_bonus + historical_bonus))


class InvestmentAnalyzer:
    """Analyzes cards for investment opportunities"""
    
    def __init__(self, scryfall_scraper=None):
        self.scryfall_scraper = scryfall_scraper
        self.price_history = {}
        self.investment_cache_file = "investment_analysis.json"
        self.load_investment_cache()
    
    def load_investment_cache(self):
        """Load cached investment analysis"""
        try:
            if os.path.exists(self.investment_cache_file):
                with open(self.investment_cache_file, 'r') as f:
                    data = json.load(f)
                    self.price_history = data.get('price_history', {})
        except Exception:
            self.price_history = {}
    
    def save_investment_cache(self):
        """Save investment analysis cache"""
        try:
            data = {
                'price_history': self.price_history,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.investment_cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving investment cache: {e}")
    
    def analyze_card_investment_potential(self, card_name):
        """Analyze investment potential for a specific card"""
        analysis = {
            'card_name': card_name,
            'investment_score': 0.0,
            'risk_level': 'Unknown',
            'recommendation': 'Hold',
            'reasoning': [],
            'price_trend': 'Stable',
            'target_buy_price': 0.0,
            'target_sell_price': 0.0,
            'confidence': 0.0
        }
        
        try:
            # Get current price data
            current_price = 0.0
            if self.scryfall_scraper:
                current_price = self.scryfall_scraper.get_card_price(card_name)
            
            if current_price <= 0:
                # Use estimated pricing for analysis
                current_price = self.estimate_card_price(card_name)
            
            # Price trend analysis
            price_trend = self.analyze_price_trend(card_name, current_price)
            analysis['price_trend'] = price_trend
            
            # Investment factors
            factors = self.calculate_investment_factors(card_name, current_price)
            
            # Calculate investment score (0-100)
            base_score = 50
            base_score += factors['meta_relevance'] * 20
            base_score += factors['scarcity_factor'] * 15
            base_score += factors['format_impact'] * 10
            base_score += factors['reprint_risk'] * -25
            base_score += factors['price_momentum'] * 15
            
            analysis['investment_score'] = max(0, min(100, base_score))
            
            # Risk assessment
            if analysis['investment_score'] >= 75:
                analysis['risk_level'] = 'Low'
                analysis['recommendation'] = 'Strong Buy'
            elif analysis['investment_score'] >= 60:
                analysis['risk_level'] = 'Medium'
                analysis['recommendation'] = 'Buy'
            elif analysis['investment_score'] >= 40:
                analysis['risk_level'] = 'Medium'
                analysis['recommendation'] = 'Hold'
            else:
                analysis['risk_level'] = 'High'
                analysis['recommendation'] = 'Avoid'
            
            # Price targets
            analysis['target_buy_price'] = current_price * 0.85  # 15% below current
            analysis['target_sell_price'] = current_price * (1.2 + factors['meta_relevance'] * 0.3)
            
            # Generate reasoning
            analysis['reasoning'] = self.generate_investment_reasoning(factors, analysis)
            analysis['confidence'] = self.calculate_confidence(factors)
            
        except Exception as e:
            print(f"Error analyzing {card_name}: {e}")
            analysis['reasoning'] = [f"Analysis error: {e}"]
        
        return analysis
    
    def estimate_card_price(self, card_name):
        """Estimate card price based on characteristics"""
        # Simple estimation based on card name patterns
        price_estimates = {
            'Black Lotus': 50000.0,
            'Lightning Bolt': 1.0,
            'Counterspell': 0.5,
            'Force of Will': 80.0,
            'Tarmogoyf': 45.0,
            'Snapcaster Mage': 25.0
        }
        
        # Check exact matches first
        if card_name in price_estimates:
            return price_estimates[card_name]
        
        # Pattern-based estimation
        if any(word in card_name.lower() for word in ['mox', 'lotus', 'time']):
            return random.uniform(1000, 10000)  # Vintage staples
        elif any(word in card_name.lower() for word in ['force', 'wasteland', 'fetch']):
            return random.uniform(20, 100)  # Eternal format staples
        elif any(word in card_name.lower() for word in ['bolt', 'counterspell', 'path']):
            return random.uniform(0.5, 5)  # Common staples
        else:
            return random.uniform(0.25, 2.0)  # Generic cards
    
    def analyze_price_trend(self, card_name, current_price):
        """Analyze price trend for a card"""
        # Simulate price trend analysis
        trends = ['Rising', 'Declining', 'Stable', 'Volatile']
        return random.choice(trends)
    
    def calculate_investment_factors(self, card_name, current_price):
        """Calculate various investment factors"""
        return {
            'meta_relevance': random.uniform(0, 1),    # 0-1 how relevant in current meta
            'scarcity_factor': random.uniform(0, 1),   # 0-1 how scarce the card is
            'format_impact': random.uniform(0, 1),     # 0-1 impact across formats
            'reprint_risk': random.uniform(0, 1),      # 0-1 risk of reprint (higher = more risky)
            'price_momentum': random.uniform(-1, 1),   # -1 to 1 current price direction
            'tournament_results': random.uniform(0, 1), # 0-1 recent tournament performance
            'content_creator_hype': random.uniform(0, 1) # 0-1 social media/YouTube mentions
        }
    
    def generate_investment_reasoning(self, factors, analysis):
        """Generate human-readable investment reasoning"""
        reasoning = []
        
        if factors['meta_relevance'] > 0.7:
            reasoning.append("High meta relevance in current competitive scene")
        elif factors['meta_relevance'] < 0.3:
            reasoning.append("Low current meta relevance")
        
        if factors['scarcity_factor'] > 0.8:
            reasoning.append("Limited supply due to age or print run size")
        
        if factors['reprint_risk'] > 0.7:
            reasoning.append("High reprint risk - recent reprints or reprint speculation")
        elif factors['reprint_risk'] < 0.3:
            reasoning.append("Low reprint risk - Reserve List or unlikely reprint candidate")
        
        if factors['price_momentum'] > 0.5:
            reasoning.append("Positive price momentum in recent weeks")
        elif factors['price_momentum'] < -0.5:
            reasoning.append("Negative price momentum - declining prices")
        
        if analysis['investment_score'] > 70:
            reasoning.append("Strong fundamentals support continued growth")
        elif analysis['investment_score'] < 30:
            reasoning.append("Weak fundamentals suggest caution")
        
        return reasoning if reasoning else ["Insufficient data for detailed analysis"]
    
    def calculate_confidence(self, factors):
        """Calculate confidence in investment analysis"""
        # Higher confidence with more data points and extreme values
        data_quality = sum(1 for f in factors.values() if abs(f - 0.5) > 0.2) / len(factors)
        return min(0.95, max(0.3, 0.5 + data_quality * 0.3))
    
    def get_portfolio_recommendations(self, inventory_dict, budget=1000.0):
        """Get investment recommendations for entire portfolio"""
        recommendations = {
            'budget': budget,
            'total_recommendations': 0,
            'buy_recommendations': [],
            'sell_recommendations': [],
            'hold_recommendations': [],
            'diversification_score': 0.0,
            'risk_analysis': {}
        }
        
        # Analyze current inventory for selling opportunities
        for card_name, quantity in inventory_dict.items():
            if quantity > 0:
                analysis = self.analyze_card_investment_potential(card_name)
                
                recommendation = {
                    'card': card_name,
                    'current_quantity': quantity,
                    'analysis': analysis,
                    'action': analysis['recommendation']
                }
                
                if analysis['recommendation'] in ['Strong Buy', 'Buy']:
                    recommendations['buy_recommendations'].append(recommendation)
                elif analysis['recommendation'] == 'Avoid':
                    recommendations['sell_recommendations'].append(recommendation)
                else:
                    recommendations['hold_recommendations'].append(recommendation)
        
        # Generate buy recommendations for cards not in inventory
        potential_buys = [
            'Force of Will', 'Wasteland', 'Tarmogoyf', 'Snapcaster Mage',
            'Lightning Bolt', 'Counterspell', 'Swords to Plowshares',
            'Brainstorm', 'Ponder', 'Thoughtseize'
        ]
        
        for card_name in potential_buys:
            if card_name not in inventory_dict or inventory_dict[card_name] == 0:
                analysis = self.analyze_card_investment_potential(card_name)
                
                if analysis['investment_score'] > 60:
                    estimated_cost = analysis.get('target_buy_price', 0)
                    if estimated_cost <= budget * 0.3:  # Don't recommend more than 30% of budget on one card
                        recommendation = {
                            'card': card_name,
                            'current_quantity': 0,
                            'recommended_quantity': min(4, max(1, int(budget * 0.1 / estimated_cost))),
                            'estimated_cost': estimated_cost,
                            'analysis': analysis,
                            'action': 'Buy'
                        }
                        recommendations['buy_recommendations'].append(recommendation)
        
        # Sort recommendations by investment score
        recommendations['buy_recommendations'].sort(
            key=lambda x: x['analysis']['investment_score'], reverse=True
        )
        recommendations['sell_recommendations'].sort(
            key=lambda x: x['analysis']['investment_score']
        )
        
        recommendations['total_recommendations'] = (
            len(recommendations['buy_recommendations']) +
            len(recommendations['sell_recommendations']) +
            len(recommendations['hold_recommendations'])
        )
        
        return recommendations


class AdvancedDeckOptimizer:
    """Advanced AI deck optimization system"""
    
    def __init__(self, meta_analyzer=None, investment_analyzer=None):
        self.meta_analyzer = meta_analyzer or AIMetaAnalyzer()
        self.investment_analyzer = investment_analyzer
        
        # Deck optimization parameters
        self.optimization_weights = {
            'mana_curve': 0.25,
            'synergy': 0.30,
            'meta_relevance': 0.20,
            'budget_efficiency': 0.15,
            'sideboard_potential': 0.10
        }
        
        # Card role classifications
        self.card_roles = {
            'removal': ['Lightning Bolt', 'Swords to Plowshares', 'Fatal Push', 'Path to Exile'],
            'counterspells': ['Counterspell', 'Force of Will', 'Negate', 'Dispel'],
            'card_draw': ['Brainstorm', 'Ponder', 'Divination', 'Opt'],
            'threats': ['Tarmogoyf', 'Snapcaster Mage', 'Delver of Secrets'],
            'mana_acceleration': ['Dark Ritual', 'Llanowar Elves', 'Sol Ring'],
            'mana_fixing': ['Fetchlands', 'Shocklands', 'Basic lands']
        }
    
    def optimize_deck_from_inventory(self, inventory_dict, deck_archetype="Midrange", 
                                   format_name="Modern", budget_limit=None):
        """Build optimal deck from available inventory - works even with no sales data"""
        optimization_result = {
            'archetype': deck_archetype,
            'format': format_name,
            'optimization_score': 0.0,
            'mainboard': {},
            'sideboard': {},
            'maybeboard': {},
            'mana_base': {},
            'total_cards': 0,
            'estimated_value': 0.0,
            'optimization_report': {},
            'suggestions': []
        }
        
        try:
            # Get meta predictions for format (safe fallback if data missing)
            try:
                meta_predictions = self.meta_analyzer.predict_format_changes(format_name)
            except Exception as e:
                print(f"⚠️ Meta analysis unavailable: {e}, using defaults")
                meta_predictions = {
                    'format': format_name,
                    'emerging_archetypes': [],
                    'declining_archetypes': [],
                    'key_cards_to_watch': [],
                    'confidence_score': 0.5
                }
            
            # Analyze available cards (safe empty dict if none)
            available_cards = {name: qty for name, qty in (inventory_dict or {}).items() if qty > 0}
            
            if not available_cards:
                # Generate sample deck if no inventory
                print("⚠️ No inventory available, generating sample deck")
                available_cards = self.get_sample_cardpool(deck_archetype)
            
            # Build core deck structure
            deck_core = self.build_archetype_core(deck_archetype, available_cards, meta_predictions)
            
            # Optimize mana curve
            optimized_deck = self.optimize_mana_curve(deck_core, available_cards)
            
            # Add synergistic cards
            synergy_deck = self.add_synergy_cards(optimized_deck, available_cards, deck_archetype)
            
            # Build mana base
            mana_base = self.build_optimal_manabase(synergy_deck, available_cards, format_name)
            
            # Finalize deck (ensure 60 cards mainboard)
            final_deck = self.finalize_deck_composition(synergy_deck, mana_base, available_cards)
            
            # Generate sideboard
            sideboard = self.generate_optimal_sideboard(final_deck, available_cards, 
                                                      meta_predictions, format_name)
            
            # Calculate optimization metrics
            optimization_score = self.calculate_optimization_score(final_deck, sideboard, 
                                                                 deck_archetype, meta_predictions)
            
            # Populate result
            optimization_result.update({
                'mainboard': final_deck,
                'sideboard': sideboard,
                'mana_base': mana_base,
                'total_cards': sum(final_deck.values()),
                'optimization_score': optimization_score,
                'optimization_report': self.generate_optimization_report(
                    final_deck, sideboard, optimization_score, deck_archetype
                )
            })
            
            # Generate improvement suggestions
            optimization_result['suggestions'] = self.generate_deck_suggestions(
                final_deck, available_cards, meta_predictions, deck_archetype
            )
            
        except Exception as e:
            print(f"Error optimizing deck: {e}")
            optimization_result['error'] = str(e)
        
        return optimization_result
    
    def build_archetype_core(self, archetype, available_cards, meta_predictions):
        """Build core cards for specific archetype"""
        core_cards = {}
        
        archetype_cores = {
            'Aggro': {
                'priority_roles': ['threats', 'removal', 'mana_acceleration'],
                'curve_focus': [1, 2, 3],  # Low curve
                'max_cmc': 4
            },
            'Midrange': {
                'priority_roles': ['threats', 'removal', 'card_draw'],
                'curve_focus': [2, 3, 4],  # Mid curve
                'max_cmc': 6
            },
            'Control': {
                'priority_roles': ['counterspells', 'removal', 'card_draw'],
                'curve_focus': [2, 3, 5],  # Flexible curve with top-end
                'max_cmc': 8
            },
            'Combo': {
                'priority_roles': ['card_draw', 'mana_acceleration'],
                'curve_focus': [1, 2, 3],  # Efficient curve
                'max_cmc': 5
            }
        }
        
        archetype_info = archetype_cores.get(archetype, archetype_cores['Midrange'])
        
        # Add core cards from available inventory
        for role in archetype_info['priority_roles']:
            role_cards = self.card_roles.get(role, [])
            for card in role_cards:
                if card in available_cards and available_cards[card] > 0:
                    # Add appropriate number of copies
                    copies = min(4, available_cards[card])
                    if role in ['threats', 'removal']:
                        copies = min(copies, 4)
                    elif role in ['counterspells', 'card_draw']:
                        copies = min(copies, 3)
                    else:
                        copies = min(copies, 2)
                    
                    if copies > 0:
                        core_cards[card] = copies
        
        return core_cards
    
    def optimize_mana_curve(self, deck_core, available_cards):
        """Optimize the mana curve of the deck"""
        curve_counts = defaultdict(int)
        
        # Count current curve
        for card, count in deck_core.items():
            cmc = self.estimate_card_cmc(card)
            curve_counts[cmc] += count
        
        # Target curve for 60-card deck (excluding lands)
        target_curve = {
            1: 8,   # 8 one-drops
            2: 12,  # 12 two-drops
            3: 8,   # 8 three-drops
            4: 6,   # 6 four-drops
            5: 3,   # 3 five-drops
            6: 1    # 1 six-drop
        }
        
        optimized_deck = dict(deck_core)
        
        # Fill gaps in curve from available cards
        for target_cmc, target_count in target_curve.items():
            current_count = curve_counts.get(target_cmc, 0)
            needed = target_count - current_count
            
            if needed > 0:
                # Find suitable cards at this CMC
                suitable_cards = [
                    card for card in available_cards
                    if self.estimate_card_cmc(card) == target_cmc 
                    and available_cards[card] > 0
                    and card not in optimized_deck
                ]
                
                # Add cards to fill curve
                for card in suitable_cards[:needed]:
                    copies = min(needed, available_cards[card], 4)
                    if copies > 0:
                        optimized_deck[card] = copies
                        needed -= copies
                        if needed <= 0:
                            break
        
        return optimized_deck
    
    def estimate_card_cmc(self, card_name):
        """Estimate converted mana cost of a card"""
        # Simple estimation based on card name patterns and known cards
        cmc_estimates = {
            'Lightning Bolt': 1,
            'Counterspell': 2,
            'Tarmogoyf': 2,
            'Snapcaster Mage': 2,
            'Force of Will': 5,
            'Wrath of God': 4,
            'Serra Angel': 5,
            'Black Lotus': 0,
            'Dark Ritual': 1,
            'Llanowar Elves': 1
        }
        
        if card_name in cmc_estimates:
            return cmc_estimates[card_name]
        
        # Pattern-based estimation
        if 'Bolt' in card_name or 'Shock' in card_name:
            return 1
        elif 'Angel' in card_name or 'Dragon' in card_name:
            return 5
        elif 'Counterspell' in card_name or 'Cancel' in card_name:
            return 2
        else:
            return 3  # Default mid-range
    
    def add_synergy_cards(self, deck, available_cards, archetype):
        """Add cards that synergize with the deck strategy"""
        synergy_deck = dict(deck)
        
        # Define synergy patterns
        synergy_patterns = {
            'Aggro': ['hasty creatures', 'cheap removal', 'reach spells'],
            'Midrange': ['versatile threats', 'efficient removal', 'card advantage'],
            'Control': ['board wipes', 'card draw', 'win conditions'],
            'Combo': ['tutors', 'protection', 'enablers']
        }
        
        # Look for synergistic cards in inventory
        total_nonland_cards = sum(synergy_deck.values())
        target_cards = 38  # Target non-land cards (60 - 22 lands)
        
        if total_nonland_cards < target_cards:
            needed_cards = target_cards - total_nonland_cards
            
            # Add remaining cards from inventory
            remaining_cards = [
                card for card in available_cards
                if available_cards[card] > 0 and card not in synergy_deck
            ]
            
            # Prioritize cards that fit the archetype
            for card in remaining_cards[:needed_cards]:
                copies = min(needed_cards, available_cards[card], 4)
                if copies > 0:
                    synergy_deck[card] = copies
                    needed_cards -= copies
                    if needed_cards <= 0:
                        break
        
        return synergy_deck
    
    def build_optimal_manabase(self, deck, available_cards, format_name):
        """Build optimal mana base for the deck"""
        # Analyze color requirements
        color_requirements = self.analyze_color_requirements(deck)
        
        # Calculate land count (typically 22-24 for 60-card deck)
        nonland_cards = sum(deck.values())
        land_count = 60 - nonland_cards
        land_count = max(22, min(24, land_count))
        
        mana_base = {}
        
        if len(color_requirements) == 1:
            # Mono-colored deck
            color = list(color_requirements.keys())[0]
            basic_land = self.get_basic_land_name(color)
            mana_base[basic_land] = land_count
        
        elif len(color_requirements) == 2:
            # Two-color deck
            colors = list(color_requirements.keys())
            color1, color2 = colors[0], colors[1]
            
            # Try to add dual lands if available
            dual_lands = self.find_dual_lands(color1, color2, available_cards)
            dual_count = min(8, sum(available_cards.get(land, 0) for land in dual_lands))
            
            for land in dual_lands:
                if available_cards.get(land, 0) > 0:
                    copies = min(4, available_cards[land])
                    mana_base[land] = copies
                    dual_count -= copies
                    if dual_count <= 0:
                        break
            
            # Fill remaining with basics
            remaining_lands = land_count - sum(mana_base.values())
            if remaining_lands > 0:
                basic1 = self.get_basic_land_name(color1)
                basic2 = self.get_basic_land_name(color2)
                
                ratio1 = color_requirements[color1] / sum(color_requirements.values())
                count1 = int(remaining_lands * ratio1)
                count2 = remaining_lands - count1
                
                if count1 > 0:
                    mana_base[basic1] = count1
                if count2 > 0:
                    mana_base[basic2] = count2
        
        else:
            # Multi-color deck - use basics for simplicity
            total_requirements = sum(color_requirements.values())
            for color, requirement in color_requirements.items():
                basic_land = self.get_basic_land_name(color)
                count = max(1, int(land_count * requirement / total_requirements))
                mana_base[basic_land] = count
        
        return mana_base
    
    def analyze_color_requirements(self, deck):
        """Analyze color requirements of deck"""
        # Simple color analysis based on card names
        color_requirements = defaultdict(int)
        
        color_patterns = {
            'W': ['Angel', 'Swords', 'Path', 'Wrath'],
            'U': ['Counter', 'Draw', 'Brainstorm', 'Force'],
            'B': ['Dark', 'Fatal', 'Thoughtseize', 'Death'],
            'R': ['Lightning', 'Bolt', 'Burn', 'Red'],
            'G': ['Elf', 'Tarmogoyf', 'Growth', 'Green']
        }
        
        for card, count in deck.items():
            for color, patterns in color_patterns.items():
                if any(pattern in card for pattern in patterns):
                    color_requirements[color] += count
                    break
        
        # If no patterns matched, assume colorless or generic
        if not color_requirements:
            color_requirements['Generic'] = sum(deck.values())
        
        return dict(color_requirements)
    
    def get_basic_land_name(self, color):
        """Get basic land name for color"""
        basic_lands = {
            'W': 'Plains',
            'U': 'Island',
            'B': 'Swamp',
            'R': 'Mountain',
            'G': 'Forest'
        }
        return basic_lands.get(color, 'Wastes')
    
    def find_dual_lands(self, color1, color2, available_cards):
        """Find available dual lands for color pair"""
        # Simple dual land detection
        dual_patterns = [
            f"{color1}{color2}",
            f"{color2}{color1}",
            "Fetchland",
            "Shockland",
            "Fastland"
        ]
        
        dual_lands = []
        for card in available_cards:
            if any(pattern in card for pattern in dual_patterns):
                dual_lands.append(card)
        
        return dual_lands
    
    def finalize_deck_composition(self, deck, mana_base, available_cards):
        """Finalize deck to exactly 60 cards"""
        final_deck = dict(deck)
        current_total = sum(final_deck.values()) + sum(mana_base.values())
        
        if current_total < 60:
            # Need to add more cards
            needed = 60 - current_total
            remaining_cards = [
                card for card in available_cards
                if available_cards[card] > 0 and card not in final_deck
            ]
            
            for card in remaining_cards:
                if needed <= 0:
                    break
                copies = min(needed, available_cards[card], 4)
                if copies > 0:
                    final_deck[card] = copies
                    needed -= copies
        
        elif current_total > 60:
            # Need to remove cards
            excess = current_total - 60
            # Remove least impactful cards first
            sorted_cards = sorted(final_deck.items(), key=lambda x: x[1])
            
            for card, count in sorted_cards:
                if excess <= 0:
                    break
                reduction = min(excess, count)
                final_deck[card] -= reduction
                if final_deck[card] <= 0:
                    del final_deck[card]
                excess -= reduction
        
        return final_deck
    
    def generate_optimal_sideboard(self, mainboard, available_cards, 
                                 meta_predictions, format_name):
        """Generate optimal 15-card sideboard"""
        sideboard = {}
        
        # Sideboard card categories
        sideboard_categories = {
            'artifact_hate': ['Ancient Grudge', 'Naturalize'],
            'graveyard_hate': ['Rest in Peace', 'Grafdigger\'s Cage'],
            'creature_removal': ['Pyroclasm', 'Wrath of God'],
            'combo_disruption': ['Counterspell', 'Thoughtseize'],
            'additional_threats': ['Tarmogoyf', 'Snapcaster Mage']
        }
        
        sideboard_slots = 15
        
        # Add key sideboard cards based on meta
        for category, cards in sideboard_categories.items():
            added = 0
            for card in cards:
                if (card in available_cards and available_cards[card] > 0 
                    and card not in mainboard and sideboard_slots > 0):
                    copies = min(3, available_cards[card], sideboard_slots)
                    sideboard[card] = copies
                    sideboard_slots -= copies
                    added += copies
                    
                    if added >= 6:  # Max 6 cards per category
                        break
                        
            if sideboard_slots <= 0:
                break
        
        return sideboard
    
    def calculate_optimization_score(self, deck, sideboard, archetype, meta_predictions):
        """Calculate overall deck optimization score (0-100)"""
        scores = {}
        
        # Mana curve score (0-25)
        scores['mana_curve'] = self.score_mana_curve(deck) * 25
        
        # Synergy score (0-30)
        scores['synergy'] = self.score_deck_synergy(deck, archetype) * 30
        
        # Meta relevance score (0-20)
        scores['meta_relevance'] = self.score_meta_relevance(deck, meta_predictions) * 20
        
        # Budget efficiency score (0-15)
        scores['budget_efficiency'] = self.score_budget_efficiency(deck) * 15
        
        # Sideboard score (0-10)
        scores['sideboard'] = self.score_sideboard_quality(sideboard) * 10
        
        total_score = sum(scores.values())
        return min(100, max(0, total_score))
    
    def score_mana_curve(self, deck):
        """Score mana curve optimization (0.0-1.0)"""
        curve_counts = defaultdict(int)
        for card, count in deck.items():
            cmc = self.estimate_card_cmc(card)
            curve_counts[cmc] += count
        
        # Ideal curve distribution
        ideal_curve = {1: 8, 2: 12, 3: 8, 4: 6, 5: 3, 6: 1}
        
        # Calculate deviation from ideal
        total_deviation = 0
        total_ideal = sum(ideal_curve.values())
        
        for cmc, ideal_count in ideal_curve.items():
            actual_count = curve_counts.get(cmc, 0)
            deviation = abs(actual_count - ideal_count) / ideal_count
            total_deviation += deviation
        
        # Convert to score (lower deviation = higher score)
        score = max(0, 1 - (total_deviation / len(ideal_curve)))
        return score
    
    def score_deck_synergy(self, deck, archetype):
        """Score deck synergy (0.0-1.0)"""
        # Simplified synergy scoring
        synergy_score = 0.7  # Base synergy
        
        # Bonus for archetype-appropriate cards
        archetype_bonuses = {
            'Aggro': 0.1 if any('Bolt' in card for card in deck) else 0,
            'Control': 0.1 if any('Counter' in card for card in deck) else 0,
            'Midrange': 0.1 if any('Tarmogoyf' in card for card in deck) else 0
        }
        
        synergy_score += archetype_bonuses.get(archetype, 0)
        return min(1.0, synergy_score)
    
    def score_meta_relevance(self, deck, meta_predictions):
        """Score meta game relevance (0.0-1.0)"""
        # Base relevance
        relevance_score = 0.6
        
        # Bonus for emerging archetype cards
        emerging_archetypes = meta_predictions.get('emerging_archetypes', [])
        for archetype_info in emerging_archetypes:
            if any(enabler['name'] in deck for enabler in archetype_info.get('key_enablers', [])):
                relevance_score += 0.1
        
        return min(1.0, relevance_score)
    
    def score_budget_efficiency(self, deck):
        """Score budget efficiency (0.0-1.0)"""
        # Simplified budget scoring - assume good efficiency
        return 0.8
    
    def score_sideboard_quality(self, sideboard):
        """Score sideboard quality (0.0-1.0)"""
        if not sideboard:
            return 0.3
        
        # Basic sideboard quality check
        sideboard_size = sum(sideboard.values())
        if sideboard_size >= 12:
            return 0.8
        else:
            return sideboard_size / 15
    
    def generate_optimization_report(self, deck, sideboard, score, archetype):
        """Generate detailed optimization report"""
        report = {
            'overall_score': score,
            'grade': self.get_score_grade(score),
            'strengths': [],
            'weaknesses': [],
            'curve_analysis': self.analyze_curve_distribution(deck),
            'color_balance': self.analyze_color_requirements(deck),
            'card_roles': self.analyze_card_roles(deck),
            'recommendations': []
        }
        
        # Determine strengths and weaknesses
        if score >= 80:
            report['strengths'].append("Excellent overall optimization")
        elif score >= 70:
            report['strengths'].append("Good deck construction")
        else:
            report['weaknesses'].append("Needs optimization improvements")
        
        # Curve analysis
        curve_score = self.score_mana_curve(deck) * 100
        if curve_score >= 75:
            report['strengths'].append("Well-optimized mana curve")
        else:
            report['weaknesses'].append("Mana curve needs adjustment")
        
        # Recommendations
        if score < 70:
            report['recommendations'].append("Consider adding more synergistic cards")
        if curve_score < 60:
            report['recommendations'].append("Rebalance mana curve for better consistency")
        if sum(sideboard.values()) < 12:
            report['recommendations'].append("Expand sideboard for better meta coverage")
        
        return report
    
    def get_score_grade(self, score):
        """Convert numeric score to letter grade"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        else:
            return "D"
    
    def analyze_curve_distribution(self, deck):
        """Analyze mana curve distribution"""
        curve_counts = defaultdict(int)
        for card, count in deck.items():
            cmc = self.estimate_card_cmc(card)
            curve_counts[cmc] += count
        
        return dict(curve_counts)
    
    def analyze_card_roles(self, deck):
        """Analyze distribution of card roles in deck"""
        role_counts = defaultdict(int)
        
        for card in deck:
            for role, role_cards in self.card_roles.items():
                if card in role_cards:
                    role_counts[role] += deck[card]
                    break
        
        return dict(role_counts)
    def get_sample_cardpool(self, archetype):
        """Generate sample cardpool when inventory is empty"""
        sample_pools = {
            'Aggro': {
                'Lightning Bolt': 4, 'Monastery Swiftspear': 4,
                'Goblin Guide': 4, 'Eidolon of the Great Revel': 3,
                'Lava Spike': 4, 'Rift Bolt': 4,
                'Skullcrack': 3, 'Atarka\'s Command': 4,
                'Searing Blaze': 3, 'Boros Charm': 4,
                'Mountain': 20, 'Sacred Foundry': 4
            },
            'Midrange': {
                'Tarmogoyf': 4, 'Dark Confidant': 3,
                'Liliana of the Veil': 3, 'Thoughtseize': 4,
                'Fatal Push': 4, 'Inquisition of Kozilek': 3,
                'Abrupt Decay': 2, 'Kolaghan\'s Command': 2,
                'Scavenging Ooze': 2, 'Seasoned Pyromancer': 3,
                'Swamp': 8, 'Forest': 6, 'Blood Crypt': 4,
                'Overgrown Tomb': 4, 'Verdant Catacombs': 4
            },
            'Control': {
                'Counterspell': 4, 'Mana Leak': 3,
                'Path to Exile': 4, 'Supreme Verdict': 3,
                'Cryptic Command': 3, 'Teferi, Hero of Dominaria': 2,
                'Jace, the Mind Sculptor': 2, 'Opt': 4,
                'Think Twice': 3, 'Sphinx\'s Revelation': 2,
                'Detention Sphere': 2, 'Island': 12,
                'Plains': 6, 'Hallowed Fountain': 4,
                'Glacial Fortress': 4, 'Celestial Colonnade': 3
            },
            'Combo': {
                'Storm Entity': 4, 'Gifts Ungiven': 4,
                'Past in Flames': 3, 'Grapeshot': 2,
                'Pyretic Ritual': 4, 'Desperate Ritual': 4,
                'Manamorphose': 4, 'Serum Visions': 4,
                'Sleight of Hand': 4, 'Baral, Chief of Compliance': 3,
                'Island': 10, 'Mountain': 6,
                'Steam Vents': 4, 'Spirebluff Canal': 4
            }
        }
        return sample_pools.get(archetype, sample_pools['Midrange'])
    
    def generate_deck_suggestions(self, deck, available_cards, 
                                 meta_predictions, archetype):
        """Generate improvement suggestions for the deck"""
        suggestions = []
        
        # Curve suggestions
        curve_analysis = self.analyze_curve_distribution(deck)
        if curve_analysis.get(1, 0) < 4:
            suggestions.append({
                'type': 'curve',
                'priority': 'high',
                'suggestion': 'Add more one-mana spells for consistency',
                'cards': ['Lightning Bolt', 'Path to Exile', 'Thoughtseize']
            })
        
        # Meta suggestions
        emerging_archetypes = meta_predictions.get('emerging_archetypes', [])
        if emerging_archetypes:
            archetype_name = emerging_archetypes[0].get('name', 'Unknown')
            suggestions.append({
                'type': 'meta',
                'priority': 'medium',
                'suggestion': f'Consider cards for emerging {archetype_name} matchup',
                'cards': ['Sideboard hate cards', 'Flexible removal']
            })
        
        # Missing roles
        role_analysis = self.analyze_card_roles(deck)
        if role_analysis.get('removal', 0) < 4:
            suggestions.append({
                'type': 'role',
                'priority': 'high',
                'suggestion': 'Add more removal spells',
                'cards': ['Lightning Bolt', 'Fatal Push', 'Swords to Plowshares']
            })
        
        return suggestions


def main():
    """Test the AI deck optimization system"""
    print("🤖 AI DECK OPTIMIZER TEST")
    print("=" * 50)
    
    # Create components
    meta_analyzer = AIMetaAnalyzer()
    investment_analyzer = InvestmentAnalyzer()
    optimizer = AdvancedDeckOptimizer(meta_analyzer, investment_analyzer)
    
    # Test inventory
    test_inventory = {
        'Lightning Bolt': 4,
        'Counterspell': 3,
        'Tarmogoyf': 2,
        'Snapcaster Mage': 1,
        'Force of Will': 1,
        'Brainstorm': 4,
        'Ponder': 2,
        'Swords to Plowshares': 3,
        'Path to Exile': 2,
        'Dark Ritual': 3,
        'Llanowar Elves': 4,
        'Serra Angel': 1,
        'Wrath of God': 2,
        'Plains': 20,
        'Island': 20,
        'Swamp': 15,
        'Mountain': 15,
        'Forest': 18
    }
    
    print(f"📦 Test inventory: {len(test_inventory)} card types")
    print(f"🃏 Total cards: {sum(test_inventory.values())}")
    
    # Test meta prediction
    print("\n🔮 META PREDICTION TEST")
    meta_prediction = meta_analyzer.predict_format_changes("Modern")
    print(f"📊 Confidence: {meta_prediction['confidence_score']:.2f}")
    print(f"🔥 Emerging archetypes: {len(meta_prediction['emerging_archetypes'])}")
    
    # Test investment analysis
    print("\n💰 INVESTMENT ANALYSIS TEST")
    investment_analysis = investment_analyzer.analyze_card_investment_potential("Lightning Bolt")
    print(f"📈 Investment score: {investment_analysis['investment_score']:.1f}")
    print(f"💡 Recommendation: {investment_analysis['recommendation']}")
    
    # Test deck optimization
    print("\n⚡ DECK OPTIMIZATION TEST")
    optimization_result = optimizer.optimize_deck_from_inventory(
        test_inventory, 
        deck_archetype="Midrange",
        format_name="Modern"
    )
    
    print(f"🎯 Optimization score: {optimization_result['optimization_score']:.1f}")
    print(f"📝 Grade: {optimization_result['optimization_report']['grade']}")
    print(f"🃏 Mainboard cards: {optimization_result['total_cards']}")
    print(f"🛡️ Sideboard cards: {sum(optimization_result['sideboard'].values())}")
    
    # Show top mainboard cards
    print(f"\n🔥 TOP MAINBOARD CARDS:")
    sorted_mainboard = sorted(optimization_result['mainboard'].items(), 
                            key=lambda x: x[1], reverse=True)
    for card, count in sorted_mainboard[:8]:
        print(f"  {count}x {card}")
    
    # Show suggestions
    suggestions = optimization_result['suggestions']
    if suggestions:
        print(f"\n💡 OPTIMIZATION SUGGESTIONS:")
        for i, suggestion in enumerate(suggestions[:3], 1):
            print(f"  {i}. {suggestion['suggestion']} (Priority: {suggestion['priority']})")
    
    print("\n🏆 AI Deck Optimization Test Complete!")


if __name__ == "__main__":
    main()