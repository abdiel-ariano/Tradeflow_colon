"""
Sanitización de entrada (OWASP — XSS en texto almacenado).
"""
from __future__ import annotations

import html
import re

_STRIP_TAGS = re.compile(r'<[^>]+>')


def sanitize_plain_text(value: str, max_length: int = 5000) -> str:
    """Elimina tags HTML y normaliza texto de usuario."""
    if not value:
        return ''
    text = _STRIP_TAGS.sub('', str(value))
    text = html.unescape(text)
    return text.strip()[:max_length]


def sanitize_identifier(value: str, max_length: int = 80) -> str:
    """SKU/códigos: alfanumérico seguro."""
    cleaned = re.sub(r'[^\w\-.]', '', str(value or ''), flags=re.UNICODE)
    return cleaned[:max_length]
