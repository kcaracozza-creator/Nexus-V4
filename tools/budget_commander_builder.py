"""
Budget Commander Deck Builder
Builds 5 budget commander decklists (~$25 each) and queries Scryfall
for all printings of each card (set code + collector number).
Outputs one CSV per deck.
"""

import csv
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from collections import OrderedDict

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "commander_decks")
SCRYFALL_SEARCH = "https://api.scryfall.com/cards/search"
SCRYFALL_NAMED = "https://api.scryfall.com/cards/named"
RATE_LIMIT_MS = 120  # Scryfall asks for 50-100ms between requests

# ──────────────────────────────────────────────────────────────
# 5 Budget Commander Decklists (99 + 1 commander = 100 each)
# Source: EDHREC budget recommendations, curated for ~$25 total
# ──────────────────────────────────────────────────────────────

DECKS = {
    "talrand_sky_summoner": {
        "commander": "Talrand, Sky Summoner",
        "colors": "U",
        "strategy": "Cast instants/sorceries, make 2/2 Drake tokens, win through the air",
        "cards": OrderedDict([
            # Commander
            ("Talrand, Sky Summoner", 1),
            # Creatures (few - we want spells)
            ("Archaeomancer", 1),
            ("Augur of Bolas", 1),
            ("Baral, Chief of Compliance", 1),
            ("Curious Homunculus", 1),
            ("Haughty Djinn", 1),
            ("Mnemonic Wall", 1),
            ("Wavebreak Hippocamp", 1),
            ("Naiad of Hidden Coves", 1),
            ("Windstorm Drake", 1),
            ("Docent of Perfection", 1),
            # Instants - Counterspells
            ("Counterspell", 1),
            ("Spell Pierce", 1),
            ("Negate", 1),
            ("Dissolve", 1),
            ("Lofty Denial", 1),
            ("Convolute", 1),
            ("Bone to Ash", 1),
            ("Exclude", 1),
            # Instants - Card Draw / Cantrips
            ("Brainstorm", 1),
            ("Consider", 1),
            ("Impulse", 1),
            ("Deliberate", 1),
            ("Telling Time", 1),
            ("Frantic Search", 1),
            ("Fact or Fiction", 1),
            ("Dig Through Time", 1),
            ("Radical Idea", 1),
            ("Obsessive Search", 1),
            ("Peek", 1),
            ("Fleeting Distraction", 1),
            ("Twisted Image", 1),
            ("A Little Chat", 1),
            # Instants - Bounce / Removal
            ("Blink of an Eye", 1),
            ("Run Away Together", 1),
            ("Boomerang", 1),
            ("Disperse", 1),
            ("Turn Aside", 1),
            ("Keep Safe", 1),
            # Sorceries
            ("Ponder", 1),
            ("Preordain", 1),
            ("Serum Visions", 1),
            ("Sleight of Hand", 1),
            ("Chart a Course", 1),
            ("Deep Analysis", 1),
            ("Compulsive Research", 1),
            ("Rise from the Tides", 1),
            ("Curse of the Swine", 1),
            ("Sleep", 1),
            ("Distant Melody", 1),
            ("Talrand's Invocation", 1),
            ("Strategic Planning", 1),
            ("Portent", 1),
            ("Void Snare", 1),
            ("Call to Mind", 1),
            # Enchantments
            ("Coastal Piracy", 1),
            ("Reconnaissance Mission", 1),
            ("Jace's Sanctum", 1),
            # Artifacts
            ("Sol Ring", 1),
            ("Sky Diamond", 1),
            ("Mind Stone", 1),
            ("Wayfarer's Bauble", 1),
            ("Heraldic Banner", 1),
            ("Bident of Thassa", 1),
            # Lands (36)
            ("Island", 31),
            ("Lonely Sandbar", 1),
            ("Remote Isle", 1),
            ("Mystic Sanctuary", 1),
            ("Halimar Depths", 1),
            ("Desert of the Mindful", 1),
        ]),
    },

    "zada_hedron_grinder": {
        "commander": "Zada, Hedron Grinder",
        "colors": "R",
        "strategy": "Go wide with tokens, cast targeted spells on Zada to copy to all creatures, storm off",
        "cards": OrderedDict([
            # Commander
            ("Zada, Hedron Grinder", 1),
            # Token Generators
            ("Dragon Fodder", 1),
            ("Krenko's Command", 1),
            ("Hordeling Outburst", 1),
            ("Empty the Warrens", 1),
            ("Goblin Instigator", 1),
            ("Mogg War Marshal", 1),
            ("Beetleback Chief", 1),
            ("Siege-Gang Commander", 1),
            ("Young Pyromancer", 1),
            ("Loyal Apprentice", 1),
            ("Krenko, Mob Boss", 1),
            ("Goblin Matron", 1),
            ("Akroan Crusader", 1),
            ("Ral's Reinforcements", 1),
            ("Forbidden Friendship", 1),
            ("Goblin War Party", 1),
            # Targeted Cantrips (copy to all with Zada)
            ("Expedite", 1),
            ("Renegade Tactics", 1),
            ("Stun", 1),
            ("Fists of Flame", 1),
            ("Ancestral Anger", 1),
            ("Blazing Crescendo", 1),
            ("Samut's Sprint", 1),
            ("Accelerate", 1),
            ("Rile", 1),
            ("Kick in the Door", 1),
            # Targeted Pump (copy to all with Zada)
            ("Titan's Strength", 1),
            ("Brute Force", 1),
            ("Sudden Breakthrough", 1),
            ("Temur Battle Rage", 1),
            ("Run Amok", 1),
            ("Brute Strength", 1),
            ("Infuriate", 1),
            ("Rush of Adrenaline", 1),
            ("Might of the Meek", 1),
            ("Felonious Rage", 1),
            # Other targeted spells
            ("Otherworldly Outburst", 1),
            ("Antagonize", 1),
            ("Balduvian Rage", 1),
            ("Witch's Mark", 1),
            # Mana Generation
            ("Battle Hymn", 1),
            ("Brightstone Ritual", 1),
            ("Skirk Prospector", 1),
            ("Iron Myr", 1),
            # Utility
            ("Guttersnipe", 1),
            ("Storm-Kiln Artist", 1),
            ("Monastery Swiftspear", 1),
            ("Kiln Fiend", 1),
            ("Soul's Fire", 1),
            # Artifacts
            ("Sol Ring", 1),
            ("Fire Diamond", 1),
            ("Mind Stone", 1),
            ("Arcane Signet", 1),
            # Lands (46)
            ("Mountain", 42),
            ("Forgotten Cave", 1),
            ("Dwarven Mine", 1),
            ("Mishra's Factory", 1),
            ("Kher Keep", 1),
        ]),
    },

    "fynn_the_fangbearer": {
        "commander": "Fynn, the Fangbearer",
        "colors": "G",
        "strategy": "Attack with deathtouch creatures to give poison counters (2 per hit), 10 poison = dead",
        "cards": OrderedDict([
            # Commander
            ("Fynn, the Fangbearer", 1),
            # Deathtouch Creatures (the core)
            ("Ambush Viper", 1),
            ("Deadly Recluse", 1),
            ("Sedge Scorpion", 1),
            ("Moss Viper", 1),
            ("Tajuru Blightblade", 1),
            ("Thornweald Archer", 1),
            ("Nightshade Dryad", 1),
            ("Fang of Shigeki", 1),
            ("Wasteland Viper", 1),
            ("Narnam Renegade", 1),
            ("Gnarlwood Dryad", 1),
            ("Jewel-Eyed Cobra", 1),
            ("Poison Dart Frog", 1),
            ("Toxic Scorpion", 1),
            ("Ankle Biter", 1),
            ("Kraul Stinger", 1),
            ("Daggerback Basilisk", 1),
            ("Underdark Basilisk", 1),
            ("Ichorspit Basilisk", 1),
            ("Mirkwood Spider", 1),
            ("Heir of the Wilds", 1),
            ("Nightshade Peddler", 1),
            ("Hornet Nest", 1),
            ("Hornet Queen", 1),
            # Infect Creatures (also give poison)
            ("Blight Mamba", 1),
            ("Glistener Elf", 1),
            # Evasion / Trample Enablers
            ("Rancor", 1),
            ("Lure", 1),
            ("Charge Through", 1),
            ("Ram Through", 1),
            ("Overrun", 1),
            # Deathtouch Enablers
            ("Viridian Longbow", 1),
            ("Cliffhaven Kitesail", 1),
            ("Fireshrieker", 1),
            ("Poison the Blade", 1),
            # Protection
            ("Snakeskin Veil", 1),
            ("Ranger's Guile", 1),
            # Removal / Interaction
            ("Bite Down", 1),
            ("Infectious Bite", 1),
            ("Rabid Bite", 1),
            ("Return to Nature", 1),
            ("Carnivorous Canopy", 1),
            # Card Draw / Utility
            ("Harmonize", 1),
            ("Lifecrafter's Bestiary", 1),
            ("Hunter's Talent", 1),
            ("Snake Umbra", 1),
            ("Blanchwood Armor", 1),
            # Ramp
            ("Llanowar Elves", 1),
            ("Wild Growth", 1),
            ("Rampant Growth", 1),
            ("Cultivate", 1),
            ("Explore", 1),
            # Creatures - Utility
            ("Acidic Slime", 1),
            ("Cankerbloom", 1),
            ("Oakhame Adversary", 1),
            ("Deathbloom Gardener", 1),
            # Artifacts
            ("Sol Ring", 1),
            ("Contagion Clasp", 1),
            # Lands (41)
            ("Forest", 36),
            ("Rogue's Passage", 1),
            ("Access Tunnel", 1),
            ("Tranquil Thicket", 1),
            ("Slippery Karst", 1),
            ("Escape Tunnel", 1),
        ]),
    },

    "edric_spymaster_of_trest": {
        "commander": "Edric, Spymaster of Trest",
        "colors": "UG",
        "strategy": "Small evasive creatures draw tons of cards via Edric, overwhelm with card advantage",
        "cards": OrderedDict([
            # Commander
            ("Edric, Spymaster of Trest", 1),
            # 1-drop Evasive Creatures
            ("Slither Blade", 1),
            ("Triton Shorestalker", 1),
            ("Mist-Cloaked Herald", 1),
            ("Gudul Lurker", 1),
            ("Spectral Sailor", 1),
            ("Siren Stormtamer", 1),
            ("Faerie Seer", 1),
            ("Cloud Sprite", 1),
            ("Zephyr Sprite", 1),
            ("Spire Tracer", 1),
            ("Treetop Scout", 1),
            ("Scryb Sprites", 1),
            ("Network Disruptor", 1),
            ("Faerie Miscreant", 1),
            ("Mistway Spy", 1),
            ("Lantern Bearer", 1),
            ("Spyglass Siren", 1),
            ("Silver Raven", 1),
            # 2-drop Evasive
            ("Wingcrafter", 1),
            ("Looter il-Kor", 1),
            ("Cloudfin Raptor", 1),
            ("Merfolk Windrobber", 1),
            ("Artificer's Assistant", 1),
            ("Spiketail Hatchling", 1),
            # Utility Creatures
            ("Tetsuko Umezawa, Fugitive", 1),
            ("Llanowar Elves", 1),
            ("Elvish Mystic", 1),
            ("Arbor Elf", 1),
            ("Cloud of Faeries", 1),
            ("Trygon Predator", 1),
            ("Jolrael, Mwonvuli Recluse", 1),
            ("Hypnotic Siren", 1),
            # Instants
            ("Counterspell", 1),
            ("Negate", 1),
            ("Mana Leak", 1),
            ("Spell Pierce", 1),
            ("Unified Will", 1),
            ("Dispel", 1),
            ("Snakeskin Veil", 1),
            # Sorceries
            ("Overrun", 1),
            ("Harvest Season", 1),
            ("Regrowth", 1),
            # Enchantments
            ("Coastal Piracy", 1),
            ("Reconnaissance Mission", 1),
            ("Beastmaster Ascension", 1),
            ("Wild Growth", 1),
            ("Witness Protection", 1),
            ("Druids' Repository", 1),
            # Artifacts
            ("Sol Ring", 1),
            ("Simic Signet", 1),
            # Lands (49)
            ("Island", 22),
            ("Forest", 20),
            ("Command Tower", 1),
            ("Yavimaya Coast", 1),
            ("Vineglimmer Snarl", 1),
            ("Thornwood Falls", 1),
            ("Simic Guildgate", 1),
            ("Evolving Wilds", 1),
            ("Terramorphic Expanse", 1),
        ]),
    },

    "teysa_karlov": {
        "commander": "Teysa Karlov",
        "colors": "WB",
        "strategy": "Aristocrats: sacrifice creatures for death triggers (doubled by Teysa), drain opponents",
        "cards": OrderedDict([
            # Commander
            ("Teysa Karlov", 1),
            # Death Trigger Payoffs
            ("Zulaport Cutthroat", 1),
            ("Cruel Celebrant", 1),
            ("Vindictive Vampire", 1),
            ("Bastion of Remembrance", 1),
            ("Falkenrath Noble", 1),
            ("Syr Konrad, the Grim", 1),
            ("Mirkwood Bats", 1),
            ("Midnight Reaper", 1),
            # Token / Death Replacement Creatures
            ("Doomed Traveler", 1),
            ("Hunted Witness", 1),
            ("Doomed Dissenter", 1),
            ("Garrison Cat", 1),
            ("Ministrant of Obligation", 1),
            ("Orzhov Enforcer", 1),
            ("Carrier Thrall", 1),
            ("Tithe Taker", 1),
            ("Hallowed Spiritkeeper", 1),
            ("Sifter of Skulls", 1),
            ("Requiem Angel", 1),
            ("Imperious Oligarch", 1),
            ("Infestation Sage", 1),
            # Sacrifice Outlets
            ("Carrion Feeder", 1),
            ("Woe Strider", 1),
            ("Priest of Forgotten Gods", 1),
            ("Yahenni, Undying Partisan", 1),
            ("Spawning Pit", 1),
            ("Ashnod's Altar", 1),
            ("Fanatical Devotion", 1),
            ("Vampiric Rites", 1),
            # Utility Creatures
            ("Solemn Simulacrum", 1),
            ("Pitiless Plunderer", 1),
            ("Teysa, Orzhov Scion", 1),
            ("Reveillark", 1),
            ("Ogre Slumlord", 1),
            # Instants
            ("Swords to Plowshares", 1),
            ("Deadly Dispute", 1),
            ("Corrupted Conviction", 1),
            ("Tragic Slip", 1),
            ("Despark", 1),
            ("Generous Gift", 1),
            ("Costly Plunder", 1),
            ("Plumb the Forbidden", 1),
            # Sorceries
            ("Sign in Blood", 1),
            ("Read the Bones", 1),
            ("Lingering Souls", 1),
            ("Bone Splinters", 1),
            ("Dread Return", 1),
            ("Feed the Swarm", 1),
            ("Unearth", 1),
            # Enchantments
            ("Field of Souls", 1),
            ("Open the Graves", 1),
            ("Hidden Stockpile", 1),
            ("Intangible Virtue", 1),
            # Artifacts
            ("Sol Ring", 1),
            ("Arcane Signet", 1),
            ("Orzhov Signet", 1),
            ("Mind Stone", 1),
            ("Wayfarer's Bauble", 1),
            ("Skullclamp", 1),
            # Lands (40)
            ("Swamp", 17),
            ("Plains", 15),
            ("Command Tower", 1),
            ("Orzhov Basilica", 1),
            ("Temple of Silence", 1),
            ("Scoured Barrens", 1),
            ("Caves of Koilos", 1),
            ("Tainted Field", 1),
            ("Evolving Wilds", 1),
            ("Terramorphic Expanse", 1),
        ]),
    },
}


