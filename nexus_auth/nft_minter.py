"""
NEXUS Auth — Polygon NFT Minter
Mints an ERC-721 authentication certificate to Polygon.
Uses web3.py + existing NexusCardNFT contract (or deploys AuthNFT if needed).

Testnet:  Polygon Amoy  (chain 80002)
Mainnet:  Polygon PoS   (chain 137)

Setup:
  pip install web3 qrcode[pil]
  Set env vars: NEXUS_WALLET_ADDRESS, NEXUS_PRIVATE_KEY, NEXUS_CONTRACT_ADDRESS
"""

import os
import json
import hashlib
import logging
import qrcode
from io import BytesIO
from typing import Optional, Dict, Any

logger = logging.getLogger("NEXUS_NFT")

# ---------------------------------------------------------------------------
# Config — pull from env, never hardcode keys
# ---------------------------------------------------------------------------
WALLET_ADDRESS    = os.getenv("NEXUS_WALLET_ADDRESS", "")
PRIVATE_KEY       = os.getenv("NEXUS_PRIVATE_KEY", "")
CONTRACT_ADDRESS  = os.getenv("NEXUS_AUTH_CONTRACT", "")

# RPC endpoints
POLYGON_MAINNET   = "https://polygon-rpc.com"
POLYGON_AMOY      = "https://rpc-amoy.polygon.technology"

USE_TESTNET       = os.getenv("NEXUS_TESTNET", "true").lower() == "true"
RPC_URL           = POLYGON_AMOY if USE_TESTNET else POLYGON_MAINNET
CHAIN_ID          = 80002 if USE_TESTNET else 137
NETWORK_NAME      = "Polygon Amoy (Testnet)" if USE_TESTNET else "Polygon Mainnet"

