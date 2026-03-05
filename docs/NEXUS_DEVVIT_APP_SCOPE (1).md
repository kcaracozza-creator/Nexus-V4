# NEXUS DEVVIT APP SCOPE
## "Card Check" — Instant Price Lookup for Reddit

---

## WHAT IT IS

A free interactive Reddit app that lets users look up any trading card's current market price directly inside Reddit posts and comments. Type a card name, get instant price, set info, and market trend. Powered by NEXUS.

Every interaction = NEXUS brand exposure + Reddit Developer Fund revenue.

---

## WHY THIS IS PERFECT

1. **You already have the data.** 106,000+ cards indexed across MTG, Pokemon, sports.
2. **Free APIs exist.** Scryfall (MTG), Pokemon TCG API, no cost to query.
3. **Reddit hosts it for FREE.** Zero server cost. Reddit runs the app on their infrastructure.
4. **The target subs are MASSIVE.** 1.5M+ combined members across collectible subs.
5. **Every user sees "Powered by NEXUS."** It's a marketing engine that pays YOU.
6. **Revenue from Day 1.** Reddit Developer Funds pay per engagement tier.
7. **No hardware needed.** This is pure software. Ships while you wait on parts.

---

## THE APP: "NEXUS Card Check"

### Core Feature
User types a card name → App returns:
- Card name and set
- Current market price (low / mid / high)
- Price trend (up/down/stable vs 30 days ago)
- Card image thumbnail
- Link to full listing on nexus-cards.com

### How It Works on Reddit

**Option A: Interactive Post (Recommended)**
- Moderator installs the app in their subreddit
- App creates an interactive "Card Check" post pinned at top
- Users type card names into the embedded search box
- Results appear inline — no leaving Reddit
- Other users can see recent lookups (community engagement)

**Option B: Comment Trigger**
- User comments `!pricecheck [card name]` on any post
- Bot replies with price data
- Simpler to build, less visual, still effective

**Option C: Both**
- Interactive post for dedicated price checking
- Comment trigger for casual lookups anywhere in the sub
- Maximum engagement = maximum revenue

### What Users See

```
╔══════════════════════════════════════════╗
║  🐉 NEXUS Card Check                    ║
║                                          ║
║  🔍 [Search any card...]                 ║
║                                          ║
║  ┌──────────────────────────────────┐    ║
║  │ [Card Image]  Black Lotus        │    ║
║  │               Alpha (1993)       │    ║
║  │                                  │    ║
║  │   Low:    $42,000                │    ║
║  │   Mid:    $85,000                │    ║
║  │   High:   $510,000              │    ║
║  │                                  │    ║
║  │   📈 +12% (30 days)             │    ║
║  │                                  │    ║
║  │   🔗 View on nexus-cards.com     │    ║
║  └──────────────────────────────────┘    ║
║                                          ║
║  Recent Lookups:                         ║
║  • Ragavan, Nimble Pilferer - $52.30     ║
║  • Charizard VMAX - $180.00             ║
║  • Mike Trout RC - $340.00              ║
║                                          ║
║  Powered by NEXUS 🐉                    ║
╚══════════════════════════════════════════╝
```

---

## TECH STACK

### Platform
- **Devvit Web** — Reddit's developer platform
- **TypeScript** — Required by Devvit
- **React** — For the interactive UI (Devvit Web supports it)
- **Redis** — Built-in storage from Reddit (free, included)

### Data Sources (all FREE)
- **Scryfall API** — MTG cards (free, no key needed, 10 requests/sec)
  - Endpoint: `https://api.scryfall.com/cards/search?q={name}`
  - Returns: name, set, prices (usd, usd_foil), image URIs
- **Pokemon TCG API** — Pokemon cards (free, 1000 req/day no key)
  - Endpoint: `https://api.pokemontcg.io/v2/cards?q=name:{name}`
  - Returns: name, set, prices, images
- **Sports Card APIs** — Various (may need TCDB cache on Zultan)

### Caching Strategy
- Cache card lookups in Reddit's built-in Redis
- Cache TTL: 1 hour for prices, 24 hours for card metadata
- Reduces API calls, faster responses
- Popular cards served from cache instantly

---

## REVENUE PROJECTIONS

### Developer Fund Payouts (one-time per tier)

