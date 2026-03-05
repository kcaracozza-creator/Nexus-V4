#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS Pokemon TCG Data Module
Handles Pokemon card data structures and lookups
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PokemonCard:
    """Represents a Pokemon TCG card"""
    name: str
    set_name: str
    set_code: str
    number: str
    rarity: str
    card_type: str  # Pokemon, Trainer, Energy
    hp: Optional[int] = None
    types: Optional[List[str]] = None
    price_usd: Optional[float] = None


class PokemonTCGData:
    """Pokemon TCG data handler for NEXUS"""

    # Pokemon card types
    CARD_TYPES = ['Pokemon', 'Trainer', 'Energy']

    # Common rarities
    RARITIES = [
        'Common', 'Uncommon', 'Rare', 'Rare Holo',
        'Ultra Rare', 'Secret Rare', 'Illustration Rare'
    ]

    # Pokemon types/elements
    POKEMON_TYPES = [
        'Colorless', 'Darkness', 'Dragon', 'Fairy',
        'Fighting', 'Fire', 'Grass', 'Lightning',
        'Metal', 'Psychic', 'Water'
    ]

    def __init__(self):
        self.cards: Dict[str, PokemonCard] = {}

    def add_card(self, card: PokemonCard) -> None:
        """Add a card to the database"""
        key = f"{card.set_code}-{card.number}"
        self.cards[key] = card

    def get_card(self, set_code: str, number: str) -> Optional[PokemonCard]:
        """Get a card by set code and number"""
        key = f"{set_code}-{number}"
        return self.cards.get(key)

    def search_by_name(self, name: str) -> List[PokemonCard]:
        """Search cards by name (partial match)"""
        name_lower = name.lower()
        return [c for c in self.cards.values() if name_lower in c.name.lower()]


if __name__ == "__main__":
    print("Pokemon TCG Data Module for NEXUS")
    print(f"Supported types: {', '.join(PokemonTCGData.POKEMON_TYPES)}")
