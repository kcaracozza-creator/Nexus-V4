# NEXUS - Investor Brief
### Collectible Card Authentication, Valuation & Marketplace Platform
**Patent Pending - Kevin Caracozza, Inventor**
**February 2026**

---

## Executive Summary

NEXUS is a vertically integrated platform for collectible trading card authentication, real-time valuation, and blockchain-verified provenance. The system combines proprietary hardware (scanner stations with robotic automation), computer vision AI, and Polygon blockchain to create an immutable chain of custody for every card scanned.

The platform is **live and deployed** on Polygon mainnet with a verified smart contract, operational scanner hardware, and a database covering **2.4M+ cards** across all major TCGs (Magic: The Gathering, Pokemon, Sports).

**First commercial deployment target: FIFA World Cup 2026 (June-July 2026)**

---

## Platform Metrics (Current State)

### Data Assets

| Asset | Count | Description |
|-------|-------|-------------|
| MTG Card Metadata | 521,124 | Complete Magic: The Gathering catalog |
| Pokemon Card Metadata | 19,818 | Full Pokemon TCG catalog |
| Sports Card Database | 1,835,350 | TCDB-sourced: Baseball 1,393,956 / Soccer 177,166 / Football 88,757 / Hockey 80,678 / Basketball 61,979 / Wrestling 17,650 / Racing 15,164 |
| **Total Card Database** | **2,376,292** | Cross-TCG searchable, unified API |
| Marketplace Cards (D1) | 57,602 | Cloud-synced to Cloudflare D1 for marketplace |
| MTG Visual Embeddings (FAISS) | 370,429 | GPU-accelerated visual search index |
| Pokemon Visual Embeddings (FAISS) | 19,765 | GPU-accelerated visual search index |
| Inventory Database | 26,850 | Physical cards cataloged in system |
| Cross-Reference Bridge Table | 390,194 | Links across metadata sources |

### Hardware Infrastructure

| Component | Specs | Role |
|-----------|-------|------|
| **ZULTAN** (GPU Server) | NVIDIA RTX 3060 12GB VRAM, 9TB storage (8.5TB free), 2.7GB AI models | FAISS visual search, card API, metadata |
| **SNARF** (Scanner Station 1) | Raspberry Pi 5, CZUR Scanner | OCR pipeline, primary capture station |
| **BROCK** (Scanner Station 2) | Raspberry Pi 5, Google Coral M.2 TPU | Art recognition, edge AI inference |
| **Robotic Arm** | 5-DOF, vacuum gripper, dual ESP32 | Automated card handling & sorting |
| **Light Box** | ESP32-controlled photography lighting | Consistent capture conditions |
| **7" Touchscreen Kiosk** | 800x480, fullscreen UI | On-site operator interface |

### Cloud Infrastructure (Cloudflare)

| Service | Details |
|---------|---------|
| **Workers** (6 deployed) | `nexus-marketplace-api`, `narwhal-council-relay`, `nexus-hq` + 3 utility |
| **D1 Databases** (3) | `nexus-marketplace` (21 tables, 57,602 cards, 21.7 MB), `nexus-hq`, `nexus-card-catalog` |
| **KV Namespaces** (4) | MESSAGES, NARWHAL_TASKS, NARWHAL_CONFIG, NEXUS_KNOWLEDGE |
| **R2 Storage Buckets** (2) | `nexus-card-images`, `nexus-scans` (ENAM region) |
| **Vectorize** | `nexus-card-embeddings` (768-dim, cosine similarity, BGE-base) |
| **Workers AI** | Card classification, description, embedding generation |
| **Region** | All resources in ENAM (Eastern North America) |

### Blockchain (Polygon Mainnet - LIVE)

