"""
NEXUS Library Import Script
===========================
Imports cards from nexus_library.json into the marketplace database
Run this after starting the server to seed listings
"""

import json
import sqlite3
import uuid
from pathlib import Path

def import_library(library_path: str, seller_id: str = None):
    """Import cards from NEXUS library JSON"""
    
    # Load library
    with open(library_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    box_inventory = data.get('box_inventory', {})
    
    # Connect to marketplace DB
    db_path = Path(__file__).parent / 'marketplace.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Create default seller if needed
    if not seller_id:
        seller_id = 'default-seller-001'
        cur.execute('''
            INSERT OR IGNORE INTO sellers (id, user_id, shop_name, verified)
            VALUES (?, ?, ?, ?)
        ''', (seller_id, 'system', 'NEXUS Demo Shop', 1))
    
    # Import cards
    imported = 0
    skipped = 0
    
    for box_name, cards in box_inventory.items():
        for card in cards:
            if not isinstance(card, dict):
                skipped += 1
                continue
            
            name = card.get('name')
            if not name:
                skipped += 1
                continue
            
            # Get price (default to 0.25 if no price)
            price = card.get('price') or card.get('prices', {}).get('usd') or 0.25
            try:
                price = float(price)
            except:
                price = 0.25
            
            # Get image URL
            image_url = card.get('image_url')
            if not image_url:
                image_uris = card.get('image_uris', {})
                image_url = image_uris.get('normal') or image_uris.get('small')
            
            listing_id = str(uuid.uuid4())
            
            try:
                cur.execute('''
                    INSERT INTO listings (
                        id, seller_id, card_name, set_code, set_name, collector_number,
                        rarity, condition, price, quantity, image_url, scryfall_id, foil
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    listing_id,
                    seller_id,
                    name,
                    card.get('set_code') or card.get('set'),
                    card.get('set_name'),
                    card.get('collector_number'),
                    card.get('rarity', 'common'),
                    card.get('condition', 'NM'),
                    price,
                    card.get('quantity', 1),
                    image_url,
                    card.get('scryfall_id'),
                    1 if card.get('foil') else 0
                ))
                imported += 1
            except Exception as e:
                print(f"Error importing {name}: {e}")
                skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ Import complete!")
    print(f"   Imported: {imported} cards")
    print(f"   Skipped: {skipped} cards")
    return imported

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python import_library.py <path_to_nexus_library.json>")
        print("Example: python import_library.py ../data/nexus_library.json")
        sys.exit(1)
    
    library_path = sys.argv[1]
    
    if not Path(library_path).exists():
        print(f"Error: File not found: {library_path}")
        sys.exit(1)
    
    import_library(library_path)
