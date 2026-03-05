#!/usr/bin/env python3
"""
PSA REGISTRY SCRAPER V2
========================
Uses PSA's internal JSON API to scrape population reports.

Based on: https://github.com/ChrisMuir/psa-scrape
Enhanced with SQLite caching and multi-category support.

Author: Kevin Caracozza / NEXUS Project
"""

import os
import sys
import time
import math
import json
import sqlite3
import cloudscraper
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('PSA-Scraper')

# =============================================================================
# PSA API CONFIGURATION  
# =============================================================================

PSA_API_URL = "https://www.psacard.com/Pop/GetSetItems"
PSA_POP_BASE = "https://www.psacard.com/pop"
PAGE_SIZE = 500  # Max per request
REQUEST_DELAY = 3  # Seconds between requests

# TCG Set URLs (add more as needed)
TCG_SETS = {
    'pokemon': {
        'base_set_1st_ed': 'https://www.psacard.com/pop/tcg-cards/1999/pokemon-game-1st-edition/27636',
        'base_set_unlimited': 'https://www.psacard.com/pop/tcg-cards/1999/pokemon-game/27752',
        'base_set_shadowless': 'https://www.psacard.com/pop/tcg-cards/1999/pokemon-game-shadowless/27754',
        'jungle_1st_ed': 'https://www.psacard.com/pop/tcg-cards/1999/pokemon-jungle-1st-edition/27756',
        'jungle_unlimited': 'https://www.psacard.com/pop/tcg-cards/1999/pokemon-jungle/27758',
        'fossil_1st_ed': 'https://www.psacard.com/pop/tcg-cards/1999/pokemon-fossil-1st-edition/27760',
        'fossil_unlimited': 'https://www.psacard.com/pop/tcg-cards/1999/pokemon-fossil/27762',
        'team_rocket_1st_ed': 'https://www.psacard.com/pop/tcg-cards/2000/pokemon-team-rocket-1st-edition/27764',
        'neo_genesis_1st_ed': 'https://www.psacard.com/pop/tcg-cards/2000/pokemon-neo-genesis-1st-edition/27768',
        'base_set_2': 'https://www.psacard.com/pop/tcg-cards/2000/pokemon-base-set-2/28011',
        'gym_heroes_1st_ed': 'https://www.psacard.com/pop/tcg-cards/2000/pokemon-gym-heroes-1st-edition/27776',
        'gym_challenge_1st_ed': 'https://www.psacard.com/pop/tcg-cards/2000/pokemon-gym-challenge-1st-edition/27780',
        'skyridge': 'https://www.psacard.com/pop/tcg-cards/2003/pokemon-skyridge/27816',
        'crystal_guardians': 'https://www.psacard.com/pop/tcg-cards/2006/pokemon-crystal-guardians/27827',
        'celebrations': 'https://www.psacard.com/pop/tcg-cards/2021/pokemon-celebrations/183159',
        'evolving_skies': 'https://www.psacard.com/pop/tcg-cards/2021/pokemon-swsh-evolving-skies/180901',
    },
    'mtg': {
        'alpha': 'https://www.psacard.com/pop/tcg-cards/1993/magic-the-gathering-alpha/183281',
        'beta': 'https://www.psacard.com/pop/tcg-cards/1993/magic-the-gathering-beta/183282',
        'unlimited': 'https://www.psacard.com/pop/tcg-cards/1993/magic-the-gathering-unlimited/183283',
        'arabian_nights': 'https://www.psacard.com/pop/tcg-cards/1993/magic-the-gathering-arabian-nights/183284',
        'antiquities': 'https://www.psacard.com/pop/tcg-cards/1994/magic-the-gathering-antiquities/183285',
        'legends': 'https://www.psacard.com/pop/tcg-cards/1994/magic-the-gathering-legends/183286',
        'the_dark': 'https://www.psacard.com/pop/tcg-cards/1994/magic-the-gathering-the-dark/183287',
    },
    'yugioh': {
        'legend_blue_eyes': 'https://www.psacard.com/pop/tcg-cards/2002/yu-gi-oh-legend-of-blue-eyes-white-dragon/183335',
        'metal_raiders': 'https://www.psacard.com/pop/tcg-cards/2002/yu-gi-oh-metal-raiders/183336',
        'pharaonic_guardian': 'https://www.psacard.com/pop/tcg-cards/2003/yu-gi-oh-pharaonic-guardian/183341',
    },
    'baseball': {
        '1952_topps': 'https://www.psacard.com/pop/baseball-cards/1952/topps/3109',
        '1989_upper_deck': 'https://www.psacard.com/pop/baseball-cards/1989/upper-deck/3946',
        '2011_topps_update': 'https://www.psacard.com/pop/baseball-cards/2011/topps-update/124920',
        '2019_bowman_chrome': 'https://www.psacard.com/pop/baseball-cards/2019/bowman-chrome/165833',
    },
    'basketball': {
        '1986_fleer': 'https://www.psacard.com/pop/basketball-cards/1986/fleer/23903',
        '2003_topps_chrome': 'https://www.psacard.com/pop/basketball-cards/2003/topps-chrome/32025',
        '2018_prizm': 'https://www.psacard.com/pop/basketball-cards/2018/panini-prizm/161261',
        '2019_mosaic': 'https://www.psacard.com/pop/basketball-cards/2019/panini-mosaic/165893',
    },
    'football': {
        '2000_playoff_contenders': 'https://www.psacard.com/pop/football-cards/2000/playoff-contenders/26877',
        '2017_panini_prizm': 'https://www.psacard.com/pop/football-cards/2017/panini-prizm/156101',
        '2020_panini_mosaic': 'https://www.psacard.com/pop/football-cards/2020/panini-mosaic/178341',
    }
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PSACard:
    """Card with population data from PSA"""
    card_name: str
    card_number: str
    set_name: str
    category: str
    year: Optional[int] = None
    variation: Optional[str] = None
    
    # Population by grade
    pop_auth: int = 0
    pop_1: int = 0
    pop_2: int = 0
    pop_3: int = 0
    pop_4: int = 0
    pop_5: int = 0
    pop_6: int = 0
    pop_7: int = 0
    pop_8: int = 0
    pop_9: int = 0
    pop_10: int = 0
    total_graded: int = 0
    
    psa_set_id: Optional[str] = None
    scraped_at: Optional[str] = None
    
    def gem_rate(self) -> float:
        """PSA 10 percentage"""
        return (self.pop_10 / self.total_graded * 100) if self.total_graded > 0 else 0


# =============================================================================
# PSA API CLIENT
# =============================================================================

class PSAClient:
    """Client for PSA's internal JSON API using cloudscraper"""
    
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.scraper.headers.update({
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.psacard.com',
            'Referer': 'https://www.psacard.com/pop',
        })
    
    def get_set_data(self, set_url: str) -> List[Dict[str, Any]]:
        """Fetch all cards for a set via PSA API"""
        # First visit the page to get cookies
        try:
            self.scraper.get(set_url, timeout=30)
            time.sleep(2)
        except:
            pass
        
        # Extract set ID from URL
        try:
            set_id = int(set_url.rstrip('/').split('/')[-1])
        except ValueError:
            logger.error(f"Invalid URL format: {set_url}")
            return []
        
        all_cards = []
        start = 0
        
        while True:
            form_data = {
                'headingID': str(set_id),
                'categoryID': '20019',  # TCG category
                'draw': 1,
                'start': start,
                'length': PAGE_SIZE,
                'isPSADNA': 'false'
            }
            
            try:
                response = self.scraper.post(PSA_API_URL, data=form_data, timeout=30)
                response.raise_for_status()
                json_data = response.json()
                
                cards = json_data.get('data', [])
                total = json_data.get('recordsTotal', 0)
                
                if cards:
                    # Skip header row if present
                    if start == 0 and len(cards) > 1:
                        cards = cards[1:]
                    all_cards.extend(cards)
                
                logger.info(f"  Fetched {len(all_cards)}/{total} cards...")
                
                # Check if we have all cards
                if len(all_cards) >= total or len(cards) == 0:
                    break
                
                start += PAGE_SIZE
                time.sleep(REQUEST_DELAY)
                
            except Exception as e:
                logger.error(f"API error: {e}")
                break
        
        return all_cards


# =============================================================================
# DATABASE CACHE
# =============================================================================

class PSADatabase:
    """SQLite database for PSA population data"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'cache' / 'psa_registry.db'
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT NOT NULL,
                card_number TEXT,
                set_name TEXT NOT NULL,
                category TEXT NOT NULL,
                year INTEGER,
                variation TEXT,
                
                pop_auth INTEGER DEFAULT 0,
                pop_1 INTEGER DEFAULT 0,
                pop_2 INTEGER DEFAULT 0,
                pop_3 INTEGER DEFAULT 0,
                pop_4 INTEGER DEFAULT 0,
                pop_5 INTEGER DEFAULT 0,
                pop_6 INTEGER DEFAULT 0,
                pop_7 INTEGER DEFAULT 0,
                pop_8 INTEGER DEFAULT 0,
                pop_9 INTEGER DEFAULT 0,
                pop_10 INTEGER DEFAULT 0,
                total_graded INTEGER DEFAULT 0,
                
                psa_set_id TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(card_name, card_number, set_name, category, variation)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_name ON cards(card_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_set_name ON cards(set_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON cards(category)')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def save_cards(self, cards: List[PSACard]):
        """Bulk save cards to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for card in cards:
            cursor.execute('''
                INSERT OR REPLACE INTO cards (
                    card_name, card_number, set_name, category, year, variation,
                    pop_auth, pop_1, pop_2, pop_3, pop_4, pop_5, pop_6, pop_7, pop_8, pop_9, pop_10,
                    total_graded, psa_set_id, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card.card_name, card.card_number, card.set_name, card.category,
                card.year, card.variation,
                card.pop_auth, card.pop_1, card.pop_2, card.pop_3, card.pop_4,
                card.pop_5, card.pop_6, card.pop_7, card.pop_8, card.pop_9, card.pop_10,
                card.total_graded, card.psa_set_id, datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def search(self, query: str, category: str = None) -> List[Dict]:
        """Search for cards by name"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM cards WHERE card_name LIKE ?"
        params = [f"%{query}%"]
        
        if category:
            sql += " AND category = ?"
            params.append(category)
        
        cursor.execute(sql + " LIMIT 100", params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict[str, Any]:
        """Database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cards")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT category, COUNT(*) FROM cards GROUP BY category")
        by_category = dict(cursor.fetchall())
        
        cursor.execute("SELECT set_name, COUNT(*) FROM cards GROUP BY set_name ORDER BY COUNT(*) DESC LIMIT 10")
        top_sets = dict(cursor.fetchall())
        
        cursor.execute("SELECT MAX(scraped_at) FROM cards")
        last_update = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_cards': total,
            'by_category': by_category,
            'top_sets': top_sets,
            'last_updated': last_update,
            'db_size_mb': round(self.db_path.stat().st_size / 1024 / 1024, 2) if self.db_path.exists() else 0
        }


# =============================================================================
# SCRAPER
# =============================================================================

class PSAScraper:
    """Main scraper class"""
    
    def __init__(self):
        self.client = PSAClient()
        self.db = PSADatabase()
    
    def parse_card_row(self, row: List, set_name: str, category: str, set_id: str) -> Optional[PSACard]:
        """Parse a card row from PSA JSON response"""
        try:
            # Row format varies but typically:
            # [0] = card name/number combined or just name
            # [1-11] = population by grade (varies)
            # Last = total
            
            if not row or len(row) < 5:
                return None
            
            # First element is usually card name (may contain HTML)
            name_raw = str(row[0]) if row[0] else ""
            
            # Strip HTML tags
            import re
            card_name = re.sub(r'<[^>]+>', '', name_raw).strip()
            
            if not card_name or card_name.lower() in ['card', 'name', 'total']:
                return None
            
            # Extract card number if present
            card_number = None
            match = re.search(r'#?(\d+[a-zA-Z]?)', card_name)
            if match:
                card_number = match.group(1)
            
            # Parse population values (usually columns 1-11 or similar)
            pops = []
            for val in row[1:]:
                try:
                    if isinstance(val, str):
                        val = val.replace(',', '').replace('-', '0')
                    pops.append(int(val) if val else 0)
                except:
                    pops.append(0)
            
            # Ensure we have enough values
            while len(pops) < 12:
                pops.append(0)
            
            return PSACard(
                card_name=card_name,
                card_number=card_number,
                set_name=set_name,
                category=category,
                pop_1=pops[0] if len(pops) > 0 else 0,
                pop_2=pops[1] if len(pops) > 1 else 0,
                pop_3=pops[2] if len(pops) > 2 else 0,
                pop_4=pops[3] if len(pops) > 3 else 0,
                pop_5=pops[4] if len(pops) > 4 else 0,
                pop_6=pops[5] if len(pops) > 5 else 0,
                pop_7=pops[6] if len(pops) > 6 else 0,
                pop_8=pops[7] if len(pops) > 7 else 0,
                pop_9=pops[8] if len(pops) > 8 else 0,
                pop_10=pops[9] if len(pops) > 9 else 0,
                total_graded=pops[10] if len(pops) > 10 else sum(pops[:10]),
                psa_set_id=set_id
            )
        except Exception as e:
            logger.debug(f"Failed to parse row: {e}")
            return None
    
    def scrape_set(self, set_url: str, set_name: str, category: str) -> int:
        """Scrape a single set"""
        logger.info(f"Scraping: {set_name}")
        
        set_id = set_url.rstrip('/').split('/')[-1]
        raw_data = self.client.get_set_data(set_url)
        
        if not raw_data:
            logger.warning(f"No data returned for {set_name}")
            return 0
        
        cards = []
        for row in raw_data:
            card = self.parse_card_row(row, set_name, category, set_id)
            if card:
                cards.append(card)
        
        if cards:
            self.db.save_cards(cards)
            logger.info(f"  Saved {len(cards)} cards")
        
        return len(cards)
    
    def scrape_category(self, category: str) -> int:
        """Scrape all sets in a category"""
        if category not in TCG_SETS:
            logger.error(f"Unknown category: {category}")
            return 0
        
        sets = TCG_SETS[category]
        total = 0
        
        for set_name, set_url in sets.items():
            count = self.scrape_set(set_url, set_name, category)
            total += count
            time.sleep(REQUEST_DELAY)
        
        logger.info(f"Category {category} complete: {total} cards")
        return total
    
    def scrape_all(self) -> int:
        """Scrape all configured sets"""
        total = 0
        for category in TCG_SETS:
            total += self.scrape_category(category)
        return total


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='PSA Registry Scraper')
    parser.add_argument('--category', '-c', choices=list(TCG_SETS.keys()) + ['all'],
                       help='Category to scrape (or "all")')
    parser.add_argument('--url', '-u', type=str,
                       help='Single set URL to scrape')
    parser.add_argument('--name', '-n', type=str, default='custom_set',
                       help='Name for single URL scrape')
    parser.add_argument('--search', '-s', type=str,
                       help='Search for a card')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List available sets')
    
    args = parser.parse_args()
    
    scraper = PSAScraper()
    
    if args.stats:
        stats = scraper.db.get_stats()
        print("\n=== PSA Database Stats ===")
        print(f"Total Cards: {stats['total_cards']:,}")
        print(f"Database Size: {stats['db_size_mb']} MB")
        print(f"Last Updated: {stats['last_updated']}")
        print("\nBy Category:")
        for cat, count in stats['by_category'].items():
            print(f"  {cat}: {count:,}")
        print("\nTop Sets:")
        for s, count in stats['top_sets'].items():
            print(f"  {s}: {count:,}")
        return
    
    if args.search:
        results = scraper.db.search(args.search)
        if results:
            print(f"\n=== Found {len(results)} cards ===")
            for r in results[:20]:
                gem_rate = (r['pop_10'] / r['total_graded'] * 100) if r['total_graded'] > 0 else 0
                print(f"\n{r['card_name']} - {r['set_name']}")
                print(f"  Total: {r['total_graded']:,} | PSA 10: {r['pop_10']:,} ({gem_rate:.1f}%)")
                print(f"  PSA 9: {r['pop_9']:,} | PSA 8: {r['pop_8']:,}")
        else:
            print(f"No cards found for '{args.search}'")
        return
    
    if args.list:
        print("\n=== Available Sets ===")
        for category, sets in TCG_SETS.items():
            print(f"\n{category.upper()}:")
            for name in sets:
                print(f"  - {name}")
        return
    
    if args.url:
        scraper.scrape_set(args.url, args.name, 'custom')
    elif args.category == 'all':
        scraper.scrape_all()
    elif args.category:
        scraper.scrape_category(args.category)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
