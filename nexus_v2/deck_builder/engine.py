#!/usr/bin/env python3
"""
NEXUS Deck Builder Engine
=========================
Core deck building logic with format support and budget constraints.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict


class Format(Enum):
    """Supported deck formats"""
    STANDARD = auto()
    MODERN = auto()
    LEGACY = auto()
    VINTAGE = auto()
    COMMANDER = auto()
    PIONEER = auto()
    PAUPER = auto()
    BRAWL = auto()


class Strategy(Enum):
    """Deck building strategies"""
    AGGRO = auto()
    CONTROL = auto()
    MIDRANGE = auto()
    COMBO = auto()
    TEMPO = auto()
    RAMP = auto()


@dataclass
class Card:
    """Represents a Magic card for deck building"""
    name: str
    mana_cost: str = ""
    cmc: float = 0.0
    colors: List[str] = field(default_factory=list)
    type_line: str = ""
    price_usd: float = 0.0

    @property
    def is_creature(self) -> bool:
        return 'Creature' in self.type_line

    @property
    def is_land(self) -> bool:
        return 'Land' in self.type_line

    @property
    def is_instant_sorcery(self) -> bool:
        return 'Instant' in self.type_line or 'Sorcery' in self.type_line


@dataclass
class Deck:
    """Represents a constructed deck"""
    name: str = "New Deck"
    format: Format = Format.STANDARD
    mainboard: Dict[str, int] = field(default_factory=dict)
    sideboard: Dict[str, int] = field(default_factory=dict)
    commander: Optional[str] = None

    @property
    def card_count(self) -> int:
        return sum(self.mainboard.values())

    @property
    def sideboard_count(self) -> int:
        return sum(self.sideboard.values())


@dataclass
class DeckConstraints:
    """Constraints for deck building"""
    format: Format = Format.STANDARD
    strategy: Strategy = Strategy.MIDRANGE
    max_budget: float = 100.0
    colors: List[str] = field(default_factory=list)
    min_lands: int = 20
    max_lands: int = 28


class DeckBuilder:
    """
    Core deck building logic.
    Generates decks based on format, strategy, and budget constraints.
    """

    def __init__(self, scryfall_db=None):
        """Initialize deck builder with optional Scryfall database"""
        self.scryfall_db = scryfall_db
        self.card_pool: List[Card] = []

    def set_card_pool(self, cards: List[Card]) -> None:
        """Set available cards for deck building"""
        self.card_pool = cards

    def build_deck(self, constraints: DeckConstraints) -> Deck:
        """
        Build a deck based on constraints.

        Args:
            constraints: DeckConstraints object with format, strategy, budget

        Returns:
            Deck object with mainboard and sideboard
        """
        deck = Deck(format=constraints.format)

        # Filter cards by color identity
        available = self._filter_by_colors(self.card_pool, constraints.colors)

        # Select lands
        lands = self._select_lands(constraints, available)
        for land, count in lands.items():
            deck.mainboard[land] = count

        # Calculate remaining slots and budget
        remaining_slots = 60 - deck.card_count
        if constraints.format == Format.COMMANDER:
            remaining_slots = 99 - deck.card_count  # Commander takes 1 slot

        land_cost = sum(
            self._get_card_price(name) * count
            for name, count in lands.items()
        )

        # Select strategy cards
        strategy_cards = self._select_strategy_cards(
            constraints, available, remaining_slots, land_cost
        )
        for card, count in strategy_cards.items():
            deck.mainboard[card] = count

        return deck

    def _filter_by_colors(self, cards: List[Card], colors: List[str]) -> List[Card]:
        """Filter cards by color identity"""
        if not colors:
            return cards
        return [c for c in cards if any(col in c.colors for col in colors) or not c.colors]

    def _select_lands(self, constraints: DeckConstraints,
                      available: List[Card]) -> Dict[str, int]:
        """Select lands for the deck"""
        lands = {}
        target = (constraints.min_lands + constraints.max_lands) // 2

        # Add basic lands based on colors
        basics = {'W': 'Plains', 'U': 'Island', 'B': 'Swamp',
                  'R': 'Mountain', 'G': 'Forest'}

        if constraints.colors:
            per_color = target // len(constraints.colors)
            for color in constraints.colors:
                if color in basics:
                    lands[basics[color]] = per_color
        else:
            # Default to balanced basics
            for basic in basics.values():
                lands[basic] = target // 5

        return lands

    def _get_card_price(self, card_name: str) -> float:
        """Get price for a card"""
        for card in self.card_pool:
            if card.name == card_name:
                return card.price_usd
        return 0.0

    def _select_strategy_cards(self, constraints: DeckConstraints,
                               available_cards: List[Card],
                               slots: int, current_cost: float) -> Dict[str, int]:
        """Select cards based on strategy"""
        selected = {}
        remaining_budget = constraints.max_budget - current_cost

        # Strategy-based card distribution
        strategy_ratios = {
            Strategy.AGGRO: {'creature': 0.6, 'spell': 0.3, 'other': 0.1},
            Strategy.CONTROL: {'creature': 0.2, 'spell': 0.6, 'other': 0.2},
            Strategy.MIDRANGE: {'creature': 0.45, 'spell': 0.35, 'other': 0.2},
            Strategy.COMBO: {'creature': 0.25, 'spell': 0.5, 'other': 0.25},
            Strategy.TEMPO: {'creature': 0.5, 'spell': 0.4, 'other': 0.1},
            Strategy.RAMP: {'creature': 0.3, 'spell': 0.3, 'other': 0.4}
        }

        ratios = strategy_ratios.get(constraints.strategy,
                                     {'creature': 0.4, 'spell': 0.4, 'other': 0.2})

        # Sort cards by CMC (for curve)
        sorted_cards = sorted(available_cards, key=lambda c: c.cmc)

        # Select creatures
        creature_slots = int(slots * ratios['creature'])
        creatures = [c for c in sorted_cards if c.is_creature]
        for card in creatures[:creature_slots // 4]:  # 4 copies each
            if card.price_usd * 4 <= remaining_budget:
                selected[card.name] = 4
                remaining_budget -= card.price_usd * 4

        # Select spells
        spell_slots = int(slots * ratios['spell'])
        spells = [c for c in sorted_cards if c.is_instant_sorcery]
        for card in spells[:spell_slots // 4]:
            if card.price_usd * 4 <= remaining_budget:
                selected[card.name] = 4
                remaining_budget -= card.price_usd * 4

        return selected

    def _calculate_mana_curve(self, deck: Deck,
                              available_cards: List[Card]) -> Dict[int, int]:
        """Calculate mana curve distribution"""
        curve = defaultdict(int)

        for card_name, count in deck.mainboard.items():
            card = self._find_card(card_name, available_cards)
            if card and not card.is_land:
                cmc = int(card.cmc)
                curve[cmc] += count

        return dict(curve)

    def _find_card(self, card_name: str,
                   card_list: List[Card]) -> Optional[Card]:
        """Find card by name in list"""
        for card in card_list:
            if card.name.lower() == card_name.lower():
                return card
        return None

    def validate_deck(self, deck: Deck) -> Tuple[bool, List[str]]:
        """
        Validate deck legality and construction

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check card count
        if deck.card_count < 60 and deck.format != Format.COMMANDER:
            errors.append(f"Deck has {deck.card_count} cards, needs 60+")

        if deck.format == Format.COMMANDER and deck.card_count != 100:
            errors.append(f"Commander deck must have exactly 100 cards")

        # Check 4-copy limit (except basic lands)
        for card_name, count in deck.mainboard.items():
            if count > 4 and not self._is_basic_land(card_name):
                errors.append(f"{card_name} has {count} copies (max 4)")

        return len(errors) == 0, errors

    def _is_basic_land(self, card_name: str) -> bool:
        """Check if card is a basic land"""
        basics = {'Plains', 'Island', 'Swamp', 'Mountain', 'Forest', 'Wastes'}
        return card_name in basics


