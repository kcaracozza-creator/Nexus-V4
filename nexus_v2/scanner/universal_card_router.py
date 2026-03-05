#!/usr/bin/env python3
"""
NEXUS UNIVERSAL CARD ROUTER
============================
The BRAIN that makes ZERO-SORT work.

Drop 100 random cards → Get 100 identified cards
MTG, Pokemon, Yu-Gi-Oh, Sports - ALL OF IT.

FLOW:
1. Card type detected from BACK (detect_card_type)
2. OCR runs on FRONT (multi_pass_ocr)
3. THIS MODULE routes to correct API based on type
4. Returns unified result format

Author: Kevin Caracozza / NEXUS Project
Patent Pending - November 2025
"""

import os
import re
import json
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from datetime import datetime

import requests

# Flow 9: Market data reporting
try:
    from nexus_v2.integrations.market_data_client import report_scan
    MARKET_DATA_AVAILABLE = True
except ImportError:
    MARKET_DATA_AVAILABLE = False

logger = logging.getLogger('NEXUS-Router')

# =============================================================================
# UNIFIED RESULT FORMAT
# =============================================================================
@dataclass
class UnifiedCardResult:
    """Unified result format for ANY card type"""
    # Core identification
    name: str
    card_type: str  # mtg, pokemon, yugioh, sports_baseball, etc.
    
    # Set/Product info
    set_code: Optional[str] = None
    set_name: Optional[str] = None
    card_number: Optional[str] = None
    year: Optional[int] = None
    
    # Pricing
    price_usd: Optional[float] = None
    price_source: Optional[str] = None
    
    # Additional metadata
    rarity: Optional[str] = None
    image_url: Optional[str] = None
    
    # Confidence & source
    confidence: int = 0  # 0-100
    api_source: Optional[str] = None
    raw_data: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# API CONFIGURATION
# =============================================================================
SCRYFALL_API = "https://api.scryfall.com"
POKEMON_API = "https://api.pokemontcg.io/v2"
YUGIOH_API = "https://db.ygoprodeck.com/api/v7"
ZYLA_API = "https://zylalabs.com/api"  # Sports cards (needs API key)

# Zultan GPU server (10TB HDD) - Sports card cache
ZULTAN_API = "http://192.168.1.152:8000"
TCDB_CACHE_PATH = "/opt/nexus/sports_cards/tcdb_cache.db"  # Path on Zultan
LOCAL_TCDB_PATH = None  # No local copy - always query Zultan

# Request timeout
API_TIMEOUT = 10


# =============================================================================
# MTG IDENTIFICATION (Scryfall) - ALREADY WORKING
# =============================================================================
def identify_mtg(ocr_results: List[str], set_code: Optional[str] = None,
                 collector_num: Optional[str] = None) -> Tuple[Optional[UnifiedCardResult], int]:
    """
    Identify MTG card using Scryfall API.
    This is the existing working code, now returning unified format.
    """
    if not ocr_results:
        return None, 0
    
    # Try each OCR result
    for text in ocr_results:
        if not text or len(text) < 3:
            continue
        
        try:
            # Exact printing lookup if we have set code
            if set_code and collector_num:
                r = requests.get(
                    f"{SCRYFALL_API}/cards/{set_code.lower()}/{collector_num}",
                    timeout=API_TIMEOUT
                )
                if r.status_code == 200:
                    card = r.json()
                    return _scryfall_to_unified(card), 95
            
            # Fuzzy name search
            r = requests.get(
                f"{SCRYFALL_API}/cards/named",
                params={'fuzzy': text},
                timeout=API_TIMEOUT
            )
            
            if r.status_code == 200:
                card = r.json()
                name = card.get('name', '')
                ratio = SequenceMatcher(None, text.lower(), name.lower()).ratio()
                confidence = int(ratio * 100)
                return _scryfall_to_unified(card), confidence
                
        except Exception as e:
            logger.debug(f"Scryfall error for '{text}': {e}")
            continue
    
    return None, 0


def _scryfall_to_unified(card: Dict) -> UnifiedCardResult:
    """Convert Scryfall response to unified format"""
    prices = card.get('prices', {})
    price = None
    for key in ['usd', 'usd_foil', 'eur']:
        if prices.get(key):
            try:
                price = float(prices[key])
                break
            except:
                pass
    
    return UnifiedCardResult(
        name=card.get('name', ''),
        card_type='mtg',
        set_code=(card.get('set') or '').upper(),
        set_name=card.get('set_name'),
        card_number=card.get('collector_number'),
        year=None,  # Scryfall doesn't give year directly
        price_usd=price,
        price_source='scryfall',
        rarity=card.get('rarity'),
        image_url=(card.get('image_uris') or {}).get('normal'),
        api_source='scryfall',
        raw_data=card
    )


