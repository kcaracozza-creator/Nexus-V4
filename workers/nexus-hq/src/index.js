/**
 * ╔═══════════════════════════════════════════════════════════════╗
 * ║        NEXUS HQ — THE NARWHAL COUNCIL                        ║
 * ║        Central Command & Client Portal                       ║
 * ║        Patent Pending — Kevin Caracozza                      ║
 * ╚═══════════════════════════════════════════════════════════════╝
 *
 * Unified Cloudflare Worker combining:
 *   - HQ Mothership Dashboard (clients, sales, revenue, subscriptions)
 *   - Client Portal (auth, licensing, wallet, software updates)
 *   - Phone-Home API (clients report sales/scans)
 *   - Admin Auth (password-protected, HTTPS, accessible anywhere)
 */

// ─── Subscription Tiers ──────────────────────────────────────────────────────
const TIERS = {
  starter:      { name: 'Starter',           price: 29,  commission: 8.0 },
  professional: { name: 'Professional',      price: 79,  commission: 6.0 },
  enterprise:   { name: 'Enterprise',        price: 199, commission: 4.0 },
  founders:     { name: "Founder's Edition", price: 0,   commission: 5.0 },
};

const CURRENT_VERSION = '3.0.1';
const SESSION_COOKIE  = 'nhq_session';
const SESSION_TTL_MS  = 8 * 60 * 60 * 1000; // 8 hours

// ─── Helpers ─────────────────────────────────────────────────────────────────
const uuid    = () => crypto.randomUUID();
const shortId = () => uuid().replace(/-/g,'').substring(0,8).toUpperCase();
const apiKey  = () => 'nxs_' + uuid().replace(/-/g,'').substring(0,24);
const now     = () => new Date().toISOString();

function cors(r) {
  r.headers.set('Access-Control-Allow-Origin', '*');
  r.headers.set('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS');
  r.headers.set('Access-Control-Allow-Headers', 'Content-Type,X-API-Key,Authorization,X-License-Key,X-Admin-Key');
  return r;
}

function json(data, status = 200, extra = {}) {
  return cors(new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...extra },
  }));
}

function html(content, status = 200, extra = {}) {
  return new Response(content, {
    status,
    headers: { 'Content-Type': 'text/html;charset=utf-8', ...extra },
  });
}

function redirect(loc) {
  return new Response(null, { status: 302, headers: { Location: loc } });
}

// ─── HMAC session token ───────────────────────────────────────────────────────
async function signToken(secret, payload) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret),
    { name:'HMAC', hash:'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(payload));
  return payload + '.' + btoa(String.fromCharCode(...new Uint8Array(sig)));
}

async function verifyToken(secret, token) {
  try {
    const dot = token.lastIndexOf('.');
    const payload = token.substring(0, dot);
    const expected = await signToken(secret, payload);
    if (expected !== token) return null;
    const [ts] = payload.split('|');
    if (Date.now() - parseInt(ts) > SESSION_TTL_MS) return null;
    return payload;
  } catch { return null; }
}

async function isAuthenticated(request, env) {
  const cookie = request.headers.get('Cookie') || '';
  const match  = cookie.match(new RegExp(SESSION_COOKIE + '=([^;]+)'));
  if (!match) return false;
  const secret = env.SESSION_SECRET || 'nexus-narwhal-secret';
  return !!(await verifyToken(secret, decodeURIComponent(match[1])));
}

// ─── DB init ─────────────────────────────────────────────────────────────────
async function initDb(db) {
  await db.batch([
    // HQ tables
    db.prepare(`CREATE TABLE IF NOT EXISTS hq_clients (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE, api_key TEXT UNIQUE,
      subscription_tier TEXT DEFAULT 'starter', commission_rate REAL DEFAULT 8.0,
      monthly_fee REAL DEFAULT 29.0, status TEXT DEFAULT 'active',
      created_at TEXT, last_seen TEXT, location TEXT, contact_phone TEXT, notes TEXT,
      billing_email TEXT, stripe_customer_id TEXT, subscription_start TEXT,
      next_billing_date TEXT, billing_status TEXT DEFAULT 'active')`),
    db.prepare(`CREATE TABLE IF NOT EXISTS hq_sales (
      id TEXT PRIMARY KEY, client_id TEXT, deck_name TEXT, format TEXT,
      card_count INTEGER, sale_value REAL, nexus_fee REAL, client_keeps REAL,
      sold_at TEXT, cards_json TEXT, FOREIGN KEY (client_id) REFERENCES hq_clients(id))`),
    db.prepare(`CREATE TABLE IF NOT EXISTS hq_scans (
      id INTEGER PRIMARY KEY AUTOINCREMENT, client_id TEXT, card_name TEXT,
      set_code TEXT, rarity TEXT, price REAL, scanned_at TEXT, ai_confidence REAL,
      FOREIGN KEY (client_id) REFERENCES hq_clients(id))`),
    db.prepare(`CREATE TABLE IF NOT EXISTS hq_disputes (
      id TEXT PRIMARY KEY, client_id TEXT, card_name TEXT, ai_grade TEXT,
      disputed_grade TEXT, resolution TEXT, status TEXT DEFAULT 'pending',
      created_at TEXT, resolved_at TEXT, FOREIGN KEY (client_id) REFERENCES hq_clients(id))`),
    db.prepare(`CREATE TABLE IF NOT EXISTS hq_invoices (
      id TEXT PRIMARY KEY, client_id TEXT, tier TEXT, amount REAL,
      period_start TEXT, period_end TEXT, status TEXT DEFAULT 'pending',
      paid_at TEXT, payment_method TEXT, stripe_invoice_id TEXT, created_at TEXT,
      FOREIGN KEY (client_id) REFERENCES hq_clients(id))`),
    // Portal tables
    db.prepare(`CREATE TABLE IF NOT EXISTS portal_users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, shop_name TEXT, station_api_key TEXT UNIQUE,
      created_at TEXT, is_admin INTEGER DEFAULT 0,
      subscription_tier TEXT DEFAULT 'free', subscription_expires TEXT)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS portal_licenses (
      id INTEGER PRIMARY KEY AUTOINCREMENT, license_key TEXT UNIQUE NOT NULL,
      user_id INTEGER NOT NULL, created_at TEXT, expires_at TEXT,
      is_active INTEGER DEFAULT 1, max_activations INTEGER DEFAULT 3,
      FOREIGN KEY (user_id) REFERENCES portal_users(id))`),
    db.prepare(`CREATE TABLE IF NOT EXISTS portal_activations (
      id INTEGER PRIMARY KEY AUTOINCREMENT, license_id INTEGER NOT NULL,
      machine_id TEXT NOT NULL, machine_name TEXT, ip_address TEXT, version TEXT,
      last_seen TEXT, first_seen TEXT,
      FOREIGN KEY (license_id) REFERENCES portal_licenses(id),
      UNIQUE(license_id, machine_id))`),
    db.prepare(`CREATE TABLE IF NOT EXISTS portal_versions (
      id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT UNIQUE NOT NULL,
      release_date TEXT, changelog TEXT, download_url TEXT,
      is_mandatory INTEGER DEFAULT 0, min_version TEXT)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS portal_wallets (
      id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL,
      balance REAL DEFAULT 0.0, pending_balance REAL DEFAULT 0.0,
      total_earned REAL DEFAULT 0.0, total_withdrawn REAL DEFAULT 0.0,
      payout_email TEXT, payout_method TEXT DEFAULT 'paypal',
      created_at TEXT, updated_at TEXT,
      FOREIGN KEY (user_id) REFERENCES portal_users(id))`),
    db.prepare(`CREATE TABLE IF NOT EXISTS portal_wallet_tx (
      id INTEGER PRIMARY KEY AUTOINCREMENT, wallet_id INTEGER NOT NULL,
      type TEXT NOT NULL, amount REAL NOT NULL, description TEXT,
      order_id TEXT, status TEXT DEFAULT 'completed', created_at TEXT,
      FOREIGN KEY (wallet_id) REFERENCES portal_wallets(id))`),
  ]);
}

