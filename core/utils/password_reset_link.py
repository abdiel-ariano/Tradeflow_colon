"""
Generación segura de magic links de recuperación (modelo PasswordResetLink).

Mirrors ``otp_handler`` / EmailVerification: secrets CSPRNG, invalidate prior
rows, persist one active token, TTL from ``PASSWORD_RESET_LINK_EXPIRY_MINUTES``.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import DatabaseError, transaction
from django.utils import timezone

from core.models import PasswordResetLink

log = logging.getLogger('tradeflow.auth')

# Keep aligned with settings.PASSWORD_RESET_TIMEOUT (15 minutes).
PASSWORD_RESET_LINK_EXPIRY_MINUTES = 15
PASSWORD_RESET_TOKEN_BYTES = 32


def _generate_secure_token() -> str:
    """URL-safe opaque token (not a short OTP)."""
    return secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)


def generate_password_reset_link(user: User) -> str:
    """
    Invalidate prior reset links for ``user``, persist a new row, return the plain token.

    Raises:
        ValueError: user not persisted.
        DatabaseError: DB failure.
    """
    if user.pk is None:
        raise ValueError('generate_password_reset_link requires a persisted User.')

    plain = _generate_secure_token()
    expires_at = timezone.now() + timedelta(minutes=PASSWORD_RESET_LINK_EXPIRY_MINUTES)

    try:
        with transaction.atomic():
            removed, _ = PasswordResetLink.objects.filter(user=user).delete()
            if removed:
                log.info(
                    'password_reset_link_invalidated user_id=%s removed=%s',
                    user.pk,
                    removed,
                )
            PasswordResetLink.objects.create(user=user, token=plain)
    except DatabaseError:
        log.exception('password_reset_link_persist_failed user_id=%s', user.pk)
        raise

    log.info(
        'password_reset_link_generated user_id=%s expires_at=%s',
        user.pk,
        expires_at.isoformat(),
    )
    return plain


def link_expires_at(row: PasswordResetLink) -> datetime:
    return row.created_at + timedelta(minutes=PASSWORD_RESET_LINK_EXPIRY_MINUTES)


@dataclass(frozen=True)
class PasswordResetLinkResult:
    ok: bool
    error_code: str = ''
    user: User | None = None
    link: PasswordResetLink | None = None


def lookup_password_reset_link(*, user: User, raw_token: str) -> PasswordResetLinkResult:
    """
    Validate token for ``user`` without consuming it (form GET / session handshake).

    Does not log the raw token.
    """
    token = (raw_token or '').strip()
    if not token or user.pk is None:
        return PasswordResetLinkResult(ok=False, error_code='invalid_or_expired')

    row = (
        PasswordResetLink.objects.filter(user=user, token=token, is_used=False)
        .order_by('-created_at')
        .first()
    )
    if row is None or not row.is_valid():
        log.warning(
            'password_reset_link_rejected reason=invalid_or_expired user_id=%s',
            user.pk,
        )
        return PasswordResetLinkResult(ok=False, error_code='invalid_or_expired')

    return PasswordResetLinkResult(ok=True, user=user, link=row)


def consume_password_reset_link(*, user: User, raw_token: str) -> PasswordResetLinkResult:
    """
    Atomically validate and delete the link (single use), same idea as OTP success path.
    """
    token = (raw_token or '').strip()
    if not token or user.pk is None:
        return PasswordResetLinkResult(ok=False, error_code='invalid_or_expired')

    try:
        with transaction.atomic():
            row = (
                PasswordResetLink.objects.select_for_update()
                .filter(user=user, token=token, is_used=False)
                .order_by('-created_at')
                .first()
            )
            if row is None or not row.is_valid():
                log.warning(
                    'password_reset_link_consume_rejected user_id=%s',
                    user.pk,
                )
                return PasswordResetLinkResult(ok=False, error_code='invalid_or_expired')

            link_id = row.pk
            row.delete()
            log.info(
                'password_reset_link_consumed user_id=%s link_id=%s',
                user.pk,
                link_id,
            )
            return PasswordResetLinkResult(ok=True, user=user)
    except Exception:
        log.exception('password_reset_link_consume_failed user_id=%s', user.pk)
        return PasswordResetLinkResult(ok=False, error_code='server_error')