| Metric | Value |
|--------|-------|
| **Contract** | `0x72a4e96cF2203DF1C1D4d3543397feB2a26C728E` |
| **Network** | Polygon Mainnet (Chain ID 137) |
| **Token Name / Symbol** | NEXUS Card Scan / NEXUS |
| **Status** | Verified on Polygonscan |
| **Tokens Minted** | 4 (prototype validation complete) |
| **Total Transactions** | 6 (deploy + authorize + 4 mints) |
| **Avg Gas per Mint** | ~327,716 gas (< $0.01 USD) |
| **Deployer Balance** | 81.47 POL (operational runway) |
| **Batch Capacity** | 100 cards per transaction (50x gas savings) |
| **Daily Throughput** | 1,100+ cards/day designed capacity |

---

## Revenue Products

### 1. Proof of Presence (PoP) NFT Minting
**Revenue Model: Per-scan fee**

Every card scanned through NEXUS is cryptographically hashed (SHA-256 "Optical DNA") and minted as an ERC-721 token on Polygon. The token records:
- Timestamp (immutable)
- GPS/geofence location (proves WHERE the card was scanned)
- Optical DNA hash (proves WHAT was scanned)
- Market price at scan time (proves VALUE at that moment)
- Scanner station ID (proves WHICH device)

**Two tiers:**
| Tier | Process | Target Price |
|------|---------|-------------|
| **Standard** | Single capture, single SHA-256 hash | $0.50 - $1.00 per scan |
| **Collector** | 5-shot burst, dual-hash (wide + detail crop), barcode scan | $2.00 - $5.00 per scan |

**Use case:** Card shows, shops, events - collector pays to get blockchain proof their card is real, in specific condition, at a specific time and place.

### 2. NEXUS Marketplace
**Revenue Model: Transaction fees (2.5% - 5%)**

Full marketplace infrastructure deployed on Cloudflare:
- Card listings with AI-generated descriptions
- Vector similarity search (find visually similar cards)
- Shopping cart, wallet, order management
- Seller onboarding and review system
- 20-table D1 database ready for production

**Endpoints live:** `/v1/cards`, `/v1/listings`, `/v1/orders`, `/v1/inventory`, `/v1/cart`, `/v1/wallet`, `/v1/reviews`, `/v1/sellers`

### 3. Scanner Station Licensing (B2B SaaS)
**Revenue Model: Hardware sale + monthly subscription**

Licensed scanner stations for card shops, grading services, and event organizers:

| Component | Revenue |
|-----------|---------|
| Hardware Kit (Pi 5 + CZUR + enclosure) | $500 - $800 one-time |
| Software License (monthly) | $49 - $149/month |
| Delegated Minting Authorization | Included in license |
| Data Network Rewards | 0.01 POL per scan back to shop |

**Smart contract supports:** Up to 255 authorized scanner stations, delegated minting (shops mint directly without bottleneck).

### 4. Automated Card Recognition (ACR) API
**Revenue Model: Per-call API pricing**

The ACR pipeline identifies cards from photos using:
- CZUR high-res capture (4624 x 3472)
- Google Coral TPU edge inference (BROCK)
- FAISS GPU-accelerated visual search (ZULTAN)
- OCR text extraction (SNARF)
- Claude AI final classification

| Tier | Calls/Month | Price |
|------|-------------|-------|
| Free | 100 | $0 |
| Pro | 10,000 | $29/month |
| Enterprise | 100,000+ | $0.005/call |

### 5. On-Chain Price Oracle
**Revenue Model: Data licensing**

The smart contract aggregates price snapshots every 100 scans per card. After sufficient volume, NEXUS becomes an authoritative price source:

- `getAveragePrice(cardIdHash, daysBack)` - Market consensus price
- `getCardPriceHistory(cardIdHash)` - Historical price snapshots
- `getCurrentMarketPrice(cardIdHash)` - 7-day rolling average

**Target customers:** Insurance companies, estate appraisers, auction houses, competing marketplaces.

| Tier | Access | Price |
|------|--------|-------|
| Basic API | Delayed data (24h) | $99/month |
| Real-time | Live oracle queries | $499/month |
| Enterprise | Full historical + bulk | Custom |

### 6. Grading Authority Service
**Revenue Model: Per-card grading fee**

