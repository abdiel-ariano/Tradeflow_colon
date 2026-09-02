"""Emite y consume enlaces mágicos opacos de restablecimiento de contraseña.

Espeja la seguridad OTP: tokens CSPRNG, invalida filas previas, TTL corto
alineado con ``PASSWORD_RESET_TIMEOUT``.
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
from core.utils.secret_hash import hash_secret

log = logging.getLogger('tradeflow.auth')

# Keep aligned with settings.PASSWORD_RESET_TIMEOUT (15 minutes).
PASSWORD_RESET_LINK_EXPIRY_MINUTES = 15
PASSWORD_RESET_TOKEN_BYTES = 32


def _generate_secure_token() -> str:
    """Devuelve un token de reset opaco seguro para URL (no un OTP corto)."""
    return secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)


def generate_password_reset_link(user: User) -> str:
    """Invalida enlaces previos, persiste una fila de token nueva y devuelve el token en claro."""
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
            PasswordResetLink.objects.create(user=user, token=hash_secret(plain))
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
    """Devuelve el datetime de expiración de una fila de enlace de reset."""
    return row.created_at + timedelta(minutes=PASSWORD_RESET_LINK_EXPIRY_MINUTES)


@dataclass(frozen=True)
class PasswordResetLinkResult:
    """Resultado inmutable de lookup/consume (ok, error, user, link)."""
    ok: bool
    error_code: str = ''
    user: User | None = None
    link: PasswordResetLink | None = None


def _find_reset_row(*, user: User, raw_token: str, for_update: bool = False):
    """Locate a reset row by hash (or legacy plaintext) for ``user``."""
    digest = hash_secret(raw_token)
    qs = PasswordResetLink.objects.filter(user=user, is_used=False)
    if for_update:
        qs = qs.select_for_update()
    row = qs.filter(token=digest).order_by('-created_at').first()
    if row is None:
        # Pre-hash migration compatibility (short-lived rows).
        row = qs.filter(token=raw_token).order_by('-created_at').first()
    return row


def lookup_password_reset_link(*, user: User, raw_token: str) -> PasswordResetLinkResult:
    """Valida el token para ``user`` sin consumirlo (handshake GET)."""
    token = (raw_token or '').strip()
    if not token or user.pk is None:
        return PasswordResetLinkResult(ok=False, error_code='invalid_or_expired')

    row = _find_reset_row(user=user, raw_token=token)
    if row is None or not row.is_valid():
        log.warning(
            'password_reset_link_rejected reason=invalid_or_expired user_id=%s',
            user.pk,
        )
        return PasswordResetLinkResult(ok=False, error_code='invalid_or_expired')

    return PasswordResetLinkResult(ok=True, user=user, link=row)


def consume_password_reset_link(*, user: User, raw_token: str) -> PasswordResetLinkResult:
    """Valida y elimina el enlace de reset de forma atómica (un solo uso)."""
    token = (raw_token or '').strip()
    if not token or user.pk is None:
        return PasswordResetLinkResult(ok=False, error_code='invalid_or_expired')

    try:
        with transaction.atomic():
            row = _find_reset_row(user=user, raw_token=token, for_update=True)
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
