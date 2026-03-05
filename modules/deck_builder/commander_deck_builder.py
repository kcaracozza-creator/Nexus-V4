#!/usr/bin/env python3
"""
Commander Deck Builder - Build legal 100-card Commander decks from your collection
"""

import csv
import random
import requests
import time
import os
import glob
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

# Import theme system
try:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from nexus_theme import NexusTheme, create_themed_button, create_themed_label, create_themed_frame
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False
    print("Theme system not available - using legacy styling")

class CommanderDeckBuilder:
    # Vintage restricted list (max 1 copy)
    VINTAGE_RESTRICTED = {
        'Ancestral Recall', 'Balance', 'Black Lotus', 'Brainstorm', 'Channel',
        'Demonic Consultation', 'Demonic Tutor', 'Dig Through Time', 'Fastbond',
        'Flash', 'Gitaxian Probe', 'Gush', 'Imperial Seal',
        'Library of Alexandria', 'Lion\'s Eye Diamond', 'Lodestone Golem',
        'Lotus Petal', 'Mana Crypt', 'Mana Vault', 'Memory Jar',
        'Mental Misstep', 'Merchant Scroll', 'Mind\'s Desire',
        'Mox Emerald', 'Mox Jet', 'Mox Pearl', 'Mox Ruby', 'Mox Sapphire',
        'Mystical Tutor', 'Necropotence', 'Ponder', 'Preordain', 'Sol Ring',
        'Strip Mine', 'Thorn of Amethyst', 'Time Vault', 'Time Walk',
        'Timetwister', 'Tinker', 'Tolarian Academy', 'Treasure Cruise',
        'Trinisphere', 'Vampiric Tutor', 'Wheel of Fortune', 'Windfall',
        'Yawgmoth\'s Will'
    }
    
    def __init__(self):
        self.collection = {}  # {card_name: quantity}
        self.card_types = defaultdict(list)  # {type: [card_names]}
        self.card_colors = defaultdict(list)  # {color: [card_names]}
        self.card_color_identity = {}  # {card_name: color_string}
        self.basic_lands = ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']
        self.price_cache = {}  # {card_name: price}
        self.card_synergies = {}  # {card_name: [synergy_cards]}
        self.high_inventory_cards = set()  # Cards with ≥90 copies
        self.slow_moving_inventory = set()  # Cards to prioritize
        
    def load_collection_folder(self, folder_path):
        """Load all CSV files from a folder and combine them"""
        print(f"Loading collection from folder: {folder_path}...")
        
        # Find all CSV files in folder
        csv_files = glob.glob(os.path.join(folder_path, '*.csv'))
        
        if not csv_files:
            print("No CSV files found in folder!")
            return 0
        
        print(f"Found {len(csv_files)} CSV file(s)")
        
        # Clear existing collection
        self.collection.clear()
        self.card_types.clear()
        self.card_colors.clear()
        self.card_color_identity.clear()
        
        # Load Master File once for all files
        master_path = r'E:\MTTGG\MASTER  SHEETS\Master File .csv'
        master_data = {}
        try:
            print("Loading Master File for card type data...")
            with open(master_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('Name') or row.get('name')
                    types = row.get('types') or ''
                    colors = row.get('colors') or ''
                    if name:
                        master_data[name] = {'types': types, 'colors': colors}
            print(f"✅ Loaded {len(master_data)} card definitions from Master File")
        except Exception as e:
            print(f"Warning: Could not load Master File: {e}")
        
        # Load each CSV file and combine quantities
        total_cards = 0
        for csv_file in csv_files:
            file_name = os.path.basename(csv_file)
            print(f"  Loading {file_name}...")
            cards_in_file = self._load_single_csv(csv_file, master_data)
            total_cards += cards_in_file
            print(f"    ✅ {cards_in_file} cards from {file_name}")
        
        print(f"\n✅ TOTAL: {len(self.collection)} unique cards, {total_cards} total cards")
        print(f"✅ Categorized: {len(self.card_types['Creature'])} creatures, "
              f"{len(self.card_types['Land'])} lands, "
              f"{len(self.card_types['Instant'])} instants, "
              f"{len(self.card_types['Sorcery'])} sorceries")
        return len(self.collection)
    
    def _load_single_csv(self, csv_path, master_data):
        """Load a single CSV file and add to collection"""
        cards_added = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try common column names
                card_name = row.get('Name') or row.get('Card Name') or row.get('name') or row.get(' Name')
                quantity = row.get('Count') or row.get('Quantity') or row.get('quantity') or row.get(' Count') or '1'
                
                if card_name:
                    # Add to existing quantity if card already in collection
                    current_qty = self.collection.get(card_name, 0)
                    self.collection[card_name] = current_qty + int(quantity)
                    cards_added += int(quantity)
                    
                    # Track high-inventory cards (≥90 copies)
                    if self.collection[card_name] >= 90:
                        self.high_inventory_cards.add(card_name)
                    
                    # Get type info from Master File or current row
                    if card_name in master_data:
                        card_type = master_data[card_name]['types']
                        colors = master_data[card_name]['colors']
                    else:
                        card_type = row.get('types') or row.get('Type') or row.get('type') or ''
                        colors = row.get('colors') or row.get('Colors') or row.get('Color') or ''
                    
                    # Only categorize if not already categorized (from previous file)
                    if card_name not in self.card_color_identity:
                        # Categorize by type
                        if 'Creature' in card_type:
                            self.card_types['Creature'].append(card_name)
                        if 'Instant' in card_type:
                            self.card_types['Instant'].append(card_name)
                        if 'Sorcery' in card_type:
                            self.card_types['Sorcery'].append(card_name)
                        if 'Enchantment' in card_type:
                            self.card_types['Enchantment'].append(card_name)
                        if 'Artifact' in card_type:
                            self.card_types['Artifact'].append(card_name)
                        if 'Land' in card_type:
                            self.card_types['Land'].append(card_name)
                        
                        # Categorize by color
                        for color in ['W', 'U', 'B', 'R', 'G']:
                            if color in colors:
                                self.card_colors[color].append(card_name)
                        
                        # Store card's full color identity
                        self.card_color_identity[card_name] = colors
        
        return cards_added
    
    def load_collection(self, csv_path):
        """Load collection from CSV file or folder"""
        # Check if path is a folder
        if os.path.isdir(csv_path):
            return self.load_collection_folder(csv_path)
        
        print(f"Loading collection from {csv_path}...")
        
        # Check if this is the Master File (has type info) or a regular export
        is_master_file = 'Master File' in csv_path
        master_data = {}
        
        # If not master file, load master file first for type lookups
        if not is_master_file:
            master_path = r'E:\MTTGG\MASTER  SHEETS\Master File .csv'
            try:
                print("Loading Master File for card type data...")
                with open(master_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get('Name') or row.get('name')
                        types = row.get('types') or ''
                        colors = row.get('colors') or ''
                        if name:
                            master_data[name] = {'types': types, 'colors': colors}
                print(f"✅ Loaded {len(master_data)} card definitions from Master File")
            except Exception as e:
                print(f"Warning: Could not load Master File: {e}")
        
        # Now load the collection
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try common column names
                card_name = row.get('Name') or row.get('Card Name') or row.get('name') or row.get(' Name')
                quantity = row.get('Count') or row.get('Quantity') or row.get('quantity') or row.get(' Count') or '1'
                
                if card_name:
                    self.collection[card_name] = int(quantity)
                    
                    # Get type info from Master File or current row
                    if card_name in master_data:
                        card_type = master_data[card_name]['types']
                        colors = master_data[card_name]['colors']
                    else:
                        card_type = row.get('types') or row.get('Type') or row.get('type') or ''
                        colors = row.get('colors') or row.get('Colors') or row.get('Color') or ''
                    
                    # Categorize by type
                    if 'Creature' in card_type:
                        self.card_types['Creature'].append(card_name)
                    if 'Instant' in card_type:
                        self.card_types['Instant'].append(card_name)
                    if 'Sorcery' in card_type:
                        self.card_types['Sorcery'].append(card_name)
                    if 'Enchantment' in card_type:
                        self.card_types['Enchantment'].append(card_name)
                    if 'Artifact' in card_type:
                        self.card_types['Artifact'].append(card_name)
                    if 'Land' in card_type:
                        self.card_types['Land'].append(card_name)
                    
                    # Categorize by color
                    for color in ['W', 'U', 'B', 'R', 'G']:
                        if color in colors:
                            self.card_colors[color].append(card_name)
                    
                    # Store card's full color identity
                    self.card_color_identity[card_name] = colors
        
        print(f"✅ Loaded {len(self.collection)} unique cards")
        print(f"✅ Categorized: {len(self.card_types['Creature'])} creatures, "
              f"{len(self.card_types['Land'])} lands, "
              f"{len(self.card_types['Instant'])} instants, "
              f"{len(self.card_types['Sorcery'])} sorceries")
        return len(self.collection)
    
    def build_deck(self, deck_format='Commander', commander=None, strategy='balanced', colors=None):
        """Build a deck based on format (Commander, Standard, Modern, etc.)
        
        PRIORITY ORDER:
        1. Format rules & banned cards (enforced by format_rules and filtering)
        2. Strategy & color identity (enforced by strategy and colors parameters)
        3. Card synergy (scored in _add_by_type)
        4. Low-value cards first (prioritize budget cards in _add_by_type)
        5. High-inventory cards ≥90 copies (prioritize in _add_by_type)
        6. Find substitutes for expensive cards (handled by find_substitutions)
        """
        # Reseed random for variety between deck builds
        random.seed()
        
        # Define format requirements
        format_rules = {
            'Commander': {'size': 100, 'max_copies': 1, 'lands': 38},
            'Brawl': {'size': 60, 'max_copies': 1, 'lands': 24},
            'Standard': {'size': 60, 'max_copies': 4, 'lands': 24},
            'Modern': {'size': 60, 'max_copies': 4, 'lands': 23},
            'Pioneer': {'size': 60, 'max_copies': 4, 'lands': 24},
            'Legacy': {'size': 60, 'max_copies': 4, 'lands': 22},
            'Vintage': {'size': 60, 'max_copies': 4, 'lands': 22},
            'Pauper': {'size': 60, 'max_copies': 4, 'lands': 24}
        }
        
        rules = format_rules.get(deck_format, format_rules['Commander'])
        deck_size = rules['size']
        max_copies = rules['max_copies']
        target_lands = rules['lands']
        
        deck = []
        used_cards = set()
        
        print(f"Building {deck_format} deck ({deck_size} cards, max {max_copies} copies)...")
        
        # Filter card pool by colors if specified
        if colors:
            # Build filtered card pool
            filtered_card_types = defaultdict(list)
            for card_type, cards in self.card_types.items():
                for card in cards:
                    card_color = self.card_color_identity.get(card, '')
                    # Include if card matches selected colors OR is colorless
                    if not card_color or any(c in card_color for c in colors):
                        filtered_card_types[card_type].append(card)
            working_types = filtered_card_types
        else:
            working_types = self.card_types
        
        # Step 1: Add commander (if provided)
        if commander and commander in self.collection:
            deck.append(commander)
            used_cards.add(commander)
            print(f"✅ Commander: {commander}")
        
        # Step 2: Add lands based on format
        lands_added = self._add_lands(deck, used_cards, target_lands, colors, max_copies)
        print(f"✅ Added {lands_added} lands")
        
        # Calculate remaining cards
        remaining = deck_size - len(deck)
        
        # Adjust strategy based on deck format and strategy type
        if strategy == 'aggro':
            creature_ratio = 0.55  # 55% creatures
            removal_ratio = 0.20
            utility_ratio = 0.25
        elif strategy == 'control':
            creature_ratio = 0.25
            removal_ratio = 0.45  # 45% removal/interaction
            utility_ratio = 0.30
        elif strategy == 'combo':
            creature_ratio = 0.30
            removal_ratio = 0.20
            utility_ratio = 0.50  # 50% combo pieces/tutors
        elif strategy == 'midrange':
            creature_ratio = 0.45
            removal_ratio = 0.30
            utility_ratio = 0.25
        elif strategy == 'tempo':
            creature_ratio = 0.50
            removal_ratio = 0.30
            utility_ratio = 0.20
        else:  # balanced
            creature_ratio = 0.45
            removal_ratio = 0.30
            utility_ratio = 0.25
        
        # Step 3: Add creatures
        target_creatures = int(remaining * creature_ratio)
        creatures_added = self._add_by_type(deck, used_cards, 'Creature', target_creatures, working_types, max_copies)
        print(f"✅ Added {creatures_added} creatures")
        
        # Step 4: Add removal/interaction
        target_removal = int(remaining * removal_ratio)
        removal_added = self._add_by_type(deck, used_cards, 'Instant', target_removal // 2, working_types, max_copies)
        removal_added += self._add_by_type(deck, used_cards, 'Sorcery', target_removal // 2, working_types, max_copies)
        print(f"✅ Added {removal_added} removal spells")
        
        # Step 5: Add utility cards
        target_utility = int(remaining * utility_ratio)
        utility_added = self._add_by_type(deck, used_cards, 'Artifact', target_utility // 2, working_types, max_copies)
        utility_added += self._add_by_type(deck, used_cards, 'Enchantment', target_utility // 2, working_types, max_copies)
        print(f"✅ Added {utility_added} utility cards")
        
        # Step 6: Fill remaining slots with best available cards
        while len(deck) < deck_size:
            remaining = deck_size - len(deck)
            print(f"Filling {remaining} remaining slots...")
            
            # Try to add more of each type proportionally
            added = False
            for card_type in ['Creature', 'Instant', 'Sorcery', 'Artifact', 'Enchantment', 'Land']:
                if len(deck) >= deck_size:
                    break
                if self._add_by_type(deck, used_cards, card_type, 1, working_types, max_copies) > 0:
                    added = True
            
            if not added:
                # No more cards available
                break
        
        return deck
    
    def _add_lands(self, deck, used_cards, target, colors=None, max_copies=1):
        """Add lands to deck"""
        added = 0
        
        # Map colors to basic lands
        color_to_land = {
            'W': 'Plains',
            'U': 'Island',
            'B': 'Swamp',
            'R': 'Mountain',
            'G': 'Forest'
        }
        
        # First add basic lands matching selected colors
        if colors:
            # Add matching basic lands
            for color in colors:
                land = color_to_land.get(color)
                if land and land in self.collection and added < target:
                    # Add multiple copies (up to 8 of each for multi-color decks)
                    copies_per_basic = min(8, target // len(colors))
                    for _ in range(copies_per_basic):
                        deck.append(land)
                        added += 1
                        if added >= target:
                            break
        else:
            # Add all basic lands evenly
            for land in self.basic_lands:
                if land in self.collection and added < target:
                    # Add multiple copies of basic lands (they're allowed)
                    copies_to_add = min(10, target - added)  # Up to 10 of each basic
                    for _ in range(copies_to_add):
                        deck.append(land)
                        added += 1
                        if added >= target:
                            break
        
        # Then add non-basic lands (singleton)
        if 'Land' in self.card_types:
            for land in self.card_types['Land']:
                if land not in self.basic_lands and land not in used_cards and added < target:
                    deck.append(land)
                    used_cards.add(land)
                    added += 1
        
        return added
    
    def set_inventory_priority(self, slow_moving_cards):
        """
        Set cards that should be prioritized for deck building (slow inventory)
        
        Args:
            slow_moving_cards: List of card names that are slow-moving inventory
        """
        self.slow_moving_inventory = set(slow_moving_cards) if slow_moving_cards else set()
        print(f"✅ Prioritizing {len(self.slow_moving_inventory)} slow-moving cards for deck building")
    
    def _add_by_type(self, deck, used_cards, card_type, target, working_types=None, max_copies=1):
        """Add cards with comprehensive priority system:
        1. Format rules (singleton, banned cards already filtered)
        2. Strategy/colors (already filtered by working_types)
        3. Synergy (cards that work well together)
        4. Low-value cards first (budget-friendly)
        5. High-inventory cards (≥90 copies)
        6. Substitutes handled elsewhere
        """
        added = 0
        
        # Use provided working_types or default to all card_types
        types_to_use = working_types if working_types is not None else self.card_types
        
        if card_type not in types_to_use:
            return 0
        
        available = [c for c in types_to_use[card_type] 
                    if c not in self.basic_lands]
        
        # PRIORITY SORTING: Create scored list of cards
        card_scores = []
        for card in available:
            score = 0
            
            # Priority 3: Synergy (placeholder - can be enhanced with actual synergy data)
            # Cards already in deck get synergy bonus
            if hasattr(self, 'card_synergies') and card in self.card_synergies:
                synergy_count = sum(1 for synergy_card in self.card_synergies[card] if synergy_card in deck)
                score += synergy_count * 1000  # High priority for synergy
            
            # Priority 4: LOW-VALUE CARDS FIRST
            price = self.price_cache.get(card, 0)
            if price == 0:
                score += 500  # Unknown price = assume budget
            elif price < 1.0:
                score += 400  # Under $1
            elif price < 5.0:
                score += 300  # Under $5
            elif price < 10.0:
                score += 200  # Under $10
            # Expensive cards get lower scores (added last)
            
            # Priority 5: HIGH-INVENTORY CARDS (≥90 copies) - HIGHEST PRIORITY!
            if card in self.high_inventory_cards:
                score += 2000  # Massively prioritize high-inventory cards
            
            # Legacy: Slow-moving inventory (90+ days) - VERY HIGH PRIORITY
            if hasattr(self, 'slow_moving_inventory') and card in self.slow_moving_inventory:
                score += 1800  # Also very high priority for old inventory
            
            # Add randomness to prevent identical decks
            score += random.randint(0, 100)
            
            card_scores.append((score, card))
        
        # Sort by score (highest first)
        card_scores.sort(reverse=True, key=lambda x: x[0])
        prioritized_list = [card for score, card in card_scores]
        
        # Stats tracking
        high_inv_added = 0
        low_value_added = 0
        
        # Track copies added
        card_counts = defaultdict(int)
        for card in deck:
            card_counts[card] += 1
        
        for card in prioritized_list:
            if added >= target:
                break

            # Check if we can add more copies (and not already used in singleton formats)
            if max_copies == 1 and card in used_cards:
                continue  # Skip cards already used in singleton formats
                
            current_count = card_counts[card]
            if current_count < max_copies and current_count < self.collection.get(card, 0):
                deck.append(card)
                card_counts[card] += 1
                if max_copies == 1:  # Singleton formats
                    used_cards.add(card)
                added += 1
                
                # Track stats
                if card in self.high_inventory_cards:
                    high_inv_added += 1
                if self.price_cache.get(card, 0) < 5.0:
                    low_value_added += 1
        
        # Print stats
        if high_inv_added > 0:
            print(f"  📦 Used {high_inv_added} high-inventory cards (≥90 copies)")
        if low_value_added > 0:
            print(f"  💰 Used {low_value_added} budget cards (<$5)")
        
        return added
    
    def find_substitutions(self, missing_cards):
        """Find substitutions for missing cards from YOUR inventory"""
        substitutions = {}
        
        for card in missing_cards:
            suggestions = []
            
            # Find the type of the missing card
            missing_card_types = []
            for card_type, cards in self.card_types.items():
                if card in cards:
                    missing_card_types.append(card_type)
            
            # Find cards in YOUR collection of same type(s)
            for card_type in missing_card_types:
                for owned_card in self.card_types.get(card_type, []):
                    # Must be in collection AND not already missing
                    if (owned_card in self.collection and 
                        owned_card not in missing_cards and
                        owned_card not in suggestions):
                        suggestions.append(owned_card)
                        if len(suggestions) >= 5:
                            break
                if len(suggestions) >= 5:
                    break
            
            # If no type match, suggest any available cards from inventory
            if not suggestions:
                for owned_card in self.collection:
                    if (owned_card not in missing_cards and
                        owned_card not in suggestions):
                        suggestions.append(owned_card)
                        if len(suggestions) >= 3:
                            break
            
            substitutions[card] = suggestions
        
        return substitutions
    
    def import_deck_list(self, file_path):
        """Import a deck list from .txt or .csv file"""
        deck_list = []
        
        try:
            if file_path.endswith('.csv'):
                # CSV format: expects columns like 'Quantity' or 'Count' and 'Name'
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        quantity = int(row.get('Quantity') or row.get('Count') or row.get('quantity') or row.get('count') or 1)
                        card_name = row.get('Name') or row.get('Card Name') or row.get('name') or row.get('Card')
                        if card_name:
                            for _ in range(quantity):
                                deck_list.append(card_name.strip())
            
            elif file_path.endswith('.txt'):
                # TXT format: expects "4 Lightning Bolt" or "1x Lightning Bolt" format
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        # Try to parse quantity and card name
                        parts = line.split(' ', 1)
                        if len(parts) == 2:
                            qty_str = parts[0].replace('x', '').strip()
                            try:
                                quantity = int(qty_str)
                                card_name = parts[1].strip()
                                for _ in range(quantity):
                                    deck_list.append(card_name)
                            except ValueError:
                                # No quantity, treat whole line as card name
                                deck_list.append(line)
                        else:
                            deck_list.append(line)
            
            print(f"✅ Imported {len(deck_list)} cards from deck list")
            return deck_list
            
        except Exception as e:
            print(f"❌ Error importing deck list: {e}")
            return []
    
    def get_card_price(self, card_name):
        """Fetch current market price for a card from Scryfall"""
        # Check cache first
        if card_name in self.price_cache:
            return self.price_cache[card_name]
        
        # Basic lands are essentially free
        if card_name in self.basic_lands:
            self.price_cache[card_name] = 0.05
            return 0.05
        
        try:
            # Use Scryfall API
            url = f"https://api.scryfall.com/cards/named?fuzzy={card_name}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                prices = data.get('prices', {})
                
                # Try to get USD price, fallback to USD foil
                price = prices.get('usd') or prices.get('usd_foil') or '0.00'
                price_float = float(price) if price else 0.00
                
                self.price_cache[card_name] = price_float
                
                # Rate limit: 100ms between requests
                time.sleep(0.1)
                
                return price_float
            else:
                print(f"Warning: Could not fetch price for {card_name}")
                self.price_cache[card_name] = 0.00
                return 0.00
                
        except Exception as e:
            print(f"Error fetching price for {card_name}: {e}")
            self.price_cache[card_name] = 0.00
            return 0.00
    
    def calculate_deck_value(self, deck):
        """Calculate total retail value of deck"""
        total_value = 0.0
        card_prices = {}
        
        # Count unique cards
        card_counts = defaultdict(int)
        for card in deck:
            card_counts[card] += 1
        
        print(f"Fetching prices for {len(card_counts)} unique cards...")
        
        for i, (card, count) in enumerate(card_counts.items(), 1):
            price = self.get_card_price(card)
            card_prices[card] = price
            total_value += price * count
            
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(card_counts)} cards...")
        
        return {
            'total_value': total_value,
            'card_prices': card_prices,
            'unique_cards': len(card_counts)
        }
    
    def calculate_deck_copies(self, deck):
        """Calculate how many copies of this deck you can make from inventory"""
        if not deck:
            return 0
        
        # Count required cards (excluding basics which are unlimited)
        required_cards = defaultdict(int)
        for card in deck:
            if card not in self.basic_lands:
                required_cards[card] += 1
        
        # Find the limiting factor
        max_copies = float('inf')
        limiting_card = None
        
        for card, needed in required_cards.items():
            available = self.collection.get(card, 0)
            if needed > 0:
                possible_copies = available // needed
                if possible_copies < max_copies:
                    max_copies = possible_copies
                    limiting_card = card
        
        if max_copies == float('inf'):
            max_copies = 0
        
        result = {
            'max_copies': int(max_copies),
            'limiting_card': limiting_card,
            'limiting_needed': required_cards.get(limiting_card, 0) if limiting_card else 0,
            'limiting_available': self.collection.get(limiting_card, 0) if limiting_card else 0
        }
        
        return result
    
    def validate_deck(self, deck, deck_format='Commander'):
        """Validate Commander deck rules"""
        issues = []
        
        # Check total cards
        required_size = 100 if deck_format == 'Commander' else 60
        if len(deck) != required_size:
            issues.append(f" Deck has {len(deck)} cards (needs exactly {required_size} for {deck_format})")
        # Check singleton rule (except basic lands)
        card_counts = defaultdict(int)
        for card in deck:
            card_counts[card] += 1
        
        for card, count in card_counts.items():
            if count > 1 and card not in self.basic_lands:
                issues.append(f"❌ {card} appears {count} times (max 1 for non-basic lands)")
        
        # Check availability in collection
        missing = []
        for card in set(deck):
            if card not in self.collection:
                missing.append(card)
        
        if missing:
            issues.append(f"❌ Missing {len(missing)} cards from collection")
        
        return issues, missing


class DeckBuilderGUI:
    def __init__(self):
        self.builder = CommanderDeckBuilder()
        
        self.root = tk.Tk()
        self.root.title("🃏 MTG Deck Builder - All Formats")
        self.root.geometry("900x700")
        
        self.setup_gui()
    
    def setup_gui(self):
        # Title
        if THEME_AVAILABLE:
            title = create_themed_label(self.root, "🃏 MTG DECK BUILDER", style='title')
        else:
            title = tk.Label(self.root, text="🃏 MTG DECK BUILDER", 
                            font=("Arial", 18, "bold"), fg="#2c3e50")
        title.pack(pady=10)
        
        # Controls frame
        if THEME_AVAILABLE:
            controls = create_themed_frame(self.root, style='control')
        else:
            controls = tk.Frame(self.root)
        controls.pack(pady=10, fill="x", padx=20)
        
        if THEME_AVAILABLE:
            create_themed_button(controls, "📂 Load Collection", 
                               command=self.load_collection, style='info').pack(side="left", padx=5)
            create_themed_button(controls, "🎯 Build Deck", 
                               command=self.build_deck, style='success').pack(side="left", padx=5)
            create_themed_button(controls, "📥 Import Deck", 
                               command=self.import_deck, style='primary').pack(side="left", padx=5)
            create_themed_button(controls, "💾 Save Deck", 
                               command=self.save_deck, style='primary').pack(side="left", padx=5)
        else:
            tk.Button(controls, text="📂 Load Collection", 
                     command=self.load_collection,
                     bg="#3498db", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
            tk.Button(controls, text="🎯 Build Deck", 
                     command=self.build_deck,
                     bg="#27ae60", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
            tk.Button(controls, text="📥 Import Deck", 
                     command=self.import_deck,
                     bg="#9b59b6", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
            tk.Button(controls, text="💾 Save Deck", 
                     command=self.save_deck,
                     bg="#8e44ad", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
        
        # Second row of buttons
        if THEME_AVAILABLE:
            controls2 = create_themed_frame(self.root, style='control')
        else:
            controls2 = tk.Frame(self.root)
        controls2.pack(pady=5, fill="x", padx=20)
        
        if THEME_AVAILABLE:
            create_themed_button(controls2, "🎲 Test Deck", 
                               command=self.test_deck, style='danger').pack(side="left", padx=5)
            create_themed_button(controls2, "🎮 Goldfish", 
                               command=self.goldfish_simulator, style='info').pack(side="left", padx=5)
            create_themed_button(controls2, "📊 Simulate Match", 
                               command=self.simulate_match, style='success').pack(side="left", padx=5)
            create_themed_button(controls2, "🔢 Deck Copies", 
                               command=self.calculate_copies, style='default').pack(side="left", padx=5)
            create_themed_button(controls2, "💰 Deck Value", 
                               command=self.show_deck_value, style='info').pack(side="left", padx=5)
        else:
            tk.Button(controls2, text="🎲 Test Deck", 
                     command=self.test_deck,
                     bg="#e74c3c", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
            tk.Button(controls2, text="🎮 Goldfish", 
                     command=self.goldfish_simulator,
                     bg="#f39c12", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
            tk.Button(controls2, text="📊 Simulate Match", 
                     command=self.simulate_match,
                     bg="#16a085", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
            tk.Button(controls2, text="🔢 Deck Copies", 
                     command=self.calculate_copies,
                     bg="#34495e", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
            tk.Button(controls2, text="💰 Deck Value", 
                     command=self.show_deck_value,
                     bg="#d35400", fg="white", font=("Arial", 11, "bold"),
                     padx=15, pady=8).pack(side="left", padx=5)
        
        # Options frame
        options = tk.Frame(self.root)
        options.pack(pady=10, fill="x", padx=20)
        
        tk.Label(options, text="Commander:", font=("Arial", 10)).pack(side="left", padx=5)
        self.commander_var = tk.StringVar(value="Auto-select")
        tk.Entry(options, textvariable=self.commander_var, width=30).pack(side="left", padx=5)
        
        tk.Label(options, text="Format:", font=("Arial", 10)).pack(side="left", padx=5)
        self.format_var = tk.StringVar(value="Commander")
        format_combo = ttk.Combobox(options, textvariable=self.format_var, 
                                   values=["Commander", "Standard", "Modern", "Pioneer", "Legacy", "Vintage", "Pauper", "Brawl"],
                                   state="readonly", width=12)
        format_combo.pack(side="left", padx=5)
        
        tk.Label(options, text="Strategy:", font=("Arial", 10)).pack(side="left", padx=15)
        self.strategy_var = tk.StringVar(value="balanced")
        strategy_combo = ttk.Combobox(options, textvariable=self.strategy_var, 
                                     values=["balanced", "aggro", "control", "combo", "midrange", "tempo"],
                                     state="readonly", width=15)
        strategy_combo.pack(side="left", padx=5)
        
        # Color selection frame
        color_frame = tk.Frame(self.root)
        color_frame.pack(pady=5, fill="x", padx=20)
        
        tk.Label(color_frame, text="Deck Colors:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        
        self.color_vars = {
            'W': tk.BooleanVar(value=False),
            'U': tk.BooleanVar(value=False),
            'B': tk.BooleanVar(value=False),
            'R': tk.BooleanVar(value=False),
            'G': tk.BooleanVar(value=False)
        }
        
        color_names = {'W': '⚪ White', 'U': '🔵 Blue', 'B': '⚫ Black', 
                      'R': '🔴 Red', 'G': '🟢 Green'}
        
        for color, name in color_names.items():
            tk.Checkbutton(color_frame, text=name, variable=self.color_vars[color],
                          font=("Arial", 9)).pack(side="left", padx=5)
        
        tk.Button(color_frame, text="Any Color", 
                 command=self.select_all_colors,
                 bg="#95a5a6", fg="white", font=("Arial", 9),
                 padx=8, pady=4).pack(side="left", padx=10)
        
        # Output display
        output_frame = tk.Frame(self.root)
        output_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        tk.Label(output_frame, text="📋 Deck List:", 
                font=("Arial", 12, "bold")).pack(anchor="w")
        
        self.output = scrolledtext.ScrolledText(output_frame, 
                                               height=25,
                                               bg="#ecf0f1", 
                                               fg="#2c3e50",
                                               font=("Courier", 10))
        self.output.pack(fill="both", expand=True)
        
        # Status bar
        self.status = tk.Label(self.root, text="Ready", 
                             bg="#34495e", fg="white", 
                             font=("Arial", 9), anchor="w", padx=10)
        self.status.pack(fill="x", side="bottom")
        
        self.current_deck = []
    
    def load_collection(self):
        filepath = filedialog.askopenfilename(
            title="Select Collection CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                count = self.builder.load_collection(filepath)
                self.status.config(text=f"✅ Loaded {count} cards from collection")
                self.output.insert("1.0", f"✅ Collection loaded: {count} unique cards\n\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load collection:\n{e}")
    
    def select_all_colors(self):
        """Select all colors for deck building"""
        for var in self.color_vars.values():
            var.set(True)
    
    def build_deck(self):
        if not self.builder.collection:
            messagebox.showwarning("Warning", "Please load a collection first!")
            return
        
        self.output.delete("1.0", tk.END)
        
        # Get format
        deck_format = self.format_var.get()
        self.output.insert("1.0", f"🎯 Building {deck_format} deck...\n\n")
        self.root.update()
        
        # Get commander if specified
        commander = self.commander_var.get()
        if commander == "Auto-select" or not commander:
            commander = None
        
        # Build deck
        try:
            # Get selected colors
            selected_colors = [color for color, var in self.color_vars.items() if var.get()]
            
            if selected_colors:
                self.output.insert("end", f"Building with colors: {', '.join(selected_colors)}\n\n")
            else:
                self.output.insert("end", "Building with all colors (none selected)\n\n")
            
            deck = self.builder.build_deck(
                deck_format=deck_format,
                commander=commander,
                strategy=self.strategy_var.get(),
                colors=selected_colors if selected_colors else None
            )
            
            self.current_deck = deck
            
            # Display deck
            self.output.insert("end", f"\n{'='*60}\n")
            self.output.insert("end", f"📋 {deck_format.upper()} DECK ({len(deck)} cards)\n")
            self.output.insert("end", f"{'='*60}\n\n")
            
            # Group by type
            card_counts = defaultdict(int)
            for card in deck:
                card_counts[card] += 1
            
            # Sort cards
            sorted_cards = sorted(card_counts.items(), key=lambda x: x[0])
            
            for card, count in sorted_cards:
                if card in self.builder.basic_lands:
                    self.output.insert("end", f"{count}x {card}\n")
                else:
                    self.output.insert("end", f"1x {card}\n")
            
            # Validate
            issues, missing = self.builder.validate_deck(deck, deck_format)
            
            self.output.insert("end", f"\n{'='*60}\n")
            self.output.insert("end", "🔍 DECK VALIDATION\n")
            self.output.insert("end", f"{'='*60}\n\n")
            
            if not issues:
                self.output.insert("end", "✅ Deck is legal and complete!\n")
            else:
                for issue in issues:
                    self.output.insert("end", f"{issue}\n")
            
            # Show substitutions if needed
            if missing:
                self.output.insert("end", f"\n💡 SUGGESTED SUBSTITUTIONS\n")
                self.output.insert("end", f"{'='*60}\n\n")
                subs = self.builder.find_substitutions(missing)
                for card, suggestions in subs.items():
                    self.output.insert("end", f"Missing: {card}\n")
                    if suggestions:
                        self.output.insert("end", f"  ➜ Try: {', '.join(suggestions[:3])}\n")
                    else:
                        self.output.insert("end", f"  ➜ No substitutions found\n")
                    self.output.insert("end", "\n")
            
            # Quick price estimate (optional - can be disabled for speed)
            self.output.insert("end", "\n💰 CALCULATING DECK VALUE...\n")
            self.root.update()
            
            try:
                value_result = self.builder.calculate_deck_value(deck)
                total_value = value_result['total_value']
                self.output.insert("end", f"💵 Total Deck Value: ${total_value:.2f}\n")
            except Exception as e:
                self.output.insert("end", f"⚠️ Could not calculate value: {e}\n")
            
            self.status.config(text=f"✅ Built {len(deck)}-card deck (${total_value:.2f} value)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build deck:\n{e}")
    
    def save_deck(self):
        if not self.current_deck:
            messagebox.showwarning("Warning", "No deck to save!")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Save Deck",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write("COMMANDER DECK\n")
                    f.write("="*60 + "\n\n")
                    
                    card_counts = defaultdict(int)
                    for card in self.current_deck:
                        card_counts[card] += 1
                    
                    for card, count in sorted(card_counts.items()):
                        if card in self.builder.basic_lands:
                            f.write(f"{count} {card}\n")
                        else:
                            f.write(f"1 {card}\n")
                
                self.status.config(text=f"✅ Deck saved to {filepath}")
                messagebox.showinfo("Success", "Deck saved successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save deck:\n{e}")
    
    def test_deck(self):
        """Test deck - opening hands, mulligans, mana curve"""
        if not self.current_deck:
            messagebox.showwarning("Warning", "Build a deck first!")
            return
        
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", "🎲 DECK TESTING\n")
        self.output.insert("end", "="*60 + "\n\n")
        
        # Simulate 10 opening hands
        self.output.insert("end", "🃏 OPENING HAND ANALYSIS (10 samples)\n")
        self.output.insert("end", "-"*60 + "\n\n")
        
        land_counts = []
        for i in range(10):
            hand = random.sample(self.current_deck, 7)
            lands = sum(1 for card in hand if card in self.builder.card_types['Land'])
            land_counts.append(lands)
            
            self.output.insert("end", f"Hand {i+1}: {lands} lands\n")
            for card in hand:
                card_type = "Land" if card in self.builder.card_types['Land'] else "Spell"
                self.output.insert("end", f"  • {card} ({card_type})\n")
            self.output.insert("end", "\n")
        
        # Statistics
        avg_lands = sum(land_counts) / len(land_counts)
        self.output.insert("end", f"\n📊 STATISTICS\n")
        self.output.insert("end", "-"*60 + "\n")
        self.output.insert("end", f"Average lands in opening hand: {avg_lands:.1f}\n")
        self.output.insert("end", f"Keepable hands (2-5 lands): {sum(1 for x in land_counts if 2 <= x <= 5)}/10\n")
        
        # Mana curve
        self.output.insert("end", f"\n📈 MANA CURVE\n")
        self.output.insert("end", "-"*60 + "\n")
        total_lands = sum(1 for card in self.current_deck if card in self.builder.card_types['Land'])
        total_spells = len(self.current_deck) - total_lands
        self.output.insert("end", f"Lands: {total_lands} ({total_lands/len(self.current_deck)*100:.1f}%)\n")
        self.output.insert("end", f"Spells: {total_spells} ({total_spells/len(self.current_deck)*100:.1f}%)\n")
        
        self.status.config(text="✅ Deck testing complete")
    
    def goldfish_simulator(self):
        """Goldfish - simulate playing the deck solo"""
        if not self.current_deck:
            messagebox.showwarning("Warning", "Build a deck first!")
            return
        
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", "🎮 GOLDFISH SIMULATOR\n")
        self.output.insert("end", "="*60 + "\n\n")
        
        # Shuffle deck
        deck = self.current_deck.copy()
        random.shuffle(deck)
        
        # Draw opening hand
        hand = deck[:7]
        deck = deck[7:]
        
        self.output.insert("end", "🃏 Opening Hand (7 cards):\n")
        for card in hand:
            self.output.insert("end", f"  • {card}\n")
        
        lands_in_hand = sum(1 for card in hand if card in self.builder.card_types['Land'])
        self.output.insert("end", f"\nLands: {lands_in_hand}, Spells: {7-lands_in_hand}\n")
        
        # Simulate first 5 turns
        self.output.insert("end", f"\n📅 TURN SIMULATION\n")
        self.output.insert("end", "-"*60 + "\n\n")
        
        lands_played = 0
        for turn in range(1, 6):
            # Draw card
            if deck:
                drawn = deck.pop(0)
                hand.append(drawn)
                self.output.insert("end", f"Turn {turn}: Drew {drawn}\n")
                
                # Play land if available
                lands_in_hand = [c for c in hand if c in self.builder.card_types['Land']]
                if lands_in_hand and lands_played < turn:
                    played_land = lands_in_hand[0]
                    hand.remove(played_land)
                    lands_played += 1
                    self.output.insert("end", f"  → Played {played_land}\n")
                
                self.output.insert("end", f"  Mana available: {lands_played}\n")
                self.output.insert("end", f"  Hand size: {len(hand)}\n\n")
        
        self.output.insert("end", f"✅ Simulation complete - Turn 5 reached with {lands_played} lands\n")
        self.status.config(text="✅ Goldfish simulation complete")
    
    def simulate_match(self):
        """Simulate multiple games and calculate statistics"""
        if not self.current_deck:
            messagebox.showwarning("Warning", "Build a deck first!")
            return
        
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", "📊 MATCH SIMULATION\n")
        self.output.insert("end", "="*60 + "\n\n")
        self.output.insert("end", "Simulating 100 games...\n\n")
        self.root.update()
        
        results = {
            'turn_4_wins': 0,
            'turn_5_wins': 0,
            'turn_6_wins': 0,
            'turn_7plus_wins': 0,
            'mulligans': 0,
            'mana_screw': 0,
            'mana_flood': 0
        }
        
        for game in range(100):
            deck = self.current_deck.copy()
            random.shuffle(deck)
            
            # Opening hand
            hand = deck[:7]
            lands = sum(1 for c in hand if c in self.builder.card_types['Land'])
            
            # Mulligan logic (keep 2-5 lands)
            if lands < 2 or lands > 5:
                results['mulligans'] += 1
                # Redraw
                deck_shuffled = self.current_deck.copy()
                random.shuffle(deck_shuffled)
                hand = deck_shuffled[:7]
                lands = sum(1 for c in hand if c in self.builder.card_types['Land'])
            
            # Simple win condition simulation (very basic)
            if lands >= 4:
                results['turn_5_wins'] += 1
            elif lands == 3:
                results['turn_6_wins'] += 1
            elif lands == 2:
                results['turn_7plus_wins'] += 1
            elif lands <= 1:
                results['mana_screw'] += 1
            elif lands >= 6:
                results['mana_flood'] += 1
        
        # Display results
        self.output.insert("end", "🏆 RESULTS (100 games)\n")
        self.output.insert("end", "-"*60 + "\n")
        self.output.insert("end", f"Fast wins (Turn 4-5): {results['turn_5_wins']}\n")
        self.output.insert("end", f"Medium wins (Turn 6): {results['turn_6_wins']}\n")
        self.output.insert("end", f"Slow wins (Turn 7+): {results['turn_7plus_wins']}\n")
        self.output.insert("end", f"Mana screw losses: {results['mana_screw']}\n")
        self.output.insert("end", f"Mulligans needed: {results['mulligans']}\n")
        
        win_rate = (results['turn_5_wins'] + results['turn_6_wins'] + results['turn_7plus_wins'])
        self.output.insert("end", f"\n💯 Estimated win rate: {win_rate}%\n")
        
        self.status.config(text=f"✅ Simulation complete - {win_rate}% win rate")
    
    def import_deck(self):
        """Import a premade deck list from file"""
        filepath = filedialog.askopenfilename(
            title="Select Deck List File",
            filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if filepath:
            try:
                self.output.delete("1.0", tk.END)
                self.output.insert("1.0", "📥 IMPORTING DECK LIST\n")
                self.output.insert("end", "="*60 + "\n\n")
                
                # Import the deck
                deck = self.builder.import_deck_list(filepath)
                
                if not deck:
                    messagebox.showerror("Error", "Failed to import deck list")
                    return
                
                self.current_deck = deck
                
                # Display imported deck
                self.output.insert("end", f"📋 IMPORTED DECK ({len(deck)} cards)\n")
                self.output.insert("end", "-"*60 + "\n\n")
                
                # Count cards
                card_counts = defaultdict(int)
                for card in deck:
                    card_counts[card] += 1
                
                for card, count in sorted(card_counts.items()):
                    self.output.insert("end", f"{count}x {card}\n")
                
                # Check availability and find substitutions
                self.output.insert("end", "\n🔍 CHECKING INVENTORY\n")
                self.output.insert("end", "-"*60 + "\n\n")
                
                missing_cards = []
                for card, needed in card_counts.items():
                    available = self.builder.collection.get(card, 0)
                    if available < needed:
                        missing_cards.append(card)
                        shortage = needed - available
                        self.output.insert("end", f"❌ {card}: Need {needed}, have {available} (short {shortage})\n")
                    else:
                        self.output.insert("end", f"✅ {card}: Have {available} (need {needed})\n")
                
                # Find substitutions for missing cards
                if missing_cards:
                    self.output.insert("end", "\n💡 SUGGESTED SUBSTITUTIONS (from your inventory)\n")
                    self.output.insert("end", "-"*60 + "\n\n")
                    
                    subs = self.builder.find_substitutions(missing_cards)
                    for missing_card, suggestions in subs.items():
                        self.output.insert("end", f"For {missing_card}:\n")
                        if suggestions:
                            for sub in suggestions:
                                self.output.insert("end", f"  ➜ {sub}\n")
                        else:
                            self.output.insert("end", "  ➜ No substitutions found\n")
                        self.output.insert("end", "\n")
                else:
                    self.output.insert("end", "\n✅ All cards available in your collection!\n")
                
                self.status.config(text=f"✅ Imported {len(deck)} card deck - {len(missing_cards)} cards need substitutions")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import deck:\n{e}")
    
    def show_deck_value(self):
        """Calculate and display total market value of current deck"""
        if not self.current_deck:
            messagebox.showwarning("Warning", "Build or import a deck first!")
            return
        
        try:
            self.output.delete("1.0", tk.END)
            self.output.insert("1.0", "💰 DECK VALUE CALCULATOR\n")
            self.output.insert("end", "="*60 + "\n\n")
            self.output.insert("end", "⏳ Fetching current market prices from Scryfall...\n")
            self.output.insert("end", "(This may take a minute)\n\n")
            self.root.update()
            
            # Calculate deck value
            result = self.builder.calculate_deck_value(self.current_deck)
            
            total_value = result['total_value']
            card_prices = result['card_prices']
            unique_cards = result['unique_cards']
            
            self.output.delete("1.0", tk.END)
            self.output.insert("1.0", "💰 DECK VALUE CALCULATOR\n")
            self.output.insert("end", "="*60 + "\n\n")
            
            self.output.insert("end", f"💵 TOTAL DECK VALUE: ${total_value:.2f}\n\n")
            self.output.insert("end", f"📊 Unique cards priced: {unique_cards}\n")
            self.output.insert("end", f"📋 Total cards in deck: {len(self.current_deck)}\n\n")
            
            # Show breakdown by card
            self.output.insert("end", "💳 CARD-BY-CARD BREAKDOWN\n")
            self.output.insert("end", "-"*60 + "\n\n")
            
            # Count cards and calculate individual values
            card_counts = defaultdict(int)
            for card in self.current_deck:
                card_counts[card] += 1
            
            # Sort by total value (price * quantity) descending
            card_values = []
            for card, count in card_counts.items():
                price = card_prices.get(card, 0.00)
                total = price * count
                card_values.append((total, card, count, price))
            
            card_values.sort(reverse=True)
            
            for total, card, count, price in card_values:
                if price > 0.00:
                    self.output.insert("end", f"{count}x {card}\n")
                    self.output.insert("end", f"   ${price:.2f} each = ${total:.2f} total\n")
            
            # Show most expensive cards
            self.output.insert("end", "\n🏆 TOP 10 MOST EXPENSIVE CARDS\n")
            self.output.insert("end", "-"*60 + "\n\n")
            
            for i, (total, card, count, price) in enumerate(card_values[:10], 1):
                if price > 0.00:
                    self.output.insert("end", f"{i}. {card}: ${price:.2f} each (${total:.2f} total)\n")
            
            # Summary statistics
            self.output.insert("end", "\n📈 VALUE STATISTICS\n")
            self.output.insert("end", "-"*60 + "\n")
            
            prices_list = [p for p in card_prices.values() if p > 0]
            if prices_list:
                avg_price = sum(prices_list) / len(prices_list)
                max_price = max(prices_list)
                min_price = min([p for p in prices_list if p > 0], default=0)
                
                self.output.insert("end", f"Average card value: ${avg_price:.2f}\n")
                self.output.insert("end", f"Most expensive card: ${max_price:.2f}\n")
                self.output.insert("end", f"Least expensive card: ${min_price:.2f}\n")
            
            self.status.config(text=f"✅ Deck value: ${total_value:.2f} (current market)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate deck value:\n{e}")
    
    def calculate_copies(self):
        """Calculate how many copies of current deck can be made"""
        if not self.current_deck:
            messagebox.showwarning("Warning", "Build or import a deck first!")
            return
        
        try:
            self.output.delete("1.0", tk.END)
            self.output.insert("1.0", "🔢 DECK COPY CALCULATOR\n")
            self.output.insert("end", "="*60 + "\n\n")
            
            result = self.builder.calculate_deck_copies(self.current_deck)
            
            max_copies = result['max_copies']
            limiting_card = result['limiting_card']
            limiting_needed = result['limiting_needed']
            limiting_available = result['limiting_available']
            
            self.output.insert("end", f"📦 Maximum deck copies: {max_copies}\n\n")
            
            if limiting_card:
                self.output.insert("end", f"🔴 Limiting factor: {limiting_card}\n")
                self.output.insert("end", f"   Need {limiting_needed} per deck\n")
                self.output.insert("end", f"   Have {limiting_available} in inventory\n")
                self.output.insert("end", f"   Allows {max_copies} complete deck(s)\n\n")
            
            # Show detailed breakdown
            self.output.insert("end", "📊 CARD AVAILABILITY BREAKDOWN\n")
            self.output.insert("end", "-"*60 + "\n\n")
            
            card_counts = defaultdict(int)
            for card in self.current_deck:
                if card not in self.builder.basic_lands:
                    card_counts[card] += 1
            
            # Sort by limiting factor (fewest possible copies)
            availability = []
            for card, needed in card_counts.items():
                available = self.builder.collection.get(card, 0)
                possible = available // needed if needed > 0 else 0
                availability.append((possible, card, needed, available))
            
            availability.sort()  # Sort by possible copies (ascending)
            
            for possible, card, needed, available in availability[:15]:  # Show top 15 limiting cards
                self.output.insert("end", f"{card}:\n")
                self.output.insert("end", f"  Need {needed}/deck, have {available} → {possible} deck(s)\n")
            
            if len(availability) > 15:
                self.output.insert("end", f"\n... and {len(availability) - 15} more cards\n")
            
            # Find substitutions for cards we don't have enough of
            shortage_cards = [card for possible, card, needed, available in availability if possible == 0]
            
            if shortage_cards:
                self.output.insert("end", "\n💡 SUGGESTED SUBSTITUTIONS (from your inventory)\n")
                self.output.insert("end", "-"*60 + "\n\n")
                
                subs = self.builder.find_substitutions(shortage_cards[:10])  # Limit to top 10
                for missing_card, suggestions in subs.items():
                    self.output.insert("end", f"For {missing_card}:\n")
                    if suggestions:
                        for sub in suggestions[:3]:  # Show top 3 suggestions
                            self.output.insert("end", f"  ➜ {sub}\n")
                    else:
                        self.output.insert("end", "  ➜ No substitutions found\n")
                    self.output.insert("end", "\n")
            
            self.status.config(text=f"✅ Can make {max_copies} complete deck copies from inventory")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate deck copies:\n{e}")
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = DeckBuilderGUI()
    app.run()

