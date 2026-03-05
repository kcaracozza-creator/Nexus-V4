/**
 * NEXUS Marketplace API Worker
 * Cloudflare Worker + D1 backend for card marketplace
 * Kevin Caracozza - NEXUS V2
 */

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

// Marketplace commission rates by subscription tier
const FEE_RATES = {
  free: 0.08,      // 8% for free tier
  basic: 0.07,     // 7% for basic subscription
  premium: 0.06,   // 6% for premium subscription
};
const DEFAULT_FEE_RATE = 0.08; // Default to 8% if no subscription

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
  });
}

function err(message, status = 400) {
  return json({ error: message }, status);
}

function uuid() {
  return crypto.randomUUID();
}

function matchRoute(pathname, pattern) {
  const pp = pattern.split('/');
  const parts = pathname.split('/');
  if (pp.length !== parts.length) return null;
  const params = {};
  for (let i = 0; i < pp.length; i++) {
    if (pp[i].startsWith(':')) params[pp[i].slice(1)] = decodeURIComponent(parts[i]);
    else if (pp[i] !== parts[i]) return null;
  }
  return params;
}

// ── Cards ────────────────────────────────────────────────────────────
async function cardSearch(db, url) {
  const q = url.searchParams.get('q');
  const type = url.searchParams.get('type');
  const set = url.searchParams.get('set');
  const year = url.searchParams.get('year');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  const offset = parseInt(url.searchParams.get('offset') || '0');

  let sql = 'SELECT * FROM cards WHERE 1=1';
  const p = [];
  if (q) { sql += ' AND card_name LIKE ?'; p.push(`%${q}%`); }
  if (type) { sql += ' AND card_type = ?'; p.push(type); }
  if (set) { sql += ' AND (set_code = ? OR set_name LIKE ?)'; p.push(set, `%${set}%`); }
  if (year) { sql += ' AND year = ?'; p.push(parseInt(year)); }
  sql += ' ORDER BY card_name ASC LIMIT ? OFFSET ?';
  p.push(limit, offset);

  const r = await db.prepare(sql).bind(...p).all();
  return json({ cards: r.results, count: r.results.length, offset, limit });
}

async function cardGet(db, id) {
  const card = await db.prepare('SELECT * FROM cards WHERE id = ?').bind(id).first();
  if (!card) return err('Card not found', 404);
  return json({ card });
}

