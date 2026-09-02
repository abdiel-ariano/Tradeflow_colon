"""Envía OTP por correo reutilizando un código aún válido y con throttle de sesión.

Evita saturar Resend cuando los usuarios refrescan pantallas de verificación
durante el onboarding ZLC.
"""
from __future__ import annotations

import time

from django.contrib.auth.models import User
from django.http import HttpRequest

from core.email_service import enviar_codigo_verificacion
from core.models import EmailVerification

OTP_RESEND_COOLDOWN_SECONDS = 60


def _session_throttle_key(user_id: int) -> str:
    """Clave de sesión usada para limitar reenvíos OTP por usuario."""
    return f'otp_sent_at_{user_id}'


def has_valid_otp(user: User) -> bool:
    """Devuelve True cuando el usuario aún tiene un OTP válido sin usar."""
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
    """Asegura que exista un OTP válido y que se haya enviado por correo recientemente.


    Devuelve ``(ok, status)`` donde status es ``sent``, ``existing``,
    ``throttled``, ``no_email``, o el detalle de error del proveedor.
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
    plain = getattr(verification, 'plain_code', '') or ''
    result = enviar_codigo_verificacion(email, plain)
    if result.ok:
        request.session[key] = now
        request.session.modified = True
        return True, 'sent'

    return False, result.detail or 'send_failed'
