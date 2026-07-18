"""Hash helpers for OTP codes and password-reset tokens at rest.

Plaintext secrets are shown once (email); the DB stores only digests.
"""
from __future__ import annotations

import hashlib
import hmac


def hash_secret(raw: str) -> str:
    """Return a hex SHA-256 digest of ``raw`` (empty → empty)."""
    value = (raw or '').strip()
    if not value:
        return ''
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def secrets_match(raw: str, stored_digest: str) -> bool:
    """Constant-time compare of plaintext against a stored digest."""
    if not raw or not stored_digest:
        return False
    candidate = hash_secret(raw)
    return hmac.compare_digest(candidate, stored_digest.strip())
