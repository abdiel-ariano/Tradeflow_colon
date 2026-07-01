"""
URLs y optimización de media enterprise (Supabase Storage / local fallback).
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

log = logging.getLogger('tradeflow.media')

from core.storage.supabase_media import supabase_media_url

PLACEHOLDER_PRODUCT = 'img/logo-icon-color.png'
PRODUCT_IMAGE_FALLBACK_STATIC = 'images/placeholder-producto.svg'


def is_remote_media_storage() -> bool:
    backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    return 's3boto3' in backend.lower() or 's3' in backend.lower()


def local_media_file_exists(rel_path: str) -> bool:
    if not rel_path:
        return False
    return (Path(settings.MEDIA_ROOT) / rel_path).is_file()

# ── Defensas contra uploads maliciosos ─────────────────────────────────────
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_IMAGE_PIXELS = 60_000_000        # anti decompression bomb
ALLOWED_IMAGE_FORMATS = ('JPEG', 'JPG', 'PNG', 'WEBP', 'GIF')


def _serve_local_media_urls() -> bool:
    if settings.DEBUG or getattr(settings, 'SERVE_LOCAL_MEDIA', False):
        return True
    return not is_remote_media_storage()


def product_image_url(product) -> str:
    """Public product image URL, or empty string when unset or unavailable."""
    try:
        if product.image and product.image.name:
            rel_path = product.image.name.replace('\\', '/')
            if local_media_file_exists(rel_path):
                return f'{settings.MEDIA_URL.rstrip("/")}/{rel_path.lstrip("/")}'
            if is_remote_media_storage():
                return supabase_media_url(rel_path)
            if _serve_local_media_urls():
                return product.image.url
    except Exception:
        pass
    return ''


def optimize_uploaded_image(uploaded_file, max_side: int = 1200, quality: int = 85) -> ContentFile:
    """
    Redimensiona JPEG/PNG para catálogo con defensas integradas:
      - Limite de bytes ANTES de decodificar (evita decoder abuse).
      - Limite de pixeles (anti decompression bomb).
      - Validacion de formato real via Pillow (rechaza ejecutables disfrazados).

    Raises:
        ValidationError si el archivo es demasiado grande o no es una imagen real.
    """
    from PIL import Image, UnidentifiedImageError

    # 1) Limite de tamano del archivo subido.
    size = getattr(uploaded_file, 'size', None)
    if size is not None and size > MAX_IMAGE_BYTES:
        raise ValidationError(
            f'Imagen demasiado grande ({size / 1024 / 1024:.1f} MiB). '
            f'Maximo permitido: {MAX_IMAGE_BYTES / 1024 / 1024:.0f} MiB.'
        )

    # 2) Aplica el limite anti-bomba de Pillow.
    _prev_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        uploaded_file.seek(0)
        try:
            img = Image.open(uploaded_file)
            img.verify()  # chequea integridad sin decodificar todo el raster.
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValidationError(f'Archivo no es una imagen valida: {exc}')

        # verify() consume el stream — hay que reabrirlo.
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)

        # 3) Validacion de formato real (por bytes, no por extension).
        fmt = (img.format or '').upper()
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError(
                f'Formato de imagen no permitido ({fmt or "desconocido"}). '
                f'Permitidos: {", ".join(ALLOWED_IMAGE_FORMATS)}.'
            )

        # 4) Conversion + redimensionado.
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / float(max(w, h))
            img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        buf.seek(0)
        name = getattr(uploaded_file, 'name', 'product.jpg')
        if not name.lower().endswith('.jpg'):
            name = name.rsplit('.', 1)[0] + '.jpg'
        return ContentFile(buf.read(), name=name)
    finally:
        Image.MAX_IMAGE_PIXELS = _prev_limit
