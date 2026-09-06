"""Fernet encryption for broker credentials at rest.

The key comes from ``settings.BROKER_CREDS_ENCRYPTION_KEY`` (generate with
``Fernet.generate_key()``). Losing the key orphans all linked accounts:
users would simply re-link: but rotating it requires re-encrypting rows,
so treat it like a database credential in k8s secrets.

Plaintext credentials must never be logged, persisted, or returned by any
API after the initial link request. Keep every decrypt call as close to
the Alpaca client construction as possible.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class BrokerCryptoError(RuntimeError):
    """Encryption layer misconfiguration or corrupt ciphertext."""


def _fernet() -> Fernet:
    key = settings.BROKER_CREDS_ENCRYPTION_KEY
    if not key:
        raise BrokerCryptoError(
            "BROKER_CREDS_ENCRYPTION_KEY is not configured: cannot link or use "
            "broker accounts. Generate one with: python -c "
            "\"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise BrokerCryptoError(f"BROKER_CREDS_ENCRYPTION_KEY is malformed: {exc}") from exc


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential string for storage."""
    if not plaintext:
        raise BrokerCryptoError("refusing to encrypt empty credential")
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a stored credential string."""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise BrokerCryptoError(
            "credential decryption failed: encryption key changed or data corrupt"
        ) from exc
