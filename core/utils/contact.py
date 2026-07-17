"""Correo de contacto público de TradeFlow Colón (pie, legal, soporte).

Fuente única de la dirección de soporte para alinear correos y plantillas
con la marca del proyecto.
"""
from __future__ import annotations

from django.conf import settings


def tradeflow_contact_email() -> str:
    """Devuelve la dirección canónica de soporte mostrada a los usuarios."""
    from core.utils.email_config import TRADEFLOW_GMAIL_ACCOUNT

    return (getattr(settings, 'TRADEFLOW_CONTACT_EMAIL', None) or TRADEFLOW_GMAIL_ACCOUNT).strip()


def email_template_context(extra: dict | None = None) -> dict:
    """Combina contexto extra con campos de contacto para plantillas de correo."""
    ctx = {'tradeflow_contact_email': tradeflow_contact_email()}
    if extra:
        ctx.update(extra)
    return ctx
