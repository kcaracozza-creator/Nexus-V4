#!/usr/bin/env python3
"""
Generate Ed25519 keypair for NEXUS firmware signing.

Run ONCE on ZULTAN:
    python3 tools/gen_firmware_keypair.py

- Private key: keep ONLY on ZULTAN, never commit, never copy to deployed units
- Public key:  embed in ota_updater.py (NEXUS_FIRMWARE_PUBKEY constant)
              or set via NEXUS_FIRMWARE_PUBKEY environment variable on DANIELSON

Usage on ZULTAN to sign a manifest:
    python3 tools/gen_firmware_keypair.py --sign manifest.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption
    )
except ImportError:
    print("Install: pip install cryptography")
    sys.exit(1)


PRIVATE_KEY_PATH = Path.home() / '.nexus' / 'firmware_signing_key.pem'
PUBLIC_KEY_PATH  = Path.home() / '.nexus' / 'firmware_signing_key.pub.pem'


def generate():
    PRIVATE_KEY_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key  = private_key.public_key()

    priv_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_pem  = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    PRIVATE_KEY_PATH.write_bytes(priv_pem)
    PRIVATE_KEY_PATH.chmod(0o600)
    PUBLIC_KEY_PATH.write_bytes(pub_pem)

    print(f"Private key: {PRIVATE_KEY_PATH}  (KEEP ON ZULTAN ONLY)")
    print(f"Public key:  {PUBLIC_KEY_PATH}")
    print()
    print("Embed this in ota_updater.py as NEXUS_FIRMWARE_PUBKEY:")
    print("=" * 60)
    print(pub_pem.decode())


def sign_manifest(manifest_path: str):
    if not PRIVATE_KEY_PATH.exists():
        print(f"Private key not found at {PRIVATE_KEY_PATH}. Run --generate first.")
        sys.exit(1)

    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    manifest    = json.loads(Path(manifest_path).read_text())
    manifest.pop('signature', None)

    payload   = json.dumps(manifest, sort_keys=True).encode()
    signature = private_key.sign(payload).hex()

    manifest['signature'] = signature
    Path(manifest_path).write_text(json.dumps(manifest, indent=2))
    print(f"Signed: {manifest_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true', help='Generate new keypair')
    parser.add_argument('--sign', metavar='MANIFEST', help='Sign a manifest.json file')
    args = parser.parse_args()

    if args.sign:
        sign_manifest(args.sign)
    else:
        generate()


if __name__ == '__main__':
    main()
