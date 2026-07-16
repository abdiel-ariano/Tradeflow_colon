"""Product image URL filters and tags for catalog and home surfaces.

Resolve the same chain as the catalog: upload → Supabase URL → AI
placeholder WebP → category seed → optional Picsum fallback.
"""
from django import template
from django.templatetags.static import static
from django.utils.html import escape, format_html

from core.utils.media_storage import PRODUCT_IMAGE_FALLBACK_STATIC, product_image_url

register = template.Library()


@register.simple_tag
def product_img(product, css_class=''):
    """Render a lazy-loaded product ``<img>`` with onerror fallback."""
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
    """Public image URL: upload, AI WebP, seed SVG/JPEG, or Picsum."""
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
    """Return True when the product shows an AI reference placeholder."""
    from core.utils.demo_product_images import product_uses_ai_reference_image

    return product_uses_ai_reference_image(product)


@register.filter
def product_image_category_icon_src(product):
    """Static category icon SVG path for product image fallbacks."""
    from core.utils.demo_product_images import category_icon_static_path

    return static(category_icon_static_path(product)) if product else ''


@register.filter
def product_image_category_seed_src(product):
    """Legacy seed static path for broken remote upload fallbacks."""
    from core.utils.demo_product_images import catalog_seed_static_path

    return static(catalog_seed_static_path(product)) if product else ''


@register.filter
def product_image_picsum_src(product):
    """Picsum URL when runtime photo placeholders are enabled."""
    from core.utils.demo_product_images import picsum_url, use_runtime_picsum

    if not product or not use_runtime_picsum():
        return ''
    return picsum_url(product)


@register.filter
def product_image_object_position(product):
    """Vary crop focal point so shared category seeds look distinct."""
    if not product or not getattr(product, 'pk', None):
        return '50% 50%'
    pk = product.pk
    x = (pk % 5) * 20
    y = ((pk // 5) % 3) * 30
    return f'{x}% {y}%'


@register.filter
def catalog_card_image_src(product):
    """Alias for product cards — same chain as ``product_image_src``."""
    return product_image_src(product)


@register.filter
def marketplace_visual_image_src(product):
    """Home bento/discover image URL preferring photo-like seeds."""
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
