"""
Keyrune Set Symbol Integration for NEXUS
Maps MTG set codes to Keyrune icon font symbols
"""

# Keyrune CSS class mapping (set_code -> icon unicode)
# Format: set_code: (unicode_char, set_name)
KEYRUNE_SET_SYMBOLS = {
    # Core Sets
    'lea': ('\ue600', 'Limited Edition Alpha'),
    'leb': ('\ue601', 'Limited Edition Beta'),
    'm10': ('\ue90a', 'Magic 2010'),
    'm11': ('\ue90b', 'Magic 2011'),
    'm12': ('\ue90c', 'Magic 2012'),
    'm13': ('\ue90d', 'Magic 2013'),
    'm14': ('\ue90e', 'Magic 2014'),
    'm15': ('\ue90f', 'Magic 2015'),
    'm19': ('\ue910', 'Magic 2019'),
    'm20': ('\ue911', 'Magic 2020'),
    'm21': ('\ue912', 'Magic 2021'),
    
    # Recent Sets (2020-2025)
    'znr': ('\ue9a0', 'Zendikar Rising'),
    'khm': ('\ue9a1', 'Kaldheim'),
    'stx': ('\ue9a2', 'Strixhaven'),
    'afr': ('\ue9a3', 'Adventures in the Forgotten Realms'),
    'mid': ('\ue9a4', 'Innistrad: Midnight Hunt'),
    'vow': ('\ue9a5', 'Innistrad: Crimson Vow'),
    'neo': ('\ue9a6', 'Kamigawa: Neon Dynasty'),
    'snc': ('\ue9a7', 'Streets of New Capenna'),
    'dmu': ('\ue9a8', 'Dominaria United'),
    'bro': ('\ue9a9', 'The Brothers\' War'),
    'one': ('\ue9aa', 'Phyrexia: All Will Be One'),
    'mom': ('\ue9ab', 'March of the Machine'),
    'mat': ('\ue9ac', 'March of the Machine: The Aftermath'),
    'woe': ('\ue9ad', 'Wilds of Eldraine'),
    'lci': ('\ue9ae', 'The Lost Caverns of Ixalan'),
    'mkm': ('\ue9af', 'Murders at Karlov Manor'),
    'otj': ('\ue9b0', 'Outlaws of Thunder Junction'),
    'blb': ('\ue9b1', 'Bloomburrow'),
    'dsk': ('\ue9b2', 'Duskmourn: House of Horror'),
    'fdn': ('\ue9b3', 'Foundations'),
    
    # Commander Sets
    'cmr': ('\ue950', 'Commander Legends'),
    'cmd': ('\ue951', 'Commander 2011'),
    'c13': ('\ue952', 'Commander 2013'),
    'c14': ('\ue953', 'Commander 2014'),
    'c15': ('\ue954', 'Commander 2015'),
    'c16': ('\ue955', 'Commander 2016'),
    'c17': ('\ue956', 'Commander 2017'),
    'c18': ('\ue957', 'Commander 2018'),
    'c19': ('\ue958', 'Commander 2019'),
    'c20': ('\ue959', 'Commander 2020'),
    'c21': ('\ue95a', 'Commander 2021'),
    'clb': ('\ue95b', 'Commander Legends: Battle for Baldur\'s Gate'),
    
    # Masters Sets
    'mh1': ('\ue970', 'Modern Horizons'),
    'mh2': ('\ue971', 'Modern Horizons 2'),
    'mh3': ('\ue972', 'Modern Horizons 3'),
    '2x2': ('\ue973', 'Double Masters 2022'),
    'tsr': ('\ue974', 'Time Spiral Remastered'),
    
    # Popular Sets
    'war': ('\ue800', 'War of the Spark'),
    'eld': ('\ue801', 'Throne of Eldraine'),
    'thb': ('\ue802', 'Theros Beyond Death'),
    'iko': ('\ue803', 'Ikoria: Lair of Behemoths'),
    'rna': ('\ue804', 'Ravnica Allegiance'),
    'grn': ('\ue805', 'Guilds of Ravnica'),
    'dom': ('\ue806', 'Dominaria'),
    'rix': ('\ue807', 'Rivals of Ixalan'),
    'xln': ('\ue808', 'Ixalan'),
    'hou': ('\ue809', 'Hour of Devastation'),
    'akh': ('\ue80a', 'Amonkhet'),
    'aer': ('\ue80b', 'Aether Revolt'),
    'kld': ('\ue80c', 'Kaladesh'),
    'emn': ('\ue80d', 'Eldritch Moon'),
    'soi': ('\ue80e', 'Shadows over Innistrad'),
    'ogw': ('\ue80f', 'Oath of the Gatewatch'),
    'bfz': ('\ue810', 'Battle for Zendikar'),
    
    # Special/Promo
    'plist': ('\ue700', 'The List'),
    'sld': ('\ue701', 'Secret Lair Drop'),
    'prm': ('\ue702', 'Promotional'),
    
    # Default for unknown sets
    'default': ('\ue684', 'Unknown Set')
}


def get_set_symbol(set_code):
    """
    Get Keyrune unicode symbol for a set code
    
    Args:
        set_code: MTG set code (e.g., 'neo', 'mid', 'c21')
        
    Returns:
        Unicode character for the set symbol
    """
    set_code_lower = set_code.lower().strip() if set_code else ''
    symbol_data = KEYRUNE_SET_SYMBOLS.get(set_code_lower, KEYRUNE_SET_SYMBOLS['default'])
    return symbol_data[0]


def get_set_name(set_code):
    """
    Get full set name for a set code
    
    Args:
        set_code: MTG set code
        
    Returns:
        Full set name string
    """
    set_code_lower = set_code.lower().strip() if set_code else ''
    symbol_data = KEYRUNE_SET_SYMBOLS.get(set_code_lower, KEYRUNE_SET_SYMBOLS['default'])
    return symbol_data[1]


def format_set_display(set_code):
    """
    Format set code with Keyrune symbol for display
    
    Args:
        set_code: MTG set code
        
    Returns:
        Formatted string with symbol + code (e.g., "⚙ NEO")
    """
    if not set_code:
        return ""
    
    symbol = get_set_symbol(set_code)
    return f"{symbol} {set_code.upper()}"


# Rarity colors for set symbols
RARITY_COLORS = {
    'common': '#1a1a1a',      # Black
    'uncommon': '#707883',    # Silver
    'rare': '#a58e4a',        # Gold
    'mythic': '#bf4427',      # Orange-Red
    'special': '#652978'      # Purple
}


def get_rarity_color(rarity):
    """Get color code for card rarity"""
    return RARITY_COLORS.get(rarity.lower() if rarity else 'common', RARITY_COLORS['common'])


if __name__ == "__main__":
    # Test set symbol mapping
    print("🎴 Testing Keyrune Set Symbols\n")
    
    test_sets = ['neo', 'mid', 'c21', 'mh2', 'khm', 'znr', 'invalid']
    
    for set_code in test_sets:
        symbol = get_set_symbol(set_code)
        name = get_set_name(set_code)
        display = format_set_display(set_code)
        print(f"{display} - {name}")
