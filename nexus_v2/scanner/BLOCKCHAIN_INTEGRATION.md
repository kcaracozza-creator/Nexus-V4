# BLOCKCHAIN INTEGRATION - SCANNER PROTOCOL

## Complete Flow: Scan → Identify → Mint NFT

```
┌─────────────┐
│   SCANNER   │ (BROCK/SNARF)
│  Captures   │
│    Image    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Step 1: Card Identification            │
│  API: ZULTAN (192.168.1.152:8000)      │
│  POST /api/identify                     │
│                                         │
│  Returns: card_id, name, set, price,   │
│           tcg, condition, confidence    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Step 2: Mint NFT on Polygon [NEW]     │
│  Contract: NexusCardNFT.sol            │
│  Function: mintCardScan()              │
│                                         │
│  Returns: token_id, tx_hash            │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│  Step 3: Add to Marketplace [OPTIONAL] │
│  API: Cloudflare D1                    │
│  POST /v1/listings                      │
└─────────────────────────────────────────┘
```

---

## CODE INTEGRATION

### File: `nexus_v2/scanner/universal_card_router.py`

Add blockchain import at top:

```python
# Add after line 30
import os
import sys
from pathlib import Path

# Import blockchain minter
try:
    from blockchain.polygon_minter import PolygonMinter, mint_from_scanner_result
    BLOCKCHAIN_ENABLED = True
except ImportError:
    BLOCKCHAIN_ENABLED = False
    logger.warning("Blockchain integration not available")
```

Add global minter initialization:

```python
# After line 88 (API configuration section)

# Blockchain configuration
POLYGON_CONTRACT = os.getenv('NEXUS_CONTRACT_ADDRESS')
SCANNER_PRIVATE_KEY = os.getenv('NEXUS_SCANNER_PRIVATE_KEY')
SCANNER_ID = int(os.getenv('SCANNER_ID', 1))
SCAN_LOCATION = os.getenv('SCAN_LOCATION', 'Unknown Location')

# Initialize Polygon minter (singleton)
_polygon_minter = None

def get_polygon_minter():
    """Get or create Polygon minter instance"""
    global _polygon_minter
    if _polygon_minter is None and BLOCKCHAIN_ENABLED and POLYGON_CONTRACT:
        _polygon_minter = PolygonMinter(
            contract_address=POLYGON_CONTRACT,
            private_key=SCANNER_PRIVATE_KEY,
            testnet=False  # Production
        )
    return _polygon_minter
```

Add minting function:

```python
# Add new function around line 400 (after identify_card function)

def mint_card_nft(
    card_result: UnifiedCardResult,
    recipient_wallet: str = None
) -> Optional[Dict]:
    """
    Mint NFT on Polygon for identified card

    Args:
        card_result: Unified card result from identify_card()
        recipient_wallet: User's wallet address (or None for custody wallet)

    Returns:
        NFT minting result or None if blockchain disabled
    """
    if not BLOCKCHAIN_ENABLED:
        logger.warning("Blockchain not enabled - skipping NFT mint")
        return None

    minter = get_polygon_minter()
    if not minter:
        logger.error("Polygon minter not initialized")
        return None

    # Use custody wallet if no recipient specified
    if not recipient_wallet:
        recipient_wallet = os.getenv('CUSTODY_WALLET_ADDRESS')
        if not recipient_wallet:
            logger.error("No recipient wallet and no custody wallet configured")
            return None

    try:
        # Convert UnifiedCardResult to scanner result format
        scan_result = {
            'card_id': f"{card_result.card_type}-{card_result.set_code}-{card_result.name}".lower().replace(' ', '-'),
            'name': card_result.name,
            'set_code': card_result.set_code or '',
            'tcg': card_result.card_type.upper(),
            'market_price': card_result.price_usd or 0,
            'condition': 'NM',  # Default - can be detected via AI
            'confidence': card_result.confidence
        }

        # Mint NFT
        nft_result = mint_from_scanner_result(
            minter=minter,
            scan_result=scan_result,
            recipient_wallet=recipient_wallet,
            scanner_id=SCANNER_ID,
            scan_location=SCAN_LOCATION
        )

        if nft_result['success']:
            logger.info(f"✅ Minted NFT #{nft_result['token_id']} - TX: {nft_result['tx_hash'][:10]}...")
        else:
            logger.error(f"❌ NFT mint failed: {nft_result.get('error')}")

        return nft_result

    except Exception as e:
        logger.error(f"NFT minting error: {e}")
        return None


def identify_and_mint(
    ocr_results: List[str],
    card_type: str,
    recipient_wallet: str = None,
    **kwargs
) -> Dict:
    """
    COMPLETE FLOW: Identify card + Mint NFT

    This is the main function scanners should call.

    Args:
        ocr_results: OCR text from card
        card_type: Detected card type (mtg, pokemon, sports_baseball, etc.)
        recipient_wallet: User's wallet address
        **kwargs: Additional params (set_code, collector_num, etc.)

    Returns:
        Combined result with card data + NFT data
    """
    # Step 1: Identify card
    card_result, confidence = identify_card(ocr_results, card_type, **kwargs)

    if not card_result:
        return {
            'success': False,
            'error': 'Card identification failed',
            'confidence': 0
        }

    result = {
        'success': True,
        'card': card_result.to_dict(),
        'confidence': confidence
    }

    # Step 2: Mint NFT (if blockchain enabled)
    if BLOCKCHAIN_ENABLED:
        nft_result = mint_card_nft(card_result, recipient_wallet)
        if nft_result:
            result['nft'] = nft_result

    # Step 3: Report to market data (Flow 9)
    if MARKET_DATA_AVAILABLE:
        try:
            report_scan(card_result.to_dict())
        except Exception as e:
            logger.error(f"Market data reporting failed: {e}")

    return result
```

---

## ENVIRONMENT VARIABLES

Create `.env` on each BROCK/SNARF scanner:

```bash
# E:\NEXUS_V2_RECREATED\.env (or /home/nexus1/.env on Pi)

# Polygon Contract (after deployment)
NEXUS_CONTRACT_ADDRESS=0xYourContractAddressHere

# Scanner Private Key (unique per scanner)
NEXUS_SCANNER_PRIVATE_KEY=0xYourPrivateKeyHere

# Scanner Identity
SCANNER_ID=1  # World Cup Booth #1
SCAN_LOCATION=World Cup 2026 - Booth 1

# Custody Wallet (for users without wallets)
CUSTODY_WALLET_ADDRESS=0xYourCustodyWalletHere

# Zultan API
ZULTAN_API=http://192.168.1.152:8000
```

---

## SCANNER CLIENT UPDATE

### File: `nexus_v2/hardware/scanner_client.py`

Replace `scan_card()` function:

```python
def scan_card(self):
    """Perform card scan with blockchain integration"""
    self.scan_count += 1
    print(f"\n[Scan #{self.scan_count}] Starting...")

    # Turn on scanning lights
    self.arduino.set_color(255, 255, 255)
    self.arduino.set_brightness(255)
    time.sleep(0.2)

    # Capture image
    print("  Capturing image...")
    frame = self.camera.capture_frame()

    if frame is None:
        print("  ✗ Capture failed!")
        self.arduino.set_color(255, 0, 0)  # Red
        time.sleep(1)
        self.arduino.lights_off()
        return None

    # Save temporary image
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_path = self.temp_dir / f"scan_{timestamp}.jpg"
    self.camera.save_image(frame, str(temp_path))
    print(f"  Saved: {temp_path}")

    # Send to NEXUS for identification + NFT minting
    print("  Sending to NEXUS for identification...")
    self.arduino.set_color(255, 255, 0)  # Yellow for processing

    # NEW: Use identify_and_mint instead of identify_card
    from nexus_v2.scanner.universal_card_router import identify_and_mint

    # Get OCR results (assume we have this from ACR pipeline)
    ocr_results = []  # TODO: Get from ACR pipeline
    card_type = "mtg"  # TODO: Detect from card back

    result = identify_and_mint(
        ocr_results=ocr_results,
        card_type=card_type,
        recipient_wallet=os.getenv('USER_WALLET'),  # Optional
        image_path=str(temp_path)
    )

    if not result['success']:
        print(f"  ✗ Error: {result.get('error')}")
        self.arduino.set_color(255, 0, 0)  # Red
        time.sleep(2)
        self.arduino.lights_off()
        return None

    # Success!
    card = result['card']
    nft = result.get('nft')

    print(f"  ✓ Identified: {card['name']} ({card['set_code']})")
    print(f"    Price: ${card['price_usd']:.2f}")
    print(f"    Confidence: {result['confidence']}%")

    if nft and nft['success']:
        print(f"    NFT: #{nft['token_id']} (TX: {nft['tx_hash'][:10]}...)")

    # Green for success
    self.arduino.set_color(0, 255, 0)
    time.sleep(1.5)
    self.arduino.lights_off()

    return result
```

