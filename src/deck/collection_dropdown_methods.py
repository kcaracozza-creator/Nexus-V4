"""
Collection Manager Dropdown Methods (Themed)
Add these to the NEXUS/MTTGGCompleteSystem class in nexus.py
Insert before the run() method (around line 11215)
"""

def create_collection_dropdowns(self, parent_frame):
    """
    Create all filter dropdowns for Collection Manager (THEMED VERSION)
    """
    from nexus_theme import NexusTheme, create_themed_button, create_themed_label, create_themed_frame
    
    # ========== MAIN FILTER FRAME ==========
    filter_frame = ttk.LabelFrame(parent_frame, text="🔍 Advanced Filters", padding=10)
    filter_frame.pack(fill="x", padx=0, pady=5)
    
    # Row 1: Type, Color, Rarity
    row1 = create_themed_frame(filter_frame, style='control')
    row1.pack(fill="x", pady=2)
    
    # Card Type
    create_themed_label(row1, "Type:", style='text').pack(side="left", padx=5)
    self.filter_type = ttk.Combobox(row1, width=12, state="readonly", values=[
        "All", "Creature", "Instant", "Sorcery", "Artifact", 
        "Enchantment", "Land", "Planeswalker", "Battle"
    ])
    self.filter_type.set("All")
    self.filter_type.pack(side="left", padx=5)
    self.filter_type.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Color
    create_themed_label(row1, "Color:", style='text').pack(side="left", padx=5)
    self.filter_color = ttk.Combobox(row1, width=12, state="readonly", values=[
        "All", "White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"
    ])
    self.filter_color.set("All")
    self.filter_color.pack(side="left", padx=5)
    self.filter_color.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Rarity
    create_themed_label(row1, "Rarity:", style='text').pack(side="left", padx=5)
    self.filter_rarity = ttk.Combobox(row1, width=12, state="readonly", values=[
        "All", "Common", "Uncommon", "Rare", "Mythic"
    ])
    self.filter_rarity.set("All")
    self.filter_rarity.pack(side="left", padx=5)
    self.filter_rarity.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Row 2: Condition, Foil, Status
    row2 = create_themed_frame(filter_frame, style='control')
    row2.pack(fill="x", pady=2)
    
    # Condition
    create_themed_label(row2, "Condition:", style='text').pack(side="left", padx=5)
    self.filter_condition = ttk.Combobox(row2, width=12, state="readonly", values=[
        "All", "Mint", "Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged"
    ])
    self.filter_condition.set("All")
    self.filter_condition.pack(side="left", padx=5)
    self.filter_condition.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Foil
    create_themed_label(row2, "Foil:", style='text').pack(side="left", padx=5)
    self.filter_foil = ttk.Combobox(row2, width=12, state="readonly", values=[
        "All", "Foil Only", "Non-Foil Only"
    ])
    self.filter_foil.set("All")
    self.filter_foil.pack(side="left", padx=5)
    self.filter_foil.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Status
    create_themed_label(row2, "Status:", style='text').pack(side="left", padx=5)
    self.filter_status = ttk.Combobox(row2, width=12, state="readonly", values=[
        "All", "Available", "Sold", "Reserved", "Listed"
    ])
    self.filter_status.set("All")
    self.filter_status.pack(side="left", padx=5)
    self.filter_status.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Row 3: Set, Box, Price Range
    row3 = create_themed_frame(filter_frame, style='control')
    row3.pack(fill="x", pady=2)
    
    # Set (dynamic - populated from collection)
    create_themed_label(row3, "Set:", style='text').pack(side="left", padx=5)
    self.filter_set = ttk.Combobox(row3, width=12, state="readonly", values=["All"])
    self.filter_set.set("All")
    self.filter_set.pack(side="left", padx=5)
    self.filter_set.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Box (dynamic - populated from library)
    create_themed_label(row3, "Box:", style='text').pack(side="left", padx=5)
    self.filter_box = ttk.Combobox(row3, width=12, state="readonly", values=["All"])
    self.filter_box.set("All")
    self.filter_box.pack(side="left", padx=5)
    self.filter_box.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # Price Range
    create_themed_label(row3, "Price:", style='text').pack(side="left", padx=5)
    self.filter_price = ttk.Combobox(row3, width=12, state="readonly", values=[
        "All", "Under $1", "$1-$5", "$5-$20", "$20-$100", "$100+"
    ])
    self.filter_price.set("All")
    self.filter_price.pack(side="left", padx=5)
    self.filter_price.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # ========== SORT & VIEW FRAME ==========
    sort_view_frame = ttk.LabelFrame(parent_frame, text="📊 Sort & Display", padding=10)
    sort_view_frame.pack(fill="x", padx=0, pady=5)
    
    sort_row = create_themed_frame(sort_view_frame, style='control')
    sort_row.pack(fill="x", pady=2)
    
    # Sort By
    create_themed_label(sort_row, "Sort By:", style='text').pack(side="left", padx=5)
    self.sort_by = ttk.Combobox(sort_row, width=12, state="readonly", values=[
        "Name", "Price", "Set", "Color", "Type", "Rarity", 
        "Date Added", "Call Number", "Quantity", "Total Value"
    ])
    self.sort_by.set("Name")
    self.sort_by.pack(side="left", padx=5)
    self.sort_by.bind('<<ComboboxSelected>>', self.apply_collection_sort)
    
    # Sort Order
    create_themed_label(sort_row, "Order:", style='text').pack(side="left", padx=5)
    self.sort_order = ttk.Combobox(sort_row, width=12, state="readonly", values=[
        "Ascending ↑", "Descending ↓"
    ])
    self.sort_order.set("Ascending ↑")
    self.sort_order.pack(side="left", padx=5)
    self.sort_order.bind('<<ComboboxSelected>>', self.apply_collection_sort)
    
    # View Mode
    create_themed_label(sort_row, "View:", style='text').pack(side="left", padx=5)
    self.view_mode_dropdown = ttk.Combobox(sort_row, width=12, state="readonly", values=[
        "Grouped", "Detailed", "Gestix-Style", "Gallery"
    ])
    self.view_mode_dropdown.set("Grouped")
    self.view_mode_dropdown.pack(side="left", padx=5)
    self.view_mode_dropdown.bind('<<ComboboxSelected>>', self.change_view_mode)
    
    # Cards Per Page
    create_themed_label(sort_row, "Show:", style='text').pack(side="left", padx=5)
    self.cards_per_page = ttk.Combobox(sort_row, width=8, state="readonly", values=[
        "25", "50", "100", "250", "All"
    ])
    self.cards_per_page.set("100")
    self.cards_per_page.pack(side="left", padx=5)
    self.cards_per_page.bind('<<ComboboxSelected>>', self.apply_collection_filters)
    
    # ========== BULK ACTIONS FRAME ==========
    bulk_frame = ttk.LabelFrame(parent_frame, text="⚡ Bulk Actions", padding=10)
    bulk_frame.pack(fill="x", padx=0, pady=5)
    
    bulk_row = create_themed_frame(bulk_frame, style='control')
    bulk_row.pack(fill="x", pady=2)
    
    # Bulk Action Dropdown
    create_themed_label(bulk_row, "Action:", style='text').pack(side="left", padx=5)
    self.bulk_action = ttk.Combobox(bulk_row, width=15, state="readonly", values=[
        "Select Action...", "Mark as Sold", "Mark as Reserved", 
        "Move to Box", "Export Selected", "Print Labels", "Delete"
    ])
    self.bulk_action.set("Select Action...")
    self.bulk_action.pack(side="left", padx=5)
    
    # Apply Button
    create_themed_button(bulk_row, "Apply to Selected", command=self.apply_bulk_action,
                        style='primary', width=15).pack(side="left", padx=10)
    
    # Export Format
    create_themed_label(bulk_row, "Export:", style='text').pack(side="left", padx=5)
    self.export_format = ttk.Combobox(bulk_row, width=12, state="readonly", values=[
        "CSV", "JSON", "PDF Report", "Price List"
    ])
    self.export_format.set("CSV")
    self.export_format.pack(side="left", padx=5)
    
    create_themed_button(bulk_row, "Export All", command=self.export_collection,
                        style='success', width=12).pack(side="left", padx=5)
    
    # ========== CONSOLIDATION FRAME ==========
    consol_frame = ttk.LabelFrame(parent_frame, text="📦 Box Consolidation", padding=10)
    consol_frame.pack(fill="x", padx=0, pady=5)
    
    consol_row = create_themed_frame(consol_frame, style='control')
    consol_row.pack(fill="x", pady=2)
    
    # Source Box (boxes below 50%)
    create_themed_label(consol_row, "From Box:", style='text').pack(side="left", padx=5)
    self.consol_source = ttk.Combobox(consol_row, width=10, state="readonly", values=["Select..."])
    self.consol_source.set("Select...")
    self.consol_source.pack(side="left", padx=5)
    
    # Target Box (boxes with room)
    create_themed_label(consol_row, "To Box:", style='text').pack(side="left", padx=5)
    self.consol_target = ttk.Combobox(consol_row, width=10, state="readonly", values=["Select..."])
    self.consol_target.set("Select...")
    self.consol_target.pack(side="left", padx=5)
    
    # Buttons
    create_themed_button(consol_row, "Check Boxes", command=self.check_consolidation,
                        style='default', width=12).pack(side="left", padx=5)
    
    create_themed_button(consol_row, "Print Move List", command=self.print_consolidation_list,
                        style='info', width=14).pack(side="left", padx=5)
    
    create_themed_button(consol_row, "Execute Move", command=self.execute_consolidation,
                        style='danger', width=12).pack(side="left", padx=5)
    
    # Status label
    self.consol_status = create_themed_label(consol_row, "", style='status', status='info')
    self.consol_status.pack(side="left", padx=10)


