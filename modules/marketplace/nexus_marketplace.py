#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS Marketplace - Internal peer-to-peer trading platform
Users can list cards for sale, browse listings, make offers, and complete transactions
"""

import json
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

class NexusMarketplace:
    """
    Internal marketplace for NEXUS users to buy/sell cards
    Features:
    - List cards for sale from your collection
    - Browse available listings from all users
    - Make offers and counter-offers
    - Seller ratings and reputation system
    - Transaction history and analytics
    - Integrated shipping label generation
    - Escrow system for secure transactions
    """
    
    def __init__(self, data_dir=r"E:\MTTGG\MARKETPLACE"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Data files
        self.listings_file = os.path.join(data_dir, "listings.json")
        self.transactions_file = os.path.join(data_dir, "transactions.json")
        self.offers_file = os.path.join(data_dir, "offers.json")
        self.users_file = os.path.join(data_dir, "users.json")
        self.watchlist_file = os.path.join(data_dir, "watchlist.json")
        
        # Load data
        self.listings = self.load_json(self.listings_file, {})
        self.transactions = self.load_json(self.transactions_file, [])
        self.offers = self.load_json(self.offers_file, {})
        self.users = self.load_json(self.users_file, {})
        self.watchlist = self.load_json(self.watchlist_file, {})
        
        # Current user (set by application)
        self.current_user = None
        
    def load_json(self, filepath, default):
        """Load JSON data with fallback"""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except:
                return default
        return default
    
    def save_json(self, filepath, data):
        """Save JSON data"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def set_user(self, username, email=None, location=None):
        """Set current user and initialize profile if needed"""
        self.current_user = username
        
        if username not in self.users:
            self.users[username] = {
                'username': username,
                'email': email or '',
                'location': location or '',
                'rating': 5.0,
                'total_sales': 0,
                'total_purchases': 0,
                'total_revenue': 0.0,
                'member_since': datetime.now().isoformat(),
                'verified': False,
                'trusted_seller': False
            }
            self.save_json(self.users_file, self.users)
        
        return self.users[username]
    
    def create_listing(self, card_data, price, quantity=1, condition='NM', notes=''):
        """
        Create a new marketplace listing
        
        Args:
            card_data: Dict with card info (name, set, collector_number, foil, etc.)
            price: Asking price in USD
            quantity: Number of copies available
            condition: Card condition (NM, LP, MP, HP, DMG)
            notes: Additional seller notes
        
        Returns:
            listing_id: Unique identifier for this listing
        """
        if not self.current_user:
            raise ValueError("No user set - call set_user() first")
        
        # Generate unique listing ID
        listing_id = self.generate_id('listing')
        
        listing = {
            'listing_id': listing_id,
            'seller': self.current_user,
            'card_name': card_data['name'],
            'set_code': card_data.get('set', 'UNK'),
            'set_name': card_data.get('set_name', ''),
            'collector_number': card_data.get('collector_number', ''),
            'foil': card_data.get('foil', False),
            'language': card_data.get('language', 'English'),
            'condition': condition,
            'price': float(price),
            'quantity': quantity,
            'notes': notes,
            'listed_date': datetime.now().isoformat(),
            'status': 'active',  # active, sold, cancelled, reserved
            'views': 0,
            'watchers': 0,
            'image_url': card_data.get('image_url', ''),
            'scryfall_id': card_data.get('id', '')
        }
        
        self.listings[listing_id] = listing
        self.save_json(self.listings_file, self.listings)
        
        return listing_id
    
    def search_listings(self, card_name=None, set_code=None, max_price=None, 
                       condition=None, foil=None, seller=None):
        """
        Search marketplace listings with filters
        
        Returns:
            List of matching listings sorted by price (lowest first)
        """
        results = []
        
        for listing_id, listing in self.listings.items():
            # Skip inactive listings
            if listing['status'] != 'active':
                continue
            
            # Apply filters
            if card_name and card_name.lower() not in listing['card_name'].lower():
                continue
            if set_code and listing['set_code'].upper() != set_code.upper():
                continue
            if max_price and listing['price'] > max_price:
                continue
            if condition and listing['condition'] != condition:
                continue
            if foil is not None and listing['foil'] != foil:
                continue
            if seller and listing['seller'] != seller:
                continue
            
            results.append(listing)
        
        # Sort by price (lowest first)
        results.sort(key=lambda x: x['price'])
        
        return results
    
    def get_listing(self, listing_id):
        """Get detailed listing info and increment view count"""
        if listing_id in self.listings:
            self.listings[listing_id]['views'] += 1
            self.save_json(self.listings_file, self.listings)
            return self.listings[listing_id]
        return None
    
    def make_offer(self, listing_id, offer_price, message=''):
        """
        Make an offer on a listing (buyer initiates)
        
        Returns:
            offer_id: Unique identifier for tracking this offer
        """
        if not self.current_user:
            raise ValueError("No user set")
        
        listing = self.get_listing(listing_id)
        if not listing:
            raise ValueError("Listing not found")
        
        if listing['seller'] == self.current_user:
            raise ValueError("Cannot make offer on your own listing")
        
        offer_id = self.generate_id('offer')
        
        offer = {
            'offer_id': offer_id,
            'listing_id': listing_id,
            'buyer': self.current_user,
            'seller': listing['seller'],
            'card_name': listing['card_name'],
            'offer_price': float(offer_price),
            'list_price': listing['price'],
            'message': message,
            'status': 'pending',  # pending, accepted, rejected, countered, expired
            'created_date': datetime.now().isoformat(),
            'expires_date': (datetime.now() + timedelta(days=3)).isoformat()
        }
        
        self.offers[offer_id] = offer
        self.save_json(self.offers_file, self.offers)
        
        return offer_id
    
    def respond_to_offer(self, offer_id, action, counter_price=None, message=''):
        """
        Seller responds to an offer
        
        Args:
            action: 'accept', 'reject', or 'counter'
            counter_price: Required if action='counter'
        """
        if offer_id not in self.offers:
            raise ValueError("Offer not found")
        
        offer = self.offers[offer_id]
        
        # Verify seller is responding
        if offer['seller'] != self.current_user:
            raise ValueError("Only seller can respond to offers")
        
        if action == 'accept':
            offer['status'] = 'accepted'
            # Create transaction
            transaction_id = self.create_transaction(offer['listing_id'], offer['buyer'], 
                                                    offer['offer_price'])
            offer['transaction_id'] = transaction_id
            
        elif action == 'reject':
            offer['status'] = 'rejected'
            offer['rejection_message'] = message
            
        elif action == 'counter':
            if counter_price is None:
                raise ValueError("Counter price required")
            offer['status'] = 'countered'
            offer['counter_price'] = float(counter_price)
            offer['counter_message'] = message
            
        offer['response_date'] = datetime.now().isoformat()
        self.save_json(self.offers_file, self.offers)
        
        return offer
    
    def buy_now(self, listing_id, quantity=1):
        """
        Instant purchase at listing price (no offer)
        
        Returns:
            transaction_id: Unique transaction identifier
        """
        if not self.current_user:
            raise ValueError("No user set")
        
        listing = self.get_listing(listing_id)
        if not listing:
            raise ValueError("Listing not found")
        
        if listing['seller'] == self.current_user:
            raise ValueError("Cannot buy your own listing")
        
        if quantity > listing['quantity']:
            raise ValueError(f"Only {listing['quantity']} available")
        
        # Create transaction
        total_price = listing['price'] * quantity
        transaction_id = self.create_transaction(listing_id, self.current_user, 
                                                 total_price, quantity)
        
        # Update listing quantity or mark sold
        listing['quantity'] -= quantity
        if listing['quantity'] == 0:
            listing['status'] = 'sold'
        
        self.save_json(self.listings_file, self.listings)
        
        return transaction_id
    
    def create_transaction(self, listing_id, buyer, price, quantity=1):
        """
        Create a transaction record (purchase confirmed)
        """
        listing = self.listings[listing_id]
        transaction_id = self.generate_id('txn')
        
        transaction = {
            'transaction_id': transaction_id,
            'listing_id': listing_id,
            'seller': listing['seller'],
            'buyer': buyer,
            'card_name': listing['card_name'],
            'set_code': listing['set_code'],
            'condition': listing['condition'],
            'quantity': quantity,
            'price': float(price),
            'status': 'pending_payment',  # pending_payment, paid, shipped, delivered, completed, disputed
            'created_date': datetime.now().isoformat(),
            'payment_method': None,
            'tracking_number': None,
            'shipping_carrier': None,
            'buyer_rating': None,
            'seller_rating': None
        }
        
        self.transactions.append(transaction)
        self.save_json(self.transactions_file, self.transactions)
        
        # Update user stats
        self.users[listing['seller']]['total_sales'] += 1
        self.users[listing['seller']]['total_revenue'] += price
        self.users[buyer]['total_purchases'] += 1
        self.save_json(self.users_file, self.users)
        
        return transaction_id
    
    def update_transaction_status(self, transaction_id, status, **kwargs):
        """
        Update transaction status
        
        Status flow:
        pending_payment -> paid -> shipped -> delivered -> completed
        """
        for txn in self.transactions:
            if txn['transaction_id'] == transaction_id:
                txn['status'] = status
                txn['last_updated'] = datetime.now().isoformat()
                
                # Update optional fields
                for key, value in kwargs.items():
                    txn[key] = value
                
                self.save_json(self.transactions_file, self.transactions)
                return txn
        
        raise ValueError("Transaction not found")
    
    def add_tracking(self, transaction_id, carrier, tracking_number):
        """Add shipping tracking to transaction"""
        return self.update_transaction_status(
            transaction_id, 
            'shipped',
            shipping_carrier=carrier,
            tracking_number=tracking_number,
            shipped_date=datetime.now().isoformat()
        )
    
    def rate_transaction(self, transaction_id, rating, review=''):
        """
        Rate a completed transaction (1-5 stars)
        Updates user reputation
        """
        txn = None
        for t in self.transactions:
            if t['transaction_id'] == transaction_id:
                txn = t
                break
        
        if not txn:
            raise ValueError("Transaction not found")
        
        # Determine if rating as buyer or seller
        if self.current_user == txn['buyer']:
            txn['seller_rating'] = rating
            txn['seller_review'] = review
            rated_user = txn['seller']
        elif self.current_user == txn['seller']:
            txn['buyer_rating'] = rating
            txn['buyer_review'] = review
            rated_user = txn['buyer']
        else:
            raise ValueError("Not authorized to rate this transaction")
        
        # Update user rating (weighted average)
        user = self.users[rated_user]
        total_ratings = user['total_sales'] + user['total_purchases']
        current_rating = user['rating']
        
        # Calculate new weighted average
        new_rating = ((current_rating * (total_ratings - 1)) + rating) / total_ratings
        user['rating'] = round(new_rating, 2)
        
        # Award trusted seller badge if 50+ sales with 4.8+ rating
        if user['total_sales'] >= 50 and user['rating'] >= 4.8:
            user['trusted_seller'] = True
        
        self.save_json(self.transactions_file, self.transactions)
        self.save_json(self.users_file, self.users)
        
        return user['rating']
    
    def add_to_watchlist(self, listing_id):
        """Add listing to user's watchlist"""
        if not self.current_user:
            return False
        
        if self.current_user not in self.watchlist:
            self.watchlist[self.current_user] = []
        
        if listing_id not in self.watchlist[self.current_user]:
            self.watchlist[self.current_user].append(listing_id)
            
            # Increment watcher count
            if listing_id in self.listings:
                self.listings[listing_id]['watchers'] += 1
                self.save_json(self.listings_file, self.listings)
            
            self.save_json(self.watchlist_file, self.watchlist)
            return True
        
        return False
    
    def get_my_listings(self):
        """Get all listings by current user"""
        if not self.current_user:
            return []
        
        return [listing for listing in self.listings.values() 
                if listing['seller'] == self.current_user]
    
    def get_my_purchases(self):
        """Get all purchases by current user"""
        if not self.current_user:
            return []
        
        return [txn for txn in self.transactions 
                if txn['buyer'] == self.current_user]
    
    def get_my_sales(self):
        """Get all sales by current user"""
        if not self.current_user:
            return []
        
        return [txn for txn in self.transactions 
                if txn['seller'] == self.current_user]
    
    def get_pending_offers(self):
        """Get offers for current user (as buyer or seller)"""
        if not self.current_user:
            return []
        
        return [offer for offer in self.offers.values()
                if (offer['buyer'] == self.current_user or offer['seller'] == self.current_user)
                and offer['status'] in ['pending', 'countered']]
    
    def get_marketplace_stats(self):
        """Get overall marketplace statistics"""
        total_listings = len([l for l in self.listings.values() if l['status'] == 'active'])
        total_sales = len([t for t in self.transactions if t['status'] == 'completed'])
        total_volume = sum(t['price'] for t in self.transactions if t['status'] == 'completed')
        
        # Most popular cards
        card_counts = defaultdict(int)
        for listing in self.listings.values():
            if listing['status'] == 'active':
                card_counts[listing['card_name']] += 1
        
        popular_cards = sorted(card_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Average prices by card
        card_prices = defaultdict(list)
        for listing in self.listings.values():
            if listing['status'] == 'active':
                card_prices[listing['card_name']].append(listing['price'])
        
        return {
            'total_active_listings': total_listings,
            'total_completed_sales': total_sales,
            'total_volume': round(total_volume, 2),
            'average_sale': round(total_volume / total_sales if total_sales > 0 else 0, 2),
            'total_users': len(self.users),
            'popular_cards': popular_cards,
            'average_prices': {card: round(sum(prices)/len(prices), 2) 
                             for card, prices in card_prices.items()}
        }
    
    def generate_id(self, prefix):
        """Generate unique ID with timestamp and hash"""
        timestamp = int(time.time() * 1000)
        random_str = os.urandom(8).hex()
        return f"{prefix}_{timestamp}_{random_str[:8]}"
    
    def cancel_listing(self, listing_id):
        """Cancel a listing (seller only)"""
        if listing_id not in self.listings:
            raise ValueError("Listing not found")
        
        listing = self.listings[listing_id]
        
        if listing['seller'] != self.current_user:
            raise ValueError("Only seller can cancel listing")
        
        listing['status'] = 'cancelled'
        listing['cancelled_date'] = datetime.now().isoformat()
        self.save_json(self.listings_file, self.listings)
        
        return True
    
    def get_user_profile(self, username):
        """Get public profile for any user"""
        if username not in self.users:
            return None
        
        user = self.users[username].copy()
        
        # Add calculated stats
        user['completed_sales'] = len([t for t in self.transactions 
                                      if t['seller'] == username and t['status'] == 'completed'])
        user['completed_purchases'] = len([t for t in self.transactions 
                                          if t['buyer'] == username and t['status'] == 'completed'])
        
        return user
    
    def search_users(self, query):
        """Search users by username"""
        results = []
        query_lower = query.lower()
        
        for username, user_data in self.users.items():
            if query_lower in username.lower():
                results.append(self.get_user_profile(username))
        
        return results


if __name__ == "__main__":
    # Test marketplace functionality
    marketplace = NexusMarketplace()
    
    # Setup test users
    marketplace.set_user("Kyle", "kyle@nexus.com", "Pennsylvania")
    
    # Create a test listing
    test_card = {
        'name': 'Black Lotus',
        'set': 'LEA',
        'set_name': 'Limited Edition Alpha',
        'collector_number': '232',
        'foil': False,
        'language': 'English'
    }
    
    listing_id = marketplace.create_listing(
        test_card,
        price=25000.00,
        condition='NM',
        notes='Mint condition, professionally graded BGS 9.5'
    )
    
    print(f"✅ Created listing: {listing_id}")
    
    # Search listings
    results = marketplace.search_listings(card_name="Black Lotus")
    print(f"✅ Found {len(results)} listings for Black Lotus")
    
    # Get stats
    stats = marketplace.get_marketplace_stats()
    print(f"✅ Marketplace stats: {stats['total_active_listings']} active listings")