// ─── HQ data helpers ──────────────────────────────────────────────────────────
async function hqStats(db) {
  const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString();
  const todayStart = new Date().toISOString().split('T')[0];
  const [cl, all, mo, td, sc, di, mrr] = await db.batch([
    db.prepare(`SELECT COUNT(*) c FROM hq_clients WHERE status='active'`),
    db.prepare(`SELECT COUNT(*) c, COALESCE(SUM(sale_value),0) v, COALESCE(SUM(nexus_fee),0) r FROM hq_sales`),
    db.prepare(`SELECT COUNT(*) c, COALESCE(SUM(sale_value),0) v, COALESCE(SUM(nexus_fee),0) r FROM hq_sales WHERE sold_at >= ?`).bind(monthStart),
    db.prepare(`SELECT COUNT(*) c, COALESCE(SUM(sale_value),0) v, COALESCE(SUM(nexus_fee),0) r FROM hq_sales WHERE sold_at >= ?`).bind(todayStart),
    db.prepare(`SELECT COUNT(*) c FROM hq_scans`),
    db.prepare(`SELECT COUNT(*) c FROM hq_disputes WHERE status='pending'`),
    db.prepare(`SELECT COALESCE(SUM(monthly_fee),0) m FROM hq_clients WHERE status='active'`),
  ]);
  const f = (n) => +parseFloat(n||0).toFixed(2);
  return {
    clients: { total: cl.results[0].c, active: cl.results[0].c },
    sales:   { total: all.results[0].c, today: td.results[0].c, this_month: mo.results[0].c },
    volume:  { total: f(all.results[0].v), today: f(td.results[0].v), this_month: f(mo.results[0].v) },
    revenue: { total_fees: f(all.results[0].r), today_fees: f(td.results[0].r), month_fees: f(mo.results[0].r), mrr: f(mrr.results[0].m) },
    network: { total_scans: sc.results[0].c, pending_disputes: di.results[0].c },
  };
}

async function hqLeaderboard(db) {
  const { results } = await db.prepare(`
    SELECT c.id, c.name, c.subscription_tier, c.commission_rate, c.location, c.last_seen,
           COUNT(s.id) sale_count,
           COALESCE(SUM(s.sale_value),0) total_volume,
           COALESCE(SUM(s.nexus_fee),0) total_fees
    FROM hq_clients c
    LEFT JOIN hq_sales s ON c.id = s.client_id
    WHERE c.status='active'
    GROUP BY c.id ORDER BY total_volume DESC`).all();
  return results;
}

async function hqRecentSales(db, limit=50) {
  const { results } = await db.prepare(`
    SELECT s.*, c.name client_name FROM hq_sales s
    JOIN hq_clients c ON s.client_id = c.id
    ORDER BY s.sold_at DESC LIMIT ?`).bind(limit).all();
  return results;
}

async function hqClientByApiKey(db, key) {
  const row = await db.prepare(`SELECT * FROM hq_clients WHERE api_key=? AND status='active'`).bind(key).first();
  if (row) await db.prepare(`UPDATE hq_clients SET last_seen=? WHERE id=?`).bind(now(), row.id).run();
  return row;
}

// ─── Portal helpers ───────────────────────────────────────────────────────────
async function hashPassword(password, secret) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret),
    { name:'HMAC', hash:'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(password));
  return Array.from(new Uint8Array(sig)).map(b=>b.toString(16).padStart(2,'0')).join('');
}