def apply_collection_filters(self, event=None):
    """Apply all selected filters to collection view"""
    filters = {
        'type': self.filter_type.get(),
        'color': self.filter_color.get(),
        'rarity': self.filter_rarity.get(),
        'condition': self.filter_condition.get(),
        'foil': self.filter_foil.get(),
        'status': self.filter_status.get(),
        'set': self.filter_set.get(),
        'box': self.filter_box.get(),
        'price': self.filter_price.get(),
        'per_page': self.cards_per_page.get()
    }
    
    # Get tree widget
    if not hasattr(self, 'collection_tree'):
        return
    
    # Clear current display
    for item in self.collection_tree.get_children():
        self.collection_tree.delete(item)
    
    # Get all cards from library
    if not self.library_system or not self.library_system.box_inventory:
        return
    
    filtered_cards = []
    
    for box_id, cards in self.library_system.box_inventory.items():
        for card in cards:
            if not isinstance(card, dict):
                continue
            
            # Apply filters
            if filters['type'] != "All":
                card_type = card.get('type', '')
                if filters['type'].lower() not in card_type.lower():
                    continue
            
            if filters['color'] != "All":
                card_colors = card.get('colors', '')
                color_map = {'White': 'W', 'Blue': 'U', 'Black': 'B', 'Red': 'R', 'Green': 'G'}
                if filters['color'] == 'Colorless':
                    if card_colors:
                        continue
                elif filters['color'] == 'Multicolor':
                    if len(card_colors) < 2:
                        continue
                else:
                    if color_map.get(filters['color'], '') not in card_colors:
                        continue
            
            if filters['rarity'] != "All":
                if card.get('rarity', '').lower() != filters['rarity'].lower():
                    continue
            
            if filters['condition'] != "All":
                if card.get('condition', 'Near Mint') != filters['condition']:
                    continue
            
            if filters['foil'] != "All":
                is_foil = card.get('foil', False)
                if filters['foil'] == 'Foil Only' and not is_foil:
                    continue
                if filters['foil'] == 'Non-Foil Only' and is_foil:
                    continue
            
            if filters['status'] != "All":
                if card.get('status', 'Available') != filters['status']:
                    continue
            
            if filters['set'] != "All":
                if card.get('set', '') != filters['set']:
                    continue
            
            if filters['box'] != "All":
                if box_id != filters['box']:
                    continue
            
            if filters['price'] != "All":
                price = card.get('price', 0) or 0
                if filters['price'] == 'Under $1' and price >= 1:
                    continue
                elif filters['price'] == '$1-$5' and (price < 1 or price >= 5):
                    continue
                elif filters['price'] == '$5-$20' and (price < 5 or price >= 20):
                    continue
                elif filters['price'] == '$20-$100' and (price < 20 or price >= 100):
                    continue
                elif filters['price'] == '$100+' and price < 100:
                    continue
            
            filtered_cards.append(card)
    
    # Apply pagination
    per_page = filters['per_page']
    if per_page != 'All':
        filtered_cards = filtered_cards[:int(per_page)]
    
    # Display filtered cards
    for card in filtered_cards:
        self.collection_tree.insert('', 'end', values=(
            card.get('name', 'Unknown'),
            card.get('call_number', '---'),
            1,
            '✨' if card.get('foil') else '',
            card.get('set', '---'),
            f"${card.get('price', 0):.2f}",
            f"${card.get('price', 0):.2f}"
        ))
    
    # Update stats
    if hasattr(self, 'update_collection_stats'):
        self.update_collection_stats(len(filtered_cards))


