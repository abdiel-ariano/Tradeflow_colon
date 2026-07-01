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
    """Public image URL — verified local file, remote URL, or picsum demo seed."""
    if not product:
        return ''
    from core.utils.demo_product_images import picsum_url
    from core.utils.media_storage import is_remote_media_storage, local_media_file_exists, product_image_url

    rel = ''
    if getattr(product, 'image', None) and product.image.name:
        rel = product.image.name.replace('\\', '/')

    if rel:
        if is_remote_media_storage():
            url = product_image_url(product)
            if url:
                return url
        elif local_media_file_exists(rel):
            return product_image_url(product)

    return picsum_url(product)


@register.filter
def product_image_picsum_src(product):
    from core.utils.demo_product_images import picsum_url

    return picsum_url(product) if product else ''


@register.filter
def catalog_card_image_src(product):
    """Alias for product cards — same chain as product_image_src."""
    return product_image_src(product)
