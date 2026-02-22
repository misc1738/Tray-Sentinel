from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.utils import sha256_bytes


_ENC_PREFIX = b"TSENC1:"


@dataclass(frozen=True)
class EvidenceEncryptionStatus:
    enabled: bool
    algorithm: str
    key_path: str
    key_fingerprint_sha256: str


class EvidenceCipher:
    def __init__(self, *, key_path: Path):
        self.key_path = key_path
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        key = self._load_or_create_key()
        self._fernet = Fernet(key)
        self._key_fingerprint = sha256_bytes(base64.urlsafe_b64decode(key))

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        return key

    def encrypt_for_storage(self, plaintext: bytes) -> bytes:
        return _ENC_PREFIX + self._fernet.encrypt(plaintext)

    def decrypt_from_storage(self, ciphertext_or_plaintext: bytes) -> bytes:
        if not ciphertext_or_plaintext.startswith(_ENC_PREFIX):
            # Backward compatibility with legacy plaintext evidence files.
            return ciphertext_or_plaintext
        token = ciphertext_or_plaintext[len(_ENC_PREFIX) :]
        try:
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise ValueError("unable to decrypt evidence payload") from exc

    def status(self) -> EvidenceEncryptionStatus:
        return EvidenceEncryptionStatus(
            enabled=True,
            algorithm="Fernet (AES-128-CBC + HMAC-SHA256)",
            key_path=str(self.key_path),
            key_fingerprint_sha256=self._key_fingerprint,
        )
