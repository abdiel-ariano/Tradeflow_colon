"""
Envío de OTP con reutilización de código vigente y throttle por sesión.
"""
from __future__ import annotations

import time

from django.contrib.auth.models import User
from django.http import HttpRequest

from core.email_service import enviar_codigo_verificacion
from core.models import EmailVerification

OTP_RESEND_COOLDOWN_SECONDS = 60


def _session_throttle_key(user_id: int) -> str:
    return f'otp_sent_at_{user_id}'


def has_valid_otp(user: User) -> bool:
    """Has valid otp."""
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
    """
    Garantiza un OTP vigente y enviado por correo.

    Returns:
        (ok, status) — status: ``sent``, ``existing``, ``throttled``,
        ``no_email``, o detalle de error del proveedor.
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
