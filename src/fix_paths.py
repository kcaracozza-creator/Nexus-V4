#!/usr/bin/env python3
"""
NEXUS PATH FIXER - Makes Everything Portable
Converts ALL hardcoded E:\ paths to relative paths that work on ANY computer
RUN THIS ONCE, then test on a machine without E:\ drive
"""

import os
import re
from pathlib import Path

def fix_file(filepath):
    """Fix hardcoded paths in a single file"""
    print(f"\n{'='*60}")
    print(f"Fixing: {filepath}")
    print(f"{'='*60}")
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        fixes_made = 0
        
        # Pattern replacements - Convert E:\ paths to portable paths
        replacements = [
            # CRITICAL PATHS - Main application files
            (r'r"E:\\MTTGG\\nexus_background\.jpg"', 
             'os.path.join(os.path.dirname(__file__), "assets", "nexus_background.jpg")'),
            
            (r'r"E:\\Downloads\\Master File\.csv"',
             'os.path.join(os.path.dirname(__file__), "data", "Master_File.csv")'),
            
            (r'r"E:\\MTTGG\\MASTER  SHEETS\\Master File \.csv"',
             'os.path.join(os.path.dirname(__file__), "data", "Master_File.csv")'),
            
            (r'r"E:\\MTTGG\\MASTER  SHEETS\\cards\.csv"',
             'os.path.join(os.path.dirname(__file__), "data", "cards.csv")'),
            
            (r'r"E:\\MTTGG\\recognition_cache"',
             'os.path.join(os.path.dirname(__file__), "cache", "recognition_cache")'),
            
            (r'r"E:\\MTTGG\\Inventory"',
             'os.path.join(os.path.dirname(__file__), "data", "inventory")'),
            
            (r'r"E:\\MTTGG\\Decklist templates"',
             'os.path.join(os.path.dirname(__file__), "data", "deck_templates")'),
            
            (r'r"E:\\MTTGG\\Saved Decks"',
             'os.path.join(os.path.dirname(__file__), "data", "saved_decks")'),
            
            (r'rf"E:\\MTTGG\\JSON\\{json_file}"',
             'os.path.join(os.path.dirname(__file__), "data", "json", json_file)'),
            
            (r'r"E:\\MTTGG\\PYTHON SOURCE FILES\\mttgg_config\.json"',
             'os.path.join(os.path.dirname(__file__), "config", "mttgg_config.json")'),
            
            (r'r"E:\\MTTGG\\Card_Images"',
             'os.path.join(os.path.dirname(__file__), "assets", "card_images")'),
            
            (r'r"E:\\MTTGG\\MOTOR_2_TROUBLESHOOTING_GUIDE\.md"',
             'os.path.join(os.path.dirname(__file__), "docs", "MOTOR_2_TROUBLESHOOTING_GUIDE.md")'),
            
            (r'r"E:\\MTTGG\\gestix_collection\.csv"',
             'os.path.join(os.path.dirname(__file__), "data", "gestix_collection.csv")'),
            
            (r"r'E:\\MTTGG\\PYTHON SOURCE FILES'",
             "os.path.dirname(__file__)"),
            
            # Forward slash versions (nexus_library_system.py)
            (r'"E:/MTTGG/nexus_library\.json"',
             'os.path.join(os.path.dirname(__file__), "data", "nexus_library.json")'),
            
            (r'"E:/MTTGG/box_labels\.txt"',
             'os.path.join(os.path.dirname(__file__), "data", "box_labels.txt")'),
            
            # String literals that reference paths (for display messages)
            (r'E:\\\\MTTGG\\\\ARDUINO_SKETCHES',
             '{os.path.join(os.path.dirname(__file__), "arduino_sketches")}'),
            
            (r'E:\\\\MTTGG\\\\MOTOR_2_WIRING_CHECK\.md',
             '{os.path.join(os.path.dirname(__file__), "docs", "MOTOR_2_WIRING_CHECK.md")}'),
        ]
        
        for old_pattern, new_replacement in replacements:
            if re.search(old_pattern, content):
                content = re.sub(old_pattern, new_replacement, content)
                fixes_made += 1
                print(f"✅ Fixed: {old_pattern[:50]}...")
        
        # Add BASE_DIR constant at top of file if not present
        if 'BASE_DIR' not in content and fixes_made > 0:
            # Find the right place to insert (after imports)
            lines = content.split('\n')
            insert_idx = 0
            
            # Skip shebang, encoding, and docstrings
            in_docstring = False
            for i, line in enumerate(lines):
                if '"""' in line or "'''" in line:
                    in_docstring = not in_docstring
                if not in_docstring and line.strip() and not line.startswith('#') and 'import' in line:
                    # Find last import
                    for j in range(i, len(lines)):
                        if 'import' not in lines[j]:
                            insert_idx = j
                            break
                    break
            
            # Insert BASE_DIR setup
            base_dir_code = [
                "",
                "# ===== PORTABLE PATH CONFIGURATION =====",
                "# Auto-added by fix_paths.py to make NEXUS work on any computer",
                "import os",
                "from pathlib import Path",
                "BASE_DIR = Path(__file__).parent.absolute()",
                "# ========================================",
                ""
            ]
            
            lines = lines[:insert_idx] + base_dir_code + lines[insert_idx:]
            content = '\n'.join(lines)
            print(f"✅ Added BASE_DIR configuration")
        
        # Write fixed content if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(content)
            print(f"\n✅ FIXED {fixes_made} paths in {os.path.basename(filepath)}")
            return fixes_made
        else:
            print(f"\n✓ No paths to fix in {os.path.basename(filepath)}")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error fixing {filepath}: {e}")
        return 0

