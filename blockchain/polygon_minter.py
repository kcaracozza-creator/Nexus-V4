#!/usr/bin/env python3
"""
NEXUS Polygon NFT Minter - PRODUCTION READY
Integrates with CardNFT.sol contract
Patent Pending - Kevin Caracozza
"""

import os
import json
import time
from datetime import datetime
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from pathlib import Path
from typing import Dict, Any, Optional, List

# Polygon Amoy Testnet (Mumbai is deprecated)
POLYGON_TESTNET_RPC = "https://rpc-amoy.polygon.technology"

# Polygon Mainnet
POLYGON_MAINNET_RPC = "https://polygon-rpc.com"

# TCG Type codes (matches contract)
TCG_TYPES = {
    'MTG': 1,
    'Pokemon': 2,
    'Sports': 3
}

# Condition codes (matches contract)
CONDITIONS = {
    'Mint': 1,
    'NM': 2,
    'LP': 3,
    'MP': 4,
    'HP': 5,
    'Damaged': 6
}

class PolygonMinter:
    """Mint NEXUS card NFTs on Polygon - Production Ready"""

    def __init__(self, contract_address: str, private_key: str, testnet: bool = True):
        self.testnet = testnet
        rpc_url = POLYGON_TESTNET_RPC if testnet else POLYGON_MAINNET_RPC

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Add PoA middleware for Polygon
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Polygon RPC: {rpc_url}")

        self.contract_address = Web3.to_checksum_address(contract_address)
        self.private_key = private_key
        self.account = self.w3.eth.account.from_key(private_key)

        # Load contract ABI from Hardhat artifact
        artifact_path = Path(__file__).parent / "artifacts" / "contracts" / "NexusCardNFT.sol" / "NexusCardNFT.json"
        legacy_abi_path = Path(__file__).parent.parent / "contracts" / "CardNFT_ABI.json"

        if artifact_path.exists():
            with open(artifact_path, 'r') as f:
                contract_data = json.load(f)
                abi = contract_data['abi']
        elif legacy_abi_path.exists():
            with open(legacy_abi_path, 'r') as f:
                contract_data = json.load(f)
                abi = contract_data.get('abi', contract_data)
        else:
            # Inline ABI for critical functions (if ABI file missing)
            abi = self._get_inline_abi()

        self.contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=abi
        )

        print(f"✓ Connected to Polygon {'Testnet (Mumbai)' if testnet else 'Mainnet'}")
        print(f"  Contract: {self.contract_address}")
        print(f"  Account: {self.account.address}")
        balance = self.w3.eth.get_balance(self.account.address)
        print(f"  Balance: {self.w3.from_wei(balance, 'ether'):.4f} MATIC")

    def _get_inline_abi(self):
        """Minimal ABI for critical functions if ABI file is missing"""
        return [
            {
                "inputs": [
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "string", "name": "cardId", "type": "string"},
                    {"internalType": "uint8", "name": "tcgType", "type": "uint8"},
                    {"internalType": "string", "name": "setCode", "type": "string"},
                    {"internalType": "string", "name": "cardName", "type": "string"},
                    {"internalType": "uint8", "name": "condition", "type": "uint8"},
                    {"internalType": "uint256", "name": "marketPrice", "type": "uint256"},
                    {"internalType": "uint256", "name": "scannerId", "type": "uint256"},
                    {"internalType": "string", "name": "scanLocation", "type": "string"},
                    {"internalType": "bool", "name": "isGraded", "type": "bool"},
                    {"internalType": "uint16", "name": "gradeValue", "type": "uint16"},
                    {"internalType": "string", "name": "metadataURI", "type": "string"}
                ],
                "name": "mintCardScan",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address[]", "name": "recipients", "type": "address[]"},
                    {"internalType": "string[]", "name": "cardIds", "type": "string[]"},
                    {"internalType": "uint8[]", "name": "tcgTypes", "type": "uint8[]"},
                    {"internalType": "uint256[]", "name": "marketPrices", "type": "uint256[]"},
                    {"internalType": "uint8[]", "name": "conditions", "type": "uint8[]"},
                    {"internalType": "uint256", "name": "scannerId", "type": "uint256"},
                    {"internalType": "string[]", "name": "metadataURIs", "type": "string[]"}
                ],
                "name": "batchMintCardScans",
                "outputs": [{"internalType": "uint256[]", "name": "", "type": "uint256[]"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "bytes32", "name": "cardIdHash", "type": "bytes32"}],
                "name": "getCardPriceHistory",
                "outputs": [
                    {
                        "components": [
                            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                            {"internalType": "uint256", "name": "avgPrice", "type": "uint256"},
                            {"internalType": "uint256", "name": "minPrice", "type": "uint256"},
                            {"internalType": "uint256", "name": "maxPrice", "type": "uint256"},
                            {"internalType": "uint256", "name": "sampleCount", "type": "uint256"}
                        ],
                        "internalType": "struct NexusCardNFT.PriceSnapshot[]",
                        "name": "",
                        "type": "tuple[]"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "cardIdHash", "type": "bytes32"},
                    {"internalType": "uint256", "name": "daysBack", "type": "uint256"}
                ],
                "name": "getAveragePrice",
                "outputs": [
                    {"internalType": "uint256", "name": "avgPrice", "type": "uint256"},
                    {"internalType": "uint256", "name": "totalSamples", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "uint256", "name": "scannerId", "type": "uint256"}],
                "name": "authorizeScanner",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "minter", "type": "address"}],
                "name": "authorizeMinter",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

    def mint_card_scan(
        self,
        recipient: str,
        card_id: str,
        tcg_type: str,
        set_code: str,
        card_name: str,
        condition: str,
        market_price_cents: int,
        scanner_id: int,
        scan_location: str,
        is_graded: bool = False,
        grade_value: int = 0,
        metadata_uri: str = ""
    ) -> Dict[str, Any]:
        """
        Mint single card NFT

        Args:
            recipient: Wallet address to receive NFT
            card_id: Unique card ID (e.g., "mtg-123456")
            tcg_type: TCG type ("MTG", "Pokemon", "Sports")
            set_code: Card set code
            card_name: Card name
            condition: Condition ("NM", "LP", "MP", "HP", etc.)
            market_price_cents: Price in USD cents
            scanner_id: Scanner station ID
            scan_location: Location string
            is_graded: Whether card is graded
            grade_value: Grade number (1-10)
            metadata_uri: IPFS/Arweave URI

        Returns:
            Transaction receipt and token ID
        """

        recipient = Web3.to_checksum_address(recipient)
        tcg_code = TCG_TYPES.get(tcg_type, 1)
        condition_code = CONDITIONS.get(condition, 2)

        # Build transaction
        tx = self.contract.functions.mintCardScan(
            recipient,
            card_id,
            tcg_code,
            set_code,
            card_name,
            condition_code,
            market_price_cents,
            scanner_id,
            scan_location,
            is_graded,
            grade_value,
            metadata_uri
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price
        })

        # Sign and send
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"  Minting NFT... tx: {tx_hash.hex()}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt['status'] == 1:
            # Extract token ID from logs
            token_id = None
            for log in receipt['logs']:
                try:
                    event = self.contract.events.CardScanned().process_log(log)
                    token_id = event['args']['tokenId']
                    break
                except:
                    continue

            print(f"  ✓ Minted NFT #{token_id}")

            return {
                'success': True,
                'token_id': token_id,
                'tx_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber'],
                'timestamp': int(time.time()),
                'gas_used': receipt['gasUsed']
            }
        else:
            return {
                'success': False,
                'error': 'Transaction failed',
                'tx_hash': tx_hash.hex()
            }

    def batch_mint_cards(
        self,
        recipients: List[str],
        card_ids: List[str],
        tcg_types: List[str],
        market_prices_cents: List[int],
        conditions: List[str],
        scanner_id: int,
        metadata_uris: List[str],
        set_codes: Optional[List[str]] = None,
        card_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Batch mint multiple cards (up to 100)
        ~10K gas per card instead of 500K

        Args:
            recipients: Wallet addresses (one per card)
            card_ids: Card identifiers
            tcg_types: TCG types ("MTG", "Pokemon", "Sports")
            market_prices_cents: Prices in USD cents
            conditions: Condition codes ("NM", "LP", etc.)
            scanner_id: Scanner station ID (same for all)
            metadata_uris: IPFS URIs

        Returns:
            Transaction receipt with token IDs
        """

        assert len(recipients) == len(card_ids) == len(tcg_types) == len(market_prices_cents) == len(conditions) == len(metadata_uris)
        assert len(recipients) <= 100, "Max 100 cards per batch"

        # Convert to checksum addresses
        recipients = [Web3.to_checksum_address(r) for r in recipients]

        # Convert TCG types and conditions to codes
        tcg_codes = [TCG_TYPES.get(t, 1) for t in tcg_types]
        condition_codes = [CONDITIONS.get(c, 2) for c in conditions]

        print(f"  Batch minting {len(recipients)} cards...")

        # Build transaction
        tx = self.contract.functions.batchMintCardScans(
            recipients,
            card_ids,
            tcg_codes,
            market_prices_cents,
            condition_codes,
            scanner_id,
            metadata_uris
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 2000000,  # Higher for batch
            'gasPrice': self.w3.eth.gas_price
        })

        # Sign and send
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"  Tx: {tx_hash.hex()}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt['status'] == 1:
            # Extract token IDs from logs
            token_ids = []
            for log in receipt['logs']:
                try:
                    event = self.contract.events.BatchCardsMinted().process_log(log)
                    first_id = event['args']['firstTokenId']
                    count = event['args']['count']
                    token_ids = list(range(first_id, first_id + count))
                    break
                except:
                    continue

            gas_per_card = receipt['gasUsed'] / len(recipients)
            print(f"  ✓ Batch complete! {len(recipients)} cards minted")
            print(f"  Gas per card: ~{gas_per_card:.0f} (~${gas_per_card * 2 / 1e9:.4f} USD)")

            return {
                'success': True,
                'token_ids': token_ids,
                'count': len(recipients),
                'tx_hash': tx_hash.hex(),
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed'],
                'gas_per_card': gas_per_card
            }
        else:
            return {
                'success': False,
                'error': 'Batch mint failed',
                'tx_hash': tx_hash.hex()
            }

    def get_price_history(self, card_id: str) -> Dict[str, Any]:
        """
        Query on-chain price history (uses snapshots)
        This is the PRICE ORACLE function
        """
        # Hash card ID to bytes32
        card_id_hash = Web3.keccak(text=card_id)

        # Query snapshots
        snapshots = self.contract.functions.getCardPriceHistory(card_id_hash).call()

        history = []
        for snap in snapshots:
            history.append({
                'timestamp': snap[0],
                'date': datetime.fromtimestamp(snap[0]).isoformat(),
                'avg_price_cents': snap[1],
                'avg_price_usd': snap[1] / 100.0,
                'min_price_cents': snap[2],
                'min_price_usd': snap[2] / 100.0,
                'max_price_cents': snap[3],
                'max_price_usd': snap[3] / 100.0,
                'sample_count': snap[4]
            })

        return {
            'card_id': card_id,
            'snapshot_count': len(history),
            'snapshots': history,
            'data_source': 'on-chain (irrefutable)'
        }

    def get_average_price(self, card_id: str, days_back: int = 90) -> Dict[str, Any]:
        """
        Get average market price from on-chain data
        Patent claim: After 90 days, NEXUS owns the irrefutable pricing data
        """
        card_id_hash = Web3.keccak(text=card_id)

        avg_price_cents, sample_size = self.contract.functions.getAveragePrice(
            card_id_hash,
            days_back
        ).call()

        return {
            'card_id': card_id,
            'days_back': days_back,
            'avg_price_cents': avg_price_cents,
            'avg_price_usd': avg_price_cents / 100.0 if avg_price_cents > 0 else 0,
            'sample_size': sample_size,
            'data_source': 'on-chain (irrefutable)'
        }

    def authorize_scanner(self, scanner_id: int) -> Dict[str, Any]:
        """Authorize a new scanner station"""
        tx = self.contract.functions.authorizeScanner(scanner_id).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price
        })

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            'success': receipt['status'] == 1,
            'scanner_id': scanner_id,
            'tx_hash': tx_hash.hex()
        }

    def authorize_minter(self, minter_address: str) -> Dict[str, Any]:
        """Authorize delegated minter (shop's BROCK instance)"""
        minter_address = Web3.to_checksum_address(minter_address)

        tx = self.contract.functions.authorizeMinter(minter_address).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 100000,
            'gasPrice': self.w3.eth.gas_price
        })

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            'success': receipt['status'] == 1,
            'minter_address': minter_address,
            'tx_hash': tx_hash.hex()
        }


