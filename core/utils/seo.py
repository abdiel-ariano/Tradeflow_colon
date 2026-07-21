"""SEO helpers: absolute URLs, robots, slugs, hreflang, JSON-LD (Fases 0–3)."""
from __future__ import annotations

import json
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.urls import reverse
from django.utils.translation import get_language, get_language_from_path

# Path fragments (language prefix stripped) that must not be indexed.
_NOINDEX_MARKERS = (
    '/login',
    '/signup',
    '/registro',
    '/password-reset',
    '/password_reset',
    '/recuperar',
    '/accounts/',
    '/oauth',
    '/i18n/',
    '/verificar',
    '/carrito',
    '/checkout',
    '/mi-tienda',
    '/mi_tienda',
    '/perfil',
    '/dashboard',
    '/admin',
    '/staff-mfa',
    '/onboarding',
    '/api/',
    '/health/',
    '/aplicar',
    '/solicitud',
    '/ordenes',
    '/mis-ordenes',
    '/nueva-orden',
    '/productos/',
    '/empresas/',
    '/usuarios',
    '/cotizacion',
    '/portal',
)


def public_base_url() -> str:
    """Return the configured public origin without a trailing slash."""
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    if base.startswith('http'):
        return base
    return 'http://127.0.0.1:8000'


def absolute_url(path: str) -> str:
    """Join ``path`` to ``PUBLIC_BASE_URL`` (path may be a full URL)."""
    raw = (path or '').strip()
    if raw.startswith('http://') or raw.startswith('https://'):
        return raw
    if not raw.startswith('/'):
        raw = '/' + raw
    return urljoin(public_base_url() + '/', raw.lstrip('/'))


def absolute_reverse(viewname: str, args=None, kwargs=None) -> str:
    """``reverse`` + ``absolute_url`` for sitemap and canonical tags."""
    return absolute_url(reverse(viewname, args=args, kwargs=kwargs))


def path_without_language(path: str) -> str:
    """Strip leading /es/ (or other locale) for policy matching."""
    path = path or '/'
    lang = get_language_from_path(path)
    if not lang:
        return path
    prefix = f'/{lang}'
    if path == prefix or path.startswith(prefix + '/'):
        stripped = path[len(prefix) :] or '/'
        return stripped if stripped.startswith('/') else f'/{stripped}'
    return path


def demo_catalog_blocks_indexing() -> bool:
    """True when public catalog/PDP must stay out of search indexes."""
    return bool(getattr(settings, 'DEMO_CATALOG_DISCLOSURE', False))


def should_noindex_path(path: str) -> bool:
    """Return True when the request path should emit noindex robots meta."""
    normalized = path_without_language(path).rstrip('/') or '/'
    for marker in _NOINDEX_MARKERS:
        if marker.rstrip('/') == normalized or marker in normalized:
            return True
    if demo_catalog_blocks_indexing():
        if (
            normalized.startswith('/catalogo')
            or normalized == '/tienda'
            or normalized.startswith('/proveedor')
        ):
            return True
    return False


def catalog_hub_canonical() -> str:
    """Canonical URL for the catalog hub (filters collapse here)."""
    return absolute_reverse('catalogo_publico')


def default_og_image_url() -> str:
    """Default Open Graph image (brand icon)."""
    return absolute_url('/static/img/logo-icon-color.png')


def robots_disallow_paths() -> list[str]:
    """Coarse robots.txt Disallow list (language-agnostic prefixes)."""
    paths = [
        '/admin/',
        '/api/',
        '/health/',
        '/i18n/',
        '/accounts/',
        '/login/',
        '/signup/',
        '/carrito/',
        '/checkout/',
        '/mi-tienda/',
        '/perfil/',
        '/dashboard/',
        '/staff-mfa/',
        '/verificar/',
        '/password-reset/',
        '/es/login/',
        '/es/signup/',
        '/es/carrito/',
        '/es/checkout/',
        '/es/mi-tienda/',
        '/es/perfil/',
        '/es/dashboard/',
        '/es/verificar/',
    ]
    if demo_catalog_blocks_indexing():
        paths.extend(
            [
                '/catalogo/',
                '/es/catalogo/',
                '/tienda/',
                '/es/tienda/',
                '/proveedor/',
                '/es/proveedor/',
            ]
        )
    return paths


def is_safe_public_host(host: str) -> bool:
    """True when host looks usable for absolute SEO URLs."""
    host = (host or '').strip().lower()
    if not host or ' ' in host:
        return False
    parsed = urlparse('https://' + host.split('/')[0])
    return bool(parsed.hostname)


def hreflang_alternates(path: str) -> list[dict]:
    """Build en / es / x-default alternate link dicts for the given path."""
    bare = path_without_language(path)
    if not bare.startswith('/'):
        bare = '/' + bare
    en_url = absolute_url(bare)
    es_path = '/es' + (bare if bare != '/' else '/')
    if bare == '/':
        es_path = '/es/'
    es_url = absolute_url(es_path)
    return [
        {'hreflang': 'en', 'href': en_url},
        {'hreflang': 'es', 'href': es_url},
        {'hreflang': 'x-default', 'href': en_url},
    ]


def organization_json_ld() -> dict:
    """Organization schema for TradeFlow Colón."""
    return {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': 'TradeFlow Colón',
        'url': public_base_url() + '/',
        'logo': default_og_image_url(),
        'description': (
            'B2B wholesale marketplace for the Colón Free Zone (Zona Libre de Colón), Panama.'
        ),
        'address': {
            '@type': 'PostalAddress',
            'addressLocality': 'Colón',
            'addressRegion': 'Colón',
            'addressCountry': 'PA',
        },
        'areaServed': 'PA',
    }


def website_json_ld() -> dict:
    """WebSite schema with SearchAction pointing at the public catalog."""
    search_target = absolute_reverse('catalogo_publico') + '?buscar={search_term_string}'
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': 'TradeFlow Colón',
        'url': public_base_url() + '/',
        'potentialAction': {
            '@type': 'SearchAction',
            'target': search_target,
            'query-input': 'required name=search_term_string',
        },
    }


def product_json_ld(product, *, canonical: str, image_url: str = '') -> dict:
    """Product schema for a catalog PDP."""
    company = product.company
    availability = (
        'https://schema.org/InStock'
        if product.available_qty > 0
        else 'https://schema.org/OutOfStock'
    )
    data = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': product.name,
        'description': (product.description or product.name)[:5000],
        'sku': product.sku or str(product.pk),
        'url': canonical,
        'brand': {
            '@type': 'Brand',
            'name': company.name if company else 'TradeFlow Colón',
        },
        'offers': {
            '@type': 'Offer',
            'url': canonical,
            'priceCurrency': getattr(product, 'currency', None) or 'USD',
            'price': str(product.display_price),
            'availability': availability,
            'seller': {
                '@type': 'Organization',
                'name': company.name if company else 'TradeFlow Colón',
            },
        },
    }
    if image_url:
        data['image'] = [image_url]
    return data


def breadcrumb_json_ld(items: list[tuple[str, str]]) -> dict:
    """BreadcrumbList from [(name, absolute_url), ...]."""
    elements = []
    for i, (name, url) in enumerate(items, start=1):
        elements.append(
            {
                '@type': 'ListItem',
                'position': i,
                'name': name,
                'item': url,
            }
        )
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': elements,
    }


def dumps_json_ld(data: dict) -> str:
    """Compact JSON-LD for safe embedding in ``<script type=application/ld+json>``."""
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))
