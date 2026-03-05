"""
Einstein Integration - Claude AI for Deck Building
Uses Anthropic API to generate optimized deck lists
"""

import os
import json
import requests
from typing import Dict, List, Optional


def build_deck_with_einstein(
    format: str,
    strategy: str,
    colors: List[str],
    commander: Optional[str] = None,
    budget: float = 50.0,
    api_key: Optional[str] = None,
    inventory: Optional[List[Dict]] = None
) -> Dict:
    """
    Build a deck using Claude AI.

    Args:
        format: 'Standard', 'Modern', 'Commander', etc.
        strategy: 'aggro', 'control', 'combo', 'midrange'
        colors: List of colors ['W', 'U', 'B', 'R', 'G']
        commander: Commander card name (for EDH)
        budget: Maximum budget in USD
        api_key: Anthropic API key
        inventory: User's card collection with cataloged_date for age

    Returns:
        Dict with 'success', 'deck_list', 'explanation', 'total_price'
    """

    # Get API key from param, env, or config
    if not api_key:
        api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        # Try config file
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'nexus_client_config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('anthropic_api_key')
        except:
            pass

    if not api_key or api_key == "YOUR_KEY_HERE":
        return {
            'success': False,
            'error': 'No Anthropic API key. Set ANTHROPIC_API_KEY env var or add to nexus_client_config.json',
            'deck_list': []
        }

    # MTG Rules Reference for AI
    RULES_CONTEXT = """
MAGIC: THE GATHERING - COMMANDER/EDH COMPLETE RULES

═══════════════════════════════════════════════════════════════════
DECK CONSTRUCTION REQUIREMENTS (MANDATORY - NO EXCEPTIONS)
═══════════════════════════════════════════════════════════════════
1. EXACTLY 100 CARDS + 1 COMMANDER = 101 TOTAL
2. SINGLETON: Only 1 copy of each card EXCEPT basic lands
3. COLOR IDENTITY: Every card must match commander's colors
4. ONLY USE REAL, LEGAL MTG CARDS - No made-up cards!
5. BANNED CARDS: Do NOT include any banned Commander cards

BANNED IN COMMANDER (never include these):
- Ancestral Recall, Balance, Biorhythm, Black Lotus
- Channel, Chaos Orb, Coalition Victory, Emrakul the Aeons Torn
- Falling Star, Fastbond, Flash
- Golos Tireless Pilgrim, Griselbrand, Hullbreacher
- Iona Shield of Emeria, Karakas, Leovold Emissary of Trest
- Library of Alexandria, Limited Resources, Lutri the Spellchaser
- Mox Emerald/Jet/Pearl/Ruby/Sapphire, Panoptic Mirror
- Paradox Engine, Primeval Titan, Prophet of Kruphix
- Recurring Nightmare, Rofellos Llanowar Emissary
- Shahrazad, Sundering Titan, Sway of the Stars
- Sylvan Primordial, Time Vault, Time Walk, Tinker
- Tolarian Academy, Trade Secrets, Upheaval, Worldfire

═══════════════════════════════════════════════════════════════════
BASIC LANDS (unlimited copies allowed):
═══════════════════════════════════════════════════════════════════
- Plains (produces W) - White decks
- Island (produces U) - Blue decks  
- Swamp (produces B) - Black decks
- Mountain (produces R) - Red decks
- Forest (produces G) - Green decks
- Wastes (produces colorless) - Any deck

═══════════════════════════════════════════════════════════════════
REQUIRED DECK COMPOSITION (100 cards, commander separate):
═══════════════════════════════════════════════════════════════════
LANDS (36-40 cards):
- 25-30 Basic lands (split by color needs)
- 5-10 Utility lands (Command Tower, Sol lands, fetch lands)

RAMP (10-12 cards) - Mana acceleration:
- Sol Ring (MUST INCLUDE - best card in format)
- Arcane Signet (2-color)
- Signets (Azorius, Dimir, etc based on colors)
- Talismans
- Land ramp: Cultivate, Kodama's Reach, Rampant Growth (green)
- Mana rocks: Mind Stone, Fellwar Stone, Commander's Sphere

CARD DRAW (10-12 cards):
- Rhystic Study, Mystic Remora (blue)
- Phyrexian Arena, Sign in Blood (black)
- Harmonize, Beast Whisperer (green)
- Mentor of the Meek (white)
- Wheel effects if aggressive

REMOVAL (8-10 cards):
- Single target: Swords to Plowshares, Path to Exile, Pongify
- Go for the Throat, Doom Blade, Terminate
- Beast Within, Generous Gift (hits anything)
- Counterspells: Counterspell, Negate, Swan Song

BOARD WIPES (3-5 cards):
- Wrath of God, Day of Judgment, Damnation
- Cyclonic Rift (BEST blue wipe), Blasphemous Act
- Toxic Deluge, Farewell, Vanquish the Horde

PROTECTION (3-5 cards):
- Lightning Greaves, Swiftfoot Boots
- Teferi's Protection, Heroic Intervention
- Counterspells double as protection

WIN CONDITIONS (3-5 cards):
- Combat damage finishers
- Combo pieces
- Alternative wins (Thassa's Oracle, Lab Man)

SYNERGY/THEME (25-35 cards):
- Cards that work with your commander's abilities
- Tribal support if tribal deck
- Theme-specific cards

═══════════════════════════════════════════════════════════════════
COLOR IDENTITY RULES:
═══════════════════════════════════════════════════════════════════
Commander colors determine what you can play:
- Mono-W: Only white cards, colorless, Plains
- Mono-U: Only blue cards, colorless, Islands
- Mono-B: Only black cards, colorless, Swamps
- Mono-R: Only red cards, colorless, Mountains
- Mono-G: Only green cards, colorless, Forests
- WU (Azorius): White + Blue + colorless
- WB (Orzhov): White + Black + colorless
- UB (Dimir): Blue + Black + colorless
- UR (Izzet): Blue + Red + colorless
- BR (Rakdos): Black + Red + colorless
- RG (Gruul): Red + Green + colorless
- GW (Selesnya): Green + White + colorless
- WUB (Esper): White + Blue + Black + colorless
- And so on for 3/4/5 color combinations

Hybrid mana (like W/U) counts as BOTH colors
Phyrexian mana counts as that color
Color indicators count (back faces)

═══════════════════════════════════════════════════════════════════
MANA CURVE TARGETS:
═══════════════════════════════════════════════════════════════════
- 0-1 CMC: 8-12 cards (early interaction, ramp)
- 2 CMC: 12-18 cards (ramp, utility)
- 3 CMC: 15-20 cards (value engines)
- 4 CMC: 10-15 cards (threats)
- 5 CMC: 6-10 cards (bombs)
- 6+ CMC: 4-8 cards (finishers)

Average CMC should be 2.5-3.5 for most decks

═══════════════════════════════════════════════════════════════════
GAMEPLAY RULES (for strategy context):
═══════════════════════════════════════════════════════════════════
- Starting life: 40 (not 20)
- 21 commander damage from SAME commander = death
- Commander goes to command zone when it dies (or graveyard, choose)
- Commander tax: +2 generic mana each recast from command zone
- Multiplayer: Usually 4 players, politics matter
- Turns go clockwise, last player standing wins

CRITICAL OUTPUT REQUIREMENT:
YOU MUST OUTPUT EXACTLY 100 CARDS (sum of all quantities).
Commander is SEPARATE - not included in the 100.
ONLY USE REAL MTG CARD NAMES THAT ACTUALLY EXIST.
DO NOT MAKE UP CARD NAMES.

NEVER INCLUDE THESE (NOT PLAYABLE CARDS):
- Token cards (Soldier Token, Zombie Token, etc.)
- Art cards / Art series cards
- Emblems
- Dungeon cards
- Checklist cards
- Oversized cards
- Substitute cards
- Helper cards (The Monarch, Day/Night, etc.)
- Promotional inserts
- ANY card that says "Token" in its name or type
"""

    # Build the prompt
    color_names = {
        'W': 'White', 'U': 'Blue', 'B': 'Black',
        'R': 'Red', 'G': 'Green'
    }
    color_str = ', '.join([color_names.get(c, c) for c in colors]) if colors else 'colorless'

    import time
    from datetime import datetime, timedelta
    start_time = time.time()
    
    # Process inventory - identify 90+ day old cards and group by name
    inventory_context = ""
    if inventory:
        # Calculate age cutoff (90 days ago)
        cutoff_date = datetime.now() - timedelta(days=90)
        
        old_stock = []  # Cards 90+ days old (priority)
        available_cards = {}  # All cards by name
        
        for card in inventory:
            name = card.get('name', '')
            price = card.get('price', 0) or card.get('price_usd', 0) or 0
            
            # Track all available cards
            if name not in available_cards:
                available_cards[name] = {'count': 0, 'price': price, 'old': False}
            available_cards[name]['count'] += 1
            
            # Check if 90+ days old
            cat_date = card.get('cataloged_date', '')
            if cat_date:
                try:
                    card_date = datetime.fromisoformat(cat_date.replace('Z', '+00:00'))
                    if card_date.replace(tzinfo=None) < cutoff_date:
                        available_cards[name]['old'] = True
                        if name not in [c['name'] for c in old_stock]:
                            old_stock.append({'name': name, 'price': price})
                except:
                    pass
        
        # Build inventory context for prompt
        old_card_names = [c['name'] for c in old_stock[:200]]  # Top 200 old cards
        all_card_names = list(available_cards.keys())  # ALL unique card names
        
        inventory_context = f"""
═══════════════════════════════════════════════════════════════════
INVENTORY CONSTRAINT (MANDATORY - NO EXCEPTIONS)
═══════════════════════════════════════════════════════════════════
YOU CAN ONLY USE CARDS FROM THIS LIST. DO NOT SUGGEST ANY OTHER CARDS.
If a card is not on this list, DO NOT INCLUDE IT.

PRIORITY 1 - 90+ DAY OLD STOCK (USE THESE FIRST):
{', '.join(old_card_names) if old_card_names else 'None identified'}

COMPLETE AVAILABLE INVENTORY (ONLY use cards from this list):
{', '.join(all_card_names)}

STRICT RULES:
1. ONLY use cards from the list above - NO EXCEPTIONS
2. PRIORITIZE 90+ day old stock first
3. If you cannot build a complete deck from this inventory, build the best partial deck possible
4. NEVER suggest cards not in the inventory list
"""
    
    if format == "Commander" and commander:
        prompt = f"""{RULES_CONTEXT}
{inventory_context}

Build a Commander/EDH deck with {commander} as commander.

Strategy: {strategy}
Budget: ${budget:.2f} maximum  
Colors: {color_str}

CRITICAL: You MUST return EXACTLY 100 cards. Count them before responding.

Suggested distribution:
- 38 Lands (basics + utility)
- 10 Ramp (Sol Ring, signets, etc)
- 10 Card Draw
- 8 Removal (single target)
- 4 Board Wipes
- 5 Protection/Counterspells
- 25 Synergy/Theme cards

Return ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "deck_name": "Creative name",
  "deck_list": [
    {{"name": "Sol Ring", "quantity": 1, "category": "ramp", "price": 1.00}},
    {{"name": "Island", "quantity": 10, "category": "land", "price": 0.10}},
    ... (MUST total exactly 99 cards when quantities are summed)
  ],
  "strategy_notes": "2-3 sentences on game plan",
  "mana_analysis": "Land/color breakdown",
  "viability_report": "Strengths and weaknesses",
  "total_price": 45.00
}}

VERIFY: Sum all quantities = 100. This is MANDATORY."""

    else:
        deck_size = 60
        
        # Different rules for 60-card constructed formats
        CONSTRUCTED_RULES = """
MAGIC: THE GATHERING - 60-CARD CONSTRUCTED FORMATS

DECK REQUIREMENTS:
- EXACTLY 60 cards maindeck (15 card sideboard optional)
- Up to 4 copies of any card EXCEPT basic lands (unlimited)
- Only use REAL, LEGAL MTG cards that exist
- NO tokens, art cards, emblems, or helper cards

BASIC LANDS: Plains, Island, Swamp, Mountain, Forest (unlimited copies)

TYPICAL DECK COMPOSITION:
- 20-24 Lands
- 20-28 Creatures (or fewer for control/combo)
- 8-16 Spells (removal, card draw, etc)

FORMAT LEGALITY:
- Standard: Last 2-3 years of sets only
- Modern: 8th Edition (2003) forward
- Pioneer: Return to Ravnica (2012) forward
- Legacy: All cards except banned list
- Pauper: Commons only

NEVER INCLUDE: Tokens, Art cards, Emblems, Dungeons, Oversized cards
"""
        
        prompt = f"""{CONSTRUCTED_RULES}

Build a competitive {format} deck.

Colors: {color_str}
Strategy: {strategy}
Budget: ${budget:.2f} maximum

Format-specific rules:
- Standard: Recent sets only, 60 cards, 4-of limit
- Modern: 8th Edition forward, 60 cards, 4-of limit
- Pioneer: Return to Ravnica forward, 60 cards
- Legacy: All cards, 60 cards, restricted list applies
- Pauper: Commons only

Requirements:
- Exactly {deck_size} cards maindeck
- Up to 4 copies of non-basic cards (4-of rule)
- Include 20-24 lands typically
- Good mana curve (1-2-3-4+ CMC distribution)
- Stay within budget

Return ONLY valid JSON:
{{
  "deck_name": "Creative deck name based on strategy/colors",
  "deck_list": [
    {{"name": "Card Name", "quantity": 4, "category": "creature", "price": 1.50}},
    ...
  ],
  "strategy_notes": "How the deck plays and wins",
  "mana_analysis": "Mana base breakdown and color requirements",
  "viability_report": "Competitive analysis: strengths, weaknesses, matchups",
  "total_price": 45.00
}}

Use real MTG card names only. No markdown."""

    # Call Anthropic API
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 8192,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            },
            timeout=120
        )

        if response.status_code == 401:
            return {
                'success': False,
                'error': 'Invalid API key. Check your Anthropic API key.',
                'deck_list': []
            }

        if response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get('error', {}).get('message', response.text)
            except:
                pass
            return {
                'success': False,
                'error': f'API error {response.status_code}: {error_detail}',
                'deck_list': []
            }

        result = response.json()
        content = result['content'][0]['text']

        # Parse JSON from response
        # Handle potential markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]

        content = content.strip()
        deck_data = json.loads(content)
        
        build_time = time.time() - start_time
        deck_list = deck_data.get('deck_list', [])
        total_cards = sum(card.get('quantity', 1) for card in deck_list)

        return {
            'success': True,
            'deck_list': deck_list,
            'deck_name': deck_data.get('deck_name', f'{strategy.title()} {color_str}'),
            'total_cards': total_cards,
            'total_price': deck_data.get('total_price', 0),
            'build_time': build_time,
            'strategy_notes': deck_data.get('strategy_notes', ''),
            'mana_analysis': deck_data.get('mana_analysis', ''),
            'viability_report': deck_data.get('viability_report', ''),
            'commander': commander
        }

    except json.JSONDecodeError as e:
        return {
            'success': False,
            'error': f'Failed to parse AI response: {e}',
            'deck_list': []
        }
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'API timeout - try again',
            'deck_list': []
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'deck_list': []
        }


def suggest_cards(
    query: str,
    colors: List[str] = None,
    card_type: str = None,
    api_key: str = None
) -> List[Dict]:
    """
    Get card suggestions from AI based on a query.

    Args:
        query: What kind of cards to suggest (e.g., "ramp spells", "board wipes")
        colors: Color restrictions
        card_type: Card type filter
        api_key: Anthropic API key

    Returns:
        List of card suggestions with names and reasons
    """
    if not api_key:
        api_key = os.getenv('ANTHROPIC_API_KEY')

    if not api_key:
        return []

    color_str = ', '.join(colors) if colors else 'any colors'
    type_str = card_type if card_type else 'any type'

    prompt = f"""Suggest 10 MTG cards for: {query}
Colors: {color_str}
Card type preference: {type_str}

Return ONLY a JSON array:
[
  {{"name": "Card Name", "reason": "Why this card fits"}},
  ...
]

No markdown, just JSON array."""

    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 1024,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )

        if response.status_code != 200:
            return []

        content = response.json()['content'][0]['text']
        if '```' in content:
            content = content.split('```')[1].split('```')[0]
            if content.startswith('json'):
                content = content[4:]

        return json.loads(content.strip())

    except Exception:
        return []