# ============================================
# DECK BUILDER ENGINE - UI INTERFACE LAYER
# ============================================

class DeckBuilderEngine:
    """
    High-level deck builder interface for UI integration.
    Wraps DeckBuilder with convenient methods.
    """

    def __init__(self, scryfall_db=None):
        """Initialize deck builder engine"""
        self.builder = DeckBuilder(scryfall_db)
        self.current_deck: Optional[Deck] = None

    def generate_deck(self, format_name: str = "Standard",
                      strategy: str = "Midrange",
                      budget: float = 30.0,
                      colors: List[str] = None,
                      card_pool: List = None) -> Optional[Dict]:
        """
        Generate a new deck based on parameters.

        Args:
            format_name: Format string (Standard, Modern, etc)
            strategy: Strategy string (Aggro, Control, etc)
            budget: Max budget in USD
            colors: List of color codes (W, U, B, R, G)
            card_pool: Optional list of Card objects to build from

        Returns:
            Dict with mainboard, sideboard, etc or None
        """
        try:
            # Map string to enums
            format_enum = Format[format_name.upper()] if format_name.upper() in Format.__members__ else Format.STANDARD
            strategy_enum = Strategy[strategy.upper()] if strategy.upper() in Strategy.__members__ else Strategy.MIDRANGE

            # Create constraints
            constraints = DeckConstraints(
                format=format_enum,
                strategy=strategy_enum,
                max_budget=budget,
                colors=colors or []
            )

            # Set card pool if provided
            if card_pool:
                cards = []
                for c in card_pool:
                    if isinstance(c, Card):
                        cards.append(c)
                    elif hasattr(c, 'name'):
                        cards.append(Card(
                            name=c.name,
                            mana_cost=getattr(c, 'mana_cost', ''),
                            cmc=getattr(c, 'cmc', 0),
                            colors=getattr(c, 'colors', []),
                            type_line=getattr(c, 'type_line', ''),
                            price_usd=getattr(c, 'price_usd', 0.0)
                        ))
                self.builder.set_card_pool(cards)

            # Build deck
            self.current_deck = self.builder.build_deck(constraints)

            return {
                'mainboard': dict(self.current_deck.mainboard),
                'sideboard': dict(self.current_deck.sideboard),
                'card_count': self.current_deck.card_count,
                'format': format_name
            }

        except Exception as e:
            print(f"Error generating deck: {e}")
            return None

    def validate_current_deck(self) -> Tuple[bool, List[str]]:
        """Validate the current deck"""
        if not self.current_deck:
            return False, ["No deck loaded"]
        return self.builder.validate_deck(self.current_deck)

    def get_mana_curve(self) -> Dict[int, int]:
        """Get mana curve of current deck"""
        if not self.current_deck:
            return {}
        return self.builder._calculate_mana_curve(
            self.current_deck, self.builder.card_pool
        )


if __name__ == "__main__":
    # Quick test
    engine = DeckBuilderEngine()
    print("Deck Builder Engine initialized")
    print(f"Supported formats: {[f.name for f in Format]}")
    print(f"Supported strategies: {[s.name for s in Strategy]}")