NEXUS scans are compared against PSA/Beckett grades on-chain (Patent Claim 101):

- `recordGradeComparison(tokenId, nexusGrade, psaGrade, psaCertNumber)`
- `getGradingAccuracy(cardIdHash)` - "NEXUS matches PSA 87% of the time"

As the dataset grows, NEXUS becomes an independent grading authority — faster and cheaper than PSA ($20/card, 6-month wait).

| Service | Price |
|---------|-------|
| NEXUS Grade (AI scan) | $2 - $5 per card |
| Grade + PoP Certificate | $5 - $10 per card |
| Bulk grading (100+ cards) | $1 - $3 per card |

**Competitive advantage:** PSA charges $20-$150/card with 30-180 day turnaround. NEXUS: $2-$10, instant result, blockchain-verified.

### 7. Event Booth Scanning
**Revenue Model: Event licensing + per-scan revenue share**

Portable scanner stations for card shows, conventions, and sporting events:

| Event Type | Model |
|------------|-------|
| FIFA World Cup 2026 | 50 booth stations, $1-$5/scan |
| Card Shows (monthly) | 2-5 stations, booth rental + scans |
| Comic-Con / Gen Con | Premium booth, collector tier focus |
| Shop Grand Openings | Single station, marketing + data |

**FIFA World Cup 2026 projection (MetLife Stadium, NJ):**
- 50 scanner booths across venue
- ~500 scans/day/booth = 25,000 scans/day
- 30 match days = 750,000 total scans
- At $1/scan average = **$750,000 event revenue**

### 8. Marketplace Consumer Subscriptions
**Revenue Model: Monthly subscription tiers**

Premium access to the NEXUS marketplace and data platform:

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | Browse listings, basic search, 5 scans/month |
| **Collector** | $9.99/month | Unlimited search, price alerts, 50 scans/month, portfolio tracking |
| **Dealer** | $29.99/month | Bulk listing tools, analytics dashboard, 500 scans/month, API access |
| **Shop Pro** | $99.99/month | Unlimited scans, delegated minting, inventory management, priority support |

**Target:** Convert free marketplace users to paid subscribers with premium data access, portfolio tracking, and scan allocations.

### 9. Scanner Lite (Consumer Hardware - 2028)
**Revenue Model: Hardware sale + app subscription**

Compact, affordable scanning device for home collectors — a simplified version of the pro scanner station:

| Component | Revenue |
|-----------|---------|
| Scanner Lite Hardware | $149 - $199 retail |
| NEXUS App (monthly) | $4.99 - $9.99/month |
| PoP minting (in-app) | $0.50 - $2.00/scan |
| Marketplace listing (in-app) | 2.5% transaction fee |

**Specs:** USB-C phone attachment or standalone unit, 12MP+ camera, LED ring light, companion app (iOS/Android). Uses phone GPU for edge inference, NEXUS cloud for final classification.

**Target market:** 45M+ active trading card collectors in the US alone. Entry-level device that feeds the NEXUS ecosystem.

### 10. Consumer Scanner Pro (2028 Roadmap)
**Revenue Model: Premium hardware + subscription**

Full-featured consumer scanner for serious collectors and small dealers:

| Component | Revenue |
|-----------|---------|
| Consumer Scanner Pro Hardware | $299 - $449 retail |
| NEXUS Pro App (monthly) | $14.99/month |
| Unlimited PoP minting | Included |
| Marketplace premium seller | Included |

**Specs:** Standalone unit with built-in display, auto-feed for batch scanning, onboard AI chip, WiFi direct to NEXUS cloud.

### 11. Multi-Agent AI Operations (Narwhal Council)
**Revenue Model: Internal efficiency / future B2B**

4-agent AI coordination system for autonomous platform operations:
- LOUIE (Voice), CLOUSE (Desktop Opus), MENDEL (VS Code Sonnet), JAQUES (Browser Haiku)
- Real-time communication via Cloudflare Workers relay
- Shared knowledge base across agents

**Future B2B potential:** License the multi-agent coordination framework to other platforms.