def apply_collection_sort(self, event=None):
    """Sort collection by selected criteria"""
    if not hasattr(self, 'collection_tree'):
        return
    
    sort_key = self.sort_by.get()
    ascending = "Ascending" in self.sort_order.get()
    
    # Get all items
    items = [(self.collection_tree.item(item)['values'], item) 
             for item in self.collection_tree.get_children()]
    
    # Sort index mapping
    sort_index = {
        'Name': 0, 'Call Number': 1, 'Quantity': 2, 
        'Set': 4, 'Price': 5, 'Total Value': 6
    }.get(sort_key, 0)
    
    # Sort
    items.sort(key=lambda x: x[0][sort_index], reverse=not ascending)
    
    # Reorder
    for index, (values, item) in enumerate(items):
        self.collection_tree.move(item, '', index)


def change_view_mode(self, event=None):
    """Change collection view mode"""
    mode = self.view_mode_dropdown.get()
    
    if hasattr(self, 'collection_view_mode'):
        mode_map = {
            'Grouped': 'grouped',
            'Detailed': 'detailed', 
            'Gestix-Style': 'gestix',
            'Gallery': 'gallery'
        }
        self.collection_view_mode.set(mode_map.get(mode, 'grouped'))
    
    if hasattr(self, 'refresh_collection_view'):
        self.refresh_collection_view()