async function cardCreate(db, body) {
  const { card_name, set_code, set_name, collector_number, card_type, rarity, year,
          image_url, price_market, price_low, price_high, price_source,
          psa_pop_10, psa_pop_9, psa_total_graded, faiss_index } = body;
  if (!card_name) return err('card_name required');

  const id = uuid();
  await db.prepare(
    `INSERT INTO cards (id, card_name, set_code, set_name, collector_number, card_type, rarity, year,
     image_url, price_market, price_low, price_high, price_source,
     psa_pop_10, psa_pop_9, psa_total_graded, faiss_index)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(id, card_name, set_code||null, set_name||null, collector_number||null,
         card_type||'mtg', rarity||null, year||null,
         image_url||null, price_market||null, price_low||null, price_high||null, price_source||null,
         psa_pop_10||0, psa_pop_9||0, psa_total_graded||0, faiss_index||null).run();

  return json({ id, card_name }, 201);
}

async function cardUpdate(db, id, body) {
  const allowed = ['card_name','set_code','set_name','collector_number','card_type','rarity','year',
    'image_url','image_r2_key','price_market','price_low','price_high','price_source',
    'psa_pop_10','psa_pop_9','psa_total_graded','faiss_index'];
  const fields = [], p = [];
  for (const [k, v] of Object.entries(body)) {
    if (allowed.includes(k)) { fields.push(`${k} = ?`); p.push(v); }
  }
  if (!fields.length) return err('No valid fields');
  fields.push("updated_at = datetime('now')");
  p.push(id);
  await db.prepare(`UPDATE cards SET ${fields.join(', ')} WHERE id = ?`).bind(...p).run();
  return json({ id, updated: true });
}

// ── Users ────────────────────────────────────────────────────────────
async function userCreate(db, body) {
  const { username, email, shop_name, role } = body;
  if (!username) return err('username required');
  const id = uuid();
  try {
    await db.prepare(
      `INSERT INTO users (id, username, email, shop_name, role) VALUES (?,?,?,?,?)`
    ).bind(id, username, email||null, shop_name||null, role||'user').run();
    return json({ id, username }, 201);
  } catch (e) {
    if (e.message?.includes('UNIQUE')) return err('Username or email already exists', 409);
    throw e;
  }
}

async function userGet(db, id) {
  const user = await db.prepare('SELECT * FROM users WHERE id = ?').bind(id).first();
  if (!user) return err('User not found', 404);
  return json({ user });
}

async function userByUsername(db, username) {
  const user = await db.prepare('SELECT * FROM users WHERE username = ?').bind(username).first();
  if (!user) return err('User not found', 404);
  return json({ user });
}

// ── Sellers ──────────────────────────────────────────────────────────
async function sellerCreate(db, body) {
  const { user_id, shop_name, description, location, shipping_policy, return_policy } = body;
  if (!user_id || !shop_name) return err('user_id and shop_name required');
  const id = uuid();
  await db.prepare(
    `INSERT INTO sellers (id, user_id, shop_name, description, location, shipping_policy, return_policy)
     VALUES (?,?,?,?,?,?,?)`
  ).bind(id, user_id, shop_name, description||null, location||null,
         shipping_policy||null, return_policy||null).run();
  // Link seller to user
  await db.prepare('UPDATE users SET shop_id = ?, shop_name = ? WHERE id = ?')
    .bind(id, shop_name, user_id).run();
  return json({ id, shop_name }, 201);
}

async function sellerGet(db, id) {
  const seller = await db.prepare(
    `SELECT s.*, u.username FROM sellers s LEFT JOIN users u ON s.user_id = u.id WHERE s.id = ?`
  ).bind(id).first();
  if (!seller) return err('Seller not found', 404);
  return json({ seller });
}

async function sellerList(db, url) {
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  const r = await db.prepare(
    `SELECT s.*, u.username FROM sellers s LEFT JOIN users u ON s.user_id = u.id
     ORDER BY s.total_sales DESC LIMIT ?`
  ).bind(limit).all();
  return json({ sellers: r.results, count: r.results.length });
}

// ── Listings ─────────────────────────────────────────────────────────
async function listingSearch(db, url) {
  const cardId = url.searchParams.get('card_id');
  const sellerId = url.searchParams.get('seller_id');
  const status = url.searchParams.get('status') || 'active';
  const sort = url.searchParams.get('sort') || 'created_at';
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  const offset = parseInt(url.searchParams.get('offset') || '0');

  let sql = `SELECT l.*, c.card_name, c.set_name, c.card_type, c.rarity, c.image_url,
             u.username as seller_name
             FROM listings l
             LEFT JOIN cards c ON l.card_id = c.id
             LEFT JOIN users u ON l.seller_id = u.id
             WHERE l.status = ?`;
  const p = [status];
  if (cardId) { sql += ' AND l.card_id = ?'; p.push(cardId); }
  if (sellerId) { sql += ' AND l.seller_id = ?'; p.push(sellerId); }

  const validSorts = ['created_at', 'price'];
  const sortCol = validSorts.includes(sort) ? sort : 'created_at';
  sql += ` ORDER BY l.${sortCol} DESC LIMIT ? OFFSET ?`;
  p.push(limit, offset);

  const r = await db.prepare(sql).bind(...p).all();
  return json({ listings: r.results, count: r.results.length, offset, limit });
}

async function listingGet(db, id) {
  const listing = await db.prepare(
    `SELECT l.*, c.card_name, c.set_name, c.card_type, c.rarity, c.image_url,
     u.username as seller_name
     FROM listings l
     LEFT JOIN cards c ON l.card_id = c.id
     LEFT JOIN users u ON l.seller_id = u.id
     WHERE l.id = ?`
  ).bind(id).first();
  if (!listing) return err('Listing not found', 404);
  return json({ listing });
}

async function listingCreate(db, body) {
  const { card_id, seller_id, price, condition, grade, grade_service,
          quantity, currency, image_r2_key, scan_data } = body;
  if (!card_id || !seller_id || !price) return err('card_id, seller_id, price required');

  const id = uuid();
  await db.prepare(
    `INSERT INTO listings (id, card_id, seller_id, price, condition, grade, grade_service,
     quantity, currency, image_r2_key, scan_data, status)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(id, card_id, seller_id, price, condition||null, grade||null, grade_service||null,
         quantity||1, currency||'USD', image_r2_key||null, scan_data||null, 'active').run();

  return json({ id, status: 'active' }, 201);
}

async function listingUpdate(db, id, body) {
  const allowed = ['price','condition','grade','grade_service','quantity','status','image_r2_key','scan_data'];
  const fields = [], p = [];
  for (const [k, v] of Object.entries(body)) {
    if (allowed.includes(k)) { fields.push(`${k} = ?`); p.push(v); }
  }
  if (!fields.length) return err('No valid fields');
  if (body.status === 'sold') fields.push("sold_at = datetime('now')");
  p.push(id);
  await db.prepare(`UPDATE listings SET ${fields.join(', ')} WHERE id = ?`).bind(...p).run();
  return json({ id, updated: true });
}

// ── Inventory ────────────────────────────────────────────────────────
async function inventoryList(db, url) {
  const userId = url.searchParams.get('user_id');
  if (!userId) return err('user_id required');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '100'), 200);
  const offset = parseInt(url.searchParams.get('offset') || '0');

  const r = await db.prepare(
    `SELECT i.*, c.card_name, c.set_name, c.card_type, c.rarity, c.image_url
     FROM inventory i LEFT JOIN cards c ON i.card_id = c.id
     WHERE i.user_id = ? ORDER BY i.created_at DESC LIMIT ? OFFSET ?`
  ).bind(userId, limit, offset).all();

  return json({ inventory: r.results, count: r.results.length, offset, limit });
}

