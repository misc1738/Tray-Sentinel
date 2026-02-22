from __future__ import annotations

from pathlib import Path

from app.evidence_crypto import EvidenceCipher


def test_evidence_cipher_encrypts_and_decrypts_roundtrip(tmp_path: Path):
    cipher = EvidenceCipher(key_path=tmp_path / "data" / "keys" / "evidence.fernet.key")
    payload = b"digital-evidence-bytes"

    encrypted = cipher.encrypt_for_storage(payload)
    assert encrypted != payload
    assert encrypted.startswith(b"TSENC1:")

    decrypted = cipher.decrypt_from_storage(encrypted)
    assert decrypted == payload


def test_evidence_cipher_accepts_legacy_plaintext(tmp_path: Path):
    cipher = EvidenceCipher(key_path=tmp_path / "data" / "keys" / "evidence.fernet.key")
    payload = b"legacy-plaintext-evidence"

    out = cipher.decrypt_from_storage(payload)
    assert out == payload
