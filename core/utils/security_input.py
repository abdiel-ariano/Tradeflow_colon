"""Sanitiza texto de usuario almacenado contra XSS (OWASP).

Elimina HTML de campos de texto libre y endurece identificadores tipo SKU
antes de persistir.
"""
from __future__ import annotations

import html
import re

_STRIP_TAGS = re.compile(r'<[^>]+>')


def sanitize_plain_text(value: str, max_length: int = 5000) -> str:
    """Elimina etiquetas HTML y normaliza texto plano aportado por el usuario."""
    if not value:
        return ''
    text = _STRIP_TAGS.sub('', str(value))
    text = html.unescape(text)
    return text.strip()[:max_length]


def sanitize_identifier(value: str, max_length: int = 80) -> str:
    """Permite solo caracteres alfanuméricos seguros para códigos tipo SKU."""
    cleaned = re.sub(r'[^\w\-.]', '', str(value or ''), flags=re.UNICODE)
    return cleaned[:max_length]
