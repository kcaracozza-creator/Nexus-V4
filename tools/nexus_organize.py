#!/usr/bin/env python3
"""
NEXUS AUTO-ORGANIZE SCRIPT
Created: Feb 13, 2026 - After The Great E: Drive Massacre

Purpose: Automatically organize recovered files AND existing OneDrive chaos
Strategy: Sort by PURPOSE and TYPE, not date (Kevin's brain works this way)
"""

import os
import shutil
import hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# TARGET FOLDER STRUCTURE (Kevin-approved)
FOLDER_MAP = {
    # Active work
    'NEXUS_ACTIVE': {
        'code': ['.py', '.js', '.html', '.css', '.json', '.yaml', '.yml', '.sh', '.bat'],
        'docs': ['.md', '.txt'],
        'tests': ['.test.py', '.test.js', '_test.py']
    },
    
    # Assets by type (easy to find)
    'NEXUS_ASSETS': {
        '3D_models': ['.stl', '.obj', '.blend', '.step', '.stp', '.3mf', '.amf'],
        'diagrams': ['.drawio', '.svg', '.vsd', '.vsdx'],
        'photos': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic'],
        'videos': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
        'renders': ['.render.png', '.render.jpg'],
        'audio': ['.mp3', '.wav', '.m4a', '.flac']
    },
    
    # History & evolution
    'NEXUS_HISTORY': {
        'origin_stories': ['origin', 'story', 'inception', 'journey', 'idea'],
        'business_plans': ['.pdf', '.pptx', '.docx'],
        'milestones': ['contract', 'signed', 'achievement', 'milestone'],
        'archives': ['old', 'deprecated', 'backup', 'archive']
    },
    
    # Legal & IP
    'NEXUS_LEGAL': {
        'patent': ['patent', 'uspto', 'claim', 'provisional'],
        'contracts': ['contract', 'agreement', 'nda', 'signed'],
        'trademark': ['trademark', 'tm', 'brand']
    },
    
    # Non-NEXUS files (categorized by type)
    'NON_NEXUS': {
        'documents': ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'],
        'images': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic'],
        'videos': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
        'audio': ['.mp3', '.wav', '.m4a', '.flac'],
        '3d_files': ['.stl', '.obj', '.blend', '.step', '.stp'],
        'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        'misc': []
    },
    
    # Chaos dump
    'TEMP_UNSORTED': {
        'screenshots': ['.png', '.jpg'],
        'random_csvs': ['.csv'],
        'misc': []
    }
}

# NEXUS DETECTION KEYWORDS
NEXUS_KEYWORDS = [
    'nexus', 'scanner', 'ocr', 'coral', 'brock', 'snarf', 'zultan',
    'card', 'mtg', 'magic', 'pokemon', 'collectible', 'inventory',
    'robot', 'arm', 'pi5', 'raspberry', 'esp32', 'arduino',
    'marketplace', 'seller', 'buyer', 'listing'
]

# FILES TO IGNORE
IGNORE_LIST = [
    'desktop.ini', 'thumbs.db', '.ds_store', 
    '.git', '.gitignore', '__pycache__',
    'node_modules', '.venv', 'venv'
]

def get_file_hash(filepath, chunk_size=8192):
    """Fast MD5 hash for duplicate detection"""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def find_duplicates(file_list):
    """Group files by hash (exact duplicates)"""
    hashes = defaultdict(list)
    
    print(f"\nScanning {len(file_list)} files for duplicates...")
    for filepath in file_list:
        file_hash = get_file_hash(filepath)
        if file_hash:
            hashes[file_hash].append(filepath)
    
    duplicates = {h: files for h, files in hashes.items() if len(files) > 1}
    
    if duplicates:
        print(f"Found {len(duplicates)} sets of duplicate files")
        total_dupes = sum(len(files) - 1 for files in duplicates.values())
        print(f"   {total_dupes} duplicate files can be removed")
    
    return duplicates