---

## Revenue Projections

### Year 1: 2026 (Launch Year - World Cup Focus)

| Product | Units | Avg Revenue | Annual |
|---------|-------|-------------|--------|
| World Cup PoP Scans | 750,000 | $1.50/scan | $1,125,000 |
| Card Show Events (12) | 2,000/show | $2.00/scan | $48,000 |
| Scanner Licenses (10 shops) | 10 | $149/mo x 12 | $17,880 |
| Marketplace Transactions | 50,000 | $15 avg x 3.5% | $26,250 |
| Marketplace Consumer Subs | 5,000 | $9.99/mo x 6 (H2 launch) | $299,700 |
| ACR API Subscriptions | 20 | $29/mo x 12 | $6,960 |
| Grading Services | 10,000 | $3.00/card | $30,000 |
| **Year 1 Total** | | | **$1,553,790** |

### Year 2: 2027 (Scale & Subscription Growth)

| Product | Units | Avg Revenue | Annual |
|---------|-------|-------------|--------|
| Event PoP Scans (20 events) | 500,000 | $2.00/scan | $1,000,000 |
| Scanner Licenses (50 shops) | 50 | $149/mo x 12 | $89,400 |
| Marketplace Transactions | 500,000 | $20 avg x 3.5% | $350,000 |
| Marketplace Consumer Subs | 25,000 | $12.99/mo avg x 12 | $3,897,000 |
| ACR API Subscriptions | 200 | $49/mo x 12 | $117,600 |
| Price Oracle Licensing | 10 | $499/mo x 12 | $59,880 |
| Grading Services | 100,000 | $3.00/card | $300,000 |
| **Year 2 Total** | | | **$5,813,880** |

### Year 3: 2028 (Consumer Hardware Launch)

| Product | Units | Avg Revenue | Annual |
|---------|-------|-------------|--------|
| Scanner Lite Sales | 15,000 | $179 | $2,685,000 |
| Scanner Pro Sales | 3,000 | $349 | $1,047,000 |
| Consumer App Subscriptions | 18,000 | $7.99/mo x 12 | $1,725,840 |
| Event PoP Scans | 1,000,000 | $2.00/scan | $2,000,000 |
| Scanner Licenses (200 shops) | 200 | $149/mo x 12 | $357,600 |
| Marketplace Transactions | 2,000,000 | $25 avg x 3.5% | $1,750,000 |
| Marketplace Consumer Subs | 75,000 | $14.99/mo avg x 12 | $13,491,000 |
| ACR API Enterprise | 50 | $99/mo x 12 | $59,400 |
| Price Oracle Licensing | 50 | $499/mo x 12 | $299,400 |
| Grading Services | 500,000 | $2.50/card | $1,250,000 |
| **Year 3 Total** | | | **$24,665,240** |

### 5-Year Summary

| Year | Revenue | Growth | Key Driver |
|------|---------|--------|------------|
| 2026 | $1.55M | Launch | World Cup + marketplace launch |
| 2027 | $5.81M | 275% | Consumer subscription scale |
| 2028 | $24.67M | 324% | Scanner Lite/Pro hardware + subs |
| 2029 | $45M+ | 82% | Network effects, 500+ shops |
| 2030 | $80M+ | 78% | International expansion, data licensing |

---

## Competitive Advantages

### Patent-Protected Technology (Patent Pending)
- **Claim 99:** Network rewards for shops contributing scan data
- **Claim 101:** Grading consistency monitoring across PSA/Beckett/BGS
- **Proof of Presence:** GPS-geofenced, timestamped, blockchain-verified authentication

### Technical Moat
1. **2.4M+ card database** across all major TCGs (largest integrated cross-TCG dataset)
2. **On-chain price oracle** with manipulation-resistant snapshots
3. **Dual-hash Optical DNA** (wide + detail) for forensic-grade authentication
4. **Sub-$0.01 minting cost** on Polygon (100x cheaper than Ethereum)
5. **Edge AI inference** via Google Coral TPU (works offline at events)
6. **Batch minting** - 100 cards per transaction (50x gas savings)
7. **Robotic automation** - 5-DOF arm for hands-free card processing

