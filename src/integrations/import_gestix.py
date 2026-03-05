"""
Import Gestix Collection CSV into NEXUS Library
Properly catalogs 26,850 cards with UUID enrichment
"""
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================
# PORTABLE PATH CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / 'data'

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Add NEXUS modules to path (same directory)
sys.path.insert(0, str(BASE_DIR))

from nexus_library_system import NexusLibrarySystem


def load_master_cards():
    """Load master cards database for UUID enrichment"""
    print("Loading master cards database (106,804 cards)...")
    master_cards = {}
    master_cards_by_name = defaultdict(list)
    
    cards_file = DATA_DIR / "cards.csv"
    
    if not cards_file.exists():
        print(f"[WARNING] Master cards file not found: {cards_file}")
        print(f"[WARNING] UUID enrichment will be skipped")
        return master_cards, master_cards_by_name
    
    with open(cards_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            uuid = row.get('uuid', '')
            if uuid:
                master_cards[uuid] = row
                name = row.get('name', '')
                if name:
                    master_cards_by_name[name].append(uuid)
    
    print(f"[OK] Loaded {len(master_cards)} cards, {len(master_cards_by_name)} unique names")
    return master_cards, master_cards_by_name


def import_gestix_csv(gestix_file: str = None):
    """Import Gestix collection with proper enrichment"""
    
    # Initialize library system
    library = NexusLibrarySystem()
    
    # Load master cards for enrichment
    master_cards, master_cards_by_name = load_master_cards()
    
    # Default Gestix file location
    if gestix_file is None:
        gestix_file = str(DATA_DIR / "gestix_collection.csv")
    
    print(f"\nReading Gestix CSV: {gestix_file}")
    
    if not Path(gestix_file).exists():
        print(f"[ERROR] Gestix file not found: {gestix_file}")
        print(f"[INFO] Please place gestix_collection.csv in: {DATA_DIR}")
        return 0
    
    with open(gestix_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"[OK] Found {len(rows)} cards to import")
    
    # Gestix column mapping (note: headers have spaces after commas)
    column_map = {
        'name': ' Name',
        'count': 'Count',
        'scryfall_id': ' Scryfall ID',
        'set': ' Edition',
        'foil': ' Foil',
        'condition': ' Condition',
        'language': ' Language',
        'collector_number': ' Collector Number'
    }
    
    imported = 0
    errors = []
    
    print("\nImporting cards...")
    for idx, row in enumerate(rows, 1):
        try:
            # Extract Gestix data
            name = row.get(column_map['name'], '').strip()
            if not name:
                errors.append(f"Row {idx}: Missing name")
                continue
            
            # Debug first 3 cards
            if idx <= 3:
                print(f"\n  Row {idx}: {name}")
                print(f"    Count: {row.get(column_map['count'])}")
                print(f"    Set: {row.get(column_map['set'])}")
                print(f"    Scryfall ID: {row.get(column_map['scryfall_id'])}")
                
            count = int(row.get(column_map['count'], '1') or '1')
            scryfall_id = row.get(column_map['scryfall_id'], '').strip()
            set_code = row.get(column_map['set'], '').strip().upper()
            is_foil = row.get(column_map['foil'], '').lower() in ['foil', 'yes', 'true', '1']
            condition = row.get(column_map['condition'], 'NM').strip()
            language = row.get(column_map['language'], 'en').strip()
            collector_num = row.get(column_map['collector_number'], '').strip()
            
            # Build card data
            card_data = {
                'name': name,
                'set': set_code,
                'foil': is_foil,
                'condition': condition,
                'language': language,
                'collector_number': collector_num,
                'scryfall_id': scryfall_id,
                'uuid': scryfall_id  # Use Scryfall ID as UUID
            }
            
            # Enrich from master database if no Scryfall ID
            if not scryfall_id and name in master_cards_by_name:
                uuids = master_cards_by_name[name]
                if uuids:
                    master_data = master_cards[uuids[0]]
                    card_data['uuid'] = uuids[0]
                    card_data['scryfall_id'] = uuids[0]
                    card_data['colors'] = master_data.get('colors', '')
                    card_data['type'] = master_data.get('type', '')
                    card_data['rarity'] = master_data.get('rarity', '')
                    card_data['mana_cost'] = master_data.get('manaCost', '')
            
            # Catalog card(s)
            call_numbers = library.catalog_card(card_data, quantity=count)
            imported += len(call_numbers)
            
            if idx % 1000 == 0:
                print(f"  Progress: {idx}/{len(rows)} rows ({imported} cards cataloged)")
        
        except Exception as e:
            errors.append(f"Row {idx} ({name}): {e}")
            if len(errors) <= 10:  # Only show first 10 errors
                print(f"  [!!] Error on row {idx}: {e}")
    
    # Force final save of any remaining changes
    library.force_save()
    
    # Final report
    print("="*60)
    print("GESTIX IMPORT COMPLETE")
    print("="*60)
    print(f"[OK] Rows processed: {len(rows)}")
    print(f"[OK] Cards cataloged: {imported}")
    print(f"[OK] Total boxes: {len(library.library_data)}")
    print(f"[OK] Current box: {library.current_box}")
    print(f"[OK] Unique card names: {len(library.card_locations)}")
    print(f"[!!] Errors: {len(errors)}")
    print("="*60)
    
    if errors:
        print("\nFirst 10 errors:")
        for err in errors[:10]:
            print(f"  {err}")
    
    return imported


if __name__ == '__main__':
    try:
        # Allow passing custom file path as argument
        gestix_file = sys.argv[1] if len(sys.argv) > 1 else None
        imported = import_gestix_csv(gestix_file)
        print(f"\n[OK] SUCCESS! {imported} cards imported into NEXUS library")
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()

