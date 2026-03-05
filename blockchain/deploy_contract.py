#!/usr/bin/env python3
"""
Deploy NexusCardNFT to Polygon Mainnet via Python
No hardhat needed - uses compiled artifact directly
"""

import json
import time
import sys
from pathlib import Path
from web3 import Web3

# Polygon Mainnet
RPC_URL = "https://polygon-rpc.com"

def deploy():
    # Load config
    config_path = Path(__file__).parent / "polygon_config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)

    private_key = config['private_key']

    # Load compiled artifact
    artifact_path = Path(__file__).parent / "artifacts" / "contracts" / "NexusCardNFT.sol" / "NexusCardNFT.json"
    with open(artifact_path, 'r') as f:
        artifact = json.load(f)

    abi = artifact['abi']
    bytecode = artifact['bytecode']

    # Connect
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        print("Failed to connect to Polygon RPC")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    balance = w3.eth.get_balance(account.address)
    balance_pol = w3.from_wei(balance, 'ether')

    print(f"Deployer: {account.address}")
    print(f"Balance: {balance_pol:.4f} POL")
    print(f"Network: Polygon Mainnet (Chain ID 137)")
    print()

    if balance_pol < 0.1:
        print("ERROR: Need at least 0.1 POL to deploy")
        sys.exit(1)

    # Deploy contract
    print("Deploying NexusCardNFT...")
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Get current gas price
    gas_price = w3.eth.gas_price
    print(f"Gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei")

    # Build deploy transaction
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.constructor().build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 6000000,  # High limit for contract deployment
        'gasPrice': gas_price,
        'chainId': 137
    })

    # Sign and send
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Deploy TX: {tx_hash.hex()}")
    print("Waiting for confirmation...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

    if receipt['status'] != 1:
        print("DEPLOYMENT FAILED!")
        sys.exit(1)

    contract_address = receipt['contractAddress']
    print(f"\nContract deployed: {contract_address}")
    print(f"Block: {receipt['blockNumber']}")
    print(f"Gas used: {receipt['gasUsed']}")
    gas_cost_pol = w3.from_wei(receipt['gasUsed'] * gas_price, 'ether')
    print(f"Cost: {gas_cost_pol:.6f} POL")

    # Authorize scanner #1
    print("\nAuthorizing scanner #1...")
    deployed_contract = w3.eth.contract(address=contract_address, abi=abi)

    nonce = w3.eth.get_transaction_count(account.address)
    auth_tx = deployed_contract.functions.authorizeScanner(1).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 100000,
        'gasPrice': gas_price,
        'chainId': 137
    })

    signed_auth = w3.eth.account.sign_transaction(auth_tx, private_key)
    auth_hash = w3.eth.send_raw_transaction(signed_auth.raw_transaction)
    auth_receipt = w3.eth.wait_for_transaction_receipt(auth_hash, timeout=120)

    if auth_receipt['status'] == 1:
        print(f"Scanner #1 authorized (TX: {auth_hash.hex()})")
    else:
        print("WARNING: Scanner authorization failed")

    # Update polygon_config.json
    config['contract_address'] = contract_address
    config['testnet'] = False
    config['network'] = 'polygon_mainnet'
    config['deployment_date'] = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    config['deployment_tx'] = tx_hash.hex()
    config['scanner_id'] = 1

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\nUpdated polygon_config.json with contract address")

    # Save deployment record
    deployment_info = {
        'contract_address': contract_address,
        'deployer': account.address,
        'network': 'polygon_mainnet',
        'chain_id': 137,
        'deployed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'deploy_tx': tx_hash.hex(),
        'block_number': receipt['blockNumber'],
        'gas_used': receipt['gasUsed'],
        'authorized_scanners': [1]
    }

    deploy_record_path = Path(__file__).parent / "polygon_deployment.json"
    with open(deploy_record_path, 'w') as f:
        json.dump(deployment_info, f, indent=2)

    print(f"\nDEPLOYMENT COMPLETE")
    print(f"Contract: {contract_address}")
    print(f"Polygonscan: https://polygonscan.com/address/{contract_address}")
    print(f"\nReady to validate!")

    return contract_address


if __name__ == '__main__':
    deploy()
