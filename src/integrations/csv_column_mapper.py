#!/usr/bin/env python3
"""
CSV Column Mapper - Universal CSV Import
Allows user to map any CSV columns to NEXUS fields
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from pathlib import Path
from typing import Dict, List, Optional
import sys

# Import the library system
from nexus_library_system import NexusLibrarySystem

# Import unified theme
from nexus_theme import NexusTheme, create_themed_button, create_themed_label, create_themed_frame


class CSVColumnMapper:
    """GUI for mapping CSV columns to NEXUS import fields"""
    
    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path
        self.csv_data = []
        self.csv_headers = []
        self.column_mapping = {}
        self.library = None
        
        # Required NEXUS fields
        self.nexus_fields = {
            'name': 'Card Name (required)',
            'quantity': 'Quantity (default: 1)',
            'set': 'Set Code (optional)',
            'scryfall_id': 'Scryfall ID (optional)',
            'foil': 'Foil (optional)',
            'uuid': 'UUID (optional)'
        }
        
        self.root = tk.Tk()
        self.root.title("NEXUS CSV Column Mapper")
        self.root.geometry("800x700")
        self.root.configure(bg=NexusTheme.BG_DARKEST)
        
        # Apply TTK theme
        NexusTheme.configure_ttk_styles(self.root)
        
        self.setup_ui()
        
        if csv_path:
            self.load_csv(csv_path)
    
    def setup_ui(self):
        """Create the mapping interface"""
        
        # Title
        create_themed_label(self.root, "🗺️ CSV COLUMN MAPPER", style='title').pack(pady=10)
        
        create_themed_label(self.root, "Import any CSV format into NEXUS", style='text',
                           fg=NexusTheme.TEXT_GRAY).pack(pady=5)
        
        # File selection
        file_frame = create_themed_frame(self.root, style='control')
        file_frame.pack(pady=10, padx=20, fill='x')
        
        create_themed_label(file_frame, "CSV File:", style='heading').pack(side='left', padx=5)
        
        self.file_label = create_themed_label(file_frame, "No file selected", style='text')
        self.file_label.pack(side='left', padx=10, fill='x', expand=True)
        
        create_themed_button(file_frame, "Browse...", command=self.browse_file, 
                            style='info').pack(side='right', padx=5)
        
        # Separator
        ttk.Separator(self.root, orient='horizontal').pack(fill='x', pady=10)
        
        # Column mapping section
        create_themed_label(self.root, "Map Your Columns:", style='heading').pack(pady=10)
        
        # Scrollable mapping frame
        map_container = create_themed_frame(self.root, style='main')
        map_container.pack(pady=10, padx=20, fill='both', expand=True)
        
        canvas = tk.Canvas(map_container, bg=NexusTheme.BG_MEDIUM, highlightthickness=0)
        scrollbar = ttk.Scrollbar(map_container, orient="vertical", command=canvas.yview)
        self.map_frame = create_themed_frame(canvas, style='panel')
        
        self.map_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.map_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.dropdowns = {}
        
        # Preview section
        create_themed_label(self.root, "Preview (first 3 rows):", style='heading').pack(pady=10)
        
        theme = NexusTheme()
        self.preview_text = tk.Text(self.root, height=6, width=90,
                                    **theme.text_code())
        self.preview_text.pack(pady=5, padx=20)
        
        # Status
        self.status_label = create_themed_label(self.root, "Ready to import", style='status', status='info')
        self.status_label.pack(pady=10)
        
        # Buttons
        btn_frame = create_themed_frame(self.root, style='control')
        btn_frame.pack(pady=20)
        
        create_themed_button(btn_frame, "Cancel", command=self.root.quit, 
                            style='default', width=15, height=2).pack(side='left', padx=10)
        
        self.import_btn = create_themed_button(btn_frame, "Import Cards", 
                                              command=self.import_cards,
                                              style='success', width=15, height=2, state='disabled')
        self.import_btn.pack(side='left', padx=10)
    
    def browse_file(self):
        """Browse for CSV file"""
        filename = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.load_csv(filename)
    
    def load_csv(self, path: str):
        """Load and analyze CSV file"""
        try:
            self.csv_path = path
            self.csv_data = []
            
            # Read CSV
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.csv_headers = reader.fieldnames
                for i, row in enumerate(reader):
                    self.csv_data.append(row)
                    if i >= 2:  # Only need first 3 rows for preview
                        break
            
            # Update UI
            self.file_label.config(text=Path(path).name)
            self.status_label.config(text=f"Found {len(self.csv_headers)} columns",
                                    status='success')
            
            # Create mapping dropdowns
            self.create_mapping_dropdowns()
            
            # Try auto-detection
            self.auto_detect_columns()
            
            # Update preview
            self.update_preview()
            
            # Enable import
            self.import_btn.config(state='normal')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV:\n{e}")
    
    def create_mapping_dropdowns(self):
        """Create dropdown menus for column mapping"""
        # Clear existing
        for widget in self.map_frame.winfo_children():
            widget.destroy()
        
        self.dropdowns.clear()
        
        # Add "None" option to available columns
        available_columns = ['<None>'] + list(self.csv_headers)
        
        row = 0
        for field_key, field_label in self.nexus_fields.items():
            # Field label
            label = create_themed_label(self.map_frame, field_label,
                                       style='text', anchor='w', width=30)
            label.grid(row=row, column=0, padx=10, pady=8, sticky='w')
            
            # Dropdown
            var = tk.StringVar(value='<None>')
            dropdown = ttk.Combobox(self.map_frame, textvariable=var,
                                   values=available_columns,
                                   state='readonly',
                                   width=35,
                                   font=('Arial', 10))
            dropdown.grid(row=row, column=1, padx=10, pady=8)
            dropdown.bind('<<ComboboxSelected>>', lambda e: self.update_preview())
            
            self.dropdowns[field_key] = var
            row += 1
    
    def auto_detect_columns(self):
        """Attempt to auto-detect column mappings"""
        # Common column name patterns
        patterns = {
            'name': ['name', 'card name', 'card', 'cardname', 'title'],
            'quantity': ['quantity', 'qty', 'count', 'amount', 'number', '#'],
            'set': ['set', 'edition', 'set code', 'setcode', 'expansion'],
            'scryfall_id': ['scryfall id', 'scryfall_id', 'scryfallid', 'id'],
            'foil': ['foil', 'finish', 'treatment', 'style'],
            'uuid': ['uuid', 'guid', 'unique id']
        }
        
        for field, keywords in patterns.items():
            for header in self.csv_headers:
                if header.lower().strip() in keywords:
                    self.dropdowns[field].set(header)
                    break
    
    def update_preview(self):
        """Update the preview display"""
        self.preview_text.delete('1.0', 'end')
        
        if not self.csv_data:
            self.preview_text.insert('1.0', 'No data loaded')
            return
        
        # Get mappings
        mapping = {k: v.get() for k, v in self.dropdowns.items() if v.get() != '<None>'}
        
        if 'name' not in mapping:
            self.preview_text.insert('1.0', '⚠️  Card Name is required!')
            return
        
        # Format preview
        preview_lines = []
        for i, row in enumerate(self.csv_data[:3], 1):
            parts = []
            
            # Name (required)
            name = row.get(mapping['name'], '???').strip()
            parts.append(f"Name: {name}")
            
            # Quantity
            if 'quantity' in mapping:
                qty = row.get(mapping['quantity'], '1').strip()
                parts.append(f"Qty: {qty}")
            else:
                parts.append("Qty: 1 (default)")
            
            # Set
            if 'set' in mapping:
                set_code = row.get(mapping['set'], '').strip()
                if set_code:
                    parts.append(f"Set: {set_code}")
            
            # Foil
            if 'foil' in mapping:
                foil = row.get(mapping['foil'], '').strip()
                if foil and foil.lower() in ['yes', 'true', 'foil', '1']:
                    parts.append("⭐FOIL")
            
            preview_lines.append(f"Row {i}: {' | '.join(parts)}")
        
        self.preview_text.insert('1.0', '\n'.join(preview_lines))
    
    def import_cards(self):
        """Import cards using the mapped columns"""
        try:
            # Get full mapping
            mapping = {k: v.get() for k, v in self.dropdowns.items() if v.get() != '<None>'}
            
            # Validate required field
            if 'name' not in mapping:
                messagebox.showerror("Error", "Card Name field is required!")
                return
            
            # Confirm import
            # Re-read full CSV
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                full_data = list(reader)
            
            if not messagebox.askyesno("Confirm Import", 
                                      f"Import {len(full_data)} cards into NEXUS library?"):
                return
            
            # Initialize library
            self.status_label.config(text="Initializing library system...", status='warning')
            self.root.update()
            
            self.library = NexusLibrarySystem()
            
            # Import cards
            self.status_label.config(text="Importing cards...", status='warning')
            self.root.update()
            
            imported = 0
            errors = 0
            
            for i, row in enumerate(full_data, 1):
                try:
                    # Extract mapped data
                    card_name = row.get(mapping['name'], '').strip()
                    if not card_name:
                        errors += 1
                        continue
                    
                    # Quantity
                    qty_str = row.get(mapping.get('quantity', ''), '1').strip()
                    try:
                        quantity = int(qty_str) if qty_str else 1
                    except:
                        quantity = 1
                    
                    # Optional fields
                    set_code = row.get(mapping.get('set', ''), '').strip() or '???'
                    scryfall_id = row.get(mapping.get('scryfall_id', ''), '').strip()
                    uuid = row.get(mapping.get('uuid', ''), '').strip() or scryfall_id
                    
                    # Foil detection
                    foil = False
                    if 'foil' in mapping:
                        foil_value = row.get(mapping['foil'], '').strip().lower()
                        foil = foil_value in ['yes', 'true', 'foil', '1', 'y']
                    
                    # Build card data
                    card_data = {
                        'name': card_name,
                        'set': set_code,
                        'foil': foil
                    }
                    
                    if uuid:
                        card_data['uuid'] = uuid
                        card_data['scryfall_id'] = uuid
                    
                    # Catalog
                    self.library.catalog_card(card_data, quantity)
                    imported += 1
                    
                    # Update progress
                    if i % 100 == 0:
                        self.status_label.config(text=f"Imported {imported} cards...", 
                                                status='warning')
                        self.root.update()
                
                except Exception as e:
                    print(f"Error on row {i}: {e}")
                    errors += 1
            
            # Force save
            self.library.force_save()
            
            # Success
            self.status_label.config(
                text=f"✅ Import complete! {imported} cards imported, {errors} errors",
                status='success'
            )
            
            messagebox.showinfo("Success", 
                              f"Successfully imported {imported} cards!\n"
                              f"Errors: {errors}\n\n"
                              f"Cards cataloged in boxes: {', '.join(sorted(self.library.box_inventory.keys()))}")
            
            # Keep window open to show results
            
        except Exception as e:
            self.status_label.config(text=f"❌ Import failed", status='error')
            messagebox.showerror("Import Failed", f"Error during import:\n{e}")
    
    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def main():
    """Run the column mapper"""
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    mapper = CSVColumnMapper(csv_path)
    mapper.run()


if __name__ == '__main__':
    main()
