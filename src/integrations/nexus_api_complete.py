"""
NEXUS SERVER API - COMPLETE BACKEND
All endpoints for card search, pricing, shops, backups, analytics
Drop this on the server: ~/nexus-api/main.py
"""

from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
import json
import hashlib
import secrets
import asyncio

app = FastAPI(
    title="NEXUS Card API",
    description="Backend for NEXUS Card Management System",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ============================================================
# DATABASE FILES (JSON for now, PostgreSQL later)
# ============================================================
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

CARDS_FILE = DATA_DIR / "cards.json"
PRICES_FILE = DATA_DIR / "price_history.json"
SHOPS_FILE = DATA_DIR / "shops.json"
MESSAGES_FILE = DATA_DIR / "messages.json"
BACKUPS_DIR = DATA_DIR / "backups"
BACKUPS_DIR.mkdir(exist_ok=True)

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def load_json(file: Path) -> dict | list:
    if file.exists():
        return json.loads(file.read_text())
    return {} if "history" in str(file) or "shops" in str(file) else []

def save_json(file: Path, data):
    file.write_text(json.dumps(data, indent=2, default=str))

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_api_key() -> str:
    return f"nxs_{secrets.token_hex(24)}"

# ============================================================
# HEALTH & STATUS
# ============================================================
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "nexus-api",
        "version": "2.0.0",
        "time": datetime.now().isoformat()
    }

@app.get("/status")
def status():
    cards = load_json(CARDS_FILE)
    shops = load_json(SHOPS_FILE)
    prices = load_json(PRICES_FILE)
    
    return {
        "status": "online",
        "cards_in_db": len(cards),
        "registered_shops": len(shops),
        "price_records": sum(len(v) for v in prices.values()),
        "uptime": "healthy",
        "last_sync": datetime.now().isoformat()
    }

# ============================================================
# CARD SEARCH API
# ============================================================
@app.get("/cards/search")
def search_cards(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, le=500),
    offset: int = 0,
    set_code: Optional[str] = None,
    color: Optional[str] = None,
    type_line: Optional[str] = None,
    rarity: Optional[str] = None
):
    """
    Search cards by name, with optional filters
    """
    cards = load_json(CARDS_FILE)
    
    results = []
    query = q.lower()
    
    for card in cards:
        if not isinstance(card, dict):
            continue
            
        name = card.get('name', '').lower()
        
        # Name match
        if query not in name:
            continue
        
        # Apply filters
        if set_code and card.get('set', '').lower() != set_code.lower():
            continue
        if color and color.upper() not in card.get('colors', ''):
            continue
        if type_line and type_line.lower() not in card.get('type_line', '').lower():
            continue
        if rarity and card.get('rarity', '').lower() != rarity.lower():
            continue
        
        results.append(card)
    
    # Pagination
    total = len(results)
    results = results[offset:offset + limit]
    
    return {
        "query": q,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results
    }

@app.get("/cards/{card_id}")
def get_card(card_id: str):
    """Get a specific card by ID (scryfall_id or uuid)"""
    cards = load_json(CARDS_FILE)
    
    for card in cards:
        if isinstance(card, dict):
            if card.get('scryfall_id') == card_id or card.get('uuid') == card_id:
                return card
    
    raise HTTPException(status_code=404, detail="Card not found")

@app.post("/cards/bulk")
def get_cards_bulk(card_ids: List[str]):
    """Get multiple cards by ID"""
    cards = load_json(CARDS_FILE)
    
    id_set = set(card_ids)
    results = []
    
    for card in cards:
        if isinstance(card, dict):
            if card.get('scryfall_id') in id_set or card.get('uuid') in id_set:
                results.append(card)
    
    return {"requested": len(card_ids), "found": len(results), "cards": results}

@app.post("/cards/import")
def import_cards(cards: List[dict]):
    """Import cards from NEXUS client"""
    existing = load_json(CARDS_FILE)
    
    # Merge by scryfall_id
    existing_ids = {c.get('scryfall_id') for c in existing if isinstance(c, dict)}
    
    added = 0
    for card in cards:
        if card.get('scryfall_id') not in existing_ids:
            existing.append(card)
            added += 1
    
    save_json(CARDS_FILE, existing)
    
    return {"imported": added, "total": len(existing)}

