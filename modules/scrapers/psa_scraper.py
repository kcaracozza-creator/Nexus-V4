#!/usr/bin/env python3
"""
PSA Pop Report Scraper (Playwright)
NEXUS V2 - Kevin Caracozza
Uses headless Chromium to render PSA's React-based pop report pages.

Usage:
  LD_LIBRARY_PATH=~/.local/usr/lib/x86_64-linux-gnu python3 psa_scraper.py -c tcg -y 1999
  LD_LIBRARY_PATH=~/.local/usr/lib/x86_64-linux-gnu python3 psa_scraper.py -c baseball -y 2020-2025
  LD_LIBRARY_PATH=~/.local/usr/lib/x86_64-linux-gnu python3 psa_scraper.py --stats
"""

import os
import re
import sys
import json
import time
import random
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [PSA] %(levelname)s: %(message)s')
logger = logging.getLogger('PSA')

DB_PATH = os.getenv('PSA_DB', '/opt/nexus/psa/psa_registry.db')
REQUEST_DELAY = 8   # seconds between page loads (PSA uses CF, be polite)
PAGE_LOAD_WAIT = 8   # seconds to wait after domcontentloaded
BACKOFF_DELAY = 120  # seconds to wait after CF block before retrying
MAX_RETRIES = 3      # max retries per page
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'

# Category IDs from PSA site (verified 2026-02-15)
CATEGORIES = {
    'tcg': {'id': '156940', 'path': 'tcg-cards'},
    'baseball': {'id': '20003', 'path': 'baseball-cards'},
    'basketball': {'id': '20019', 'path': 'basketball-cards'},
    'football': {'id': '20014', 'path': 'football-cards'},
    'hockey': {'id': '20020', 'path': 'hockey-cards'},
    'soccer': {'id': '20004', 'path': 'soccer-cards'},
}


