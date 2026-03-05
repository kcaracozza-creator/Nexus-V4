#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestix-Style Inventory Display
Replicates Gestix.org's card grouping and version display
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List
from collections import defaultdict


class GestixStyleInventory:
    """
    Inventory view that mirrors Gestix.org:
    - Groups cards by name
    - Shows all versions/printings as expandable sub-rows
    - Displays mana symbols, set icons, foil indicators
    - Shows quantities and prices per version
    """
    
    def __init__(self, parent, master_cards: Dict, library_system):
        self.parent = parent
        self.master_cards = master_cards
        self.library_system = library_system
        self.expanded_cards = set()  # Track which cards are expanded
        
        # Mana symbol mapping (Unicode)
        self.mana_symbols = {
            'W': '⚪',  # White
            'U': '🔵',  # Blue
            'B': '⚫',  # Black
            'R': '🔴',  # Red
            'G': '🟢',  # Green
            'C': '◇',   # Colorless
            'X': 'X',
            'T': '⟳',   # Tap
            'Q': '⟲',   # Untap
        }
    
    def create_treeview(self):
        """Create Gestix-style treeview with expandable rows"""
        # Columns: Card Name | Mana Cost | Versions | Total Qty | Total Value
        columns = ('name', 'mana', 'versions', 'qty', 'value')
        
        tree = ttk.Treeview(self.parent, columns=columns, show='tree headings', height=25)
        
        # Column headers
        tree.heading('name', text='Card Name', command=lambda: self.sort_by('name'))
        tree.heading('mana', text='Mana Cost')
        tree.heading('versions', text='Versions', command=lambda: self.sort_by('versions'))
        tree.heading('qty', text='Qty', command=lambda: self.sort_by('qty'))
        tree.heading('value', text='Value', command=lambda: self.sort_by('value'))
        
        # Column widths
        tree.column('#0', width=30, stretch=False)  # Expand icon
        tree.column('name', width=300)
        tree.column('mana', width=120)
        tree.column('versions', width=250)
        tree.column('qty', width=80)
        tree.column('value', width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Expand/collapse on click
        tree.bind('<Button-1>', self.on_tree_click)
        
        return tree
    
    def populate_inventory(self, tree):
        """Populate with Gestix-style grouped cards"""
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)
        
        # Group cards by name (not UUID)
        card_groups = defaultdict(lambda: {
            'versions': [],  # List of {set, uuid, qty, foil, price, locations}
            'total_qty': 0,
            'total_value': 0.0,
            'mana_cost': '',
            'colors': ''
        })
        
        # Build groups from library
        for box_id, cards in self.library_system.box_inventory.items():
            for card in cards:
                if not isinstance(card, dict):
                    continue
                
                name = card.get('name', 'Unknown')
                uuid = card.get('uuid') or card.get('scryfall_id', '')
                set_code = card.get('set', '???')
                call_num = card.get('call_number', '---')
                is_foil = card.get('foil', False)
                
                # Get master data for mana cost
                if uuid and uuid in self.master_cards:
                    master = self.master_cards[uuid]
                    if not card_groups[name]['mana_cost']:
                        card_groups[name]['mana_cost'] = master.get('manaCost', '')
                        card_groups[name]['colors'] = master.get('colors', '')
                
                # Find or create version entry
                version_key = (set_code, uuid, is_foil)
                version_found = False
                
                for version in card_groups[name]['versions']:
                    if (version['set'], version['uuid'], version['foil']) == version_key:
                        version['qty'] += 1
                        version['locations'].append(call_num)
                        version_found = True
                        break
                
                if not version_found:
                    card_groups[name]['versions'].append({
                        'set': set_code,
                        'uuid': uuid,
                        'qty': 1,
                        'foil': is_foil,
                        'price': 0.0,  # TODO: Price lookup
                        'locations': [call_num]
                    })
                
                card_groups[name]['total_qty'] += 1
        
        # Sort by card name
        sorted_cards = sorted(card_groups.items(), key=lambda x: x[0])
        
        # Insert into tree
        for card_name, data in sorted_cards:
            # Format mana cost with symbols
            mana_display = self._format_mana_cost(data['mana_cost'])
            
            # Versions summary (collapsed view)
            num_versions = len(data['versions'])
            version_summary = f"{num_versions} version{'s' if num_versions != 1 else ''}"
            
            # Parent row (card name)
            parent_id = tree.insert('', 'end', 
                                   values=(card_name, mana_display, version_summary, 
                                          data['total_qty'], f"${data['total_value']:.2f}"),
                                   tags=('parent',))
            
            # Child rows (versions) - hidden until expanded
            for version in sorted(data['versions'], key=lambda v: v['set']):
                set_icon = f"[{version['set'].upper()}]"
                foil_indicator = " ⭐" if version['foil'] else ""
                locations = f"{version['locations'][0]}...{version['locations'][-1]}" if len(version['locations']) > 1 else version['locations'][0]
                
                tree.insert(parent_id, 'end',
                           values=('', '', f"{set_icon}{foil_indicator} - {locations}",
                                  version['qty'], f"${version['price']:.2f}"),
                           tags=('child',))
            
            # Start collapsed
            tree.item(parent_id, open=False)
        
        # Style tags
        tree.tag_configure('parent', background='#2e2e2e', foreground='#e8dcc4', font=('Arial', 10, 'bold'))
        tree.tag_configure('child', background='#1a1a1a', foreground='#aaaaaa', font=('Arial', 9))
    
    def _format_mana_cost(self, mana_cost: str) -> str:
        """Convert {W}{U} to ⚪🔵"""
        if not mana_cost:
            return ''
        
        result = mana_cost
        for symbol, icon in self.mana_symbols.items():
            result = result.replace(f'{{{symbol}}}', icon)
        
        # Handle generic mana {1}, {2}, etc.
        import re
        result = re.sub(r'\{(\d+)\}', r'(\1)', result)
        
        return result
    
    def on_tree_click(self, event):
        """Handle expand/collapse on row click"""
        tree = event.widget
        region = tree.identify_region(event.x, event.y)
        
        if region == 'tree':
            item = tree.identify_row(event.y)
            if item:
                # Toggle expand/collapse
                current_state = tree.item(item, 'open')
                tree.item(item, open=not current_state)
    
    def sort_by(self, column):
        """Sort tree by column"""
        # TODO: Implement sorting
        pass