// ─── Main handler ─────────────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const db     = env.DB;
    const url    = new URL(request.url);
    const path   = url.pathname;
    const method = request.method;
    const secret = env.SESSION_SECRET || 'nexus-narwhal-secret';
    const admPwd = env.ADMIN_PASSWORD  || 'nexus-admin';

    if (method === 'OPTIONS') {
      return new Response(null, { headers: {
        'Access-Control-Allow-Origin':'*',
        'Access-Control-Allow-Methods':'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Headers':'Content-Type,X-API-Key,Authorization,X-License-Key',
      }});
    }

    try {
      await initDb(db);

      // ── Login page ────────────────────────────────────────────────────────
      if (path === '/login') {
        if (method === 'GET') return html(LOGIN_HTML);
        if (method === 'POST') {
          const body = await request.text();
          const params = new URLSearchParams(body);
          if (params.get('password') === admPwd) {
            const payload = `${Date.now()}|admin`;
            const token   = await signToken(secret, payload);
            const cookie  = `${SESSION_COOKIE}=${encodeURIComponent(token)}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=28800`;
            return new Response(null, { status: 302, headers: { Location: '/', 'Set-Cookie': cookie }});
          }
          return html(LOGIN_HTML.replace('<!--ERR-->', '<div class="err">Incorrect password.</div>'));
        }
      }

      if (path === '/logout') {
        return new Response(null, { status: 302, headers: {
          Location: '/login',
          'Set-Cookie': `${SESSION_COOKIE}=; HttpOnly; Secure; Path=/; Max-Age=0`,
        }});
      }

      // ── Phone-Home API (no dashboard auth — uses client API key) ─────────
      if (path.startsWith('/api/phone-home/') || path.startsWith('/api/auth/') || path === '/health' || path === '/api/updates/check') {
        return await handlePublicApi(path, method, request, db, env, secret, admPwd);
      }

      // ── All other routes require admin session ────────────────────────────
      if (!(await isAuthenticated(request, env))) {
        if (path.startsWith('/api/')) return json({ error: 'Unauthorized' }, 401);
        return redirect('/login');
      }

      // ── Admin API ─────────────────────────────────────────────────────────
      if (path.startsWith('/api/')) {
        return await handleAdminApi(path, method, request, db, url, env, admPwd);
      }

      // ── Dashboard HTML ────────────────────────────────────────────────────
      if (path === '/' || path === '/dashboard') return html(DASHBOARD_HTML);
      if (path === '/portal') return html(PORTAL_HTML);

      return json({ error: 'Not found' }, 404);

    } catch (err) {
      console.error(err);
      return json({ error: 'Internal error', detail: err.message }, 500);
    }
  },
};