### First-Mover Advantages
- **Only platform** combining scan authentication + blockchain proof + marketplace
- **Only platform** with on-chain PSA/Beckett grade comparison
- **Only platform** with geofence-proven provenance (proves WHERE a card was authenticated)

---

## Market Opportunity

| Segment | Market Size |
|---------|-------------|
| Global Trading Card Market (2025) | $25.3B |
| Sports Card Market (US) | $13.4B |
| Pokemon TCG | $4.9B |
| Magic: The Gathering | $2.1B |
| Card Grading Services (PSA/BGS/CGC) | $800M+ |
| Card Authentication & Verification | $200M+ (emerging) |

**Active collectors in the US:** 45M+
**PSA cards graded (2024):** 30M+ (at $20-$150/card)

---

## Team & IP

- **Kevin Caracozza** - Inventor, CEO. Patent Pending on NEXUS system.
- **AI Development Team** - Multi-agent AI system (4 specialized agents)
- **Smart Contract** - Verified on Polygon Mainnet, fully auditable

### Intellectual Property
- Patent application filed (Patent Pending)
- Trade secrets: ACR pipeline, FAISS training methodology, Optical DNA algorithm
- Proprietary database: 2.4M+ cross-TCG card catalog with visual embeddings

---

## Current Status & Milestones

### Completed
- [x] Smart contract deployed and **verified** on Polygon Mainnet
- [x] 4 tokens minted on-chain (proof of concept validated, 6 total transactions)
- [x] 2,376,292 cards in database across MTG, Pokemon, and 7 sports
- [x] 390,194 visual embeddings in FAISS indexes (GPU-accelerated)
- [x] 57,602 cards synced to Cloudflare D1 marketplace
- [x] ACR pipeline operational (camera -> TPU -> FAISS -> OCR -> Claude AI -> blockchain)
- [x] Marketplace API deployed (6 Cloudflare Workers, 3 D1 databases, 4 KV namespaces, 2 R2 buckets)
- [x] Touch kiosk UI for 7" scanner station display (800x480 fullscreen)
- [x] Robotic arm integration (5-DOF + vacuum gripper + dual ESP32)
- [x] Multi-agent AI coordination system (4 agents, real-time relay)
- [x] Barcode scanning for sealed products (UPC/EAN/QR from camera image)
- [x] Geofence zones configured (NEXUS HQ + 3 FIFA World Cup 2026 venues + Liberty State Park)
- [x] Dual-hash Collector Tier (wide + detail Optical DNA)
- [x] Unified API serving all TCGs on port 8000 (ZULTAN, confirmed online)

### Next Milestones
- [ ] FIFA World Cup 2026 booth deployment (June 2026)
- [ ] 10 card shop beta program (Q2 2026)
- [ ] Marketplace public launch with consumer subscriptions (Q3 2026)
- [ ] Price oracle goes live (after 10,000+ scans)
- [ ] Scanner Lite prototype (Q1 2028)
- [ ] Scanner Lite + Scanner Pro retail launch (Q3 2028)
- [ ] International expansion (2029)

---

## Investment Ask

**Seeking: [TBD by Kevin]**

**Use of funds:**
1. FIFA World Cup 2026 deployment (50 scanner stations) - Hardware, logistics, staff
2. Card shop beta program - 10 partner shops with licensed stations
3. Marketplace launch - Marketing, onboarding, payment processing
4. Consumer scanner R&D (2028 target)
5. Patent prosecution and IP protection
6. Team expansion (embedded AI engineers, sales)

---

## Contact

**Kevin Caracozza**
Inventor & CEO, NEXUS
Patent Pending

**Live Contract:** [Polygonscan](https://polygonscan.com/address/0x72a4e96cF2203DF1C1D4d3543397feB2a26C728E#code)

---

*This document contains confidential and proprietary information. Patent Pending.*
