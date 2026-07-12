"""
TradeFlow — server-side cache helpers for public pages and merchandising.

Uses Django's cache framework (Redis when REDIS_URL is set, else DB or LocMem).
Invalidate via signals when catalog, CMS, or order data changes.
On backend errors (missing cache table, Redis down), falls back to uncached ORM.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import get_language

log = logging.getLogger(__name__)

T = TypeVar('T')

HOME_STATS_KEY = 'merch:home_stats'
HOME_CTX_KEY = 'merch:home_ctx:{lang}'
NAV_CATEGORIES_KEY = 'merch:nav_categories'
CATALOG_CATEGORIES_KEY = 'merch:catalog_categories'
CATALOG_EMPRESAS_KEY = 'merch:catalog_empresas'
API_HOME_MERCH_KEY = 'merch:api_home_v2'

_SUPPORTED_LANGS = ('es', 'en')


def cache_ttl(setting_name: str, default: int) -> int:
    """Cache ttl."""
    return int(getattr(settings, setting_name, default))


def _cache_get(key: str) -> Any:
    try:
        return cache.get(key)
    except Exception as exc:
        log.warning('cache get failed key=%s: %s', key, exc, exc_info=True)
        return None


def _cache_set(key: str, value: Any, timeout: int) -> None:
    try:
        cache.set(key, value, timeout)
    except Exception as exc:
        log.warning('cache set failed key=%s: %s', key, exc, exc_info=True)


def _cache_delete_many(keys: list[str]) -> None:
    if not keys:
        return
    try:
        cache.delete_many(keys)
    except Exception as exc:
        log.warning('cache delete_many failed: %s', exc, exc_info=True)


def get_or_set(key: str, timeout: int, factory: Callable[[], T]) -> T:
    """Read-through cache with a callable producer; never raises on cache errors."""
    cached = _cache_get(key)
    if cached is not None:
        return cached
    value = factory()
    _cache_set(key, value, timeout)
    return value


def invalidate_merchandising_cache() -> None:
    """Drop merchandising and public-page cache entries."""
    keys = [
        HOME_STATS_KEY,
        NAV_CATEGORIES_KEY,
        CATALOG_CATEGORIES_KEY,
        CATALOG_EMPRESAS_KEY,
        API_HOME_MERCH_KEY,
        *[HOME_CTX_KEY.format(lang=lang) for lang in _SUPPORTED_LANGS],
    ]
    _cache_delete_many(keys)


def cached_home_stats() -> dict[str, Any]:
    """Cached home stats."""
    from core import merchandising as merch

    return get_or_set(
        HOME_STATS_KEY,
        cache_ttl('CACHE_TTL_STATS', 300),
        merch.home_stats_uncached,
    )


def cached_nav_categories() -> list:
    """Cached nav categories."""
    from django.db.models import Count, Q

    from core.models import Category

    def _load():
        return list(
            Category.objects.annotate(
                num_productos=Count('products', filter=Q(products__is_active=True)),
            )
            .filter(num_productos__gt=0)
            .order_by('-num_productos', 'name')[:10]
        )

    return get_or_set(
        NAV_CATEGORIES_KEY,
        cache_ttl('CACHE_TTL_NAV', 600),
        _load,
    )


def cached_catalog_categories() -> list:
    """Cached catalog categories."""
    from django.db.models import Count, Q

    from core.models import Category

    def _load():
        return list(
            Category.objects.annotate(
                num_productos=Count('products', filter=Q(products__is_active=True)),
            )
            .filter(num_productos__gt=0)
            .order_by('name')
        )

    return get_or_set(
        CATALOG_CATEGORIES_KEY,
        cache_ttl('CACHE_TTL_CATALOG_META', 300),
        _load,
    )


def cached_catalog_empresas() -> list:
    """Cached catalog empresas."""
    from django.db.models import Count, Q

    from core.models import Company

    def _load():
        return list(
            Company.objects.annotate(
                num_productos=Count('products', filter=Q(products__is_active=True)),
            )
            .filter(num_productos__gt=0)
            .order_by('name')
        )

    return get_or_set(
        CATALOG_EMPRESAS_KEY,
        cache_ttl('CACHE_TTL_CATALOG_META', 300),
        _load,
    )


def cached_guest_home_context(lang: str | None = None) -> dict[str, Any]:
    """Cached guest home context."""
    from core import merchandising as merch

    lang_code = (lang or get_language() or settings.LANGUAGE_CODE)[:2]
    if lang_code not in _SUPPORTED_LANGS:
        lang_code = settings.LANGUAGE_CODE[:2]

    return get_or_set(
        HOME_CTX_KEY.format(lang=lang_code),
        cache_ttl('CACHE_TTL_HOME', 120),
        lambda: merch.build_guest_home_context(lang_code),
    )


def cached_api_home_merchandising() -> dict[str, Any]:
    """Cached api home merchandising."""
    from core import merchandising as merch

    def _load():
        sections = []
        for section in merch.active_home_sections():
            sections.append({
                'slug': section.slug,
                'type': section.section_type,
                'title_es': section.title_es,
                'title_en': section.title_en or section.title_es,
                'product_ids': [p.pk for p in merch.resolve_section_products(section)],
            })
        return {
            'daily_deals': [p.pk for p in merch.daily_deals(12)],
            'bestsellers': [p.pk for p in merch.bestsellers(12)],
            'featured': [p.pk for p in merch.featured_products(12)],
            'sections': sections,
            'stats': cached_home_stats(),
        }

    return get_or_set(
        API_HOME_MERCH_KEY,
        cache_ttl('CACHE_TTL_HOME', 120),
        _load,
    )