async function inventoryAdd(db, body) {
  const { user_id, card_id, quantity, condition, grade, grade_service,
          acquisition_price, acquisition_date, scan_id, notes } = body;
  if (!user_id || !card_id) return err('user_id and card_id required');

  const id = uuid();
  await db.prepare(
    `INSERT INTO inventory (id, user_id, card_id, quantity, condition, grade, grade_service,
     acquisition_price, acquisition_date, scan_id, notes)
     VALUES (?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(id, user_id, card_id, quantity||1, condition||null, grade||null, grade_service||null,
         acquisition_price||null, acquisition_date||null, scan_id||null, notes||null).run();

  return json({ id }, 201);
}

// ── Scans ────────────────────────────────────────────────────────────
async function scanCreate(db, body) {
  const { user_id, card_id, scanner_id, image_r2_key, acr_result,
          acr_confidence, acr_stage, grade_result } = body;

  const id = uuid();
  await db.prepare(
    `INSERT INTO scans (id, user_id, scanner_id, card_id, image_r2_key,
     acr_result, acr_confidence, acr_stage, grade_result)
     VALUES (?,?,?,?,?,?,?,?,?)`
  ).bind(id, user_id||null, scanner_id||null, card_id||null, image_r2_key||null,
         acr_result||null, acr_confidence||null, acr_stage||null, grade_result||null).run();

  return json({ id, scan_id: id }, 201);
}

async function scanHistory(db, url) {
  const userId = url.searchParams.get('user_id');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  let sql = `SELECT s.*, c.card_name, c.set_name FROM scans s
             LEFT JOIN cards c ON s.card_id = c.id`;
  const p = [];
  if (userId) { sql += ' WHERE s.user_id = ?'; p.push(userId); }
  sql += ' ORDER BY s.created_at DESC LIMIT ?';
  p.push(limit);
  const r = await db.prepare(sql).bind(...p).all();
  return json({ scans: r.results, count: r.results.length });
}

// ── Orders ───────────────────────────────────────────────────────────
async function orderCreate(db, body) {
  const { buyer_id, seller_id, items, shipping_address, notes } = body;
  if (!buyer_id || !seller_id || !items?.length) return err('buyer_id, seller_id, items required');

  const orderId = uuid();
  let subtotal = 0;

  // Calculate subtotal from items
  for (const item of items) {
    subtotal += (item.price || 0) * (item.quantity || 1);
  }

  // Get seller's subscription tier to determine fee rate
  const seller = await db.prepare('SELECT subscription_tier FROM users WHERE id = ?').bind(seller_id).first();
  const tier = seller?.subscription_tier || 'free';
  const fee_rate = FEE_RATES[tier] || DEFAULT_FEE_RATE;

  const platform_fee = subtotal * fee_rate;
  const seller_payout = subtotal - platform_fee;
  const shipping_cost = body.shipping_cost || 0;
  const total = subtotal + shipping_cost;

  await db.prepare(
    `INSERT INTO orders (id, buyer_id, seller_id, status, subtotal, platform_fee, seller_payout,
     shipping_cost, total, shipping_address, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(orderId, buyer_id, seller_id, 'pending', subtotal, platform_fee, seller_payout,
         shipping_cost, total, shipping_address||null, notes||null).run();

  // Track platform revenue
  await db.prepare(
    `INSERT INTO platform_revenue (id, order_id, amount) VALUES (?, ?, ?)`
  ).bind(uuid(), orderId, platform_fee).run();

  // Insert order items
  for (const item of items) {
    const itemId = uuid();
    await db.prepare(
      `INSERT INTO order_items (id, order_id, listing_id, card_name, price, quantity, condition)
       VALUES (?,?,?,?,?,?,?)`
    ).bind(itemId, orderId, item.listing_id, item.card_name||'', item.price,
           item.quantity||1, item.condition||null).run();

    // Mark listing as sold
    await db.prepare("UPDATE listings SET status = 'sold', sold_at = datetime('now') WHERE id = ?")
      .bind(item.listing_id).run();
  }

  return json({
    id: orderId,
    subtotal,
    platform_fee,
    seller_payout,
    shipping_cost,
    total,
    status: 'pending'
  }, 201);
}

async function orderGet(db, id) {
  const order = await db.prepare(
    `SELECT o.*, ub.username as buyer_name, us.username as seller_name
     FROM orders o
     LEFT JOIN users ub ON o.buyer_id = ub.id
     LEFT JOIN users us ON o.seller_id = us.id
     WHERE o.id = ?`
  ).bind(id).first();
  if (!order) return err('Order not found', 404);

  const items = await db.prepare('SELECT * FROM order_items WHERE order_id = ?').bind(id).all();
  return json({ order, items: items.results });
}

async function orderList(db, url) {
  const userId = url.searchParams.get('user_id');
  const role = url.searchParams.get('role') || 'buyer'; // buyer or seller
  if (!userId) return err('user_id required');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);

  const col = role === 'seller' ? 'seller_id' : 'buyer_id';
  const r = await db.prepare(
    `SELECT o.*, ub.username as buyer_name, us.username as seller_name
     FROM orders o
     LEFT JOIN users ub ON o.buyer_id = ub.id
     LEFT JOIN users us ON o.seller_id = us.id
     WHERE o.${col} = ? ORDER BY o.created_at DESC LIMIT ?`
  ).bind(userId, limit).all();

  return json({ orders: r.results, count: r.results.length });
}

async function orderUpdate(db, id, body) {
  const allowed = ['status','tracking_number','shipping_address','notes'];
  const fields = [], p = [];
  for (const [k, v] of Object.entries(body)) {
    if (allowed.includes(k)) { fields.push(`${k} = ?`); p.push(v); }
  }
  if (!fields.length) return err('No valid fields');
  fields.push("updated_at = datetime('now')");
  p.push(id);
  await db.prepare(`UPDATE orders SET ${fields.join(', ')} WHERE id = ?`).bind(...p).run();
  return json({ id, updated: true });
}

// ── Cart ─────────────────────────────────────────────────────────────
async function cartGet(db, userId) {
  const r = await db.prepare(
    `SELECT ci.*, l.price, l.condition, l.grade, c.card_name, c.set_name, c.image_url,
     u.username as seller_name
     FROM cart_items ci
     LEFT JOIN listings l ON ci.listing_id = l.id
     LEFT JOIN cards c ON l.card_id = c.id
     LEFT JOIN users u ON l.seller_id = u.id
     WHERE ci.user_id = ? ORDER BY ci.added_at DESC`
  ).bind(userId).all();
  return json({ cart: r.results, count: r.results.length });
}

async function cartAdd(db, body) {
  const { user_id, listing_id, quantity } = body;
  if (!user_id || !listing_id) return err('user_id and listing_id required');
  const id = uuid();
  await db.prepare(
    'INSERT INTO cart_items (id, user_id, listing_id, quantity) VALUES (?,?,?,?)'
  ).bind(id, user_id, listing_id, quantity||1).run();
  return json({ id }, 201);
}

async function cartRemove(db, itemId) {
  await db.prepare('DELETE FROM cart_items WHERE id = ?').bind(itemId).run();
  return json({ deleted: true });
}

// ── Wallets ──────────────────────────────────────────────────────────
async function walletGet(db, userId) {
  let wallet = await db.prepare('SELECT * FROM wallets WHERE user_id = ?').bind(userId).first();
  if (!wallet) {
    // Auto-create wallet
    await db.prepare('INSERT INTO wallets (user_id) VALUES (?)').bind(userId).run();
    wallet = await db.prepare('SELECT * FROM wallets WHERE user_id = ?').bind(userId).first();
  }
  return json({ wallet });
}

async function walletTransactions(db, url) {
  const userId = url.searchParams.get('user_id');
  if (!userId) return err('user_id required');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  const wallet = await db.prepare('SELECT id FROM wallets WHERE user_id = ?').bind(userId).first();
  if (!wallet) return json({ transactions: [], count: 0 });
  const r = await db.prepare(
    'SELECT * FROM wallet_transactions WHERE wallet_id = ? ORDER BY created_at DESC LIMIT ?'
  ).bind(wallet.id, limit).all();
  return json({ transactions: r.results, count: r.results.length });
}

// ── Reviews ──────────────────────────────────────────────────────────
async function reviewCreate(db, body) {
  const { order_id, buyer_id, seller_id, rating, comment } = body;
  if (!order_id || !buyer_id || !seller_id || !rating) return err('order_id, buyer_id, seller_id, rating required');
  if (rating < 1 || rating > 5) return err('rating must be 1-5');

  const id = uuid();
  await db.prepare(
    'INSERT INTO reviews (id, order_id, buyer_id, seller_id, rating, comment) VALUES (?,?,?,?,?,?)'
  ).bind(id, order_id, buyer_id, seller_id, rating, comment||null).run();

  // Update seller rating
  const avg = await db.prepare(
    'SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM reviews WHERE seller_id = ?'
  ).bind(seller_id).first();
  if (avg) {
    await db.prepare('UPDATE sellers SET rating = ?, total_sales = ? WHERE user_id = ?')
      .bind(avg.avg_rating, avg.count, seller_id).run();
  }

  return json({ id, rating }, 201);
}

async function reviewList(db, url) {
  const sellerId = url.searchParams.get('seller_id');
  if (!sellerId) return err('seller_id required');
  const r = await db.prepare(
    `SELECT r.*, u.username as buyer_name FROM reviews r
     LEFT JOIN users u ON r.buyer_id = u.id
     WHERE r.seller_id = ? ORDER BY r.created_at DESC LIMIT 50`
  ).bind(sellerId).all();
  return json({ reviews: r.results, count: r.results.length });
}

// ── Platform Revenue ─────────────────────────────────────────────────
async function platformRevenue(db, url) {
  const period = url.searchParams.get('period') || 'all'; // all, today, week, month

  let dateFilter = '';
  if (period === 'today') {
    dateFilter = "WHERE DATE(created_at) = DATE('now')";
  } else if (period === 'week') {
    dateFilter = "WHERE created_at >= DATE('now', '-7 days')";
  } else if (period === 'month') {
    dateFilter = "WHERE created_at >= DATE('now', '-30 days')";
  }

  const total = await db.prepare(
    `SELECT SUM(amount) as total, COUNT(*) as count FROM platform_revenue ${dateFilter}`
  ).first();

  const recent = await db.prepare(
    `SELECT pr.*, o.buyer_id, o.seller_id, o.total as order_total
     FROM platform_revenue pr
     LEFT JOIN orders o ON pr.order_id = o.id
     ORDER BY pr.created_at DESC LIMIT 20`
  ).all();

  return json({
    period,
    total_revenue: total.total || 0,
    transaction_count: total.count || 0,
    recent_fees: recent.results
  });
}

// ── Stats ────────────────────────────────────────────────────────────
async function stats(db) {
  const [cards, users, listings, inventory, scans, orders, sellers, revenue] = await Promise.all([
    db.prepare('SELECT COUNT(*) as c FROM cards').first(),
    db.prepare('SELECT COUNT(*) as c FROM users').first(),
    db.prepare("SELECT COUNT(*) as c FROM listings WHERE status = 'active'").first(),
    db.prepare('SELECT COUNT(*) as c FROM inventory').first(),
    db.prepare('SELECT COUNT(*) as c FROM scans').first(),
    db.prepare('SELECT COUNT(*) as c FROM orders').first(),
    db.prepare('SELECT COUNT(*) as c FROM sellers').first(),
    db.prepare('SELECT SUM(amount) as total FROM platform_revenue').first(),
  ]);
  return json({
    stats: {
      cards: cards.c, users: users.c, active_listings: listings.c,
      inventory_items: inventory.c, total_scans: scans.c,
      orders: orders.c, sellers: sellers.c,
      platform_revenue: revenue.total || 0,
    },
    version: 'v1', database: 'nexus-marketplace',
  });
}

// ── AI ───────────────────────────────────────────────────────────────
async function aiClassifyImage(ai, body) {
  const { image } = body; // base64-encoded image
  if (!image) return err('image (base64) required');

  const imageBytes = Uint8Array.from(atob(image), c => c.charCodeAt(0));

  const result = await ai.run('@cf/microsoft/resnet-50', {
    image: [...imageBytes],
  });

  return json({
    classifications: result,
    model: '@cf/microsoft/resnet-50',
  });
}

async function aiDescribeCard(ai, body) {
  const { card_name, set_name, card_type, rarity, year, grade } = body;
  if (!card_name) return err('card_name required');

  const prompt = `Write a brief 2-sentence marketplace listing description for this collectible card:
Card: ${card_name}
Set: ${set_name || 'Unknown'}
Type: ${card_type || 'trading card'}
Rarity: ${rarity || 'Unknown'}
Year: ${year || 'Unknown'}
${grade ? `Grade: ${grade}` : ''}
Keep it professional and factual.`;

  const result = await ai.run('@cf/meta/llama-3.1-8b-instruct', {
    prompt,
    max_tokens: 150,
  });

  return json({
    description: result.response,
    model: '@cf/meta/llama-3.1-8b-instruct',
  });
}

async function aiEmbedText(ai, body) {
  const { text } = body;
  if (!text) return err('text required');

  const result = await ai.run('@cf/baai/bge-base-en-v1.5', {
    text: Array.isArray(text) ? text : [text],
  });

  return json({
    embeddings: result.data,
    model: '@cf/baai/bge-base-en-v1.5',
    dimensions: result.data?.[0]?.length || 0,
  });
}

// ── Vectorize (Similarity Search) ────────────────────────────────────
async function vectorInsert(ai, vectorize, db, body) {
  const { card_id } = body;
  if (!card_id) return err('card_id required');

  const card = await db.prepare('SELECT * FROM cards WHERE id = ?').bind(card_id).first();
  if (!card) return err('Card not found', 404);

  // Build search text from card fields
  const text = [card.card_name, card.set_name, card.card_type, card.rarity, card.year]
    .filter(Boolean).join(' ');

  // Generate embedding
  const embedding = await ai.run('@cf/baai/bge-base-en-v1.5', { text: [text] });
  const values = embedding.data[0];

  // Insert into Vectorize (upsert to handle re-indexing)
  const vectorData = [{
    id: card_id,
    values,
    metadata: {
      card_name: card.card_name,
      set_name: card.set_name || '',
      card_type: card.card_type || '',
      rarity: card.rarity || '',
      year: card.year || 0,
    },
  }];

  try {
    await vectorize.upsert(vectorData);
  } catch (e) {
    return err(`Vectorize error: ${e.message}`, 500);
  }

  return json({ card_id, dimensions: values.length, indexed: true });
}

async function vectorSearch(ai, vectorize, body) {
  const { query, top_k, card_type } = body;
  if (!query) return err('query required');

  // Generate query embedding
  const embedding = await ai.run('@cf/baai/bge-base-en-v1.5', { text: [query] });
  const queryVector = embedding.data[0];

  const options = { topK: top_k || 10, returnMetadata: 'all', returnValues: false };
  if (card_type) {
    options.filter = { card_type };
  }

  const results = await vectorize.query(queryVector, options);

  return json({
    query,
    matches: results.matches.map(m => ({
      card_id: m.id,
      score: m.score,
      ...m.metadata,
    })),
    count: results.count,
  });
}

async function vectorBulkInsert(ai, vectorize, db, body) {
  const { card_type, limit: maxCards } = body;
  const limit = Math.min(maxCards || 100, 500);

  let sql = 'SELECT * FROM cards';
  const p = [];
  if (card_type) { sql += ' WHERE card_type = ?'; p.push(card_type); }
  sql += ' LIMIT ?';
  p.push(limit);

  const cards = await db.prepare(sql).bind(...p).all();
  if (!cards.results.length) return json({ indexed: 0 });

  let indexed = 0;
  // Process in batches of 10
  for (let i = 0; i < cards.results.length; i += 10) {
    const batch = cards.results.slice(i, i + 10);
    const texts = batch.map(c =>
      [c.card_name, c.set_name, c.card_type, c.rarity, c.year].filter(Boolean).join(' ')
    );

    const embeddings = await ai.run('@cf/baai/bge-base-en-v1.5', { text: texts });

    const vectors = batch.map((c, j) => ({
      id: c.id,
      values: embeddings.data[j],
      metadata: {
        card_name: c.card_name,
        set_name: c.set_name || '',
        card_type: c.card_type || '',
        rarity: c.rarity || '',
        year: c.year || 0,
      },
    }));

    await vectorize.upsert(vectors);
    indexed += vectors.length;
  }

  return json({ indexed, total_cards: cards.results.length });
}

// ── Licenses ─────────────────────────────────────────────────────────
async function licenseValidate(db, body) {
  const { license_key, machine_id, machine_name, version } = body;
  if (!license_key) return err('license_key required');

  const license = await db.prepare(
    'SELECT * FROM licenses WHERE license_key = ? AND is_active = 1'
  ).bind(license_key).first();

  if (!license) return err('Invalid or inactive license', 403);
  if (license.expires_at && new Date(license.expires_at) < new Date()) {
    return err('License expired', 403);
  }

  // Check/create client record
  if (machine_id) {
    const existing = await db.prepare(
      'SELECT * FROM clients WHERE license_id = ? AND machine_id = ?'
    ).bind(license.id, machine_id).first();

    if (!existing) {
      const activeClients = await db.prepare(
        'SELECT COUNT(*) as c FROM clients WHERE license_id = ? AND is_active = 1'
      ).bind(license.id).first();

      if (activeClients.c >= license.max_activations) {
        return err('Max activations reached', 403);
      }

      await db.prepare(
        `INSERT INTO clients (license_id, machine_id, machine_name, version, last_seen)
         VALUES (?,?,?,?,datetime('now'))`
      ).bind(license.id, machine_id, machine_name||null, version||null).run();
    } else {
      await db.prepare(
        "UPDATE clients SET last_seen = datetime('now'), version = ? WHERE id = ?"
      ).bind(version||existing.version, existing.id).run();
    }
  }

  return json({
    valid: true,
    tier: license.tier,
    user_id: license.user_id,
    expires_at: license.expires_at,
  });
}

// ── Auth ─────────────────────────────────────────────────────────────
async function hashPassword(password, salt) {
  const enc = new TextEncoder();
  const data = enc.encode(salt + password);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2,'0')).join('');
}