# ============================================================
# PRICE HISTORY API
# ============================================================
@app.get("/prices/{card_id}")
def get_price_history(card_id: str, days: int = 30):
    """Get price history for a card"""
    prices = load_json(PRICES_FILE)
    
    history = prices.get(card_id, [])
    
    # Filter by days
    cutoff = datetime.now() - timedelta(days=days)
    history = [p for p in history if datetime.fromisoformat(p['date']) > cutoff]
    
    return {
        "card_id": card_id,
        "days": days,
        "records": len(history),
        "history": history,
        "current": history[-1] if history else None
    }

@app.post("/prices/{card_id}")
def record_price(card_id: str, price: float, source: str = "manual"):
    """Record a price point for a card"""
    prices = load_json(PRICES_FILE)
    
    if card_id not in prices:
        prices[card_id] = []
    
    prices[card_id].append({
        "date": datetime.now().isoformat(),
        "price": price,
        "source": source
    })
    
    # Keep last 365 days only
    cutoff = datetime.now() - timedelta(days=365)
    prices[card_id] = [
        p for p in prices[card_id] 
        if datetime.fromisoformat(p['date']) > cutoff
    ]
    
    save_json(PRICES_FILE, prices)
    
    return {"status": "recorded", "card_id": card_id, "price": price}

@app.post("/prices/bulk")
def record_prices_bulk(price_updates: List[dict]):
    """Record multiple prices at once"""
    prices = load_json(PRICES_FILE)
    recorded = 0
    
    for update in price_updates:
        card_id = update.get('card_id')
        price = update.get('price')
        
        if not card_id or price is None:
            continue
        
        if card_id not in prices:
            prices[card_id] = []
        
        prices[card_id].append({
            "date": datetime.now().isoformat(),
            "price": price,
            "source": update.get('source', 'bulk')
        })
        recorded += 1
    
    save_json(PRICES_FILE, prices)
    
    return {"recorded": recorded}

# ============================================================
# SHOP REGISTRATION & AUTH
# ============================================================
@app.post("/shops/register")
def register_shop(
    shop_name: str,
    owner_name: str,
    email: str,
    password: str
):
    """Register a new shop"""
    shops = load_json(SHOPS_FILE)
    
    # Check if exists
    if email in shops:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    api_key = generate_api_key()
    
    shops[email] = {
        "shop_name": shop_name,
        "owner_name": owner_name,
        "email": email,
        "password_hash": hash_password(password),
        "api_key": api_key,
        "created": datetime.now().isoformat(),
        "last_sync": None,
        "cards_synced": 0,
        "status": "active"
    }
    
    save_json(SHOPS_FILE, shops)
    
    return {
        "status": "registered",
        "shop_name": shop_name,
        "api_key": api_key,
        "message": "Save your API key! You'll need it for all requests."
    }

@app.post("/shops/auth")
def authenticate_shop(email: str, password: str):
    """Authenticate and get API key"""
    shops = load_json(SHOPS_FILE)
    
    shop = shops.get(email)
    if not shop:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if shop['password_hash'] != hash_password(password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "status": "authenticated",
        "shop_name": shop['shop_name'],
        "api_key": shop['api_key']
    }

