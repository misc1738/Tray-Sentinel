from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


@dataclass(frozen=True)
class KeyMaterial:
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey


def _keys_dir(base_dir: Path) -> Path:
    d = base_dir / "data" / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_or_create_user_keys(*, base_dir: Path, user_id: str) -> KeyMaterial:
    """Prototype key management.

    - Stores user private keys locally on disk.
    - In production, private keys should be in HSM / smartcard / OS keystore.
    """

    keys_dir = _keys_dir(base_dir)
    priv_path = keys_dir / f"{user_id}.ed25519.pem"

    if priv_path.exists():
        pem = priv_path.read_bytes()
        private = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError("unexpected private key type")
        return KeyMaterial(private_key=private, public_key=private.public_key())

    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    priv_path.write_bytes(pem)
    return KeyMaterial(private_key=private, public_key=private.public_key())


def pubkey_b64(pub: Ed25519PublicKey) -> str:
    raw = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode("utf-8")


def sign_b64(priv: Ed25519PrivateKey, payload: bytes) -> str:
    sig = priv.sign(payload)
    return base64.b64encode(sig).decode("utf-8")


def verify_signature(*, pubkey_b64_str: str, signature_b64_str: str, payload: bytes) -> bool:
    try:
        pub_raw = base64.b64decode(pubkey_b64_str)
        sig_raw = base64.b64decode(signature_b64_str)
        pub = Ed25519PublicKey.from_public_bytes(pub_raw)
        pub.verify(sig_raw, payload)
        return True
    except Exception:
        return False
