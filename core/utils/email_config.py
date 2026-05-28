"""Helpers de configuración SMTP (sin secretos en código)."""
from __future__ import annotations

from django.conf import settings


def smtp_configured() -> bool:
    """True si hay credenciales SMTP listas (Gmail, Resend o SendGrid)."""
    if getattr(settings, 'EMAIL_SMTP_CONFIGURED', False):
        return True
    user = (getattr(settings, 'EMAIL_HOST_USER', '') or '').strip()
    password = (getattr(settings, 'EMAIL_HOST_PASSWORD', '') or '').strip()
    return bool(user and password)
