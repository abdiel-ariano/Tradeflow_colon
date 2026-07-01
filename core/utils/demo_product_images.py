"""
Helpers for demo product image management commands.

Production uses Supabase S3 (django-storages). The default storage checks
HeadObject before upload (file_overwrite=False), which often returns 403.
These helpers support explicit local filesystem writes and a safer remote path.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage

from core.models import Product

log = logging.getLogger('tradeflow.demo_images')

PICSUM_SIZE = '400/300'

CATEGORY_KEYWORDS = {
    'textiles': ['textile', 'fabric', 'clothing', 'uniform', 'apparel'],
    'electronics': ['electronic', 'gadget', 'computer', 'phone', 'tech'],
    'home_appliances': ['appliance', 'kitchen', 'home', 'household'],
    'beauty': ['beauty', 'cosmetic', 'perfume', 'fragrance', 'personal care'],
    'toys': ['toy', 'game', 'children'],
    'general': ['wholesale', 'bulk', 'merchandise', 'general'],
}

BRAND_COLORS = [
    (15, 42, 68),
    (27, 59, 99),
    (46, 91, 138),
    (242, 101, 34),
]


def category_keyword(product: Product) -> str:
    if not product.category_id or not product.category:
        return 'general'
    cat_name = product.category.name.lower()
    for key, hints in CATEGORY_KEYWORDS.items():
        if key.replace('_', ' ') in cat_name or key in cat_name:
            return key
        if any(hint in cat_name for hint in hints):
            return key
    return 'general'


def seed_slug(product: Product) -> str:
    raw = f'{product.pk}_{product.name[:40]}'
    return re.sub(r'[^a-zA-Z0-9_-]', '_', raw)


def picsum_url(product: Product) -> str:
    return f'https://picsum.photos/seed/{seed_slug(product)}/{PICSUM_SIZE}'


def extract_initials(name: str) -> str:
    """First letter of first two words, or first two letters of a single word."""
    words = [w for w in (name or '').split() if w]
    if len(words) >= 2:
        return f'{words[0][0]}{words[1][0]}'.upper()
    if len(words) == 1 and len(words[0]) >= 2:
        return words[0][:2].upper()
    if len(words) == 1 and len(words[0]) == 1:
        return words[0][0].upper()
    return 'NA'


def placeholder_relative_path(product: Product) -> str:
    initials = extract_initials(product.name)
    return f'productos/placeholders/placeholder_{product.pk}_{initials}.png'


def assign_product_image(product: Product, *, log_fn=None) -> str:
    """
    Generate a brand placeholder PNG, write to MEDIA_ROOT/productos/, return relative path.

    Requires product.pk. Raises if the file is missing or zero bytes after write.
    """
    if not product.pk:
        raise ValueError('Product must be saved before assigning an image')

    content = generate_placeholder_bytes(product)
    if not content:
        raise ValueError(f'Empty image bytes for product {product.pk}')

    rel_path = placeholder_relative_path(product)
    write_local_image(rel_path, content)

    full_path = Path(settings.MEDIA_ROOT) / rel_path
    if not full_path.is_file() or full_path.stat().st_size == 0:
        raise OSError(f'Image file missing or empty after write: {full_path}')

    if log_fn:
        log_fn(f'Generated image for {product.name} → {rel_path}')
    return rel_path


def relative_image_path(product: Product) -> str:
    return f'products/demo/product_{product.pk}.jpg'


def is_remote_storage() -> bool:
    backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    return 's3boto3' in backend.lower() or 's3' in backend.lower()


def local_media_storage() -> FileSystemStorage:
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)


def write_local_image(rel_path: str, content: bytes) -> str:
    """Write bytes to MEDIA_ROOT/rel_path (overwrites if exists)."""
    full_path = Path(settings.MEDIA_ROOT) / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    return rel_path.replace('\\', '/')


def remote_command_storage():
    """S3 storage for management commands — skip HeadObject via file_overwrite."""
    backend = settings.STORAGES['default']['BACKEND']
    options = dict(settings.STORAGES['default'].get('OPTIONS', {}))
    options['file_overwrite'] = True
    options['default_acl'] = None
    from django.utils.module_loading import import_string

    storage_cls = import_string(backend)
    return storage_cls(**options)


def save_product_image_bytes(
    product: Product,
    content: bytes,
    *,
    storage_mode: str = 'local',
) -> str:
    """
    Persist image bytes and update Product.image.

    storage_mode:
      - local: always write to MEDIA_ROOT (default, no S3 HeadObject)
      - remote: upload via S3-compatible storage
      - auto: try remote, fall back to local on failure
    """
    rel_path = relative_image_path(product)
    file_obj = ContentFile(content)

    if storage_mode == 'local':
        saved = write_local_image(rel_path, content)
        Product.objects.filter(pk=product.pk).update(image=saved)
        return saved

    if storage_mode in ('remote', 'auto'):
        try:
            storage = remote_command_storage() if storage_mode == 'remote' else remote_command_storage()
            saved = storage.save(rel_path, file_obj)
            Product.objects.filter(pk=product.pk).update(image=saved)
            return saved
        except Exception as exc:
            if storage_mode == 'remote':
                raise
            log.warning('Remote storage failed for product %s (%s); using local.', product.pk, exc)
            saved = write_local_image(rel_path, content)
            Product.objects.filter(pk=product.pk).update(image=saved)
            return saved

    raise ValueError(f'Unknown storage_mode: {storage_mode}')


def generate_placeholder_bytes(product: Product) -> bytes:
    """400×400 PNG with vertical brand gradient and centered white initials."""
    from PIL import Image, ImageDraw, ImageFont

    size = 400
    top_rgb = (0x1B, 0x3B, 0x63)
    bottom_rgb = (0x2E, 0x5B, 0x8A)
    initials = extract_initials(product.name)

    img = Image.new('RGB', (size, size), top_rgb)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(size - 1, 1)
        color = tuple(
            int(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * t)
            for i in range(3)
        )
        draw.line([(0, y), (size, y)], fill=color)

    font_candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ]
    font = ImageFont.load_default()
    for path in font_candidates:
        if Path(path).is_file():
            font = ImageFont.truetype(path, 120)
            break

    bbox = draw.textbbox((0, 0), initials, font=font)
    x = (size - (bbox[2] - bbox[0])) / 2
    y = (size - (bbox[3] - bbox[1])) / 2
    draw.text((x, y), initials, fill=(255, 255, 255), font=font)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def save_placeholder_for_product(
    product: Product,
    content: bytes,
    *,
    storage_mode: str = 'local',
) -> str:
    """Save PNG placeholder and assign product.image (idempotent path per product)."""
    rel_path = placeholder_relative_path(product)

    if storage_mode == 'local':
        write_local_image(rel_path, content)
        Product.objects.filter(pk=product.pk).update(image=rel_path)
        return rel_path

    if storage_mode in ('remote', 'auto'):
        try:
            storage = remote_command_storage()
            saved = storage.save(rel_path, ContentFile(content))
            Product.objects.filter(pk=product.pk).update(image=saved)
            return saved
        except Exception as exc:
            if storage_mode == 'remote':
                raise
            log.warning('Remote storage failed for product %s (%s); using local.', product.pk, exc)
            write_local_image(rel_path, content)
            Product.objects.filter(pk=product.pk).update(image=rel_path)
            return rel_path

    raise ValueError(f'Unknown storage_mode: {storage_mode}')


def storage_mode_help() -> str:
    if is_remote_storage():
        return (
            'local (default): write to MEDIA_ROOT — safe in Docker/CI. '
            'remote: upload to Supabase/S3 (needs bucket permissions). '
            'auto: remote with local fallback.'
        )
    return 'local (default). remote/auto only apply when S3 storage is configured.'
