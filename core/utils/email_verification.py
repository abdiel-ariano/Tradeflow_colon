"""Generate and verify email OTP codes for account activation.

Short-lived codes gate checkout and seller portals when
``REQUIRE_EMAIL_VERIFICATION`` is on.
"""
from __future__ import annotations

import random
import string
from datetime import timedelta

from django.utils import timezone

from core.models import UserProfile


def generate_email_otp() -> str:
    """Create a fresh email verification code for the user."""
    return ''.join(random.choices(string.digits, k=6))


def assign_email_verification_code(profile: UserProfile, *, hours: int = 24) -> str:
    """Persist a fresh OTP on the profile; clear prior verification state."""
    code = generate_email_otp()
    profile.codigo_verificacion_email = code
    profile.codigo_verificacion_expira = timezone.now() + timedelta(hours=hours)
    profile.email_verificado = False
    profile.save(
        update_fields=[
            'codigo_verificacion_email',
            'codigo_verificacion_expira',
            'email_verificado',
        ]
    )
    return code


def verify_email_code(profile: UserProfile, raw_code: str) -> tuple[bool, str]:
    """Validate the submitted OTP and mark the email verified."""
    code = (raw_code or '').strip().replace(' ', '')
    if len(code) != 6 or not code.isdigit():
        return False, 'invalid_format'
    if not profile.codigo_verificacion_email:
        return False, 'no_code'
    if profile.codigo_verificacion_expira and timezone.now() > profile.codigo_verificacion_expira:
        return False, 'expired'
    if code != profile.codigo_verificacion_email:
        return False, 'wrong_code'
    profile.email_verificado = True
    profile.codigo_verificacion_email = ''
    profile.codigo_verificacion_expira = None
    profile.token_verificacion = None
    profile.save(
        update_fields=[
            'email_verificado',
            'codigo_verificacion_email',
            'codigo_verificacion_expira',
            'token_verificacion',
        ]
    )
    return True, ''
