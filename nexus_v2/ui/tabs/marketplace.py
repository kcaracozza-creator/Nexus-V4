#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS V2 - Marketplace Tab
Connected to live NEXUS marketplace server on Zultan
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import json
import os
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from nexus_v2.integrations.marketplace_client import MarketplaceClient

class NexusMarketplace:
    """Internal marketplace for peer-to-peer trading"""
    
    def __init__(self):
        self.listings = []
        self.transactions = []
        self.users = {}
        self.current_user = None
        self.watchlist = []
        self.data_file = Path("data/marketplace/marketplace.json")
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.load_marketplace_data()
        
    def set_user(self, username, email, location):
        """Set current user"""
        self.current_user = username
        if username not in self.users:
            self.users[username] = {
                'username': username,
                'email': email,
                'location': location,
                'rating': 5.0,
                'completed_sales': 0,
                'completed_purchases': 0,
                'total_revenue': 0.0,
                'member_since': datetime.now().isoformat(),
                'trusted_seller': False
            }
            
    def create_listing(self, card_name, set_name, price, condition, description=""):
        """Create new marketplace listing"""
        listing = {
            'id': f"L{len(self.listings) + 1:04d}",
            'seller': self.current_user,
            'card_name': card_name,
            'set_name': set_name,
            'price': float(price),
            'condition': condition,
            'description': description,
            'created_date': datetime.now().isoformat(),
            'status': 'active',
            'views': 0,
            'watchers': []
        }
        self.listings.append(listing)
        self.save_marketplace_data()
        return listing
        
    def search_listings(self, card_name="", set_name="", max_price=None):
        """Search marketplace listings"""
        results = []
        for listing in self.listings:
            if listing['status'] != 'active':
                continue
                
            # Apply filters
            if card_name and card_name.lower() not in listing['card_name'].lower():
                continue
            if set_name and set_name.upper() != listing['set_name'].upper():
                continue
            if max_price and listing['price'] > max_price:
                continue
                
            results.append(listing)
            
        return sorted(results, key=lambda x: x['price'])
        
    def buy_listing(self, listing_id, buyer):
        """Purchase a listing"""
        for listing in self.listings:
            if listing['id'] == listing_id and listing['status'] == 'active':
                # Create transaction
                transaction = {
                    'transaction_id': f"T{len(self.transactions) + 1:04d}",
                    'listing_id': listing_id,
                    'card_name': listing['card_name'],
                    'seller': listing['seller'],
                    'buyer': buyer,
                    'price': listing['price'],
                    'created_date': datetime.now().isoformat(),
                    'status': 'pending_payment'
                }
                
                self.transactions.append(transaction)
                listing['status'] = 'sold'
                
                # Update user stats
                if listing['seller'] in self.users:
                    self.users[listing['seller']]['completed_sales'] += 1
                    self.users[listing['seller']]['total_revenue'] += listing['price']
                    
                if buyer in self.users:
                    self.users[buyer]['completed_purchases'] += 1
                    
                self.save_marketplace_data()
                
                # ==========================================
                # PHONE HOME TO NEXUS HQ
                # ==========================================
                try:
                    from phone_home import report_card_sale
                    hq_result = report_card_sale(
                        card_name=listing['card_name'],
                        price=listing['price'],
                        quantity=1,
                        set_code=listing.get('set_name', ''),
                        condition=listing.get('condition', 'NM')
                    )
                    if hq_result.get('success'):
                        print(f"📡 Phoned home: {listing['card_name']} ${listing['price']:.2f}")
                except Exception as e:
                    print(f"⚠️ Phone home failed: {e}")
                
                return transaction
                
        return None
        
    def get_my_listings(self, username):
        """Get user's active listings"""
        return [l for l in self.listings if l['seller'] == username]
        
    def get_marketplace_stats(self):
        """Get marketplace statistics"""
        active_listings = len([l for l in self.listings if l['status'] == 'active'])
        completed_sales = len([t for t in self.transactions if t['status'] == 'completed'])
        
        total_volume = sum(t['price'] for t in self.transactions if t['status'] == 'completed')
        avg_sale = total_volume / completed_sales if completed_sales > 0 else 0
        
        # Popular cards
        card_counts = {}
        for listing in self.listings:
            card = listing['card_name']
            card_counts[card] = card_counts.get(card, 0) + 1
            
        popular_cards = sorted(card_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_active_listings': active_listings,
            'total_completed_sales': completed_sales,
            'total_volume': total_volume,
            'average_sale': avg_sale,
            'total_users': len(self.users),
            'popular_cards': popular_cards[:10],
            'average_prices': {}  # Could calculate from recent sales
        }
        
    def get_user_profile(self, username):
        """Get user profile"""
        return self.users.get(username, {})
        
    def load_marketplace_data(self):
        """Load marketplace data from file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.listings = data.get('listings', [])
                    self.transactions = data.get('transactions', [])
                    self.users = data.get('users', {})
        except Exception as e:
            print(f"Failed to load marketplace data: {e}")
            
    def save_marketplace_data(self):
        """Save marketplace data to file"""
        try:
            data = {
                'listings': self.listings,
                'transactions': self.transactions,
                'users': self.users
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save marketplace data: {e}")

class MarketplaceTab:
    """Complete marketplace interface - Connected to live server"""
    
    def __init__(self, parent_notebook, config=None):
        self.notebook = parent_notebook
        self.config = config or {}
        self.colors = {
            'bg_dark': '#0d0d0d',
            'bg_light': '#1a1a1a',
            'text_gold': '#d4af37',
            'button_primary': '#4b0082',
            'accent_green': '#2d5016',
            'accent_red': '#8b0000'
        }
        
        # Initialize marketplace client (auto-connects to Zultan)
        self.client = MarketplaceClient()
        self.logged_in = False
        self.current_user = None
        
        # Create the tab
        self.create_tab()
        
        # Try to auto-login with portal credentials
        self.auto_login()
        
    def auto_login(self):
        """Auto-login using saved credentials or show login dialog"""
        self.user_email = ""

        # Check if server is reachable first
        try:
            health = self.client.check_health()
            if health.get('status') not in ('healthy', 'online'):
                print(f"Marketplace server offline: {health}")
                return
        except Exception as e:
            print(f"Marketplace server unreachable: {e}")
            return

        # Try to get current user (from saved session)
        try:
            result = self.client.get_current_user()
            if result.get('user'):
                self.logged_in = True
                self.current_user = result['user']
                self.user_email = self.current_user.get('email', '')
                self.refresh_listings()
                self.refresh_my_listings()
                self.refresh_cart()
                self.refresh_transactions()
                return
        except Exception:
            pass

        # Show login dialog after window is ready
        self.frame.after(500, self.show_login_dialog)

    def show_login_dialog(self):
        """Show login/register dialog"""
        dialog = tk.Toplevel()
        dialog.title("NEXUS Marketplace Login")
        dialog.geometry("400x300")
        dialog.configure(bg=self.colors['bg_dark'])
        dialog.attributes('-topmost', True)
        dialog.focus_force()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 200
        y = (dialog.winfo_screenheight() // 2) - 150
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="NEXUS Marketplace", font=("Arial", 16, "bold"),
                fg=self.colors['text_gold'], bg=self.colors['bg_dark']).pack(pady=20)

        # Email
        tk.Label(dialog, text="Email:", fg="white", bg=self.colors['bg_dark'],
                font=("Arial", 11)).pack(anchor="w", padx=50)
        email_entry = tk.Entry(dialog, width=35, font=("Arial", 11))
        email_entry.pack(pady=5)
        email_entry.insert(0, "kevin@nexuscards.com")

        # Password
        tk.Label(dialog, text="Password:", fg="white", bg=self.colors['bg_dark'],
                font=("Arial", 11)).pack(anchor="w", padx=50)
        password_entry = tk.Entry(dialog, width=35, font=("Arial", 11), show="*")
        password_entry.pack(pady=5)
        password_entry.focus_set()

        # Status label
        status_label = tk.Label(dialog, text="", fg="red", bg=self.colors['bg_dark'],
                               font=("Arial", 10))
        status_label.pack(pady=5)

        def do_login():
            email = email_entry.get().strip()
            password = password_entry.get()
            if not email or not password:
                status_label.config(text="Enter email and password")
                return

            status_label.config(text="Logging in...", fg="yellow")
            dialog.update()

            try:
                result = self.client.login(email, password)
                if result.get('user'):
                    self.logged_in = True
                    self.current_user = result['user']
                    self.user_email = email
                    dialog.destroy()
                    self.refresh_listings()
                    self.refresh_my_listings()
                    self.refresh_cart()
                    self.refresh_transactions()
                    messagebox.showinfo("Success",
                        f"Logged in as: {self.current_user.get('shop_name', self.current_user.get('username', 'User'))}")
                else:
                    status_label.config(text=result.get('error', 'Login failed'), fg="red")
            except Exception as e:
                status_label.config(text=str(e), fg="red")

        def do_register():
            email = email_entry.get().strip()
            password = password_entry.get()
            if not email or not password:
                status_label.config(text="Enter email and password")
                return

            username = email.split('@')[0]
            status_label.config(text="Registering...", fg="yellow")
            dialog.update()

            try:
                result = self.client.register(username, email, password, role='seller', shop_name='NEXUS Cards')
                if result.get('user'):
                    self.logged_in = True
                    self.current_user = result['user']
                    self.user_email = email
                    dialog.destroy()
                    self.refresh_listings()
                    messagebox.showinfo("Success", f"Account created and logged in!")
                else:
                    status_label.config(text=result.get('error', 'Registration failed'), fg="red")
            except Exception as e:
                status_label.config(text=str(e), fg="red")

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.colors['bg_dark'])
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Login", command=do_login,
                 bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 12), width=12).pack(side="left", padx=10)

        tk.Button(btn_frame, text="Register", command=do_register,
                 bg=self.colors['accent_green'], fg="white",
                 font=("Arial", 12), width=12).pack(side="left", padx=10)

        # Bind Enter key to login
        password_entry.bind('<Return>', lambda e: do_login())

        def on_close():
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
    def create_tab(self):
        """Create the complete marketplace tab"""
        # Main frame
        self.frame = tk.Frame(self.notebook, bg=self.colors['bg_dark'])
        self.notebook.add(self.frame, text="🏪 Marketplace")
        
        # Header
        header = tk.Label(self.frame, text="NEXUS MARKETPLACE",
                         font=("Arial", 18, "bold"), fg=self.colors['text_gold'], 
                         bg=self.colors['bg_light'])
        header.pack(pady=15)
        
        # Create tabbed interface
        self.market_tabs = ttk.Notebook(self.frame)
        self.market_tabs.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create sub-tabs
        self.create_browse_tab()
        self.create_cart_tab()
        self.create_my_listings_tab()
        self.create_transactions_tab()
        self.create_stats_tab()
        
    def create_browse_tab(self):
        """Browse marketplace listings"""
        browse_tab = tk.Frame(self.market_tabs, bg=self.colors['bg_dark'])
        self.market_tabs.add(browse_tab, text="Browse")
        
        # Search controls
        search_frame = ttk.LabelFrame(browse_tab, text="Search Listings", padding=15)
        search_frame.pack(fill="x", padx=10, pady=10)
        
        search_row = tk.Frame(search_frame, bg=self.colors['bg_light'])
        search_row.pack(fill="x", pady=5)
        
        tk.Label(search_row, text="Card Name:", font=("Arial", 12),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=2)
        self.search_name = tk.Entry(search_row, width=25, font=("Arial", 11))
        self.search_name.pack(side="left", padx=5)
        
        tk.Label(search_row, text="Set:", font=("Arial", 12),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=(15, 2))
        self.search_set = tk.Entry(search_row, width=8, font=("Arial", 11))
        self.search_set.pack(side="left", padx=5)
        
        tk.Label(search_row, text="Max Price:", font=("Arial", 12),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=(15, 2))
        self.search_price = tk.Entry(search_row, width=8, font=("Arial", 11))
        self.search_price.pack(side="left", padx=5)
        
        tk.Button(search_row, text="Search", command=self.search_listings,
                 bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 11)).pack(side="left", padx=10)
        
        # Listings display
        listings_frame = ttk.LabelFrame(browse_tab, text="Available Listings", padding=10)
        listings_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Treeview for listings
        columns = ('Card', 'Set', 'Condition', 'List', 'Market', 'Seller')
        self.listings_tree = ttk.Treeview(listings_frame, columns=columns, show='headings', height=15)

        col_widths = {'Card': 180, 'Set': 80, 'Condition': 70, 'List': 70, 'Market': 70, 'Seller': 100}
        for col in columns:
            self.listings_tree.heading(col, text=col)
            self.listings_tree.column(col, width=col_widths.get(col, 100))
        
        self.listings_tree.pack(fill="both", expand=True, side="left")
        
        # Scrollbar
        v_scroll = ttk.Scrollbar(listings_frame, orient="vertical", command=self.listings_tree.yview)
        v_scroll.pack(side="right", fill="y")
        self.listings_tree.configure(yscrollcommand=v_scroll.set)

        # Mouse wheel scrolling
        self.listings_tree.bind("<MouseWheel>", lambda e: self.listings_tree.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Action buttons
        action_frame = tk.Frame(browse_tab, bg=self.colors['bg_dark'])
        action_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Button(action_frame, text="Buy Now", command=self.buy_selected,
                 bg=self.colors['accent_green'], fg="white",
                 font=("Arial", 12), padx=15).pack(side="left", padx=5)
        
        tk.Button(action_frame, text="Make Offer", command=self.make_offer,
                 bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 12), padx=15).pack(side="left", padx=5)
        
        tk.Button(action_frame, text="Add to Watchlist", command=self.add_to_watchlist,
                 bg=self.colors['text_gold'], fg="black",
                 font=("Arial", 12), padx=15).pack(side="left", padx=5)
        
        tk.Button(action_frame, text="Refresh", command=self.refresh_listings,
                 bg="gray", fg="white",
                 font=("Arial", 12), padx=15).pack(side="right", padx=5)

    def create_cart_tab(self):
        """Shopping cart view and checkout"""
        cart_tab = tk.Frame(self.market_tabs, bg=self.colors['bg_dark'])
        self.market_tabs.add(cart_tab, text="Cart")

        # Cart header with total
        header_frame = tk.Frame(cart_tab, bg=self.colors['bg_light'])
        header_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(header_frame, text="Shopping Cart",
                font=("Arial", 14, "bold"), fg=self.colors['text_gold'],
                bg=self.colors['bg_light']).pack(side="left", padx=10)

        self.cart_total_label = tk.Label(header_frame, text="Total: $0.00",
                font=("Arial", 14, "bold"), fg="#3fb950",
                bg=self.colors['bg_light'])
        self.cart_total_label.pack(side="right", padx=10)

        self.cart_count_label = tk.Label(header_frame, text="(0 items)",
                font=("Arial", 11), fg="white",
                bg=self.colors['bg_light'])
        self.cart_count_label.pack(side="right", padx=5)

        # Cart items display
        cart_frame = ttk.LabelFrame(cart_tab, text="Cart Items", padding=10)
        cart_frame.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ('Card', 'Set', 'Condition', 'Price', 'Qty', 'Subtotal', 'Seller')
        self.cart_tree = ttk.Treeview(cart_frame, columns=columns, show='headings', height=12)

        col_widths = {'Card': 180, 'Set': 80, 'Condition': 70, 'Price': 80, 'Qty': 50, 'Subtotal': 80, 'Seller': 100}
        for col in columns:
            self.cart_tree.heading(col, text=col)
            self.cart_tree.column(col, width=col_widths.get(col, 100))

        self.cart_tree.pack(fill="both", expand=True, side="left")

        v_scroll = ttk.Scrollbar(cart_frame, orient="vertical", command=self.cart_tree.yview)
        v_scroll.pack(side="right", fill="y")
        self.cart_tree.configure(yscrollcommand=v_scroll.set)
        self.cart_tree.bind("<MouseWheel>", lambda e: self.cart_tree.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Cart actions
        cart_actions = tk.Frame(cart_tab, bg=self.colors['bg_dark'])
        cart_actions.pack(fill="x", padx=10, pady=5)

        tk.Button(cart_actions, text="Remove Selected", command=self.remove_from_cart,
                 bg=self.colors['accent_red'], fg="white",
                 font=("Arial", 11), padx=10).pack(side="left", padx=5)

        tk.Button(cart_actions, text="Clear Cart", command=self.clear_cart,
                 bg="gray", fg="white",
                 font=("Arial", 11), padx=10).pack(side="left", padx=5)

        tk.Button(cart_actions, text="Refresh Cart", command=self.refresh_cart,
                 bg="gray", fg="white",
                 font=("Arial", 11), padx=10).pack(side="right", padx=5)

        # Checkout section
        checkout_frame = ttk.LabelFrame(cart_tab, text="Checkout", padding=15)
        checkout_frame.pack(fill="x", padx=10, pady=10)

        # Shipping address
        addr_row = tk.Frame(checkout_frame, bg=self.colors['bg_light'])
        addr_row.pack(fill="x", pady=5)

        tk.Label(addr_row, text="Shipping Address:", font=("Arial", 11),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=5)

        self.shipping_address = tk.Text(addr_row, width=50, height=3, font=("Arial", 10),
                                        bg=self.colors['bg_dark'], fg="white",
                                        insertbackground="white")
        self.shipping_address.pack(side="left", padx=10, fill="x", expand=True)

        # Checkout button
        checkout_btn_frame = tk.Frame(checkout_frame, bg=self.colors['bg_light'])
        checkout_btn_frame.pack(fill="x", pady=10)

        tk.Button(checkout_btn_frame, text="Proceed to Checkout",
                 command=self.checkout,
                 bg=self.colors['accent_green'], fg="white",
                 font=("Arial", 14, "bold"), padx=30, pady=10).pack(side="right", padx=10)

        self.checkout_status = tk.Label(checkout_btn_frame, text="",
                font=("Arial", 10), fg=self.colors['text_gold'],
                bg=self.colors['bg_light'])
        self.checkout_status.pack(side="left", padx=10)

    def create_my_listings_tab(self):
        """My listings management"""
        my_tab = tk.Frame(self.market_tabs, bg=self.colors['bg_dark'])
        self.market_tabs.add(my_tab, text="My Listings")
        
        # Create new listing
        create_frame = ttk.LabelFrame(my_tab, text="Create New Listing", padding=15)
        create_frame.pack(fill="x", padx=10, pady=10)
        
        create_row = tk.Frame(create_frame, bg=self.colors['bg_light'])
        create_row.pack(fill="x", pady=5)
        
        tk.Label(create_row, text="Card:", font=("Arial", 12),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=2)
        self.new_card_name = tk.Entry(create_row, width=25, font=("Arial", 11))
        self.new_card_name.pack(side="left", padx=5)
        
        tk.Label(create_row, text="Set:", font=("Arial", 12),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=(15, 2))
        self.new_set = tk.Entry(create_row, width=8, font=("Arial", 11))
        self.new_set.pack(side="left", padx=5)
        
        tk.Label(create_row, text="Price:", font=("Arial", 12),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=(15, 2))
        self.new_price = tk.Entry(create_row, width=8, font=("Arial", 11))
        self.new_price.pack(side="left", padx=5)
        
        tk.Label(create_row, text="Condition:", font=("Arial", 12),
                fg="white", bg=self.colors['bg_light']).pack(side="left", padx=(15, 2))
        self.new_condition = ttk.Combobox(create_row, values=['NM', 'LP', 'MP', 'HP', 'DMG'],
                                         state="readonly", width=6)
        self.new_condition.set('NM')
        self.new_condition.pack(side="left", padx=5)
        
        tk.Button(create_row, text="Create Listing", command=self.create_listing,
                 bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 11)).pack(side="left", padx=15)
        
        # My active listings
        my_frame = ttk.LabelFrame(my_tab, text="My Active Listings", padding=10)
        my_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        columns = ('Card', 'Set', 'Price', 'Condition', 'Views', 'Status')
        self.my_tree = ttk.Treeview(my_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.my_tree.heading(col, text=col)
            self.my_tree.column(col, width=120)
        
        self.my_tree.pack(fill="both", expand=True, side="left")
        
        v_scroll2 = ttk.Scrollbar(my_frame, orient="vertical", command=self.my_tree.yview)
        v_scroll2.pack(side="right", fill="y")
        self.my_tree.configure(yscrollcommand=v_scroll2.set)
        self.my_tree.bind("<MouseWheel>", lambda e: self.my_tree.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Actions
        my_actions = tk.Frame(my_tab, bg=self.colors['bg_dark'])
        my_actions.pack(fill="x", padx=10, pady=10)
        
        tk.Button(my_actions, text="Cancel Listing", command=self.cancel_listing,
                 bg=self.colors['accent_red'], fg="white",
                 font=("Arial", 12)).pack(side="left", padx=5)
        
        tk.Button(my_actions, text="Edit Listing", command=self.edit_listing,
                 bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 12)).pack(side="left", padx=5)
        
        tk.Button(my_actions, text="Bulk Upload Inventory", command=self.bulk_upload_inventory,
                 bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 12)).pack(side="right", padx=5)

        tk.Button(my_actions, text="Refresh", command=self.refresh_my_listings,
                 bg="gray", fg="white",
                 font=("Arial", 12)).pack(side="right", padx=5)
                 
    def create_transactions_tab(self):
        """Transaction history"""
        trans_tab = tk.Frame(self.market_tabs, bg=self.colors['bg_dark'])
        self.market_tabs.add(trans_tab, text="Transactions")
        
        # Purchases
        purchases_frame = ttk.LabelFrame(trans_tab, text="My Purchases", padding=10)
        purchases_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ('Date', 'Card', 'Seller', 'Price', 'Status')
        self.purchases_tree = ttk.Treeview(purchases_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            self.purchases_tree.heading(col, text=col)
            self.purchases_tree.column(col, width=120)
        
        self.purchases_tree.pack(fill="both", expand=True)
        
        # Sales
        sales_frame = ttk.LabelFrame(trans_tab, text="My Sales", padding=10)
        sales_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.sales_tree = ttk.Treeview(sales_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            self.sales_tree.heading(col, text=col)
            self.sales_tree.column(col, width=120)
        
        self.sales_tree.pack(fill="both", expand=True)
        
    def create_stats_tab(self):
        """Marketplace statistics"""
        stats_tab = tk.Frame(self.market_tabs, bg=self.colors['bg_dark'])
        self.market_tabs.add(stats_tab, text="Statistics")
        
        # Stats display
        self.stats_display = scrolledtext.ScrolledText(stats_tab, height=25, width=80,
                                                      font=("Courier", 10),
                                                      bg=self.colors['bg_dark'], fg="white")
        self.stats_display.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Refresh button
        tk.Button(stats_tab, text="Refresh Stats", command=self.show_stats,
                 bg=self.colors['button_primary'], fg="white",
                 font=("Arial", 12)).pack(pady=10)
        
    # Event handlers and operations
    def search_listings(self):
        """Search marketplace listings"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", 
                "Please log in to browse marketplace")
            return
            
        card_name = self.search_name.get().strip()
        set_name = self.search_set.get().strip()
        
        try:
            result = self.client.browse_listings(search=card_name, 
                                                 set_name=set_name)
            listings = result.get('listings', [])
            self.populate_listings_tree(listings)
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")
        
    def populate_listings_tree(self, listings):
        """Populate listings treeview"""
        # Clear existing items
        for item in self.listings_tree.get_children():
            self.listings_tree.delete(item)
            
        # Add listings
        for listing in listings:
            list_price = float(listing.get('price', 0))
            market_price = float(listing.get('market_price', 0))
            market_str = f"${market_price:.2f}" if market_price > 0 else "-"

            self.listings_tree.insert('', 'end', values=(
                listing['card_name'],
                listing.get('set_name', ''),
                listing['condition'],
                f"${list_price:.2f}",
                market_str,
                listing.get('shop_name', 'Unknown')
            ), tags=(listing['id'],))
            
    def refresh_listings(self):
        """Refresh all listings"""
        if not self.logged_in:
            return
        try:
            result = self.client.browse_listings()
            listings = result.get('listings', [])
            self.populate_listings_tree(listings)
        except Exception as e:
            print(f"Failed to refresh listings: {e}")
        
    def buy_selected(self):
        """Add selected listing to cart"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", 
                "Please log in to add to cart")
            return
            
        selection = self.listings_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", 
                "Please select a listing")
            return
            
        item = self.listings_tree.item(selection[0])
        listing_id = item['tags'][0]
        
        try:
            result = self.client.add_to_cart(listing_id, quantity=1)
            if result.get('error'):
                messagebox.showerror("Error", result['error'])
            else:
                # Refresh cart and switch to cart tab
                self.refresh_cart()
                card_name = item['values'][0]
                messagebox.showinfo("Added to Cart",
                    f"{card_name} added to cart!\n\nGo to Cart tab to checkout.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add to cart: {e}")
                
    def make_offer(self):
        """Make offer on selected listing"""
        messagebox.showinfo("Coming Soon", 
            "Offer system will be implemented soon!")
        
    def add_to_watchlist(self):
        """Add to watchlist"""
        messagebox.showinfo("Coming Soon", 
            "Watchlist feature will be implemented soon!")
        
    def create_listing(self):
        """Create new listing"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", 
                "Please log in to create listings")
            return
            
        card_name = self.new_card_name.get().strip()
        set_name = self.new_set.get().strip()
        condition = self.new_condition.get()
        
        try:
            price = float(self.new_price.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid price")
            return
            
        if not card_name:
            messagebox.showerror("Error", "Card name required")
            return
        
        try:
            result = self.client.create_listing(
                card_name=card_name,
                price=price,
                quantity=1,
                condition=condition,
                set_name=set_name
            )
            
            if result.get('error'):
                messagebox.showerror("Error", result['error'])
            else:
                listing_id = result.get('listing_id', 'Unknown')
                messagebox.showinfo("Success", 
                    f"Listing created! ID: {listing_id[:8]}...")
                
                # Clear form
                self.new_card_name.delete(0, tk.END)
                self.new_set.delete(0, tk.END)
                self.new_price.delete(0, tk.END)
                self.new_condition.set('NM')
                
                self.refresh_my_listings()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create listing: {e}")
            
    def refresh_my_listings(self):
        """Refresh my listings"""
        if not self.logged_in:
            return
            
        # Clear existing items
        for item in self.my_tree.get_children():
            self.my_tree.delete(item)
        
        try:
            result = self.client.get_my_listings()
            my_listings = result.get('listings', [])
            
            for listing in my_listings:
                if listing['status'] == 'active':
                    self.my_tree.insert('', 'end', values=(
                        listing['card_name'],
                        listing.get('set_name', ''),
                        f"${listing['price']:.2f}",
                        listing['condition'],
                        listing.get('views', 0),
                        listing['status'].upper()
                    ), tags=(listing['id'],))
        except Exception as e:
            print(f"Failed to refresh my listings: {e}")
                
    def cancel_listing(self):
        """Cancel selected listing"""
        if not self.logged_in:
            return
            
        selection = self.my_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", 
                "Please select a listing to cancel")
            return
            
        confirm = messagebox.askyesno("Confirm", "Cancel this listing?")
        if confirm:
            item = self.my_tree.item(selection[0])
            listing_id = item['tags'][0]
            
            try:
                result = self.client.delete_listing(listing_id)
                if result.get('success'):
                    messagebox.showinfo("Success", "Listing cancelled")
                    self.refresh_my_listings()
                else:
                    messagebox.showerror("Error", 
                        result.get('error', 'Failed to cancel'))
            except Exception as e:
                messagebox.showerror("Error", 
                    f"Failed to cancel listing: {e}")
            
    def edit_listing(self):
        """Edit selected listing"""
        messagebox.showinfo("Coming Soon", "Listing editing will be implemented soon!")

    def bulk_upload_inventory(self):
        """Upload entire inventory to marketplace"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", "Please log in first to upload inventory")
            return

        # Ask for pricing strategy
        from tkinter import simpledialog
        strategy = messagebox.askquestion(
            "Pricing Strategy",
            "Use market price for all cards?\n\nYes = Market Price\nNo = Manual Configuration"
        )

        if strategy == 'no':
            messagebox.showinfo("Manual Config", "Manual pricing configuration not yet implemented.\nUsing market price for now.")

        # Confirm bulk upload
        confirm = messagebox.askyesno(
            "Bulk Upload",
            "This will upload ALL cards from your collection to the marketplace.\n\nContinue?"
        )

        if not confirm:
            return

        try:
            # Get inventory from DANIELSON library API
            import requests
            danielson_url = "http://192.168.1.219:5001"
            response = requests.get(f"{danielson_url}/api/library/all", timeout=10)

            if response.status_code != 200:
                messagebox.showerror("Error", "Failed to fetch inventory from DANIELSON")
                return

            inventory = response.json()
            cards = inventory.get('results', [])

            if not cards:
                messagebox.showinfo("No Cards", "No cards found in inventory")
                return

            # Use MarketplaceClient bulk upload
            from nexus_v2.integrations.marketplace_client import MarketplaceClient
            client = MarketplaceClient()

            # Prepare cards for bulk upload
            cards_to_upload = []
            for card in cards:
                cards_to_upload.append({
                    'card_name': card.get('name'),
                    'price': card.get('price') or 0.99,
                    'quantity': card.get('quantity', 1),
                    'condition': 'NM',
                    'set_name': card.get('set_name'),
                    'set_code': card.get('set_code'),
                    'rarity': card.get('rarity'),
                    'foil': card.get('foil', False),
                    'collector_number': card.get('collector_number'),
                    'image_url': card.get('image_url'),
                    'scryfall_id': card.get('scryfall_id')
                })

            # Bulk upload
            messagebox.showinfo("Uploading", f"Uploading {len(cards_to_upload)} cards to marketplace...\n\nThis may take a moment.")

            result = client.bulk_create_listings(cards_to_upload)

            success_count = len(result.get('success', []))
            failed_count = len(result.get('failed', []))

            msg = f"Bulk Upload Complete!\n\n"
            msg += f"✓ Successfully listed: {success_count}\n"
            msg += f"✗ Failed: {failed_count}"

            if failed_count > 0:
                msg += f"\n\nFirst 5 failures:\n"
                for failure in result.get('failed', [])[:5]:
                    msg += f"- {failure.get('card')}: {failure.get('error')}\n"

            messagebox.showinfo("Upload Complete", msg)

            # Refresh listings
            self.refresh_my_listings()

        except Exception as e:
            messagebox.showerror("Upload Error", f"Failed to bulk upload inventory:\n\n{e}")

    def show_stats(self):
        """Display marketplace statistics"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", 
                "Please log in to view stats")
            return
            
        self.stats_display.delete('1.0', tk.END)
        
        try:
            result = self.client.get_seller_stats()
            
            text = f"""
NEXUS MARKETPLACE STATISTICS
{'='*60}

YOUR SELLER STATS:
   Active Listings: {result.get('active_listings', 0)}
   Total Sales: {result.get('total_sales', 0)}
   Revenue: ${result.get('revenue', 0):.2f}
   Rating: {result.get('rating', 0):.1f}⭐

MARKETPLACE INFO:
   Connected to: {self.client.server_url}
   Account: {self.user_email}
"""
            self.stats_display.insert('1.0', text)
            
        except Exception as e:
            self.stats_display.insert('1.0', 
                f"Failed to load stats: {e}\n\nCheck server connection")
            print(f"Stats error: {e}")
            
    def refresh_transactions(self):
        """Refresh transaction history from server"""
        if not self.logged_in:
            return
            
        # Clear existing
        for item in self.purchases_tree.get_children():
            self.purchases_tree.delete(item)
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
            
        try:
            # Get buyer orders
            buyer_result = self.client.get_orders(role='buyer')
            for order in buyer_result.get('orders', []):
                for item in order.get('items', []):
                    self.purchases_tree.insert('', 'end', values=(
                        order['created_at'][:10],
                        item['card_name'],
                        order.get('seller_name', 'Unknown'),
                        f"${item['price']:.2f}",
                        order['status']
                    ))
                    
            # Get seller orders
            seller_result = self.client.get_orders(role='seller')
            for order in seller_result.get('orders', []):
                for item in order.get('items', []):
                    self.sales_tree.insert('', 'end', values=(
                        order['created_at'][:10],
                        item['card_name'],
                        order.get('buyer_email', 'Unknown'),
                        f"${item['price']:.2f}",
                        order['status']
                    ))
                    
        except Exception as e:
            print(f"Failed to refresh transactions: {e}")

    # ============================================
    # CART OPERATIONS
    # ============================================
    def refresh_cart(self):
        """Refresh cart from server"""
        if not self.logged_in:
            return

        # Clear existing items
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)

        try:
            result = self.client.get_cart()
            cart_items = result.get('items', [])
            total = 0.0
            count = 0

            for item in cart_items:
                price = float(item.get('price', 0))
                qty = int(item.get('quantity', 1))
                subtotal = price * qty
                total += subtotal
                count += qty

                self.cart_tree.insert('', 'end', values=(
                    item.get('card_name', 'Unknown'),
                    item.get('set_name', ''),
                    item.get('condition', 'NM'),
                    f"${price:.2f}",
                    qty,
                    f"${subtotal:.2f}",
                    item.get('seller_name', 'Unknown')
                ), tags=(item.get('id', ''),))

            # Update totals
            self.cart_total_label.config(text=f"Total: ${total:.2f}")
            self.cart_count_label.config(text=f"({count} items)")

        except Exception as e:
            print(f"Failed to refresh cart: {e}")
            self.cart_total_label.config(text="Total: $0.00")
            self.cart_count_label.config(text="(0 items)")

    def remove_from_cart(self):
        """Remove selected item from cart"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", "Please log in first")
            return

        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to remove")
            return

        item = self.cart_tree.item(selection[0])
        item_id = item['tags'][0] if item['tags'] else None

        if not item_id:
            messagebox.showerror("Error", "Could not identify item")
            return

        try:
            result = self.client.remove_from_cart(item_id)
            if result.get('error'):
                messagebox.showerror("Error", result['error'])
            else:
                self.refresh_cart()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove item: {e}")

    def clear_cart(self):
        """Clear all items from cart"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", "Please log in first")
            return

        confirm = messagebox.askyesno("Confirm", "Clear all items from cart?")
        if not confirm:
            return

        try:
            result = self.client.clear_cart()
            if result.get('error'):
                messagebox.showerror("Error", result['error'])
            else:
                self.refresh_cart()
                messagebox.showinfo("Success", "Cart cleared")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear cart: {e}")

    def checkout(self):
        """Process checkout"""
        if not self.logged_in:
            messagebox.showwarning("Not Logged In", "Please log in first")
            return

        # Get shipping address
        address = self.shipping_address.get("1.0", tk.END).strip()
        if not address:
            messagebox.showwarning("Missing Address", "Please enter a shipping address")
            return

        # Check cart has items
        if not self.cart_tree.get_children():
            messagebox.showwarning("Empty Cart", "Your cart is empty")
            return

        self.checkout_status.config(text="Processing order...")

        try:
            # Create order
            result = self.client.create_order(shipping_address=address)

            if result.get('error'):
                self.checkout_status.config(text="")
                messagebox.showerror("Error", result['error'])
                return

            order_id = result.get('order_id')
            total = result.get('total', 0)

            self.checkout_status.config(text="Order created! Processing payment...")

            # For now, show success (payment integration would go here)
            messagebox.showinfo("Order Created",
                f"Order ID: {order_id}\n"
                f"Total: ${total:.2f}\n\n"
                "Payment processing coming soon!\n"
                "Seller will be notified of your order.")

            self.checkout_status.config(text="")
            self.shipping_address.delete("1.0", tk.END)
            self.refresh_cart()
            self.refresh_transactions()

        except Exception as e:
            self.checkout_status.config(text="")
            messagebox.showerror("Error", f"Checkout failed: {e}")