def create_directory_structure():
    """Create the portable directory structure"""
    print(f"\n{'='*60}")
    print("Creating Portable Directory Structure")
    print(f"{'='*60}\n")
    
    base = Path.cwd()
    
    directories = [
        'data',
        'data/inventory',
        'data/deck_templates',
        'data/saved_decks',
        'data/json',
        'assets',
        'assets/card_images',
        'cache',
        'cache/recognition_cache',
        'config',
        'docs',
        'arduino_sketches',
        'backups',
    ]
    
    for dir_name in directories:
        dir_path = base / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {dir_name}/")
    
    print(f"\n✅ Directory structure created")

def main():
    """Main path fixer"""
    print("\n" + "="*60)
    print("NEXUS PATH FIXER - Making Everything Portable")
    print("="*60)
    print("This script converts ALL hardcoded E:\\ paths to portable paths")
    print("that work on ANY computer")
    print("="*60)
    
    # Files to fix
    python_files = [
        'nexus.py',
        'nexus_library_system.py',
        'import_gestix.py',
    ]
    
    total_fixes = 0
    
    # Fix each file
    for filename in python_files:
        if os.path.exists(filename):
            fixes = fix_file(filename)
            total_fixes += fixes
        else:
            print(f"\n⚠️  File not found: {filename}")
    
    # Create directory structure
    create_directory_structure()
    
    # Summary
    print(f"\n{'='*60}")
    print("FIX SUMMARY")
    print(f"{'='*60}")
    print(f"Total paths fixed: {total_fixes}")
    print(f"Files modified: {len([f for f in python_files if os.path.exists(f)])}")
    print(f"\n✅ NEXUS is now PORTABLE!")
    print(f"\n{'='*60}")
    print("NEXT STEPS:")
    print(f"{'='*60}")
    print("1. Copy your data files to the new directories:")
    print("   - Master_File.csv → data/")
    print("   - cards.csv → data/")
    print("   - nexus_background.jpg → assets/")
    print("   - nexus_library.json → data/")
    print("\n2. Test NEXUS on a computer WITHOUT E:\\ drive")
    print("\n3. If it works, you're ready to deploy to shops!")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