# Minimal ERC-721 ABI — just what we need to mint
ERC721_MINT_ABI = [
    {
        "inputs": [
            {"name": "to",      "type": "address"},
            {"name": "tokenURI","type": "string"},
        ],
        "name": "safeMint",
        "outputs": [{"name": "tokenId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "from",    "type": "address"},
            {"indexed": True,  "name": "to",      "type": "address"},
            {"indexed": True,  "name": "tokenId", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]


def _get_web3():
    """Return a Web3 instance. Raises ImportError if web3 not installed."""
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        return w3
    except ImportError:
        raise ImportError("web3 not installed. Run: pip install web3")


def _build_token_uri(cert: Dict[str, Any]) -> str:
    """
    Build on-chain metadata URI.
    For production: upload JSON to IPFS and return ipfs:// URI.
    For now: returns a NEXUS verify URL with the cert hash embedded.
    """
    item_id   = cert.get("item_id", "UNKNOWN")
    auth_hash = cert.get("blockchain", {}).get("hash", "")
    return f"https://nexus.io/auth/{item_id}?hash={auth_hash[:16]}"


def mint_nft(cert: Dict[str, Any],
             recipient_address: Optional[str] = None) -> Dict[str, Any]:
    """
    Mint an authentication NFT to Polygon.

    Args:
        cert:               Certificate dict from auth_engine.generate_certificate()
        recipient_address:  Fan's wallet address. If None, mints to NEXUS operator wallet.

    Returns:
        dict with tx_hash, token_id, network, opensea_url
    """
    result = {
        "success":      False,
        "tx_hash":      None,
        "token_id":     None,
        "network":      NETWORK_NAME,
        "opensea_url":  None,
        "error":        None,
    }

    if not WALLET_ADDRESS or not PRIVATE_KEY:
        result["error"] = "NEXUS_WALLET_ADDRESS / NEXUS_PRIVATE_KEY not set"
        logger.error(result["error"])
        return result

    if not CONTRACT_ADDRESS:
        result["error"] = "NEXUS_AUTH_CONTRACT address not set"
        logger.error(result["error"])
        return result

    try:
        from web3 import Web3

        w3   = _get_web3()
        to   = recipient_address or WALLET_ADDRESS
        uri  = _build_token_uri(cert)

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=ERC721_MINT_ABI,
        )

        nonce = w3.eth.get_transaction_count(
            Web3.to_checksum_address(WALLET_ADDRESS)
        )

        tx = contract.functions.safeMint(
            Web3.to_checksum_address(to), uri
        ).build_transaction({
            "chainId":  CHAIN_ID,
            "gas":      200_000,
            "gasPrice": w3.to_wei("30", "gwei"),
            "nonce":    nonce,
        })

        signed  = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        # Extract token ID from Transfer event
        token_id = None
        try:
            logs = contract.events.Transfer().process_receipt(receipt)
            if logs:
                token_id = logs[0]["args"]["tokenId"]
        except Exception:
            pass

        result["success"]  = receipt.status == 1
        result["tx_hash"]  = tx_hash.hex()
        result["token_id"] = token_id
        result["opensea_url"] = (
            f"https://opensea.io/assets/matic/{CONTRACT_ADDRESS}/{token_id}"
            if token_id and not USE_TESTNET else None
        )

        logger.info(f"NFT minted: tx={result['tx_hash'][:16]}... token={token_id}")
        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Mint failed: {e}")
        return result


# ---------------------------------------------------------------------------
# QR code generation — displayed on screen for fan to scan
# ---------------------------------------------------------------------------

def generate_qr(cert: Dict[str, Any],
                nft_result: Optional[Dict] = None,
                size: int = 300) -> Optional[bytes]:
    """
    Generate a QR code PNG (bytes) pointing to the auth certificate.
    Fan scans this with their phone to claim or view their NFT cert.
    """
    try:
        item_id   = cert.get("item_id", "UNKNOWN")
        auth_hash = cert.get("blockchain", {}).get("hash", "")
        tx_hash   = (nft_result or {}).get("tx_hash", "")
        token_id  = (nft_result or {}).get("token_id", "")

        # OpenSea link if minted, else fallback verify URL
        if token_id and not USE_TESTNET:
            url = f"https://opensea.io/assets/matic/{CONTRACT_ADDRESS}/{token_id}"
        else:
            url = f"https://nexus.io/auth/{item_id}?hash={auth_hash[:16]}"

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except ImportError:
        logger.warning("qrcode not installed. Run: pip install qrcode[pil]")
        return None
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        return None


# ---------------------------------------------------------------------------
# Simulated mint (no web3 / no wallet — for offline venue demo)
# ---------------------------------------------------------------------------

def simulate_mint(cert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fake mint for demo / offline mode.
    Generates a plausible-looking tx hash from the cert hash.
    """
    auth_hash = cert.get("blockchain", {}).get("hash", "demo")
    fake_tx   = "0x" + hashlib.sha256((auth_hash + "polygon").encode()).hexdigest()
    fake_id   = int(auth_hash[:8], 16) % 100_000

    return {
        "success":      True,
        "tx_hash":      fake_tx,
        "token_id":     fake_id,
        "network":      f"{NETWORK_NAME} [DEMO]",
        "opensea_url":  None,
        "error":        None,
        "simulated":    True,
    }


def mint_or_simulate(cert: Dict[str, Any],
                     recipient_address: Optional[str] = None,
                     force_simulate: bool = False) -> Dict[str, Any]:
    """
    Try real mint; fall back to simulation if web3 unavailable or config missing.
    UI calls this — doesn't need to know which path ran.
    """
    if force_simulate or not WALLET_ADDRESS or not PRIVATE_KEY or not CONTRACT_ADDRESS:
        logger.info("Simulation mode — no wallet/contract configured")
        return simulate_mint(cert)

    try:
        return mint_nft(cert, recipient_address)
    except ImportError:
        logger.warning("web3 not installed — falling back to simulation")
        return simulate_mint(cert)
    except Exception as e:
        logger.warning(f"Mint failed, simulating: {e}")
        return simulate_mint(cert)
