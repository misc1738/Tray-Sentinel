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
        try:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            key = self._load_or_create_key()
            self._fernet = Fernet(key)
            self._key_fingerprint = sha256_bytes(base64.urlsafe_b64decode(key))
        except (OSError, ValueError) as e:
            raise RuntimeError(f"Failed to initialize encryption: {e}")

    def _load_or_create_key(self) -> bytes:
        try:
            if self.key_path.exists():
                key = self.key_path.read_bytes().strip()
                # Validate key format
                if len(key) < 44:  # Fernet keys are 44 chars minimum
                    raise ValueError("Invalid encryption key format")
                return key
            # Create new key
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            self.key_path.chmod(0o600)  # Restrict permissions to owner only
            return key
        except (OSError, ValueError) as e:
            raise RuntimeError(f"Failed to load/create encryption key: {e}")

    def encrypt_for_storage(self, plaintext: bytes) -> bytes:
        try:
            return _ENC_PREFIX + self._fernet.encrypt(plaintext)
        except Exception as e:
            raise RuntimeError(f"Failed to encrypt evidence: {e}")

    def decrypt_from_storage(self, ciphertext_or_plaintext: bytes) -> bytes:
        try:
            if not ciphertext_or_plaintext.startswith(_ENC_PREFIX):
                # Backward compatibility with legacy plaintext evidence files.
                return ciphertext_or_plaintext
            token = ciphertext_or_plaintext[len(_ENC_PREFIX) :]
            return self._fernet.decrypt(token)
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt evidence payload - key may be wrong") from exc
        except Exception as e:
            raise RuntimeError(f"Decryption error: {e}") from e

    def status(self) -> EvidenceEncryptionStatus:
        return EvidenceEncryptionStatus(
            enabled=True,
            algorithm="Fernet (AES-128-CBC + HMAC-SHA256)",
            key_path=str(self.key_path),
            key_fingerprint_sha256=self._key_fingerprint,
        )
