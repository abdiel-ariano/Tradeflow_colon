"""Staff/admin TOTP MFA helpers (required unless Expo demo / opt-out)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import string

from django.conf import settings
from django.contrib.auth.models import User

from core.utils.saas_demo import user_is_read_only_saas_demo

log = logging.getLogger('tradeflow.security')

SESSION_MFA_OK = 'tf_staff_mfa_ok'
SESSION_BACKUP_CODES = 'tf_mfa_backup_codes_once'
ISSUER = 'TradeFlow Colón'
BACKUP_CODE_COUNT = 8
BACKUP_CODE_LEN = 10


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
    if user_is_read_only_saas_demo(user):
        return False
    return (
        user_is_staffish(user)
        and staff_mfa_required()
        and not user_has_staff_totp(user)
    )


def user_needs_staff_mfa(user: User) -> bool:
    """True when staff must complete MFA setup or challenge this session."""
    if user_is_read_only_saas_demo(user):
        return False
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


def hash_backup_code(code: str) -> str:
    """SHA-256 hex digest of a normalized backup code (not tied to SECRET_KEY)."""
    normalized = (code or '').strip().upper().replace(' ', '').replace('-', '')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> list[str]:
    """Return plaintext one-time backup codes (show once to the user)."""
    alphabet = string.ascii_uppercase + string.digits
    # Avoid ambiguous characters.
    alphabet = alphabet.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    codes: list[str] = []
    for _ in range(count):
        raw = ''.join(secrets.choice(alphabet) for _ in range(BACKUP_CODE_LEN))
        codes.append(f'{raw[:5]}-{raw[5:]}')
    return codes


def store_backup_code_hashes(profile, plain_codes: list[str]) -> None:
    """Persist SHA-256 hashes of backup codes on the profile."""
    profile.staff_totp_backup_hashes = [hash_backup_code(c) for c in plain_codes]
    profile.save(update_fields=['staff_totp_backup_hashes'])


def remaining_backup_codes(profile) -> int:
    """Count unused backup code hashes."""
    hashes = getattr(profile, 'staff_totp_backup_hashes', None) or []
    return len(hashes) if isinstance(hashes, list) else 0


def consume_backup_code(user: User, code: str) -> bool:
    """Validate and consume one backup code. Survives SECRET_KEY rotation."""
    profile = getattr(user, 'profile', None)
    if not profile or not profile.staff_totp_enabled:
        return False
    hashes = list(profile.staff_totp_backup_hashes or [])
    if not hashes:
        return False
    digest = hash_backup_code(code)
    match_idx = None
    for i, stored in enumerate(hashes):
        if hmac.compare_digest(str(stored), digest):
            match_idx = i
            break
    if match_idx is None:
        log.warning('staff_mfa_backup_failed user_id=%s', user.pk)
        return False
    hashes.pop(match_idx)
    profile.staff_totp_backup_hashes = hashes
    profile.save(update_fields=['staff_totp_backup_hashes'])
    log.info('staff_mfa_backup_ok user_id=%s remaining=%s', user.pk, len(hashes))
    return True


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


def totp_decrypt_broken(user: User) -> bool:
    """True when an enabled secret cannot be decrypted (e.g. SECRET_KEY rotated)."""
    profile = getattr(user, 'profile', None)
    if not profile or not profile.staff_totp_enabled or not profile.staff_totp_secret:
        return False
    try:
        secret = decrypt_totp_secret(profile.staff_totp_secret)
        return not bool(secret)
    except Exception:
        return True


def verify_staff_mfa_code(user: User, code: str) -> bool:
    """Accept a TOTP code or a one-time backup code."""
    raw = (code or '').strip()
    if not raw:
        return False
    # Backup codes look like XXXXX-XXXXX (longer than 6 digits).
    if len(raw.replace('-', '').replace(' ', '')) > 6:
        return consume_backup_code(user, raw)
    if verify_totp(user, raw):
        return True
    # Allow backup codes without dashes typed as continuous strings too.
    return consume_backup_code(user, raw)


def clear_staff_mfa(profile) -> None:
    """Wipe TOTP secret, flag, and backup hashes (ops recovery)."""
    profile.staff_totp_secret = ''
    profile.staff_totp_enabled = False
    profile.staff_totp_backup_hashes = []
    profile.save(update_fields=[
        'staff_totp_secret', 'staff_totp_enabled', 'staff_totp_backup_hashes',
    ])


def constant_time_equals(a: str, b: str) -> bool:
    """hmac.compare_digest wrapper for non-TOTP secrets."""
    return hmac.compare_digest((a or '').encode(), (b or '').encode())
