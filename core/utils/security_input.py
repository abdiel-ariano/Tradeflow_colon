"""Sanitize stored user text against XSS (OWASP).

Strips HTML from free-text fields and tightens SKU-like identifiers
before persistence.
"""
from __future__ import annotations

import html
import re

_STRIP_TAGS = re.compile(r'<[^>]+>')


def sanitize_plain_text(value: str, max_length: int = 5000) -> str:
    """Strip HTML tags and normalize user-provided plain text."""
    if not value:
        return ''
    text = _STRIP_TAGS.sub('', str(value))
    text = html.unescape(text)
    return text.strip()[:max_length]


def sanitize_identifier(value: str, max_length: int = 80) -> str:
    """Allow only safe alphanumeric characters for SKU-like codes."""
    cleaned = re.sub(r'[^\w\-.]', '', str(value or ''), flags=re.UNICODE)
    return cleaned[:max_length]