def is_nexus_related(filepath):
    """Detect if file is NEXUS-related based on filename, path, and date"""
    path = Path(filepath)
    filename = path.name.lower()
    full_path = str(path).lower()
    
    # NEXUS BIRTHDAY: October 17, 2025
    # Any file created/modified BEFORE this date = NOT NEXUS
    try:
        file_mtime = os.path.getmtime(filepath)
        file_date = datetime.fromtimestamp(file_mtime)
        nexus_birthday = datetime(2025, 10, 17)
        
        if file_date < nexus_birthday:
            return False
    except:
        pass
    
    # Check for NEXUS keywords
    for keyword in NEXUS_KEYWORDS:
        if keyword in filename or keyword in full_path:
            return True
    
    # Check for NEXUS folder names
    path_parts = path.parts
    for part in path_parts:
        if 'nexus' in part.lower():
            return True
    
    return False

def categorize_file(filepath):
    """Determine where a file should go"""
    path = Path(filepath)
    filename = path.name.lower()
    ext = path.suffix.lower()
    
    if filename in IGNORE_LIST or any(ig in str(path) for ig in IGNORE_LIST):
        return None
    
    is_nexus = is_nexus_related(filepath)
    
    if not is_nexus:
        if ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt']:
            return ('NON_NEXUS', 'documents')
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic']:
            if 'screenshot' in filename or 'screen' in filename:
                return ('TEMP_UNSORTED', 'screenshots')
            return ('NON_NEXUS', 'images')
        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
            return ('NON_NEXUS', 'videos')
        if ext in ['.mp3', '.wav', '.m4a', '.flac']:
            return ('NON_NEXUS', 'audio')
        if ext in ['.stl', '.obj', '.blend', '.step', '.stp']:
            return ('NON_NEXUS', '3d_files')
        if ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return ('NON_NEXUS', 'archives')
        if ext == '.csv':
            return ('TEMP_UNSORTED', 'random_csvs')
        return ('NON_NEXUS', 'misc')
    
    if any(kw in filename for kw in ['patent', 'uspto', 'claim', 'provisional']):
        return ('NEXUS_LEGAL', 'patent')
    if any(kw in filename for kw in ['contract', 'agreement', 'nda', 'signed']):
        return ('NEXUS_LEGAL', 'contracts')
    if any(kw in filename for kw in ['trademark', 'tm', 'brand']):
        return ('NEXUS_LEGAL', 'trademark')
    
    if any(kw in filename for kw in ['origin', 'story', 'inception', 'journey', 'idea']):
        return ('NEXUS_HISTORY', 'origin_stories')
    if any(kw in filename for kw in ['milestone', 'achievement', 'win']):
        return ('NEXUS_HISTORY', 'milestones')
    if ext in ['.pdf', '.pptx', '.docx'] and any(kw in filename for kw in ['business', 'plan', 'investor', 'pitch']):
        return ('NEXUS_HISTORY', 'business_plans')
    
    if ext in ['.stl', '.obj', '.blend', '.step', '.stp', '.3mf', '.amf']:
        return ('NEXUS_ASSETS', '3D_models')
    if ext in ['.drawio', '.svg', '.vsd', '.vsdx']:
        return ('NEXUS_ASSETS', 'diagrams')
    if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
        return ('NEXUS_ASSETS', 'videos')
    if ext in ['.mp3', '.wav', '.m4a', '.flac']:
        return ('NEXUS_ASSETS', 'audio')
    if 'render' in filename and ext in ['.png', '.jpg']:
        return ('NEXUS_ASSETS', 'renders')
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic']:
        if 'screenshot' in filename or 'screen' in filename:
            return ('TEMP_UNSORTED', 'screenshots')
        return ('NEXUS_ASSETS', 'photos')
    
    if ext in ['.py', '.js', '.html', '.css', '.json', '.yaml', '.yml', '.sh', '.bat']:
        return ('NEXUS_ACTIVE', 'code')
    if ext in ['.md', '.txt'] and 'readme' not in filename:
        return ('NEXUS_ACTIVE', 'docs')
    
    if ext == '.csv':
        return ('TEMP_UNSORTED', 'random_csvs')
    
    return ('TEMP_UNSORTED', 'misc')