async function authRegister(db, body) {
  const { username, email, password, role, shop_name } = body;
  if (!username || !email || !password) return err('username, email, password required');
  if (password.length < 6) return err('Password must be at least 6 characters');

  const salt = crypto.randomUUID();
  const password_hash = await hashPassword(password, salt);
  const id = uuid();
  const token = uuid(); // Simple bearer token

  try {
    await db.prepare(
      `INSERT INTO users (id, username, email, password_hash, password_salt, role, auth_token)
       VALUES (?,?,?,?,?,?,?)`
    ).bind(id, username, email, password_hash, salt, role || 'buyer', token).run();

    // If seller, create seller profile
    if (role === 'seller' && shop_name) {
      const sellerId = uuid();
      await db.prepare(
        `INSERT INTO sellers (id, user_id, shop_name) VALUES (?,?,?)`
      ).bind(sellerId, id, shop_name).run();
      await db.prepare('UPDATE users SET shop_id = ?, shop_name = ? WHERE id = ?')
        .bind(sellerId, shop_name, id).run();
    }

    return json({
      user: { id, username, email, role, shop_name: shop_name || null },
      token
    }, 201);
  } catch (e) {
    if (e.message?.includes('UNIQUE')) return err('Username or email already exists', 409);
    throw e;
  }
}

