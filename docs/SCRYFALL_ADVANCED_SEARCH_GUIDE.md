# 🔍 Scryfall Advanced Search Integration Guide

## Overview
The Scryfall scraper now supports comprehensive advanced search syntax based on official Scryfall documentation. This enables powerful card filtering and discovery capabilities.

---

## 🎨 **Color & Color Identity**

### Syntax
- `c:` or `color:` - Card colors
- `id:` or `identity:` - Color identity (for Commander)

### Examples
```python
# Red and green cards
scraper.build_advanced_query(colors='rg')
# Query: "c:rg"

# Color identity for Esper (WUB)
scraper.build_advanced_query(color_identity='esper')
# Query: "id:esper"

# Colorless cards
scraper.build_advanced_query(colors='c')
```

### Color Codes
- `w` = White
- `u` = Blue  
- `b` = Black
- `r` = Red
- `g` = Green
- `c` = Colorless
- `m` = Multicolor

### Guild/Shard Names Supported
- Guilds: `azorius`, `dimir`, `rakdos`, `gruul`, `selesnya`, `orzhov`, `izzet`, `golgari`, `boros`, `simic`
- Shards: `bant`, `esper`, `grixis`, `jund`, `naya`
- Wedges: `abzan`, `jeskai`, `mardu`, `sultai`, `temur`

---

## 🃏 **Card Types**

### Syntax
- `t:` or `type:` - Card type/subtype

### Examples
```python
# Legendary creatures
scraper.build_advanced_query(type_line='legendary creature')

# Instant spells
scraper.build_advanced_query(type_line='instant')

# Goblin tribal
scraper.search_cards('t:goblin')
```

### Common Types
- Creatures, Instants, Sorceries, Artifacts, Enchantments
- Lands, Planeswalkers, Battles
- Legendary, Tribal, Snow

---

## 📝 **Oracle Text & Keywords**

### Syntax
- `o:` or `oracle:` - Text in Oracle text
- `kw:` or `keyword:` - Specific keyword abilities

### Examples
```python
# Cards that draw cards
scraper.build_advanced_query(oracle_text='draw')

# Cards with flying
scraper.build_advanced_query(keywords='flying')

# Multiple keywords
scraper.search_cards('kw:flying kw:trample')
```

### Common Keywords
- Flying, First Strike, Deathtouch, Trample, Haste
- Lifelink, Vigilance, Hexproof, Indestructible
- Flash, Defender, Menace, Reach

---

## 💎 **Mana Costs & CMC**

### Syntax
- `m:` or `mana:` - Specific mana cost
- `mv:` or `manavalue:` - Mana value (CMC)

### Examples
```python
# CMC = 3
scraper.build_advanced_query(cmc='=3')

# CMC <= 2 (low curve)
scraper.build_advanced_query(cmc='<=2')

# Specific mana cost {2}{U}{U}
scraper.build_advanced_query(mana_cost='2UU')
```

### Operators
- `=`, `<`, `>`, `<=`, `>=`, `!=`

---

## 💪 **Power, Toughness, Loyalty**

### Syntax
- `pow:` or `power:` - Creature power
- `tou:` or `toughness:` - Creature toughness
- `loy:` or `loyalty:` - Planeswalker loyalty

### Examples
```python
# Big creatures (power >= 8)
scraper.build_advanced_query(power='>=8')

# Top-heavy creatures (power > toughness)
scraper.search_cards('pow>tou t:creature')

# Planeswalkers starting at 4 loyalty
scraper.build_advanced_query(loyalty='=4')
```

---

## ⭐ **Rarity**

### Syntax
- `r:` or `rarity:` - Card rarity

### Examples
```python
# Mythic rares
scraper.build_advanced_query(rarity='mythic')

# Rare or above (rare + mythic)
scraper.search_cards('r>=rare')

# Commons only
scraper.build_advanced_query(rarity='common')
```

### Rarity Levels
- `common`, `uncommon`, `rare`, `mythic`, `special`, `bonus`

---

## 📦 **Sets & Blocks**

### Syntax
- `e:` or `s:` or `set:` - Set code
- `b:` or `block:` - Block code

### Examples
```python
# Cards from War of the Spark
scraper.build_advanced_query(set_code='war')

# Zendikar block
scraper.search_cards('b:zen')

# Multiple sets
scraper.search_cards('e:war OR e:m20')
```

---

## 🎮 **Format Legality**

### Syntax
- `f:` or `format:` - Format legal in
- `banned:` - Banned in format
- `is:commander` - Can be commander

### Examples
```python
# Modern legal cards
scraper.build_advanced_query(format='modern')

# Commander options
scraper.build_advanced_query(is_commander=True)

# Banned in Legacy
scraper.search_cards('banned:legacy')
```

### Supported Formats
- `standard`, `modern`, `legacy`, `vintage`, `pioneer`
- `commander`, `brawl`, `pauper`, `historic`
- `duel` (Duel Commander), `penny` (Penny Dreadful)

---

## 💰 **Price Filters**

### Syntax
- `usd:` - USD price
- `eur:` - EUR price  
- `tix:` - MTGO tickets

### Examples
```python
# Budget cards (under $5)
scraper.build_advanced_query(price_usd='<5')

# High-value cards ($50+)
scraper.build_advanced_query(price_usd='>=50')

# Free on MTGO (< 0.01 tix)
scraper.search_cards('tix<0.01')
```

---

## ✨ **Foil & Finishes**

### Syntax
- `is:foil` - Available in foil
- `is:nonfoil` - Available in non-foil
- `is:etched` - Etched foil available

