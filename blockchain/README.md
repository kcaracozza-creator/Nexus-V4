# NEXUS Blockchain Integration

**Patent Pending - Kevin Caracozza**

## Overview

Every card scanned at NEXUS stations gets minted as an NFT on Polygon with:
- **Timestamp** (block time = irrefutable)
- **Market price** at time of scan
- **Card metadata** (TCG, set, condition, grade)
- **Scanner location** (World Cup booth, shop ID, etc.)

**After 90 days, NEXUS owns the irrefutable historical data layer for that market.**

PSA/TCGPlayer can't replicate this without infringing our patent claims. We become the price oracle.

## Architecture

```
Scanner Station (SNARF/BROCK)
  ↓
Card Identified
  ↓
Polygon Minter (Python)
  ↓
NFT Minted on Polygon
  ↓
Price Oracle (on-chain query)
```

## Quick Start

### 1. Deploy Contract

```bash
cd E:\NEXUS_V2_RECREATED\blockchain

# Install dependencies
npm install

# Copy .env.example to .env and fill in your private key
cp .env.example .env

# Deploy to Polygon testnet (Mumbai)
npm run deploy:testnet

# Deploy to Polygon mainnet (when ready)
npm run deploy:mainnet
```

### 2. Integrate with Scanner

```python
from blockchain.polygon_minter import PolygonMinter, mint_from_scanner_result

# Initialize minter
minter = PolygonMinter(
    contract_address="0x...",  # From deployment
    private_key="0x...",        # Your private key
    testnet=False               # Use mainnet
)

# Mint NFT from scanner result
result = mint_from_scanner_result(
    minter=minter,
    scan_result=scanner_data,
    recipient_wallet="0x...",   # User's wallet
    scanner_id=1,               # World Cup booth #
    scan_location="World Cup 2026 - Booth 1"
)

print(f"Minted NFT #{result['token_id']}")
```

### 3. Query Price Oracle

```python
# Get 90-day price history for a card
history = minter.get_price_history("mtg-123456", days_back=90)

# Get average market price (irrefutable on-chain data)
avg = minter.get_average_price("mtg-123456", days_back=90)
print(f"Average price: ${avg['avg_price_usd']}")
print(f"Sample size: {avg['sample_size']} scans")
print(f"Data source: {avg['data_source']}")  # "on-chain (irrefutable)"
```

## Patent Angle

**If they ask about competition/moat:**

"Every card scanned at World Cup gets minted on-chain with timestamp + price. After 90 days, NEXUS owns the irrefutable historical data layer for that market. PSA/TCGPlayer can't replicate that without infringing our claims. **We become the price oracle.**"

That's not "We have hardware." That's **"We control market truth."**

## Contract Functions

### `mintCardScan()`
Mint NFT when card is scanned. Only authorized scanners can call this.

### `getCardPriceHistory(cardId, daysBack)`
Query historical price data for a card. Returns arrays of timestamps and prices.

### `getAveragePrice(cardId, daysBack)`
Get average market price from on-chain data. This is the PRICE ORACLE.

### `authorizeScanner(scannerId)`
Authorize a new scanner station (World Cup booth, shop location, etc.)

## Gas Costs

On Polygon mainnet:
- Deploy contract: ~$2-5 (one-time)
- Mint NFT: ~$0.01-0.05 per card
- Query price: FREE (read-only)

You can cover gas costs for users, or charge a premium tier.

## World Cup Integration

For World Cup launch:
1. Deploy contract to Polygon mainnet
2. Authorize scanner booth IDs (1, 2, 3, etc.)
3. Each scan auto-mints NFT to user's wallet (free or paid tier)
4. After event, you own 90 days of irrefutable pricing data

## Revenue Model

- **Free tier**: User gets NFT, you own price data
- **Premium tier**: User gets NFT + full metadata, advanced analytics
- **Enterprise**: Shops/dealers get API access to price oracle

## Next Steps

- [ ] Deploy to Polygon mainnet
- [ ] Integrate with scanner_client.py
- [ ] Set up IPFS for metadata storage
- [ ] Build price oracle API endpoint
- [ ] Verify contract on Polygonscan
- [ ] Create user wallet registration flow

## Files

- `CardNFT.sol` - Solidity smart contract
- `polygon_minter.py` - Python integration
- `deploy_polygon.js` - Deployment script
- `hardhat.config.js` - Hardhat configuration
- `package.json` - NPM dependencies

## Support

Questions? Email: kevin@nexusproject.com