async function authLogin(db, body) {
  const { email, password } = body;
  if (!email || !password) return err('email and password required');

  const user = await db.prepare('SELECT * FROM users WHERE email = ?').bind(email).first();
  if (!user) return err('Invalid email or password', 401);

  const hash = await hashPassword(password, user.password_salt || '');
  if (hash !== user.password_hash) return err('Invalid email or password', 401);

  // Refresh token
  const token = uuid();
  await db.prepare('UPDATE users SET auth_token = ? WHERE id = ?').bind(token, user.id).run();

  return json({
    user: {
      id: user.id, username: user.username, email: user.email,
      role: user.role, shop_name: user.shop_name, shop_id: user.shop_id
    },
    token
  });
}

async function authMe(db, request) {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.replace('Bearer ', '').trim();
  if (!token) return err('Authorization required', 401);

  const user = await db.prepare('SELECT * FROM users WHERE auth_token = ?').bind(token).first();
  if (!user) return err('Invalid or expired token', 401);

  return json({
    user: {
      id: user.id, username: user.username, email: user.email,
      role: user.role, shop_name: user.shop_name, shop_id: user.shop_id
    }
  });
}

async function authLogout(db, request) {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.replace('Bearer ', '').trim();
  if (token) {
    await db.prepare('UPDATE users SET auth_token = NULL WHERE auth_token = ?').bind(token).run();
  }
  return json({ success: true });
}

