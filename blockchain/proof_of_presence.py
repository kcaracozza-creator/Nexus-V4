#!/usr/bin/env python3
"""
NEXUS Proof of Presence (PoP) - Blockchain Validation Module

Patent Pending - Kevin Caracozza
Filed: System and Method for Real-Time On-Site Collectible Validation
Using Optical Fingerprinting and Distributed Ledger Technology

Flow:
  1. Capture high-res image (Optical DNA)
  2. SHA-256 hash the image (cryptographic fingerprint)
  3. Identify item via NEXUS AI (optional - works without ID too)
  4. Mint immutable record on Polygon blockchain
  5. Generate verifiable digital receipt

The image hash is stored on-chain as the metadataURI, making it
permanently verifiable. Any future scan of the same item can be
compared against this hash.
"""

import hashlib
import json
import math
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from web3 import Web3

logger = logging.getLogger(__name__)

# =============================================================================
# MINT GATE — schema compliance hold
# =============================================================================
# Set to True only after cert schema has been verified clean end-to-end.
# Tokens #1-4 were pre-compliance development tests; see MINT_COMPLIANCE_LOG.md.
# Do not re-enable without reviewing blockchain/MINT_COMPLIANCE_LOG.md.
MINTING_ENABLED = False

# Polygon Mainnet RPCs (fallback chain for receipt polling)
POLYGON_RPCS = [
    "https://polygon-rpc.com",
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
]
POLYGONSCAN_TX = "https://polygonscan.com/tx/"
POLYGONSCAN_TOKEN = "https://polygonscan.com/token/"