// ─── Public API (no session required) ────────────────────────────────────────
async function handlePublicApi(path, method, request, db, env, secret, admPwd) {
  const appSecret = env.SESSION_SECRET || 'nexus-narwhal-secret';

  if (path === '/health') {
    return json({ status: 'healthy', service: 'NEXUS HQ — The Narwhal Council', version: '2.0.0', timestamp: now() });
  }

  // Phone home: sale
  if (path === '/api/phone-home/sale' && method === 'POST') {
    const key = request.headers.get('X-API-Key') || (request.headers.get('Authorization')||'').replace('Bearer ','');
    if (!key) return json({ error: 'Missing API key' }, 401);
    const client = await hqClientByApiKey(db, key);
    if (!client) return json({ error: 'Invalid API key' }, 401);
    const data = await request.json();
    const val  = parseFloat(data.sale_value || 0);
    const fee  = +(val * client.commission_rate / 100).toFixed(2);
    const keeps= +(val - fee).toFixed(2);
    const sid  = 'SALE-' + shortId();
    await db.prepare(`INSERT INTO hq_sales (id,client_id,deck_name,format,card_count,sale_value,nexus_fee,client_keeps,sold_at,cards_json) VALUES (?,?,?,?,?,?,?,?,?,?)`)
      .bind(sid, client.id, data.deck_name||'Unknown', data.format||'Unknown', data.card_count||0, val, fee, keeps, now(), JSON.stringify(data.cards||[])).run();
    return json({ success:true, message:`Sale recorded! NEXUS fee: $${fee.toFixed(2)}`, sale_id:sid, sale_value:val, nexus_fee:fee, client_keeps:keeps });
  }

  // Phone home: scan
  if (path === '/api/phone-home/scan' && method === 'POST') {
    const key = request.headers.get('X-API-Key') || (request.headers.get('Authorization')||'').replace('Bearer ','');
    if (!key) return json({ error: 'Missing API key' }, 401);
    const client = await hqClientByApiKey(db, key);
    if (!client) return json({ error: 'Invalid API key' }, 401);
    const data = await request.json();
    await db.prepare(`INSERT INTO hq_scans (client_id,card_name,set_code,rarity,price,scanned_at,ai_confidence) VALUES (?,?,?,?,?,?,?)`)
      .bind(client.id, data.card_name||'', data.set_code||'', data.rarity||'', parseFloat(data.price||0), now(), parseFloat(data.confidence||0)).run();
    return json({ success: true, message: 'Scan recorded' });
  }

  // Phone home: batch scans
  if (path === '/api/phone-home/batch-scans' && method === 'POST') {
    const key = request.headers.get('X-API-Key') || (request.headers.get('Authorization')||'').replace('Bearer ','');
    if (!key) return json({ error: 'Missing API key' }, 401);
    const client = await hqClientByApiKey(db, key);
    if (!client) return json({ error: 'Invalid API key' }, 401);
    const data  = await request.json();
    const scans = data.scans || [];
    if (scans.length) {
      await db.batch(scans.map(s => db.prepare(`INSERT INTO hq_scans (client_id,card_name,set_code,rarity,price,scanned_at,ai_confidence) VALUES (?,?,?,?,?,?,?)`)
        .bind(client.id, s.card_name||'', s.set_code||'', s.rarity||'', parseFloat(s.price||0), now(), parseFloat(s.confidence||0))));
    }
    return json({ success: true, recorded: scans.length });
  }

  // Portal auth: register
  if (path === '/api/auth/register' && method === 'POST') {
    const data = await request.json();
    if (!data.email || !data.password) return json({ error: 'email and password required' }, 400);
    const hash = await hashPassword(data.password, appSecret);
    const stationKey = `nxs_${uuid().replace(/-/g,'')}`;
    const licenseKey = `NEXUS-${shortId()}-${shortId()}`;
    try {
      const result = await db.prepare(`INSERT INTO portal_users (email,password_hash,shop_name,station_api_key,created_at) VALUES (?,?,?,?,?)`)
        .bind(data.email, hash, data.shop_name||'', stationKey, now()).run();
      const userId = result.meta.last_row_id;
      await db.prepare(`INSERT INTO portal_licenses (license_key,user_id,created_at,is_active) VALUES (?,?,?,1)`)
        .bind(licenseKey, userId, now()).run();
      await db.prepare(`INSERT INTO portal_wallets (user_id,created_at,updated_at) VALUES (?,?,?)`).bind(userId, now(), now()).run();
      return json({ success:true, license_key:licenseKey, station_api_key:stationKey, message:'Registration successful' }, 201);
    } catch (e) {
      return json({ success:false, error:'Email already registered' }, 400);
    }
  }

  // Portal auth: login
  if (path === '/api/auth/login' && method === 'POST') {
    const data = await request.json();
    const hash = await hashPassword(data.password||'', appSecret);
    const user = await db.prepare(`SELECT * FROM portal_users WHERE email=? AND password_hash=?`).bind(data.email||'', hash).first();
    if (!user) return json({ error: 'Invalid credentials' }, 401);
    const payload = `${Date.now()}|${user.id}`;
    const token   = await signToken(appSecret, payload);
    return json({ success:true, token, user:{ id:user.id, email:user.email, shop_name:user.shop_name, subscription_tier:user.subscription_tier }});
  }

  // Portal auth: validate license
  if (path === '/api/auth/validate' && method === 'POST') {
    const data = await request.json();
    const licKey = data.license_key || request.headers.get('X-License-Key');
    if (!licKey) return json({ valid:false, error:'No license key' }, 401);
    const lic = await db.prepare(`SELECT l.*, u.email, u.shop_name FROM portal_licenses l JOIN portal_users u ON l.user_id=u.id WHERE l.license_key=? AND l.is_active=1`).bind(licKey).first();
    if (!lic) return json({ valid:false, error:'Invalid license' }, 401);
    if (lic.expires_at && new Date(lic.expires_at) < new Date()) return json({ valid:false, error:'License expired' }, 401);
    // Register activation
    const machineId = data.machine_id || (await hashPassword(request.headers.get('CF-Connecting-IP')||'unknown', 'machine')).substring(0,16);
    await db.prepare(`INSERT INTO portal_activations (license_id,machine_id,machine_name,ip_address,version,last_seen,first_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(license_id,machine_id) DO UPDATE SET last_seen=excluded.last_seen, version=excluded.version`)
      .bind(lic.id, machineId, data.machine_name||'', request.headers.get('CF-Connecting-IP')||'', data.version||CURRENT_VERSION, now(), now()).run();
    return json({ valid:true, license_key:licKey, shop_name:lic.shop_name, email:lic.email, version:CURRENT_VERSION });
  }

  // Software update check
  if (path === '/api/updates/check' && method === 'GET') {
    const clientVer = url.searchParams.get('version') || '0.0.0';
    const latest = await db.prepare(`SELECT * FROM portal_versions ORDER BY release_date DESC LIMIT 1`).first();
    const hasUpdate = latest && latest.version !== clientVer;
    return json({ current_version:CURRENT_VERSION, latest_version:latest?.version||CURRENT_VERSION, has_update:hasUpdate, mandatory:latest?.is_mandatory||false, changelog:latest?.changelog||'', download_url:latest?.download_url||'' });
  }

  return json({ error: 'Not found' }, 404);
}

