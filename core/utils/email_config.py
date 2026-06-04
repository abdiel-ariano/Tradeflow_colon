"""Comprueba si hay canal de envío real (Supabase o SMTP Django)."""
from __future__ import annotations

from django.conf import settings

# Cuenta Gmail del proyecto (App Password en Google). Sustituye infotradeflow@gmail.com.
TRADEFLOW_GMAIL_ACCOUNT = 'tradeflowcolon@gmail.com'
LEGACY_GMAIL_ACCOUNT = 'infotradeflow@gmail.com'


def normalize_project_gmail(email: str) -> str:
    """Mapea el Gmail antiguo al oficial del proyecto."""
    cleaned = (email or '').strip()
    if cleaned.lower() == LEGACY_GMAIL_ACCOUNT:
        return TRADEFLOW_GMAIL_ACCOUNT
    return cleaned


def smtp_configured() -> bool:
    """True si Supabase está listo o EMAIL_BACKEND no es consola."""
    if getattr(settings, 'SUPABASE_CONFIGURED', False):
        return True
    backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
    return 'console' not in backend and 'locmem' not in backend
