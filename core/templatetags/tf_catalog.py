"""
Django template tags — catalog i18n and category display.

- ``category_label`` / ``category_icon`` — localized category name and Material icon.
- ``tf_language_next`` — builds ``next`` URL for ``/i18n/setlang/`` (EN unprefixed, ES /es/).
"""
from django import template
from core.utils.i18n_urls import tf_translate_url
from core.utils.category_display import category_display_name, category_icon_name

register = template.Library()


@register.filter(name='category_label')
def category_label(value):
    """Category label."""
    return category_display_name(value)


@register.filter(name='category_icon')
def category_icon(value):
    """Category icon."""
    return category_icon_name(value)


@register.simple_tag(takes_context=True)
def tf_language_next(context, lang_code):
    """Translate current path to the target language for set_language redirects."""
    request = context.get('request')
    if not request:
        return '/'
    return tf_translate_url(request.get_full_path(), lang_code)
