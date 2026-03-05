"""
NEXUS Cloud Sync Module
Synchronizes collections across multiple scanner stations
Handles conflict resolution and maintains central database
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
import hashlib


class CloudSyncManager:
    """Manages collection synchronization across network"""
    
    def __init__(self, db_path='nexus_cloud_sync.db'):
        self.db_path = Path(db_path)
        self.init_database()
    
    def init_database(self):
        """Initialize cloud sync database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Scanner registry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scanners (
                scanner_id TEXT PRIMARY KEY,
                location TEXT,
                last_seen TIMESTAMP,
                total_scans INTEGER DEFAULT 0
            )
        ''')
        
        # Unified collection
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection (
                card_id TEXT PRIMARY KEY,
                name TEXT,
                set_code TEXT,
                collector_number TEXT,
                quantity INTEGER DEFAULT 1,
                first_scanned TIMESTAMP,
                last_updated TIMESTAMP,
                scanner_id TEXT,
                FOREIGN KEY (scanner_id) REFERENCES scanners(scanner_id)
            )
        ''')
        
        # Sync log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP,
                scanner_id TEXT,
                action TEXT,
                card_id TEXT,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def register_scanner(self, scanner_id, location):
        """Register a scanner station"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO scanners (scanner_id, location, last_seen)
            VALUES (?, ?, ?)
        ''', (scanner_id, location, datetime.now()))
        
        conn.commit()
        conn.close()
        
        print(f"[SYNC] Registered scanner: {scanner_id} at {location}")
    
    def sync_card(self, scanner_id, card_data):
        """Sync a single card from scanner"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Generate unique card ID
        card_id = self.generate_card_id(
            card_data['name'],
            card_data['set'],
            card_data.get('collector_number', '')
        )
        
        # Check if card exists
        cursor.execute(
            'SELECT quantity FROM collection WHERE card_id = ?',
            (card_id,)
        )
        result = cursor.fetchone()
        
        if result:
            # Update quantity
            new_qty = result[0] + 1
            cursor.execute('''
                UPDATE collection
                SET quantity = ?, last_updated = ?, scanner_id = ?
                WHERE card_id = ?
            ''', (new_qty, datetime.now(), scanner_id, card_id))
            
            action = 'increment'
        else:
            # Add new card
            cursor.execute('''
                INSERT INTO collection
                (card_id, name, set_code, collector_number, quantity,
                 first_scanned, last_updated, scanner_id)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            ''', (
                card_id,
                card_data['name'],
                card_data['set'],
                card_data.get('collector_number', ''),
                datetime.now(),
                datetime.now(),
                scanner_id
            ))
            
            action = 'add'
        
        # Log sync action
        cursor.execute('''
            INSERT INTO sync_log (timestamp, scanner_id, action, card_id)
            VALUES (?, ?, ?, ?)
        ''', (datetime.now(), scanner_id, action, card_id))
        
        # Update scanner stats
        cursor.execute('''
            UPDATE scanners
            SET total_scans = total_scans + 1, last_seen = ?
            WHERE scanner_id = ?
        ''', (datetime.now(), scanner_id))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'card_id': card_id,
            'action': action
        }
    
    def generate_card_id(self, name, set_code, collector_number):
        """Generate unique card identifier"""
        identifier = f"{name}|{set_code}|{collector_number}"
        return hashlib.md5(identifier.encode()).hexdigest()[:16]
    
    def get_collection_stats(self):
        """Get overall collection statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*), SUM(quantity) FROM collection')
        unique, total = cursor.fetchone()
        
        cursor.execute('SELECT COUNT(*) FROM scanners')
        scanner_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'unique_cards': unique or 0,
            'total_cards': total or 0,
            'active_scanners': scanner_count,
            'last_updated': datetime.now().isoformat()
        }
    
    def get_scanner_stats(self, scanner_id):
        """Get stats for specific scanner"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT location, last_seen, total_scans
            FROM scanners WHERE scanner_id = ?
        ''', (scanner_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'scanner_id': scanner_id,
                'location': result[0],
                'last_seen': result[1],
                'total_scans': result[2]
            }
        return None
    
    def export_collection(self, format='json'):
        """Export entire collection"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT card_id, name, set_code, collector_number,
                   quantity, first_scanned, last_updated, scanner_id
            FROM collection
            ORDER BY name
        ''')
        
        columns = [
            'card_id', 'name', 'set_code', 'collector_number',
            'quantity', 'first_scanned', 'last_updated', 'scanner_id'
        ]
        
        cards = []
        for row in cursor.fetchall():
            card = dict(zip(columns, row))
            cards.append(card)
        
        conn.close()
        
        if format == 'json':
            return json.dumps(cards, indent=2)
        elif format == 'csv':
            # TODO: Implement CSV export
            pass
        
        return cards
    
    def resolve_conflicts(self):
        """
        Handle synchronization conflicts
        (e.g., same card scanned at multiple stations simultaneously)
        """
        # TODO: Implement conflict resolution logic
        pass
    
    def broadcast_update(self, card_data):
        """
        Broadcast card update to all connected scanners
        (For real-time sync in multi-scanner setup)
        """
        # TODO: Implement WebSocket or similar for real-time updates
        pass


# Example usage
if __name__ == '__main__':
    sync = CloudSyncManager()
    
    # Register scanner
    sync.register_scanner('scanner_001', 'Shop Counter')
    
    # Sync a card
    card = {
        'name': 'Black Lotus',
        'set': 'LEA',
        'collector_number': '232'
    }
    result = sync.sync_card('scanner_001', card)
    print(result)
    
    # Get stats
    stats = sync.get_collection_stats()
    print(json.dumps(stats, indent=2))
