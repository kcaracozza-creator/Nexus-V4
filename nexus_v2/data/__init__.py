"""
NEXUS V2 - Data Module

Exports:
- CallSignGenerator, get_generator, generate_call_sign, generate_call_signs
- GestixStyleInventory (UI component)
- ScryfallDatabase, ScryfallCard, get_scryfall_db
"""

# Call sign system
from .call_sign_generator import (
    CallSignGenerator,
    get_generator,
    generate_call_sign,
    generate_call_signs
)

# Inventory UI (Gestix-style)
from .inventory_schema import GestixStyleInventory

# Scryfall database
from .scryfall_db import (
    ScryfallDatabase,
    ScryfallCard,
    get_scryfall_db
)

__all__ = [
    # Call signs
    'CallSignGenerator',
    'get_generator',
    'generate_call_sign',
    'generate_call_signs',

    # Inventory UI
    'GestixStyleInventory',

    # Scryfall
    'ScryfallDatabase',
    'ScryfallCard',
    'get_scryfall_db'
]