// ─── Admin API (session required) ────────────────────────────────────────────
async function handleAdminApi(path, method, request, db, url, env, admPwd) {
  const f2 = (n) => +parseFloat(n||0).toFixed(2);

  // Status
  if (path === '/api/status') {
    const stats = await hqStats(db);
    return json({ status:'online', clients:stats.clients.total, total_volume:stats.volume.total, total_revenue:stats.revenue.total_fees, mrr:stats.revenue.mrr });
  }

  // Dashboard
  if (path === '/api/dashboard') {
    const [stats, lb, rs] = await Promise.all([hqStats(db), hqLeaderboard(db), hqRecentSales(db, 20)]);
    return json({ stats, leaderboard:lb, recent_sales:rs });
  }
  if (path === '/api/dashboard/stats')       return json(await hqStats(db));
  if (path === '/api/dashboard/leaderboard') return json(await hqLeaderboard(db));
  if (path === '/api/dashboard/sales')       return json(await hqRecentSales(db, parseInt(url.searchParams.get('limit')||'50')));

  // Clients
  if (path === '/api/clients' && method === 'GET') {
    const { results } = await db.prepare(`SELECT id,name,email,subscription_tier,commission_rate,monthly_fee,status,created_at,last_seen,location,contact_phone,notes FROM hq_clients ORDER BY created_at DESC`).all();
    return json({ clients:results, count:results.length });
  }
  if (path === '/api/clients/register' && method === 'POST') {
    const data = await request.json();
    if (!data.name || !data.email) return json({ error:'Missing name or email' }, 400);
    const tier = data.tier || 'starter';
    const t    = TIERS[tier] || TIERS.starter;
    const id   = shortId();
    const key  = apiKey();
    try {
      await db.prepare(`INSERT INTO hq_clients (id,name,email,api_key,subscription_tier,commission_rate,monthly_fee,created_at,last_seen,location,contact_phone,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`)
        .bind(id, data.name, data.email, key, tier, t.commission, t.price, now(), now(), data.location||'', data.phone||'', data.notes||'').run();
      return json({ success:true, client_id:id, api_key:key, tier, commission:t.commission, monthly_fee:t.price }, 201);
    } catch(e) { return json({ success:false, error:e.message }, 400); }
  }
  const cmatch = path.match(/^\/api\/clients\/([^/]+)$/);
  if (cmatch && method === 'GET') {
    const row = await db.prepare(`SELECT * FROM hq_clients WHERE id=?`).bind(cmatch[1]).first();
    if (!row) return json({ error:'Not found' }, 404);
    delete row.api_key;
    return json(row);
  }

  // Subscriptions
  if (path === '/api/subscriptions/tiers')   return json(TIERS);
  if (path === '/api/subscriptions/revenue') {
    const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString();
    const [mrr,mc,tc,pend,tiers] = await db.batch([
      db.prepare(`SELECT COALESCE(SUM(monthly_fee),0) m FROM hq_clients WHERE status='active'`),
      db.prepare(`SELECT COALESCE(SUM(amount),0) c FROM hq_invoices WHERE status='paid' AND paid_at>=?`).bind(monthStart),
      db.prepare(`SELECT COALESCE(SUM(amount),0) c FROM hq_invoices WHERE status='paid'`),
      db.prepare(`SELECT COUNT(*) c, COALESCE(SUM(amount),0) a FROM hq_invoices WHERE status='pending'`),
      db.prepare(`SELECT subscription_tier, COUNT(*) c, SUM(monthly_fee) r FROM hq_clients WHERE status='active' GROUP BY subscription_tier`),
    ]);
    return json({ mrr:f2(mrr.results[0].m), month_collected:f2(mc.results[0].c), total_collected:f2(tc.results[0].c), pending_invoices:pend.results[0].c, pending_amount:f2(pend.results[0].a), tier_breakdown:tiers.results });
  }
  if (path === '/api/subscriptions/invoices' && method === 'GET') {
    const { results } = await db.prepare(`SELECT i.*, c.name client_name, c.email FROM hq_invoices i JOIN hq_clients c ON i.client_id=c.id WHERE i.status='pending' ORDER BY i.created_at`).all();
    return json({ invoices:results });
  }
  if (path === '/api/subscriptions/invoices/create' && method === 'POST') {
    const data = await request.json();
    if (!data.client_id) return json({ error:'Missing client_id' }, 400);
    const client = await db.prepare(`SELECT subscription_tier FROM hq_clients WHERE id=?`).bind(data.client_id).first();
    if (!client) return json({ error:'Client not found' }, 404);
    const tier = data.tier || client.subscription_tier;
    const amount = (TIERS[tier]||TIERS.starter).price;
    const iid = 'INV-' + shortId();
    const pEnd = new Date(Date.now() + 30*86400000).toISOString();
    await db.prepare(`INSERT INTO hq_invoices (id,client_id,tier,amount,period_start,period_end,status,created_at) VALUES (?,?,?,?,?,?,'pending',?)`)
      .bind(iid, data.client_id, tier, amount, now(), pEnd, now()).run();
    await db.prepare(`UPDATE hq_clients SET next_billing_date=? WHERE id=?`).bind(pEnd, data.client_id).run();
    return json({ success:true, invoice:{ invoice_id:iid, client_id:data.client_id, tier, amount, period_end:pEnd, status:'pending' }}, 201);
  }
  const payM = path.match(/^\/api\/subscriptions\/invoices\/([^/]+)\/pay$/);
  if (payM && method === 'POST') {
    const data = await request.json().catch(()=>({}));
    await db.prepare(`UPDATE hq_invoices SET status='paid',paid_at=?,payment_method=? WHERE id=?`).bind(now(), data.payment_method||'manual', payM[1]).run();
    return json({ success:true });
  }
  const tierM = path.match(/^\/api\/subscriptions\/client\/([^/]+)\/tier$/);
  if (tierM && method === 'PUT') {
    const data = await request.json();
    const t = TIERS[data.tier];
    if (!t) return json({ error:'Invalid tier' }, 400);
    await db.prepare(`UPDATE hq_clients SET subscription_tier=?,commission_rate=?,monthly_fee=? WHERE id=?`).bind(data.tier, t.commission, t.price, tierM[1]).run();
    return json({ success:true, new_tier:data.tier, commission_rate:t.commission, monthly_fee:t.price });
  }
  if (path === '/api/subscriptions/generate-invoices' && method === 'POST') {
    const { results } = await db.prepare(`SELECT id,subscription_tier FROM hq_clients WHERE status='active' AND monthly_fee>0 AND (next_billing_date IS NULL OR next_billing_date<=?)`).bind(now()).all();
    const created = [];
    for (const row of results) {
      const t = TIERS[row.subscription_tier]||TIERS.starter;
      const iid = 'INV-' + shortId();
      const pEnd = new Date(Date.now()+30*86400000).toISOString();
      await db.prepare(`INSERT INTO hq_invoices (id,client_id,tier,amount,period_start,period_end,status,created_at) VALUES (?,?,?,?,?,?,'pending',?)`)
        .bind(iid, row.id, row.subscription_tier, t.price, now(), pEnd, now()).run();
      await db.prepare(`UPDATE hq_clients SET next_billing_date=? WHERE id=?`).bind(pEnd, row.id).run();
      created.push({ invoice_id:iid, client_id:row.id, amount:t.price });
    }
    return json({ success:true, invoices_created:created.length, invoices:created });
  }

  // Portal admin
  if (path === '/api/portal/users' && method === 'GET') {
    const { results } = await db.prepare(`SELECT id,email,shop_name,subscription_tier,created_at,subscription_expires FROM portal_users ORDER BY created_at DESC`).all();
    return json({ users:results, count:results.length });
  }
  if (path === '/api/portal/versions' && method === 'POST') {
    const data = await request.json();
    await db.prepare(`INSERT INTO portal_versions (version,release_date,changelog,download_url,is_mandatory,min_version) VALUES (?,?,?,?,?,?) ON CONFLICT(version) DO UPDATE SET changelog=excluded.changelog,download_url=excluded.download_url,is_mandatory=excluded.is_mandatory`)
      .bind(data.version, now(), data.changelog||'', data.download_url||'', data.mandatory?1:0, data.min_version||'').run();
    return json({ success:true });
  }
  if (path === '/api/portal/wallet/credit' && method === 'POST') {
    const data = await request.json();
    const wallet = await db.prepare(`SELECT id FROM portal_wallets WHERE user_id=?`).bind(data.user_id).first();
    if (!wallet) return json({ error:'Wallet not found' }, 404);
    await db.prepare(`UPDATE portal_wallets SET balance=balance+?,total_earned=total_earned+?,updated_at=? WHERE id=?`).bind(parseFloat(data.amount||0), parseFloat(data.amount||0), now(), wallet.id).run();
    await db.prepare(`INSERT INTO portal_wallet_tx (wallet_id,type,amount,description,order_id,created_at) VALUES (?,?,?,?,?,?)`).bind(wallet.id, 'credit', parseFloat(data.amount||0), data.description||'Manual credit', data.order_id||null, now()).run();
    return json({ success:true });
  }

  return json({ error: 'Not found' }, 404);
}

