"""Public contact email for TradeFlow Colón (footer, legal, support).

Single source for support address so emails and templates stay aligned
with project branding.
"""
from __future__ import annotations

from django.conf import settings


def tradeflow_contact_email() -> str:
    """Return the canonical support address shown to users."""
    from core.utils.email_config import TRADEFLOW_GMAIL_ACCOUNT

    return (getattr(settings, 'TRADEFLOW_CONTACT_EMAIL', None) or TRADEFLOW_GMAIL_ACCOUNT).strip()


def email_template_context(extra: dict | None = None) -> dict:
    """Merge extra context with contact fields for email templates."""
    ctx = {'tradeflow_contact_email': tradeflow_contact_email()}
    if extra:
        ctx.update(extra)
    return ctx
