"""Comprueba si hay canal de envío real (Resend o consola en DEBUG)."""
from __future__ import annotations

from django.conf import settings
from django.utils.translation import gettext as _

# Cuenta Gmail del proyecto (contacto público). Sustituye infotradeflow@gmail.com.
TRADEFLOW_GMAIL_ACCOUNT = 'tradeflowcolon@gmail.com'
LEGACY_GMAIL_ACCOUNT = 'infotradeflow@gmail.com'
LEGACY_CONTACT_EMAIL = 'info@tradeflow.pa'


def explain_email_failure(detail: str) -> str:
    """Mensaje legible para admin según el error del proveedor."""
    d = (detail or '').lower()
    if 'resend_not_configured' in d:
        return _(
            'RESEND_API_KEY is not configured. Create one at resend.com/api-keys '
            'and verify your sender domain in Resend → Domains.'
        )
    if 'only send testing emails' in d or 'verify a domain' in d or 'resend.com' in d:
        return _(
            'Resend is in test mode or the sender domain is not verified. '
            'Verify your domain in Resend → Domains and set DEFAULT_FROM_EMAIL accordingly.'
        )
    if 'validation_error' in d or 'statuscode":403' in d or 'statuscode": 403' in d:
        return _(
            'Resend rejected the send (403). Check that DEFAULT_FROM_EMAIL uses a verified '
            'domain and that RESEND_API_KEY is valid.'
        )
    return _(
        'We could not send the email. Check RESEND_API_KEY, DEFAULT_FROM_EMAIL, '
        'and logs at resend.com/emails.'
    )


def normalize_project_gmail(email: str) -> str:
    """Mapea el Gmail antiguo al oficial del proyecto."""
    cleaned = (email or '').strip()
    if cleaned.lower() == LEGACY_GMAIL_ACCOUNT:
        return TRADEFLOW_GMAIL_ACCOUNT
    return cleaned


def normalize_contact_email(email: str) -> str:
    """Correo público de contacto (footer, legales, soporte)."""
    cleaned = normalize_project_gmail(email)
    if cleaned.lower() == LEGACY_CONTACT_EMAIL:
        return TRADEFLOW_GMAIL_ACCOUNT
    return cleaned or TRADEFLOW_GMAIL_ACCOUNT


def smtp_configured() -> bool:
    """True si Resend está listo o DEBUG permite consola."""
    if (getattr(settings, 'RESEND_API_KEY', '') or '').strip():
        return True
    if settings.DEBUG:
        backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
        return 'console' in backend or 'locmem' in backend
    return False
