"""Create and persist user OTP rows for email verification flows.

Invalidates prior unused codes so only one active OTP exists per user.
"""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import DatabaseError, transaction
from django.utils import timezone

from core.models import EmailVerification

log = logging.getLogger('tradeflow.auth')

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10


def _generate_secure_otp() -> str:
    """Return a cryptographically secure 6-digit numeric OTP."""
    return f'{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}'


def generate_user_otp(user: User) -> str:
    """Invalidate prior OTPs and persist a new code for the user."""
    if user.pk is None:
        raise ValueError('generate_user_otp requires a persisted User instance.')

    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    plain_code = _generate_secure_otp()

    try:
        with transaction.atomic():
            removed, _ = EmailVerification.objects.filter(user=user).delete()
            if removed:
                log.info(
                    'otp_invalidated user_id=%s removed=%s',
                    user.pk,
                    removed,
                )

            EmailVerification.objects.create(user=user, code=plain_code)
    except DatabaseError:
        log.exception(
            'otp_persist_failed user_id=%s',
            user.pk,
        )
        raise

    log.info(
        'otp_generated user_id=%s expires_at=%s',
        user.pk,
        expires_at.isoformat(),
    )
    return plain_code
