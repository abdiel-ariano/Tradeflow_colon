"""Resuelve y optimiza media de productos para Supabase o almacenamiento local.

Las tarjetas públicas del catálogo necesitan URLs estables; las subidas se
redimensionan y escanean antes de entrar a inventarios de vendedores ZLC.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

log = logging.getLogger('tradeflow.media')

PLACEHOLDER_PRODUCT = 'img/logo-icon-color.png'
PRODUCT_IMAGE_FALLBACK_STATIC = 'images/placeholder-producto.svg'


def is_remote_media_storage() -> bool:
    """Devuelve True cuando el backend STORAGES por defecto es compatible con S3."""
    backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    return 's3boto3' in backend.lower() or 's3' in backend.lower()


def local_media_file_exists(rel_path: str) -> bool:
    """Devuelve True cuando una ruta relativa de media existe en disco."""
    if not rel_path:
        return False
    return (Path(settings.MEDIA_ROOT) / rel_path).is_file()

# ── Defenses against malicious uploads ───────────────────────────────────
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_IMAGE_PIXELS = 60_000_000        # anti decompression bomb
ALLOWED_IMAGE_FORMATS = ('JPEG', 'JPG', 'PNG', 'WEBP', 'GIF')


def _serve_local_media_urls() -> bool:
    """Devuelve True cuando debe usarse MEDIA_URL local para imágenes de producto."""
    if settings.DEBUG or getattr(settings, 'SERVE_LOCAL_MEDIA', False):
        return True
    return not is_remote_media_storage()


def product_image_url(product) -> str:
    """Devuelve la URL pública de imagen del producto, o cadena vacía si no hay."""
    try:
        if product.image and product.image.name:
            rel_path = product.image.name.replace('\\', '/')
            if local_media_file_exists(rel_path):
                return f'{settings.MEDIA_URL.rstrip("/")}/{rel_path.lstrip("/")}'
            if is_remote_media_storage():
                # Delegate URL generation to the selected backend. Supabase
                # returns a native object URL; AWS S3 returns a private,
                # short-lived SigV4 URL using the EC2 instance role.
                return product.image.url
            if _serve_local_media_urls():
                return product.image.url
    except Exception:
        pass
    return ''


def optimize_uploaded_image(uploaded_file, max_side: int = 1200, quality: int = 85) -> ContentFile:
    """Redimensiona y re-codifica subidas del catálogo con defensas de tamaño/formato.


    Rechaza archivos demasiado grandes, bombas de descompresión y payloads no imagen
    antes de que los vendedores publiquen fotos del catálogo ZLC.
    """
    from PIL import Image, UnidentifiedImageError

    # 1) Uploaded file size limit.
    size = getattr(uploaded_file, 'size', None)
    if size is not None and size > MAX_IMAGE_BYTES:
        raise ValidationError(
            f'Imagen demasiado grande ({size / 1024 / 1024:.1f} MiB). '
            f'Maximo permitido: {MAX_IMAGE_BYTES / 1024 / 1024:.0f} MiB.'
        )

    # 2) Apply Pillow anti-decompression-bomb limit.
    _prev_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        uploaded_file.seek(0)
        try:
            img = Image.open(uploaded_file)
            img.verify()  # chequea integridad sin decodificar todo el raster.
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValidationError(f'Archivo no es una imagen valida: {exc}')

        # verify() consumes the stream — reopen it.
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)

        # 3) Validate real format (by bytes, not extension).
        fmt = (img.format or '').upper()
        if fmt not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError(
                f'Formato de imagen no permitido ({fmt or "desconocido"}). '
                f'Permitidos: {", ".join(ALLOWED_IMAGE_FORMATS)}.'
            )

        # 4) Conversion + resize.
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