// ── Cart Clear ───────────────────────────────────────────────────────
async function cartClear(db, body) {
  const { user_id } = body;
  if (!user_id) return err('user_id required');
  await db.prepare('DELETE FROM cart_items WHERE user_id = ?').bind(user_id).run();
  return json({ cleared: true });
}

// ── My Listings (seller filtered) ────────────────────────────────────
async function myListings(db, url, request) {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.replace('Bearer ', '').trim();

  let sellerId = url.searchParams.get('seller_id');

  // If no seller_id param, try to get from auth token
  if (!sellerId && token) {
    const user = await db.prepare('SELECT id FROM users WHERE auth_token = ?').bind(token).first();
    if (user) sellerId = user.id;
  }

  if (!sellerId) return err('seller_id required or must be authenticated');

  const status = url.searchParams.get('status');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '100'), 200);

  let sql = `SELECT l.*, c.card_name, c.set_name, c.card_type, c.rarity, c.image_url
             FROM listings l LEFT JOIN cards c ON l.card_id = c.id
             WHERE l.seller_id = ?`;
  const p = [sellerId];
  if (status) { sql += ' AND l.status = ?'; p.push(status); }
  sql += ' ORDER BY l.created_at DESC LIMIT ?';
  p.push(limit);

  const r = await db.prepare(sql).bind(...p).all();
  return json({ listings: r.results, count: r.results.length });
}

