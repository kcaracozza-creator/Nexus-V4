#!/usr/bin/env python3
"""Check deployer wallet balance"""

try:
    from web3 import Web3
except ImportError:
    print("Installing web3...")
    import subprocess
    subprocess.run(["pip", "install", "web3"], capture_output=True)
    from web3 import Web3

# Connect to Polygon
w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))

# Deployer wallet
addr = '0x1671223861ECDEebA3dc20dB4cA8c4a5de70734F'

# Check balance
balance_wei = w3.eth.get_balance(addr)
balance_pol = w3.from_wei(balance_wei, 'ether')

print(f"Deployer Wallet: {addr}")
print(f"Balance: {balance_pol} POL")
print(f"Balance (wei): {balance_wei}")

if balance_pol > 0:
    print(f"\n✅ Wallet has {balance_pol} POL - ready to deploy!")
else:
    print(f"\n❌ Wallet empty - transfer POL to deploy")
