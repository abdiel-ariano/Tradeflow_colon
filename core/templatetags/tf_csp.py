r"""
Template tags y filtros para integrarse con CSP nonce.

Casos de uso:
  {% load tf_csp %}
  {% json_data_block tf_i18n "tf-i18n-data" %}

Eso renderiza un `<script type="application/json" id="tf-i18n-data"
nonce="...">{ ... }</script>` con el JSON escapado de forma segura
(igual que el filter built-in `json_script` de Django, pero anadiendo
el nonce CSP que toma de `request.csp_nonce`).
"""
from __future__ import annotations

import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Escapes identicos a los que hace Django.utils.html.json_script para que
# JSON con `</` o `<!--` no termine el bloque <script> ni inicie HTML comments.
_JSON_SCRIPT_ESCAPES = {
    ord('>'): '\\u003E',
    ord('<'): '\\u003C',
    ord('&'): '\\u0026',
}


@register.simple_tag(takes_context=True)
def json_data_block(context, value, element_id: str):
    """Como `{{ value|json_script:"id" }}` pero anadiendo nonce CSP."""
    request = context.get('request')
    nonce = getattr(request, 'csp_nonce', '') if request is not None else ''
    encoded = json.dumps(value, separators=(',', ':')).translate(_JSON_SCRIPT_ESCAPES)
    return format_html(
        '<script id="{}" type="application/json" nonce="{}">{}</script>',
        element_id, nonce, mark_safe(encoded)
    )