# =============================================================================
# SCANNER INTEGRATION HELPERS
# =============================================================================

def mint_from_scanner_result(
    minter: PolygonMinter,
    scan_result: Dict[str, Any],
    recipient_wallet: str,
    scanner_id: int,
    scan_location: str
) -> Dict[str, Any]:
    """
    Helper function to mint NFT from NEXUS scanner result

    Args:
        minter: Polygon minter instance
        scan_result: Result from universal_card_router.py
        recipient_wallet: User's wallet address
        scanner_id: Scanner station ID
        scan_location: Location string
    """

    card_id = scan_result.get('card_id', scan_result.get('id', ''))
    tcg_type = scan_result.get('tcg', 'MTG')
    card_name = scan_result.get('name', 'Unknown Card')
    set_code = scan_result.get('set_code', scan_result.get('set', ''))

    # Get market price (convert to cents)
    market_price = scan_result.get('market_price', scan_result.get('price', 0))
    if isinstance(market_price, str):
        market_price = float(market_price.replace('$', '').replace(',', ''))
    market_price_cents = int(market_price * 100)

    # Condition and grading
    condition = scan_result.get('condition', 'NM')
    is_graded = scan_result.get('is_graded', False)
    grade_value = scan_result.get('grade', 0)

    # Metadata URI
    metadata_uri = scan_result.get('metadata_uri', f"ipfs://nexus/{card_id}")

    return minter.mint_card_scan(
        recipient=recipient_wallet,
        card_id=card_id,
        tcg_type=tcg_type,
        set_code=set_code,
        card_name=card_name,
        condition=condition,
        market_price_cents=market_price_cents,
        scanner_id=scanner_id,
        scan_location=scan_location,
        is_graded=is_graded,
        grade_value=grade_value,
        metadata_uri=metadata_uri
    )


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == '__main__':
    import sys

    config_file = Path(__file__).parent / "polygon_config.json"
    if not config_file.exists():
        print("Create polygon_config.json with:")
        print(json.dumps({
            "contract_address": "0x...",
            "private_key": "0x...",
            "testnet": True
        }, indent=2))
        sys.exit(1)

    with open(config_file, 'r') as f:
        config = json.load(f)

    minter = PolygonMinter(
        contract_address=config['contract_address'],
        private_key=config['private_key'],
        testnet=config.get('testnet', True)
    )

    print("\nReady to deploy to World Cup! 🎖️")
