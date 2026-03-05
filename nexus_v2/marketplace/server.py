"""
NEXUS MARKETPLACE V2 - API SERVER
=================================
Full-featured marketplace backend with:
- Multi-seller support
- Cart & checkout
- Order management
- User authentication
- Inventory sync from NEXUS app

Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.
PATENT PENDING
"""

from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nexus-marketplace-dev-key-change-in-prod')
CORS(app, supports_credentials=True)

# Configuration
DB_PATH = Path(__file__).parent / 'marketplace.db'
UPLOAD_DIR = Path(__file__).parent / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)

# ============================================
# DATABASE SETUP
# ============================================

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cur = conn.cursor()
    
    # Users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            username TEXT NOT NULL,
            role TEXT DEFAULT 'buyer',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    ''')
    
    # Sellers table (linked to users)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sellers (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            shop_name TEXT NOT NULL,
            description TEXT,
            logo_url TEXT,
            rating REAL DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            location TEXT,
            shipping_policy TEXT,
            return_policy TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Listings table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            seller_id TEXT NOT NULL,
            card_name TEXT NOT NULL,
            set_code TEXT,
            set_name TEXT,
            collector_number TEXT,
            rarity TEXT,
            condition TEXT DEFAULT 'NM',
            price REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            image_url TEXT,
            scryfall_id TEXT,
            language TEXT DEFAULT 'English',
            foil INTEGER DEFAULT 0,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    ''')
    
    # Cart items table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            listing_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (listing_id) REFERENCES listings(id)
        )
    ''')
    
    # Orders table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            buyer_id TEXT NOT NULL,
            seller_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            subtotal REAL NOT NULL,
            shipping_cost REAL DEFAULT 0,
            total REAL NOT NULL,
            shipping_address TEXT,
            tracking_number TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    ''')
    
    # Order items table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            listing_id TEXT NOT NULL,
            card_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            condition TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (listing_id) REFERENCES listings(id)
        )
    ''')
    
    # Reviews table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            buyer_id TEXT NOT NULL,
            seller_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
        )
    ''')
    
    # Create indexes for performance
    cur.execute('CREATE INDEX IF NOT EXISTS idx_listings_seller ON listings(seller_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_listings_card ON listings(card_name)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_listings_set ON listings(set_code)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders(seller_id)')

    # Download auth codes table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS download_codes (
            id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            app_name TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            max_uses INTEGER DEFAULT 1,
            use_count INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')

    # Download logs table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS download_logs (
            id TEXT PRIMARY KEY,
            code_id TEXT NOT NULL,
            app_name TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (code_id) REFERENCES download_codes(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database initialized")

# ============================================
# AUTH HELPERS
# ============================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated

def seller_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        if session.get('role') != 'seller':
            return jsonify({'error': 'Seller account required'}), 403
        return f(*args, **kwargs)
    return decorated

# ============================================
# AUTH ROUTES
# ============================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    username = data.get('username', '').strip()
    role = data.get('role', 'buyer')
    
    if not email or not password or not username:
        return jsonify({'error': 'Email, password, and username required'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    # Check if email exists
    cur.execute('SELECT id FROM users WHERE email = ?', (email,))
    if cur.fetchone():
        conn.close()
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create user
    user_id = str(uuid.uuid4())
    password_hash = generate_password_hash(password)
    
    cur.execute('''
        INSERT INTO users (id, email, password_hash, username, role)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, email, password_hash, username, role))
    
    # If registering as seller, create seller profile
    seller_id = None
    if role == 'seller':
        seller_id = str(uuid.uuid4())
        shop_name = data.get('shop_name', username + "'s Shop")
        cur.execute('''
            INSERT INTO sellers (id, user_id, shop_name)
            VALUES (?, ?, ?)
        ''', (seller_id, user_id, shop_name))
    
    conn.commit()
    conn.close()
    
    # Set session
    session['user_id'] = user_id
    session['username'] = username
    session['role'] = role
    session['seller_id'] = seller_id
    
    return jsonify({
        'success': True,
        'user': {
            'id': user_id,
            'email': email,
            'username': username,
            'role': role,
            'seller_id': seller_id
        }
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cur.fetchone()
    
    if not user or not check_password_hash(user['password_hash'], password):
        conn.close()
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Get seller_id if seller
    seller_id = None
    if user['role'] == 'seller':
        cur.execute('SELECT id FROM sellers WHERE user_id = ?', (user['id'],))
        seller = cur.fetchone()
        if seller:
            seller_id = seller['id']
    
    # Update last login
    cur.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                (datetime.now().isoformat(), user['id']))
    conn.commit()
    conn.close()
    
    # Set session
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['seller_id'] = seller_id
    
    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'role': user['role'],
            'seller_id': seller_id
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/me')
def get_current_user():
    """Get current logged in user"""
    if 'user_id' not in session:
        return jsonify({'user': None})
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id, email, username, role FROM users WHERE id = ?', 
                (session['user_id'],))
    user = cur.fetchone()
    conn.close()
    
    if not user:
        session.clear()
        return jsonify({'user': None})
    
    return jsonify({
        'user': {
            'id': user['id'],
            'email': user['email'],
            'username': user['username'],
            'role': user['role'],
            'seller_id': session.get('seller_id')
        }
    })

# ============================================
# LISTINGS ROUTES
# ============================================

@app.route('/api/listings')
def get_listings():
    """Get all active listings with filters"""
    conn = get_db()
    cur = conn.cursor()
    
    # Base query
    query = '''
        SELECT l.*, s.shop_name, s.rating as seller_rating, s.verified
        FROM listings l
        JOIN sellers s ON l.seller_id = s.id
        WHERE l.status = 'active' AND l.quantity > 0
    '''
    params = []
    
    # Apply filters
    search = request.args.get('search', '').strip()
    if search:
        query += ' AND (l.card_name LIKE ? OR l.set_name LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    
    set_code = request.args.get('set')
    if set_code:
        query += ' AND l.set_code = ?'
        params.append(set_code)
    
    rarity = request.args.get('rarity')
    if rarity:
        query += ' AND l.rarity = ?'
        params.append(rarity)
    
    condition = request.args.get('condition')
    if condition:
        query += ' AND l.condition = ?'
        params.append(condition)
    
    min_price = request.args.get('min_price', type=float)
    if min_price is not None:
        query += ' AND l.price >= ?'
        params.append(min_price)
    
    max_price = request.args.get('max_price', type=float)
    if max_price is not None:
        query += ' AND l.price <= ?'
        params.append(max_price)
    
    foil = request.args.get('foil')
    if foil:
        query += ' AND l.foil = ?'
        params.append(1 if foil == 'true' else 0)
    
    seller_id = request.args.get('seller')
    if seller_id:
        query += ' AND l.seller_id = ?'
        params.append(seller_id)
    
    # Sorting
    sort = request.args.get('sort', 'newest')
    if sort == 'price_asc':
        query += ' ORDER BY l.price ASC'
    elif sort == 'price_desc':
        query += ' ORDER BY l.price DESC'
    elif sort == 'name':
        query += ' ORDER BY l.card_name ASC'
    else:  # newest
        query += ' ORDER BY l.created_at DESC'
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 48, type=int)
    per_page = min(per_page, 100)  # Max 100 per page
    offset = (page - 1) * per_page
    
    # Get total count
    count_query = query.replace('SELECT l.*, s.shop_name, s.rating as seller_rating, s.verified', 'SELECT COUNT(*)')
    count_query = count_query.split(' ORDER BY')[0]
    cur.execute(count_query, params)
    total = cur.fetchone()[0]
    
    # Get page of results
    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, offset])
    
    cur.execute(query, params)
    listings = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    return jsonify({
        'listings': listings,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })

@app.route('/api/listings/<listing_id>')
def get_listing(listing_id):
    """Get single listing details"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT l.*, s.shop_name, s.rating as seller_rating, s.verified,
               s.shipping_policy, s.return_policy, s.total_sales
        FROM listings l
        JOIN sellers s ON l.seller_id = s.id
        WHERE l.id = ?
    ''', (listing_id,))
    
    listing = cur.fetchone()
    conn.close()
    
    if not listing:
        return jsonify({'error': 'Listing not found'}), 404
    
    return jsonify({'listing': dict(listing)})

@app.route('/api/listings', methods=['POST'])
@seller_required
def create_listing():
    """Create a new listing"""
    data = request.json
    seller_id = session.get('seller_id')
    
    if not seller_id:
        return jsonify({'error': 'Seller profile not found'}), 400
    
    required = ['card_name', 'price']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    listing_id = str(uuid.uuid4())
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        INSERT INTO listings (
            id, seller_id, card_name, set_code, set_name, collector_number,
            rarity, condition, price, quantity, image_url, scryfall_id,
            language, foil, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        listing_id, seller_id,
        data.get('card_name'),
        data.get('set_code'),
        data.get('set_name'),
        data.get('collector_number'),
        data.get('rarity', 'common'),
        data.get('condition', 'NM'),
        float(data.get('price')),
        int(data.get('quantity', 1)),
        data.get('image_url'),
        data.get('scryfall_id'),
        data.get('language', 'English'),
        1 if data.get('foil') else 0,
        data.get('description')
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'listing_id': listing_id})

@app.route('/api/listings/<listing_id>', methods=['PUT'])
@seller_required
def update_listing(listing_id):
    """Update a listing"""
    data = request.json
    seller_id = session.get('seller_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    # Verify ownership
    cur.execute('SELECT seller_id FROM listings WHERE id = ?', (listing_id,))
    listing = cur.fetchone()
    
    if not listing:
        conn.close()
        return jsonify({'error': 'Listing not found'}), 404
    
    if listing['seller_id'] != seller_id:
        conn.close()
        return jsonify({'error': 'Not authorized'}), 403
    
    # Update fields
    updates = []
    params = []
    
    for field in ['card_name', 'set_code', 'set_name', 'rarity', 'condition', 
                  'price', 'quantity', 'image_url', 'language', 'description', 'status']:
        if field in data:
            updates.append(f'{field} = ?')
            params.append(data[field])
    
    if 'foil' in data:
        updates.append('foil = ?')
        params.append(1 if data['foil'] else 0)
    
    if updates:
        updates.append('updated_at = ?')
        params.append(datetime.now().isoformat())
        params.append(listing_id)
        
        cur.execute(f'UPDATE listings SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})

@app.route('/api/listings/<listing_id>', methods=['DELETE'])
@seller_required
def delete_listing(listing_id):
    """Delete a listing"""
    seller_id = session.get('seller_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    # Verify ownership
    cur.execute('SELECT seller_id FROM listings WHERE id = ?', (listing_id,))
    listing = cur.fetchone()
    
    if not listing:
        conn.close()
        return jsonify({'error': 'Listing not found'}), 404
    
    if listing['seller_id'] != seller_id:
        conn.close()
        return jsonify({'error': 'Not authorized'}), 403
    
    cur.execute('DELETE FROM listings WHERE id = ?', (listing_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============================================
# CART ROUTES
# ============================================

@app.route('/api/cart')
@login_required
def get_cart():
    """Get user's cart"""
    user_id = session['user_id']
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT ci.*, l.card_name, l.set_name, l.condition, l.price, l.image_url,
               l.quantity as available_qty, l.foil, s.shop_name, s.id as seller_id
        FROM cart_items ci
        JOIN listings l ON ci.listing_id = l.id
        JOIN sellers s ON l.seller_id = s.id
        WHERE ci.user_id = ? AND l.status = 'active'
    ''', (user_id,))
    
    items = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    # Group by seller
    sellers = {}
    for item in items:
        seller_id = item['seller_id']
        if seller_id not in sellers:
            sellers[seller_id] = {
                'seller_id': seller_id,
                'shop_name': item['shop_name'],
                'items': [],
                'subtotal': 0
            }
        sellers[seller_id]['items'].append(item)
        sellers[seller_id]['subtotal'] += item['price'] * item['quantity']
    
    total = sum(s['subtotal'] for s in sellers.values())
    
    return jsonify({
        'cart': list(sellers.values()),
        'total': total,
        'item_count': len(items)
    })

@app.route('/api/cart', methods=['POST'])
@login_required
def add_to_cart():
    """Add item to cart"""
    data = request.json
    user_id = session['user_id']
    listing_id = data.get('listing_id')
    quantity = int(data.get('quantity', 1))
    
    if not listing_id:
        return jsonify({'error': 'listing_id required'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    # Check listing exists and has stock
    cur.execute('SELECT quantity, seller_id FROM listings WHERE id = ? AND status = "active"', 
                (listing_id,))
    listing = cur.fetchone()
    
    if not listing:
        conn.close()
        return jsonify({'error': 'Listing not found or unavailable'}), 404
    
    # Check if seller is trying to buy own item
    if session.get('seller_id') == listing['seller_id']:
        conn.close()
        return jsonify({'error': 'Cannot buy your own listing'}), 400
    
    # Check existing cart item
    cur.execute('SELECT id, quantity FROM cart_items WHERE user_id = ? AND listing_id = ?',
                (user_id, listing_id))
    existing = cur.fetchone()
    
    if existing:
        new_qty = existing['quantity'] + quantity
        if new_qty > listing['quantity']:
            conn.close()
            return jsonify({'error': f'Only {listing["quantity"]} available'}), 400
        
        cur.execute('UPDATE cart_items SET quantity = ? WHERE id = ?', 
                    (new_qty, existing['id']))
    else:
        if quantity > listing['quantity']:
            conn.close()
            return jsonify({'error': f'Only {listing["quantity"]} available'}), 400
        
        cart_id = str(uuid.uuid4())
        cur.execute('INSERT INTO cart_items (id, user_id, listing_id, quantity) VALUES (?, ?, ?, ?)',
                    (cart_id, user_id, listing_id, quantity))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/cart/<item_id>', methods=['PUT'])
@login_required
def update_cart_item(item_id):
    """Update cart item quantity"""
    data = request.json
    user_id = session['user_id']
    quantity = int(data.get('quantity', 1))
    
    conn = get_db()
    cur = conn.cursor()
    
    # Verify ownership and get listing
    cur.execute('''
        SELECT ci.*, l.quantity as available_qty
        FROM cart_items ci
        JOIN listings l ON ci.listing_id = l.id
        WHERE ci.id = ? AND ci.user_id = ?
    ''', (item_id, user_id))
    
    item = cur.fetchone()
    
    if not item:
        conn.close()
        return jsonify({'error': 'Cart item not found'}), 404
    
    if quantity > item['available_qty']:
        conn.close()
        return jsonify({'error': f'Only {item["available_qty"]} available'}), 400
    
    if quantity <= 0:
        cur.execute('DELETE FROM cart_items WHERE id = ?', (item_id,))
    else:
        cur.execute('UPDATE cart_items SET quantity = ? WHERE id = ?', (quantity, item_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/cart/<item_id>', methods=['DELETE'])
@login_required
def remove_from_cart(item_id):
    """Remove item from cart"""
    user_id = session['user_id']
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM cart_items WHERE id = ? AND user_id = ?', (item_id, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/cart/clear', methods=['POST'])
@login_required
def clear_cart():
    """Clear entire cart"""
    user_id = session['user_id']
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============================================
# ORDER ROUTES
# ============================================

@app.route('/api/orders', methods=['POST'])
@login_required
def create_order():
    """Create order from cart (checkout)"""
    data = request.json
    user_id = session['user_id']
    shipping_address = data.get('shipping_address')
    
    if not shipping_address:
        return jsonify({'error': 'Shipping address required'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    # Get cart items grouped by seller
    cur.execute('''
        SELECT ci.*, l.card_name, l.price, l.condition, l.seller_id, l.quantity as available_qty
        FROM cart_items ci
        JOIN listings l ON ci.listing_id = l.id
        WHERE ci.user_id = ? AND l.status = 'active'
    ''', (user_id,))
    
    items = cur.fetchall()
    
    if not items:
        conn.close()
        return jsonify({'error': 'Cart is empty'}), 400
    
    # Group by seller and create orders
    orders_created = []
    sellers = {}
    
    for item in items:
        seller_id = item['seller_id']
        if seller_id not in sellers:
            sellers[seller_id] = []
        sellers[seller_id].append(item)
    
    for seller_id, seller_items in sellers.items():
        # Calculate totals
        subtotal = sum(item['price'] * item['quantity'] for item in seller_items)
        shipping_cost = 3.99 if subtotal < 25 else 0  # Free shipping over $25
        total = subtotal + shipping_cost
        
        # Create order
        order_id = str(uuid.uuid4())
        cur.execute('''
            INSERT INTO orders (id, buyer_id, seller_id, subtotal, shipping_cost, total, shipping_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, user_id, seller_id, subtotal, shipping_cost, total, shipping_address))
        
        # Create order items and update inventory
        for item in seller_items:
            order_item_id = str(uuid.uuid4())
            cur.execute('''
                INSERT INTO order_items (id, order_id, listing_id, card_name, price, quantity, condition)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order_item_id, order_id, item['listing_id'], item['card_name'], 
                  item['price'], item['quantity'], item['condition']))
            
            # Reduce listing quantity
            new_qty = item['available_qty'] - item['quantity']
            if new_qty <= 0:
                cur.execute('UPDATE listings SET quantity = 0, status = "sold" WHERE id = ?',
                            (item['listing_id'],))
            else:
                cur.execute('UPDATE listings SET quantity = ? WHERE id = ?',
                            (new_qty, item['listing_id']))
        
        orders_created.append({
            'order_id': order_id,
            'seller_id': seller_id,
            'total': total
        })
    
    # Clear cart
    cur.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'orders': orders_created,
        'message': f'Created {len(orders_created)} order(s)'
    })

@app.route('/api/orders')
@login_required
def get_orders():
    """Get user's orders (as buyer or seller)"""
    user_id = session['user_id']
    seller_id = session.get('seller_id')
    role = request.args.get('role', 'buyer')  # 'buyer' or 'seller'
    
    conn = get_db()
    cur = conn.cursor()
    
    if role == 'seller' and seller_id:
        cur.execute('''
            SELECT o.*, u.username as buyer_name, u.email as buyer_email
            FROM orders o
            JOIN users u ON o.buyer_id = u.id
            WHERE o.seller_id = ?
            ORDER BY o.created_at DESC
        ''', (seller_id,))
    else:
        cur.execute('''
            SELECT o.*, s.shop_name
            FROM orders o
            JOIN sellers s ON o.seller_id = s.id
            WHERE o.buyer_id = ?
            ORDER BY o.created_at DESC
        ''', (user_id,))
    
    orders = []
    for row in cur.fetchall():
        order = dict(row)
        # Get order items
        cur.execute('SELECT * FROM order_items WHERE order_id = ?', (order['id'],))
        order['items'] = [dict(item) for item in cur.fetchall()]
        orders.append(order)
    
    conn.close()
    
    return jsonify({'orders': orders})

@app.route('/api/orders/<order_id>')
@login_required
def get_order(order_id):
    """Get single order details"""
    user_id = session['user_id']
    seller_id = session.get('seller_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT o.*, s.shop_name, u.username as buyer_name, u.email as buyer_email
        FROM orders o
        JOIN sellers s ON o.seller_id = s.id
        JOIN users u ON o.buyer_id = u.id
        WHERE o.id = ?
    ''', (order_id,))
    
    order = cur.fetchone()
    
    if not order:
        conn.close()
        return jsonify({'error': 'Order not found'}), 404
    
    # Check authorization
    if order['buyer_id'] != user_id and order['seller_id'] != seller_id:
        conn.close()
        return jsonify({'error': 'Not authorized'}), 403
    
    order_dict = dict(order)
    
    # Get order items
    cur.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
    order_dict['items'] = [dict(item) for item in cur.fetchall()]
    
    conn.close()
    
    return jsonify({'order': order_dict})

@app.route('/api/orders/<order_id>/status', methods=['PUT'])
@seller_required
def update_order_status(order_id):
    """Update order status (seller only)"""
    data = request.json
    seller_id = session.get('seller_id')
    new_status = data.get('status')
    tracking_number = data.get('tracking_number')
    
    valid_statuses = ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
    if new_status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {valid_statuses}'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    # Verify ownership
    cur.execute('SELECT seller_id FROM orders WHERE id = ?', (order_id,))
    order = cur.fetchone()
    
    if not order:
        conn.close()
        return jsonify({'error': 'Order not found'}), 404
    
    if order['seller_id'] != seller_id:
        conn.close()
        return jsonify({'error': 'Not authorized'}), 403
    
    updates = ['status = ?', 'updated_at = ?']
    params = [new_status, datetime.now().isoformat()]
    
    if tracking_number:
        updates.append('tracking_number = ?')
        params.append(tracking_number)
    
    params.append(order_id)
    cur.execute(f'UPDATE orders SET {", ".join(updates)} WHERE id = ?', params)
    
    # Update seller stats if delivered
    if new_status == 'delivered':
        cur.execute('UPDATE sellers SET total_sales = total_sales + 1 WHERE id = ?', (seller_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============================================
# SELLER ROUTES
# ============================================

@app.route('/api/sellers')
def get_sellers():
    """Get all sellers"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT s.*, COUNT(l.id) as listing_count
        FROM sellers s
        LEFT JOIN listings l ON s.id = l.seller_id AND l.status = 'active'
        GROUP BY s.id
        ORDER BY s.rating DESC, s.total_sales DESC
    ''')
    
    sellers = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    return jsonify({'sellers': sellers})

@app.route('/api/sellers/<seller_id>')
def get_seller(seller_id):
    """Get seller profile"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM sellers WHERE id = ?', (seller_id,))
    seller = cur.fetchone()
    
    if not seller:
        conn.close()
        return jsonify({'error': 'Seller not found'}), 404
    
    # Get recent reviews
    cur.execute('''
        SELECT r.*, u.username
        FROM reviews r
        JOIN users u ON r.buyer_id = u.id
        WHERE r.seller_id = ?
        ORDER BY r.created_at DESC
        LIMIT 10
    ''', (seller_id,))
    reviews = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    return jsonify({
        'seller': dict(seller),
        'reviews': reviews
    })

@app.route('/api/seller/profile', methods=['PUT'])
@seller_required
def update_seller_profile():
    """Update seller's own profile"""
    data = request.json
    seller_id = session.get('seller_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    updates = []
    params = []
    
    for field in ['shop_name', 'description', 'logo_url', 'location', 
                  'shipping_policy', 'return_policy']:
        if field in data:
            updates.append(f'{field} = ?')
            params.append(data[field])
    
    if updates:
        params.append(seller_id)
        cur.execute(f'UPDATE sellers SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()
    
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/seller/stats')
@seller_required
def get_seller_stats():
    """Get seller's dashboard stats"""
    seller_id = session.get('seller_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    # Active listings count
    cur.execute('SELECT COUNT(*) FROM listings WHERE seller_id = ? AND status = "active"', 
                (seller_id,))
    active_listings = cur.fetchone()[0]
    
    # Total inventory value
    cur.execute('SELECT SUM(price * quantity) FROM listings WHERE seller_id = ? AND status = "active"',
                (seller_id,))
    inventory_value = cur.fetchone()[0] or 0
    
    # Pending orders
    cur.execute('SELECT COUNT(*) FROM orders WHERE seller_id = ? AND status = "pending"',
                (seller_id,))
    pending_orders = cur.fetchone()[0]
    
    # This month's sales
    month_start = datetime.now().replace(day=1).isoformat()
    cur.execute('''
        SELECT COUNT(*), SUM(total) FROM orders 
        WHERE seller_id = ? AND status = "delivered" AND created_at >= ?
    ''', (seller_id, month_start))
    row = cur.fetchone()
    monthly_orders = row[0] or 0
    monthly_revenue = row[1] or 0
    
    # Recent orders
    cur.execute('''
        SELECT o.*, u.username as buyer_name
        FROM orders o
        JOIN users u ON o.buyer_id = u.id
        WHERE o.seller_id = ?
        ORDER BY o.created_at DESC
        LIMIT 5
    ''', (seller_id,))
    recent_orders = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    return jsonify({
        'active_listings': active_listings,
        'inventory_value': inventory_value,
        'pending_orders': pending_orders,
        'monthly_orders': monthly_orders,
        'monthly_revenue': monthly_revenue,
        'recent_orders': recent_orders
    })

# ============================================
# BULK IMPORT FROM NEXUS
# ============================================

@app.route('/api/seller/import', methods=['POST'])
@seller_required
def import_from_nexus():
    """Import cards from NEXUS library JSON"""
    seller_id = session.get('seller_id')
    data = request.json
    cards = data.get('cards', [])
    
    if not cards:
        return jsonify({'error': 'No cards provided'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    imported = 0
    for card in cards:
        try:
            listing_id = str(uuid.uuid4())
            cur.execute('''
                INSERT INTO listings (
                    id, seller_id, card_name, set_code, set_name, collector_number,
                    rarity, condition, price, quantity, image_url, scryfall_id, foil
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                listing_id, seller_id,
                card.get('name'),
                card.get('set_code'),
                card.get('set_name'),
                card.get('collector_number'),
                card.get('rarity', 'common'),
                card.get('condition', 'NM'),
                float(card.get('price', 0)),
                int(card.get('quantity', 1)),
                card.get('image_url') or card.get('image_uris', {}).get('normal'),
                card.get('scryfall_id'),
                1 if card.get('foil') else 0
            ))
            imported += 1
        except Exception as e:
            print(f"Error importing card: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'imported': imported,
        'total': len(cards)
    })

# ============================================
# DOWNLOAD ROUTES (AUTH CODE REQUIRED)
# ============================================

DOWNLOAD_DIR = Path(__file__).parent / 'downloads'
DOWNLOAD_DIR.mkdir(exist_ok=True)

AVAILABLE_APPS = {
    'nexus-mtg-check': 'Magic: The Gathering card price lookup',
    'nexus-pokemon-check': 'Pokemon TCG card price lookup',
    'nexus-sports-check': 'Sports cards price lookup (Baseball/Basketball/Football/Hockey)'
}

def generate_download_code(length=8):
    """Generate a random download code"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    # Remove ambiguous characters
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
    return ''.join(random.choice(chars) for _ in range(length))

@app.route('/api/admin/download-codes', methods=['POST'])
def create_download_code():
    """Create a new download auth code (admin only)"""
    data = request.json
    admin_key = data.get('admin_key')

    # Simple admin key check (in prod, use proper auth)
    if admin_key != os.environ.get('ADMIN_KEY', 'nexus-admin-2026'):
        return jsonify({'error': 'Unauthorized'}), 401

    code = data.get('code') or generate_download_code()
    app_name = data.get('app_name')  # None = all apps
    max_uses = int(data.get('max_uses', 1))
    expires_days = int(data.get('expires_days', 30))

    code_id = str(uuid.uuid4())
    expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute('''
            INSERT INTO download_codes (id, code, app_name, created_by, expires_at, max_uses)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (code_id, code.upper(), app_name, 'admin', expires_at, max_uses))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Code already exists'}), 400

    conn.close()

    return jsonify({
        'success': True,
        'code': code.upper(),
        'app_name': app_name or 'all',
        'max_uses': max_uses,
        'expires_at': expires_at
    })

@app.route('/api/admin/download-codes')
def list_download_codes():
    """List all download codes (admin only)"""
    admin_key = request.args.get('admin_key')

    if admin_key != os.environ.get('ADMIN_KEY', 'nexus-admin-2026'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM download_codes ORDER BY created_at DESC')
    codes = [dict(row) for row in cur.fetchall()]
    conn.close()

    return jsonify({'codes': codes})

@app.route('/api/downloads')
def list_available_downloads():
    """List available apps for download"""
    return jsonify({
        'apps': [
            {'name': name, 'description': desc}
            for name, desc in AVAILABLE_APPS.items()
        ]
    })

@app.route('/api/downloads/verify', methods=['POST'])
def verify_download_code():
    """Verify a download code is valid"""
    data = request.json
    code = (data.get('code') or '').strip().upper()
    app_name = data.get('app_name')

    if not code:
        return jsonify({'error': 'Code required'}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT * FROM download_codes WHERE code = ? AND active = 1', (code,))
    code_row = cur.fetchone()
    conn.close()

    if not code_row:
        return jsonify({'valid': False, 'error': 'Invalid code'})

    # Check expiry
    if code_row['expires_at']:
        expires = datetime.fromisoformat(code_row['expires_at'])
        if datetime.now() > expires:
            return jsonify({'valid': False, 'error': 'Code expired'})

    # Check uses
    if code_row['max_uses'] and code_row['use_count'] >= code_row['max_uses']:
        return jsonify({'valid': False, 'error': 'Code usage limit reached'})

    # Check app restriction
    if code_row['app_name'] and app_name and code_row['app_name'] != app_name:
        return jsonify({'valid': False, 'error': 'Code not valid for this app'})

    return jsonify({
        'valid': True,
        'remaining_uses': (code_row['max_uses'] - code_row['use_count']) if code_row['max_uses'] else 'unlimited',
        'apps': [code_row['app_name']] if code_row['app_name'] else list(AVAILABLE_APPS.keys())
    })

@app.route('/api/downloads/<app_name>')
def download_app(app_name):
    """Download an app with auth code"""
    code = request.args.get('code', '').strip().upper()

    if app_name not in AVAILABLE_APPS:
        return jsonify({'error': 'App not found'}), 404

    if not code:
        return jsonify({'error': 'Download code required. Get one at nexus-cards.com'}), 401

    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT * FROM download_codes WHERE code = ? AND active = 1', (code,))
    code_row = cur.fetchone()

    if not code_row:
        conn.close()
        return jsonify({'error': 'Invalid download code'}), 401

    # Check expiry
    if code_row['expires_at']:
        expires = datetime.fromisoformat(code_row['expires_at'])
        if datetime.now() > expires:
            conn.close()
            return jsonify({'error': 'Download code expired'}), 401

    # Check uses
    if code_row['max_uses'] and code_row['use_count'] >= code_row['max_uses']:
        conn.close()
        return jsonify({'error': 'Download code usage limit reached'}), 401

    # Check app restriction
    if code_row['app_name'] and code_row['app_name'] != app_name:
        conn.close()
        return jsonify({'error': 'Code not valid for this app'}), 401

    # Check file exists
    zip_path = DOWNLOAD_DIR / f'{app_name}.zip'
    if not zip_path.exists():
        conn.close()
        return jsonify({'error': 'Download file not found'}), 404

    # Log download and increment use count
    log_id = str(uuid.uuid4())
    cur.execute('''
        INSERT INTO download_logs (id, code_id, app_name, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?)
    ''', (log_id, code_row['id'], app_name, request.remote_addr, request.user_agent.string))

    cur.execute('UPDATE download_codes SET use_count = use_count + 1 WHERE id = ?',
                (code_row['id'],))
    conn.commit()
    conn.close()

    # Serve the file
    return send_from_directory(DOWNLOAD_DIR, f'{app_name}.zip', as_attachment=True)

@app.route('/downloads')
def download_page():
    """Serve download page"""
    return '''<!DOCTYPE html>
<html>
<head>
    <title>NEXUS Downloads</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: system-ui, -apple-system, sans-serif; background: #0a0a0a; color: #fff; min-height: 100vh; }
        .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
        h1 { font-size: 2rem; margin-bottom: 8px; }
        .subtitle { color: #888; margin-bottom: 32px; }
        .card { background: #1a1a1a; border-radius: 12px; padding: 24px; margin-bottom: 16px; }
        .card h3 { margin-bottom: 8px; }
        .card p { color: #888; font-size: 14px; margin-bottom: 16px; }
        input { width: 100%; padding: 12px; border: 1px solid #333; border-radius: 8px; background: #0a0a0a; color: #fff; font-size: 16px; margin-bottom: 12px; }
        input:focus { outline: none; border-color: #10b981; }
        button { width: 100%; padding: 12px; border: none; border-radius: 8px; background: #10b981; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer; }
        button:hover { background: #059669; }
        button:disabled { background: #333; cursor: not-allowed; }
        .apps { display: flex; flex-direction: column; gap: 8px; margin-top: 16px; }
        .app-btn { background: #262626; text-align: left; display: flex; justify-content: space-between; align-items: center; }
        .app-btn:hover { background: #333; }
        .app-btn .icon { font-size: 24px; }
        .status { padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
        .status.error { background: #7f1d1d; }
        .status.success { background: #14532d; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 NEXUS Downloads</h1>
        <p class="subtitle">Reddit Devvit Apps for Card Price Lookup</p>

        <div class="card">
            <h3>Enter Download Code</h3>
            <p>Get your code from the NEXUS team or Kickstarter rewards</p>
            <div id="status" class="status hidden"></div>
            <input type="text" id="code" placeholder="Enter code (e.g. NEXUS-XXXX)" maxlength="20" />
            <button onclick="verifyCode()">Verify Code</button>
        </div>

        <div id="downloads" class="card hidden">
            <h3>Available Downloads</h3>
            <p>Click to download. Run <code>npm install</code> after extracting.</p>
            <div id="apps" class="apps"></div>
        </div>
    </div>

    <script>
        let validCode = '';

        async function verifyCode() {
            const code = document.getElementById('code').value.trim();
            const status = document.getElementById('status');

            if (!code) {
                status.className = 'status error';
                status.textContent = 'Please enter a code';
                status.classList.remove('hidden');
                return;
            }

            try {
                const res = await fetch('/api/downloads/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code })
                });
                const data = await res.json();

                if (data.valid) {
                    validCode = code;
                    status.className = 'status success';
                    status.textContent = '✓ Code valid! ' + (data.remaining_uses !== 'unlimited' ? `(${data.remaining_uses} uses remaining)` : '');
                    status.classList.remove('hidden');
                    showDownloads(data.apps);
                } else {
                    status.className = 'status error';
                    status.textContent = '✗ ' + data.error;
                    status.classList.remove('hidden');
                    document.getElementById('downloads').classList.add('hidden');
                }
            } catch (e) {
                status.className = 'status error';
                status.textContent = 'Error verifying code';
                status.classList.remove('hidden');
            }
        }

        function showDownloads(apps) {
            const container = document.getElementById('downloads');
            const appsDiv = document.getElementById('apps');

            const appInfo = {
                'nexus-mtg-check': { icon: '🃏', name: 'MTG Check', desc: 'Magic: The Gathering' },
                'nexus-pokemon-check': { icon: '⚡', name: 'Pokemon Check', desc: 'Pokemon TCG' },
                'nexus-sports-check': { icon: '🏆', name: 'Sports Check', desc: 'Baseball/Basketball/Football/Hockey' }
            };

            appsDiv.innerHTML = apps.map(app => {
                const info = appInfo[app] || { icon: '📦', name: app, desc: '' };
                return `<button class="app-btn" onclick="download('${app}')">
                    <span><span class="icon">${info.icon}</span> ${info.name}<br><small style="color:#888">${info.desc}</small></span>
                    <span>↓</span>
                </button>`;
            }).join('');

            container.classList.remove('hidden');
        }

        function download(app) {
            window.location.href = `/api/downloads/${app}?code=${validCode}`;
        }

        document.getElementById('code').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') verifyCode();
        });
    </script>
</body>
</html>'''

# ============================================
# STATIC FILES
# ============================================

@app.route('/')
def serve_index():
    """Serve the frontend"""
    return send_from_directory('.', 'index.html')

@app.route('/kickstarter')
def serve_kickstarter():
    """Serve the Kickstarter landing page"""
    return send_from_directory('.', 'kickstarter.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('.', path)

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print("🚀 NEXUS Marketplace V2 Server")
    print(f"   http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