// ─── HTML Templates ───────────────────────────────────────────────────────────
const LOGIN_HTML = `<!DOCTYPE html>
<html>
<head>
  <title>NEXUS HQ — Login</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:'Segoe UI',sans-serif;background:#0a0a0a;display:flex;align-items:center;justify-content:center;min-height:100vh}
    .box{background:#1a1a2e;border:1px solid #d4af37;border-radius:12px;padding:40px;width:360px;text-align:center}
    h1{color:#d4af37;font-size:22px;margin-bottom:6px}
    .sub{color:#666;font-size:13px;margin-bottom:28px}
    input{width:100%;background:#0d0d1a;border:1px solid #333;color:#e0e0e0;padding:12px 14px;border-radius:8px;font-size:15px;margin-bottom:14px;outline:none}
    input:focus{border-color:#d4af37}
    button{width:100%;background:#d4af37;color:#000;border:none;padding:13px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer}
    button:hover{background:#c9a227}
    .err{color:#f87171;font-size:13px;margin-top:14px}
    .live{display:inline-block;width:8px;height:8px;background:#4CAF50;border-radius:50%;margin-right:8px;animation:p 2s infinite}
    @keyframes p{0%,100%{opacity:1}50%{opacity:.5}}
  </style>
</head>
<body>
  <div class="box">
    <h1><span class="live"></span>NEXUS HQ</h1>
    <div class="sub">The Narwhal Council — Command Center</div>
    <form method="POST" action="/login">
      <input type="password" name="password" placeholder="Admin password" autofocus required>
      <button type="submit">Enter</button>
    </form>
    <!--ERR-->
  </div>
</body>
</html>`;

const NAV = `
<nav style="background:#0d0d1a;border-bottom:1px solid #d4af37;padding:12px 40px;display:flex;align-items:center;gap:20px">
  <span style="color:#d4af37;font-weight:700;font-size:16px">⚓ NEXUS HQ</span>
  <a href="/" style="color:#888;text-decoration:none;font-size:13px">HQ Dashboard</a>
  <a href="/portal" style="color:#888;text-decoration:none;font-size:13px">Client Portal</a>
  <a href="/logout" style="color:#888;text-decoration:none;font-size:13px;margin-left:auto">Logout</a>
</nav>`;

