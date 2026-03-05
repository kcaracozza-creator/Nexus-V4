#!/usr/bin/env python3
"""
TCDB (Trading Card Database) Scraper for NEXUS
===============================================
Scrapes sports card metadata and images from tcdb.com
Runs on Zultan (192.168.1.152) with 10TB storage

RESPECTFUL SCRAPING:
- Rate limited (1.5 request/second default)
- Saves progress (can resume)
- Doesn't hammer servers

USAGE on Zultan:
    python3 tcdb_scraper.py --sport baseball --start-year 2020 --end-year 2026
    python3 tcdb_scraper.py --sport basketball --download-images
    python3 tcdb_scraper.py --resume  # Continue from last progress
    python3 tcdb_scraper.py --rescrape  # Re-scrape existing sets with pagination fix

Sports: baseball, basketball, football, hockey, soccer, racing, wrestling, ufc
"""

import os
import re
import sys
import json
import time
import sqlite3
import logging
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

import cloudscraper
from bs4 import BeautifulSoup

# =============================================================================
# ZULTAN PATHS - 10TB HDD
# =============================================================================
DATA_DIR = Path("/opt/nexus/sports_cards")
METADATA_DIR = DATA_DIR / "metadata"
IMAGES_DIR = DATA_DIR / "images"
DATABASE_FILE = DATA_DIR / "tcdb_cache.db"
PROGRESS_FILE = DATA_DIR / "scrape_progress.json"
LOG_FILE = DATA_DIR / "scraper.log"

# Create directories
for d in [DATA_DIR, METADATA_DIR, IMAGES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# =============================================================================
# LOGGING SETUP
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('TCDB-Scraper')

# =============================================================================
# CONFIGURATION
# =============================================================================
BASE_URL = "https://www.tcdb.com"
REQUEST_DELAY = 1.5  # Seconds between requests (be nice!)
MAX_RETRIES = 3
TIMEOUT = 30
CARDS_PER_PAGE = 100  # TCDB shows 100 cards per Checklist page

# Sport category mappings on TCDB
SPORT_CATEGORIES = {
    'baseball': 'Baseball',
    'basketball': 'Basketball',
    'football': 'Football',
    'hockey': 'Hockey',
    'soccer': 'Soccer',
    'racing': 'Racing',
    'wrestling': 'Wrestling',
    'ufc': 'MMA',
    'golf': 'Golf',
    'boxing': 'Boxing',
    'tennis': 'Tennis',
}

# =============================================================================
# DATA CLASSES
# =============================================================================
@dataclass
class CardSet:
    """Represents a card set/product"""
    set_id: str
    name: str
    year: int
    sport: str
    manufacturer: str
    card_count: int
    url: str
    scraped_at: Optional[str] = None

@dataclass
class Card:
    """Represents a single card"""
    card_id: str
    set_id: str
    name: str  # Player/subject name
    card_number: str
    team: Optional[str]
    position: Optional[str]
    variant: Optional[str]
    subset: Optional[str]
    year: int
    sport: str
    image_url_front: Optional[str]
    image_url_back: Optional[str]
    local_image_front: Optional[str] = None
    local_image_back: Optional[str] = None
    scraped_at: Optional[str] = None

# =============================================================================
# HTTP SESSION
# =============================================================================
def create_session():
    """Create a cloudscraper session to bypass Cloudflare"""
    session = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    return session

# =============================================================================
# DATABASE SETUP
# =============================================================================
def init_database():
    """Initialize SQLite database for caching"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sets (
            set_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            year INTEGER,
            sport TEXT,
            manufacturer TEXT,
            card_count INTEGER,
            url TEXT,
            scraped_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            card_id TEXT PRIMARY KEY,
            set_id TEXT,
            name TEXT NOT NULL,
            card_number TEXT,
            team TEXT,
            position TEXT,
            variant TEXT,
            subset TEXT,
            year INTEGER,
            sport TEXT,
            image_url_front TEXT,
            image_url_back TEXT,
            local_image_front TEXT,
            local_image_back TEXT,
            scraped_at TEXT,
            FOREIGN KEY (set_id) REFERENCES sets(set_id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_year ON cards(year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_sport ON cards(sport)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_number ON cards(card_number)')

    conn.commit()
    return conn

# =============================================================================
# PROGRESS TRACKING
# =============================================================================
def load_progress() -> Dict:
    """Load scraping progress from file"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'completed_sets': [],
        'failed_sets': [],
        'last_sport': None,
        'last_year': None,
        'total_cards': 0,
        'total_images': 0,
        'started_at': None,
        'updated_at': None
    }

