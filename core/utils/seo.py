"""SEO helpers: absolute URLs, robots policy, and indexability gates.

Fase 0 — keep crawlers on public marketing/catalog surfaces and off
auth, checkout, seller portals, and demo catalog when disclosure is on.
"""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.urls import reverse
from django.utils.translation import get_language_from_path

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
        if normalized.startswith('/catalogo') or normalized == '/tienda':
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
        paths.extend(['/catalogo/', '/es/catalogo/', '/tienda/', '/es/tienda/'])
    return paths


def is_safe_public_host(host: str) -> bool:
    """True when host looks usable for absolute SEO URLs."""
    host = (host or '').strip().lower()
    if not host or ' ' in host:
        return False
    parsed = urlparse('https://' + host.split('/')[0])
    return bool(parsed.hostname)