def init_db():
    """Create PSA database tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS sets (
        set_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        year INTEGER,
        category TEXT,
        url TEXT,
        card_count INTEGER DEFAULT 0,
        scraped_at TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id TEXT,
        card_name TEXT NOT NULL,
        card_number TEXT,
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
        category TEXT,
        year INTEGER,
        set_name TEXT,
        scraped_at TIMESTAMP,
        UNIQUE(set_id, card_name, card_number, variation)
    )''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_psa_card_name ON cards(card_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_psa_set_id ON cards(set_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_psa_category ON cards(category)')

    conn.commit()
    conn.close()
    logger.info(f"Database ready: {DB_PATH}")


def fresh_page(browser):
    """Create a fresh browser context + page to avoid CF bot detection."""
    ctx = browser.new_context(user_agent=USER_AGENT)
    page = ctx.new_page()
    return ctx, page


def load_page(browser, url):
    """Load a URL in a fresh context with CF detection and retry logic."""
    for attempt in range(MAX_RETRIES):
        ctx, page = fresh_page(browser)
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(PAGE_LOAD_WAIT)

            title = page.title()

            # Check for CF access denied (IP blocked)
            if 'access denied' in title.lower():
                ctx.close()
                wait = BACKOFF_DELAY * (attempt + 1)
                logger.warning(f"  CF access denied (attempt {attempt+1}/{MAX_RETRIES}), backing off {wait}s...")
                time.sleep(wait)
                continue

            # Check for CF challenge page
            if 'moment' in title.lower() or 'challenge' in title.lower():
                logger.warning(f"  CF challenge detected, waiting 15s...")
                time.sleep(15)
                title = page.title()
                if 'moment' in title.lower() or 'access denied' in title.lower():
                    ctx.close()
                    wait = BACKOFF_DELAY * (attempt + 1)
                    logger.warning(f"  Still blocked (attempt {attempt+1}/{MAX_RETRIES}), backing off {wait}s...")
                    time.sleep(wait)
                    continue

            return ctx, page

        except Exception as e:
            logger.error(f"  Failed to load {url}: {e}")
            ctx.close()
            if attempt < MAX_RETRIES - 1:
                time.sleep(REQUEST_DELAY * 2)
                continue
            return None, None

    logger.error(f"  All {MAX_RETRIES} attempts failed for {url}")
    return None, None


def discover_year_sets(browser, category_path, category_id, year):
    """Get all set URLs for a category+year from PSA.

    Uses fresh browser contexts for each page load to avoid
    Cloudflare bot detection on sequential requests.
    """
    # Step 1: Get the year page URL from the category main page
    cat_url = f'https://www.psacard.com/pop/{category_path}/{category_id}'
    logger.info(f"Loading category page: {cat_url}")

    ctx, page = load_page(browser, cat_url)
    if not page:
        return []

    # Find the year link
    year_links = page.evaluate("""(year) => {
        const results = [];
        document.querySelectorAll("a").forEach(el => {
            const href = el.href || "";
            const text = el.textContent.trim();
            if (text === String(year) && href.includes("/pop/")) {
                results.push(href);
            }
        });
        return results;
    }""", year)

    ctx.close()

    if not year_links:
        logger.warning(f"  No year link found for {year}")
        return []

    year_url = year_links[0]
    logger.info(f"  Year {year} URL: {year_url}")

    # Step 2: Load the year page in a FRESH context
    time.sleep(REQUEST_DELAY)
    ctx2, page2 = load_page(browser, year_url)
    if not page2:
        return []

    # Extract set links - format: /pop/category-path/year/set-slug/set-id
    set_pattern = f'/pop/{category_path}/{year}/'
    links = page2.evaluate("""(pattern) => {
        const results = [];
        document.querySelectorAll("a").forEach(el => {
            const href = el.href || "";
            const text = el.textContent.trim();
            if (href.includes(pattern) && text.length > 3 &&
                text.indexOf("Shop with") === -1) {
                var clean = href.split("#")[0].split("?")[0];
                var parts = clean.split("/");
                var last = parts[parts.length - 1];
                var afterPat = href.split(pattern)[1] || "";
                if (last.length > 0 && Number(last) > 0 && afterPat.indexOf("/") !== -1) {
                    results.push({
                        href: clean,
                        text: text,
                        set_id: last
                    });
                }
            }
        });
        return results;
    }""", set_pattern)

    ctx2.close()

    sets = []
    seen = set()
    for link in links:
        sid = link['set_id']
        if sid not in seen:
            seen.add(sid)
            sets.append({
                'set_id': sid,
                'name': link['text'],
                'url': link['href'],
                'year': year
            })

    logger.info(f"  Found {len(sets)} sets for {year}")
    return sets


def scrape_set_page(browser, set_url, set_id, set_name, category, year):
    """Scrape pop data from a single set page using a fresh context."""
    logger.info(f"Scraping: {set_name} ({set_id})")

    ctx, page = load_page(browser, set_url)
    if not page:
        return []

    # Wait for table to appear
    try:
        page.wait_for_selector('table', timeout=10000)
    except Exception:
        logger.warning(f"  No table found for {set_name}")
        ctx.close()
        return []

    # Extract table rows via JavaScript
    # PSA table structure:
    #   td[0]: hidden control  td[1]: card number  td[2]: name (<strong> + <br>variation)
    #   td[3]: labels  td[4]: Auth  td[5-15]: grades 1,1.5,2,3,4,5,6,7,8,9,10  td[16]: total
    #   Each pop cell has 3 <div>s: [grade_pop, plus_pop, qualifier_pop] - we want the first
    cards = page.evaluate("""() => {
        var results = [];
        var rows = document.querySelectorAll("table tbody tr");

        for (var i = 0; i < rows.length; i++) {
            var cells = rows[i].querySelectorAll("td");
            if (cells.length < 10) continue;

            var numCell = cells[1] ? cells[1].textContent.trim() : "";
            var nameCell = cells[2];
            var cardName = "";
            var variation = "";

            if (nameCell) {
                var strong = nameCell.querySelector("strong");
                cardName = strong ? strong.textContent.trim() : nameCell.textContent.trim();
                var shopIdx = cardName.indexOf("Shop with");
                if (shopIdx > 0) cardName = cardName.substring(0, shopIdx).trim();
                var br = nameCell.querySelector("br");
                if (br && br.nextSibling) {
                    var varText = br.nextSibling.textContent || "";
                    var shopIdx2 = varText.indexOf("Shop with");
                    variation = shopIdx2 > 0 ? varText.substring(0, shopIdx2).trim() : varText.trim();
                }
            }

            if (cardName === "" || cardName === "TOTAL POPULATION") continue;

            var pops = [];
            for (var j = 4; j < cells.length; j++) {
                var divs = cells[j].querySelectorAll("div");
                var val = 0;
                if (divs.length > 0) {
                    var raw = divs[0].textContent.trim().replace(",", "");
                    val = parseInt(raw) || 0;
                } else {
                    var raw2 = cells[j].textContent.trim().replace(",", "");
                    val = parseInt(raw2) || 0;
                }
                pops.push(val);
            }

            results.push({
                card_number: numCell,
                card_name: cardName,
                variation: variation || null,
                pops: pops
            });
        }

        return results;
    }""")

    ctx.close()

    if not cards:
        logger.warning(f"  No card data extracted for {set_name}")
        return []

    parsed = []
    now = datetime.now().isoformat()
    for card in cards:
        pops = card['pops']
        while len(pops) < 13:
            pops.append(0)
        # pops: [auth, gr1, gr1.5, gr2, gr3, gr4, gr5, gr6, gr7, gr8, gr9, gr10, total]
        parsed.append({
            'set_id': set_id,
            'card_name': card['card_name'],
            'card_number': card['card_number'] if card['card_number'] != 'N/A' else None,
            'variation': card['variation'],
            'pop_auth': pops[0],
            'pop_1': pops[1],
            'pop_2': pops[3],   # skip 1.5 (index 2)
            'pop_3': pops[4],
            'pop_4': pops[5],
            'pop_5': pops[6],
            'pop_6': pops[7],
            'pop_7': pops[8],
            'pop_8': pops[9],
            'pop_9': pops[10],
            'pop_10': pops[11],
            'total_graded': pops[12] if len(pops) > 12 else sum(pops[:12]),
            'category': category,
            'year': year,
            'set_name': set_name,
            'scraped_at': now,
        })

    logger.info(f"  Parsed {len(parsed)} cards from {set_name}")
    return parsed



def save_cards(cards):
    """Save cards to database."""
    if not cards:
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for card in cards:
        c.execute('''INSERT OR REPLACE INTO cards
            (set_id, card_name, card_number, variation,
             pop_auth, pop_1, pop_2, pop_3, pop_4, pop_5, pop_6, pop_7, pop_8, pop_9, pop_10,
             total_graded, category, year, set_name, scraped_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (card['set_id'], card['card_name'], card['card_number'], card['variation'],
             card['pop_auth'], card['pop_1'], card['pop_2'], card['pop_3'], card['pop_4'],
             card['pop_5'], card['pop_6'], card['pop_7'], card['pop_8'], card['pop_9'], card['pop_10'],
             card['total_graded'], card['category'], card['year'], card['set_name'], card['scraped_at']))

    conn.commit()
    conn.close()
    logger.info(f"  Saved {len(cards)} cards to DB")


def save_sets(sets, category):
    """Save discovered sets to database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for s in sets:
        c.execute('''INSERT OR REPLACE INTO sets (set_id, name, year, category, url, scraped_at)
            VALUES (?,?,?,?,?,?)''',
            (s['set_id'], s['name'], s['year'], category, s['url'], datetime.now().isoformat()))
    conn.commit()
    conn.close()


