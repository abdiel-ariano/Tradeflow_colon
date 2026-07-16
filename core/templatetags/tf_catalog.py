"""Catalog i18n helpers for category labels and language switch URLs.

Seed categories mix English and Spanish names; filters map them to the
active UI locale without rewriting the database.
"""
from django import template
from core.utils.i18n_urls import tf_translate_url
from core.utils.category_display import category_display_name, category_icon_name

register = template.Library()


@register.filter(name='category_label')
def category_label(value):
    """Localized category display name for the active UI language."""
    return category_display_name(value)


@register.filter(name='category_icon')
def category_icon(value):
    """Material icon name associated with a category label."""
    return category_icon_name(value)


@register.simple_tag(takes_context=True)
def tf_language_next(context, lang_code):
    """Build the ``next`` path for ``/i18n/setlang/`` in the target language."""
    request = context.get('request')
    if not request:
        return '/'
    return tf_translate_url(request.get_full_path(), lang_code)
