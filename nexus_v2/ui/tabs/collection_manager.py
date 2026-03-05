#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS V2 - Collection Management Tab
Advanced collection management with import/export and image display
Extracted and modernized from the 85% complete pre-crash system
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import os
import sys
import json
import csv
import threading
import time
from datetime import datetime
from collections import defaultdict, Counter
from pathlib import Path

class CollectionManagerTab:
    """Advanced collection management system"""
    
    def __init__(self, parent_notebook, config=None):
        self.notebook = parent_notebook
        self.config = config or {}
        self.colors = {
            'bg_dark': '#0d0d0d',
            'bg_light': '#1a1a1a',
            'text_gold': '#d4af37',
            'button_primary': '#4b0082',
            'accent_green': '#2d5016',
            'accent_red': '#8b0000'
        }
        
        # Data storage
        self.collection_data = []
        self.filtered_data = []
        self.current_selection = None
        self.total_value = 0.0
        
        # Create the tab
        self.create_tab()
        
    def create_tab(self):
        """Create the complete collection management tab"""
        # Main frame
        self.frame = tk.Frame(self.notebook, bg=self.colors['bg_dark'])
        self.notebook.add(self.frame, text="Collection Manager")
        
        # Header
        header = tk.Label(self.frame, text="COLLECTION MANAGEMENT CENTER", 
                         font=("Arial", 18, "bold"), fg="purple", bg="white")
        header.pack(pady=15)
        
        # Create sections
        self.create_statistics_panel()
        self.create_import_export_controls()
        self.create_collection_view()
        self.create_card_details_panel()
        
        # Load initial data
        self.load_collection_data()
        
    def create_statistics_panel(self):
        """Collection statistics display"""
        stats_frame = ttk.LabelFrame(self.frame, text="Collection Statistics", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        stats_container = tk.Frame(stats_frame, bg=self.colors['bg_light'])
        stats_container.pack(fill="x")
        
        # Statistics labels
        self.total_value_label = tk.Label(stats_container, text="Total Value: $0.00",
                                          font=("Arial", 13), fg="green", bg=self.colors['bg_light'])
        self.total_value_label.pack(side="left", padx=20)
        
        self.card_count_label = tk.Label(stats_container, text="Unique Cards: 0 | Total Cards: 0",
                                         font=("Arial", 13), fg="blue", bg=self.colors['bg_light'])
        self.card_count_label.pack(side="left", padx=20)
        
        self.avg_value_label = tk.Label(stats_container, text="Avg Value: $0.00",
                                        font=("Arial", 13), fg="purple", bg=self.colors['bg_light'])
        self.avg_value_label.pack(side="left", padx=20)
        
        # Control buttons
        tk.Button(stats_container, text="View Set Completion", 
                 command=self.show_set_completion, bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 12)).pack(side="left", padx=10)
        
        tk.Button(stats_container, text="Refresh Stats", 
                 command=self.update_statistics, bg=self.colors['accent_green'], fg="white",
                 font=("Arial", 12)).pack(side="left", padx=5)
                 
    def create_import_export_controls(self):
        """Import/Export functionality"""
        control_frame = ttk.LabelFrame(self.frame, text="Import/Export Controls", padding=15)
        control_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Import buttons row
        import_frame = tk.Frame(control_frame, bg=self.colors['bg_light'])
        import_frame.pack(fill="x", pady=5)
        
        tk.Label(import_frame, text="Import:", font=("Arial", 12, "bold"), 
                bg=self.colors['bg_light'], fg=self.colors['text_gold']).pack(side="left", padx=(0, 10))
        
        tk.Button(import_frame, text="CSV Collection", 
                 command=self.import_csv_collection, bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        tk.Button(import_frame, text="Gestic Scan", 
                 command=self.import_gestic_scan, bg=self.colors['accent_green'], fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        tk.Button(import_frame, text="Untapped Deck", 
                 command=self.import_untapped_deck, bg="orange", fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        tk.Button(import_frame, text="JSON Library", 
                 command=self.import_json_library, bg="#8B4513", fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        # Export buttons row
        export_frame = tk.Frame(control_frame, bg=self.colors['bg_light'])
        export_frame.pack(fill="x", pady=5)
        
        tk.Label(export_frame, text="Export:", font=("Arial", 12, "bold"), 
                bg=self.colors['bg_light'], fg=self.colors['text_gold']).pack(side="left", padx=(0, 10))
        
        tk.Button(export_frame, text="CSV Collection", 
                 command=self.export_csv_collection, bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        tk.Button(export_frame, text="Full Report", 
                 command=self.export_collection_report, bg=self.colors['accent_red'], fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        tk.Button(export_frame, text="Decklist", 
                 command=self.export_as_decklist, bg="#2F4F4F", fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        # Utility buttons row  
        utility_frame = tk.Frame(control_frame, bg=self.colors['bg_light'])
        utility_frame.pack(fill="x", pady=5)
        
        tk.Label(utility_frame, text="Utilities:", font=("Arial", 12, "bold"), 
                bg=self.colors['bg_light'], fg=self.colors['text_gold']).pack(side="left", padx=(0, 10))
        
        tk.Button(utility_frame, text="Update Prices", 
                 command=self.update_scryfall_prices, bg="orange", fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        tk.Button(utility_frame, text="Check Foils", 
                 command=self.check_foil_availability, bg=self.colors['text_gold'], fg="black",
                 font=("Arial", 11)).pack(side="left", padx=2)
        
        tk.Button(utility_frame, text="Validate Collection", 
                 command=self.validate_collection, bg="#8B0000", fg="white",
                 font=("Arial", 11)).pack(side="left", padx=2)
                 
    def create_collection_view(self):
        """Main collection display with search and filtering"""
        view_frame = ttk.LabelFrame(self.frame, text="Collection View", padding=10)
        view_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Search and filter controls
        search_frame = tk.Frame(view_frame, bg=self.colors['bg_light'])
        search_frame.pack(fill="x", pady=(0, 10))
        
        # Search bar
        tk.Label(search_frame, text="Search:", font=("Arial", 12), 
                bg=self.colors['bg_light'], fg="white").pack(side="left")
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_collection)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, 
                               font=("Arial", 12), width=25)
        search_entry.pack(side="left", padx=(5, 10))
        
        # Filters
        tk.Label(search_frame, text="Type:", font=("Arial", 12), 
                bg=self.colors['bg_light'], fg="white").pack(side="left", padx=(10, 5))
        
        self.type_filter = tk.StringVar(value="All")
        type_combo = ttk.Combobox(search_frame, textvariable=self.type_filter,
                                 values=["All", "Creature", "Instant", "Sorcery", "Land", 
                                        "Artifact", "Enchantment", "Planeswalker"],
                                 width=12, state="readonly")
        type_combo.pack(side="left", padx=2)
        type_combo.bind('<<ComboboxSelected>>', self.filter_collection)
        
        tk.Label(search_frame, text="Set:", font=("Arial", 12), 
                bg=self.colors['bg_light'], fg="white").pack(side="left", padx=(10, 5))
        
        self.set_filter = tk.StringVar(value="All")
        self.set_combo = ttk.Combobox(search_frame, textvariable=self.set_filter,
                                     width=8, state="readonly")
        self.set_combo.pack(side="left", padx=2)
        self.set_combo.bind('<<ComboboxSelected>>', self.filter_collection)
        
        # Collection treeview
        tree_frame = tk.Frame(view_frame, bg=self.colors['bg_light'])
        tree_frame.pack(fill="both", expand=True)
        
        # Treeview with scrollbars
        self.tree = ttk.Treeview(tree_frame, columns=('Name', 'Set', 'Type', 'Rarity', 'Foil', 'Price', 'Quantity'), show='headings')
        
        # Configure columns
        self.tree.heading('Name', text='Card Name')
        self.tree.heading('Set', text='Set')
        self.tree.heading('Type', text='Type')
        self.tree.heading('Rarity', text='Rarity')
        self.tree.heading('Foil', text='Foil')
        self.tree.heading('Price', text='Price')
        self.tree.heading('Quantity', text='Qty')
        
        self.tree.column('Name', width=250)
        self.tree.column('Set', width=60)
        self.tree.column('Type', width=100)
        self.tree.column('Rarity', width=80)
        self.tree.column('Foil', width=50)
        self.tree.column('Price', width=80)
        self.tree.column('Quantity', width=50)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # Pack treeview and scrollbars
        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        
        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self.on_card_select)
        
    def create_card_details_panel(self):
        """Card details display panel"""
        details_frame = ttk.LabelFrame(self.frame, text="Card Details", padding=10)
        details_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Details display
        self.details_text = scrolledtext.ScrolledText(details_frame, height=6, 
                                                     font=("Courier", 10),
                                                     bg=self.colors['bg_dark'], fg="white")
        self.details_text.pack(fill="x")
        
    # Event handlers
    def on_card_select(self, event):
        """Handle card selection in treeview"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            values = item['values']
            
            if values:
                self.show_card_details(values[0])  # Pass card name
                
    def show_card_details(self, card_name):
        """Display detailed information about selected card"""
        self.details_text.delete(1.0, tk.END)
        
        # Find card in collection
        card_data = None
        for card in self.collection_data:
            if card.get('name') == card_name:
                card_data = card
                break
                
        if card_data:
            details = f"""CARD DETAILS
{'='*50}
Name: {card_data.get('name', 'Unknown')}
Set: {card_data.get('set_name', 'Unknown')} ({card_data.get('set', '')})
Type: {card_data.get('type_line', 'Unknown')}
Rarity: {card_data.get('rarity', 'Unknown').title()}
CMC: {card_data.get('cmc', 'N/A')}
Foil: {'Yes' if card_data.get('foil') else 'No'}
Price: ${card_data.get('usd_price', 0.0):.2f}
Quantity: {card_data.get('quantity', 1)}

Mana Cost: {card_data.get('mana_cost', 'N/A')}
Oracle Text: {card_data.get('oracle_text', 'N/A')[:200]}
"""
            self.details_text.insert(1.0, details)
    
    # Data management methods
    def load_collection_data(self):
        """Load collection from various sources"""
        self.collection_data = []
        
        # Try to load from JSON library first
        library_path = Path("data/library/nexus_library.json")
        if library_path.exists():
            self.load_from_json_library(library_path)
        
        # Load from CSV if available
        csv_path = Path("data/library/collection.csv")
        if csv_path.exists():
            self.load_from_csv(csv_path)
            
        # Update display
        self.populate_treeview()
        self.update_statistics()
        self.update_set_filter()
        
    def load_from_json_library(self, file_path):
        """Load collection from NEXUS JSON library format"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                library_data = json.load(f)
                
            for call_number, card_data in library_data.items():
                if isinstance(card_data, dict):
                    # Convert library format to collection format
                    collection_card = {
                        'name': card_data.get('name', ''),
                        'set': card_data.get('set', ''),
                        'set_name': card_data.get('set_name', ''),
                        'type_line': card_data.get('type_line', ''),
                        'rarity': card_data.get('rarity', ''),
                        'foil': card_data.get('foil', False),
                        'usd_price': float(card_data.get('usd_price', 0.0)),
                        'quantity': 1,  # Assume 1 per library entry
                        'call_number': call_number,
                        'cataloged_at': card_data.get('cataloged_at', ''),
                        'box_id': card_data.get('box_id', ''),
                        'position': card_data.get('position', 0)
                    }
                    self.collection_data.append(collection_card)
                    
            print(f"✓ Loaded {len(self.collection_data)} cards from JSON library")
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load JSON library: {e}")
            
    def load_from_csv(self, file_path):
        """Load collection from CSV file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                csv_data = []
                
                for row in reader:
                    # Convert CSV format to standard format
                    collection_card = {
                        'name': row.get('name', ''),
                        'set': row.get('set', ''),
                        'set_name': row.get('set_name', ''),
                        'type_line': row.get('type_line', ''),
                        'rarity': row.get('rarity', ''),
                        'foil': row.get('foil', '').lower() == 'true',
                        'usd_price': float(row.get('usd_price', 0.0)),
                        'quantity': int(row.get('quantity', 1))
                    }
                    csv_data.append(collection_card)
                    
            # Merge with existing data
            self.collection_data.extend(csv_data)
            print(f"✓ Loaded {len(csv_data)} additional cards from CSV")
            
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load CSV: {e}")
            
    def populate_treeview(self):
        """Populate the treeview with collection data"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add cards to treeview
        for card in self.filtered_data or self.collection_data:
            foil_text = "Yes" if card.get('foil') else "No"
            price_text = f"${card.get('usd_price', 0.0):.2f}"
            
            self.tree.insert('', 'end', values=(
                card.get('name', ''),
                card.get('set', ''),
                card.get('type_line', ''),
                card.get('rarity', '').title(),
                foil_text,
                price_text,
                card.get('quantity', 1)
            ))
            
    def filter_collection(self, *args):
        """Filter collection based on search and filter criteria"""
        search_text = self.search_var.get().lower()
        type_filter = self.type_filter.get()
        set_filter = self.set_filter.get()
        
        self.filtered_data = []
        
        for card in self.collection_data:
            # Text search
            if search_text and search_text not in card.get('name', '').lower():
                continue
                
            # Type filter
            if type_filter != "All" and type_filter not in card.get('type_line', ''):
                continue
                
            # Set filter
            if set_filter != "All" and set_filter != card.get('set', ''):
                continue
                
            self.filtered_data.append(card)
            
        self.populate_treeview()
        
    def update_statistics(self):
        """Update collection statistics"""
        if not self.collection_data:
            return
            
        total_cards = len(self.collection_data)
        unique_cards = len(set(card['name'] for card in self.collection_data))
        total_value = sum(card.get('usd_price', 0.0) * card.get('quantity', 1) 
                         for card in self.collection_data)
        avg_value = total_value / total_cards if total_cards > 0 else 0
        
        self.total_value_label.config(text=f"Total Value: ${total_value:.2f}")
        self.card_count_label.config(text=f"Unique Cards: {unique_cards} | Total Cards: {total_cards}")
        self.avg_value_label.config(text=f"Avg Value: ${avg_value:.2f}")
        
    def update_set_filter(self):
        """Update the set filter dropdown with available sets"""
        if not self.collection_data:
            return
            
        sets = set(card.get('set', '') for card in self.collection_data)
        sets = sorted([s for s in sets if s])  # Remove empty and sort
        
        self.set_combo.config(values=["All"] + sets)
        
    # Import methods
    def import_csv_collection(self):
        """Import collection from CSV file"""
        file_path = filedialog.askopenfilename(
            title="Import CSV Collection",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            self.load_from_csv(file_path)
            self.populate_treeview()
            self.update_statistics()
            self.update_set_filter()
            messagebox.showinfo("Import Complete", f"Imported collection from {file_path}")
            
    def import_gestic_scan(self):
        """Import Gestix scan data"""
        messagebox.showinfo("Coming Soon", "Gestix scan import will be implemented soon!")
        
    def import_untapped_deck(self):
        """Import Untapped deck"""
        messagebox.showinfo("Coming Soon", "Untapped deck import will be implemented soon!")
        
    def import_json_library(self):
        """Import from NEXUS JSON library"""
        file_path = filedialog.askopenfilename(
            title="Import JSON Library",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            self.load_from_json_library(file_path)
            self.populate_treeview()
            self.update_statistics()
            self.update_set_filter()
            messagebox.showinfo("Import Complete", f"Imported library from {file_path}")
    
    # Export methods
    def export_csv_collection(self):
        """Export collection to CSV"""
        file_path = filedialog.asksaveasfilename(
            title="Export CSV Collection",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if self.collection_data:
                        # Use keys from first card for headers
                        headers = list(self.collection_data[0].keys())
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(self.collection_data)
                        
                messagebox.showinfo("Export Complete", f"Collection exported to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")
                
    def export_collection_report(self):
        """Export detailed collection report"""
        messagebox.showinfo("Coming Soon", "Collection report export will be implemented soon!")
        
    def export_as_decklist(self):
        """Export collection as decklist format"""
        messagebox.showinfo("Coming Soon", "Decklist export will be implemented soon!")
    
    # Utility methods
    def update_scryfall_prices(self):
        """Update card prices from Scryfall"""
        messagebox.showinfo("Coming Soon", "Price update integration will be implemented soon!")
        
    def check_foil_availability(self):
        """Check foil availability for cards"""
        messagebox.showinfo("Coming Soon", "Foil availability check will be implemented soon!")
        
    def validate_collection(self):
        """Validate collection data integrity"""
        issues = []
        
        for i, card in enumerate(self.collection_data):
            if not card.get('name'):
                issues.append(f"Row {i+1}: Missing card name")
            if not card.get('set'):
                issues.append(f"Row {i+1}: Missing set")
            if card.get('usd_price', 0) < 0:
                issues.append(f"Row {i+1}: Invalid price")
                
        if issues:
            issue_text = '\n'.join(issues[:20])  # Show first 20 issues
            if len(issues) > 20:
                issue_text += f"\n... and {len(issues) - 20} more issues"
            messagebox.showwarning("Collection Issues", f"Found {len(issues)} issues:\n\n{issue_text}")
        else:
            messagebox.showinfo("Validation Complete", "Collection data is valid!")
            
    def show_set_completion(self):
        """Show set completion statistics"""
        messagebox.showinfo("Coming Soon", "Set completion view will be implemented soon!")