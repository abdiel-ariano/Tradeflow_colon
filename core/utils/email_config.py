"""Comprueba si hay canal de envío real (Supabase o SMTP Django)."""
from __future__ import annotations

import os

from django.conf import settings

# Cuenta Gmail del proyecto (App Password en Google). Sustituye infotradeflow@gmail.com.
TRADEFLOW_GMAIL_ACCOUNT = 'tradeflowcolon@gmail.com'
LEGACY_GMAIL_ACCOUNT = 'infotradeflow@gmail.com'
LEGACY_CONTACT_EMAIL = 'info@tradeflow.pa'


def is_railway_deploy() -> bool:
    """True cuando la app corre en Railway (SMTP saliente suele estar bloqueado)."""
    if getattr(settings, 'RAILWAY_DEPLOY', False):
        return True
    return bool(os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_PROJECT_ID'))


def django_smtp_fallback_enabled() -> bool:
    """SMTP directo desde Django (no usar en Railway — Errno 101)."""
    if not getattr(settings, 'EMAIL_SMTP_CONFIGURED', False):
        return False
    return bool(getattr(settings, 'EMAIL_SMTP_FALLBACK_ENABLED', not is_railway_deploy()))


def explain_email_failure(detail: str) -> str:
    """Mensaje legible para admin según el error del proveedor."""
    d = (detail or '').lower()
    if 'only send testing emails' in d or 'verify a domain' in d or 'resend.com' in d:
        return (
            'Supabase está llamando una Edge Function antigua con Resend en modo prueba '
            '(solo envía a tu correo). En Railway pon '
            'SUPABASE_EMAIL_FUNCTION=send-transactional-email, despliega esa función con '
            'GMAIL_USER + GMAIL_APP_PASSWORD en Supabase, y no uses bright-handler.'
        )
    if 'network is unreachable' in d or 'errno 101' in d:
        return (
            'Railway bloquea SMTP saliente (Gmail directo no funciona). '
            'Usa SUPABASE_EMAIL_ENABLED=true y la Edge Function send-transactional-email '
            'con secrets Gmail en Supabase.'
        )
    if 'gmail_not_configured' in d:
        return (
            'La Edge Function no tiene GMAIL_USER / GMAIL_APP_PASSWORD. '
            'Configúralos en Supabase → Edge Functions → Secrets.'
        )
    if 'not_found' in d or 'requested function was not found' in d:
        return (
            'La Edge Function send-transactional-email no está desplegada en Supabase. '
            'GitHub → Actions → "Deploy Supabase Edge Functions" → Run workflow, '
            'o ejecuta: bash scripts/deploy_supabase_email.sh'
        )
    if 'smtp_not_configured' in d:
        return (
            'Correo no configurado. Activa SUPABASE_EMAIL_ENABLED y despliega '
            'send-transactional-email, o configura Gmail solo en local (no en Railway).'
        )
    return (
        'No se pudo enviar el correo. Revisa SUPABASE_EMAIL_FUNCTION, secrets Gmail en '
        'Supabase y los logs de la Edge Function.'
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
    """True si Supabase está listo o EMAIL_BACKEND no es consola."""
    if getattr(settings, 'SUPABASE_CONFIGURED', False):
        return True
    backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
    return 'console' not in backend and 'locmem' not in backend
