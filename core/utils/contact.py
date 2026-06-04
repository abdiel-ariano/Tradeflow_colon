"""Public contact email for TradeFlow Colón (footer, legal, support copy)."""
from __future__ import annotations

from django.conf import settings


def tradeflow_contact_email() -> str:
    """Canonical support/contact address shown to users."""
    from core.utils.email_config import TRADEFLOW_GMAIL_ACCOUNT

    return (getattr(settings, 'TRADEFLOW_CONTACT_EMAIL', None) or TRADEFLOW_GMAIL_ACCOUNT).strip()


def email_template_context(extra: dict | None = None) -> dict:
    """Context for ``render_to_string`` on emails (no HTTP request)."""
    ctx = {'tradeflow_contact_email': tradeflow_contact_email()}
    if extra:
        ctx.update(extra)
    return ctx