class ProofOfPresence:
    """
    On-site collectible validation via optical fingerprinting + blockchain.

    Each validation creates an immutable Proof of Presence record:
    - WHO: Scanner station ID + operator wallet
    - WHAT: Item identity (AI recognition) + optical fingerprint (SHA-256)
    - WHEN: Block timestamp (immutable)
    - WHERE: Scanner location + blockchain address
    """

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent / "polygon_config.json"

        with open(config_path, 'r') as f:
            config = json.load(f)

        self.contract_address = config['contract_address']
        self.private_key = config['private_key']
        self.scanner_id = config.get('scanner_id', 1)
        self.scan_location = config.get('scan_location', 'NEXUS Station')

        # Geofence configuration
        gps = config.get('scanner_gps', {})
        self.scanner_lat = gps.get('lat')
        self.scanner_lng = gps.get('lng')
        self.geofence_enabled = config.get('geofence_enabled', False)
        self.geofence_zones = config.get('geofence_zones', [])

        # Resolve scan_location from GPS if within a known zone
        if self.scanner_lat and self.scanner_lng and self.geofence_zones:
            zone = self._get_current_zone()
            if zone:
                self.scan_location = zone['name']
                self.active_zone = zone
            else:
                self.active_zone = None
                if self.geofence_enabled:
                    raise ValueError(
                        f"Scanner GPS ({self.scanner_lat}, {self.scanner_lng}) "
                        f"is outside all authorized geofence zones. "
                        f"Validation blocked."
                    )
        else:
            self.active_zone = None

        if not self.contract_address:
            raise ValueError("Contract not deployed - run deploy_contract.py first")

        # Connect to Polygon (try multiple RPCs)
        self.w3 = None
        for rpc in POLYGON_RPCS:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 30}))
                if w3.is_connected():
                    self.w3 = w3
                    logger.info(f"Connected to {rpc}")
                    break
            except Exception:
                continue
        if self.w3 is None:
            raise ConnectionError("Cannot connect to any Polygon RPC")

        self.account = self.w3.eth.account.from_key(self.private_key)

        # Load contract
        artifact_path = Path(__file__).parent / "artifacts" / "contracts" / "NexusCardNFT.sol" / "NexusCardNFT.json"
        with open(artifact_path, 'r') as f:
            artifact = json.load(f)

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=artifact['abi']
        )

        balance = self.w3.eth.get_balance(self.account.address)
        self.balance_pol = float(self.w3.from_wei(balance, 'ether'))

        logger.info(f"PoP initialized: contract={self.contract_address[:10]}..., balance={self.balance_pol:.4f} POL")

    # =========================================================================
    # GEOFENCE
    # =========================================================================

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Distance in meters between two GPS coordinates (Haversine formula)."""
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lng2 - lng1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _get_current_zone(self) -> Optional[Dict]:
        """Check if scanner GPS is inside any authorized geofence zone."""
        if not self.scanner_lat or not self.scanner_lng:
            return None
        for zone in self.geofence_zones:
            dist = self._haversine(
                self.scanner_lat, self.scanner_lng,
                zone['lat'], zone['lng']
            )
            if dist <= zone.get('radius_m', 500):
                return zone
        return None

    def is_in_geofence(self) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Check if scanner is within an authorized zone.
        Returns (in_zone, zone_name, distance_meters)
        """
        if not self.scanner_lat or not self.scanner_lng:
            return (True, self.scan_location, 0)  # No GPS = allow (not enforced)
        zone = self._get_current_zone()
        if zone:
            dist = self._haversine(
                self.scanner_lat, self.scanner_lng,
                zone['lat'], zone['lng']
            )
            return (True, zone['name'], dist)
        # Find nearest zone for error reporting
        nearest_name = "Unknown"
        nearest_dist = float('inf')
        for z in self.geofence_zones:
            d = self._haversine(self.scanner_lat, self.scanner_lng, z['lat'], z['lng'])
            if d < nearest_dist:
                nearest_dist = d
                nearest_name = z['name']
        return (False, nearest_name, nearest_dist)

    def get_location_string(self) -> str:
        """Build location string for on-chain storage. Includes GPS coordinates."""
        parts = [self.scan_location]
        if self.scanner_lat and self.scanner_lng:
            parts.append(f"GPS:{self.scanner_lat:.6f},{self.scanner_lng:.6f}")
        return " | ".join(parts)

    # =========================================================================
    # BARCODE SCANNING
    # =========================================================================

    def scan_barcode(self, image_path: str) -> Optional[Dict[str, str]]:
        """
        Scan image for barcodes (UPC, EAN, QR, Code128, etc).
        Returns dict with barcode data + type, or None if no barcode found.
        For sealed products, the UPC/EAN becomes the on-chain item identity.
        """
        try:
            from pyzbar.pyzbar import decode as decode_barcodes
            from PIL import Image

            img = Image.open(image_path)
            barcodes = decode_barcodes(img)

            if not barcodes:
                logger.info("No barcode detected in image")
                return None

            # Take the first barcode found
            bc = barcodes[0]
            barcode_data = bc.data.decode('utf-8')
            barcode_type = bc.type  # EAN13, UPCA, QRCODE, CODE128, etc.

            logger.info(f"Barcode found: {barcode_type} = {barcode_data}")

            result = {
                'data': barcode_data,
                'type': barcode_type,
                'count': len(barcodes),
            }

            # If multiple barcodes, include all
            if len(barcodes) > 1:
                result['all'] = [
                    {'data': b.data.decode('utf-8'), 'type': b.type}
                    for b in barcodes
                ]

            return result

        except ImportError:
            logger.warning("pyzbar not installed - barcode scanning disabled")
            return None
        except Exception as e:
            logger.warning(f"Barcode scan error: {e}")
            return None

    # =========================================================================
    # OPTICAL FINGERPRINT
    # =========================================================================

    def hash_image(self, image_path: str) -> str:
        """
        Generate SHA-256 hash of image file (Optical DNA fingerprint).
        This is the cryptographic proof that ties a specific physical
        item's appearance to a specific moment in time.
        """
        h = hashlib.sha256()
        with open(image_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def hash_image_bytes(self, image_bytes: bytes) -> str:
        """Hash image from bytes (for streaming captures)."""
        return hashlib.sha256(image_bytes).hexdigest()

    def validate(
        self,
        image_path: str,
        card_id: str = None,
        card_name: str = None,
        tcg_type: str = None,
        condition: str = "NM",
        market_price_cents: int = 100,
        is_graded: bool = False,
        grade_value: int = 0
    ) -> Dict[str, Any]:
        """
        Execute full Proof of Presence validation.

        Args:
            image_path: Path to captured image (Optical DNA source)
            card_id: Item identifier (from AI recognition, or barcode)
            card_name: Item name (optional, for receipt)
            tcg_type: "MTG", "Pokemon", "Sports" (default "Sports")
            condition: "NM", "LP", "MP", "HP"
            market_price_cents: Price in USD cents (minimum 1)
            is_graded: Whether item has PSA/BGS grade
            grade_value: Grade number (1-10)

        Returns:
            Dict with validation result, tx hash, receipt data
        """
        if not MINTING_ENABLED:
            return {
                'success': False,
                'error': (
                    'MINTING_ENABLED=False — schema compliance hold active. '
                    'See blockchain/MINT_COMPLIANCE_LOG.md before re-enabling.'
                ),
                'timestamp': datetime.now().isoformat(),
            }

        start_time = time.time()
        result = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'scanner_id': self.scanner_id,
            'location': self.scan_location,
            'gps': f"{self.scanner_lat},{self.scanner_lng}" if self.scanner_lat else None
        }

        try:
            # Step 0: Geofence check
            if self.geofence_enabled:
                in_zone, zone_name, dist = self.is_in_geofence()
                if not in_zone:
                    result['error'] = (
                        f"GEOFENCE VIOLATION: Scanner is {dist:.0f}m outside "
                        f"nearest zone '{zone_name}'. Validation blocked."
                    )
                    logger.error(result['error'])
                    return result
                logger.info(f"Geofence OK: {zone_name} ({dist:.0f}m from center)")
                result['geofence_zone'] = zone_name

            # Step 1: Generate optical fingerprint
            logger.info("Step 1: Generating optical fingerprint (SHA-256)...")
            image_hash = self.hash_image(image_path)
            result['image_hash'] = image_hash
            result['image_path'] = str(image_path)
            logger.info(f"  Hash: {image_hash[:16]}...")

            # Step 1.5: Scan for barcodes (sealed products)
            barcode = self.scan_barcode(image_path)
            if barcode:
                result['barcode'] = barcode['data']
                result['barcode_type'] = barcode['type']
                # Barcode becomes the item identity if no card_id provided
                if not card_id:
                    card_id = f"upc:{barcode['data']}"
                if not card_name:
                    card_name = f"Sealed Product {barcode['data']}"

            # Step 2: Prepare item identity
            if not card_id:
                card_id = f"pop-{image_hash[:16]}"
            if not card_name:
                card_name = f"Validated Item {image_hash[:8]}"
            if not tcg_type:
                tcg_type = "Sports"

            # TCG type code
            tcg_codes = {'MTG': 1, 'Pokemon': 2, 'Sports': 3}
            tcg_code = tcg_codes.get(tcg_type, 3)

            # Condition code
            cond_codes = {'Mint': 1, 'NM': 2, 'LP': 3, 'MP': 4, 'HP': 5, 'Damaged': 6}
            cond_code = cond_codes.get(condition, 2)

            # Store the image hash as the metadataURI - this goes ON CHAIN
            metadata_uri = f"sha256:{image_hash}"

            result['card_id'] = card_id
            result['card_name'] = card_name
            result['tcg_type'] = tcg_type

            # Step 3: Mint on Polygon
            logger.info("Step 2: Minting Proof of Presence on Polygon...")

            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price

            tx = self.contract.functions.mintCardScan(
                self.account.address,   # to (self-mint for validation)
                card_id,                # cardId
                tcg_code,               # tcgType
                "",                     # setCode
                card_name,              # cardName
                cond_code,              # condition
                max(market_price_cents, 1),  # marketPrice (must be > 0)
                self.scanner_id,        # scannerId
                self.get_location_string(),  # scanLocation (includes GPS)
                is_graded,              # isGraded
                grade_value,            # gradeValue
                metadata_uri            # metadataURI = sha256 hash
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': 137
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"  TX sent: {tx_hash_hex[:16]}...")

            # Step 4: Wait for confirmation (retry across multiple RPCs)
            logger.info("Step 3: Waiting for blockchain confirmation...")
            receipt = None
            for attempt in range(20):
                time.sleep(4)
                # Try current RPC first, then fallbacks
                for rpc in POLYGON_RPCS:
                    try:
                        w3_check = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
                        receipt = w3_check.eth.get_transaction_receipt(tx_hash)
                        if receipt:
                            break
                    except Exception:
                        continue
                if receipt:
                    break

            if not receipt:
                result['error'] = 'Transaction timed out'
                result['tx_hash'] = tx_hash_hex
                result['polygonscan'] = f"{POLYGONSCAN_TX}0x{tx_hash_hex}"
                return result

            if receipt['status'] != 1:
                result['error'] = 'Transaction reverted'
                result['tx_hash'] = tx_hash_hex
                return result

            # Extract token ID from events
            token_id = None
            for log in receipt['logs']:
                try:
                    event = self.contract.events.CardScanned().process_log(log)
                    token_id = event['args']['tokenId']
                    break
                except Exception:
                    continue

            elapsed = time.time() - start_time
            gas_cost_pol = float(self.w3.from_wei(receipt['gasUsed'] * gas_price, 'ether'))

            # Build success result
            result['success'] = True
            result['token_id'] = token_id
            result['tx_hash'] = tx_hash_hex
            result['block_number'] = receipt['blockNumber']
            result['gas_used'] = receipt['gasUsed']
            result['gas_cost_pol'] = gas_cost_pol
            result['elapsed_seconds'] = round(elapsed, 1)
            result['polygonscan'] = f"{POLYGONSCAN_TX}0x{tx_hash_hex}"
            result['contract'] = self.contract_address

            logger.info(f"  VALIDATED! Token #{token_id}, {elapsed:.1f}s, cost {gas_cost_pol:.6f} POL")

            return result

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Validation failed: {e}")
            return result

    def get_receipt_text(self, result: Dict[str, Any]) -> str:
        """Generate human-readable validation receipt."""
        if not result.get('success'):
            return f"VALIDATION FAILED: {result.get('error', 'Unknown error')}"

        lines = [
            "=" * 50,
            "    NEXUS PROOF OF PRESENCE",
            "    Blockchain Validation Receipt",
            "=" * 50,
            "",
            f"  Item: {result.get('card_name', 'N/A')}",
            f"  Type: {result.get('tcg_type', 'N/A')}",
            f"  ID:   {result.get('card_id', 'N/A')}",
            "",
            f"  Optical Fingerprint (SHA-256):",
            f"  {result.get('image_hash', 'N/A')}",
            "",
            f"  Blockchain Record:",
            f"  Token:  #{result.get('token_id', 'N/A')}",
            f"  TX:     0x{result.get('tx_hash', 'N/A')[:16]}...",
            f"  Block:  {result.get('block_number', 'N/A')}",
            f"  Chain:  Polygon (137)",
            "",
            f"  Scanner: #{result.get('scanner_id', 'N/A')}",
            f"  Location: {result.get('location', 'N/A')}",
            f"  GPS:    {result.get('gps', 'N/A')}",
            f"  Zone:   {result.get('geofence_zone', 'N/A')}",
            f"  Time:   {result.get('timestamp', 'N/A')}",
            "",
            f"  Verify: {result.get('polygonscan', 'N/A')}",
            "",
            "  This record is immutable and publicly",
            "  verifiable on the Polygon blockchain.",
            "",
            "=" * 50,
            "  Patent Pending - NEXUS by Kevin Caracozza",
            "=" * 50,
        ]
        return "\n".join(lines)

    # =========================================================================
    # COLLECTOR TIER
    # =========================================================================

    def crop_detail(self, image_path: str, output_path: str = None) -> str:
        """
        Crop the center 50% of an image for detail-level Optical DNA.
        This simulates a macro pass - center region at full resolution.

        Returns path to the cropped image.
        """
        from PIL import Image

        img = Image.open(image_path)
        w, h = img.size

        # Center 50% crop
        crop_w, crop_h = w // 2, h // 2
        left = (w - crop_w) // 2
        top = (h - crop_h) // 2
        right = left + crop_w
        bottom = top + crop_h

        detail = img.crop((left, top, right, bottom))

        if output_path is None:
            p = Path(image_path)
            output_path = str(p.parent / f"{p.stem}_detail{p.suffix}")

        detail.save(output_path, quality=95)
        logger.info(f"Detail crop: {w}x{h} -> {crop_w}x{crop_h} saved to {output_path}")
        return output_path

    def validate_collector_tier(
        self,
        image_path: str,
        card_id: str = None,
        card_name: str = None,
        tcg_type: str = None,
        condition: str = "NM",
        market_price_cents: int = 100,
        is_graded: bool = False,
        grade_value: int = 0
    ) -> Dict[str, Any]:
        """
        Collector Tier validation - dual-hash forensic scan.

        1. Hash the full wide shot (identity fingerprint)
        2. Crop center 50% for detail hash (macro-level Optical DNA)
        3. Bundle both hashes into a single Polygon mint

        metadataURI format: "sha256-wide:<hash>|sha256-detail:<hash>"
        """
        if not MINTING_ENABLED:
            return {
                'success': False,
                'error': (
                    'MINTING_ENABLED=False — schema compliance hold active. '
                    'See blockchain/MINT_COMPLIANCE_LOG.md before re-enabling.'
                ),
                'timestamp': datetime.now().isoformat(),
            }

        start_time = time.time()
        result = {
            'success': False,
            'tier': 'COLLECTOR',
            'timestamp': datetime.now().isoformat(),
            'scanner_id': self.scanner_id,
            'location': self.scan_location,
            'gps': f"{self.scanner_lat},{self.scanner_lng}" if self.scanner_lat else None
        }

        try:
            # Step 0: Geofence check
            if self.geofence_enabled:
                in_zone, zone_name, dist = self.is_in_geofence()
                if not in_zone:
                    result['error'] = (
                        f"GEOFENCE VIOLATION: Scanner is {dist:.0f}m outside "
                        f"nearest zone '{zone_name}'. Validation blocked."
                    )
                    return result
                result['geofence_zone'] = zone_name

            # Step 1: Wide shot hash (identity fingerprint)
            logger.info("COLLECTOR TIER - Step 1: Wide shot hash...")
            wide_hash = self.hash_image(image_path)
            result['wide_hash'] = wide_hash
            result['image_path'] = str(image_path)
            logger.info(f"  Wide hash: {wide_hash[:16]}...")

            # Step 2: Detail crop + hash (macro-level Optical DNA)
            logger.info("COLLECTOR TIER - Step 2: Detail crop hash...")
            detail_path = self.crop_detail(image_path)
            detail_hash = self.hash_image(detail_path)
            result['detail_hash'] = detail_hash
            result['detail_path'] = detail_path
            logger.info(f"  Detail hash: {detail_hash[:16]}...")

            # Combined hash for backward compat
            result['image_hash'] = wide_hash

            # Step 2.5: Scan for barcodes (sealed products)
            barcode = self.scan_barcode(image_path)
            if barcode:
                result['barcode'] = barcode['data']
                result['barcode_type'] = barcode['type']
                if not card_id:
                    card_id = f"upc:{barcode['data']}"
                if not card_name:
                    card_name = f"Sealed Product {barcode['data']}"

            # Step 3: Prepare item identity
            if not card_id:
                card_id = f"pop-{wide_hash[:16]}"
            if not card_name:
                card_name = f"Validated Item {wide_hash[:8]}"
            if not tcg_type:
                tcg_type = "Sports"

            tcg_codes = {'MTG': 1, 'Pokemon': 2, 'Sports': 3}
            tcg_code = tcg_codes.get(tcg_type, 3)
            cond_codes = {'Mint': 1, 'NM': 2, 'LP': 3, 'MP': 4, 'HP': 5, 'Damaged': 6}
            cond_code = cond_codes.get(condition, 2)

            # Dual-hash metadataURI - BOTH hashes go ON CHAIN
            metadata_uri = f"sha256-wide:{wide_hash}|sha256-detail:{detail_hash}"

            result['card_id'] = card_id
            result['card_name'] = card_name
            result['tcg_type'] = tcg_type

            # Step 4: Mint on Polygon
            logger.info("COLLECTOR TIER - Step 3: Minting dual-hash on Polygon...")

            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price

            tx = self.contract.functions.mintCardScan(
                self.account.address,
                card_id,
                tcg_code,
                "",
                card_name,
                cond_code,
                max(market_price_cents, 1),
                self.scanner_id,
                self.get_location_string(),
                is_graded,
                grade_value,
                metadata_uri
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': 137
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"  TX sent: {tx_hash_hex[:16]}...")

            # Step 5: Wait for confirmation
            logger.info("COLLECTOR TIER - Step 4: Waiting for confirmation...")
            receipt = None
            for attempt in range(20):
                time.sleep(4)
                for rpc in POLYGON_RPCS:
                    try:
                        w3_check = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
                        receipt = w3_check.eth.get_transaction_receipt(tx_hash)
                        if receipt:
                            break
                    except Exception:
                        continue
                if receipt:
                    break

            if not receipt:
                result['error'] = 'Transaction timed out'
                result['tx_hash'] = tx_hash_hex
                result['polygonscan'] = f"{POLYGONSCAN_TX}0x{tx_hash_hex}"
                return result

            if receipt['status'] != 1:
                result['error'] = 'Transaction reverted'
                result['tx_hash'] = tx_hash_hex
                return result

            # Extract token ID
            token_id = None
            for log in receipt['logs']:
                try:
                    event = self.contract.events.CardScanned().process_log(log)
                    token_id = event['args']['tokenId']
                    break
                except Exception:
                    continue

            elapsed = time.time() - start_time
            gas_cost_pol = float(self.w3.from_wei(receipt['gasUsed'] * gas_price, 'ether'))

            result['success'] = True
            result['token_id'] = token_id
            result['tx_hash'] = tx_hash_hex
            result['block_number'] = receipt['blockNumber']
            result['gas_used'] = receipt['gasUsed']
            result['gas_cost_pol'] = gas_cost_pol
            result['elapsed_seconds'] = round(elapsed, 1)
            result['polygonscan'] = f"{POLYGONSCAN_TX}0x{tx_hash_hex}"
            result['contract'] = self.contract_address

            logger.info(f"  COLLECTOR VALIDATED! Token #{token_id}, {elapsed:.1f}s, cost {gas_cost_pol:.6f} POL")
            return result

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Collector validation failed: {e}")
            return result

    def get_receipt_text(self, result: Dict[str, Any]) -> str:
        """Generate human-readable validation receipt."""
        if not result.get('success'):
            return f"VALIDATION FAILED: {result.get('error', 'Unknown error')}"

        tier = result.get('tier', 'STANDARD')
        is_collector = tier == 'COLLECTOR'

        lines = [
            "=" * 50,
            "    NEXUS PROOF OF PRESENCE",
            f"    {'Collector Tier' if is_collector else 'Standard'} Validation Receipt",
            "=" * 50,
            "",
            f"  Item: {result.get('card_name', 'N/A')}",
            f"  Type: {result.get('tcg_type', 'N/A')}",
            f"  ID:   {result.get('card_id', 'N/A')}",
            f"  Tier: {tier}",
        ]

        if result.get('barcode'):
            lines += [
                f"  Barcode: {result['barcode']} ({result.get('barcode_type', 'N/A')})",
            ]

        lines += [""]

        if is_collector:
            lines += [
                f"  Wide Fingerprint (SHA-256):",
                f"  {result.get('wide_hash', 'N/A')}",
                "",
                f"  Detail Fingerprint (SHA-256):",
                f"  {result.get('detail_hash', 'N/A')}",
            ]
        else:
            lines += [
                f"  Optical Fingerprint (SHA-256):",
                f"  {result.get('image_hash', 'N/A')}",
            ]

        lines += [
            "",
            f"  Blockchain Record:",
            f"  Token:  #{result.get('token_id', 'N/A')}",
            f"  TX:     0x{result.get('tx_hash', 'N/A')[:16]}...",
            f"  Block:  {result.get('block_number', 'N/A')}",
            f"  Chain:  Polygon (137)",
            "",
            f"  Scanner: #{result.get('scanner_id', 'N/A')}",
            f"  Location: {result.get('location', 'N/A')}",
            f"  GPS:    {result.get('gps', 'N/A')}",
            f"  Zone:   {result.get('geofence_zone', 'N/A')}",
            f"  Time:   {result.get('timestamp', 'N/A')}",
            "",
            f"  Verify: {result.get('polygonscan', 'N/A')}",
            "",
            "  This record is immutable and publicly",
            "  verifiable on the Polygon blockchain.",
            "",
            "=" * 50,
            "  Patent Pending - NEXUS by Kevin Caracozza",
            "=" * 50,
        ]
        return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    import sys
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    parser = argparse.ArgumentParser(description='NEXUS Proof of Presence Validator')
    parser.add_argument('image', help='Path to item image')
    parser.add_argument('--name', help='Item name', default=None)
    parser.add_argument('--id', help='Item ID', default=None)
    parser.add_argument('--type', help='TCG type (MTG/Pokemon/Sports)', default='Sports')
    parser.add_argument('--config', help='Path to polygon_config.json', default=None)
    args = parser.parse_args()

    pop = ProofOfPresence(config_path=args.config)
    print(f"Balance: {pop.check_balance():.4f} POL")
    print()

    result = pop.validate(
        image_path=args.image,
        card_id=args.id,
        card_name=args.name,
        tcg_type=args.type
    )

    print()
    print(pop.get_receipt_text(result))

    if result['success']:
        sys.exit(0)
    else:
        sys.exit(1)
