"""
Yu-Gi-Oh! Card Data Structures
Interfaces with YGOProDeck API v7
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class YugiohCard:
    """
    Yu-Gi-Oh! card data structure matching YGOProDeck API v7 response

    Attributes:
        id: YGOProDeck card ID (unique identifier)
        name: Card name
        type: Full card type (e.g., "Normal Monster", "Effect Monster", "Spell Card")
        frameType: Frame classification (normal, effect, xyz, synchro, fusion, link, spell, trap)
        desc: Card text/effect description
        race: Monster type (Spellcaster, Dragon, Warrior, etc.) or Spell/Trap subtype
        attribute: Monster attribute (DARK, LIGHT, EARTH, FIRE, WATER, WIND, DIVINE)
        atk: Attack points (monsters only)
        def_: Defense points (monsters only, using def_ since def is a reserved keyword)
        level: Level/Rank/Link rating (monsters only)
        archetype: Archetype name (e.g., "Dark Magician", "Blue-Eyes")
        card_sets: List of printings with set info and prices
        card_images: List of image URLs (small, normal, cropped)
        card_prices: Market prices from multiple sources
    """

    # Core identity fields
    id: int
    name: str
    type: str
    frameType: str
    desc: str

    # Monster-specific attributes (Optional - only for monsters)
    race: Optional[str] = None
    attribute: Optional[str] = None
    atk: Optional[int] = None
    def_: Optional[int] = None  # def is Python reserved keyword
    level: Optional[int] = None
    scale: Optional[int] = None  # Pendulum scale
    linkval: Optional[int] = None  # Link rating
    linkmarkers: Optional[List[str]] = None  # Link arrows
    archetype: Optional[str] = None

    # Set and pricing information
    card_sets: List[Dict[str, Any]] = field(default_factory=list)
    card_images: List[Dict[str, str]] = field(default_factory=list)
    card_prices: List[Dict[str, str]] = field(default_factory=list)

    # Metadata
    humanReadableCardType: Optional[str] = None
    typeline: Optional[List[str]] = None  # Parsed type components

    def __post_init__(self):
        """Parse additional data after initialization"""
        # Extract prices if available
        if self.card_prices:
            prices = self.card_prices[0]  # Use first price entry
            self.cardmarket_price = self._safe_float(prices.get('cardmarket_price'))
            self.tcgplayer_price = self._safe_float(prices.get('tcgplayer_price'))
            self.ebay_price = self._safe_float(prices.get('ebay_price'))
            self.amazon_price = self._safe_float(prices.get('amazon_price'))
            self.coolstuffinc_price = self._safe_float(prices.get('coolstuffinc_price'))
        else:
            self.cardmarket_price = None
            self.tcgplayer_price = None
            self.ebay_price = None
            self.amazon_price = None
            self.coolstuffinc_price = None

    @staticmethod
    def _safe_float(value: Optional[str]) -> Optional[float]:
        """Convert string price to float, handling None and invalid values"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_best_price(self) -> float:
        """
        Calculate consensus price using Byzantine Fault Tolerance (BFT) algorithm
        Weights favor TCGPlayer for US market, CardMarket for EU

        Returns:
            Weighted average price, or 0.0 if no prices available
        """
        prices = [
            (self.tcgplayer_price, 0.50),      # 50% weight - US market leader
            (self.cardmarket_price, 0.30),     # 30% weight - EU market leader
            (self.coolstuffinc_price, 0.15),   # 15% weight - US retail
            (self.ebay_price, 0.05),           # 5% weight - auction (volatile)
        ]

        weighted_sum = sum(p * w for p, w in prices if p and p > 0)
        total_weight = sum(w for p, w in prices if p and p > 0)

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def get_price_confidence(self) -> str:
        """
        Calculate confidence level for price consensus

        Returns:
            'H' (HIGH), 'M' (MEDIUM), or 'L' (LOW)
        """
        valid_prices = [p for p in [
            self.tcgplayer_price,
            self.cardmarket_price,
            self.coolstuffinc_price,
            self.ebay_price
        ] if p and p > 0]

        if len(valid_prices) >= 3:
            return 'H'  # HIGH - 3+ sources
        elif len(valid_prices) == 2:
            return 'M'  # MEDIUM - 2 sources
        elif len(valid_prices) == 1:
            return 'L'  # LOW - only 1 source
        else:
            return 'L'  # LOW - no prices

    def get_primary_image_url(self, size: str = "normal") -> Optional[str]:
        """
        Get image URL for the card

        Args:
            size: Image size ('small', 'normal', 'cropped')

        Returns:
            Image URL or None if not available
        """
        if not self.card_images:
            return None

        img = self.card_images[0]
        size_map = {
            'small': 'image_url_small',
            'normal': 'image_url',
            'cropped': 'image_url_cropped'
        }

        return img.get(size_map.get(size, 'image_url'))

    def is_monster(self) -> bool:
        """Check if card is a monster"""
        return "Monster" in self.type

    def is_spell(self) -> bool:
        """Check if card is a spell"""
        return "Spell" in self.type

    def is_trap(self) -> bool:
        """Check if card is a trap"""
        return "Trap" in self.type

    def is_extra_deck(self) -> bool:
        """Check if card belongs in Extra Deck"""
        extra_deck_types = ['Fusion', 'Synchro', 'Xyz', 'Link']
        return any(t in self.type for t in extra_deck_types)

    def get_display_stats(self) -> str:
        """
        Get formatted ATK/DEF string for display

        Returns:
            Formatted string like "ATK/2500 DEF/2100" or "?" for special cases
        """
        if not self.is_monster():
            return ""

        atk_str = str(self.atk) if self.atk is not None else "?"
        def_str = str(self.def_) if self.def_ is not None else "?"

        # Link monsters don't have DEF
        if "Link" in self.type:
            return f"ATK/{atk_str}"

        return f"ATK/{atk_str} DEF/{def_str}"

    def get_level_stars(self) -> str:
        """
        Get visual representation of level/rank

        Returns:
            String of star symbols (★) for level
        """
        if self.level:
            return "★" * self.level
        return ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert card to dictionary for storage"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'frameType': self.frameType,
            'desc': self.desc,
            'race': self.race,
            'attribute': self.attribute,
            'atk': self.atk,
            'def': self.def_,
            'level': self.level,
            'scale': self.scale,
            'linkval': self.linkval,
            'linkmarkers': self.linkmarkers,
            'archetype': self.archetype,
            'card_sets': self.card_sets,
            'card_images': self.card_images,
            'card_prices': self.card_prices,
            'best_price': self.get_best_price(),
            'price_confidence': self.get_price_confidence(),
        }

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'YugiohCard':
        """
        Create YugiohCard from YGOProDeck API v7 response

        Args:
            data: JSON response data from API

        Returns:
            YugiohCard instance
        """
        # Handle defense field (API returns 'def', we use 'def_')
        def_value = data.get('def')

        return cls(
            id=data['id'],
            name=data['name'],
            type=data['type'],
            frameType=data.get('frameType', ''),
            desc=data.get('desc', ''),
            race=data.get('race'),
            attribute=data.get('attribute'),
            atk=data.get('atk'),
            def_=def_value,
            level=data.get('level'),
            scale=data.get('scale'),
            linkval=data.get('linkval'),
            linkmarkers=data.get('linkmarkers'),
            archetype=data.get('archetype'),
            card_sets=data.get('card_sets', []),
            card_images=data.get('card_images', []),
            card_prices=data.get('card_prices', []),
            humanReadableCardType=data.get('humanReadableCardType'),
            typeline=data.get('typeline'),
        )