def scryfall_get_printings(card_name):
    """Query Scryfall for all printings of a card. Returns list of (set_code, set_name, collector_number)."""
    # Use exact name search with unique=prints to get all printings
    query = f'!"{card_name}"'
    params = urllib.parse.urlencode({
        "q": query,
        "unique": "prints",
        "order": "released",
    })
    url = f"{SCRYFALL_SEARCH}?{params}"

    printings = []
    while url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NexusBudgetCommander/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())

            for card in data.get("data", []):
                set_code = card.get("set", "").upper()
                set_name = card.get("set_name", "")
                collector_number = card.get("collector_number", "")
                # Skip digital-only sets (Arena/MTGO only)
                if card.get("digital", False) and not card.get("paper", True):
                    continue
                printings.append((set_code, set_name, collector_number))

            # Handle pagination
            if data.get("has_more"):
                url = data.get("next_page")
                time.sleep(RATE_LIMIT_MS / 1000.0)
            else:
                url = None

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  WARNING: Card not found on Scryfall: {card_name}")
                return []
            elif e.code == 429:
                print(f"  Rate limited, waiting 2s...")
                time.sleep(2)
                continue
            else:
                print(f"  ERROR {e.code} for {card_name}: {e.reason}")
                return []
        except Exception as e:
            print(f"  ERROR for {card_name}: {e}")
            return []

    return printings