# =============================================================================
# POKEMON IDENTIFICATION (pokemontcg.io)
# =============================================================================
def identify_pokemon(ocr_results: List[str], set_code: Optional[str] = None) -> Tuple[Optional[UnifiedCardResult], int]:
    """
    Identify Pokemon card using pokemontcg.io API.
    Free tier: 1000 requests/day without key, 20000/day with key.
    """
    if not ocr_results:
        return None, 0
    
    for text in ocr_results:
        if not text or len(text) < 3:
            continue
        
        try:
            # Search by name
            params = {'q': f'name:"{text}"'}
            if set_code:
                params['q'] += f' set.id:{set_code.lower()}'
            
            r = requests.get(
                f"{POKEMON_API}/cards",
                params=params,
                timeout=API_TIMEOUT
            )
            
            if r.status_code == 200:
                data = r.json()
                cards = data.get('data', [])
                
                if cards:
                    # Find best match
                    best_card = None
                    best_ratio = 0
                    
                    for card in cards[:10]:  # Check top 10
                        name = card.get('name', '')
                        ratio = SequenceMatcher(None, text.lower(), name.lower()).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_card = card
                    
                    if best_card and best_ratio > 0.6:
                        confidence = int(best_ratio * 100)
                        return _pokemon_to_unified(best_card), confidence
                        
        except Exception as e:
            logger.debug(f"Pokemon API error for '{text}': {e}")
            continue
    
    return None, 0


def _pokemon_to_unified(card: Dict) -> UnifiedCardResult:
    """Convert Pokemon TCG response to unified format"""
    # Get price from tcgplayer data
    price = None
    tcgplayer = card.get('tcgplayer', {})
    prices = tcgplayer.get('prices', {})
    
    # Try different price types
    for price_type in ['holofoil', 'reverseHolofoil', 'normal', '1stEditionHolofoil']:
        if price_type in prices:
            market = prices[price_type].get('market')
            if market:
                price = market
                break
    
    set_data = card.get('set', {})
    
    return UnifiedCardResult(
        name=card.get('name', ''),
        card_type='pokemon',
        set_code=set_data.get('id', '').upper(),
        set_name=set_data.get('name'),
        card_number=card.get('number'),
        year=int(set_data.get('releaseDate', '')[:4]) if set_data.get('releaseDate') else None,
        price_usd=price,
        price_source='tcgplayer',
        rarity=card.get('rarity'),
        image_url=(card.get('images') or {}).get('large'),
        api_source='pokemontcg.io',
        raw_data=card
    )


# =============================================================================
# YU-GI-OH IDENTIFICATION (YGOProDeck)
# =============================================================================
def identify_yugioh(ocr_results: List[str]) -> Tuple[Optional[UnifiedCardResult], int]:
    """
    Identify Yu-Gi-Oh card using YGOProDeck API.
    Free API, no key required.
    """
    if not ocr_results:
        return None, 0
    
    for text in ocr_results:
        if not text or len(text) < 3:
            continue
        
        try:
            # Fuzzy name search
            r = requests.get(
                f"{YUGIOH_API}/cardinfo.php",
                params={'fname': text},
                timeout=API_TIMEOUT
            )
            
            if r.status_code == 200:
                data = r.json()
                cards = data.get('data', [])
                
                if cards:
                    # Find best match
                    best_card = None
                    best_ratio = 0
                    
                    for card in cards[:10]:
                        name = card.get('name', '')
                        ratio = SequenceMatcher(None, text.lower(), name.lower()).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_card = card
                    
                    if best_card and best_ratio > 0.6:
                        confidence = int(best_ratio * 100)
                        return _yugioh_to_unified(best_card), confidence
                        
        except Exception as e:
            logger.debug(f"YGOProDeck error for '{text}': {e}")
            continue
    
    return None, 0


def _yugioh_to_unified(card: Dict) -> UnifiedCardResult:
    """Convert YGOProDeck response to unified format"""
    # Get price from card_prices
    price = None
    card_prices = card.get('card_prices', [{}])[0]
    for source in ['tcgplayer_price', 'cardmarket_price', 'ebay_price']:
        if card_prices.get(source):
            try:
                price = float(card_prices[source])
                if price > 0:
                    break
            except:
                pass
    
    # Get first set info
    card_sets = card.get('card_sets', [])
    set_info = card_sets[0] if card_sets else {}
    
    # Get image
    images = card.get('card_images', [{}])[0]
    
    return UnifiedCardResult(
        name=card.get('name', ''),
        card_type='yugioh',
        set_code=set_info.get('set_code'),
        set_name=set_info.get('set_name'),
        card_number=set_info.get('set_code'),  # YGO uses set_code as number
        year=None,
        price_usd=price,
        price_source='tcgplayer',
        rarity=set_info.get('set_rarity'),
        image_url=images.get('image_url'),
        api_source='ygoprodeck',
        raw_data=card
    )