---

## TESTING PROTOCOL

### 1. Deploy Contract to Mumbai Testnet

```bash
cd E:\NEXUS_V2_RECREATED\blockchain
npm install
cp .env.example .env
# Edit .env with your testnet private key
npx hardhat run deploy_polygon.js --network mumbai
```

### 2. Authorize Test Scanner

```python
from blockchain.polygon_minter import PolygonMinter
import json

with open('blockchain/polygon_config.json') as f:
    config = json.load(f)

minter = PolygonMinter(
    contract_address=config['contract_address'],
    private_key=config['private_key'],
    testnet=True
)

# Authorize scanner #1
minter.authorize_scanner(1)
print("✅ Scanner #1 authorized")

# Authorize your wallet as minter
minter.authorize_minter("0xYourWalletAddress")
print("✅ Minter authorized")
```

### 3. Test End-to-End

```python
from nexus_v2.scanner.universal_card_router import identify_and_mint

# Test with known card
result = identify_and_mint(
    ocr_results=["Lightning Bolt", "LEA"],
    card_type="mtg",
    recipient_wallet="0xYourTestWallet"
)

print(result)
# Expected:
# {
#   'success': True,
#   'card': {...},
#   'nft': {
#     'success': True,
#     'token_id': 0,
#     'tx_hash': '0x...'
#   }
# }
```

---

## DEPLOYMENT CHECKLIST

**Before World Cup:**
- [ ] Deploy contract to Polygon mainnet
- [ ] Authorize scanners 1-50
- [ ] Generate 50 scanner wallets (1 per booth)
- [ ] Fund each scanner wallet with 50 MATIC (~$25)
- [ ] Authorize all 50 scanner wallets as minters
- [ ] Update .env on each BROCK/SNARF
- [ ] Test 1 scanner end-to-end
- [ ] Test batch minting (100 cards)
- [ ] Verify gas costs < $0.01/card

**During World Cup:**
- [ ] Monitor scanner uptime
- [ ] Watch gas prices (adjust if needed)
- [ ] Track NFT mint count
- [ ] Monitor wallet balances (refund if low)

**After World Cup:**
- [ ] Query price oracle (getAveragePrice)
- [ ] Calculate grading accuracy (getGradingAccuracy)
- [ ] Claim shop rewards
- [ ] Generate investor pitch with on-chain proof

---

## API CALL SUMMARY

### Scanner → ZULTAN (Card ID)
```
POST http://192.168.1.152:8000/api/identify
Body: image file
Returns: card data
```

### Scanner → Polygon (NFT Mint)
```
Contract Function: mintCardScan()
Chain: Polygon Mainnet
Returns: token_id, tx_hash
Gas: ~250K (~$0.005 USD)
```

### Scanner → Cloudflare (Marketplace)
```
POST https://nexus-marketplace-api.kcaracozza.workers.dev/v1/listings
Body: card + NFT data
Returns: listing_id
```

---

## READY TO DEPLOY 🚀

Once contract is deployed, everything else is plug-and-play.