def save_progress(progress: Dict):
    """Save scraping progress to file"""
    progress['updated_at'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

# =============================================================================
# SCRAPER CLASS
# =============================================================================
class TCDBScraper:
    """Main scraper class for TCDB.com"""

    def __init__(self, delay: float = REQUEST_DELAY):
        self.session = create_session()
        self.conn = init_database()
        self.delay = delay
        self.progress = load_progress()

        if not self.progress['started_at']:
            self.progress['started_at'] = datetime.now().isoformat()

        logger.info(f"TCDB Scraper initialized (delay={delay}s)")

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return parsed HTML"""
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Fetching: {url}")
                response = self.session.get(url, timeout=TIMEOUT)
                response.raise_for_status()
                time.sleep(self.delay)
                return BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/{MAX_RETRIES} failed for {url}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(self.delay * (attempt + 1))
        logger.error(f"All retries failed for {url}")
        return None

    def _download_image(self, url: str, save_path: Path) -> bool:
        """Download an image to local storage"""
        try:
            response = self.session.get(url, timeout=TIMEOUT, stream=True)
            response.raise_for_status()
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            time.sleep(self.delay / 2)
            return True
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False

    # -------------------------------------------------------------------------
    # GET SETS FOR A SPORT/YEAR
    # -------------------------------------------------------------------------
    def get_sets_for_year(self, sport: str, year: int) -> List[CardSet]:
        """Get all card sets for a sport and year from ViewAll page"""
        sets = []

        browse_url = f"{BASE_URL}/ViewAll.cfm/sp/{SPORT_CATEGORIES.get(sport, sport)}/year/{year}"
        logger.info(f"Fetching sets for {sport} {year}...")
        soup = self._fetch_page(browse_url)

        if not soup:
            return sets

        set_links = soup.find_all('a', href=re.compile(r'/ViewSet\.cfm/sid/\d+'))

        for link in set_links:
            try:
                href = link.get('href', '')
                set_id_match = re.search(r'/sid/(\d+)', href)
                if not set_id_match:
                    continue

                set_id = set_id_match.group(1)
                set_name = link.get_text(strip=True)

                if not set_name or len(set_name) < 3:
                    continue

                manufacturer = self._extract_manufacturer(set_name)

                card_set = CardSet(
                    set_id=set_id,
                    name=set_name,
                    year=year,
                    sport=sport,
                    manufacturer=manufacturer,
                    card_count=0,
                    url=f"{BASE_URL}{href}",
                )
                sets.append(card_set)

            except Exception as e:
                logger.warning(f"Error parsing set link: {e}")
                continue

        logger.info(f"Found {len(sets)} sets for {sport} {year}")
        return sets

    def _extract_manufacturer(self, set_name: str) -> str:
        """Extract manufacturer from set name"""
        manufacturers = [
            'Topps', 'Panini', 'Upper Deck', 'Fleer', 'Donruss', 'Bowman',
            'Score', 'Leaf', 'O-Pee-Chee', 'Pinnacle', 'Pacific', 'SP',
            'Skybox', 'Hoops', 'Stadium Club', 'Finest', 'Chrome', 'Prizm'
        ]
        name_lower = set_name.lower()
        for mfr in manufacturers:
            if mfr.lower() in name_lower:
                return mfr
        return 'Unknown'

    # -------------------------------------------------------------------------
    # GET CARDS FROM A SET - FIXED WITH PAGINATION
    # -------------------------------------------------------------------------
    def get_cards_from_set(self, card_set: CardSet) -> List[Card]:
        """Scrape ALL cards from a set using Checklist.cfm with pagination.

        Uses Checklist.cfm (not ViewSet.cfm) which shows the full card listing
        at 100 cards per page. Follows pagination via ?PageIndex=N.
        """
        all_cards = []
        seen_card_ids = set()

        # Convert ViewSet URL to Checklist URL
        checklist_url = card_set.url.replace('/ViewSet.cfm/', '/Checklist.cfm/')

        logger.info(f"Scraping set: {card_set.name} ({card_set.set_id})")

        page_num = 1
        max_pages = 1  # Will be updated after fetching page 1

        while page_num <= max_pages:
            if page_num == 1:
                url = checklist_url
            else:
                url = f"{checklist_url}?PageIndex={page_num}"

            soup = self._fetch_page(url)
            if not soup:
                break

            # Detect total pages from pagination links on first page
            if page_num == 1:
                max_pages = self._detect_max_page(soup)
                if max_pages > 1:
                    logger.info(f"  {max_pages} pages detected for {card_set.name}")

            # Parse cards from this page
            page_cards = self._parse_checklist_page(soup, card_set, seen_card_ids)

            if not page_cards:
                break

            all_cards.extend(page_cards)
            page_num += 1

        logger.info(f"Found {len(all_cards)} cards in {card_set.name}")
        return all_cards

    def _detect_max_page(self, soup: BeautifulSoup) -> int:
        """Detect max page number from ?PageIndex=N links on the page."""
        max_page = 1
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            match = re.search(r'PageIndex=(\d+)', href)
            if match:
                # Exclude ViewCard PageIndex links (those are card-level, not pagination)
                if '/ViewCard.cfm' not in href:
                    page = int(match.group(1))
                    if page > max_page:
                        max_page = page
        return max_page

    def _parse_checklist_page(self, soup: BeautifulSoup, card_set: CardSet,
                               seen_card_ids: set) -> List[Card]:
        """Parse cards from a single Checklist.cfm page.

        TCDB Checklist table structure (27 cells per row):
          Cell 0-1: Thumbnail image links (ViewCard)
          Cell 9: Card number (text of ViewCard link)
          Cell 18: Player name (text of Person.cfm link)
          Cell 26: Team name (text of Team.cfm link)
        """
        cards = []

        # Find the main data table (largest table on page)
        tables = soup.find_all('table')
        main_table = None
        max_rows = 0
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > max_rows:
                max_rows = len(rows)
                main_table = table

        if not main_table:
            return cards

        for row in main_table.find_all('tr'):
            # Must have a ViewCard link to be a card row
            card_link = row.find('a', href=re.compile(r'/ViewCard\.cfm/sid/\d+/cid/\d+'))
            if not card_link:
                continue

            href = card_link.get('href', '')
            cid_match = re.search(r'/cid/(\d+)', href)
            if not cid_match:
                continue

            card_id = cid_match.group(1)
            if card_id in seen_card_ids:
                continue
            seen_card_ids.add(card_id)

            cells = row.find_all(['td', 'th'])

            # Extract player name from Person.cfm link
            player_name = ''
            person_link = row.find('a', href=re.compile(r'/Person\.cfm/'))
            if person_link:
                player_name = person_link.get_text(strip=True)

            # Fallback: extract name from URL path
            if not player_name:
                url_match = re.search(r'/\d+-(.+?)(?:\?|$)', href)
                if url_match:
                    player_name = url_match.group(1).replace('-', ' ')

            # Extract card number from the ViewCard link that has text
            card_number = ''
            for link in row.find_all('a', href=re.compile(r'/ViewCard\.cfm')):
                text = link.get_text(strip=True)
                if text and re.match(r'^[\d]+[a-zA-Z]?$', text):
                    card_number = text
                    break

            # Fallback: try extracting number from URL
            if not card_number:
                num_match = re.search(r'/\d+-(\d+[a-zA-Z]?)-', href)
                if num_match:
                    card_number = num_match.group(1)

            # Extract team from Team.cfm link
            team = None
            team_link = row.find('a', href=re.compile(r'/Team\.cfm/'))
            if team_link:
                team = team_link.get_text(strip=True)

            # Check for variant info
            variant = None
            row_text = row.get_text()
            variant_patterns = ['RC', 'Rookie', 'Parallel', 'Refractor', 'Prizm',
                              'Auto', 'Autograph', 'Relic', 'Jersey', 'Patch']
            for pattern in variant_patterns:
                if pattern in row_text:
                    variant = pattern
                    break

            card = Card(
                card_id=card_id,
                set_id=card_set.set_id,
                name=player_name,
                card_number=card_number,
                team=team,
                position=None,
                variant=variant,
                subset=None,
                year=card_set.year,
                sport=card_set.sport,
                image_url_front=None,
                image_url_back=None,
            )
            cards.append(card)

        return cards

    # -------------------------------------------------------------------------
    # GET CARD DETAILS (Including Images)
    # -------------------------------------------------------------------------
    def get_card_details(self, card: Card, set_id: str) -> Card:
        """Get full card details including image URLs"""
        detail_url = f"{BASE_URL}/ViewCard.cfm/sid/{set_id}/cid/{card.card_id}"
        soup = self._fetch_page(detail_url)

        if not soup:
            return card

        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            if '/Images/Cards/' in src or 'card' in src.lower():
                alt = img.get('alt', '').lower()
                parent_text = img.parent.get_text().lower() if img.parent else ''
                full_url = src if src.startswith('http') else f"{BASE_URL}{src}"
                if 'back' in alt or 'back' in parent_text:
                    card.image_url_back = full_url
                else:
                    card.image_url_front = full_url

        card.scraped_at = datetime.now().isoformat()
        return card

    # -------------------------------------------------------------------------
    # SAVE TO DATABASE
    # -------------------------------------------------------------------------
    def save_set(self, card_set: CardSet):
        """Save a set to the database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO sets
            (set_id, name, year, sport, manufacturer, card_count, url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            card_set.set_id, card_set.name, card_set.year, card_set.sport,
            card_set.manufacturer, card_set.card_count, card_set.url,
            datetime.now().isoformat()
        ))
        self.conn.commit()

    def save_cards_batch(self, cards: List[Card]):
        """Save multiple cards at once"""
        cursor = self.conn.cursor()
        for card in cards:
            cursor.execute('''
                INSERT OR REPLACE INTO cards
                (card_id, set_id, name, card_number, team, position, variant, subset,
                 year, sport, image_url_front, image_url_back, local_image_front,
                 local_image_back, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card.card_id, card.set_id, card.name, card.card_number, card.team,
                card.position, card.variant, card.subset, card.year, card.sport,
                card.image_url_front, card.image_url_back, card.local_image_front,
                card.local_image_back, card.scraped_at or datetime.now().isoformat()
            ))
        self.conn.commit()
        logger.info(f"Saved {len(cards)} cards to database")

    # -------------------------------------------------------------------------
    # DOWNLOAD IMAGES
    # -------------------------------------------------------------------------
    def download_card_images(self, card: Card) -> Card:
        """Download card images to local storage"""
        image_dir = IMAGES_DIR / card.sport / str(card.year) / card.set_id
        image_dir.mkdir(parents=True, exist_ok=True)

        if card.image_url_front:
            front_path = image_dir / f"{card.card_id}_front.jpg"
            if not front_path.exists():
                if self._download_image(card.image_url_front, front_path):
                    card.local_image_front = str(front_path)
                    self.progress['total_images'] += 1
            else:
                card.local_image_front = str(front_path)

        if card.image_url_back:
            back_path = image_dir / f"{card.card_id}_back.jpg"
            if not back_path.exists():
                if self._download_image(card.image_url_back, back_path):
                    card.local_image_back = str(back_path)
                    self.progress['total_images'] += 1
            else:
                card.local_image_back = str(back_path)

        return card

    # -------------------------------------------------------------------------
    # MAIN SCRAPING ORCHESTRATION
    # -------------------------------------------------------------------------
    def scrape_sport_year(self, sport: str, year: int, download_images: bool = False,
                          get_details: bool = False):
        """Scrape all cards for a sport/year combination"""
        logger.info(f"{'='*60}")
        logger.info(f"SCRAPING: {sport.upper()} {year}")
        logger.info(f"{'='*60}")

        sets = self.get_sets_for_year(sport, year)

        if not sets:
            logger.warning(f"No sets found for {sport} {year}")
            return

        total_cards = 0

        for i, card_set in enumerate(sets, 1):
            set_key = f"{sport}_{year}_{card_set.set_id}"

            if set_key in self.progress['completed_sets']:
                logger.info(f"Skipping already completed: {card_set.name}")
                continue

            logger.info(f"[{i}/{len(sets)}] Processing: {card_set.name}")

            try:
                cards = self.get_cards_from_set(card_set)

                if not cards:
                    logger.warning(f"No cards found in {card_set.name}")
                    continue

                card_set.card_count = len(cards)
                self.save_set(card_set)

                if get_details:
                    for j, card in enumerate(cards):
                        if (j + 1) % 50 == 0:
                            logger.info(f"  Getting details: {j+1}/{len(cards)}")
                        cards[j] = self.get_card_details(card, card_set.set_id)

                if download_images:
                    for j, card in enumerate(cards):
                        if (j + 1) % 50 == 0:
                            logger.info(f"  Downloading images: {j+1}/{len(cards)}")
                        cards[j] = self.download_card_images(card)

                self.save_cards_batch(cards)

                total_cards += len(cards)
                self.progress['total_cards'] += len(cards)
                self.progress['completed_sets'].append(set_key)
                save_progress(self.progress)

                logger.info(f"  Saved {len(cards)} cards from {card_set.name}")

            except Exception as e:
                logger.error(f"Error processing {card_set.name}: {e}")
                self.progress['failed_sets'].append(set_key)
                save_progress(self.progress)
                continue

        logger.info(f"Completed {sport} {year}: {total_cards} cards total")
        self.progress['last_sport'] = sport
        self.progress['last_year'] = year
        save_progress(self.progress)

    def scrape_sport_range(self, sport: str, start_year: int, end_year: int,
                           download_images: bool = False, get_details: bool = False):
        """Scrape multiple years for a sport"""
        for year in range(start_year, end_year + 1):
            self.scrape_sport_year(sport, year, download_images, get_details)

    def rescrape_existing_sets(self, sport: str = None, year: int = None):
        """Re-scrape sets already in the database with the pagination fix.

        This fixes the data for sets that were scraped with the old broken
        ViewSet.cfm method (which only got ~10-13 cards per set).
        """
        cursor = self.conn.cursor()

        sql = "SELECT set_id, name, year, sport, url FROM sets WHERE 1=1"
        params = []
        if sport:
            sql += " AND sport = ?"
            params.append(sport)
        if year:
            sql += " AND year = ?"
            params.append(year)
        sql += " ORDER BY sport, year, name"

        cursor.execute(sql, params)
        sets = cursor.fetchall()

        logger.info(f"Re-scraping {len(sets)} sets with pagination fix...")
        total_new = 0

        for i, (set_id, name, yr, sp, url) in enumerate(sets, 1):
            card_set = CardSet(
                set_id=set_id, name=name, year=yr, sport=sp,
                manufacturer='', card_count=0, url=url or f"{BASE_URL}/ViewSet.cfm/sid/{set_id}"
            )

            try:
                cards = self.get_cards_from_set(card_set)
                if cards:
                    # Check if we found more cards than before
                    cursor.execute("SELECT COUNT(*) FROM cards WHERE set_id = ?", (set_id,))
                    old_count = cursor.fetchone()[0]

                    if len(cards) > old_count:
                        new_cards = len(cards) - old_count
                        total_new += new_cards
                        logger.info(f"[{i}/{len(sets)}] {name}: {old_count} -> {len(cards)} (+{new_cards})")

                    card_set.card_count = len(cards)
                    self.save_set(card_set)
                    self.save_cards_batch(cards)

                if i % 100 == 0:
                    logger.info(f"Progress: {i}/{len(sets)} sets, {total_new} new cards so far")

            except Exception as e:
                logger.error(f"Error re-scraping {name}: {e}")
                continue

        logger.info(f"Re-scrape complete: {total_new} new cards added")

    def get_stats(self) -> Dict:
        """Get current database statistics"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM sets')
        total_sets = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM cards')
        total_cards = cursor.fetchone()[0]
        cursor.execute('SELECT DISTINCT sport FROM cards')
        sports = [r[0] for r in cursor.fetchall()]
        cursor.execute('SELECT sport, COUNT(*) FROM cards GROUP BY sport')
        cards_by_sport = dict(cursor.fetchall())
        cursor.execute('SELECT MIN(year), MAX(year) FROM cards')
        year_range = cursor.fetchone()
        return {
            'total_sets': total_sets,
            'total_cards': total_cards,
            'sports': sports,
            'cards_by_sport': cards_by_sport,
            'year_range': year_range,
            'images_downloaded': self.progress.get('total_images', 0),
        }

    def close(self):
        """Clean up resources"""
        self.conn.close()
        save_progress(self.progress)
        logger.info("Scraper closed, progress saved")


# =============================================================================
# SEARCH FUNCTIONS (For NEXUS Integration)
# =============================================================================
def search_cards(query: str, sport: str = None, year: int = None,
                 limit: int = 20) -> List[Dict]:
    """Search for cards in the local database"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = "SELECT * FROM cards WHERE (name LIKE ? OR card_number LIKE ?)"
    params = [f'%{query}%', f'%{query}%']

    if sport:
        sql += ' AND sport = ?'
        params.append(sport)
    if year:
        sql += ' AND year = ?'
        params.append(year)

    sql += f' LIMIT {limit}'
    cursor.execute(sql, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def lookup_card(player: str, year: int = None, card_number: str = None,
                set_name: str = None, sport: str = None) -> List[Dict]:
    """Look up a card by various criteria (for NEXUS scanner)"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    conditions = ['name LIKE ?']
    params = [f'%{player}%']

    if year:
        conditions.append('year = ?')
        params.append(year)
    if card_number:
        conditions.append('card_number = ?')
        params.append(card_number)
    if set_name:
        conditions.append('set_id IN (SELECT set_id FROM sets WHERE name LIKE ?)')
        params.append(f'%{set_name}%')
    if sport:
        conditions.append('sport = ?')
        params.append(sport)

    sql = f"SELECT * FROM cards WHERE {' AND '.join(conditions)} LIMIT 50"
    cursor.execute(sql, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


# =============================================================================
# CLI MAIN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description='TCDB Sports Card Scraper for NEXUS (Pagination Fixed)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Scrape baseball cards from 2020-2026
  python3 tcdb_scraper.py --sport baseball --start-year 2020 --end-year 2026

  # Re-scrape existing sets with pagination fix (gets missing cards)
  python3 tcdb_scraper.py --rescrape --sport baseball

  # Scrape all major sports (recent years)
  python3 tcdb_scraper.py --all-sports --start-year 2020

  # Resume from last progress
  python3 tcdb_scraper.py --resume

  # Check database stats
  python3 tcdb_scraper.py --stats

  # Search for a card
  python3 tcdb_scraper.py --search "Mike Trout" --year 2023
        '''
    )

    parser.add_argument('--sport', choices=list(SPORT_CATEGORIES.keys()),
                        help='Sport category to scrape')
    parser.add_argument('--all-sports', action='store_true',
                        help='Scrape all major sports')
    parser.add_argument('--start-year', type=int, default=2020,
                        help='Start year (default: 2020)')
    parser.add_argument('--end-year', type=int, default=2026,
                        help='End year (default: 2026)')
    parser.add_argument('--download-images', action='store_true',
                        help='Download card images')
    parser.add_argument('--get-details', action='store_true',
                        help='Get full card details (slower)')
    parser.add_argument('--delay', type=float, default=REQUEST_DELAY,
                        help=f'Delay between requests (default: {REQUEST_DELAY})')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from last progress')
    parser.add_argument('--rescrape', action='store_true',
                        help='Re-scrape existing sets with pagination fix')
    parser.add_argument('--stats', action='store_true',
                        help='Show database statistics')
    parser.add_argument('--search', type=str,
                        help='Search for cards by player name')
    parser.add_argument('--year', type=int,
                        help='Filter search by year')

    args = parser.parse_args()

    init_database()

    # Show stats
    if args.stats:
        scraper = TCDBScraper(delay=args.delay)
        stats = scraper.get_stats()
        scraper.close()

        print(f"\n{'='*50}")
        print("TCDB CACHE STATISTICS")
        print(f"{'='*50}")
        print(f"Total Sets:    {stats['total_sets']:,}")
        print(f"Total Cards:   {stats['total_cards']:,}")
        print(f"Sports:        {', '.join(stats['sports']) if stats['sports'] else 'None'}")
        if stats['year_range'] and stats['year_range'][0]:
            print(f"Year Range:    {stats['year_range'][0]} - {stats['year_range'][1]}")
        print(f"Images DL'd:   {stats['images_downloaded']:,}")
        print()
        if stats['cards_by_sport']:
            print("Cards by Sport:")
            for sport, count in sorted(stats['cards_by_sport'].items()):
                print(f"  {sport}: {count:,}")
        print(f"{'='*50}")
        return

    # Search
    if args.search:
        results = search_cards(args.search, year=args.year)
        if not results:
            print(f"No cards found for '{args.search}'")
            return
        print(f"\nFound {len(results)} cards:\n")
        for card in results:
            print(f"  [{card['year']}] {card['name']} #{card['card_number']} - {card['sport']}")
            if card['team']:
                print(f"         Team: {card['team']}")
        return

    # Re-scrape with pagination fix
    if args.rescrape:
        scraper = TCDBScraper(delay=args.delay)
        try:
            scraper.rescrape_existing_sets(sport=args.sport, year=args.year)
        finally:
            scraper.close()
        return

    # Resume
    if args.resume:
        progress = load_progress()
        if progress.get('last_sport') and progress.get('last_year'):
            args.sport = progress['last_sport']
            args.start_year = progress['last_year']
            print(f"Resuming from {args.sport} {args.start_year}")
        else:
            print("No progress to resume from")
            return

    # Need sport to scrape
    if not args.sport and not args.all_sports:
        parser.print_help()
        print("\nError: Please specify --sport, --all-sports, or --rescrape")
        return

    scraper = TCDBScraper(delay=args.delay)

    try:
        if args.all_sports:
            major_sports = ['baseball', 'basketball', 'football', 'hockey',
                          'soccer', 'racing', 'wrestling']
            for sport in major_sports:
                scraper.scrape_sport_range(
                    sport=sport,
                    start_year=args.start_year,
                    end_year=args.end_year,
                    download_images=args.download_images,
                    get_details=args.get_details
                )
        else:
            scraper.scrape_sport_range(
                sport=args.sport,
                start_year=args.start_year,
                end_year=args.end_year,
                download_images=args.download_images,
                get_details=args.get_details
            )

        stats = scraper.get_stats()
        print(f"\n{'='*50}")
        print("SCRAPING COMPLETE!")
        print(f"{'='*50}")
        print(f"Total Cards in Database: {stats['total_cards']:,}")
        print(f"Images Downloaded: {stats['images_downloaded']:,}")
        print(f"{'='*50}")

    except KeyboardInterrupt:
        print("\n\nInterrupted! Progress saved.")
    finally:
        scraper.close()


if __name__ == '__main__':
    main()
