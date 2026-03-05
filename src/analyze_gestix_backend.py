#!/usr/bin/env python3
"""
Gestix Backend Scraper - Reverse engineer their inventory management system
Analyzes how Gestix displays set icons, groups versions, and structures card data
"""

import requests
from bs4 import BeautifulSoup
import json
import re


class GestixBackendAnalyzer:
    """Analyze Gestix.org's frontend/backend architecture"""
    
    def __init__(self):
        self.base_url = "https://gestix.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        print("[GESTIX ANALYZER] Initialized")
    
    def analyze_collection_page(self, html_file=None):
        """Analyze the collection page structure"""
        print("\n=== ANALYZING GESTIX COLLECTION PAGE ===\n")
        
        if html_file:
            # Analyze from saved HTML
            with open(html_file, 'r', encoding='utf-8') as f:
                html = f.read()
        else:
            # Fetch live (requires login)
            print("Note: Live fetching requires authentication")
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find card rows
        card_rows = soup.find_all('tr', class_=re.compile(r'card|item|row'))
        print(f"Found {len(card_rows)} potential card rows")
        
        # Analyze structure
        if card_rows:
            sample = card_rows[0]
            print("\n📦 Sample Card Row Structure:")
            print(f"  Classes: {sample.get('class')}")
            print(f"  Columns: {len(sample.find_all(['td', 'th']))}")
            
            # Extract column data
            columns = sample.find_all('td')
            for idx, col in enumerate(columns):
                print(f"\n  Column {idx}:")
                print(f"    Text: {col.get_text(strip=True)[:50]}")
                print(f"    Classes: {col.get('class')}")
                
                # Look for icons
                icons = col.find_all('i', class_=re.compile(r'ss-|ms-'))
                if icons:
                    print(f"    Icons found: {[i.get('class') for i in icons]}")
                
                # Look for images
                imgs = col.find_all('img')
                if imgs:
                    print(f"    Images: {[img.get('src') for img in imgs]}")
        
        # Look for JavaScript/API calls
        scripts = soup.find_all('script')
        print(f"\n🔍 Found {len(scripts)} script tags")
        
        api_endpoints = []
        for script in scripts:
            if script.string:
                # Look for API endpoints
                endpoints = re.findall(r'["\']/(api|collection|cards)/[^"\']+["\']', script.string)
                api_endpoints.extend(endpoints)
        
        if api_endpoints:
            print("\n📡 API Endpoints detected:")
            for ep in set(api_endpoints):
                print(f"  • {ep}")
        
        return {
            'card_rows': len(card_rows),
            'api_endpoints': list(set(api_endpoints)),
            'structure': 'analyzed'
        }
    
    def analyze_set_icons(self):
        """Analyze how Gestix displays set icons"""
        print("\n=== ANALYZING SET ICON SYSTEM ===\n")
        
        # Gestix likely uses Keyrune or Mana font
        icon_systems = {
            'keyrune': {
                'url': 'https://keyrune.andrewgioia.com/',
                'css_class': 'ss ss-{set}',
                'example': 'ss ss-blb (for Bloomburrow)'
            },
            'mana': {
                'url': 'https://mana.andrewgioia.com/',
                'css_class': 'ms ms-{symbol}',
                'example': 'ms ms-u (for blue mana)'
            }
        }
        
        print("Gestix likely uses:")
        for system, info in icon_systems.items():
            print(f"\n  {system.upper()}:")
            print(f"    URL: {info['url']}")
            print(f"    Format: {info['css_class']}")
            print(f"    Example: {info['example']}")
        
        return icon_systems
    
    def analyze_version_grouping(self):
        """Analyze how Gestix groups card versions"""
        print("\n=== ANALYZING VERSION GROUPING ===\n")
        
        print("Gestix Version Grouping Logic:")
        print("  • Groups by card name")
        print("  • Shows multiple printings as 'versions'")
        print("  • Each version has:")
        print("    - Set icon (Keyrune)")
        print("    - Quantity")
        print("    - Language flag")
        print("    - Price")
        print("  • Displays mana cost icons")
        print("  • Shows rarity color")
        
        structure = {
            'grouping': 'by_card_name',
            'version_display': {
                'set_icon': 'keyrune_css_class',
                'quantity': 'integer',
                'language': 'flag_icon',
                'price': 'currency',
                'mana_cost': 'mana_symbols',
                'rarity': 'color_coded'
            },
            'expandable': True,
            'sortable': True
        }
        
        return structure
    
    def extract_data_structure(self, sample_csv_path):
        """Analyze Gestix CSV export structure"""
        print("\n=== ANALYZING CSV EXPORT STRUCTURE ===\n")
        
        import csv
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            sample_rows = [row for _, row in zip(range(3), reader)]
        
        print("CSV Headers:")
        for idx, header in enumerate(headers):
            print(f"  {idx}: {header}")
        
        print("\nSample Data:")
        for idx, row in enumerate(sample_rows):
            print(f"\n  Row {idx + 1}:")
            for key, value in row.items():
                if value:
                    print(f"    {key}: {value}")
        
        # Determine data structure
        structure = {
            'headers': headers,
            'has_scryfall_id': 'Scryfall ID' in headers,
            'has_set_code': 'Edition' in headers or 'Set' in headers,
            'has_quantity': 'Count' in headers,
            'has_language': 'Language' in headers,
            'has_foil': 'Foil' in headers,
            'has_condition': 'Condition' in headers
        }
        
        return structure


def main():
    """Analyze Gestix backend"""
    analyzer = GestixBackendAnalyzer()
    
    # Analyze set icons
    analyzer.analyze_set_icons()
    
    # Analyze version grouping
    grouping = analyzer.analyze_version_grouping()
    print(f"\n📊 Version Structure: {json.dumps(grouping, indent=2)}")
    
    # Analyze CSV if provided
    csv_path = r"E:\Downloads\Collection_export (12).csv"
    try:
        structure = analyzer.extract_data_structure(csv_path)
        print(f"\n📋 CSV Structure: {json.dumps(structure, indent=2)}")
    except Exception as e:
        print(f"\nCould not analyze CSV: {e}")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS FOR NEXUS:")
    print("="*60)
    print("1. Use Keyrune for set icons (ss ss-{set_code})")
    print("2. Use Mana font for mana symbols (ms ms-{symbol})")
    print("3. Group cards by name, expand to show versions")
    print("4. Each version = unique set + condition + foil + language")
    print("5. Display format:")
    print("   Card Name [mana icons]")
    print("   ↳ [set icon] 3x NM en $0.04")
    print("   ↳ [set icon] 1x NM foil en $0.12")


if __name__ == '__main__':
    main()