# Constants for Yu-Gi-Oh! card characteristics

YUGIOH_CARD_TYPES = {
    'monster': ['Normal Monster', 'Effect Monster', 'Ritual Monster', 'Fusion Monster',
                'Synchro Monster', 'XYZ Monster', 'Pendulum Effect Monster',
                'Link Monster', 'Ritual Effect Monster', 'Synchro Tuner Monster',
                'Flip Effect Monster', 'Toon Monster', 'Spirit Monster', 'Union Effect Monster'],
    'spell': ['Spell Card'],
    'trap': ['Trap Card']
}

YUGIOH_ATTRIBUTES = [
    'DARK', 'LIGHT', 'EARTH', 'FIRE', 'WATER', 'WIND', 'DIVINE'
]

YUGIOH_MONSTER_RACES = [
    'Spellcaster', 'Dragon', 'Zombie', 'Warrior', 'Beast-Warrior', 'Beast',
    'Fiend', 'Fairy', 'Insect', 'Dinosaur', 'Reptile', 'Fish', 'Sea Serpent',
    'Aqua', 'Pyro', 'Thunder', 'Rock', 'Plant', 'Machine', 'Psychic',
    'Divine-Beast', 'Creator-God', 'Wyrm', 'Cyberse', 'Illusion'
]

YUGIOH_SPELL_TRAP_TYPES = [
    'Normal', 'Continuous', 'Counter', 'Quick-Play', 'Field', 'Equip', 'Ritual'
]

YUGIOH_RARITIES = [
    'Starlight Rare', 'Ghost Rare', 'Prismatic Secret Rare', 'Secret Rare',
    'Ultimate Rare', 'Ultra Rare', 'Super Rare', 'Rare', 'Common',
    'Short Print', 'Mosaic Rare', 'Shatterfoil Rare'
]

# Archetype examples (top competitive archetypes)
POPULAR_ARCHETYPES = [
    'Blue-Eyes', 'Dark Magician', 'Red-Eyes', 'Exodia',
    'Cyber Dragon', 'Hero', 'Burning Abyss', 'Shaddoll',
    'Nekroz', 'Kozmo', 'Kaiju', 'True Draco', 'SPYRAL',
    'Pendulum Magician', 'Trickstar', 'Sky Striker', 'Salamangreat',
    'Orcust', 'Thunder Dragon', 'Danger!', 'Phantom Knights',
    'Virtual World', 'Drytron', 'Tri-Brigade', 'Swordsoul',
    'Tearlaments', 'Kashtira', 'Purrely', 'Snake-Eye'
]