def scrape_category(category='tcg', years=None):
    """Scrape all sets in a category for given years.

    Uses fresh browser contexts per page load to avoid Cloudflare
    bot detection on sequential requests.
    """
    from playwright.sync_api import sync_playwright

    cat_info = CATEGORIES.get(category)
    if not cat_info:
        logger.error(f"Unknown category: {category}")
        return

    if years is None:
        years = list(range(1999, 2027))

    init_db()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        total_cards = 0

        for year in years:
            sets = discover_year_sets(browser, cat_info['path'], cat_info['id'], year)
            if not sets:
                continue

            save_sets(sets, category)
            time.sleep(REQUEST_DELAY)

            for i, s in enumerate(sets):
                cards = scrape_set_page(browser, s['url'], s['set_id'], s['name'], category, year)
                if cards:
                    save_cards(cards)
                    total_cards += len(cards)

                    # Update set card count
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute('UPDATE sets SET card_count=?, scraped_at=? WHERE set_id=?',
                                (len(cards), datetime.now().isoformat(), s['set_id']))
                    conn.commit()
                    conn.close()

                logger.info(f"  [{i+1}/{len(sets)}] {year} - Total so far: {total_cards}")
                time.sleep(REQUEST_DELAY)

        browser.close()

    logger.info(f"Category {category} complete: {total_cards} total cards")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='PSA Pop Report Scraper (Playwright)')
    parser.add_argument('--category', '-c', choices=list(CATEGORIES.keys()) + ['all'], default='tcg',
                       help='Category to scrape')
    parser.add_argument('--years', '-y', type=str, default=None,
                       help='Year range (e.g., "1999-2005" or "2024")')
    parser.add_argument('--stats', action='store_true', help='Show database stats')

    args = parser.parse_args()

    if args.stats:
        if not os.path.exists(DB_PATH):
            print("No PSA database yet")
            return
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
        sets_count = conn.execute('SELECT COUNT(*) FROM sets').fetchone()[0]
        print(f"\n=== PSA Database ===")
        print(f"Cards: {total:,}")
        print(f"Sets:  {sets_count:,}")
        cats = conn.execute('SELECT category, COUNT(*) FROM cards GROUP BY category ORDER BY COUNT(*) DESC').fetchall()
        for cat, cnt in cats:
            print(f"  {cat}: {cnt:,}")
        yrs = conn.execute('SELECT year, COUNT(*) FROM cards GROUP BY year ORDER BY year').fetchall()
        print(f"\nYears scraped:")
        for yr, cnt in yrs:
            print(f"  {yr}: {cnt:,}")
        conn.close()
        return

    years = None
    if args.years:
        if '-' in args.years:
            start, end = args.years.split('-')
            years = list(range(int(start), int(end) + 1))
        else:
            years = [int(args.years)]

    if args.category == 'all':
        for cat in CATEGORIES:
            scrape_category(cat, years)
    else:
        scrape_category(args.category, years)


if __name__ == '__main__':
    main()
