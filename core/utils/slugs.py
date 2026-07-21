"""Unique slug helpers for Product and Company SEO URLs."""
from __future__ import annotations

from django.utils.text import slugify


def allocate_unique_slug(model_cls, value: str, *, exclude_pk=None, max_length: int = 200) -> str:
    """Build a unique slug from ``value`` for ``model_cls.slug``."""
    base = slugify(value)[: max_length - 8] or 'item'
    slug = base
    n = 2
    qs = model_cls.objects.all()
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        suffix = f'-{n}'
        slug = f'{base[: max_length - len(suffix)]}{suffix}'
        n += 1
    return slug
