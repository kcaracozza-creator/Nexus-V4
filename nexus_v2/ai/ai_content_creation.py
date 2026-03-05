#!/usr/bin/env python3
"""
MTTGG AI Content Creation System
Custom card generation, deck theme analysis, automated naming, and story generation
"""

import os
import sys
import json
import re
import random
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import requests
import time

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    IMAGING_AVAILABLE = True
except ImportError:
    print("[WARN] Imaging libraries not available - some features will be limited")
    IMAGING_AVAILABLE = False

try:
    # For advanced AI features (optional)
    import openai
    AI_API_AVAILABLE = True
except ImportError:
    AI_API_AVAILABLE = False


class CustomCardGenerator:
    """AI-powered custom Magic card generation system"""

    # Default paths (can be overridden via config)
    _DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"

    def __init__(self, master_db_path=None, output_dir=None, templates_dir=None):
        self.master_db_path = master_db_path or str(self._DEFAULT_DATA_DIR / "master_cards.csv")
        self.output_dir = Path(output_dir) if output_dir else self._DEFAULT_DATA_DIR / "generated_cards"
        self.templates_dir = Path(templates_dir) if templates_dir else self._DEFAULT_DATA_DIR / "card_templates"

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Card data
        self.master_cards = {}
        self.card_types = []
        self.mana_costs = []
        self.abilities = []

        # Templates and assets
        self.card_templates = {}
        self.fonts = {}

        logger.info("Custom Card Generator initialized")
        self.load_card_data()
        self.setup_templates()
    
    def load_card_data(self):
        """Load existing card data for AI training"""
        try:
            if os.path.exists(self.master_db_path):
                import csv
                with open(self.master_db_path, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get('Name', '').strip()
                        if name:
                            self.master_cards[name] = {
                                'type': row.get('Type', ''),
                                'mana_cost': row.get('Mana Cost', ''),
                                'text': row.get('Oracle Text', ''),
                                'power': row.get('Power', ''),
                                'toughness': row.get('Toughness', ''),
                                'rarity': row.get('Rarity', ''),
                                'set': row.get('Set', '')
                            }
                
                print(f"[OK] Loaded {len(self.master_cards)} cards for AI training")
                self.analyze_card_patterns()
            
        except Exception as e:
            print(f"[WARN] Could not load master database: {e}")
            print("🔄 Using fallback card generation patterns")
            self.setup_fallback_patterns()
    
    def analyze_card_patterns(self):
        """Analyze existing cards to learn patterns"""
        print("🧠 Analyzing card patterns for AI generation...")
        
        for card_data in self.master_cards.values():
            # Extract card types
            card_type = card_data.get('type', '')
            if card_type and card_type not in self.card_types:
                self.card_types.append(card_type)
            
            # Extract mana costs
            mana_cost = card_data.get('mana_cost', '')
            if mana_cost and mana_cost not in self.mana_costs:
                self.mana_costs.append(mana_cost)
            
            # Extract common abilities
            text = card_data.get('text', '')
            if text:
                abilities = self.extract_abilities(text)
                for ability in abilities:
                    if ability not in self.abilities:
                        self.abilities.append(ability)
        
        print(f"📊 Learned {len(self.card_types)} card types")
        print(f"📊 Learned {len(self.mana_costs)} mana cost patterns")
        print(f"📊 Learned {len(self.abilities)} ability patterns")
    
    def extract_abilities(self, text):
        """Extract common abilities from card text"""
        abilities = []
        common_abilities = [
            'Flying', 'Trample', 'First Strike', 'Double Strike', 'Deathtouch',
            'Lifelink', 'Vigilance', 'Reach', 'Haste', 'Hexproof', 'Indestructible',
            'Flash', 'Defender', 'Menace', 'Prowess', 'Scry', 'Draw a card'
        ]
        
        for ability in common_abilities:
            if ability.lower() in text.lower():
                abilities.append(ability)
        
        return abilities
    
    def setup_fallback_patterns(self):
        """Setup basic patterns when master DB is unavailable"""
        self.card_types = [
            'Creature', 'Instant', 'Sorcery', 'Enchantment', 'Artifact',
            'Planeswalker', 'Land', 'Legendary Creature', 'Artifact Creature'
        ]
        
        self.mana_costs = [
            '{1}', '{2}', '{3}', '{1}{W}', '{1}{U}', '{1}{B}', '{1}{R}', '{1}{G}',
            '{2}{W}', '{2}{U}', '{2}{B}', '{2}{R}', '{2}{G}', '{W}{U}', '{U}{B}'
        ]
        
        self.abilities = [
            'Flying', 'Trample', 'First Strike', 'Deathtouch', 'Lifelink',
            'Vigilance', 'Haste', 'Hexproof', 'Flash', 'Menace', 'Prowess'
        ]
    
    def setup_templates(self):
        """Setup card templates and fonts"""
        if not IMAGING_AVAILABLE:
            print("[WARN] Image generation not available - text-only cards")
            return
        
        try:
            # Create basic templates
            self.create_basic_templates()
            print("[OK] Card templates ready")
        except Exception as e:
            print(f"[WARN] Template setup error: {e}")
    
    def create_basic_templates(self):
        """Create basic card templates"""
        if not IMAGING_AVAILABLE:
            return
        
        # Standard MTG card dimensions (approx 2.5 x 3.5 inches at 300 DPI)
        card_width, card_height = 750, 1050
        
        # Create templates for different card types
        templates = {
            'creature': self.create_creature_template(card_width, card_height),
            'spell': self.create_spell_template(card_width, card_height),
            'land': self.create_land_template(card_width, card_height)
        }
        
        self.card_templates = templates
    
    def create_creature_template(self, width, height):
        """Create creature card template"""
        # Create base image with MTG-style border
        img = Image.new('RGB', (width, height), color='#2C1810')
        draw = ImageDraw.Draw(img)
        
        # Draw border
        border_thickness = 20
        draw.rectangle([border_thickness, border_thickness, 
                       width-border_thickness, height-border_thickness], 
                      outline='#8B4513', width=5)
        
        # Text areas
        name_area = (40, 30, width-40, 80)
        cost_area = (width-150, 30, width-40, 80)
        art_area = (40, 90, width-40, height//2)
        type_area = (40, height//2 + 10, width-40, height//2 + 50)
        text_area = (40, height//2 + 60, width-40, height-150)
        pt_area = (width-120, height-80, width-40, height-40)
        
        return {
            'image': img,
            'areas': {
                'name': name_area,
                'cost': cost_area,
                'art': art_area,
                'type': type_area,
                'text': text_area,
                'power_toughness': pt_area
            }
        }
    
    def create_spell_template(self, width, height):
        """Create spell card template"""
        img = Image.new('RGB', (width, height), color='#1A1A2E')
        draw = ImageDraw.Draw(img)
        
        # Draw border
        border_thickness = 20
        draw.rectangle([border_thickness, border_thickness, 
                       width-border_thickness, height-border_thickness], 
                      outline='#4A4A8A', width=5)
        
        return {
            'image': img,
            'areas': {
                'name': (40, 30, width-40, 80),
                'cost': (width-150, 30, width-40, 80),
                'art': (40, 90, width-40, height//2),
                'type': (40, height//2 + 10, width-40, height//2 + 50),
                'text': (40, height//2 + 60, width-40, height-100)
            }
        }
    
    def create_land_template(self, width, height):
        """Create land card template"""
        img = Image.new('RGB', (width, height), color='#2F4F2F')
        draw = ImageDraw.Draw(img)
        
        # Draw border
        border_thickness = 20
        draw.rectangle([border_thickness, border_thickness, 
                       width-border_thickness, height-border_thickness], 
                      outline='#228B22', width=5)
        
        return {
            'image': img,
            'areas': {
                'name': (40, 30, width-40, 80),
                'art': (40, 90, width-40, height//2 + 50),
                'type': (40, height//2 + 60, width-40, height//2 + 100),
                'text': (40, height//2 + 110, width-40, height-100)
            }
        }
    
    def generate_custom_card(self, theme=None, card_type=None, power_level='medium'):
        """Generate a custom Magic card"""
        print(f"🎨 Generating custom card - Theme: {theme}, Type: {card_type}")
        
        # Generate card properties
        card_data = self.generate_card_properties(theme, card_type, power_level)
        
        # Generate card image (if imaging available)
        card_image = None
        if IMAGING_AVAILABLE:
            card_image = self.create_card_image(card_data)
        
        # Save card data
        card_file = self.save_generated_card(card_data, card_image)
        
        print(f"[OK] Generated card: {card_data['name']}")
        return {
            'card_data': card_data,
            'image_path': card_image,
            'data_file': card_file
        }
    
    def generate_card_properties(self, theme, card_type, power_level):
        """Generate the properties of a custom card"""
        # Determine card type
        if not card_type:
            card_type = random.choice(self.card_types)
        
        # Generate name
        name = self.generate_card_name(theme, card_type)
        
        # Generate mana cost
        mana_cost = self.generate_mana_cost(card_type, power_level)
        
        # Generate card text
        card_text = self.generate_card_text(theme, card_type, power_level)
        
        # Generate power/toughness for creatures
        power, toughness = None, None
        if 'Creature' in card_type:
            power, toughness = self.generate_power_toughness(mana_cost, power_level)
        
        return {
            'name': name,
            'mana_cost': mana_cost,
            'type': card_type,
            'text': card_text,
            'power': power,
            'toughness': toughness,
            'rarity': self.determine_rarity(power_level),
            'theme': theme,
            'generated_at': datetime.now().isoformat()
        }
    
    def generate_card_name(self, theme, card_type):
        """Generate a thematic card name"""
        if theme:
            theme_words = {
                'fire': ['Blazing', 'Infernal', 'Scorching', 'Molten', 'Burning'],
                'water': ['Flowing', 'Tidal', 'Aquatic', 'Mystic', 'Depths'],
                'nature': ['Wild', 'Ancient', 'Grove', 'Verdant', 'Primal'],
                'shadow': ['Dark', 'Shadowy', 'Cursed', 'Void', 'Nightmare'],
                'light': ['Radiant', 'Holy', 'Divine', 'Celestial', 'Blessed']
            }
            
            descriptors = theme_words.get(theme.lower(), ['Mystical', 'Arcane', 'Enchanted'])
        else:
            descriptors = ['Mystical', 'Arcane', 'Ancient', 'Powerful', 'Legendary']
        
        # Type-specific words
        type_words = {
            'Creature': ['Guardian', 'Warrior', 'Beast', 'Spirit', 'Dragon'],
            'Instant': ['Strike', 'Blast', 'Flash', 'Burst', 'Surge'],
            'Sorcery': ['Ritual', 'Invocation', 'Summoning', 'Spell', 'Magic'],
            'Enchantment': ['Aura', 'Blessing', 'Curse', 'Ward', 'Protection'],
            'Artifact': ['Relic', 'Device', 'Construct', 'Engine', 'Tool'],
            'Land': ['Realm', 'Domain', 'Sanctuary', 'Grounds', 'Territory']
        }
        
        descriptor = random.choice(descriptors)
        type_word = random.choice(type_words.get(card_type, ['Entity']))
        
        # Combine for name
        name_patterns = [
            f"{descriptor} {type_word}",
            f"{type_word} of {descriptor} Power",
            f"{descriptor} {type_word} Master",
            f"The {descriptor} {type_word}"
        ]
        
        return random.choice(name_patterns)
    
    def generate_mana_cost(self, card_type, power_level):
        """Generate appropriate mana cost"""
        base_costs = {
            'low': ['{1}', '{2}', '{W}', '{U}', '{B}', '{R}', '{G}'],
            'medium': ['{2}', '{3}', '{1}{W}', '{1}{U}', '{1}{B}', '{1}{R}', '{1}{G}'],
            'high': ['{4}', '{5}', '{3}{W}', '{3}{U}', '{3}{B}', '{3}{R}', '{3}{G}']
        }
        
        costs = base_costs.get(power_level, base_costs['medium'])
        
        # Adjust for card type
        if card_type == 'Land':
            return ''  # Lands typically have no mana cost
        elif 'Creature' in card_type and power_level == 'high':
            return random.choice(['{4}', '{5}', '{6}', '{2}{W}{W}', '{2}{U}{U}'])
        
        return random.choice(costs)
    
    def generate_card_text(self, theme, card_type, power_level):
        """Generate card rules text"""
        if card_type == 'Land':
            return self.generate_land_text(theme)
        elif 'Creature' in card_type:
            return self.generate_creature_text(theme, power_level)
        else:
            return self.generate_spell_text(theme, card_type, power_level)
    
    def generate_creature_text(self, theme, power_level):
        """Generate creature abilities"""
        abilities = []
        
        # Basic abilities based on power level
        if power_level == 'low':
            abilities = random.sample(['Flying', 'Vigilance', 'First Strike'], k=random.randint(0, 1))
        elif power_level == 'medium':
            abilities = random.sample(['Flying', 'Trample', 'Deathtouch', 'Lifelink', 'Vigilance'], k=random.randint(1, 2))
        else:  # high
            abilities = random.sample(['Flying', 'Trample', 'Deathtouch', 'Lifelink', 'Hexproof', 'Indestructible'], k=random.randint(2, 3))
        
        # Add thematic abilities
        if theme:
            theme_abilities = {
                'fire': ['Haste', 'First Strike'],
                'water': ['Flying', 'Hexproof'],
                'nature': ['Trample', 'Vigilance'],
                'shadow': ['Deathtouch', 'Menace'],
                'light': ['Lifelink', 'Vigilance']
            }
            
            if theme.lower() in theme_abilities:
                theme_ability = random.choice(theme_abilities[theme.lower()])
                if theme_ability not in abilities:
                    abilities.append(theme_ability)
        
        # Add activated ability for high power level
        if power_level == 'high':
            activated_abilities = [
                "{T}: Deal 1 damage to any target.",
                "{T}: Gain 1 life.",
                "{T}: Draw a card, then discard a card.",
                "Sacrifice this creature: Deal 2 damage to any target."
            ]
            abilities.append(random.choice(activated_abilities))
        
        return ', '.join(abilities) if abilities else "No abilities."
    
    def generate_spell_text(self, theme, card_type, power_level):
        """Generate spell effects"""
        if card_type == 'Instant':
            effects = [
                "Deal 3 damage to any target.",
                "Counter target spell.",
                "Draw two cards.",
                "Destroy target creature.",
                "Target creature gets +3/+3 until end of turn."
            ]
        elif card_type == 'Sorcery':
            effects = [
                "Deal 4 damage to target creature or player.",
                "Draw three cards.",
                "Destroy all creatures.",
                "Search your library for a basic land card and put it onto the battlefield.",
                "Return target creature to its owner's hand."
            ]
        elif card_type == 'Enchantment':
            effects = [
                "At the beginning of your upkeep, gain 1 life.",
                "Creatures you control get +1/+1.",
                "Whenever a creature enters the battlefield, draw a card.",
                "Players can't cast spells during combat."
            ]
        else:  # Artifact
            effects = [
                "{T}: Add one mana of any color.",
                "{T}: Deal 1 damage to any target.",
                "Creatures you control have vigilance.",
                "{T}: Draw a card, then discard a card."
            ]
        
        return random.choice(effects)
    
    def generate_land_text(self, theme):
        """Generate land abilities"""
        basic_lands = [
            "{T}: Add {W}.",
            "{T}: Add {U}.",
            "{T}: Add {B}.",
            "{T}: Add {R}.",
            "{T}: Add {G}."
        ]
        
        special_lands = [
            "{T}: Add {C}.\\n{T}: Add one mana of any color. This land enters the battlefield tapped.",
            "{T}: Add {C}.\\n{1}, {T}: Target creature gets +1/+1 until end of turn."
        ]
        
        if theme:
            return random.choice(basic_lands + special_lands)
        else:
            return random.choice(basic_lands)
    
    def generate_power_toughness(self, mana_cost, power_level):
        """Generate creature power and toughness"""
        # Convert mana cost to CMC estimate
        cmc = self.estimate_cmc(mana_cost)
        
        # Base stats on CMC and power level
        if power_level == 'low':
            base_power = max(1, cmc - 1)
            base_toughness = max(1, cmc)
        elif power_level == 'medium':
            base_power = max(1, cmc)
            base_toughness = max(1, cmc)
        else:  # high
            base_power = max(2, cmc + 1)
            base_toughness = max(1, cmc)
        
        # Add some variation
        power = max(1, base_power + random.randint(-1, 1))
        toughness = max(1, base_toughness + random.randint(-1, 1))
        
        return power, toughness
    
    def estimate_cmc(self, mana_cost):
        """Estimate converted mana cost from string"""
        if not mana_cost:
            return 0
        
        # Simple estimation - count numbers and mana symbols
        import re
        numbers = re.findall(r'\{(\d+)\}', mana_cost)
        symbols = re.findall(r'\{[WUBRG]\}', mana_cost)
        
        numeric_cost = sum(int(n) for n in numbers)
        symbol_cost = len(symbols)
        
        return numeric_cost + symbol_cost
    
    def determine_rarity(self, power_level):
        """Determine card rarity"""
        rarity_map = {
            'low': 'Common',
            'medium': 'Uncommon',
            'high': 'Rare'
        }
        return rarity_map.get(power_level, 'Common')
    
    def create_card_image(self, card_data):
        """Create visual card image"""
        if not IMAGING_AVAILABLE:
            return None
        
        try:
            # Determine template type
            card_type = card_data['type']
            if 'Creature' in card_type:
                template = self.card_templates.get('creature')
            elif card_type == 'Land':
                template = self.card_templates.get('land')
            else:
                template = self.card_templates.get('spell')
            
            if not template:
                print("[WARN] No template available")
                return None
            
            # Create card image
            img = template['image'].copy()
            draw = ImageDraw.Draw(img)
            
            # Add card text (simplified - would need proper fonts)
            try:
                # Use default font
                font_size = 20
                font = ImageFont.load_default()
                
                # Add name
                name_area = template['areas']['name']
                draw.text((name_area[0], name_area[1]), card_data['name'], 
                         fill='white', font=font)
                
                # Add mana cost
                if 'cost' in template['areas']:
                    cost_area = template['areas']['cost']
                    draw.text((cost_area[0], cost_area[1]), card_data['mana_cost'], 
                             fill='yellow', font=font)
                
                # Add type
                type_area = template['areas']['type']
                draw.text((type_area[0], type_area[1]), card_data['type'], 
                         fill='white', font=font)
                
                # Add text
                text_area = template['areas']['text']
                # Wrap text (simplified)
                text_lines = self.wrap_text(card_data['text'], 40)
                y_offset = text_area[1]
                for line in text_lines[:5]:  # Limit lines
                    draw.text((text_area[0], y_offset), line, 
                             fill='black', font=font)
                    y_offset += 25
                
                # Add power/toughness for creatures
                if card_data['power'] is not None:
                    pt_area = template['areas']['power_toughness']
                    pt_text = f"{card_data['power']}/{card_data['toughness']}"
                    draw.text((pt_area[0], pt_area[1]), pt_text, 
                             fill='white', font=font)
                
            except Exception as e:
                print(f"[WARN] Text rendering error: {e}")
            
            # Save image
            card_id = hashlib.md5(card_data['name'].encode()).hexdigest()[:8]
            image_path = self.output_dir / f"card_{card_id}.png"
            img.save(image_path)
            
            return str(image_path)
            
        except Exception as e:
            print(f"[WARN] Image creation error: {e}")
            return None
    
    def wrap_text(self, text, width):
        """Simple text wrapping"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def save_generated_card(self, card_data, image_path):
        """Save generated card data"""
        card_id = hashlib.md5(card_data['name'].encode()).hexdigest()[:8]
        data_file = self.output_dir / f"card_{card_id}.json"
        
        card_record = {
            **card_data,
            'image_path': image_path,
            'card_id': card_id
        }
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(card_record, f, indent=2)
        
        return str(data_file)
    
    def generate_card_set(self, theme, count=5, power_levels=None):
        """Generate a set of related cards"""
        if not power_levels:
            power_levels = ['low', 'medium', 'high']
        
        print(f"🎨 Generating {count} cards for theme: {theme}")
        
        generated_cards = []
        for i in range(count):
            power_level = random.choice(power_levels)
            card_type = random.choice(self.card_types)
            
            card = self.generate_custom_card(theme, card_type, power_level)
            generated_cards.append(card)
            
            print(f"  {i+1}/{count}: {card['card_data']['name']}")
        
        # Save set metadata
        set_data = {
            'theme': theme,
            'generated_at': datetime.now().isoformat(),
            'cards': [card['card_data'] for card in generated_cards]
        }
        
        set_file = self.output_dir / f"set_{theme}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(set_file, 'w', encoding='utf-8') as f:
            json.dump(set_data, f, indent=2)
        
        print(f"[OK] Generated {count}-card set saved to: {set_file}")
        return generated_cards


class DeckThemeAnalyzer:
    """AI-powered deck theme analysis and artistic coherence scoring"""
    
    def __init__(self, master_db_path=None):
        self.master_db_path = master_db_path or r"E:\MTTGG\MASTER  SHEETS\Master File .csv"
        self.deck_templates_dir = Path(r"E:\MTTGG\Decklist templates")
        self.analysis_cache = {}
        
        # Theme categories
        self.theme_categories = {
            'tribal': ['Human', 'Elf', 'Goblin', 'Dragon', 'Angel', 'Vampire', 'Zombie'],
            'mechanical': ['Artifact', 'Enchantment', 'Graveyard', 'Counter', 'Token'],
            'color_identity': ['Mono-White', 'Mono-Blue', 'Mono-Black', 'Mono-Red', 'Mono-Green'],
            'playstyle': ['Aggro', 'Control', 'Midrange', 'Combo', 'Ramp'],
            'setting': ['Innistrad', 'Ravnica', 'Zendikar', 'Dominaria', 'Phyrexia']
        }
        
        # Load card database for analysis
        self.card_database = {}
        self.load_card_database()
        
        print("📊 Deck Theme Analyzer initialized")
    
    def load_card_database(self):
        """Load card database for theme analysis"""
        try:
            if os.path.exists(self.master_db_path):
                import csv
                with open(self.master_db_path, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get('Name', '').strip()
                        if name:
                            self.card_database[name] = {
                                'type': row.get('Type', ''),
                                'colors': row.get('Colors', ''),
                                'keywords': row.get('Keywords', ''),
                                'text': row.get('Oracle Text', ''),
                                'set': row.get('Set', ''),
                                'artist': row.get('Artist', ''),
                                'flavor': row.get('Flavor Text', '')
                            }
                
                print(f"[OK] Loaded {len(self.card_database)} cards for theme analysis")
            else:
                print("[WARN] Master database not found - using limited analysis")
        except Exception as e:
            print(f"[WARN] Database load error: {e}")
    
    def analyze_deck_theme(self, deck_list, deck_name="Unknown Deck"):
        """Analyze the thematic coherence of a deck"""
        print(f"📊 Analyzing deck theme: {deck_name}")
        
        # Parse deck list
        cards = self.parse_deck_list(deck_list)
        
        if not cards:
            return {'error': 'No valid cards found in deck list'}
        
        # Perform various theme analyses
        analysis = {
            'deck_name': deck_name,
            'total_cards': len(cards),
            'tribal_analysis': self.analyze_tribal_theme(cards),
            'color_analysis': self.analyze_color_theme(cards),
            'mechanical_analysis': self.analyze_mechanical_theme(cards),
            'artistic_coherence': self.analyze_artistic_coherence(cards),
            'playstyle_analysis': self.analyze_playstyle(cards),
            'overall_theme_score': 0,
            'theme_suggestions': [],
            'coherence_issues': [],
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Calculate overall theme score
        analysis['overall_theme_score'] = self.calculate_overall_theme_score(analysis)
        
        # Generate suggestions
        analysis['theme_suggestions'] = self.generate_theme_suggestions(analysis, cards)
        
        # Identify coherence issues
        analysis['coherence_issues'] = self.identify_coherence_issues(analysis, cards)
        
        print(f"[OK] Theme analysis complete - Score: {analysis['overall_theme_score']:.1f}/100")
        return analysis
    
    def parse_deck_list(self, deck_list):
        """Parse deck list text into card objects"""
        cards = []
        
        if isinstance(deck_list, str):
            lines = deck_list.strip().split('\n')
        elif isinstance(deck_list, list):
            lines = deck_list
        else:
            return cards
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('#'):
                continue
            
            # Parse "quantity cardname" format
            import re
            match = re.match(r'^(\d+)\s+(.+)$', line)
            if match:
                quantity = int(match.group(1))
                card_name = match.group(2).strip()
                
                # Get card data from database
                card_data = self.card_database.get(card_name, {})
                
                cards.append({
                    'name': card_name,
                    'quantity': quantity,
                    'type': card_data.get('type', ''),
                    'colors': card_data.get('colors', ''),
                    'keywords': card_data.get('keywords', ''),
                    'text': card_data.get('text', ''),
                    'set': card_data.get('set', ''),
                    'artist': card_data.get('artist', ''),
                    'flavor': card_data.get('flavor', '')
                })
        
        return cards
    
    def analyze_tribal_theme(self, cards):
        """Analyze tribal creature themes in deck"""
        creature_types = {}
        total_creatures = 0
        
        for card in cards:
            if 'Creature' in card.get('type', ''):
                total_creatures += card['quantity']
                
                # Extract creature types
                card_type = card.get('type', '')
                for tribe in self.theme_categories['tribal']:
                    if tribe in card_type:
                        creature_types[tribe] = creature_types.get(tribe, 0) + card['quantity']
        
        if not creature_types:
            return {
                'dominant_tribe': None,
                'tribal_density': 0,
                'tribal_score': 0,
                'tribes_present': []
            }
        
        # Find dominant tribe
        dominant_tribe = max(creature_types.items(), key=lambda x: x[1])
        tribal_density = dominant_tribe[1] / total_creatures if total_creatures > 0 else 0
        
        # Calculate tribal score (higher for focused tribal decks)
        tribal_score = min(100, tribal_density * 120) if tribal_density > 0.3 else tribal_density * 50
        
        return {
            'dominant_tribe': dominant_tribe[0],
            'tribe_count': dominant_tribe[1],
            'tribal_density': tribal_density,
            'tribal_score': tribal_score,
            'tribes_present': list(creature_types.keys()),
            'all_tribes': creature_types
        }
    
    def analyze_color_theme(self, cards):
        """Analyze color identity and mana curve coherence"""
        color_counts = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
        multicolor_count = 0
        total_cards = 0
        
        for card in cards:
            colors = card.get('colors', '')
            quantity = card['quantity']
            total_cards += quantity
            
            if not colors or colors == 'C':
                color_counts['C'] += quantity
            else:
                for color in 'WUBRG':
                    if color in colors:
                        color_counts[color] += quantity
                
                if len([c for c in 'WUBRG' if c in colors]) > 1:
                    multicolor_count += quantity
        
        # Determine color identity
        present_colors = [color for color, count in color_counts.items() 
                         if count > 0 and color != 'C']
        
        # Calculate color focus score
        if len(present_colors) == 1:
            color_focus = 'Mono-' + present_colors[0]
            focus_score = 90
        elif len(present_colors) == 2:
            color_focus = ''.join(present_colors)
            focus_score = 75
        elif len(present_colors) == 3:
            color_focus = 'Tri-color'
            focus_score = 60
        else:
            color_focus = 'Multi-color'
            focus_score = 40
        
        # Penalize for too much multicolor in focused decks
        if len(present_colors) <= 2 and multicolor_count / total_cards > 0.3:
            focus_score -= 20
        
        return {
            'color_identity': present_colors,
            'color_focus': color_focus,
            'color_distribution': color_counts,
            'multicolor_density': multicolor_count / total_cards,
            'color_focus_score': max(0, focus_score)
        }
    
    def analyze_mechanical_theme(self, cards):
        """Analyze mechanical themes and synergies"""
        mechanics = {}
        artifact_count = 0
        enchantment_count = 0
        
        # Common MTG mechanics to look for
        common_mechanics = [
            'Flying', 'Trample', 'First Strike', 'Double Strike', 'Deathtouch',
            'Lifelink', 'Vigilance', 'Reach', 'Haste', 'Hexproof', 'Indestructible',
            'Flash', 'Defender', 'Menace', 'Prowess', 'Scry', 'Surveil',
            'Convoke', 'Delve', 'Affinity', 'Storm', 'Flashback', 'Cascade'
        ]
        
        for card in cards:
            card_text = card.get('text', '') + ' ' + card.get('keywords', '')
            card_type = card.get('type', '')
            quantity = card['quantity']
            
            # Count artifact/enchantment themes
            if 'Artifact' in card_type:
                artifact_count += quantity
            if 'Enchantment' in card_type:
                enchantment_count += quantity
            
            # Count mechanics
            for mechanic in common_mechanics:
                if mechanic.lower() in card_text.lower():
                    mechanics[mechanic] = mechanics.get(mechanic, 0) + quantity
        
        # Find dominant mechanical theme
        total_cards = sum(card['quantity'] for card in cards)
        dominant_mechanic = None
        mechanic_score = 0
        
        if mechanics:
            dominant_mechanic = max(mechanics.items(), key=lambda x: x[1])
            mechanic_density = dominant_mechanic[1] / total_cards
            mechanic_score = min(100, mechanic_density * 150)
        
        # Special themes
        special_themes = {}
        if artifact_count / total_cards > 0.3:
            special_themes['Artifact'] = artifact_count / total_cards * 100
        if enchantment_count / total_cards > 0.3:
            special_themes['Enchantment'] = enchantment_count / total_cards * 100
        
        return {
            'dominant_mechanic': dominant_mechanic[0] if dominant_mechanic else None,
            'mechanic_count': dominant_mechanic[1] if dominant_mechanic else 0,
            'mechanic_score': mechanic_score,
            'all_mechanics': mechanics,
            'special_themes': special_themes,
            'artifact_density': artifact_count / total_cards,
            'enchantment_density': enchantment_count / total_cards
        }
    
    def analyze_artistic_coherence(self, cards):
        """Analyze artistic and flavor coherence"""
        # This is a simplified analysis - in a full implementation,
        # you might analyze actual card art or use more sophisticated methods
        
        sets_present = {}
        artists_present = {}
        flavor_themes = []
        
        for card in cards:
            card_set = card.get('set', 'Unknown')
            artist = card.get('artist', 'Unknown')
            flavor = card.get('flavor', '')
            quantity = card['quantity']
            
            sets_present[card_set] = sets_present.get(card_set, 0) + quantity
            artists_present[artist] = artists_present.get(artist, 0) + quantity
            
            # Simple flavor analysis
            if flavor:
                flavor_themes.append(flavor.lower())
        
        total_cards = sum(card['quantity'] for card in cards)
        
        # Calculate set coherence (fewer sets = more coherent)
        set_coherence = 100 / len(sets_present) if sets_present else 0
        
        # Find dominant set
        dominant_set = max(sets_present.items(), key=lambda x: x[1]) if sets_present else ('Unknown', 0)
        set_focus = dominant_set[1] / total_cards
        
        # Artist diversity analysis
        artist_diversity = len(artists_present)
        
        # Simple flavor coherence (look for common words)
        flavor_coherence = 0
        if flavor_themes:
            common_words = ['dark', 'light', 'magic', 'power', 'ancient', 'war', 'peace']
            word_counts = {}
            for flavor in flavor_themes:
                for word in common_words:
                    if word in flavor:
                        word_counts[word] = word_counts.get(word, 0) + 1
            
            if word_counts:
                max_word_count = max(word_counts.values())
                flavor_coherence = (max_word_count / len(flavor_themes)) * 100
        
        coherence_score = (set_coherence * 0.4) + (flavor_coherence * 0.3) + \
                         (min(50, 100 - artist_diversity * 2) * 0.3)
        
        return {
            'artistic_coherence_score': coherence_score,
            'dominant_set': dominant_set[0],
            'set_focus': set_focus,
            'sets_present': list(sets_present.keys()),
            'artist_diversity': artist_diversity,
            'flavor_coherence': flavor_coherence,
            'set_distribution': sets_present
        }
    
    def calculate_overall_theme_score(self, analysis):
        """Calculate overall thematic coherence score"""
        scores = [
            analysis['tribal_analysis']['tribal_score'] * 0.25,
            analysis['color_analysis']['color_focus_score'] * 0.25,
            analysis['mechanical_analysis']['mechanic_score'] * 0.20,
            analysis['artistic_coherence']['artistic_coherence_score'] * 0.15,
            analysis['playstyle_analysis']['curve_score'] * 0.15
        ]
        
        return sum(scores)
    
    def analyze_playstyle(self, cards):
        """Analyze deck playstyle and strategy"""
        cmc_distribution = {i: 0 for i in range(8)}  # 0-7+ mana costs
        creature_count = 0
        instant_sorcery_count = 0
        
        for card in cards:
            card_type = card.get('type', '')
            quantity = card['quantity']
            
            # Estimate CMC (simplified)
            cmc = self.estimate_cmc_from_text(card.get('text', ''))
            cmc_key = min(7, cmc)  # Cap at 7+
            cmc_distribution[cmc_key] += quantity
            
            if 'Creature' in card_type:
                creature_count += quantity
            elif 'Instant' in card_type or 'Sorcery' in card_type:
                instant_sorcery_count += quantity
        
        total_cards = sum(card['quantity'] for card in cards)
        
        # Analyze curve
        low_cmc = sum(cmc_distribution[i] for i in range(3))  # 0-2 CMC
        mid_cmc = sum(cmc_distribution[i] for i in range(3, 5))  # 3-4 CMC
        high_cmc = sum(cmc_distribution[i] for i in range(5, 8))  # 5+ CMC
        
        # Determine playstyle
        playstyle = 'Unknown'
        if low_cmc / total_cards > 0.6:
            playstyle = 'Aggro'
        elif high_cmc / total_cards > 0.4:
            playstyle = 'Control'
        elif mid_cmc / total_cards > 0.5:
            playstyle = 'Midrange'
        elif instant_sorcery_count / total_cards > 0.5:
            playstyle = 'Spell-based'
        
        curve_score = self.calculate_curve_score(cmc_distribution, playstyle)
        
        return {
            'playstyle': playstyle,
            'cmc_distribution': cmc_distribution,
            'avg_cmc': sum(cmc * count for cmc, count in cmc_distribution.items()) / total_cards,
            'creature_density': creature_count / total_cards,
            'spell_density': instant_sorcery_count / total_cards,
            'curve_score': curve_score
        }
    
    def estimate_cmc_from_text(self, text):
        """Simple CMC estimation from card text"""
        # This is a very basic estimation
        # In a real implementation, you'd parse the actual mana cost
        if 'mana cost' in text.lower():
            return 0  # Lands typically
        elif len(text) < 50:
            return random.randint(1, 3)  # Simple cards
        elif len(text) < 100:
            return random.randint(2, 5)  # Medium complexity
        else:
            return random.randint(4, 7)  # Complex cards
    
    def calculate_curve_score(self, cmc_dist, playstyle):
        """Calculate how well the mana curve fits the playstyle"""
        total = sum(cmc_dist.values())
        if total == 0:
            return 0
        
        # Ideal distributions for different playstyles
        ideal_curves = {
            'Aggro': [0.1, 0.3, 0.3, 0.2, 0.1, 0.0, 0.0, 0.0],
            'Midrange': [0.1, 0.2, 0.3, 0.25, 0.1, 0.05, 0.0, 0.0],
            'Control': [0.05, 0.1, 0.15, 0.2, 0.2, 0.15, 0.1, 0.05],
            'Unknown': [0.15, 0.2, 0.2, 0.2, 0.15, 0.1, 0.0, 0.0]
        }
        
        ideal = ideal_curves.get(playstyle, ideal_curves['Unknown'])
        actual = [count/total for count in cmc_dist.values()]
        
        # Calculate similarity (inverse of difference)
        difference = sum(abs(ideal[i] - actual[i]) for i in range(8))
        similarity = max(0, 100 - (difference * 100))
        
        return similarity
    
    def generate_theme_suggestions(self, analysis, cards):
        """Generate suggestions to improve thematic coherence"""
        suggestions = []
        
        # Tribal suggestions
        tribal = analysis['tribal_analysis']
        if tribal['tribal_score'] > 0 and tribal['tribal_score'] < 70:
            suggestions.append(f"Consider adding more {tribal['dominant_tribe']} creatures to strengthen tribal theme")
        
        # Color suggestions
        color = analysis['color_analysis']
        if len(color['color_identity']) > 3:
            suggestions.append("Consider reducing colors for better mana consistency")
        
        # Mechanical suggestions
        mechanical = analysis['mechanical_analysis']
        if mechanical['mechanic_score'] < 50:
            suggestions.append("Consider focusing on a specific mechanic or synergy")
        
        # Curve suggestions
        playstyle = analysis['playstyle_analysis']
        if playstyle['curve_score'] < 60:
            suggestions.append(f"Adjust mana curve for better {playstyle['playstyle']} strategy")
        
        return suggestions
    
    def identify_coherence_issues(self, analysis, cards):
        """Identify specific coherence issues"""
        issues = []
        
        # Color identity issues
        color = analysis['color_analysis']
        if color['multicolor_density'] > 0.4 and len(color['color_identity']) <= 2:
            issues.append("High multicolor density may cause mana problems")
        
        # Tribal inconsistency
        tribal = analysis['tribal_analysis']
        if 0 < tribal['tribal_score'] < 40:
            issues.append("Weak tribal focus - either commit more or diversify")
        
        # Curve issues
        playstyle = analysis['playstyle_analysis']
        if playstyle['avg_cmc'] > 4.5:
            issues.append("Mana curve may be too high for consistent play")
        
        return issues


class AutomatedDeckNamer:
    """AI-powered automated deck naming system"""
    
    def __init__(self, master_db_path=None):
        self.master_db_path = master_db_path or r"E:\MTTGG\MASTER  SHEETS\Master File .csv"
        
        # Naming patterns and vocabularies
        self.name_patterns = {
            'tribal': [
                "{tribe} {descriptor}",
                "{descriptor} {tribe} {format}",
                "The {tribe} {concept}",
                "{tribe} {strategy}",
                "{adjective} {tribe} Force"
            ],
            'color': [
                "{color} {strategy}",
                "{color} {concept}",
                "Mono-{color} {descriptor}",
                "{color} {playstyle} Deck",
                "The {color} {theme}"
            ],
            'mechanical': [
                "{mechanic} {strategy}",
                "{mechanic}-based {concept}",
                "The {mechanic} Engine",
                "{adjective} {mechanic}",
                "{mechanic} {format}"
            ],
            'playstyle': [
                "{speed} {strategy}",
                "{strategy} {concept}",
                "Ultimate {strategy}",
                "{adjective} {strategy}",
                "The {strategy} Machine"
            ],
            'thematic': [
                "{theme} {concept}",
                "Tales of {theme}",
                "{theme} Chronicles",
                "The {theme} Saga",
                "{adjective} {theme}"
            ]
        }
        
        # Vocabularies for different categories
        self.vocabularies = {
            'descriptors': [
                'Mighty', 'Ancient', 'Legendary', 'Elite', 'Supreme',
                'Eternal', 'Sacred', 'Mystic', 'Royal', 'Divine'
            ],
            'concepts': [
                'Alliance', 'Legion', 'Coalition', 'Assembly', 'Brotherhood',
                'Order', 'Circle', 'Guild', 'Clan', 'Empire'
            ],
            'strategies': [
                'Dominance', 'Control', 'Assault', 'Rush', 'Storm',
                'Siege', 'Blitz', 'Strike', 'Wave', 'Surge'
            ],
            'adjectives': [
                'Unstoppable', 'Relentless', 'Devastating', 'Overwhelming',
                'Powerful', 'Fearless', 'Brutal', 'Swift', 'Cunning'
            ],
            'formats': [
                'Army', 'Force', 'Squad', 'Battalion', 'Regiment',
                'Brigade', 'Division', 'Company', 'Unit', 'Faction'
            ],
            'themes': [
                'Shadow', 'Light', 'Fire', 'Storm', 'Nature',
                'Chaos', 'Order', 'Darkness', 'Dawn', 'Twilight'
            ],
            'colors': {
                'W': 'White', 'U': 'Blue', 'B': 'Black', 
                'R': 'Red', 'G': 'Green', 'C': 'Colorless'
            }
        }
        
        # Creative naming elements
        self.creative_elements = {
            'fantasy_words': [
                'Arcane', 'Mystical', 'Ethereal', 'Celestial', 'Infernal',
                'Primordial', 'Spectral', 'Temporal', 'Astral', 'Elemental'
            ],
            'action_words': [
                'Rising', 'Awakening', 'Ascending', 'Conquering', 'Dominating',
                'Emerging', 'Unleashed', 'Triumphant', 'Victorious', 'Legendary'
            ],
            'power_words': [
                'Titan', 'Overlord', 'Champion', 'Master', 'Lord',
                'King', 'Emperor', 'Sovereign', 'Ruler', 'Commander'
            ]
        }
        
        print("🏷️ Automated Deck Namer initialized")
    
    def generate_deck_name(self, deck_analysis, style='auto', creativity_level='medium'):
        """Generate a thematic deck name based on analysis"""
        print(f"🏷️ Generating deck name - Style: {style}, Creativity: {creativity_level}")
        
        if not deck_analysis or 'error' in deck_analysis:
            return self.generate_fallback_name(style, creativity_level)
        
        # Determine naming approach based on strongest theme
        naming_approach = self.determine_naming_approach(deck_analysis, style)
        
        # Generate name candidates
        candidates = self.generate_name_candidates(deck_analysis, naming_approach, creativity_level)
        
        # Score and select best name
        best_name = self.select_best_name(candidates, deck_analysis, creativity_level)
        
        print(f"[OK] Generated deck name: {best_name}")
        return best_name
    
    def determine_naming_approach(self, deck_analysis, style):
        """Determine the best naming approach based on deck characteristics"""
        if style != 'auto':
            return style
        
        # Score different approaches
        approach_scores = {
            'tribal': deck_analysis.get('tribal_analysis', {}).get('tribal_score', 0),
            'color': deck_analysis.get('color_analysis', {}).get('color_focus_score', 0),
            'mechanical': deck_analysis.get('mechanical_analysis', {}).get('mechanic_score', 0),
            'playstyle': deck_analysis.get('playstyle_analysis', {}).get('curve_score', 0),
            'thematic': deck_analysis.get('artistic_coherence', {}).get('artistic_coherence_score', 0)
        }
        
        # Choose approach with highest score
        best_approach = max(approach_scores.items(), key=lambda x: x[1])
        
        # If no clear winner, use most distinctive feature
        if best_approach[1] < 50:
            return 'playstyle'  # Default to playstyle
        
        return best_approach[0]
    
    def generate_name_candidates(self, deck_analysis, approach, creativity_level):
        """Generate multiple name candidates"""
        candidates = []
        
        if approach == 'tribal':
            candidates.extend(self.generate_tribal_names(deck_analysis, creativity_level))
        elif approach == 'color':
            candidates.extend(self.generate_color_names(deck_analysis, creativity_level))
        elif approach == 'mechanical':
            candidates.extend(self.generate_mechanical_names(deck_analysis, creativity_level))
        elif approach == 'playstyle':
            candidates.extend(self.generate_playstyle_names(deck_analysis, creativity_level))
        else:  # thematic
            candidates.extend(self.generate_thematic_names(deck_analysis, creativity_level))
        
        # Add some creative alternatives
        if creativity_level in ['high', 'maximum']:
            candidates.extend(self.generate_creative_names(deck_analysis))
        
        return candidates
    
    def generate_tribal_names(self, deck_analysis, creativity_level):
        """Generate names based on tribal theme"""
        names = []
        tribal_data = deck_analysis.get('tribal_analysis', {})
        
        if not tribal_data.get('dominant_tribe'):
            return names
        
        tribe = tribal_data['dominant_tribe']
        patterns = self.name_patterns['tribal']
        
        for pattern in patterns:
            # Basic substitutions
            name = pattern.format(
                tribe=tribe,
                descriptor=random.choice(self.vocabularies['descriptors']),
                format=random.choice(self.vocabularies['formats']),
                concept=random.choice(self.vocabularies['concepts']),
                strategy=random.choice(self.vocabularies['strategies']),
                adjective=random.choice(self.vocabularies['adjectives'])
            )
            names.append(name)
        
        # Creativity variations
        if creativity_level in ['medium', 'high']:
            # Add fantasy elements
            fantasy_names = [
                f"{random.choice(self.creative_elements['fantasy_words'])} {tribe} {random.choice(self.vocabularies['concepts'])}",
                f"{tribe} {random.choice(self.creative_elements['action_words'])}",
                f"The {random.choice(self.creative_elements['power_words'])} of {tribe}s"
            ]
            names.extend(fantasy_names)
        
        return names
    
    def generate_color_names(self, deck_analysis, creativity_level):
        """Generate names based on color identity"""
        names = []
        color_data = deck_analysis.get('color_analysis', {})
        
        color_identity = color_data.get('color_identity', [])
        if not color_identity:
            return names
        
        patterns = self.name_patterns['color']
        
        # Handle different color combinations
        if len(color_identity) == 1:
            color_name = self.vocabularies['colors'][color_identity[0]]
            color_theme = self.get_color_theme(color_identity[0])
            
            for pattern in patterns[:3]:  # Use mono-color patterns
                name = pattern.format(
                    color=color_name,
                    strategy=random.choice(self.vocabularies['strategies']),
                    concept=random.choice(self.vocabularies['concepts']),
                    descriptor=random.choice(self.vocabularies['descriptors']),
                    playstyle=deck_analysis.get('playstyle_analysis', {}).get('playstyle', 'Control'),
                    theme=color_theme
                )
                names.append(name)
        
        elif len(color_identity) == 2:
            # Two-color combinations
            guild_name = self.get_guild_name(color_identity)
            names.extend([
                f"{guild_name} Alliance",
                f"{guild_name} {random.choice(self.vocabularies['strategies'])}",
                f"The {guild_name} {random.choice(self.vocabularies['concepts'])}"
            ])
        
        else:
            # Multi-color
            names.extend([
                f"Rainbow {random.choice(self.vocabularies['strategies'])}",
                f"Prismatic {random.choice(self.vocabularies['concepts'])}",
                f"Chromatic {random.choice(self.vocabularies['formats'])}"
            ])
        
        return names
    
    def generate_mechanical_names(self, deck_analysis, creativity_level):
        """Generate names based on mechanical theme"""
        names = []
        mechanical_data = deck_analysis.get('mechanical_analysis', {})
        
        dominant_mechanic = mechanical_data.get('dominant_mechanic')
        if not dominant_mechanic:
            return names
        
        patterns = self.name_patterns['mechanical']
        
        for pattern in patterns:
            name = pattern.format(
                mechanic=dominant_mechanic,
                strategy=random.choice(self.vocabularies['strategies']),
                concept=random.choice(self.vocabularies['concepts']),
                adjective=random.choice(self.vocabularies['adjectives']),
                format=random.choice(self.vocabularies['formats'])
            )
            names.append(name)
        
        # Special mechanical themes
        special_themes = mechanical_data.get('special_themes', {})
        for theme, density in special_themes.items():
            if density > 60:
                names.extend([
                    f"{theme} {random.choice(self.vocabularies['strategies'])}",
                    f"Pure {theme} {random.choice(self.vocabularies['concepts'])}",
                    f"{theme}-Based {random.choice(self.vocabularies['formats'])}"
                ])
        
        return names
    
    def generate_playstyle_names(self, deck_analysis, creativity_level):
        """Generate names based on playstyle"""
        names = []
        playstyle_data = deck_analysis.get('playstyle_analysis', {})
        
        playstyle = playstyle_data.get('playstyle', 'Unknown')
        if playstyle == 'Unknown':
            return names
        
        patterns = self.name_patterns['playstyle']
        
        # Map playstyles to appropriate words
        playstyle_mapping = {
            'Aggro': {'speed': 'Lightning', 'strategy': 'Blitz', 'concept': 'Strike Force'},
            'Control': {'speed': 'Patient', 'strategy': 'Control', 'concept': 'Dominion'},
            'Midrange': {'speed': 'Balanced', 'strategy': 'Tempo', 'concept': 'Coalition'},
            'Combo': {'speed': 'Explosive', 'strategy': 'Combo', 'concept': 'Engine'},
            'Ramp': {'speed': 'Massive', 'strategy': 'Ramp', 'concept': 'Titans'}
        }
        
        style_words = playstyle_mapping.get(playstyle, {
            'speed': 'Swift', 'strategy': playstyle, 'concept': 'Force'
        })
        
        for pattern in patterns:
            name = pattern.format(
                speed=style_words['speed'],
                strategy=style_words['strategy'],
                concept=style_words['concept'],
                adjective=random.choice(self.vocabularies['adjectives'])
            )
            names.append(name)
        
        return names
    
    def generate_thematic_names(self, deck_analysis, creativity_level):
        """Generate names based on artistic/thematic coherence"""
        names = []
        artistic_data = deck_analysis.get('artistic_coherence', {})
        
        dominant_set = artistic_data.get('dominant_set', 'Unknown')
        if dominant_set == 'Unknown':
            return names
        
        # Map sets to themes
        set_themes = {
            'Innistrad': 'Gothic Horror',
            'Ravnica': 'Urban Guild',
            'Zendikar': 'Adventure',
            'Dominaria': 'Legacy',
            'Phyrexia': 'Corruption',
            'Kamigawa': 'Honor',
            'Mirrodin': 'Artifact'
        }
        
        theme = set_themes.get(dominant_set, 'Mystical')
        patterns = self.name_patterns['thematic']
        
        for pattern in patterns:
            name = pattern.format(
                theme=theme,
                concept=random.choice(self.vocabularies['concepts']),
                adjective=random.choice(self.vocabularies['adjectives'])
            )
            names.append(name)
        
        return names
    
    def generate_creative_names(self, deck_analysis):
        """Generate highly creative and unique names"""
        creative_names = []
        
        # Combine random elements creatively
        fantasy = self.creative_elements['fantasy_words']
        actions = self.creative_elements['action_words']
        powers = self.creative_elements['power_words']
        
        creative_patterns = [
            f"{random.choice(fantasy)} {random.choice(actions)}",
            f"The {random.choice(powers)} {random.choice(fantasy)}",
            f"{random.choice(actions)} {random.choice(powers)}",
            f"Codex of {random.choice(fantasy)} {random.choice(powers)}",
            f"The {random.choice(fantasy)} Prophecy",
            f"Saga of {random.choice(actions)} {random.choice(power)}s",
            f"{random.choice(fantasy)} {random.choice(actions)} Chronicles"
        ]
        
        creative_names.extend(creative_patterns)
        
        return creative_names
    
    def select_best_name(self, candidates, deck_analysis, creativity_level):
        """Select the best name from candidates"""
        if not candidates:
            return self.generate_fallback_name('auto', creativity_level)
        
        # Score names based on various criteria
        scored_names = []
        
        for name in candidates:
            score = self.score_name(name, deck_analysis, creativity_level)
            scored_names.append((name, score))
        
        # Sort by score and return best
        scored_names.sort(key=lambda x: x[1], reverse=True)
        
        # Add some randomness for creativity
        if creativity_level == 'high':
            # Pick from top 3
            top_names = scored_names[:3]
            return random.choice(top_names)[0]
        else:
            return scored_names[0][0]
    
    def score_name(self, name, deck_analysis, creativity_level):
        """Score a deck name based on various factors"""
        score = 50  # Base score
        
        # Length scoring (prefer reasonable lengths)
        length = len(name)
        if 15 <= length <= 30:
            score += 20
        elif 10 <= length <= 40:
            score += 10
        else:
            score -= 10
        
        # Readability (avoid too many consecutive consonants)
        if self.is_readable(name):
            score += 15
        
        # Uniqueness (prefer less common words)
        if self.is_unique(name):
            score += 10
        
        # Thematic consistency
        if self.matches_theme(name, deck_analysis):
            score += 25
        
        # Creativity bonus
        if creativity_level == 'high' and self.is_creative(name):
            score += 15
        
        return score
    
    def is_readable(self, name):
        """Check if name is easily readable"""
        # Simple heuristic: avoid too many consecutive consonants
        consonants = 'bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ'
        consecutive = 0
        max_consecutive = 0
        
        for char in name:
            if char in consonants:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        
        return max_consecutive <= 3
    
    def is_unique(self, name):
        """Check if name uses uncommon/unique words"""
        common_words = ['the', 'of', 'and', 'a', 'an', 'deck', 'magic', 'card']
        words = name.lower().split()
        
        unique_words = [w for w in words if w not in common_words]
        return len(unique_words) >= len(words) * 0.7
    
    def matches_theme(self, name, deck_analysis):
        """Check if name matches deck theme"""
        name_lower = name.lower()
        
        # Check tribal match
        tribal = deck_analysis.get('tribal_analysis', {})
        if tribal.get('dominant_tribe'):
            if tribal['dominant_tribe'].lower() in name_lower:
                return True
        
        # Check color match
        color = deck_analysis.get('color_analysis', {})
        for color_code in color.get('color_identity', []):
            color_name = self.vocabularies['colors'][color_code].lower()
            if color_name in name_lower:
                return True
        
        # Check playstyle match
        playstyle = deck_analysis.get('playstyle_analysis', {})
        if playstyle.get('playstyle', '').lower() in name_lower:
            return True
        
        return False
    
    def is_creative(self, name):
        """Check if name demonstrates creativity"""
        # Look for fantasy/creative elements
        for word_list in self.creative_elements.values():
            for word in word_list:
                if word.lower() in name.lower():
                    return True
        return False
    
    def get_color_theme(self, color_code):
        """Get thematic concept for color"""
        color_themes = {
            'W': 'Order',
            'U': 'Knowledge',
            'B': 'Power',
            'R': 'Chaos',
            'G': 'Nature',
            'C': 'Void'
        }
        return color_themes.get(color_code, 'Mystery')
    
    def get_guild_name(self, color_identity):
        """Get guild name for two-color combinations"""
        guild_map = {
            frozenset(['W', 'U']): 'Azorius',
            frozenset(['U', 'B']): 'Dimir',
            frozenset(['B', 'R']): 'Rakdos',
            frozenset(['R', 'G']): 'Gruul',
            frozenset(['G', 'W']): 'Selesnya',
            frozenset(['W', 'B']): 'Orzhov',
            frozenset(['U', 'R']): 'Izzet',
            frozenset(['B', 'G']): 'Golgari',
            frozenset(['R', 'W']): 'Boros',
            frozenset(['G', 'U']): 'Simic'
        }
        
        return guild_map.get(frozenset(color_identity), 'Prismatic')
    
    def generate_fallback_name(self, style, creativity_level):
        """Generate a fallback name when analysis is unavailable"""
        fallback_patterns = [
            f"{random.choice(self.vocabularies['descriptors'])} {random.choice(self.vocabularies['concepts'])}",
            f"{random.choice(self.vocabularies['adjectives'])} {random.choice(self.vocabularies['strategies'])}",
            f"The {random.choice(self.vocabularies['descriptors'])} {random.choice(self.vocabularies['formats'])}",
            f"{random.choice(self.creative_elements['fantasy_words'])} {random.choice(self.vocabularies['concepts'])}"
        ]
        
        return random.choice(fallback_patterns)
    
    def generate_multiple_names(self, deck_analysis, count=5, styles=None, creativity_level='medium'):
        """Generate multiple name options for a deck"""
        if not styles:
            styles = ['tribal', 'color', 'mechanical', 'playstyle', 'thematic']
        
        all_names = []
        
        for style in styles:
            name = self.generate_deck_name(deck_analysis, style, creativity_level)
            all_names.append({
                'name': name,
                'style': style,
                'creativity_level': creativity_level
            })
        
        # Add extra creative names if requested
        while len(all_names) < count:
            style = random.choice(styles)
            name = self.generate_deck_name(deck_analysis, style, 'high')
            all_names.append({
                'name': name,
                'style': style,
                'creativity_level': 'high'
            })
        
        return all_names[:count]


class StoryGenerator:
    """AI-powered story generation for custom Magic formats and lore"""
    
    def __init__(self, master_db_path=None):
        self.master_db_path = master_db_path or r"E:\MTTGG\MASTER  SHEETS\Master File .csv"
        self.stories_dir = Path(r"E:\MTTGG\Generated_Stories")
        self.stories_dir.mkdir(exist_ok=True)
        
        # Story templates and elements
        self.story_templates = {
            'origin': [
                "Long ago in the plane of {setting}, {protagonist} discovered {artifact}...",
                "In the {time_period} of {setting}, a great {conflict} threatened all who lived there...",
                "When {protagonist} first set foot in {setting}, they could never have imagined {discovery}..."
            ],
            'conflict': [
                "The peace was shattered when {antagonist} unleashed {threat} upon {setting}...",
                "{protagonist} faced their greatest challenge as {antagonist} sought to {evil_plan}...",
                "War erupted across {setting} as {faction_1} clashed with {faction_2}..."
            ],
            'resolution': [
                "With {ally}'s help, {protagonist} finally defeated {antagonist} using {solution}...",
                "The {artifact} proved to be the key to stopping {threat} and saving {setting}...",
                "Though {sacrifice} was great, {protagonist} restored peace to {setting}..."
            ]
        }
        
        # Story elements vocabulary
        self.story_elements = {
            'protagonists': [
                'a brave planeswalker', 'an ancient mage', 'a skilled artificer',
                'a noble knight', 'a cunning rogue', 'a wise druid',
                'a powerful wizard', 'a fearless warrior', 'a mysterious stranger'
            ],
            'antagonists': [
                'a dark overlord', 'an evil planeswalker', 'a corrupted deity',
                'a mad scientist', 'a demon lord', 'a fallen hero',
                'an ancient evil', 'a tyrannical emperor', 'a chaos entity'
            ],
            'settings': [
                'Ravnica', 'Innistrad', 'Zendikar', 'Dominaria', 'Phyrexia',
                'Mirrodin', 'Kamigawa', 'Lorwyn', 'Alara', 'Tarkir'
            ],
            'artifacts': [
                'an ancient crown', 'a magical sword', 'a mysterious orb',
                'a powerful ring', 'a sacred tome', 'a crystal of power',
                'an enchanted staff', 'a divine chalice', 'a cosmic key'
            ],
            'threats': [
                'a spreading darkness', 'an army of undead', 'a world-ending spell',
                'a plague of corruption', 'an invasion force', 'a reality storm',
                'a time rift', 'a magical catastrophe', 'an ancient curse'
            ],
            'conflicts': [
                'war', 'invasion', 'plague', 'corruption', 'betrayal',
                'revolution', 'cataclysm', 'awakening', 'convergence'
            ],
            'time_periods': [
                'golden age', 'dark times', 'age of heroes', 'time of chaos',
                'era of peace', 'days of legend', 'forgotten epoch'
            ],
            'factions': [
                'the Guild Alliance', 'the Shadow Council', 'the Order of Light',
                'the Crimson Legion', 'the Nature\'s Guard', 'the Arcane Circle',
                'the Steel Brotherhood', 'the Mystic Order', 'the Free Cities'
            ]
        }
        
        # Deck-specific story elements
        self.deck_story_mapping = {
            'tribal': {
                'Human': {'theme': 'civilization', 'conflict': 'unity vs division'},
                'Elf': {'theme': 'nature', 'conflict': 'preservation vs progress'},
                'Dragon': {'theme': 'power', 'conflict': 'dominance vs freedom'},
                'Angel': {'theme': 'divine order', 'conflict': 'justice vs mercy'},
                'Demon': {'theme': 'corruption', 'conflict': 'temptation vs purity'}
            },
            'color': {
                'White': {'theme': 'order and justice', 'emotion': 'righteousness'},
                'Blue': {'theme': 'knowledge and progress', 'emotion': 'curiosity'},
                'Black': {'theme': 'power and ambition', 'emotion': 'ruthlessness'},
                'Red': {'theme': 'freedom and passion', 'emotion': 'fury'},
                'Green': {'theme': 'nature and growth', 'emotion': 'harmony'}
            },
            'playstyle': {
                'Aggro': {'approach': 'swift and decisive action', 'mood': 'intense'},
                'Control': {'approach': 'patient strategy and planning', 'mood': 'calculated'},
                'Midrange': {'approach': 'balanced and adaptable', 'mood': 'steady'},
                'Combo': {'approach': 'complex schemes and synergy', 'mood': 'ingenious'}
            }
        }
        
        print("📚 Story Generator initialized")
    
    def generate_deck_story(self, deck_analysis, story_type='full', length='medium'):
        """Generate a story based on deck analysis"""
        print(f"📚 Generating {story_type} story - Length: {length}")
        
        if not deck_analysis or 'error' in deck_analysis:
            return self.generate_generic_story(story_type, length)
        
        # Extract story elements from deck analysis
        story_context = self.extract_story_context(deck_analysis)
        
        # Generate story based on type
        if story_type == 'origin':
            story = self.generate_origin_story(story_context, length)
        elif story_type == 'battle':
            story = self.generate_battle_story(story_context, length)
        elif story_type == 'legend':
            story = self.generate_legend_story(story_context, length)
        else:  # full
            story = self.generate_full_story(story_context, length)
        
        # Save story
        story_file = self.save_story(story, deck_analysis.get('deck_name', 'Unknown'), story_type)
        
        print(f"[OK] Generated {len(story.split())} word story")
        return {
            'story': story,
            'story_file': story_file,
            'word_count': len(story.split()),
            'story_type': story_type,
            'deck_name': deck_analysis.get('deck_name', 'Unknown')
        }
    
    def extract_story_context(self, deck_analysis):
        """Extract story context from deck analysis"""
        context = {
            'deck_name': deck_analysis.get('deck_name', 'The Nameless Deck'),
            'theme_score': deck_analysis.get('overall_theme_score', 50)
        }
        
        # Extract tribal elements
        tribal = deck_analysis.get('tribal_analysis', {})
        if tribal.get('dominant_tribe'):
            tribe = tribal['dominant_tribe']
            context.update({
                'protagonist_type': f"a {tribe.lower()} leader",
                'theme': self.deck_story_mapping.get('tribal', {}).get(tribe, {}).get('theme', 'unity'),
                'conflict': self.deck_story_mapping.get('tribal', {}).get(tribe, {}).get('conflict', 'survival vs extinction')
            })
        
        # Extract color elements
        color = deck_analysis.get('color_analysis', {})
        color_identity = color.get('color_identity', [])
        if color_identity:
            primary_color = color_identity[0]
            color_info = self.deck_story_mapping.get('color', {}).get(primary_color, {})
            context.update({
                'primary_theme': color_info.get('theme', 'mystery'),
                'emotional_tone': color_info.get('emotion', 'determination'),
                'color_identity': color_identity
            })
        
        # Extract playstyle elements
        playstyle = deck_analysis.get('playstyle_analysis', {})
        deck_playstyle = playstyle.get('playstyle', 'Unknown')
        if deck_playstyle != 'Unknown':
            playstyle_info = self.deck_story_mapping.get('playstyle', {}).get(deck_playstyle, {})
            context.update({
                'strategic_approach': playstyle_info.get('approach', 'careful planning'),
                'story_mood': playstyle_info.get('mood', 'adventurous')
            })
        
        # Extract artistic elements
        artistic = deck_analysis.get('artistic_coherence', {})
        dominant_set = artistic.get('dominant_set', 'Unknown')
        if dominant_set != 'Unknown':
            context['setting'] = dominant_set
        
        return context
    
    def generate_full_story(self, context, length):
        """Generate a complete story with beginning, middle, and end"""
        # Story structure based on length
        if length == 'short':
            paragraphs = [
                self.generate_opening(context),
                self.generate_conflict(context),
                self.generate_resolution(context)
            ]
        elif length == 'long':
            paragraphs = [
                self.generate_opening(context),
                self.generate_character_development(context),
                self.generate_rising_action(context),
                self.generate_climax(context),
                self.generate_resolution(context),
                self.generate_epilogue(context)
            ]
        else:  # medium
            paragraphs = [
                self.generate_opening(context),
                self.generate_rising_action(context),
                self.generate_climax(context),
                self.generate_resolution(context)
            ]
        
        return '\\n\\n'.join(paragraphs)
    
    def generate_opening(self, context):
        """Generate story opening"""
        deck_name = context.get('deck_name', 'The Nameless Deck')
        setting = context.get('setting', random.choice(self.story_elements['settings']))
        protagonist = context.get('protagonist_type', random.choice(self.story_elements['protagonists']))
        
        openings = [
            f"In the mystical realm of {setting}, legends spoke of {deck_name} - a force that would reshape destiny itself. {protagonist.title()} stood at the threshold of this legend, unaware that their fate was already intertwined with powers beyond imagination.",
            
            f"The chronicles of {setting} tell of many heroes, but none quite like the tale of {deck_name}. When {protagonist} first discovered their calling, the very essence of {setting} began to shift, as if the plane itself recognized a new chapter was beginning.",
            
            f"Long had the scholars of {setting} debated the prophecies surrounding {deck_name}. Some called it myth, others feared it as inevitable doom. But {protagonist} knew the truth - for they could feel its power stirring within their very soul."
        ]
        
        return random.choice(openings)
    
    def generate_conflict(self, context):
        """Generate main conflict"""
        antagonist = random.choice(self.story_elements['antagonists'])
        threat = random.choice(self.story_elements['threats'])
        setting = context.get('setting', random.choice(self.story_elements['settings']))
        
        conflicts = [
            f"But peace was not to last. {antagonist.title()} emerged from the shadows, wielding {threat} that threatened to consume all of {setting}. The very foundations of reality began to crack under this malevolent force.",
            
            f"The harmony was shattered when {antagonist} unleashed {threat} upon the unsuspecting inhabitants of {setting}. What had once been a realm of wonder now trembled before an evil that defied comprehension.",
            
            f"It was then that {antagonist} revealed their true nature, bringing forth {threat} that had been festering in the dark corners of {setting}. The time of reckoning had arrived."
        ]
        
        return random.choice(conflicts)
    
    def generate_resolution(self, context):
        """Generate story resolution"""
        emotional_tone = context.get('emotional_tone', 'determination')
        strategic_approach = context.get('strategic_approach', 'careful planning')
        deck_name = context.get('deck_name', 'The Nameless Deck')
        
        resolutions = [
            f"Through {strategic_approach} and unwavering {emotional_tone}, the heroes channeled the true power of {deck_name}. In a final, decisive moment, light triumphed over darkness, and peace was restored to the realm.",
            
            f"The power of {deck_name} proved stronger than any evil that dared challenge it. With {emotional_tone} burning bright in their hearts and guided by {strategic_approach}, the forces of good prevailed against all odds.",
            
            f"In the end, it was not just strength that won the day, but the unity embodied by {deck_name}. Through {strategic_approach} and the pure force of {emotional_tone}, a new age of prosperity began."
        ]
        
        return random.choice(resolutions)
    
    def generate_character_development(self, context):
        """Generate character development section"""
        protagonist = context.get('protagonist_type', 'a brave hero')
        primary_theme = context.get('primary_theme', 'courage')
        
        developments = [
            f"As {protagonist} journeyed deeper into their destiny, they began to understand the true meaning of {primary_theme}. Each challenge faced was not just a test of strength, but a lesson in wisdom that would prove crucial in the battles to come.",
            
            f"The trials ahead would test not just {protagonist}'s abilities, but their very character. For the path of {primary_theme} is not one walked lightly, and the burdens it carries can either forge a hero or break them entirely."
        ]
        
        return random.choice(developments)
    
    def generate_rising_action(self, context):
        """Generate rising action"""
        story_mood = context.get('story_mood', 'tense')
        theme = context.get('theme', 'good vs evil')
        
        actions = [
            f"The conflict escalated as the true scope of the threat became clear. In this {story_mood} struggle between {theme}, every decision carried weight that could tip the balance of fate itself.",
            
            f"Events spiraled toward an inevitable confrontation. The {story_mood} atmosphere grew thick with anticipation as the eternal battle of {theme} reached its crescendo."
        ]
        
        return random.choice(actions)
    
    def generate_climax(self, context):
        """Generate story climax"""
        deck_name = context.get('deck_name', 'The Nameless Deck')
        theme_score = context.get('theme_score', 50)
        
        if theme_score >= 80:
            intensity = "earth-shattering"
        elif theme_score >= 60:
            intensity = "dramatic"
        else:
            intensity = "decisive"
        
        climaxes = [
            f"In the {intensity} final battle, the true power of {deck_name} was finally unleashed. Reality itself seemed to hold its breath as forces beyond mortal comprehension clashed in a conflict that would be remembered for all time.",
            
            f"The {intensity} confrontation reached its peak when {deck_name} revealed its ultimate potential. In that moment, the fate of countless souls hung in the balance."
        ]
        
        return random.choice(climaxes)
    
    def generate_epilogue(self, context):
        """Generate story epilogue"""
        setting = context.get('setting', 'the realm')
        deck_name = context.get('deck_name', 'The Nameless Deck')
        
        epilogues = [
            f"Years later, bards would sing of {deck_name} and the heroes who wielded its power. {setting.title()} flourished once more, but those who lived through those dark times never forgot the price of peace.",
            
            f"The legend of {deck_name} became etched into the very fabric of {setting}'s history. Future generations would look back on this time as the moment when everything changed forever."
        ]
        
        return random.choice(epilogues)
    
    def generate_origin_story(self, context, length):
        """Generate an origin story for the deck"""
        deck_name = context.get('deck_name', 'The Nameless Power')
        setting = context.get('setting', random.choice(self.story_elements['settings']))
        artifact = random.choice(self.story_elements['artifacts'])
        
        if length == 'short':
            return f"The legend of {deck_name} began when an ancient {artifact} was discovered in the deepest vaults of {setting}. This artifact held within it the power to unite disparate forces into a singular, unstoppable force."
        else:
            return f"Long before the great wars that would shape {setting}, there existed {artifact} of immense power. This relic, forged in the earliest days of creation, lay dormant until fate decreed that it would become the foundation of what history would remember as {deck_name}. The discovery of this artifact marked the beginning of an age where the impossible became inevitable, and legends were born from the courage of those willing to wield powers beyond their understanding."
    
    def generate_battle_story(self, context, length):
        """Generate a battle-focused story"""
        deck_name = context.get('deck_name', 'The War Engine')
        strategic_approach = context.get('strategic_approach', 'overwhelming force')
        
        if length == 'short':
            return f"The Battle of {deck_name} became legendary for its display of {strategic_approach}. When the dust settled, none could deny the supremacy of those who had mastered such devastating power."
        else:
            return f"In the annals of warfare, few conflicts match the intensity of the Battle of {deck_name}. The opposing forces had never faced such {strategic_approach} before, and the very landscape bore the scars of their encounter for generations to come. It was a battle that redefined the very nature of conflict itself, where strategy and raw power merged into something that transcended mere victory and entered the realm of legend. Those who survived spoke of it with awe and terror in equal measure."
    
    def generate_legend_story(self, context, length):
        """Generate a legendary tale"""
        deck_name = context.get('deck_name', 'The Eternal Legend')
        primary_theme = context.get('primary_theme', 'heroism')
        
        if length == 'short':
            return f"The Legend of {deck_name} speaks of {primary_theme} that transcended mortal limitations. Even now, its influence can be felt by those brave enough to seek its power."
        else:
            return f"In the great tapestry of myth and legend that spans all planes of existence, few tales shine as brightly as that of {deck_name}. This is a story of {primary_theme} that refused to bow before impossible odds, of power that chose its wielders as much as it was chosen by them. The legend tells us that even in our darkest hours, there exists a force that can overcome any adversity - but only for those who truly understand the responsibility that comes with such power. It is said that on quiet nights, when the moons align just so, you can still hear the echoes of this legend whispering across the planes."
    
    def generate_generic_story(self, story_type, length):
        """Generate a generic story when analysis is unavailable"""
        generic_templates = {
            'origin': "In a time forgotten by history, a power arose that would change everything...",
            'battle': "The greatest battle ever fought was not won by sword or spell, but by unity...",
            'legend': "Legends say that in times of greatest need, heroes emerge to save the day...",
            'full': "Once upon a time, in a land far from here, magic still ruled supreme..."
        }
        
        base_story = generic_templates.get(story_type, generic_templates['full'])
        
        if length == 'short':
            return base_story
        else:
            return base_story + " This is the tale of courage, sacrifice, and the eternal struggle between light and darkness that defines us all."
    
    def save_story(self, story, deck_name, story_type):
        """Save generated story to file"""
        # Clean filename
        clean_name = re.sub(r'[^\w\s-]', '', deck_name).strip()
        clean_name = re.sub(r'[-\s]+', '_', clean_name)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"story_{story_type}_{clean_name}_{timestamp}.txt"
        filepath = self.stories_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {story_type.title()} Story: {deck_name}\\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
            f.write(story)
            f.write(f"\\n\\n# End of Story\\n")
            f.write(f"# Word Count: {len(story.split())} words\\n")
        
        return str(filepath)
    
    def generate_format_lore(self, format_name, format_description, themes):
        """Generate lore for a custom format"""
        print(f"📚 Generating lore for format: {format_name}")
        
        # Build context from format information
        context = {
            'format_name': format_name,
            'format_description': format_description,
            'themes': themes if isinstance(themes, list) else [themes]
        }
        
        # Generate comprehensive lore
        lore_sections = {
            'overview': self.generate_format_overview(context),
            'history': self.generate_format_history(context),
            'key_figures': self.generate_key_figures(context),
            'locations': self.generate_locations(context),
            'conflicts': self.generate_format_conflicts(context)
        }
        
        # Combine into full lore document
        full_lore = self.compile_format_lore(lore_sections, context)
        
        # Save lore
        lore_file = self.save_format_lore(full_lore, format_name)
        
        return {
            'lore': full_lore,
            'sections': lore_sections,
            'lore_file': lore_file,
            'word_count': len(full_lore.split())
        }
    
    def generate_format_overview(self, context):
        """Generate format overview"""
        format_name = context['format_name']
        description = context['format_description']
        themes = context['themes']
        
        return f"The {format_name} format represents {description}. Central to this format are the themes of {', '.join(themes)}, which shape not only the gameplay but the very essence of the stories told within its boundaries."
    
    def generate_format_history(self, context):
        """Generate format history"""
        format_name = context['format_name']
        
        return f"The origins of {format_name} can be traced back to ancient times when planeswalkers first discovered the unique magical resonances that would come to define this format. Over the centuries, it has evolved from a simple practice into a complex art form that draws practitioners from across the multiverse."
    
    def generate_key_figures(self, context):
        """Generate key figures for format lore"""
        return "Among the most notable figures in this format's history are the Archmaster of the First Order, the Shadowweaver of the Eastern Reaches, and the Timekeeper who watches over the eternal conflicts."
    
    def generate_locations(self, context):
        """Generate important locations"""
        format_name = context['format_name']
        
        return f"The primary battlegrounds of {format_name} include the Crystal Sanctuaries where magic flows freely, the Contested Borderlands where alliances are forged and broken, and the Nexus Points where multiple planes converge."
    
    def generate_format_conflicts(self, context):
        """Generate ongoing conflicts in the format"""
        themes = context['themes']
        
        conflict_themes = ', '.join(themes)
        return f"The eternal struggles within this format center around {conflict_themes}, creating a dynamic environment where no victory is ever permanent and every defeat carries the seeds of future triumph."
    
    def compile_format_lore(self, sections, context):
        """Compile all lore sections into full document"""
        format_name = context['format_name']
        
        full_lore = f"# The Complete Lore of {format_name}\\n\\n"
        full_lore += f"## Overview\\n{sections['overview']}\\n\\n"
        full_lore += f"## Historical Background\\n{sections['history']}\\n\\n"
        full_lore += f"## Key Figures\\n{sections['key_figures']}\\n\\n"
        full_lore += f"## Important Locations\\n{sections['locations']}\\n\\n"
        full_lore += f"## Ongoing Conflicts\\n{sections['conflicts']}\\n\\n"
        
        return full_lore
    
    def save_format_lore(self, lore, format_name):
        """Save format lore to file"""
        clean_name = re.sub(r'[^\\w\\s-]', '', format_name).strip()
        clean_name = re.sub(r'[-\\s]+', '_', clean_name)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"format_lore_{clean_name}_{timestamp}.md"
        filepath = self.stories_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(lore)
            f.write(f"\\n\\n---\\n")
            f.write(f"*Generated by MTTGG Story Generator on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\\n")
        
        return str(filepath)


# Helper function for easy access
def get_card_generator():
    """Get initialized card generator"""
    return CustomCardGenerator()


def get_theme_analyzer():
    """Get initialized theme analyzer"""
    return DeckThemeAnalyzer()


def get_deck_namer():
    """Get initialized deck namer"""
    return AutomatedDeckNamer()


def get_story_generator():
    """Get initialized story generator"""
    return StoryGenerator()


# Comprehensive testing functions
def test_ai_content_creation():
    """Test all AI content creation features"""
    print("🧪 TESTING AI CONTENT CREATION SYSTEM")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Custom Card Generation
    print("\\n🎨 TEST 1: Custom Card Generation")
    try:
        generator = get_card_generator()
        card = generator.generate_custom_card(theme="fire", card_type="Creature")
        
        results['card_generation'] = {
            'status': 'PASSED',
            'card_name': card['card_data']['name'],
            'card_type': card['card_data']['type'],
            'image_created': card['image_path'] is not None
        }
        
        print(f"[OK] Generated card: {card['card_data']['name']}")
        print(f"   Type: {card['card_data']['type']}")
        print(f"   Mana Cost: {card['card_data']['mana_cost']}")
        
    except Exception as e:
        results['card_generation'] = {'status': 'ERROR', 'error': str(e)}
        print(f"[ERROR] Card generation error: {e}")
    
    # Test 2: Deck Theme Analysis
    print("\\n📊 TEST 2: Deck Theme Analysis")
    try:
        analyzer = get_theme_analyzer()
        
        # Sample deck list for testing
        sample_deck = """
        4 Lightning Bolt
        4 Goblin Guide
        4 Monastery Swiftspear
        4 Lava Spike
        4 Rift Bolt
        4 Mountain
        """
        
        analysis = analyzer.analyze_deck_theme(sample_deck, "Test Burn Deck")
        
        results['theme_analysis'] = {
            'status': 'PASSED',
            'theme_score': analysis['overall_theme_score'],
            'playstyle': analysis['playstyle_analysis']['playstyle'],
            'color_focus': analysis['color_analysis']['color_focus']
        }
        
        print(f"[OK] Analyzed deck theme")
        print(f"   Theme Score: {analysis['overall_theme_score']:.1f}/100")
        print(f"   Playstyle: {analysis['playstyle_analysis']['playstyle']}")
        
    except Exception as e:
        results['theme_analysis'] = {'status': 'ERROR', 'error': str(e)}
        print(f"[ERROR] Theme analysis error: {e}")
    
    # Test 3: Automated Deck Naming
    print("\\n🏷️ TEST 3: Automated Deck Naming")
    try:
        namer = get_deck_namer()
        
        # Use analysis from previous test if available
        deck_analysis = results.get('theme_analysis', {}).get('analysis', {})
        
        deck_name = namer.generate_deck_name(deck_analysis, style='auto', creativity_level='medium')
        
        results['deck_naming'] = {
            'status': 'PASSED',
            'generated_name': deck_name
        }
        
        print(f"[OK] Generated deck name: {deck_name}")
        
    except Exception as e:
        results['deck_naming'] = {'status': 'ERROR', 'error': str(e)}
        print(f"[ERROR] Deck naming error: {e}")
    
    # Test 4: Story Generation
    print("\\n📚 TEST 4: Story Generation")
    try:
        story_gen = get_story_generator()
        
        # Generate a short story
        story_result = story_gen.generate_deck_story({
            'deck_name': 'Fire Elemental Legion',
            'tribal_analysis': {'dominant_tribe': 'Elemental'},
            'color_analysis': {'color_identity': ['R']},
            'playstyle_analysis': {'playstyle': 'Aggro'},
            'overall_theme_score': 85
        }, story_type='origin', length='short')
        
        results['story_generation'] = {
            'status': 'PASSED',
            'word_count': story_result['word_count'],
            'story_file': story_result['story_file']
        }
        
        print(f"[OK] Generated story")
        print(f"   Word Count: {story_result['word_count']}")
        print(f"   Saved to: {story_result['story_file']}")
        
    except Exception as e:
        results['story_generation'] = {'status': 'ERROR', 'error': str(e)}
        print(f"[ERROR] Story generation error: {e}")
    
    # Overall Results
    print("\\n" + "=" * 60)
    print("📊 OVERALL TEST RESULTS")
    print("=" * 60)
    
    passed_tests = sum(1 for test in results.values() 
                      if test.get('status') == 'PASSED')
    total_tests = len(results)
    
    print(f"[OK] Tests Passed: {passed_tests}/{total_tests}")
    print(f"📈 Success Rate: {passed_tests/total_tests*100:.1f}%")
    
    # Detailed results
    for test_name, result in results.items():
        status = result.get('status', 'UNKNOWN')
        emoji = "[OK]" if status == "PASSED" else "[ERROR]" if status == "ERROR" else "[WARN]"
        print(f"{emoji} {test_name.upper()}: {status}")
    
    if passed_tests == total_tests:
        print("\\n🎉 ALL AI CONTENT CREATION FEATURES WORKING!")
        print("🎨 Ready for creative Magic: The Gathering content!")
        return True
    else:
        print(f"\\n[WARN] {total_tests - passed_tests} features need attention")
        return False


def demo_ai_content_creation():
    """Demonstration of AI content creation capabilities"""
    print("🎨 AI CONTENT CREATION DEMONSTRATION")
    print("=" * 50)
    
    # Demo 1: Generate a themed card set
    print("\\n🎨 DEMO 1: Generating Fire Elemental Card Set")
    generator = get_card_generator()
    fire_set = generator.generate_card_set(theme="fire", count=3, power_levels=['medium', 'high'])
    
    for i, card in enumerate(fire_set, 1):
        card_data = card['card_data']
        print(f"  {i}. {card_data['name']} ({card_data['type']})")
        print(f"     Mana: {card_data['mana_cost']}, Text: {card_data['text'][:50]}...")
    
    # Demo 2: Analyze a competitive deck
    print("\\n📊 DEMO 2: Analyzing Competitive Deck Theme")
    analyzer = get_theme_analyzer()
    
    competitive_deck = """
    4 Aether Vial
    4 Champion of the Parish
    4 Thalia's Lieutenant
    4 Thalia, Guardian of Thraben
    4 Militia Bugler
    4 Kitesail Freebooter
    4 Mantis Rider
    3 Reflector Mage
    4 Plains
    4 Flooded Strand
    """
    
    analysis = analyzer.analyze_deck_theme(competitive_deck, "Human Tribal Deck")
    
    print(f"  Theme Score: {analysis['overall_theme_score']:.1f}/100")
    print(f"  Dominant Tribe: {analysis['tribal_analysis']['dominant_tribe']}")
    print(f"  Color Focus: {analysis['color_analysis']['color_focus']}")
    print(f"  Playstyle: {analysis['playstyle_analysis']['playstyle']}")
    
    # Demo 3: Generate multiple deck names
    print("\\n🏷️ DEMO 3: Generating Multiple Deck Names")
    namer = get_deck_namer()
    
    names = namer.generate_multiple_names(analysis, count=5)
    for i, name_info in enumerate(names, 1):
        print(f"  {i}. {name_info['name']} ({name_info['style']} style)")
    
    # Demo 4: Create format lore
    print("\\n📚 DEMO 4: Generating Custom Format Lore")
    story_gen = get_story_generator()
    
    format_lore = story_gen.generate_format_lore(
        "Elemental Wars", 
        "a format focused on elemental creature combat",
        ["fire", "water", "earth", "air"]
    )
    
    print(f"  Generated {format_lore['word_count']} words of lore")
    print(f"  Saved to: {format_lore['lore_file']}")
    print(f"  Sample: {format_lore['lore'][:100]}...")
    
    print("\\n✨ AI Content Creation Demo Complete!")


def create_ai_content_suite():
    """Create a complete AI content creation suite"""
    print("🚀 CREATING AI CONTENT CREATION SUITE")
    print("=" * 50)
    
    # Initialize all components
    suite = {
        'card_generator': get_card_generator(),
        'theme_analyzer': get_theme_analyzer(),
        'deck_namer': get_deck_namer(),
        'story_generator': get_story_generator()
    }
    
    # Create integration functions
    def generate_complete_deck_package(theme, card_count=10):
        """Generate a complete deck package with cards, analysis, name, and story"""
        print(f"📦 Creating complete package for theme: {theme}")
        
        # Generate card set
        cards = suite['card_generator'].generate_card_set(theme, card_count)
        
        # Create deck list for analysis
        deck_list = "\\n".join([
            f"{card['card_data']['quantity'] if 'quantity' in card['card_data'] else 1} {card['card_data']['name']}"
            for card in cards
        ])
        
        # Analyze theme
        analysis = suite['theme_analyzer'].analyze_deck_theme(deck_list, f"{theme.title()} Custom Deck")
        
        # Generate name
        deck_name = suite['deck_namer'].generate_deck_name(analysis, creativity_level='high')
        
        # Generate story
        story = suite['story_generator'].generate_deck_story(analysis, story_type='full', length='medium')
        
        return {
            'theme': theme,
            'cards': cards,
            'analysis': analysis,
            'deck_name': deck_name,
            'story': story,
            'package_created': datetime.now().isoformat()
        }
    
    # Add integration function to suite
    suite['generate_complete_package'] = generate_complete_deck_package
    
    print("[OK] AI Content Creation Suite Ready")
    print("🎯 Available Functions:")
    print("   - Custom card generation")
    print("   - Deck theme analysis")  
    print("   - Automated deck naming")
    print("   - Story generation")
    print("   - Complete deck packages")
    
    return suite


# Main testing and demo
if __name__ == "__main__":
    # Run comprehensive tests
    test_success = test_ai_content_creation()
    
    if test_success:
        print("\\n" + "="*60)
        print("🎨 RUNNING AI CONTENT CREATION DEMO")
        print("="*60)
        demo_ai_content_creation()
        
        print("\\n" + "="*60)
        print("🚀 CREATING COMPLETE AI SUITE")
        print("="*60)
        suite = create_ai_content_suite()
        
        print("\\n🎉 AI CONTENT CREATION SYSTEM FULLY OPERATIONAL!")
    else:
        print("\\n[WARN] Some features need attention before full deployment")