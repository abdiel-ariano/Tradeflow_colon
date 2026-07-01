from django import template
from django.templatetags.static import static
from django.utils.html import escape, format_html

from core.utils.media_storage import PRODUCT_IMAGE_FALLBACK_STATIC, product_image_url

register = template.Library()


@register.simple_tag
def product_img(product, css_class=''):
    url = product_image_url(product) or static(PRODUCT_IMAGE_FALLBACK_STATIC)
    name = escape(getattr(product, 'name', 'Product'))
    fallback = static(PRODUCT_IMAGE_FALLBACK_STATIC)
    return format_html(
        '<img src="{}" alt="{}" class="{}" loading="lazy" decoding="async" '
        'data-tf-product-image onerror="this.onerror=null;this.src=\'{}\';" '
        'style="object-fit:cover;">',
        url,
        name,
        css_class,
        fallback,
    )


@register.filter
def product_image_src(product):
    """Public image URL with deterministic demo fallback for catalog/home cards."""
    url = product_image_url(product)
    if url:
        return url
    from core.utils.demo_product_images import picsum_url

    return picsum_url(product)


@register.filter
def catalog_card_image_src(product):
    """Alias for product cards — same chain as product_image_src."""
    return product_image_src(product)
