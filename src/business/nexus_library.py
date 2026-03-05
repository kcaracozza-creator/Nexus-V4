#!/usr/bin/env python3
"""
Nexus Library System - Dewey Decimal Style Organization
Box-based cataloging: 1 box = 1000 cards maximum
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict

# ============================================
# PORTABLE PATH CONFIGURATION  
# ============================================
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / 'data'

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)


class NexusLibrarySystem:
    """
    ZERO-SORT Library System
    
    Philosophy: NO HUMAN SORTING REQUIRED
    - Load scanner with random cards -> Scan -> Box fills sequentially
    - Box AA: Positions 1-1000 (whatever order cards came in)
    - Box AB: Positions 1-1000 (whatever order cards came in)
    - Computer searches/sorts digitally - humans just load/unload
    
    Structure:
    - Box ID: AA, AB, AC... ZZ (676 boxes = 676,000 cards)
    - Position: 1-1000 (sequential scan order)
    - Call Number: AA-0234 (Box AA, Position 234)
    
    NO COLOR/TYPE SORTING - Just scan in whatever order they come!
    """
    
    CARDS_PER_BOX = 1000
    
    def __init__(self, library_file: str = None):
        """
        Initialize zero-sort library system
        
        Args:
            library_file: Path to library database JSON (default: data/nexus_library.json)
        """
        if library_file is None:
            library_file = str(DATA_DIR / "nexus_library.json")
        
        self.library_file = library_file
        self.library_data = {}
        self.box_inventory = defaultdict(list)  # box_id -> [cards in scan order]
        self.card_locations = {}  # card_name -> call_number
        self.current_box = None  # Currently active box for scanning
        self._unsaved_changes = 0  # Batch save counter
        
        self._load_library()
        print(f"[LIBRARY] Nexus Zero-Sort Library System initialized")
        print(f"[LIBRARY] Total boxes: {len(self.box_inventory)}")
        print(f"[LIBRARY] Total cards cataloged: {len(self.card_locations)}")
        print(f"[LIBRARY] Philosophy: SCAN IN ANY ORDER - NO SORTING NEEDED!")
    
    def _load_library(self):
        """Load library database from JSON"""
        if os.path.exists(self.library_file):
            try:
                with open(self.library_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.library_data = data.get('library', {})
                    self.card_locations = data.get('card_locations', {})
                    
                    # Rebuild box inventory from library data
                    for call_number, card_data in self.library_data.items():
                        box_id = call_number.split('-')[0]
                        # Store full card dict, not just call number
                        card_with_callnum = dict(card_data)
                        card_with_callnum['call_number'] = call_number
                        self.box_inventory[box_id].append(card_with_callnum)
                    
                    # Find current box (last box with space)
                    if self.box_inventory:
                        for box_id in sorted(self.box_inventory.keys(), reverse=True):
                            if len(self.box_inventory[box_id]) < self.CARDS_PER_BOX:
                                self.current_box = box_id
                                break
                        else:
                            # All boxes full, need new one
                            self.current_box = self._get_next_box_id(sorted(self.box_inventory.keys())[-1])
                    
                    print(f"[LIBRARY] Loaded {len(self.library_data)} cards from {self.library_file}")
                    if self.current_box:
                        print(f"[LIBRARY] Current active box: {self.current_box} ({len(self.box_inventory.get(self.current_box, []))}/{self.CARDS_PER_BOX})")
            except Exception as e:
                print(f"[LIBRARY] Error loading library: {e}")
                self._initialize_new_library()
        else:
            self._initialize_new_library()
    
    def _initialize_new_library(self):
        """Initialize a fresh library"""
        self.library_data = {}
        self.box_inventory = defaultdict(list)
        self.card_locations = {}
        self.current_box = "AA"
        print(f"[LIBRARY] Initialized new library, starting with Box AA")
    
    def _get_next_box_id(self, current_box: str) -> str:
        """Get next box ID in sequence (AA -> AB -> ... -> AZ -> BA -> ...)"""
        first = current_box[0]
        second = current_box[1]
        
        if second == 'Z':
            # Move to next letter
            if first == 'Z':
                raise Exception("Maximum capacity reached (ZZ = 676,000 cards)")
            return chr(ord(first) + 1) + 'A'
        else:
            return first + chr(ord(second) + 1)
    
    def _get_next_position(self, box_id: str) -> int:
        """Get next available position in box"""
        return len(self.box_inventory[box_id]) + 1
    
    def catalog_card(self, card_data: dict, quantity: int = 1) -> List[str]:
        """
        Catalog a card into the library
        
        Args:
            card_data: Dictionary with card information
            quantity: Number of copies to catalog
            
        Returns:
            List of assigned call numbers
        """
        call_numbers = []
        
        for _ in range(quantity):
            # Check if current box is full
            if self.current_box is None:
                self.current_box = "AA"
            
            if len(self.box_inventory[self.current_box]) >= self.CARDS_PER_BOX:
                self.current_box = self._get_next_box_id(self.current_box)
                print(f"[LIBRARY] Box full, moving to {self.current_box}")
            
            # Get next position
            position = self._get_next_position(self.current_box)
            call_number = f"{self.current_box}-{position:04d}"
            
            # Store card data
            self.library_data[call_number] = {
                'call_number': call_number,
                'box_id': self.current_box,
                'position': position,
                'cataloged_at': datetime.now().isoformat(),
                **card_data
            }
            
            # Update indexes
            self.box_inventory[self.current_box].append(call_number)
            card_name = card_data.get('name', 'Unknown')
            if card_name not in self.card_locations:
                self.card_locations[card_name] = []
            if isinstance(self.card_locations[card_name], str):
                self.card_locations[card_name] = [self.card_locations[card_name]]
            self.card_locations[card_name].append(call_number)
            
            call_numbers.append(call_number)
        
        # Batch save: only save every 100 cards or when crossing box boundary
        self._unsaved_changes += len(call_numbers)
        if self._unsaved_changes >= 100 or len(self.box_inventory[self.current_box]) == 1:
            self._save_library()
            self._unsaved_changes = 0
        
        return call_numbers
    
    def _save_library(self):
        """Save library to JSON file"""
        try:
            data = {
                'library': self.library_data,
                'card_locations': self.card_locations,
                'metadata': {
                    'total_cards': len(self.library_data),
                    'total_boxes': len(self.box_inventory),
                    'current_box': self.current_box,
                    'last_updated': datetime.now().isoformat()
                }
            }
            with open(self.library_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)  # No indent - faster, smaller file
        except Exception as e:
            print(f"[LIBRARY] Error saving: {e}")
    
    def force_save(self):
        """Force save any unsaved changes"""
        if self._unsaved_changes > 0:
            self._save_library()
            self._unsaved_changes = 0
            print(f"[LIBRARY] Final save complete")
    
    def find_card(self, card_name: str) -> List[dict]:
        """Find all copies of a card by name"""
        results = []
        locations = self.card_locations.get(card_name, [])
        
        if isinstance(locations, str):
            locations = [locations]
        
        for call_number in locations:
            if call_number in self.library_data:
                results.append(self.library_data[call_number])
        
        return results
    
    def get_box_contents(self, box_id: str) -> List[dict]:
        """Get all cards in a specific box"""
        contents = []
        for call_number in self.box_inventory.get(box_id, []):
            if call_number in self.library_data:
                contents.append(self.library_data[call_number])
        return contents
    
    def get_statistics(self) -> dict:
        """Get library statistics"""
        return {
            'total_cards': len(self.library_data),
            'total_boxes': len(self.box_inventory),
            'unique_card_names': len(self.card_locations),
            'current_box': self.current_box,
            'current_box_count': len(self.box_inventory.get(self.current_box, [])),
            'capacity_per_box': self.CARDS_PER_BOX
        }
    
    def search(self, query: str, field: str = 'name') -> List[dict]:
        """Search library by field"""
        results = []
        query_lower = query.lower()
        
        for call_number, card_data in self.library_data.items():
            value = str(card_data.get(field, '')).lower()
            if query_lower in value:
                results.append(card_data)
        
        return results
    
    def remove_card(self, call_number: str) -> bool:
        """Remove a card from the library"""
        if call_number not in self.library_data:
            return False
        
        card_data = self.library_data[call_number]
        card_name = card_data.get('name', '')
        box_id = call_number.split('-')[0]
        
        # Remove from library
        del self.library_data[call_number]
        
        # Remove from box inventory
        if call_number in self.box_inventory[box_id]:
            self.box_inventory[box_id].remove(call_number)
        
        # Remove from card locations
        if card_name in self.card_locations:
            locations = self.card_locations[card_name]
            if isinstance(locations, list):
                if call_number in locations:
                    locations.remove(call_number)
                if not locations:
                    del self.card_locations[card_name]
            elif locations == call_number:
                del self.card_locations[card_name]
        
        self._save_library()
        return True
    
    def generate_box_labels(self, output_file: str = None):
        """Generate printable box labels"""
        if output_file is None:
            output_file = str(DATA_DIR / "box_labels.txt")
        
        with open(output_file, 'w') as f:
            for box_id in sorted(self.box_inventory.keys()):
                count = len(self.box_inventory[box_id])
                f.write(f"{'='*40}\n")
                f.write(f"BOX: {box_id}\n")
                f.write(f"Cards: {count}/{self.CARDS_PER_BOX}\n")
                f.write(f"{'='*40}\n\n")
        
        print(f"[LIBRARY] Box labels saved to {output_file}")
        return output_file


# For testing
if __name__ == '__main__':
    library = NexusLibrarySystem()
    print("\nLibrary Statistics:")
    stats = library.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