def apply_bulk_action(self):
    """Apply selected bulk action to selected items"""
    if not hasattr(self, 'collection_tree'):
        return
    
    action = self.bulk_action.get()
    selected = self.collection_tree.selection()
    
    if action == "Select Action..." or not selected:
        return
    
    if action == "Mark as Sold":
        for item in selected:
            values = self.collection_tree.item(item)['values']
            print(f"Marking {values[0]} as sold")
    
    elif action == "Mark as Reserved":
        for item in selected:
            values = self.collection_tree.item(item)['values']
            print(f"Marking {values[0]} as reserved")
    
    elif action == "Export Selected":
        if hasattr(self, 'export_selected_cards'):
            self.export_selected_cards(selected)
    
    elif action == "Print Labels":
        if hasattr(self, 'print_card_labels'):
            self.print_card_labels(selected)
    
    elif action == "Delete":
        if messagebox.askyesno("Confirm Delete", f"Delete {len(selected)} cards?"):
            for item in selected:
                self.collection_tree.delete(item)
    
    self.bulk_action.set("Select Action...")


def export_collection(self):
    """Export collection in selected format"""
    format_type = self.export_format.get()
    
    if format_type == "CSV":
        if hasattr(self, 'export_csv_collection'):
            self.export_csv_collection()
    elif format_type == "JSON":
        if hasattr(self, 'export_json_collection'):
            self.export_json_collection()
    elif format_type == "PDF Report":
        if hasattr(self, 'export_pdf_report'):
            self.export_pdf_report()
    elif format_type == "Price List":
        if hasattr(self, 'export_price_list'):
            self.export_price_list()


