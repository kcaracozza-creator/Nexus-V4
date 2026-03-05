#!/usr/bin/env python3
"""
NEXUS Scanner with Blockchain Integration
Auto-mints NFT on Polygon for every scanned card

Patent Pending - Kevin Caracozza
"""

import os
import sys
import json
from pathlib import Path

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from blockchain.polygon_minter import PolygonMinter, mint_from_scanner_result
from nexus_v2.scanner.universal_card_router import identify_card


class BlockchainScanner:
    """Scanner with automatic NFT minting"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "blockchain" / "polygon_config.json"

        # Load blockchain config
        with open(config_path, 'r') as f:
            config = json.load(f)

        self.minter = PolygonMinter(
            contract_address=config['contract_address'],
            private_key=config['private_key'],
            testnet=config.get('testnet', False)
        )

        self.scanner_id = config.get('scanner_id', 1)
        self.scan_location = config.get('scan_location', 'NEXUS Station')
        self.default_wallet = config.get('default_wallet')  # Optional: custody wallets for users

        print(f"✓ Blockchain Scanner Ready")
        print(f"  Scanner ID: {self.scanner_id}")
        print(f"  Location: {self.scan_location}")
        print(f"  Network: {'Testnet' if config.get('testnet') else 'Mainnet'}")

    def scan_and_mint(self, image_path: str, recipient_wallet: str = None) -> dict:
        """
        Scan card and mint NFT in one step

        Args:
            image_path: Path to card image
            recipient_wallet: User's wallet address (or None to use custody wallet)

        Returns:
            Dict with scan result + NFT data
        """

        print(f"\n[Blockchain Scan] Processing {image_path}...")

        # Step 1: Identify card using NEXUS AI
        print("  1/2 Identifying card...")
        scan_result = identify_card(image_path)

        if not scan_result or 'error' in scan_result:
            return {
                'success': False,
                'error': 'Card identification failed',
                'details': scan_result
            }

        card_name = scan_result.get('name', 'Unknown')
        tcg = scan_result.get('tcg', 'Unknown')
        confidence = scan_result.get('confidence', 0)

        print(f"      ✓ {card_name} ({tcg}) - {confidence:.1f}% confidence")

        # Step 2: Mint NFT on Polygon
        print("  2/2 Minting NFT on Polygon...")

        wallet = recipient_wallet or self.default_wallet
        if not wallet:
            return {
                'success': False,
                'error': 'No wallet specified and no default custody wallet configured'
            }

        try:
            nft_result = mint_from_scanner_result(
                minter=self.minter,
                scan_result=scan_result,
                recipient_wallet=wallet,
                scanner_id=self.scanner_id,
                scan_location=self.scan_location
            )

            if nft_result['success']:
                print(f"      ✓ NFT #{nft_result['token_id']} minted")
                print(f"      TX: {nft_result['tx_hash']}")

                return {
                    'success': True,
                    'card': scan_result,
                    'nft': nft_result,
                    'message': f"Scanned {card_name} and minted NFT #{nft_result['token_id']}"
                }
            else:
                return {
                    'success': False,
                    'card': scan_result,
                    'error': 'NFT minting failed',
                    'details': nft_result
                }

        except Exception as e:
            return {
                'success': False,
                'card': scan_result,
                'error': f'Blockchain error: {str(e)}'
            }

    def get_card_history(self, card_id: str, days_back: int = 90) -> dict:
        """Query price history from blockchain (the price oracle)"""
        return self.minter.get_price_history(card_id, days_back)

    def get_average_price(self, card_id: str, days_back: int = 90) -> dict:
        """Get average market price (irrefutable on-chain data)"""
        return self.minter.get_average_price(card_id, days_back)


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='NEXUS Blockchain Scanner')
    parser.add_argument('image', help='Path to card image')
    parser.add_argument('--wallet', help='Recipient wallet address')
    parser.add_argument('--config', help='Path to polygon_config.json')

    args = parser.parse_args()

    scanner = BlockchainScanner(config_path=args.config)
    result = scanner.scan_and_mint(args.image, args.wallet)

    if result['success']:
        print(f"\n✓ SUCCESS!")
        print(f"  Card: {result['card']['name']}")
        print(f"  NFT: #{result['nft']['token_id']}")
        print(f"  TX: {result['nft']['tx_hash']}")
    else:
        print(f"\n✗ FAILED: {result['error']}")
        sys.exit(1)


if __name__ == '__main__':
    main()
