#!/usr/bin/env python3
"""
NEXUS Bridge Table Populator
==============================
Populates nexus_cards.db which bridges FAISS vector indexes to card metadata.

The FAISS index stores embeddings with integer indices (0, 1, 2, ...).
The card_ids.json maps those indices to card identifiers.
nexus_cards.db maps: faiss_index -> card metadata (name, set, rarity, etc.)

This makes FAISS visual matches useful: image -> FAISS index -> card info.

Run on ZULTAN:
    python3 populate_bridge_table.py
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Paths on ZULTAN
NEXUS_CARDS_DB = os.path.expanduser("~/nexus_cards.db")

# MTG FAISS data
MTG_CARD_IDS_PATH = os.path.expanduser("~/training/models/faiss_index/card_ids.json")
MTG_LOOKUP_PATH = os.path.expanduser("~/training/metadata/card_lookup.json")

# Pokemon FAISS data
POKEMON_CARD_IDS_PATH = os.path.expanduser("~/training/models/pokemon/faiss_index/pokemon_card_ids.json")
POKEMON_LOOKUP_PATH = "/opt/nexus/training/data/pokemon/metadata/pokemon_lookup.json"


def populate():
    start = time.time()

    conn = sqlite3.connect(NEXUS_CARDS_DB)
    cursor = conn.cursor()

    # Ensure table exists with expanded schema
    cursor.execute("DROP TABLE IF EXISTS cards")
    cursor.execute("""
        CREATE TABLE cards (
            faiss_index INTEGER,
            tcg TEXT NOT NULL,
            card_id TEXT,
            name TEXT,
            set_code TEXT,
            set_name TEXT,
            collector_number TEXT,
            rarity TEXT,
            image_url TEXT,
            scryfall_id TEXT,
            oracle_id TEXT,
            price_usd REAL,
            card_data TEXT,
            PRIMARY KEY (tcg, faiss_index)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_name ON cards(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_card_id ON cards(card_id)")

    total_inserted = 0

    # =========================================================================
    # MTG: card_ids.json -> card_lookup.json
    # =========================================================================
    print("[Bridge] Loading MTG data...")
    try:
        # card_ids.json: list of identifiers, index position = FAISS index
        with open(MTG_CARD_IDS_PATH, "r") as f:
            mtg_card_ids = json.load(f)
        print(f"[Bridge] MTG FAISS IDs: {len(mtg_card_ids):,}")

        with open(MTG_LOOKUP_PATH, "r") as f:
            mtg_lookup = json.load(f)
        print(f"[Bridge] MTG lookup: {len(mtg_lookup):,}")

        # Build name->scryfall_id index for matching
        # card_ids entries are like "set_cn_Name" format
        name_set_index = {}
        for sid, card in mtg_lookup.items():
            name = card.get("n", "")
            set_code = card.get("s", "")
            cn = card.get("cn", "")
            # Multiple index keys for matching
            name_set_index[sid] = card  # Direct scryfall_id match
            name_set_index[f"{set_code}_{cn}_{name}"] = (sid, card)
            name_set_index[f"{set_code}_{cn}"] = (sid, card)

        matched = 0
        for faiss_idx, card_id_str in enumerate(mtg_card_ids):
            # card_id_str might be a scryfall UUID or a formatted string
            card_data = None
            scryfall_id = None

            # Try direct scryfall_id match
            if card_id_str in mtg_lookup:
                scryfall_id = card_id_str
                card_data = mtg_lookup[card_id_str]
            else:
                # Try matching by the formatted string
                match = name_set_index.get(card_id_str)
                if match and isinstance(match, tuple):
                    scryfall_id, card_data = match

            if card_data:
                cursor.execute("""
                    INSERT OR REPLACE INTO cards
                    (faiss_index, tcg, card_id, name, set_code, set_name,
                     collector_number, rarity, image_url, scryfall_id, oracle_id,
                     price_usd, card_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    faiss_idx, "mtg", scryfall_id,
                    card_data.get("n", ""),
                    card_data.get("s", ""),
                    card_data.get("sn", ""),
                    card_data.get("cn", ""),
                    card_data.get("r", ""),
                    f"https://api.scryfall.com/cards/{scryfall_id}?format=image" if scryfall_id else "",
                    scryfall_id,
                    card_data.get("o", ""),
                    card_data.get("p", 0),
                    json.dumps(card_data)
                ))
                matched += 1
            else:
                # Insert with just the card_id string and faiss_index
                cursor.execute("""
                    INSERT OR REPLACE INTO cards
                    (faiss_index, tcg, card_id, name, set_code, set_name,
                     collector_number, rarity, image_url, scryfall_id, oracle_id,
                     price_usd, card_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (faiss_idx, "mtg", card_id_str, card_id_str,
                      "", "", "", "", "", "", "", 0, ""))

            total_inserted += 1

        conn.commit()
        print(f"[Bridge] MTG: {total_inserted:,} entries, {matched:,} matched to metadata")

    except Exception as e:
        print(f"[Bridge] MTG error: {e}")

    # =========================================================================
    # POKEMON: pokemon_card_ids.json -> pokemon_lookup.json
    # =========================================================================
    print("[Bridge] Loading Pokemon data...")
    poke_inserted = 0
    try:
        with open(POKEMON_CARD_IDS_PATH, "r") as f:
            pokemon_card_ids = json.load(f)
        print(f"[Bridge] Pokemon FAISS IDs: {len(pokemon_card_ids):,}")

        with open(POKEMON_LOOKUP_PATH, "r") as f:
            pokemon_lookup = json.load(f)
        print(f"[Bridge] Pokemon lookup: {len(pokemon_lookup):,}")

        # Pokemon card_ids are like "sm2_75_Mudbray" format
        # Pokemon lookup keys are like "sm2-75"
        poke_matched = 0
        for faiss_idx, card_id_str in enumerate(pokemon_card_ids):
            # Try to convert "sm2_75_Mudbray" to "sm2-75" lookup key
            parts = card_id_str.split('_')
            lookup_key = None
            card_data = None

            if len(parts) >= 2:
                # Try set_id-number format
                lookup_key = f"{parts[0]}-{parts[1]}"
                card_data = pokemon_lookup.get(lookup_key)

            if not card_data:
                # Try with more parts: "swsh11tg_TG03_Charizard" -> "swsh11tg-TG03"
                if len(parts) >= 2:
                    for i in range(1, min(3, len(parts))):
                        test_key = f"{parts[0]}-{'_'.join(parts[1:i+1])}"
                        card_data = pokemon_lookup.get(test_key)
                        if card_data:
                            lookup_key = test_key
                            break

            if card_data:
                cursor.execute("""
                    INSERT OR REPLACE INTO cards
                    (faiss_index, tcg, card_id, name, set_code, set_name,
                     collector_number, rarity, image_url, scryfall_id, oracle_id,
                     price_usd, card_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    faiss_idx, "pokemon", lookup_key,
                    card_data.get("name", ""),
                    card_data.get("set_id", ""),
                    card_data.get("set_name", ""),
                    card_data.get("number", ""),
                    card_data.get("rarity", ""),
                    card_data.get("image_large", ""),
                    "", "",  # No scryfall/oracle for pokemon
                    0,
                    json.dumps(card_data)
                ))
                poke_matched += 1
            else:
                # Insert unmatched with card_id_str as name
                name_part = parts[-1] if parts else card_id_str
                cursor.execute("""
                    INSERT OR REPLACE INTO cards
                    (faiss_index, tcg, card_id, name, set_code, set_name,
                     collector_number, rarity, image_url, scryfall_id, oracle_id,
                     price_usd, card_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (faiss_idx, "pokemon", card_id_str, name_part,
                      parts[0] if parts else "", "", parts[1] if len(parts) > 1 else "",
                      "", "", "", "", 0, ""))

            poke_inserted += 1

        conn.commit()
        total_inserted += poke_inserted
        print(f"[Bridge] Pokemon: {poke_inserted:,} entries, {poke_matched:,} matched to metadata")

    except Exception as e:
        print(f"[Bridge] Pokemon error: {e}")

    elapsed = time.time() - start

    # Final count
    cursor.execute("SELECT tcg, COUNT(*) FROM cards GROUP BY tcg")
    counts = dict(cursor.fetchall())

    print(f"\n{'='*50}")
    print("BRIDGE TABLE POPULATED")
    print(f"{'='*50}")
    for tcg, count in sorted(counts.items()):
        print(f"  {tcg}: {count:,}")
    print(f"  Total: {sum(counts.values()):,}")
    print(f"Time: {elapsed:.1f}s")
    print(f"{'='*50}")

    conn.close()


if __name__ == '__main__':
    populate()
