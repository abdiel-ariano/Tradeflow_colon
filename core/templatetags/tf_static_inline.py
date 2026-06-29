"""Inline static CSS at render time when /static/ links are unavailable."""
from __future__ import annotations

from django import template
from django.contrib.staticfiles import finders
from django.utils.safestring import mark_safe

register = template.Library()

_CACHE: dict[str, str] = {}
_JS_CACHE: dict[str, str] = {}


def _read_static(static_path: str, cache: dict[str, str]) -> str:
    if static_path in cache:
        return cache[static_path]

    resolved = finders.find(static_path)
    if not resolved:
        return ''

    try:
        content = resolved.read_text(encoding='utf-8')
    except OSError:
        return ''

    cache[static_path] = content
    return content


@register.simple_tag
def inline_css(static_path: str) -> str:
    """
    Return raw CSS from a static file for embedding in <style nonce="...">.

    Uses staticfiles finders (STATICFILES_DIRS + collected staticfiles).
    """
    content = _read_static(static_path, _CACHE)
    return mark_safe(content) if content else ''


@register.simple_tag
def inline_js(static_path: str) -> str:
    """Return raw JS from a static file for embedding in <script nonce=\"...\">."""
    content = _read_static(static_path, _JS_CACHE)
    return mark_safe(content) if content else ''
