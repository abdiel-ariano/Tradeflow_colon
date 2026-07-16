"""Inline static CSS/JS at render time when ``/static/`` links fail.

Useful for CSP-nonce ``<style>`` / ``<script>`` blocks and environments
where collected static URLs are unavailable during local preview.
"""
from __future__ import annotations

from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.utils.safestring import mark_safe

register = template.Library()

_CACHE: dict[str, str] = {}
_JS_CACHE: dict[str, str] = {}


def _read_static(static_path: str, cache: dict[str, str]) -> str:
    """Load a static file once via finders and cache the text body."""
    if static_path in cache:
        return cache[static_path]

    resolved = finders.find(static_path)
    if not resolved:
        return ''

    try:
        content = Path(resolved).read_text(encoding='utf-8')
    except OSError:
        return ''

    cache[static_path] = content
    return content


@register.simple_tag
def inline_css(static_path: str) -> str:
    """Return raw CSS for embedding in a nonce-bearing ``<style>`` tag."""
    content = _read_static(static_path, _CACHE)
    return mark_safe(content) if content else ''


@register.simple_tag
def inline_js(static_path: str) -> str:
    """Return raw JS for embedding in a nonce-bearing ``<script>`` tag."""
    content = _read_static(static_path, _JS_CACHE)
    return mark_safe(content) if content else ''
