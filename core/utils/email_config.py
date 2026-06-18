"""Comprueba si hay canal de envío real (Resend o consola en DEBUG)."""
from __future__ import annotations

from django.conf import settings

# Cuenta Gmail del proyecto (contacto público). Sustituye infotradeflow@gmail.com.
TRADEFLOW_GMAIL_ACCOUNT = 'tradeflowcolon@gmail.com'
LEGACY_GMAIL_ACCOUNT = 'infotradeflow@gmail.com'
LEGACY_CONTACT_EMAIL = 'info@tradeflow.pa'


def explain_email_failure(detail: str) -> str:
    """Mensaje legible para admin según el error del proveedor."""
    d = (detail or '').lower()
    if 'resend_not_configured' in d:
        return (
            'RESEND_API_KEY no está configurada en Railway. '
            'Créala en resend.com/api-keys y verifica el dominio remitente en Resend → Domains.'
        )
    if 'only send testing emails' in d or 'verify a domain' in d or 'resend.com' in d:
        return (
            'Resend está en modo prueba o el dominio remitente no está verificado. '
            'Verifica tu dominio en Resend → Domains y usa DEFAULT_FROM_EMAIL con ese dominio.'
        )
    if 'validation_error' in d or 'statuscode":403' in d or 'statuscode": 403' in d:
        return (
            'Resend rechazó el envío (403). Revisa que DEFAULT_FROM_EMAIL use un dominio '
            'verificado en Resend y que RESEND_API_KEY sea válida.'
        )
    return (
        'No se pudo enviar el correo. Revisa RESEND_API_KEY, DEFAULT_FROM_EMAIL '
        'y los logs en resend.com/emails.'
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
