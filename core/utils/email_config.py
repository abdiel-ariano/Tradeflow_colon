"""Comprueba si Resend está configurado para envío real."""
from django.conf import settings


def smtp_configured() -> bool:
    """True si hay RESEND_API_KEY (compatibilidad con vistas legacy)."""
    key = (getattr(settings, 'ANYMAIL', {}) or {}).get('RESEND_API_KEY', '')
    if not key:
        key = getattr(settings, 'RESEND_API_KEY', '')
    return bool((key or '').strip())
