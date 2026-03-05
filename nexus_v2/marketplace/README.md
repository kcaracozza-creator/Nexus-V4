# NEXUS Marketplace V2

A full-featured card marketplace with multi-seller support, cart & checkout, and order management.

## Features

✅ **Browse & Search** - Full card browsing with filters (price, condition, rarity, foil)
✅ **Multi-Seller** - Multiple shops can list and sell cards
✅ **User Accounts** - Buyers and sellers with separate dashboards
✅ **Shopping Cart** - Add items from multiple sellers
✅ **Checkout** - Create orders with shipping address
✅ **Order Management** - Track orders, update status
✅ **Seller Dashboard** - Stats, manage listings, view orders
✅ **NEXUS Integration** - Import cards directly from NEXUS library

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the Server

```bash
python server.py
```

Server will start at: http://localhost:5000

### 3. Import Cards from NEXUS

```bash
python import_library.py "E:\MTTGG\PYTHON SOURCE FILES\data\nexus_library.json"
```

### 4. Create a Seller Account

1. Go to http://localhost:5000
2. Click "Sign Up"
3. Select "Sell Cards"
4. Enter shop name

## API Endpoints

### Auth
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Current user

### Listings
- `GET /api/listings` - Browse listings (with filters)
- `GET /api/listings/:id` - Single listing
- `POST /api/listings` - Create listing (seller)
- `PUT /api/listings/:id` - Update listing (seller)
- `DELETE /api/listings/:id` - Delete listing (seller)

### Cart
- `GET /api/cart` - Get cart
- `POST /api/cart` - Add to cart
- `PUT /api/cart/:id` - Update quantity
- `DELETE /api/cart/:id` - Remove item
- `POST /api/cart/clear` - Clear cart

### Orders
- `POST /api/orders` - Checkout (create orders)
- `GET /api/orders` - List orders
- `GET /api/orders/:id` - Order details
- `PUT /api/orders/:id/status` - Update status (seller)

### Sellers
- `GET /api/sellers` - List sellers
- `GET /api/sellers/:id` - Seller profile
- `PUT /api/seller/profile` - Update profile (seller)
- `GET /api/seller/stats` - Dashboard stats (seller)
- `POST /api/seller/import` - Bulk import cards (seller)

## Deployment

### Local Development
```bash
python server.py
```

### Production (Render)
1. Create new Web Service
2. Connect GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn server:app`
5. Add environment variable: `SECRET_KEY=your-secret-key`

### Production (Your Server)
```bash
# Install
pip install -r requirements.txt gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 server:app

# Or use systemd service
sudo nano /etc/systemd/system/nexus-marketplace.service
```

Example systemd service:
```ini
[Unit]
Description=NEXUS Marketplace
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/nexus-marketplace
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:5000 server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## Database

SQLite database (`marketplace.db`) with tables:
- `users` - User accounts
- `sellers` - Seller profiles
- `listings` - Card listings
- `cart_items` - Shopping cart
- `orders` - Orders
- `order_items` - Items in orders
- `reviews` - Seller reviews

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JS + CSS
- **Database**: SQLite
- **Auth**: Session-based with werkzeug password hashing

## License

Copyright (c) 2025 Kevin Caracozza. All Rights Reserved.
PATENT PENDING
