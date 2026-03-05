#!/usr/bin/env python3
"""
Patch 8: Expand stopwords, require word length >= 7 for search,
raise near-miss overlap threshold back to 2.
"""
import sys

SERVER = "/home/danielson/danielson/danielson_server.py"

with open(SERVER, "r") as f:
    content = f.read()

# Fix 1: Expand stopwords and require >= 7 char words for search
old_sw = """            stopwords = {'creature', 'instant', 'sorcery', 'artifact', 'enchantment', 'enchantments', 'planeswalker',
                         'legendary', 'target', 'player', 'trample', 'flying', 'haste', 'lifelink',
                         'whenever', 'deals', 'combat', 'damage', 'destroy', 'becomes', 'controls',
                         'counter', 'permanent', 'creature'}
            search_words = sorted([w for w in ocr_all_words if len(w) >= 5 and w not in stopwords], key=len, reverse=True)"""

new_sw = """            stopwords = {
                # Card types
                'creature', 'instant', 'sorcery', 'artifact', 'enchantment', 'enchantments',
                'planeswalker', 'legendary', 'tribal', 'basic', 'land', 'battle',
                # Keywords
                'target', 'player', 'trample', 'flying', 'haste', 'lifelink', 'deathtouch',
                'vigilance', 'hexproof', 'indestructible', 'menace', 'reach', 'flash',
                'whenever', 'deals', 'combat', 'damage', 'destroy', 'becomes', 'controls',
                'counter', 'permanent', 'enters', 'battlefield', 'triggers', 'activated',
                # Common ability words
                'library', 'graveyard', 'exile', 'exiled', 'exiles', 'hand', 'spell',
                'ability', 'effect', 'power', 'toughness', 'mana', 'equal', 'least',
                'control', 'controller', 'opponent', 'another', 'token', 'sacrifice',
                'reveal', 'cards', 'draw', 'discard', 'loses', 'gains', 'search',
                'shuffle', 'return', 'prevent', 'instead', 'would', 'unless', 'attach',
                'block', 'attack', 'attacks', 'blocks', 'choose', 'chooses', 'chosen',
                'cast', 'costs', 'reduce', 'each', 'other', 'their', 'puts', 'until',
                # Common short words that match too broadly
                'the', 'and', 'that', 'this', 'with', 'have', 'into', 'from', 'then',
                'also', 'only', 'more', 'than', 'your', 'also', 'upon', 'once', 'when',
                'they', 'them', 'its', 'you',
                # Flavor text words (common false positives)
                'punishment', 'fickle', 'preserve', 'behemoth', 'prophecy', 'delivering',
                'human', 'alone', 'stand', 'hold', 'wall', 'city', 'touch', 'alone',
                'against', 'before', 'costs', 'control',
            }
            # Only search on highly specific words: >= 7 chars, not stopwords
            search_words = sorted([w for w in ocr_all_words if len(w) >= 7 and w not in stopwords], key=len, reverse=True)"""

if old_sw in content:
    content = content.replace(old_sw, new_sw, 1)
    print("Fix 1 applied: stopwords expanded, min word length 5->7")
else:
    print("ERROR: stopwords block not found")
    sys.exit(1)

# Fix 2: raise overlap back to 2 (was incorrectly lowered to 1)
old_ov = "                        if soverlap >= 1 and sword.lower() in sname.lower():"
new_ov = "                        if soverlap >= 2 and sword.lower() in sname.lower():"

if old_ov in content:
    content = content.replace(old_ov, new_ov, 1)
    print("Fix 2 applied: overlap threshold back to 2")
else:
    print("WARNING: overlap line not found")

with open(SERVER, "w") as f:
    f.write(content)

import subprocess
r = subprocess.run(['python3', '-c', f'import py_compile; py_compile.compile("{SERVER}", doraise=True)'],
                   capture_output=True, text=True)
print("Syntax OK" if r.returncode == 0 else f"SYNTAX ERROR: {r.stderr}")
print("Done")
