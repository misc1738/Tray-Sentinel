from __future__ import annotations

import base64
import os
import hashlib
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.backends import default_backend


@dataclass(frozen=True)
class KeyMaterial:
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey


# ===== KEY ENCRYPTION PASSWORD DERIVATION =====
def _get_key_encryption_password() -> bytes:
    """
    Get the master password for encrypting private keys at rest.
    
    In production, this should come from:
    - HSM / Azure Key Vault / AWS KMS
    - Environment variable (MASTER_KEY_PASSWORD) for simpler deployments
    - OS keychain
    """
    master_key = os.getenv("MASTER_KEY_PASSWORD")
    
    if not master_key:
        # Fallback: use a derived key from system if available
        # WARNING: This is NOT secure for production!
        # In production, MASTER_KEY_PASSWORD must be set
        import warnings
        warnings.warn(
            "⚠️  MASTER_KEY_PASSWORD environment variable not set. "
            "Private keys will NOT be encrypted at rest. "
            "This is a security risk in production!"
        )
        return b"insecure-default-key-not-for-production"
    
    # Derive a consistent encryption key from the master password using PBKDF2-like approach
    salt = b"traceys-sentinel-key-encryption"  # Fixed salt for consistency
    # Use PBKDF2-like iteration with hashlib for key derivation
    derived_key = master_key.encode()
    for _ in range(100000):
        derived_key = hashlib.sha256(derived_key + salt).digest()
    return derived_key


def _keys_dir(base_dir: Path) -> Path:
    d = base_dir / "data" / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_or_create_user_keys(*, base_dir: Path, user_id: str) -> KeyMaterial:
    """
    Prototype key management with encrypted storage at rest.
    
    - Stores user private keys locally on disk with AES encryption
    - Password derived from MASTER_KEY_PASSWORD environment variable
    - In production, use HSM / smartcard / OS keystore instead
    """

    keys_dir = _keys_dir(base_dir)
    priv_path = keys_dir / f"{user_id}.ed25519.pem"

    if priv_path.exists():
        pem = priv_path.read_bytes()
        password = _get_key_encryption_password()
        
        try:
            private = serialization.load_pem_private_key(pem, password=password, backend=default_backend())
        except ValueError as e:
            # Handle case where password is wrong or key is not encrypted
            raise ValueError(f"Failed to decrypt private key for {user_id}: {str(e)}")
        
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError("unexpected private key type")
        return KeyMaterial(private_key=private, public_key=private.public_key())

    # Generate new key
    private = Ed25519PrivateKey.generate()
    
    # Encrypt with master key password
    password = _get_key_encryption_password()
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
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
