"""CSP nonce helpers for inline JSON data blocks in templates.

Renders ``<script type="application/json">`` with the same escapes as
Django ``json_script`` plus ``nonce`` from ``request.csp_nonce``.
"""
from __future__ import annotations

import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Match Django.utils.html.json_script so </ or <!-- cannot break out.
_JSON_SCRIPT_ESCAPES = {
    ord('>'): '\\u003E',
    ord('<'): '\\u003C',
    ord('&'): '\\u0026',
}


@register.simple_tag(takes_context=True)
def json_data_block(context, value, element_id: str):
    """Emit a nonce-bearing JSON script tag for client bootstrap data."""
    request = context.get('request')
    nonce = getattr(request, 'csp_nonce', '') if request is not None else ''
    encoded = json.dumps(value, separators=(',', ':')).translate(_JSON_SCRIPT_ESCAPES)
    return format_html(
        '<script id="{}" type="application/json" nonce="{}">{}</script>',
        element_id, nonce, mark_safe(encoded)
    )