const DASHBOARD_HTML = `<!DOCTYPE html>
<html>
<head>
  <title>NEXUS HQ — The Narwhal Council</title>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:'Segoe UI',sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh}
    .header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px 40px;border-bottom:2px solid #d4af37}
    .header h1{color:#d4af37;font-size:26px;display:flex;align-items:center;gap:12px}
    .header h1 small{font-size:13px;color:#888}
    .container{padding:28px 40px;max-width:1600px;margin:0 auto}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:18px;margin-bottom:28px}
    .card{background:#1a1a2e;border:1px solid #333;border-radius:10px;padding:18px;text-align:center}
    .card.gold{border-color:#d4af37}
    .card h3{color:#888;font-size:11px;text-transform:uppercase;margin-bottom:8px}
    .card .val{font-size:30px;font-weight:700;color:#fff}
    .card.gold .val{color:#d4af37}
    .card .sub{font-size:11px;color:#666;margin-top:4px}
    .section{margin-bottom:28px}
    .section h2{color:#d4af37;font-size:17px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #333;display:flex;align-items:center;gap:10px}
    table{width:100%;border-collapse:collapse}
    th,td{padding:11px 14px;text-align:left;border-bottom:1px solid #1a1a2e}
    th{background:#141428;color:#d4af37;font-size:11px;text-transform:uppercase}
    tr:hover td{background:#141428}
    .money{color:#4CAF50}.fee{color:#d4af37}
    .tier{padding:3px 7px;border-radius:4px;font-size:10px;text-transform:uppercase}
    .tier.starter{background:#333;color:#888}
    .tier.professional{background:#1a365d;color:#63b3ed}
    .tier.enterprise{background:#553c9a;color:#b794f4}
    .tier.founders{background:#744210;color:#d4af37}
    .btn{background:#d4af37;color:#000;border:none;padding:8px 16px;border-radius:5px;cursor:pointer;font-weight:700;font-size:12px}
    .btn:hover{background:#c9a227}
    .live{display:inline-block;width:8px;height:8px;background:#4CAF50;border-radius:50%;animation:p 2s infinite}
    @keyframes p{0%,100%{opacity:1}50%{opacity:.5}}
  </style>
</head>
<body>
${NAV}
<div class="header">
  <h1><span class="live"></span>NEXUS HQ — The Narwhal Council <small>Mothership Command</small></h1>
</div>
<div class="container">
  <div class="grid">
    <div class="card gold"><h3>MRR</h3><div class="val" id="mrr">$0</div><div class="sub">Subscription revenue</div></div>
    <div class="card gold"><h3>Commission Fees</h3><div class="val" id="fees">$0</div><div class="sub">This month</div></div>
    <div class="card"><h3>Active Clients</h3><div class="val" id="clients">0</div><div class="sub">Deployed shops</div></div>
    <div class="card"><h3>Sales Volume</h3><div class="val" id="volume">$0</div><div class="sub">This month</div></div>
    <div class="card"><h3>Total Sales</h3><div class="val" id="sales">0</div><div class="sub">This month</div></div>
    <div class="card"><h3>Cards Scanned</h3><div class="val" id="scans">0</div><div class="sub">Network-wide</div></div>
  </div>
  <div class="section">
    <h2>Client Leaderboard</h2>
    <table><thead><tr><th>Client</th><th>Location</th><th>Tier</th><th>Sales</th><th>Volume</th><th>NEXUS Fees</th><th>Last Seen</th></tr></thead>
    <tbody id="lb"></tbody></table>
  </div>
  <div class="section">
    <h2>Recent Sales <button class="btn" onclick="load()" style="margin-left:10px">Refresh</button></h2>
    <table><thead><tr><th>Time</th><th>Client</th><th>Deck</th><th>Format</th><th>Cards</th><th>Sale Value</th><th>NEXUS Fee</th></tr></thead>
    <tbody id="rs"></tbody></table>
  </div>
</div>
<script>
async function load(){
  const d = await fetch('/api/dashboard').then(r=>r.json());
  const f = n => '$'+parseFloat(n||0).toFixed(2);
  document.getElementById('mrr').textContent = f(d.stats.revenue.mrr);
  document.getElementById('fees').textContent = f(d.stats.revenue.month_fees);
  document.getElementById('clients').textContent = d.stats.clients.total;
  document.getElementById('volume').textContent = f(d.stats.volume.this_month);
  document.getElementById('sales').textContent = d.stats.sales.this_month;
  document.getElementById('scans').textContent = (d.stats.network.total_scans||0).toLocaleString();
  document.getElementById('lb').innerHTML = d.leaderboard.map(c=>
    \`<tr><td><b>\${c.name}</b></td><td>\${c.location||'-'}</td><td><span class="tier \${c.subscription_tier}">\${c.subscription_tier}</span></td><td>\${c.sale_count}</td><td class="money">\${f(c.total_volume)}</td><td class="fee">\${f(c.total_fees)}</td><td>\${c.last_seen?new Date(c.last_seen).toLocaleDateString():'-'}</td></tr>\`
  ).join('');
  document.getElementById('rs').innerHTML = d.recent_sales.map(s=>
    \`<tr><td>\${new Date(s.sold_at).toLocaleString()}</td><td>\${s.client_name}</td><td>\${s.deck_name}</td><td>\${s.format}</td><td>\${s.card_count}</td><td class="money">\${f(s.sale_value)}</td><td class="fee">\${f(s.nexus_fee)}</td></tr>\`
  ).join('');
}
load(); setInterval(load,30000);
</script>
</body></html>`;

