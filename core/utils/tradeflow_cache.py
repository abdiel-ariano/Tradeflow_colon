"""Caché de servidor para merchandising público y páginas de invitados.

Arquitectura de backends (en orden de preferencia vía settings):

* **Redis** (`REDIS_URL`) — caché compartida entre workers Gunicorn.
* **DatabaseCache** (`USE_DB_CACHE=true`) — tabla Django compartida sin Redis.
* **LocMem** — fallback local por proceso; útil en desarrollo.

Si el backend falla (tabla ausente, Redis caído, etc.), ``get_or_set`` y los
helpers seguros degradan a ORM sin caché para que el catálogo ZLC siga
respondiendo.

Invalidación: ``invalidate_merchandising_cache()`` borra todas las claves
``merch:*`` conocidas. Se dispara desde señales en ``core/signals_cache.py``
al mutar Product, Company, Category, HomePromoSection u Order (status).
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
CATALOG_MARKET_CTX_KEY = 'merch:catalog_market_ctx'
VERIFIED_COMPANIES_KEY = 'merch:verified_companies_count'
API_HOME_MERCH_KEY = 'merch:api_home_v2'
ACTIVE_COMPANY_IDS_KEY = 'merch:active_company_ids'
SPOTLIGHTS_KEY = 'merch:spotlights:{per}:{cats}'
MEGA_MENU_KEY = 'merch:buyer_mega:{cats}:{per}'
SELLER_DASH_KEY = 'seller:dash:{company_id}:{days}'
EXPIRE_PENDING_ORDERS_KEY = 'ops:expire_pending_orders'

_SUPPORTED_LANGS = ('es', 'en')


def cache_ttl(setting_name: str, default: int) -> int:
    """Lee un TTL entero desde settings, con valor por defecto."""
    return int(getattr(settings, setting_name, default))


def _cache_get(key: str) -> Any:
    """``cache.get`` seguro: devuelve None si el backend falla."""
    try:
        return cache.get(key)
    except Exception as exc:
        log.warning('cache get failed key=%s: %s', key, exc, exc_info=True)
        return None


def _cache_set(key: str, value: Any, timeout: int) -> None:
    """``cache.set`` seguro: ignora errores del backend."""
    try:
        cache.set(key, value, timeout)
    except Exception as exc:
        log.warning('cache set failed key=%s: %s', key, exc, exc_info=True)


def _cache_delete_many(keys: list[str]) -> None:
    """``cache.delete_many`` seguro: ignora errores del backend."""
    if not keys:
        return
    try:
        cache.delete_many(keys)
    except Exception as exc:
        log.warning('cache delete_many failed: %s', exc, exc_info=True)


def get_or_set(key: str, timeout: int, factory: Callable[[], T]) -> T:
    """Caché read-through con factory; nunca lanza por errores de caché."""
    cached = _cache_get(key)
    if cached is not None:
        return cached
    value = factory()
    _cache_set(key, value, timeout)
    return value


def invalidate_merchandising_cache() -> None:
    """Elimina claves de merchandising y páginas públicas tras cambios de catálogo."""
    keys = [
        HOME_STATS_KEY,
        NAV_CATEGORIES_KEY,
        CATALOG_CATEGORIES_KEY,
        CATALOG_EMPRESAS_KEY,
        CATALOG_MARKET_CTX_KEY,
        VERIFIED_COMPANIES_KEY,
        API_HOME_MERCH_KEY,
        ACTIVE_COMPANY_IDS_KEY,
        # Default catalog/home spotlight + mega-menu shapes.
        SPOTLIGHTS_KEY.format(per=4, cats=4),
        MEGA_MENU_KEY.format(cats=8, per=6),
        *[HOME_CTX_KEY.format(lang=lang) for lang in _SUPPORTED_LANGS],
    ]
    _cache_delete_many(keys)


def cached_marketplace_active_company_ids() -> list[int]:
    """IDs de empresas visibles en marketplace (caché corto, compartido)."""
    from core.utils.seller_lifecycle import marketplace_active_company_ids_uncached

    return get_or_set(
        ACTIVE_COMPANY_IDS_KEY,
        cache_ttl('CACHE_TTL_ACTIVE_COMPANIES', 120),
        marketplace_active_company_ids_uncached,
    )


def cached_category_spotlights(limit_per_cat: int = 4, max_cats: int = 4) -> list:
    """Filas spotlight del catálogo/home (caché; sin exclude_ids)."""
    from core import merchandising as merch

    return get_or_set(
        SPOTLIGHTS_KEY.format(per=limit_per_cat, cats=max_cats),
        cache_ttl('CACHE_TTL_SPOTLIGHTS', 120),
        lambda: merch.category_spotlights(limit_per_cat, max_cats),
    )


def cached_buyer_mega_menu_panels(
    limit_categories: int = 8,
    products_per: int = 6,
) -> list:
    """Paneles del mega-menú buyer (caché)."""
    from core import merchandising as merch

    return get_or_set(
        MEGA_MENU_KEY.format(cats=limit_categories, per=products_per),
        cache_ttl('CACHE_TTL_MEGA_MENU', 180),
        lambda: merch.buyer_mega_menu_panels(limit_categories, products_per),
    )


def cached_seller_portal_dashboard(company_id: int, days: int = 30) -> dict[str, Any]:
    """KPIs del home ``/mi-tienda/`` por empresa (caché corto)."""
    from core.models import Company
    from core.utils.seller_analytics import seller_portal_dashboard

    def _load():
        company = Company.objects.get(pk=company_id)
        return seller_portal_dashboard(company, days=days)

    return get_or_set(
        SELLER_DASH_KEY.format(company_id=company_id, days=days),
        cache_ttl('CACHE_TTL_SELLER_DASH', 45),
        _load,
    )


def maybe_expire_pending_orders(*, min_interval: int = 60) -> None:
    """Ejecuta ``expire_pending_orders`` como máximo una vez por intervalo."""
    if _cache_get(EXPIRE_PENDING_ORDERS_KEY) is not None:
        return
    from core.utils.order_workflow import expire_pending_orders

    expire_pending_orders()
    _cache_set(EXPIRE_PENDING_ORDERS_KEY, 1, min_interval)


def cached_home_stats() -> dict[str, Any]:
    """Estadísticas del marketplace para la home de invitados (caché)."""
    from core import merchandising as merch

    return get_or_set(
        HOME_STATS_KEY,
        cache_ttl('CACHE_TTL_STATS', 300),
        merch.home_stats_uncached,
    )


def cached_nav_categories() -> list:
    """Categorías top para la navegación del header (caché)."""
    from django.db.models import Count, Q

    from core.models import Category

    def _load():
        """Carga categorías con conteo de productos activos."""
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
    """Categorías con productos activos para filtros del catálogo (caché)."""
    from django.db.models import Count, Q

    from core.models import Category

    def _load():
        """Carga todas las categorías que aún tienen productos activos."""
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
    """Empresas visibles en marketplace con productos activos (caché)."""
    from django.db.models import Count, Q

    from core.models import Company

    def _load():
        """Carga empresas visibles en marketplace con catálogo activo."""
        from core.utils.seller_lifecycle import marketplace_active_company_ids

        visible_ids = marketplace_active_company_ids()
        return list(
            Company.objects.filter(pk__in=visible_ids)
            .annotate(
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


def cached_marketplace_categories_context() -> dict[str, Any]:
    """Contexto de categorías del marketplace (rail/modal) con caché."""
    from core import merchandising as merch

    return get_or_set(
        CATALOG_MARKET_CTX_KEY,
        cache_ttl('CACHE_TTL_CATALOG_META', 300),
        merch.marketplace_categories_context,
    )


def cached_verified_company_count() -> int:
    """Cuenta empresas verificadas con al menos un producto activo (caché)."""
    from core.models import Company

    def _load():
        """Misma consulta que usaba catalogo_publico sin caché."""
        return (
            Company.objects.filter(is_verified=True, products__is_active=True)
            .distinct()
            .count()
        )

    return get_or_set(
        VERIFIED_COMPANIES_KEY,
        cache_ttl('CACHE_TTL_CATALOG_META', 300),
        _load,
    )


def cached_guest_home_context(lang: str | None = None) -> dict[str, Any]:
    """Contexto de plantilla de la home de invitados por idioma (caché)."""
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
    """Payload JSON de merchandising de home para la API pública (caché)."""
    from core import merchandising as merch

    def _load():
        """Arma secciones de home y listas de IDs de productos."""
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
