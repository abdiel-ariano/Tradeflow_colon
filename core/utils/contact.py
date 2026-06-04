"""Public contact email for TradeFlow Colón (footer, legal, support copy)."""
from __future__ import annotations

from django.conf import settings


def tradeflow_contact_email() -> str:
    """Canonical support/contact address shown to users."""
    return (getattr(settings, 'TRADEFLOW_CONTACT_EMAIL', None) or 'info@tradeflow.pa').strip()


def email_template_context(extra: dict | None = None) -> dict:
    """Context for ``render_to_string`` on emails (no HTTP request)."""
    ctx = {'tradeflow_contact_email': tradeflow_contact_email()}
    if extra:
        ctx.update(extra)
    return ctx