def check_consolidation(self):
    """Check which boxes need consolidation"""
    if not self.library_system:
        return
    
    # Find boxes below 50%
    flagged = []
    targets = []
    
    for box_id, cards in self.library_system.box_inventory.items():
        count = len(cards)
        if 0 < count <= 500:  # Below 50%
            flagged.append(f"{box_id} ({count})")
        elif count < 1000:  # Has room
            room = 1000 - count
            targets.append(f"{box_id} (room: {room})")
    
    # Update dropdowns
    self.consol_source['values'] = flagged if flagged else ["None needed"]
    self.consol_target['values'] = targets if targets else ["No room"]
    
    self.consol_status.config(text=f"Found {len(flagged)} boxes to consolidate", status='warning')


def print_consolidation_list(self):
    """Print move list for consolidation"""
    source = self.consol_source.get().split()[0]
    target = self.consol_target.get().split()[0]
    
    if source == "Select..." or target == "Select...":
        return
    
    # Generate and print move list
    if hasattr(self.library_system, 'consolidator'):
        move_list = self.library_system.consolidator.print_move_list(source, target)
        
        # Save to file
        filename = f"consolidation_{source}_to_{target}.txt"
        with open(filename, 'w') as f:
            f.write(move_list)
        
        self.consol_status.config(text=f"Saved: {filename}", status='success')


def execute_consolidation(self):
    """Execute the consolidation"""
    source = self.consol_source.get().split()[0]
    target = self.consol_target.get().split()[0]
    
    if source == "Select..." or target == "Select...":
        return
    
    if hasattr(self.library_system, 'consolidator'):
        result = self.library_system.consolidator.execute_consolidation(source, target)
        
        if result['success']:
            self.consol_status.config(
                text=f"✅ Moved {result['cards_moved']} cards: {source} → {target}",
                status='success'
            )
            self.apply_collection_filters()  # Refresh view
        else:
            self.consol_status.config(text=f"❌ {result.get('error', 'Failed')}", status='error')


def populate_filter_dropdowns(self):
    """Populate dynamic dropdowns (sets, boxes) from collection data"""
    if not self.library_system:
        return
    
    # Get unique sets
    sets = set()
    boxes = set()
    
    for box_id, cards in self.library_system.box_inventory.items():
        boxes.add(box_id)
        for card in cards:
            if isinstance(card, dict) and card.get('set'):
                sets.add(card['set'])
    
    # Update dropdowns
    if hasattr(self, 'filter_set'):
        self.filter_set['values'] = ["All"] + sorted(list(sets))
    if hasattr(self, 'filter_box'):
        self.filter_box['values'] = ["All"] + sorted(list(boxes))


def update_collection_stats(self, visible_count):
    """Update the collection statistics display"""
    if hasattr(self, 'collection_count_label') and self.library_system:
        total = sum(len(cards) for cards in self.library_system.box_inventory.values())
        self.collection_count_label.config(text=f"Showing {visible_count} of {total} cards")
