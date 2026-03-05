"""
Import existing inventory CSVs into NEXUS database
Handles multiple CSV files from E:\MTTGG\Inventory folder
"""

import csv
import sqlite3
import os
from datetime import datetime
from pathlib import Path


def create_nexus_database(db_path="nexus_inventory.db"):
    """Create NEXUS inventory database if it doesn't exist"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Main inventory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT NOT NULL,
            set_name TEXT,
            set_code TEXT,
            rarity TEXT,
            condition TEXT,
            language TEXT DEFAULT 'en',
            foil BOOLEAN DEFAULT 0,
            quantity INTEGER DEFAULT 1,
            cost_basis REAL DEFAULT 0,
            current_price REAL DEFAULT 0,
            box_id TEXT,
            card_number INTEGER,
            scryfall_id TEXT,
            collector_number TEXT,
            scan_date TEXT,
            last_updated TEXT,
            days_in_inventory INTEGER DEFAULT 0,
            image_path TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_card_name ON inventory(card_name)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_set_code ON inventory(set_code)
    """)
    
    conn.commit()
    return conn


def parse_csv_row(row, set_code="UNKNOWN"):
    """Parse a row from CSV and return normalized data"""
    
    # Handle both column name formats
    name = row.get('Name', row.get(' Name', '')).strip()
    count = int(row.get('Count', row.get(' Count', 1)))
    edition = row.get('Edition', row.get(' Edition', set_code)).strip()
    condition = row.get('Condition', row.get(' Condition', 'NM')).strip()
    language = row.get('Language', row.get(' Language', 'en')).strip()
    foil_str = row.get('Foil', row.get(' Foil', '')).strip()
    scryfall_id = row.get('Scryfall ID', row.get(' Scryfall ID', '')).strip()
    collector_num = row.get('Collector Number', row.get(' Collector Number', '')).strip()
    
    # Parse foil status
    is_foil = 1 if foil_str.lower() in ['foil', 'etched', 'true', '1'] else 0
    
    return {
        'name': name,
        'count': count,
        'edition': edition,
        'condition': condition,
        'language': language,
        'foil': is_foil,
        'scryfall_id': scryfall_id,
        'collector_number': collector_num
    }


def import_csv_file(conn, csv_path, set_code=None):
    """Import a single CSV file into the database"""
    
    if set_code is None:
        # Try to extract set code from filename
        filename = Path(csv_path).stem
        set_code = filename.split('_')[0].split(' ')[0]
    
    cursor = conn.cursor()
    cards_imported = 0
    total_quantity = 0
    
    print(f"\nImporting {csv_path}...")
    print(f"Set Code: {set_code}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                card_data = parse_csv_row(row, set_code)
                
                if not card_data['name']:
                    continue
                
                # Import each copy individually (for location tracking)
                for i in range(card_data['count']):
                    cursor.execute("""
                        INSERT INTO inventory 
                        (card_name, set_name, set_code, condition, language, foil,
                         scryfall_id, collector_number, scan_date, last_updated,
                         box_id, card_number, days_in_inventory)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        card_data['name'],
                        card_data['edition'].upper(),
                        set_code.upper(),
                        card_data['condition'],
                        card_data['language'],
                        card_data['foil'],
                        card_data['scryfall_id'],
                        card_data['collector_number'],
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                        f"SET-{set_code.upper()}",  # Temporary box assignment
                        cards_imported + i + 1,
                        0  # Will calculate days later
                    ))
                
                cards_imported += 1
                total_quantity += card_data['count']
                
            except Exception as e:
                print(f"Error importing row: {row}")
                print(f"Error: {e}")
                continue
    
    conn.commit()
    print(f"✅ Imported {cards_imported} unique cards ({total_quantity} total copies)")
    return cards_imported, total_quantity


def import_all_inventory_csvs(inventory_folder="E:\\MTTGG\\Inventory", db_path="nexus_inventory.db"):
    """Import all CSV files from inventory folder"""
    
    conn = create_nexus_database(db_path)
    
    csv_files = [f for f in os.listdir(inventory_folder) if f.endswith('.csv')]
    
    print(f"Found {len(csv_files)} CSV files to import")
    print("=" * 60)
    
    total_unique = 0
    total_copies = 0
    
    for csv_file in csv_files:
        csv_path = os.path.join(inventory_folder, csv_file)
        unique, copies = import_csv_file(conn, csv_path)
        total_unique += unique
        total_copies += copies
    
    print("\n" + "=" * 60)
    print(f"IMPORT COMPLETE")
    print(f"Total unique cards: {total_unique}")
    print(f"Total card copies: {total_copies}")
    print(f"Database: {db_path}")
    print("=" * 60)
    
    # Generate summary statistics
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM inventory")
    total_cards = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT card_name) FROM inventory")
    unique_names = cursor.fetchone()[0]
    
    cursor.execute("SELECT set_code, COUNT(*) FROM inventory GROUP BY set_code")
    set_breakdown = cursor.fetchall()
    
    print(f"\nDatabase Statistics:")
    print(f"Total cards in database: {total_cards}")
    print(f"Unique card names: {unique_names}")
    print(f"\nBreakdown by set:")
    for set_code, count in set_breakdown:
        print(f"  {set_code}: {count} cards")
    
    conn.close()
    
    return total_cards


def quick_search_demo(db_path="nexus_inventory.db", search_term="Lightning Bolt"):
    """Demo the search functionality"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n" + "=" * 60)
    print(f"DEMO: Searching for '{search_term}'")
    print("=" * 60)
    
    cursor.execute("""
        SELECT card_name, set_code, condition, foil, box_id, card_number
        FROM inventory
        WHERE card_name LIKE ?
        LIMIT 10
    """, (f"%{search_term}%",))
    
    results = cursor.fetchall()
    
    if results:
        print(f"Found {len(results)} results:\n")
        for card_name, set_code, condition, foil, box_id, card_num in results:
            foil_str = " (FOIL)" if foil else ""
            print(f"  {card_name} [{set_code}] - {condition}{foil_str}")
            print(f"    Location: Box {box_id}, Card #{card_num}")
            print()
    else:
        print("No results found")
    
    conn.close()


if __name__ == "__main__":
    print("NEXUS INVENTORY CSV IMPORTER")
    print("=" * 60)
    
    # Import all CSVs
    total = import_all_inventory_csvs()
    
    # Demo search functionality
    if total > 0:
        quick_search_demo(search_term="Ajani")
        quick_search_demo(search_term="Turtle")
