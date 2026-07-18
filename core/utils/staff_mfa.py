"""Staff/admin TOTP MFA helpers (required unless Expo demo / opt-out)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from django.conf import settings
from django.contrib.auth.models import User

log = logging.getLogger('tradeflow.security')

SESSION_MFA_OK = 'tf_staff_mfa_ok'
ISSUER = 'TradeFlow Colón'


def _fernet_key() -> bytes:
    """Derive a stable 32-byte key from SECRET_KEY for secret-at-rest wrapping."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_totp_secret(plain: str) -> str:
    """Encrypt a TOTP secret for DB storage (Fernet when available, else HMAC mask)."""
    try:
        from cryptography.fernet import Fernet
        return Fernet(_fernet_key()).encrypt(plain.encode('utf-8')).decode('ascii')
    except Exception:
        # Fallback: store XOR-mask with SECRET_KEY hash (better than plaintext).
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        raw = plain.encode('utf-8')
        masked = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
        return 'xor:' + base64.urlsafe_b64encode(masked).decode('ascii')


def decrypt_totp_secret(stored: str) -> str:
    """Decrypt a TOTP secret previously stored by ``encrypt_totp_secret``."""
    if not stored:
        return ''
    if stored.startswith('xor:'):
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        masked = base64.urlsafe_b64decode(stored[4:].encode('ascii'))
        raw = bytes(b ^ key[i % len(key)] for i, b in enumerate(masked))
        return raw.decode('utf-8')
    from cryptography.fernet import Fernet
    return Fernet(_fernet_key()).decrypt(stored.encode('ascii')).decode('utf-8')


def user_is_staffish(user: User) -> bool:
    """True for Django staff/superuser or profile role=admin."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role == 'admin')


def staff_mfa_required() -> bool:
    """Whether staff must enroll+pass TOTP (off in Expo demo or explicit setting)."""
    if getattr(settings, 'EXPO_DEMO_MODE', False):
        return False
    return bool(getattr(settings, 'STAFF_MFA_REQUIRED', True))


def user_has_staff_totp(user: User) -> bool:
    """True when the profile has an enabled TOTP secret."""
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.staff_totp_enabled and profile.staff_totp_secret)


def user_needs_staff_mfa_setup(user: User) -> bool:
    """True when staff MFA is required but the user has not enrolled yet."""
    return (
        user_is_staffish(user)
        and staff_mfa_required()
        and not user_has_staff_totp(user)
    )


def user_needs_staff_mfa(user: User) -> bool:
    """True when staff must complete MFA setup or challenge this session."""
    if not user_is_staffish(user):
        return False
    if user_has_staff_totp(user):
        return True
    return staff_mfa_required()


def session_mfa_ok(request) -> bool:
    """Return whether this session already passed staff MFA."""
    return bool(request.session.get(SESSION_MFA_OK))


def mark_session_mfa_ok(request) -> None:
    """Mark the session as MFA-verified."""
    request.session[SESSION_MFA_OK] = True
    request.session.modified = True


def clear_session_mfa(request) -> None:
    """Clear MFA session flag (e.g. on logout)."""
    if SESSION_MFA_OK in request.session:
        del request.session[SESSION_MFA_OK]
        request.session.modified = True


def generate_totp_secret() -> str:
    """Return a new base32 TOTP secret."""
    import pyotp
    return pyotp.random_base32()


def provisioning_uri(user: User, plain_secret: str) -> str:
    """otpauth:// URI for authenticator apps."""
    import pyotp
    return pyotp.totp.TOTP(plain_secret).provisioning_uri(
        name=user.email or user.username,
        issuer_name=ISSUER,
    )


def verify_totp(user: User, code: str) -> bool:
    """Validate a 6-digit TOTP code against the user's stored secret."""
    import pyotp
    profile = getattr(user, 'profile', None)
    if not profile or not profile.staff_totp_secret:
        return False
    try:
        secret = decrypt_totp_secret(profile.staff_totp_secret)
    except Exception:
        log.exception('staff_mfa_decrypt_failed user_id=%s', user.pk)
        return False
    totp = pyotp.TOTP(secret)
    ok = totp.verify((code or '').strip(), valid_window=1)
    if ok:
        log.info('staff_mfa_ok user_id=%s', user.pk)
    else:
        log.warning('staff_mfa_failed user_id=%s', user.pk)
    return ok


def constant_time_equals(a: str, b: str) -> bool:
    """hmac.compare_digest wrapper for non-TOTP secrets."""
    return hmac.compare_digest((a or '').encode(), (b or '').encode())