// ── Seller Stats ─────────────────────────────────────────────────────
async function sellerStats(db, url, request) {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.replace('Bearer ', '').trim();

  let sellerId = url.searchParams.get('seller_id');
  if (!sellerId && token) {
    const user = await db.prepare('SELECT id FROM users WHERE auth_token = ?').bind(token).first();
    if (user) sellerId = user.id;
  }
  if (!sellerId) return err('seller_id required or must be authenticated');

  const [activeListings, soldListings, totalOrders, totalRevenue] = await Promise.all([
    db.prepare("SELECT COUNT(*) as c FROM listings WHERE seller_id = ? AND status = 'active'").bind(sellerId).first(),
    db.prepare("SELECT COUNT(*) as c FROM listings WHERE seller_id = ? AND status = 'sold'").bind(sellerId).first(),
    db.prepare("SELECT COUNT(*) as c, SUM(seller_payout) as payout FROM orders WHERE seller_id = ?").bind(sellerId).first(),
    db.prepare("SELECT SUM(platform_fee) as fees FROM platform_revenue pr JOIN orders o ON pr.order_id = o.id WHERE o.seller_id = ?").bind(sellerId).first(),
  ]);

  return json({
    seller_id: sellerId,
    active_listings: activeListings.c || 0,
    sold_listings: soldListings.c || 0,
    total_orders: totalOrders.c || 0,
    total_payout: totalOrders.payout || 0,
    total_fees_paid: totalRevenue.fees || 0,
  });
}

