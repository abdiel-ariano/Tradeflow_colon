from django import template
from django.utils.html import escape, format_html

from core.utils.media_storage import product_image_url

register = template.Library()


@register.simple_tag
def product_img(product, css_class=''):
    url = product_image_url(product)
    name = escape(getattr(product, 'name', 'Producto'))
    return format_html(
        '<img src="{}" alt="{}" class="{}" loading="lazy" decoding="async" '
        'style="object-fit:cover;">',
        url,
        name,
        css_class,
    )


@register.filter
def product_image_src(product):
    return product_image_url(product)
