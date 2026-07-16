"""Send email OTP with reuse of a still-valid code and session throttle.

Avoids flooding Resend when users refresh verification screens during
CFZ onboarding.
"""
from __future__ import annotations

import time

from django.contrib.auth.models import User
from django.http import HttpRequest

from core.email_service import enviar_codigo_verificacion
from core.models import EmailVerification

OTP_RESEND_COOLDOWN_SECONDS = 60


def _session_throttle_key(user_id: int) -> str:
    """Session key used to throttle OTP resends per user."""
    return f'otp_sent_at_{user_id}'


def has_valid_otp(user: User) -> bool:
    """Return True when the user still has an unused valid OTP."""
    latest = (
        EmailVerification.objects.filter(user=user, is_used=False)
        .order_by('-created_at')
        .first()
    )
    return bool(latest and latest.is_valid())


def ensure_otp_sent(
    request: HttpRequest,
    user: User,
    *,
    force: bool = False,
) -> tuple[bool, str]:
    """Ensure a valid OTP exists and was emailed recently.
    
    
    Returns ``(ok, status)`` where status is ``sent``, ``existing``,
    ``throttled``, ``no_email``, or a provider error detail.
    """
    email = (user.email or '').strip()
    if not email:
        return False, 'no_email'

    if not force and has_valid_otp(user):
        return True, 'existing'

    key = _session_throttle_key(user.pk)
    last = request.session.get(key)
    now = time.time()
    if not force and last and (now - float(last)) < OTP_RESEND_COOLDOWN_SECONDS:
        return True, 'throttled'

    verification = EmailVerification.generate_for(user)
    result = enviar_codigo_verificacion(email, verification.code)
    if result.ok:
        request.session[key] = now
        request.session.modified = True
        return True, 'sent'

    return False, result.detail or 'send_failed'
