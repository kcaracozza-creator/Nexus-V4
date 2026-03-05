# Deploy NEXUS Blockchain - Before Tuesday Meeting

## Prerequisites (5 minutes)

1. **Get MATIC for gas**
   - Buy $50-100 MATIC on Coinbase/Binance
   - Send to your deployment wallet
   - Address: (you'll create this in step 2)

2. **Install Node.js** (if not installed)
   ```bash
   # Check if installed
   node --version

   # If not: Download from nodejs.org
   ```

## Deployment (10 minutes)

```bash
# 1. Go to blockchain directory
cd E:\NEXUS_V2_RECREATED\blockchain

# 2. Install dependencies
npm install

# 3. Create .env file
copy .env.example .env

# 4. Edit .env - add your private key
notepad .env
# Add: PRIVATE_KEY=0x... (your wallet private key)

# 5. Deploy to Polygon MAINNET
npm run deploy:mainnet

# Output will show:
# ✓ Contract deployed to: 0x...
# Copy this address - you need it for the meeting
```

## After Deployment

The contract is LIVE on Polygon. Now:

1. **Verify on Polygonscan**
   ```bash
   npm run verify 0xYourContractAddress
   ```

2. **Test Minting**
   ```bash
   cd ..
   python blockchain/polygon_minter.py
   ```

3. **Authorize World Cup Scanners**
   - Scanner #1 is already authorized
   - Add more: `minter.authorize_scanner(2)` for booth #2, etc.

## For the Meeting

Show them:

1. **Live contract on Polygonscan**: https://polygonscan.com/address/0xYourAddress
2. **First minted card**: "Here's card #1 - timestamp, price, all on-chain"
3. **Price oracle query**: "90 days from now, we own this data layer"

## Integration Timeline

- **Now → Tuesday**: Deploy contract, mint test cards
- **Tuesday meeting**: Show live blockchain proof
- **Post-meeting**: Integrate with scanner stations
- **World Cup launch**: Every scan auto-mints NFT

## Cost Breakdown

- Deploy contract: ~$2-5 (one-time)
- Mint per card: ~$0.01-0.05
- Query price: FREE (read-only)

For World Cup, if you scan 1000 cards = $10-50 in gas total. You can:
- Cover it (marketing expense)
- Charge premium tier ($1-5 per scan = profitable)
- Split with shops (they cover gas, you provide tech)

## Questions They'll Ask

**Q: What if Polygon goes down?**
A: Data is replicated across thousands of nodes. More reliable than AWS.

**Q: Can we switch chains later?**
A: Yes - contract is standard ERC-721. Deploy to Ethereum, Base, Arbitrum, etc.

**Q: What if gas fees spike?**
A: Polygon is ~1000x cheaper than Ethereum. Even if it 10x, still pennies.

**Q: How do users get wallets?**
A:
- Option 1: Email-based wallets (Magic.link, Web3Auth) - no crypto knowledge needed
- Option 2: Metamask for power users
- Option 3: You custody wallets (easiest for World Cup)

## Revenue Model

1. **Free tier**: User gets NFT, you own price data (loss leader)
2. **Premium ($5/month)**: Advanced analytics, API access
3. **Enterprise ($500/month)**: Shops get price oracle API, white-label scanner

After 90 days of World Cup scans, you have pricing data competitors CAN'T GET without your permission.

## Next Steps After Meeting

If they're interested:
- [ ] Integrate with scanner_client.py (auto-mint on scan)
- [ ] Build user wallet registration flow
- [ ] Set up IPFS for card images/metadata
- [ ] Create price oracle API endpoint
- [ ] Design NFT marketplace (trade scanned cards)

Ready to go! 🚀
