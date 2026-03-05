#!/usr/bin/env python3
"""
NEXUS Inventory Backfill Script
================================
Fills empty columns in nexus_library.db using card_lookup.json from Scryfall.

The inventory has 26,850 cards with name + set_code + collector_number
but 15+ columns are empty (rarity, type_line, image_url, etc.).

This script:
1. Loads card_lookup.json (521K MTG cards keyed by Scryfall UUID)
2. Builds a set_code+collector_number index for fast matching
3. For each inventory card, finds the matching Scryfall data
4. Updates the empty columns in nexus_library.db

Run on ZULTAN:
    python3 backfill_inventory.py
    python3 backfill_inventory.py --dry-run    # Preview without writing
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Paths on ZULTAN
CARD_LOOKUP_PATH = os.path.expanduser("~/training/metadata/card_lookup.json")
INVENTORY_DB_PATH = os.path.expanduser("~/training/data/nexus_library.db")

# card_lookup.json uses compact keys:
#   n=name, s=set_code, cn=collector_number, sn=set_name,
#   r=rarity, o=oracle_id, p=price_usd


def build_set_cn_index(card_lookup):
    """Build an index: (set_code, collector_number) -> scryfall_id + data"""
    index = {}
    for scryfall_id, card in card_lookup.items():
        set_code = card.get("s", "").upper()
        cn = card.get("cn", "").strip()
        if set_code and cn:
            key = (set_code, cn)
            if key not in index:
                index[key] = (scryfall_id, card)
    return index


def build_name_set_index(card_lookup):
    """Fallback index: (name_lower, set_code) -> scryfall_id + data"""
    index = {}
    for scryfall_id, card in card_lookup.items():
        name = card.get("n", "").lower()
        set_code = card.get("s", "").upper()
        if name and set_code:
            key = (name, set_code)
            if key not in index:
                index[key] = (scryfall_id, card)
    return index


def backfill(dry_run=False):
    start = time.time()

    print(f"[Backfill] Loading card_lookup.json from {CARD_LOOKUP_PATH}...")
    with open(CARD_LOOKUP_PATH, "r") as f:
        card_lookup = json.load(f)
    print(f"[Backfill] Loaded {len(card_lookup):,} cards")

    print("[Backfill] Building indexes...")
    set_cn_index = build_set_cn_index(card_lookup)
    name_set_index = build_name_set_index(card_lookup)
    print(f"[Backfill] Indexes: {len(set_cn_index):,} set+cn, {len(name_set_index):,} name+set")

    print(f"[Backfill] Opening inventory DB: {INVENTORY_DB_PATH}")
    conn = sqlite3.connect(INVENTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cards")
    total = cursor.fetchone()[0]
    print(f"[Backfill] Inventory has {total:,} cards")

    # Fetch all inventory cards
    cursor.execute("SELECT rowid, * FROM cards")
    rows = cursor.fetchall()

    matched = 0
    updated = 0
    no_match = 0
    already_filled = 0

    for i, row in enumerate(rows):
        row_dict = dict(row)
        rowid = row_dict['rowid']
        name = row_dict.get('name', '')
        set_code = row_dict.get('set_code', '').upper()
        cn = row_dict.get('collector_number', '').strip()

        # Try set_code + collector_number match first
        match = None
        key = (set_code, cn)
        if key in set_cn_index:
            match = set_cn_index[key]
        else:
            # Fallback: name + set_code
            key2 = (name.lower(), set_code)
            if key2 in name_set_index:
                match = name_set_index[key2]

        if not match:
            no_match += 1
            continue

        scryfall_id, card_data = match
        matched += 1

        # Build the full card data JSON
        full_data = json.dumps({
            "scryfall_id": scryfall_id,
            "oracle_id": card_data.get("o", ""),
            "name": card_data.get("n", ""),
            "set_code": card_data.get("s", ""),
            "set_name": card_data.get("sn", ""),
            "collector_number": card_data.get("cn", ""),
            "rarity": card_data.get("r", ""),
            "price_usd": card_data.get("p", 0),
        })

        # Check if this card needs updating (has empty columns)
        needs_update = (
            not row_dict.get('set_name') or
            not row_dict.get('rarity') or
            not row_dict.get('scryfall_id') or
            not row_dict.get('image_url')
        )

        if not needs_update:
            already_filled += 1
            continue

        # Build the image URL
        image_url = f"https://api.scryfall.com/cards/{scryfall_id}?format=image&version=normal"
        image_url_small = f"https://api.scryfall.com/cards/{scryfall_id}?format=image&version=small"

        if not dry_run:
            cursor.execute("""
                UPDATE cards SET
                    set_name = COALESCE(NULLIF(set_name, ''), ?),
                    rarity = COALESCE(NULLIF(rarity, ''), ?),
                    scryfall_id = COALESCE(NULLIF(scryfall_id, ''), ?),
                    image_url = COALESCE(NULLIF(image_url, ''), ?),
                    image_url_small = COALESCE(NULLIF(image_url_small, ''), ?),
                    price = COALESCE(NULLIF(price, ''), NULLIF(price, 0), ?),
                    price_source = COALESCE(NULLIF(price_source, ''), 'scryfall')
                WHERE rowid = ?
            """, (
                card_data.get("sn", ""),
                card_data.get("r", ""),
                scryfall_id,
                image_url,
                image_url_small,
                card_data.get("p", 0),
                rowid
            ))
            updated += 1

        if (i + 1) % 5000 == 0:
            if not dry_run:
                conn.commit()
            print(f"[Backfill] Progress: {i+1}/{total} ({matched} matched, {updated} updated, {no_match} no match)")

    if not dry_run:
        conn.commit()

    elapsed = time.time() - start

    print(f"\n{'='*50}")
    print(f"BACKFILL {'DRY RUN ' if dry_run else ''}COMPLETE")
    print(f"{'='*50}")
    print(f"Total inventory cards: {total:,}")
    print(f"Matched to Scryfall:   {matched:,} ({100*matched/total:.1f}%)")
    print(f"Updated:               {updated:,}")
    print(f"Already filled:        {already_filled:,}")
    print(f"No match found:        {no_match:,}")
    print(f"Time: {elapsed:.1f}s")
    print(f"{'='*50}")

    conn.close()


def main():
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("[Backfill] DRY RUN MODE - no changes will be written")
    backfill(dry_run=dry_run)


if __name__ == '__main__':
    main()