### Examples
```python
# Foil cards only
scraper.build_advanced_query(is_foil=True)

# Cards available in both foil and non-foil
scraper.search_cards('is:foil is:nonfoil')

# Etched foils from a set
scraper.search_cards('e:cmr is:etched')
```

---

## 🎨 **Artist & Flavor Text**

### Syntax
- `a:` or `artist:` - Artist name
- `ft:` or `flavor:` - Flavor text

### Examples
```python
# Cards by John Avon
scraper.build_advanced_query(artist='Avon')

# Cards mentioning Urza in flavor text
scraper.build_advanced_query(flavor_text='Urza')
```

---

## 🔧 **Advanced Search Methods**

### `build_advanced_query(**filters)`
Build complex queries programmatically:

```python
query = scraper.build_advanced_query(
    colors='ub',
    type_line='creature',
    format='modern',
    cmc='<=3',
    rarity='rare',
    is_foil=True
)
# Result: "c:ub t:creature f:modern mv<=3 r:rare is:foil"
```

### `search_by_color_and_type(colors, card_type, format_legal=None)`
Quick color + type search:

```python
cards = scraper.search_by_color_and_type('rg', 'creature', 'standard')
```

### `search_foil_cards_in_set(set_code, min_price=None)`
Find valuable foils in a set:

```python
foils = scraper.search_foil_cards_in_set('mh2', min_price=20.0)
```

### `search_commander_options(colors=None, min_power=None)`
Find commander candidates:

```python
commanders = scraper.search_commander_options(colors='wubg', min_power=5)
```

### `search_budget_cards(card_type, max_price, format_legal)`
Budget-friendly cards:

```python
budget = scraper.search_budget_cards('creature', 2.0, 'modern')
```

### `search_high_value_foils(min_price=50.0, rarity='rare')`
Investment-grade foils:

```python
valuable = scraper.search_high_value_foils(min_price=100.0, rarity='mythic')
```

### `search_collection_upgrades(color_identity, format_name, card_type='creature', min_value=5.0)`
Find upgrade targets:

```python
upgrades = scraper.search_collection_upgrades('bant', 'commander', 'creature', 10.0)
```

---

## 🔗 **Complex Queries**

### Using OR
```python
# Fish OR Birds
scraper.search_cards('t:fish OR t:bird')

# Multiple artists
scraper.search_cards('(a:avon OR a:proce) t:land')
```

### Negation
```python
# Red cards without haste
scraper.search_cards('c:r -kw:haste')

# Non-creature goblins
scraper.search_cards('t:goblin -t:creature')
```

### Nesting Conditions
```python
# Legendary elves or goblins
scraper.search_cards('t:legendary (t:elf OR t:goblin)')
```

---

## 📊 **Special Filters**

### Multi-faced Cards
- `is:split`, `is:flip`, `is:transform`, `is:meld`, `is:dfc`, `is:mdfc`

### Card Properties
- `is:vanilla` - No abilities
- `is:spell` - Non-permanent
- `is:permanent` - Permanent card
- `is:reprint` - Previously printed
- `is:reserved` - Reserved List

### Land Types
- `is:fetchland`, `is:shockland`, `is:dual`
- `is:checkland`, `is:fastland`, `is:painland`

---

## 💡 **Example Use Cases**

### 1. Building a Budget Modern Deck
```python
# Budget red creatures for Modern
query = scraper.build_advanced_query(
    colors='r',
    type_line='creature',
    format='modern',
    price_usd='<2',
    cmc='<=3'
)
results = scraper.search_cards(query)
```

### 2. Finding Commander Staples
```python
# Valuable commander cards
commanders = scraper.search_commander_options(colors='grixis')
staples = scraper.search_cards('f:commander usd>=10 is:permanent')
```

### 3. Investment Hunting
```python
# High-value foil mythics
investments = scraper.search_high_value_foils(min_price=50.0, rarity='mythic')
```

### 4. Collection Analysis
```python
# Cards from a specific set that are foil-available
foil_data = scraper.search_foil_cards_in_set('mh2', min_price=5.0)

# Budget upgrades for a deck
upgrades = scraper.search_collection_upgrades('esper', 'modern', 'instant', 3.0)
```

---

## 🚀 **Integration Examples**

### In Main System
```python
# Check which cards in collection have foil versions
for card_name in inventory_data.keys():
    foil_info = scraper.get_foil_availability(card_name)
    if foil_info and foil_info['foil_available']:
        print(f"✨ {card_name} - Foil: ${foil_info['foil_price']:.2f}")

# Search for collection upgrades
upgrades = scraper.build_advanced_query(
    color_identity='wubrg',
    format='commander',
    type_line='creature',
    price_usd='>=15'
)
upgrade_cards = scraper.search_cards(upgrades)
```

---

## 📚 **Reference**

- Full Scryfall Syntax: https://scryfall.com/docs/syntax
- API Documentation: https://scryfall.com/docs/api
- Tagger Tags: https://scryfall.com/docs/tagger-tags

---

## ✅ **Summary**

The enhanced Scryfall scraper now supports:
- ✅ 50+ search operators
- ✅ Advanced query building
- ✅ Foil availability tracking
- ✅ Price filtering (USD/EUR/TIX)
- ✅ Format legality checks
- ✅ Commander-specific searches
- ✅ Complex boolean logic (AND/OR/NOT)
- ✅ Preset search methods for common use cases

Use these tools to build powerful card discovery, collection analysis, and investment tracking features!