def demo():
    """Demo Gestix-style inventory"""
    root = tk.Tk()
    root.title("Gestix-Style Inventory Demo")
    root.geometry("1000x600")
    root.configure(bg='#0d0d0d')
    
    frame = tk.Frame(root, bg='#0d0d0d')
    frame.pack(fill='both', expand=True, padx=10, pady=10)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    
    # Mock data
    mock_master_cards = {
        'uuid1': {'manaCost': '{2}{U}{U}', 'colors': ['U']},
        'uuid2': {'manaCost': '{1}{R}', 'colors': ['R']},
    }
    
    class MockLibrary:
        box_inventory = {
            'AA': [
                {'name': 'Counterspell', 'uuid': 'uuid1', 'set': 'IMA', 'foil': False, 'call_number': 'AA-0001'},
                {'name': 'Counterspell', 'uuid': 'uuid1', 'set': 'IMA', 'foil': False, 'call_number': 'AA-0002'},
                {'name': 'Counterspell', 'uuid': 'uuid1', 'set': '7ED', 'foil': True, 'call_number': 'AA-0003'},
                {'name': 'Lightning Bolt', 'uuid': 'uuid2', 'set': 'M11', 'foil': False, 'call_number': 'AA-0004'},
            ]
        }
    
    inventory = GestixStyleInventory(frame, mock_master_cards, MockLibrary())
    tree = inventory.create_treeview()
    inventory.populate_inventory(tree)
    
    root.mainloop()


if __name__ == '__main__':
    demo()