**Engagement Revenue:**
| Tier | Threshold | Payout | Realistic Timeline |
|------|-----------|--------|-------------------|
| 1 | 500 daily users | $500 | Week 2-3 |
| 2 | 1,000 daily users | $1,000 | Month 1-2 |
| 3 | 10,000 daily users | $5,000 | Month 2-3 |
| 4 | 25,000 daily users | $10,500 | Month 3-6 |
| 5 | 50,000 daily users | $25,000 | Month 6+ |
| 6 | 100,000 daily users | $25,000 | Month 6+ |

**Install Revenue:**
| Tier | Threshold | Payout |
|------|-----------|--------|
| 1 | 50 communities | $500 |
| 2 | 250 communities | $1,000 |
| 3 | 1,000 communities | $2,000 |

**Conservative estimate:** $1,500 - $6,500 in first 3 months
**Aggressive estimate:** $17,000 - $42,000 in first 6 months

### Why Engagement Numbers Are Realistic

Target subreddits (SFW, 200+ members, logged-in users):
- r/magicTCG — 700,000+ members
- r/PokemonTCG — 500,000+ members
- r/mtgfinance — 150,000+ members
- r/baseballcards — 100,000+ members
- r/footballcards — 50,000+ members
- r/basketballcards — 50,000+ members
- r/hockeycards — 30,000+ members
- r/yugioh — 300,000+ members
- r/SportCardTracker — Various
- Dozens of smaller collecting subs

**Total addressable Reddit audience: 2,000,000+ members**

Even 0.5% daily engagement = 10,000 daily users = Tier 3 ($6,500 cumulative)

### Revenue Beyond Reddit Funds

The REAL money isn't the Developer Fund. It's what the app DRIVES:
- Every lookup links to nexus-cards.com
- Every user sees "Powered by NEXUS"
- Email signups from nexus-cards.com
- Kickstarter traffic from Reddit users
- Brand recognition in EVERY collector community

---

## THREE APPS (Maximum 3 qualify for funds)

Reddit pays for up to 3 apps. Build one platform, skin it three ways:

### App 1: "NEXUS MTG Check"
- MTG-specific card lookup
- Target: r/magicTCG, r/mtgfinance, r/EDH, r/ModernMagic
- Data: Scryfall API
- Unique feature: Commander deck price calculator

### App 2: "NEXUS Pokemon Check"
- Pokemon-specific card lookup
- Target: r/PokemonTCG, r/pokemoncardvalue, r/PokemonCardCollectors
- Data: Pokemon TCG API
- Unique feature: Set completion tracker

### App 3: "NEXUS Sports Check"
- Sports cards (baseball, basketball, football, hockey)
- Target: r/baseballcards, r/basketballcards, r/footballcards, r/hockeycards
- Data: TCDB cache / Zultan
- Unique feature: Rookie card spotlight

**Three apps × full tier payouts = up to $501,000 theoretical maximum**
**Realistic 6-month target across 3 apps: $20,000 - $50,000**

---

## BUILD PLAN

### Phase 1: MVP — "NEXUS MTG Check" (Week 1)
- [ ] Set up Devvit dev environment (Node 22, npm, Devvit CLI)
- [ ] Create Reddit account for NEXUS app developer
- [ ] Initialize project with Devvit Web template
- [ ] Build search UI (text input, card display, price output)
- [ ] Integrate Scryfall API (free, no key needed)
- [ ] Add Redis caching for lookups
- [ ] Add "Powered by NEXUS" branding + nexus-cards.com link
- [ ] Create test subreddit (r/NEXUSCardCheck or similar)
- [ ] Playtest and debug
- [ ] Submit for Reddit App Review

### Phase 2: Comment Bot (Week 2)
- [ ] Add `!pricecheck` comment trigger
- [ ] Auto-reply with formatted price data
- [ ] Works across all installed subreddits
- [ ] Add `!foilcheck` for foil prices

### Phase 3: Pokemon + Sports Apps (Week 3-4)
- [ ] Clone MTG app, swap data source to Pokemon TCG API
- [ ] Clone MTG app, swap data source to sports card data
- [ ] Submit both for review
- [ ] Deploy across target subreddits

