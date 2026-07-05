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
    """Public image URL — upload, AI reference WebP, or category icon SVG."""
    if not product:
        return ''
    from core.utils.demo_product_images import (
        ai_placeholder_file_exists,
        ai_placeholder_static_path,
        catalog_seed_static_path,
        picsum_url,
        use_runtime_picsum,
    )
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

    if ai_placeholder_file_exists(product):
        return static(ai_placeholder_static_path(product))

    if use_runtime_picsum():
        return picsum_url(product)

    return static(catalog_seed_static_path(product))


@register.filter
def product_image_is_reference(product):
    from core.utils.demo_product_images import product_uses_ai_reference_image

    return product_uses_ai_reference_image(product)


@register.filter
def product_image_category_icon_src(product):
    from core.utils.demo_product_images import category_icon_static_path

    return static(category_icon_static_path(product)) if product else ''


@register.filter
def product_image_category_seed_src(product):
    """Legacy intermediate fallback for broken remote uploads."""
    from core.utils.demo_product_images import catalog_seed_static_path

    return static(catalog_seed_static_path(product)) if product else ''


@register.filter
def product_image_picsum_src(product):
    from core.utils.demo_product_images import picsum_url, use_runtime_picsum

    if not product or not use_runtime_picsum():
        return ''
    return picsum_url(product)


@register.filter
def product_image_object_position(product):
    """Offset crop focal point so same category seed JPEGs look distinct in grids."""
    if not product or not getattr(product, 'pk', None):
        return '50% 50%'
    pk = product.pk
    x = (pk % 5) * 20
    y = ((pk // 5) % 3) * 30
    return f'{x}% {y}%'


@register.filter
def catalog_card_image_src(product):
    """Alias for product cards — same chain as product_image_src."""
    return product_image_src(product)


@register.filter
def marketplace_visual_image_src(product):
    """Home bento / discover — photo-like catalog seeds instead of SVG icons."""
    if not product:
        return ''
    from core.utils.demo_product_images import (
        ai_placeholder_file_exists,
        ai_placeholder_static_path,
        catalog_seed_static_path,
        picsum_url,
        use_runtime_picsum,
    )
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

    if ai_placeholder_file_exists(product):
        return static(ai_placeholder_static_path(product))

    if use_runtime_picsum():
        return picsum_url(product)

    return static(catalog_seed_static_path(product))
