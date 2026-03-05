"""
NEXUS API Server — ZULTAN (192.168.1.152:8000)
===============================================
Central API gateway for the NEXUS ecosystem.

Services:
  - Card data & metadata lookup
  - Market data collection (Flow 9: The Data Moat)
  - Price aggregation & authority
  - Dev dashboard

This is NOT the marketplace (that's on Cloudflare Workers).
This is the brain — pricing oracle, data warehouse, intelligence hub.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import json
from datetime import datetime

# Import routers
from routers.market_data import router as market_data_router

app = FastAPI(
    title="NEXUS API — ZULTAN",
    version="2.0.0",
    description="Card data gateway, pricing oracle, and market intelligence"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================================================
# Mount Routers
# ================================================================
app.include_router(market_data_router)

# ================================================================
# Core Endpoints
# ================================================================
dev_messages = []
cards_db = {}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "nexus-api-zultan",
        "version": "2.0.0",
        "host": "192.168.1.152:8000",
        "time": datetime.now().isoformat(),
        "modules": ["market_data", "dev_dashboard"]
    }


@app.get("/")
def root():
    return {
        "message": "NEXUS ZULTAN Server Live",
        "domain": "nexus-cards.com",
        "role": "Card data gateway + pricing oracle",
        "endpoints": {
            "core": ["/health", "/dev", "/cards/search"],
            "market_data": [
                "/api/market/scan-event",
                "/api/market/sale-event",
                "/api/market/price",
                "/api/market/batch",
                "/api/market/stats"
            ]
        }
    }


# ================================================================
# Card Search (connects to Scryfall cache / local DB)
# ================================================================
@app.get("/cards/search")
def search_cards(q: str = Query(..., min_length=2)):
    # TODO: Connect to Scryfall cache DB / PostgreSQL
    return {"query": q, "results": [], "message": "Database not loaded yet"}


# ================================================================
# Dev Dashboard
# ================================================================
@app.get("/dev", response_class=HTMLResponse)
def dev_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>NEXUS Dev Dashboard</title>
        <style>
            body { background: #0a0a0f; color: #e0e0e0; font-family: 'Consolas', monospace; padding: 20px; }
            h1 { color: #ffd700; }
            .message { background: #1a1a25; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 3px solid #4ade80; }
            .message.mendel { border-left-color: #f87171; }
            .message.kevin { border-left-color: #ffd700; }
            .author { font-weight: bold; margin-bottom: 5px; }
            .clouse .author { color: #4ade80; }
            .mendel .author { color: #f87171; }
            .kevin .author { color: #ffd700; }
            .time { color: #888; font-size: 12px; }
            .stats { background: #12121a; padding: 20px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 30px; flex-wrap: wrap; }
            .stat { }
            .stat-value { font-size: 24px; color: #ffd700; }
            .stat-label { font-size: 12px; color: #888; }
            #messages { max-height: 500px; overflow-y: auto; }
            form { margin-top: 20px; }
            input, select { background: #1a1a25; border: 1px solid #333; color: white; padding: 10px; margin: 5px; border-radius: 4px; }
            button { background: #4ade80; color: black; border: none; padding: 10px 20px; cursor: pointer; border-radius: 4px; font-weight: bold; }
            .moat { background: #12121a; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #4ade80; }
            .moat h2 { color: #4ade80; margin-top: 0; }
        </style>
    </head>
    <body>
        <h1>NEXUS ZULTAN — Dev Dashboard</h1>

        <div class="moat">
            <h2>DATA MOAT (Flow 9)</h2>
            <div class="stats" id="moatStats">
                <div class="stat"><div class="stat-value" id="totalScans">-</div><div class="stat-label">Scan Events</div></div>
                <div class="stat"><div class="stat-value" id="totalSales">-</div><div class="stat-label">Sale Events</div></div>
                <div class="stat"><div class="stat-value" id="uniqueCards">-</div><div class="stat-label">Unique Cards</div></div>
                <div class="stat"><div class="stat-value" id="totalVolume">-</div><div class="stat-label">Sales Volume</div></div>
                <div class="stat"><div class="stat-value" id="cachedPrices">-</div><div class="stat-label">Priced Cards</div></div>
                <div class="stat"><div class="stat-value" id="moatStatus">-</div><div class="stat-label">Status</div></div>
            </div>
        </div>

        <div class="stats">
            <div class="stat"><div class="stat-value" id="msgCount">0</div><div class="stat-label">Messages</div></div>
            <div class="stat"><div class="stat-value">🟢</div><div class="stat-label">Server</div></div>
        </div>

        <div id="messages"></div>
        <form onsubmit="sendMessage(event)">
            <select id="author"><option value="kevin">Kevin</option><option value="clouse">Clouse</option><option value="mendel">Mendel</option></select>
            <input type="text" id="msg" placeholder="Type message..." style="width: 400px;">
            <button type="submit">Send</button>
        </form>
        <script>
            async function loadMoatStats() {
                try {
                    const res = await fetch('/api/market/stats');
                    const s = await res.json();
                    document.getElementById('totalScans').textContent = s.total_scan_events.toLocaleString();
                    document.getElementById('totalSales').textContent = s.total_sale_events.toLocaleString();
                    document.getElementById('uniqueCards').textContent = s.unique_cards_scanned.toLocaleString();
                    document.getElementById('totalVolume').textContent = '$' + s.total_sales_volume_usd.toLocaleString();
                    document.getElementById('cachedPrices').textContent = s.cached_prices.toLocaleString();
                    document.getElementById('moatStatus').textContent = s.moat_status.toUpperCase();
                } catch(e) {
                    console.error('Moat stats failed:', e);
                }
            }
            async function loadMessages() {
                const res = await fetch('/dev/messages');
                const messages = await res.json();
                document.getElementById('msgCount').textContent = messages.length;
                document.getElementById('messages').innerHTML = messages.map(m =>
                    '<div class="message ' + m.author + '"><div class="author">' + m.author.toUpperCase() + '</div><div>' + m.text + '</div><div class="time">' + m.time + '</div></div>'
                ).join('');
            }
            async function sendMessage(e) {
                e.preventDefault();
                await fetch('/dev/messages', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({author: document.getElementById('author').value, text: document.getElementById('msg').value})
                });
                document.getElementById('msg').value = '';
                loadMessages();
            }
            loadMoatStats();
            loadMessages();
            setInterval(loadMoatStats, 30000);
            setInterval(loadMessages, 5000);
        </script>
    </body>
    </html>
    """


@app.get("/dev/messages")
def get_messages():
    return dev_messages


@app.post("/dev/messages")
def post_message(data: dict):
    dev_messages.append({
        "author": data.get("author", "unknown"),
        "text": data.get("text", ""),
        "time": datetime.now().strftime("%H:%M:%S")
    })
    return {"status": "sent"}
