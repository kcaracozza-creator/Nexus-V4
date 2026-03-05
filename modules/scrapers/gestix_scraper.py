#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestix.org Collection Scraper
Pulls MTG collection data with Scryfall IDs from Gestix.org
"""

import requests
import json
from typing import Dict, List, Optional
import time


class GestixScraper:
    """Scraper for Gestix.org card inventory"""
    
    def __init__(self):
        self.base_url = "https://gestix.org"
        self.api_url = "https://gestix.org/api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        print("[GESTIX] Scraper initialized")
    
    def login(self, username: str, password: str) -> bool:
        """
        Login to Gestix account
        
        Args:
            username: Gestix username/email
            password: Account password
            
        Returns:
            True if login successful
        """
        try:
            login_url = f"{self.api_url}/auth/login"
            payload = {
                'username': username,
                'password': password
            }
            
            response = self.session.post(login_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('token') or data.get('access_token')
                
                if token:
                    self.session.headers.update({
                        'Authorization': f'Bearer {token}'
                    })
                    print("[GESTIX] ✓ Login successful")
                    return True
            
            print(f"[GESTIX] Login failed: {response.status_code}")
            return False
            
        except Exception as e:
            print(f"[GESTIX] Login error: {e}")
            return False
    
    def get_collection(self, user_id: Optional[str] = None) -> List[Dict]:
        """
        Get ONLY user's Collection (scanned cards) - NOT wishlist/decks/trades
        
        Args:
            user_id: Optional user ID (uses authenticated user if None)
            
        Returns:
            List of card dictionaries with Scryfall data from Collection ONLY
        """
        try:
            # ONLY Collection endpoints - ignore wishlist, decks, trades, etc.
            endpoints = [
                f"{self.api_url}/collection",
                f"{self.api_url}/cards/collection",
                f"{self.api_url}/user/collection"
            ]
            
            if user_id:
                endpoints.extend([
                    f"{self.api_url}/user/{user_id}/collection",
                    f"{self.api_url}/collection/{user_id}"
                ])
            
            print("[GESTIX] Fetching COLLECTION ONLY (scanned cards)")
            
            for endpoint in endpoints:
                try:
                    print(f"[GESTIX] Trying endpoint: {endpoint}")
                    response = self.session.get(endpoint, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Handle different response formats
                        cards = []
                        if isinstance(data, list):
                            cards = data
                        elif isinstance(data, dict):
                            cards = (data.get('cards') or 
                                    data.get('collection') or 
                                    data.get('inventory') or 
                                    data.get('data') or [])
                        
                        if cards:
                            print(f"[GESTIX] ✓ Found {len(cards)} cards")
                            return self._normalize_cards(cards)
                    
                except requests.exceptions.RequestException as e:
                    print(f"[GESTIX] Endpoint failed: {e}")
                    continue
            
            print("[GESTIX] ⚠ No collection data found")
            return []
            
        except Exception as e:
            print(f"[GESTIX] Collection fetch error: {e}")
            return []
    
    def _normalize_cards(self, cards: List[Dict]) -> List[Dict]:
        """
        Normalize Gestix card data to standard format
        
        Args:
            cards: Raw card data from Gestix
            
        Returns:
            Normalized card list with Scryfall IDs
        """
        normalized = []
        
        for card in cards:
            try:
                # Extract card info (handle multiple field name variations)
                name = (card.get('name') or 
                       card.get('card_name') or 
                       card.get('cardName') or '')
                
                scryfall_id = (card.get('scryfall_id') or 
                             card.get('scryfallId') or 
                             card.get('id') or 
                             card.get('uuid') or '')
                
                set_code = (card.get('set') or 
                          card.get('set_code') or 
                          card.get('setCode') or 
                          card.get('edition') or '')
                
                quantity = int(card.get('quantity') or 
                             card.get('count') or 
                             card.get('qty') or 1)
                
                foil = card.get('foil', False)
                
                # Price data
                price = float(card.get('price') or 
                            card.get('market_price') or 
                            card.get('marketPrice') or 0.0)
                
                # Additional metadata
                rarity = card.get('rarity', '')
                collector_number = card.get('collector_number') or card.get('number', '')
                condition = card.get('condition', 'NM')
                language = card.get('language', 'en')
                
                normalized.append({
                    'name': name,
                    'scryfall_id': scryfall_id,
                    'set': set_code,
                    'quantity': quantity,
                    'foil': foil,
                    'price': price,
                    'rarity': rarity,
                    'collector_number': collector_number,
                    'condition': condition,
                    'language': language
                })
                
            except Exception as e:
                print(f"[GESTIX] Card normalization error: {e}")
                continue
        
        return normalized
    
    def export_to_csv(self, cards: List[Dict], output_path: str) -> bool:
        """
        Export collection to CSV format
        
        Args:
            cards: Card list from get_collection()
            output_path: Output CSV file path
            
        Returns:
            True if export successful
        """
        try:
            import csv
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Name', 'Scryfall ID', 'Set', 'Count', 'Foil', 
                    'Price', 'Rarity', 'Collector Number', 'Condition', 'Language'
                ])
                writer.writeheader()
                
                for card in cards:
                    writer.writerow({
                        'Name': card['name'],
                        'Scryfall ID': card['scryfall_id'],
                        'Set': card['set'],
                        'Count': card['quantity'],
                        'Foil': 'foil' if card['foil'] else '',
                        'Price': f"{card['price']:.2f}",
                        'Rarity': card['rarity'],
                        'Collector Number': card['collector_number'],
                        'Condition': card['condition'],
                        'Language': card['language']
                    })
            
            print(f"[GESTIX] ✓ Exported {len(cards)} cards to {output_path}")
            return True
            
        except Exception as e:
            print(f"[GESTIX] Export error: {e}")
            return False


def main():
    """Test Gestix scraper"""
    scraper = GestixScraper()
    
    # Get credentials
    print("\n=== GESTIX COLLECTION SCRAPER ===\n")
    username = input("Gestix Username/Email: ").strip()
    password = input("Gestix Password: ").strip()
    
    # Login
    if scraper.login(username, password):
        # Get collection
        cards = scraper.get_collection()
        
        if cards:
            print(f"\n✓ Retrieved {len(cards)} cards")
            print("\nSample cards:")
            for card in cards[:5]:
                print(f"  • {card['name']} ({card['set']}) - Qty: {card['quantity']}")
            
            # Export option
            export = input("\nExport to CSV? (y/n): ").strip().lower()
            if export == 'y':
                output_path = input("Output file path: ").strip() or "gestix_collection.csv"
                scraper.export_to_csv(cards, output_path)
        else:
            print("\n⚠ No cards found - check API endpoints or try manual export")
    else:
        print("\n⚠ Login failed - check credentials")


if __name__ == '__main__':
    main()