def scan_directory(source_dir):
    """Scan directory and categorize all files"""
    source_path = Path(source_dir)
    
    if not source_path.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        return None
    
    print(f"\nScanning: {source_dir}")
    
    all_files = []
    for root, dirs, files in os.walk(source_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_LIST]
        
        for file in files:
            if file not in IGNORE_LIST:
                all_files.append(os.path.join(root, file))
    
    print(f"   Found {len(all_files)} files")
    
    categorized = defaultdict(lambda: defaultdict(list))
    uncategorized = []
    
    for filepath in all_files:
        category = categorize_file(filepath)
        if category:
            parent, subfolder = category
            categorized[parent][subfolder].append(filepath)
        else:
            uncategorized.append(filepath)
    
    duplicates = find_duplicates(all_files)
    
    return {
        'files': all_files,
        'categorized': dict(categorized),
        'uncategorized': uncategorized,
        'duplicates': duplicates
    }

def generate_report(scan_results, output_file='organize_preview.txt'):
    """Generate preview report for user approval"""
    report = []
    report.append("=" * 80)
    report.append("NEXUS AUTO-ORGANIZE PREVIEW REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    report.append("")
    
    categorized = scan_results['categorized']
    duplicates = scan_results['duplicates']
    
    total_files = len(scan_results['files'])
    categorized_count = sum(len(files) for category in categorized.values() for files in category.values())
    
    report.append("SUMMARY")
    report.append("-" * 80)
    report.append(f"Total files scanned: {total_files}")
    report.append(f"Files categorized: {categorized_count}")
    report.append(f"Files uncategorized: {len(scan_results['uncategorized'])}")
    report.append(f"Duplicate sets found: {len(duplicates)}")
    report.append("")
    
    report.append("CATEGORIZATION BREAKDOWN")
    report.append("-" * 80)
    
    for parent in sorted(categorized.keys()):
        report.append(f"\n{parent}/")
        for subfolder in sorted(categorized[parent].keys()):
            file_count = len(categorized[parent][subfolder])
            report.append(f"  +-- {subfolder}/ ({file_count} files)")
            
            for i, filepath in enumerate(categorized[parent][subfolder][:5]):
                filename = Path(filepath).name
                prefix = "  |   +--" if i < 4 else "  |   +--"
                report.append(f"{prefix} {filename}")
            
            if file_count > 5:
                report.append(f"  |       ... and {file_count - 5} more files")
    
    if duplicates:
        report.append("\n" + "=" * 80)
        report.append("DUPLICATE FILES (KEEP NEWEST, DELETE OLDER)")
        report.append("-" * 80)
        
        for file_hash, files in list(duplicates.items())[:20]:
            report.append(f"\nDuplicate set (hash: {file_hash[:12]}...):")
            files_sorted = sorted(files, key=lambda f: os.path.getmtime(f), reverse=True)
            for i, filepath in enumerate(files_sorted):
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                status = "KEEP (newest)" if i == 0 else "DELETE"
                report.append(f"  [{status}] {filepath}")
                report.append(f"          Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    report_text = "\n".join(report)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"\nPreview report saved: {output_file}")
    print(f"\nREVIEW THIS FILE BEFORE PROCEEDING!")
    
    return output_file

if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 80)
    print("NEXUS AUTO-ORGANIZE")
    print("=" * 80)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python nexus_organize.py <source_dir>")
        print("\nExamples:")
        print("  python nexus_organize.py C:\\Users\\kcara\\Desktop\\E_DRIVE_RECOVERY")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    
    results = scan_directory(source_dir)
    
    if not results:
        sys.exit(1)
    
    report_file = generate_report(results)
    
    print(f"\nNEXT STEPS:")
    print(f"   1. Review: {report_file}")
    print(f"   2. Files will NOT be moved until you approve")