### Phase 4: Growth (Ongoing)
- [ ] Reach out to subreddit moderators for installs
- [ ] Add "Daily Price Movers" auto-posts (top gainers/losers)
- [ ] Add collection value tracker feature
- [ ] Add price alerts (user sets threshold, app notifies)
- [ ] Community leaderboard (most lookups, best finds)

---

## SUBREDDIT OUTREACH PLAN

Getting installed in subreddits is KEY. More installs = more engagement = more revenue.

**Approach for moderators:**
```
Subject: Free price check tool for your community

Hey [mod name],

I built a free card price lookup app for Reddit using Devvit. 
Your members can search any [MTG/Pokemon/sports] card and get 
instant market prices without leaving the subreddit.

No ads. No data collection. Just a free utility for collectors.

Would you be open to trying it in [subreddit name]? Happy to 
set up a demo post so you can test it first.

Thanks!
```

**Target: 50 installs in first month** (hits Tier 1 install payout of $500)

---

## WHAT MENDEL NEEDS TO BUILD

This is a TypeScript/JavaScript project. Mendel's lane.

### File Structure
```
nexus-card-check/
├── devvit.yaml          # App config
├── package.json         # Dependencies
├── src/
│   ├── main.ts          # Entry point, Devvit app registration
│   ├── components/
│   │   ├── CardSearch.tsx    # Search input UI
│   │   ├── CardResult.tsx    # Price display card
│   │   └── RecentLookups.tsx # Community recent searches
│   ├── api/
│   │   ├── scryfall.ts      # MTG price fetcher
│   │   ├── pokemon.ts       # Pokemon price fetcher
│   │   └── sports.ts        # Sports card fetcher
│   ├── cache/
│   │   └── redis.ts         # Redis caching layer
│   └── utils/
│       └── formatPrice.ts   # Price formatting helpers
├── assets/
│   └── nexus-logo.png       # Branding assets
└── README.md
```

### Key Technical Requirements
1. Devvit Web app (not Blocks — need rich UI)
2. Use `fetch()` for external API calls
3. Redis for caching (built into Devvit, free)
4. Interactive post type with search functionality
5. Comment trigger handler for `!pricecheck`
6. Responsive design (works on mobile Reddit)
7. NEXUS branding on every screen

---

## COMPETITIVE ANALYSIS

### Existing Reddit Price Bots
Most current price bots are basic text-only comment bots. They respond to triggers but have NO visual UI. No images. No interactive search. No brand presence.

### NEXUS Card Check Advantages
- **Visual UI** — Card images, formatted prices, trend arrows
- **Interactive** — Search without commenting, browse results
- **Multi-category** — MTG, Pokemon, AND sports in one ecosystem
- **Community features** — Recent lookups, trending cards
- **Professional branding** — NEXUS dragon, clean design
- **Maintained** — Backed by a real company, not a hobby bot

---

## TIMELINE TO FIRST DOLLAR

| Day | Milestone |
|-----|-----------|
| 1-3 | Set up Devvit, build MVP, test on private sub |
| 4-5 | Submit for Reddit App Review |
| 5-7 | Review period (Reddit reviews apps) |
| 7-10 | Deploy to first 5 subreddits |
| 10-14 | Outreach to moderators, push for 50 installs |
| 14-21 | Hit 500 daily users (Tier 1: $500) |
| 21-30 | Hit 1,000 daily users (Tier 2: +$1,000) |

**First revenue within 2-3 weeks of launch.**

---

## COST TO BUILD

- Devvit hosting: **FREE** (Reddit hosts everything)
- Scryfall API: **FREE** (no key required)
- Pokemon TCG API: **FREE** (no key required)
- Development: **Mendel** (already on payroll... sort of)
- Total: **$0.00**

Zero cost. Pure profit from Developer Fund payouts.
Plus infinite brand marketing value.

---

## THE BOTTOM LINE

This is bridge money AND a marketing engine rolled into one.

While you're waiting on scanner parts:
- App gets built (Mendel's job)
- App gets deployed (free hosting)
- App starts earning (Developer Fund)
- App starts marketing (every user sees NEXUS)
- App drives traffic (every card links to nexus-cards.com)
- App builds email list (Kickstarter fuel)

The scanner is the cannon. This app is the flag that flies while you load it.

Revenue. Marketing. Brand awareness. Email capture. Zero cost.

This is the play. 🐉
