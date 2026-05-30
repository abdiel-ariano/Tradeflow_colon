"""
URLs y optimización de media enterprise (Supabase Storage / local fallback).
"""
from __future__ import annotations

import io
import logging

from django.conf import settings
from django.core.files.base import ContentFile

log = logging.getLogger('tradeflow.media')

PLACEHOLDER_PRODUCT = 'img/logo-icon-color.png'


def product_image_url(product) -> str:
    """URL pública de imagen de producto o placeholder de marca."""
    try:
        if product.image and product.image.name:
            return product.image.url
    except Exception:
        pass
    return f'{settings.STATIC_URL.rstrip("/")}/{PLACEHOLDER_PRODUCT}'


def optimize_uploaded_image(uploaded_file, max_side: int = 1200, quality: int = 85) -> ContentFile:
    """
    Redimensiona JPEG/PNG para catálogo (menor peso, carga mobile más rápida).

    Returns:
        ContentFile listo para guardar en ImageField.
    """
    from PIL import Image

    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
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