# =============================================================================
# SPORTS CARD IDENTIFICATION (TCDB Cache + Zyla API)
# =============================================================================
def identify_sports(ocr_results: List[str], sport: str = 'unknown',
                    year: Optional[int] = None) -> Tuple[Optional[UnifiedCardResult], int]:
    """
    Identify sports card using local TCDB cache first, then Zyla API.
    
    Args:
        ocr_results: OCR text from card (player name, etc.)
        sport: baseball, basketball, football, hockey, or unknown
        year: Card year if detected
    """
    if not ocr_results:
        return None, 0
    
    # Try local TCDB cache first (fast + free)
    result, confidence = _lookup_tcdb_cache(ocr_results, sport, year)
    if result and confidence >= 70:
        return result, confidence
    
    # Fall back to manual mode for now
    # TODO: Add Zyla API integration when subscribed
    
    # Return partial result if we have player name
    for text in ocr_results:
        if text and len(text) >= 3:
            return UnifiedCardResult(
                name=text,
                card_type=f'sports_{sport}' if sport != 'unknown' else 'sports',
                year=year,
                confidence=30,
                api_source='ocr_only',
                price_source=None
            ), 30
    
    return None, 0


def _lookup_tcdb_cache(ocr_results: List[str], sport: str,
                       year: Optional[int]) -> Tuple[Optional[UnifiedCardResult], int]:
    """Look up card via Zultan API (10TB HDD with TCDB cache)"""

    for text in ocr_results:
        if not text or len(text) < 3:
            continue

        try:
            # Query Zultan's sports card lookup API
            params = {'query': text}
            if sport and sport != 'unknown':
                params['sport'] = sport
            if year:
                params['year'] = year

            response = requests.get(
                f"{ZULTAN_API}/api/sports/lookup",
                params=params,
                timeout=API_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('cards') and len(data['cards']) > 0:
                    # Find best match
                    best = data['cards'][0]
                    name_similarity = SequenceMatcher(
                        None, text.lower(), best.get('name', '').lower()
                    ).ratio()

                    if name_similarity >= 0.6:
                        return UnifiedCardResult(
                            name=best.get('name', text),
                            card_type=f"sports_{best.get('sport', sport)}",
                            set_code=best.get('set_id'),
                            set_name=best.get('set_name'),
                            card_number=best.get('card_number'),
                            year=best.get('year', year),
                            confidence=int(name_similarity * 100),
                            api_source='tcdb_zultan',
                            raw_data=best
                        ), int(name_similarity * 100)
        except requests.RequestException as e:
            logger.debug(f"Zultan API error: {e}")
            continue

    # Fallback: try local SQLite if it exists
    for db_path in [TCDB_CACHE_PATH, LOCAL_TCDB_PATH]:
        if db_path and os.path.exists(db_path):
            return _lookup_tcdb_local(ocr_results, sport, year, db_path)

    return None, 0


def _lookup_tcdb_local(ocr_results: List[str], sport: str,
                       year: Optional[int], db_path: str) -> Tuple[Optional[UnifiedCardResult], int]:
    """Fallback: Local SQLite lookup"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for text in ocr_results:
            if not text or len(text) < 3:
                continue

            conditions = ["name LIKE ?"]
            params = [f"%{text}%"]

            if sport and sport != 'unknown':
                conditions.append("sport = ?")
                params.append(sport)

            if year:
                conditions.append("year = ?")
                params.append(year)

            sql = f"""
                SELECT * FROM cards
                WHERE {' AND '.join(conditions)}
                LIMIT 20
            """

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            if rows:
                # Find best match
                best_row = None
                best_ratio = 0
                
                for row in rows:
                    name = row['name'] or ''
                    ratio = SequenceMatcher(None, text.lower(), name.lower()).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_row = row
                
                if best_row and best_ratio > 0.6:
                    conn.close()
                    confidence = int(best_ratio * 100)
                    return _tcdb_to_unified(dict(best_row)), confidence
        
        conn.close()
        
    except Exception as e:
        logger.error(f"TCDB lookup error: {e}")
    
    return None, 0


def _tcdb_to_unified(card: Dict) -> UnifiedCardResult:
    """Convert TCDB cache row to unified format"""
    return UnifiedCardResult(
        name=card.get('name', ''),
        card_type=f"sports_{card.get('sport', 'unknown')}",
        set_code=card.get('set_id'),
        set_name=None,  # Would need join with sets table
        card_number=card.get('card_number'),
        year=card.get('year'),
        price_usd=None,  # TCDB cache doesn't have prices
        price_source=None,
        rarity=card.get('variant'),
        image_url=card.get('image_url_front'),
        api_source='tcdb_cache',
        raw_data=card
    )


# =============================================================================
# MAIN ROUTER - THE BRAIN
# =============================================================================
def identify_card_universal(ocr_results: List[str], 
                            card_type: str,
                            set_code: Optional[str] = None,
                            collector_num: Optional[str] = None,
                            year: Optional[int] = None) -> Tuple[Optional[Dict], int]:
    """
    UNIVERSAL CARD IDENTIFICATION ROUTER
    
    This is THE function that makes NEXUS work.
    Drop 100 random cards → Get 100 identified cards.
    
    Args:
        ocr_results: List of OCR text candidates from card front
        card_type: Detected card type from back ('mtg', 'pokemon', 'yugioh', 
                   'sports_baseball', 'sports_basketball', 'sports_football',
                   'sports_hockey', 'sports_unknown', 'unknown')
        set_code: Optional set code if detected
        collector_num: Optional collector number if detected
        year: Optional year if detected from card
    
    Returns:
        (card_dict, confidence) - Card data dict and confidence 0-100
    """
    logger.info(f"=== UNIVERSAL ROUTER === type={card_type}, ocr={ocr_results[:2] if ocr_results else []}")
    
    result = None
    confidence = 0
    
    # Route based on detected card type
    if card_type == 'mtg':
        result, confidence = identify_mtg(ocr_results, set_code, collector_num)
        
    elif card_type == 'pokemon':
        result, confidence = identify_pokemon(ocr_results, set_code)
        
    elif card_type == 'yugioh':
        result, confidence = identify_yugioh(ocr_results)
        
    elif card_type.startswith('sports'):
        # Extract sport subcategory
        sport = 'unknown'
        if '_' in card_type:
            sport = card_type.split('_')[1]  # sports_baseball → baseball
        result, confidence = identify_sports(ocr_results, sport, year)
        
    elif card_type == 'unknown':
        # Try all APIs in order of likelihood
        result, confidence = _try_all_apis(ocr_results, set_code, collector_num)
    
    else:
        logger.warning(f"Unknown card type: {card_type}")
        result, confidence = _try_all_apis(ocr_results, set_code, collector_num)
    
    # Convert to dict for compatibility with existing code
    if result:
        card_dict = result.to_dict()
        logger.info(f"IDENTIFIED: {result.name} ({result.card_type}) - {confidence}%")
        
        # ============================================================
        # FLOW 9: Report scan event to ZULTAN (anonymous supply signal)
        # Fire-and-forget — never blocks identification pipeline
        # ============================================================
        if MARKET_DATA_AVAILABLE and confidence >= 70:
            try:
                report_scan(
                    card_name=result.name,
                    set_code=result.set_code,
                    card_type=result.card_type,
                    condition_estimate=None,  # Set later during grading
                    foil=False  # TODO: detect from scan
                )
            except Exception as e:
                logger.debug(f"Market data scan event failed (non-blocking): {e}")
        
        return card_dict, confidence
    
    logger.warning(f"FAILED TO IDENTIFY - type={card_type}")
    return None, 0


def _try_all_apis(ocr_results: List[str], 
                  set_code: Optional[str] = None,
                  collector_num: Optional[str] = None) -> Tuple[Optional[UnifiedCardResult], int]:
    """
    Try all APIs when card type is unknown.
    Order: MTG (most common) → Pokemon → Yu-Gi-Oh → Sports
    """
    # Try MTG first (most common in card shops)
    result, conf = identify_mtg(ocr_results, set_code, collector_num)
    if result and conf >= 70:
        return result, conf
    
    # Try Pokemon
    result, conf = identify_pokemon(ocr_results, set_code)
    if result and conf >= 70:
        return result, conf
    
    # Try Yu-Gi-Oh
    result, conf = identify_yugioh(ocr_results)
    if result and conf >= 70:
        return result, conf
    
    # Try Sports (local cache only)
    result, conf = identify_sports(ocr_results)
    if result and conf >= 50:
        return result, conf
    
    return None, 0


# =============================================================================
# BATCH IDENTIFICATION (For bulk scanning)
# =============================================================================
def identify_batch(cards: List[Dict]) -> List[Dict]:
    """
    Identify a batch of cards.
    
    Args:
        cards: List of dicts with keys:
            - ocr_results: List[str]
            - card_type: str
            - set_code: Optional[str]
            - image_path: Optional[str]
    
    Returns:
        List of identification results
    """
    results = []
    
    for i, card in enumerate(cards):
        ocr_results = card.get('ocr_results', [])
        card_type = card.get('card_type', 'unknown')
        set_code = card.get('set_code')
        collector_num = card.get('collector_num')
        year = card.get('year')
        
        identified, confidence = identify_card_universal(
            ocr_results, card_type, set_code, collector_num, year
        )
        
        results.append({
            'index': i,
            'input': card,
            'result': identified,
            'confidence': confidence,
            'status': 'identified' if confidence >= 70 else 'review' if confidence >= 50 else 'failed'
        })
    
    # Stats
    identified = sum(1 for r in results if r['status'] == 'identified')
    review = sum(1 for r in results if r['status'] == 'review')
    failed = sum(1 for r in results if r['status'] == 'failed')
    
    logger.info(f"BATCH COMPLETE: {identified} identified, {review} review, {failed} failed")
    
    return results


# =============================================================================
# LEGACY COMPATIBILITY - Drop-in replacement for identify_card()
# =============================================================================
def identify_card(ocr_results: List[str], 
                  set_code: Optional[str] = None,
                  collector_num: Optional[str] = None,
                  card_type: str = 'mtg') -> Tuple[Optional[Dict], int]:
    """
    Legacy compatibility wrapper.
    
    This matches the old identify_card() signature but uses universal routing.
    Default to MTG for backwards compatibility.
    """
    return identify_card_universal(ocr_results, card_type, set_code, collector_num)


# =============================================================================
# API STATUS CHECK
# =============================================================================
def check_api_status() -> Dict[str, bool]:
    """Check which APIs are available"""
    status = {}
    
    # Scryfall
    try:
        r = requests.get(f"{SCRYFALL_API}/cards/random", timeout=5)
        status['scryfall'] = r.status_code == 200
    except:
        status['scryfall'] = False
    
    # Pokemon TCG
    try:
        r = requests.get(f"{POKEMON_API}/cards?pageSize=1", timeout=5)
        status['pokemon_tcg'] = r.status_code == 200
    except:
        status['pokemon_tcg'] = False
    
    # YGOProDeck
    try:
        r = requests.get(f"{YUGIOH_API}/cardinfo.php?name=Dark Magician", timeout=5)
        status['ygoprodeck'] = r.status_code == 200
    except:
        status['ygoprodeck'] = False
    
    # TCDB Cache
    status['tcdb_cache'] = os.path.exists(TCDB_CACHE_PATH) or os.path.exists(LOCAL_TCDB_PATH)
    
    return status


# =============================================================================
# TEST
# =============================================================================
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("NEXUS UNIVERSAL CARD ROUTER - TEST")
    print("=" * 60)
    
    # Check API status
    print("\n📡 API STATUS:")
    status = check_api_status()
    for api, available in status.items():
        icon = "✅" if available else "❌"
        print(f"  {icon} {api}")
    
    # Test MTG
    print("\n🃏 TEST: MTG (Lightning Bolt)")
    result, conf = identify_card_universal(['Lightning Bolt'], 'mtg')
    if result:
        print(f"  ✅ {result['name']} - ${result.get('price_usd', 'N/A')} ({conf}%)")
    else:
        print("  ❌ Failed")
    
    # Test Pokemon
    print("\n⚡ TEST: Pokemon (Pikachu)")
    result, conf = identify_card_universal(['Pikachu'], 'pokemon')
    if result:
        print(f"  ✅ {result['name']} - ${result.get('price_usd', 'N/A')} ({conf}%)")
    else:
        print("  ❌ Failed")
    
    # Test Yu-Gi-Oh
    print("\n🌀 TEST: Yu-Gi-Oh (Dark Magician)")
    result, conf = identify_card_universal(['Dark Magician'], 'yugioh')
    if result:
        print(f"  ✅ {result['name']} - ${result.get('price_usd', 'N/A')} ({conf}%)")
    else:
        print("  ❌ Failed")
    
    # Test Unknown (should try all)
    print("\n❓ TEST: Unknown (Blue-Eyes White Dragon)")
    result, conf = identify_card_universal(['Blue-Eyes White Dragon'], 'unknown')
    if result:
        print(f"  ✅ {result['name']} ({result['card_type']}) - {conf}%")
    else:
        print("  ❌ Failed")
    
    print("\n" + "=" * 60)
    print("ROUTER TEST COMPLETE")
    print("=" * 60)
