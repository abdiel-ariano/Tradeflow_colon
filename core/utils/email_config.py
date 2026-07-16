"""Detect whether a real outbound email channel is configured.

Resend is preferred in production; DEBUG may fall back to the console
backend for local CFZ onboarding tests.
"""
from __future__ import annotations

from django.conf import settings
from django.utils.translation import gettext as _

# Project Gmail (public contact). Replaces infotradeflow@gmail.com.
TRADEFLOW_GMAIL_ACCOUNT = 'tradeflowcolon@gmail.com'
LEGACY_GMAIL_ACCOUNT = 'infotradeflow@gmail.com'
LEGACY_CONTACT_EMAIL = 'info@tradeflow.pa'


def explain_email_failure(detail: str) -> str:
    """Return an admin-readable message for a provider error."""
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
    """Map legacy Gmail addresses to the official project inbox."""
    cleaned = (email or '').strip()
    if cleaned.lower() == LEGACY_GMAIL_ACCOUNT:
        return TRADEFLOW_GMAIL_ACCOUNT
    return cleaned


def normalize_contact_email(email: str) -> str:
    """Normalize the public contact address for footer/legal."""
    cleaned = normalize_project_gmail(email)
    if cleaned.lower() == LEGACY_CONTACT_EMAIL:
        return TRADEFLOW_GMAIL_ACCOUNT
    return cleaned or TRADEFLOW_GMAIL_ACCOUNT


def smtp_configured() -> bool:
    """Return True when Resend is ready or DEBUG allows console delivery."""
    if (getattr(settings, 'RESEND_API_KEY', '') or '').strip():
        return True
    if settings.DEBUG:
        backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
        return 'console' in backend or 'locmem' in backend
    return False