def verify_deck_count(deck_name, cards):
    """Verify a deck has exactly 100 cards."""
    total = sum(cards.values())
    if total != 100:
        print(f"  WARNING: {deck_name} has {total} cards (expected 100)")
    return total


def build_csv(deck_name, deck_info, output_dir):
    """Build a CSV file for one deck with all printings."""
    commander = deck_info["commander"]
    cards = deck_info["cards"]
    colors = deck_info["colors"]
    strategy = deck_info["strategy"]

    total = verify_deck_count(deck_name, cards)

    csv_path = os.path.join(output_dir, f"{deck_name}.csv")
    print(f"\n{'='*60}")
    print(f"Building: {commander} ({colors}) - {total} cards")
    print(f"Strategy: {strategy}")
    print(f"Output: {csv_path}")
    print(f"{'='*60}")

    # Collect all unique card names (basics don't need printings lookup)
    basics = {"Island", "Mountain", "Forest", "Plains", "Swamp"}

    rows = []
    unique_cards = [name for name in cards.keys() if name not in basics]
    total_unique = len(unique_cards)

    for i, card_name in enumerate(unique_cards):
        qty = cards[card_name]
        print(f"  [{i+1}/{total_unique}] {card_name}...", end=" ", flush=True)

        time.sleep(RATE_LIMIT_MS / 1000.0)
        printings = scryfall_get_printings(card_name)

        if printings:
            print(f"{len(printings)} printings")
            for set_code, set_name, collector_num in printings:
                rows.append({
                    "card_name": card_name,
                    "quantity": qty,
                    "set_code": set_code,
                    "set_name": set_name,
                    "collector_number": collector_num,
                    "is_commander": "YES" if card_name == commander else "",
                })
        else:
            print("NO PRINTINGS FOUND")
            rows.append({
                "card_name": card_name,
                "quantity": qty,
                "set_code": "???",
                "set_name": "Unknown",
                "collector_number": "???",
                "is_commander": "YES" if card_name == commander else "",
            })

    # Add basics (no need to look up every basic land printing)
    for basic in basics:
        if basic in cards:
            rows.append({
                "card_name": basic,
                "quantity": cards[basic],
                "set_code": "ANY",
                "set_name": "Any set (basic land)",
                "collector_number": "Any",
                "is_commander": "",
            })

    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "card_name", "quantity", "set_code", "set_name", "collector_number", "is_commander"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Wrote {len(rows)} rows to {csv_path}")
    return csv_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("NEXUS Budget Commander Deck Builder")
    print(f"Building {len(DECKS)} decks with Scryfall printings data")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    csv_files = []
    for deck_name, deck_info in DECKS.items():
        csv_path = build_csv(deck_name, deck_info, OUTPUT_DIR)
        csv_files.append(csv_path)

    print(f"\n{'='*60}")
    print("DONE! Generated CSV files:")
    for f in csv_files:
        print(f"  {f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