@app.get("/shops/me")
def get_shop_info(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current shop info (requires API key)"""
    if not credentials:
        raise HTTPException(status_code=401, detail="API key required")
    
    shops = load_json(SHOPS_FILE)
    
    for email, shop in shops.items():
        if shop['api_key'] == credentials.credentials:
            return {
                "shop_name": shop['shop_name'],
                "email": email,
                "created": shop['created'],
                "last_sync": shop['last_sync'],
                "cards_synced": shop['cards_synced']
            }
    
    raise HTTPException(status_code=401, detail="Invalid API key")

# ============================================================
# BACKUP API
# ============================================================
@app.post("/backup")
def create_backup(
    library_data: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Backup NEXUS library to server"""
    if not credentials:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Find shop
    shops = load_json(SHOPS_FILE)
    shop_email = None
    
    for email, shop in shops.items():
        if shop['api_key'] == credentials.credentials:
            shop_email = email
            break
    
    if not shop_email:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shop_dir = BACKUPS_DIR / shop_email.replace('@', '_at_').replace('.', '_')
    shop_dir.mkdir(exist_ok=True)
    
    backup_file = shop_dir / f"backup_{timestamp}.json"
    
    backup_data = {
        "timestamp": datetime.now().isoformat(),
        "shop": shop_email,
        "library": library_data
    }
    
    save_json(backup_file, backup_data)
    
    # Update shop last sync
    shops[shop_email]['last_sync'] = datetime.now().isoformat()
    shops[shop_email]['cards_synced'] = library_data.get('total_cards', 0)
    save_json(SHOPS_FILE, shops)
    
    # Keep only last 10 backups
    backups = sorted(shop_dir.glob("backup_*.json"))
    for old_backup in backups[:-10]:
        old_backup.unlink()
    
    return {
        "status": "backed_up",
        "timestamp": timestamp,
        "cards": library_data.get('total_cards', 0),
        "file": str(backup_file.name)
    }

@app.get("/backup/list")
def list_backups(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """List available backups"""
    if not credentials:
        raise HTTPException(status_code=401, detail="API key required")
    
    shops = load_json(SHOPS_FILE)
    shop_email = None
    
    for email, shop in shops.items():
        if shop['api_key'] == credentials.credentials:
            shop_email = email
            break
    
    if not shop_email:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    shop_dir = BACKUPS_DIR / shop_email.replace('@', '_at_').replace('.', '_')
    
    if not shop_dir.exists():
        return {"backups": []}
    
    backups = []
    for f in sorted(shop_dir.glob("backup_*.json"), reverse=True):
        data = load_json(f)
        backups.append({
            "file": f.name,
            "timestamp": data.get('timestamp'),
            "cards": data.get('library', {}).get('total_cards', 0)
        })
    
    return {"backups": backups}

@app.get("/backup/restore/{filename}")
def restore_backup(filename: str, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Restore a backup"""
    if not credentials:
        raise HTTPException(status_code=401, detail="API key required")
    
    shops = load_json(SHOPS_FILE)
    shop_email = None
    
    for email, shop in shops.items():
        if shop['api_key'] == credentials.credentials:
            shop_email = email
            break
    
    if not shop_email:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    shop_dir = BACKUPS_DIR / shop_email.replace('@', '_at_').replace('.', '_')
    backup_file = shop_dir / filename
    
    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    
    data = load_json(backup_file)
    
    return {
        "status": "restored",
        "timestamp": data.get('timestamp'),
        "library": data.get('library')
    }

# ============================================================
# ANALYTICS API
# ============================================================
@app.get("/analytics/summary")
def get_analytics_summary(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get analytics summary"""
    cards = load_json(CARDS_FILE)
    prices = load_json(PRICES_FILE)
    
    # Calculate stats
    total_cards = len(cards)
    cards_with_prices = len(prices)
    
    # Price trends (cards that went up/down)
    trending_up = 0
    trending_down = 0
    
    for card_id, history in prices.items():
        if len(history) >= 2:
            old_price = history[-2]['price']
            new_price = history[-1]['price']
            if new_price > old_price:
                trending_up += 1
            elif new_price < old_price:
                trending_down += 1
    
    return {
        "total_cards": total_cards,
        "cards_with_prices": cards_with_prices,
        "trending_up": trending_up,
        "trending_down": trending_down,
        "generated": datetime.now().isoformat()
    }

@app.get("/analytics/top-movers")
def get_top_movers(days: int = 7, limit: int = 10):
    """Get cards with biggest price changes"""
    prices = load_json(PRICES_FILE)
    cards = load_json(CARDS_FILE)
    
    # Build card name lookup
    card_names = {}
    for card in cards:
        if isinstance(card, dict):
            card_names[card.get('scryfall_id', '')] = card.get('name', 'Unknown')
    
    cutoff = datetime.now() - timedelta(days=days)
    movers = []
    
    for card_id, history in prices.items():
        recent = [p for p in history if datetime.fromisoformat(p['date']) > cutoff]
        
        if len(recent) >= 2:
            old_price = recent[0]['price']
            new_price = recent[-1]['price']
            
            if old_price > 0:
                change_pct = ((new_price - old_price) / old_price) * 100
                movers.append({
                    "card_id": card_id,
                    "name": card_names.get(card_id, 'Unknown'),
                    "old_price": old_price,
                    "new_price": new_price,
                    "change": new_price - old_price,
                    "change_pct": round(change_pct, 2)
                })
    
    # Sort by absolute change percentage
    movers.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    
    return {
        "days": days,
        "top_gainers": [m for m in movers if m['change_pct'] > 0][:limit],
        "top_losers": [m for m in movers if m['change_pct'] < 0][:limit]
    }

# ============================================================
# DEV DASHBOARD (Messages)
# ============================================================
@app.get("/dev", response_class=HTMLResponse)
def dev_dashboard():
    """Live dev chat dashboard"""
    return """<!DOCTYPE html>
<html><head><title>NEXUS Dev</title>
<style>
body{background:#0a0a0f;color:#e0e0e0;font-family:'Consolas',monospace;padding:20px;margin:0}
h1{color:#ffd700;margin-bottom:20px}
.stats{display:flex;gap:20px;margin-bottom:20px}
.stat{background:#1a1a25;padding:15px;border-radius:8px;text-align:center}
.stat-value{font-size:24px;color:#ffd700}
.stat-label{font-size:12px;color:#888}
.msg{background:#1a1a25;padding:12px;margin:8px 0;border-radius:8px;border-left:3px solid #4ade80}
.msg.mendel{border-color:#f87171}
.msg.kevin{border-color:#ffd700}
.msg.clouse{border-color:#4ade80}
.author{font-weight:bold;margin-right:10px}
.author.kevin{color:#ffd700}
.author.clouse{color:#4ade80}
.author.mendel{color:#f87171}
.time{color:#666;font-size:12px}
.text{margin-top:5px}
#messages{max-height:500px;overflow-y:auto;margin-bottom:20px}
.input-row{display:flex;gap:10px}
select,input{background:#1a1a25;border:1px solid #333;color:white;padding:10px;border-radius:4px}
input{flex:1}
button{background:#4ade80;color:black;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;font-weight:bold}
button:hover{background:#3bca71}
.footer{margin-top:20px;color:#666;font-style:italic;text-align:center}
</style></head>
<body>
<h1>🔧 NEXUS DEV DASHBOARD</h1>
<div class="stats">
<div class="stat"><div class="stat-value">26,850</div><div class="stat-label">Cards</div></div>
<div class="stat"><div class="stat-value" id="msgCount">0</div><div class="stat-label">Messages</div></div>
<div class="stat"><div class="stat-value">🟢</div><div class="stat-label">Server</div></div>
<div class="stat"><div class="stat-value">$163M</div><div class="stat-label">Yacht Goal</div></div>
</div>
<div id="messages"></div>
<div class="input-row">
<select id="author">
<option value="kevin">👑 Kevin</option>
<option value="clouse">🤘 Clouse</option>
<option value="mendel">💀 Mendel</option>
</select>
<input type="text" id="text" placeholder="Type message..." onkeypress="if(event.key==='Enter')send()">
<button onclick="send()">Send</button>
</div>
<div class="footer">"Humbling AI Since '25" - NJ to Beijing, no passport needed 🌉</div>
<script>
async function load(){
  const r=await fetch('/dev/messages');
  const msgs=await r.json();
  document.getElementById('msgCount').textContent=msgs.length;
  document.getElementById('messages').innerHTML=msgs.map(m=>
    '<div class="msg '+m.author+'"><span class="author '+m.author+'">'+m.author.toUpperCase()+'</span><span class="time">'+m.time+'</span><div class="text">'+m.text+'</div></div>'
  ).join('');
  document.getElementById('messages').scrollTop=999999;
}
async function send(){
  const a=document.getElementById('author').value;
  const t=document.getElementById('text').value;
  if(!t)return;
  await fetch('/dev/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({author:a,text:t})});
  document.getElementById('text').value='';
  load();
}
load();
setInterval(load,3000);
</script>
</body></html>"""

@app.get("/dev/messages")
def get_messages():
    return load_json(MESSAGES_FILE)

@app.post("/dev/messages")
def post_message(data: dict):
    msgs = load_json(MESSAGES_FILE)
    msgs.append({
        "author": data.get("author", "unknown"),
        "text": data.get("text", ""),
        "time": datetime.now().strftime("%H:%M:%S")
    })
    # Keep last 100 messages
    msgs = msgs[-100:]
    save_json(MESSAGES_FILE, msgs)
    return {"status": "sent"}

# ============================================================
# STARTUP
# ============================================================
@app.on_event("startup")
async def startup():
    """Initialize data files"""
    for f in [CARDS_FILE, PRICES_FILE, SHOPS_FILE, MESSAGES_FILE]:
        if not f.exists():
            save_json(f, [] if f == CARDS_FILE or f == MESSAGES_FILE else {})
    print("🚀 NEXUS API Started")
    print(f"📁 Data directory: {DATA_DIR}")

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