const PORTAL_HTML = `<!DOCTYPE html>
<html>
<head>
  <title>NEXUS HQ — Client Portal Admin</title>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:'Segoe UI',sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh}
    .header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px 40px;border-bottom:2px solid #4a9eff}
    .header h1{color:#4a9eff;font-size:26px}
    .container{padding:28px 40px;max-width:1600px;margin:0 auto}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:28px}
    .card{background:#1a1a2e;border:1px solid #333;border-radius:10px;padding:20px}
    .card h2{color:#4a9eff;font-size:15px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #333}
    table{width:100%;border-collapse:collapse}
    th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #1a1a2e;font-size:13px}
    th{background:#141428;color:#4a9eff;font-size:11px;text-transform:uppercase}
    tr:hover td{background:#141428}
    .badge{padding:2px 7px;border-radius:4px;font-size:10px;background:#1a365d;color:#63b3ed}
    .form-row{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
    input,select{background:#0d0d1a;border:1px solid #333;color:#e0e0e0;padding:8px 10px;border-radius:6px;font-size:13px;flex:1;min-width:120px}
    .btn{background:#4a9eff;color:#000;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:700;font-size:12px;white-space:nowrap}
    .btn.gold{background:#d4af37}
    .btn:hover{opacity:.9}
    .status{font-size:12px;color:#4ade80;margin-top:6px;min-height:18px}
  </style>
</head>
<body>
${NAV}
<div class="header">
  <h1>🔐 Client Portal Admin</h1>
</div>
<div class="container">
  <div class="grid2">
    <!-- Register HQ Client -->
    <div class="card">
      <h2>Register HQ Client (Shop)</h2>
      <div class="form-row"><input id="rName" placeholder="Shop name" /></div>
      <div class="form-row"><input id="rEmail" placeholder="Email" /></div>
      <div class="form-row">
        <select id="rTier">
          <option value="starter">Starter — $29/mo (8%)</option>
          <option value="professional">Professional — $79/mo (6%)</option>
          <option value="enterprise">Enterprise — $199/mo (4%)</option>
          <option value="founders">Founder's Edition — $0/mo (5%)</option>
        </select>
      </div>
      <div class="form-row"><input id="rLocation" placeholder="Location (optional)" /></div>
      <div class="form-row"><input id="rPhone" placeholder="Phone (optional)" /></div>
      <button class="btn gold" onclick="registerClient()">Register Client</button>
      <div class="status" id="rStatus"></div>
    </div>

    <!-- Generate Invoices -->
    <div class="card">
      <h2>Subscription Billing</h2>
      <button class="btn" onclick="genInvoices()">Generate Monthly Invoices</button>
      <div class="status" id="invStatus"></div>
      <div style="margin-top:16px" id="pendingInvDiv"></div>
    </div>
  </div>

  <!-- Client list -->
  <div class="card" style="margin-bottom:24px">
    <h2>HQ Clients</h2>
    <table><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Tier</th><th>Monthly Fee</th><th>Commission</th><th>Last Seen</th></tr></thead>
    <tbody id="clientsTbl"></tbody></table>
  </div>

  <!-- Portal Users -->
  <div class="card" style="margin-bottom:24px">
    <h2>Portal Users (License Holders)</h2>
    <table><thead><tr><th>ID</th><th>Email</th><th>Shop</th><th>Tier</th><th>Joined</th></tr></thead>
    <tbody id="usersTbl"></tbody></table>
  </div>

  <!-- Release Version -->
  <div class="card">
    <h2>Push Software Update</h2>
    <div class="form-row"><input id="vVer" placeholder="Version (e.g. 3.0.2)" /></div>
    <div class="form-row"><input id="vUrl" placeholder="Download URL" /></div>
    <div class="form-row"><input id="vLog" placeholder="Changelog" /></div>
    <div class="form-row">
      <label style="color:#888;font-size:13px;display:flex;align-items:center;gap:6px">
        <input type="checkbox" id="vMand" style="width:auto;flex:none"> Mandatory update
      </label>
    </div>
    <button class="btn" onclick="pushVersion()">Push Version</button>
    <div class="status" id="vStatus"></div>
  </div>
</div>
<script>
const f = n=>'$'+parseFloat(n||0).toFixed(2);

async function registerClient(){
  const s = document.getElementById('rStatus');
  s.textContent = 'Registering...'; s.style.color='#888';
  const r = await fetch('/api/clients/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    name:document.getElementById('rName').value,
    email:document.getElementById('rEmail').value,
    tier:document.getElementById('rTier').value,
    location:document.getElementById('rLocation').value,
    phone:document.getElementById('rPhone').value,
  })});
  const d = await r.json();
  if(d.success){s.textContent='✓ Registered! API Key: '+d.api_key; s.style.color='#4ade80'; loadClients();}
  else{s.textContent='✗ '+d.error; s.style.color='#f87171';}
}

async function genInvoices(){
  const s = document.getElementById('invStatus');
  const d = await fetch('/api/subscriptions/generate-invoices',{method:'POST'}).then(r=>r.json());
  s.textContent = d.invoices_created+' invoices generated';
  s.style.color='#4ade80';
  loadPendingInvoices();
}

async function loadPendingInvoices(){
  const d = await fetch('/api/subscriptions/invoices').then(r=>r.json());
  const div = document.getElementById('pendingInvDiv');
  if(!d.invoices.length){div.innerHTML='<p style="color:#666;font-size:13px">No pending invoices</p>';return;}
  div.innerHTML='<table><thead><tr><th>Invoice</th><th>Client</th><th>Amount</th><th>Action</th></tr></thead><tbody>'+
    d.invoices.map(i=>\`<tr><td>\${i.id}</td><td>\${i.client_name}</td><td class="fee">\${f(i.amount)}</td><td><button class="btn" onclick="payInv('\${i.id}')">Mark Paid</button></td></tr>\`).join('')+'</tbody></table>';
}

async function payInv(id){
  await fetch('/api/subscriptions/invoices/'+id+'/pay',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"payment_method":"manual"}'});
  loadPendingInvoices();
}

async function loadClients(){
  const d = await fetch('/api/clients').then(r=>r.json());
  document.getElementById('clientsTbl').innerHTML = d.clients.map(c=>
    \`<tr><td style="font-size:11px;color:#888">\${c.id}</td><td><b>\${c.name}</b></td><td>\${c.email||'-'}</td><td><span class="badge">\${c.subscription_tier}</span></td><td class="fee">\${f(c.monthly_fee)}/mo</td><td>\${c.commission_rate}%</td><td>\${c.last_seen?new Date(c.last_seen).toLocaleDateString():'-'}</td></tr>\`
  ).join('');
}

async function loadUsers(){
  const d = await fetch('/api/portal/users').then(r=>r.json());
  document.getElementById('usersTbl').innerHTML = d.users.map(u=>
    \`<tr><td>\${u.id}</td><td>\${u.email}</td><td>\${u.shop_name||'-'}</td><td><span class="badge">\${u.subscription_tier}</span></td><td>\${u.created_at?new Date(u.created_at).toLocaleDateString():'-'}</td></tr>\`
  ).join('');
}

async function pushVersion(){
  const s = document.getElementById('vStatus');
  const r = await fetch('/api/portal/versions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    version:document.getElementById('vVer').value,
    download_url:document.getElementById('vUrl').value,
    changelog:document.getElementById('vLog').value,
    mandatory:document.getElementById('vMand').checked,
  })});
  const d = await r.json();
  s.textContent = d.success?'✓ Version pushed':'✗ '+d.error;
  s.style.color = d.success?'#4ade80':'#f87171';
}

loadClients(); loadUsers(); loadPendingInvoices();
</script>
</body></html>`;