// ── Main Router ──────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const db = env.DB;

    try {
      // Health
      if (path === '/' || path === '/health') {
        return json({
          status: 'ok', service: 'nexus-marketplace-api',
          version: 'v1', database: 'nexus-marketplace (D1)',
          tables: 20,
        });
      }

      // Auth
      if (path === '/v1/auth/register' && method === 'POST') return authRegister(db, await request.json());
      if (path === '/v1/auth/login' && method === 'POST') return authLogin(db, await request.json());
      if (path === '/v1/auth/logout' && method === 'POST') return authLogout(db, request);
      if (path === '/v1/auth/me' && method === 'GET') return authMe(db, request);

      // Stats
      if (path === '/v1/stats') return stats(db);

      // Platform Revenue
      if (path === '/v1/revenue' && method === 'GET') return platformRevenue(db, url);

      // Cards
      if (path === '/v1/cards' && method === 'GET') return cardSearch(db, url);
      if (path === '/v1/cards' && method === 'POST') return cardCreate(db, await request.json());
      let params = matchRoute(path, '/v1/cards/:id');
      if (params && method === 'GET') return cardGet(db, params.id);
      if (params && method === 'PUT') return cardUpdate(db, params.id, await request.json());

      // Users
      if (path === '/v1/users' && method === 'POST') return userCreate(db, await request.json());
      params = matchRoute(path, '/v1/users/:id');
      if (params && method === 'GET') return userGet(db, params.id);
      params = matchRoute(path, '/v1/users/username/:username');
      if (params && method === 'GET') return userByUsername(db, params.username);

      // Sellers
      if (path === '/v1/sellers' && method === 'GET') return sellerList(db, url);
      if (path === '/v1/sellers' && method === 'POST') return sellerCreate(db, await request.json());
      params = matchRoute(path, '/v1/sellers/:id');
      if (params && method === 'GET') return sellerGet(db, params.id);

      // Listings
      if (path === '/v1/listings' && method === 'GET') return listingSearch(db, url);
      if (path === '/v1/listings' && method === 'POST') return listingCreate(db, await request.json());
      params = matchRoute(path, '/v1/listings/:id');
      if (params && method === 'GET') return listingGet(db, params.id);
      if (params && method === 'PUT') return listingUpdate(db, params.id, await request.json());

      // Inventory
      if (path === '/v1/inventory' && method === 'GET') return inventoryList(db, url);
      if (path === '/v1/inventory' && method === 'POST') return inventoryAdd(db, await request.json());

      // Scans
      if (path === '/v1/scans' && method === 'POST') return scanCreate(db, await request.json());
      if (path === '/v1/scans' && method === 'GET') return scanHistory(db, url);

      // Orders
      if (path === '/v1/orders' && method === 'POST') return orderCreate(db, await request.json());
      if (path === '/v1/orders' && method === 'GET') return orderList(db, url);
      params = matchRoute(path, '/v1/orders/:id');
      if (params && method === 'GET') return orderGet(db, params.id);
      if (params && method === 'PUT') return orderUpdate(db, params.id, await request.json());

      // Cart
      params = matchRoute(path, '/v1/cart/:user_id');
      if (params && method === 'GET') return cartGet(db, params.user_id);
      if (path === '/v1/cart' && method === 'POST') return cartAdd(db, await request.json());
      if (path === '/v1/cart/clear' && method === 'POST') return cartClear(db, await request.json());
      params = matchRoute(path, '/v1/cart/item/:id');
      if (params && method === 'DELETE') return cartRemove(db, params.id);

      // Seller Dashboard
      if (path === '/v1/seller/stats' && method === 'GET') return sellerStats(db, url, request);
      if (path === '/v1/listings/mine' && method === 'GET') return myListings(db, url, request);

      // Wallets
      params = matchRoute(path, '/v1/wallet/:user_id');
      if (params && method === 'GET') return walletGet(db, params.user_id);
      if (path === '/v1/wallet/transactions' && method === 'GET') return walletTransactions(db, url);

      // Reviews
      if (path === '/v1/reviews' && method === 'POST') return reviewCreate(db, await request.json());
      if (path === '/v1/reviews' && method === 'GET') return reviewList(db, url);

      // AI
      if (path === '/v1/ai/classify' && method === 'POST') return aiClassifyImage(env.AI, await request.json());
      if (path === '/v1/ai/describe' && method === 'POST') return aiDescribeCard(env.AI, await request.json());
      if (path === '/v1/ai/embed' && method === 'POST') return aiEmbedText(env.AI, await request.json());

      // Vectorize (similarity search)
      if (path === '/v1/vector/insert' && method === 'POST') return vectorInsert(env.AI, env.VECTORIZE, db, await request.json());
      if (path === '/v1/vector/search' && method === 'POST') return vectorSearch(env.AI, env.VECTORIZE, await request.json());
      if (path === '/v1/vector/bulk-insert' && method === 'POST') return vectorBulkInsert(env.AI, env.VECTORIZE, db, await request.json());

      // Licenses
      if (path === '/v1/license/validate' && method === 'POST') return licenseValidate(db, await request.json());

      return err('Not found', 404);

    } catch (e) {
      console.error('Marketplace API error:', e);
      return err(`Internal error: ${e.message}`, 500);
    }
  },
};
