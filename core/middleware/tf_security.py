"""HTTP security headers, audit logging, and IP rate limits.

Protects TradeFlow Colón HTML and API surfaces with CSP nonces,
OWASP-oriented security event logs, and per-bucket request throttling.
"""
from __future__ import annotations

import logging
import secrets
import time

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

# Vendor CDNs used by Leaflet, supabase-js, Bootstrap, and Chart.js.
_CSP_SCRIPT_CDN = "https://cdn.jsdelivr.net https://unpkg.com"
_CSP_STYLE_CDN = "https://fonts.googleapis.com https://cdn.jsdelivr.net"
# External endpoints reached after a same-origin form POST → 302. Browsers
# enforce form-action on the redirect chain, so each destination must be listed.
_CSP_FORM_ACTION_EXTERNAL = (
    "https://accounts.google.com "
    "https://login.microsoftonline.com "
    "https://www.linkedin.com "
    "https://checkout.stripe.com"
)


class SecurityHeadersMiddleware:
    """Attach hardening headers and a per-request CSP nonce.

    Sets ``request.csp_nonce`` before the view so templates can mark
    inline ``<script>`` / ``<style>`` tags. CSP uses that nonce instead
    of ``'unsafe-inline'`` except on Django admin and Leaflet map pages.
    """

    def __init__(self, get_response):
        """Initialize middleware with the next ASGI/WSGI callable."""
        self.get_response = get_response

    def __call__(self, request):
        # Nonce before the view so context processors/templates can read it.
        """Process one request through this middleware hook."""
        request.csp_nonce = secrets.token_urlsafe(16)

        response = self.get_response(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        # Geolocation stays self-only for checkout and carrier selection.
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=(self), payment=(), '
            'usb=(), magnetometer=(), gyroscope=(), accelerometer=()',
        )
        # Cross-origin isolation (Spectre + popup exfil mitigations).
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')

        # Skip strict CSP on admin (own inlines) and Leaflet/OSM map pages.
        _path = request.path
        _is_admin = _path.startswith('/admin/')
        _is_leaflet_map = (
            _path == '/mapa/' or _path.startswith('/mapa/')
            or _path.startswith('/en/mapa/') or _path.startswith('/es/mapa/')
        )
        if not _is_admin:
            nonce = request.csp_nonce
            if _is_leaflet_map:
                # Relaxed CSP for Leaflet/OSM (CDN scripts + https tiles).
                response.headers.setdefault(
                    'Content-Security-Policy',
                    "default-src 'self'; "
                    "img-src 'self' data: https: blob:; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    f"script-src 'self' 'unsafe-inline' {_CSP_SCRIPT_CDN}; "
                    "connect-src 'self' https: wss:; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    f"form-action 'self' {_CSP_FORM_ACTION_EXTERNAL};",
                )
            else:
                # Strict nonce-based CSP for marketplace pages.
                response.headers.setdefault(
                    'Content-Security-Policy',
                    "default-src 'self'; "
                    "img-src 'self' data: https: blob:; "
                    f"style-src 'self' 'nonce-{nonce}' {_CSP_STYLE_CDN}; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    f"script-src 'self' 'nonce-{nonce}' {_CSP_SCRIPT_CDN}; "
                    "connect-src 'self' https: wss:; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    f"form-action 'self' {_CSP_FORM_ACTION_EXTERNAL};",
                )
        if request.is_secure():
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response


class SecurityEventLogMiddleware:
    """Log security-relevant HTTP outcomes for audit monitoring.

    Captures 401/403, admin 404 scans, 429 rate limits, 5xx errors, and
    anonymous redirects from ``/admin/`` (OWASP A09 logging failures).
    """

    SENSITIVE_PATHS = ('/admin/', '/api/admin/')

    def __init__(self, get_response):
        """Initialize middleware with the next ASGI/WSGI callable."""
        self.get_response = get_response
        self.log = logging.getLogger('tradeflow.security')

    def __call__(self, request):
        """Process one request through this middleware hook."""
        response = self.get_response(request)
        status = response.status_code
        path = request.path
        is_sensitive = any(path.startswith(p) for p in self.SENSITIVE_PATHS)
        user = getattr(request, 'user', None)
        is_anon = (user is None) or (not getattr(user, 'is_authenticated', False))

        is_sec_event = (
            status in (401, 403, 429)
            or (status == 404 and is_sensitive)
            or status >= 500
            or (status in (301, 302) and is_sensitive and is_anon)
        )
        if is_sec_event:
            user_id = getattr(user, 'id', None) if not is_anon else None
            ip = self._client_ip(request)
            self.log.warning(
                'security_event status=%s method=%s path=%s user_id=%s ip=%s ua=%s',
                status, request.method, path[:200], user_id, ip,
                (request.META.get('HTTP_USER_AGENT', '') or '')[:120],
            )
        return response

    @staticmethod
    def _client_ip(request):
        """Best-effort client IP (rightmost XFF hop; see client_ip helper)."""
        from core.utils.client_ip import get_client_ip
        return get_client_ip(request)


class ApiRateLimitMiddleware:
    """Throttle APIs, AI search, catalog partials, and seller toggles by IP."""

    WINDOW = 60
    API_LIMIT = 120
    SEARCH_LIMIT = 60
    CATALOG_PARTIAL_LIMIT = 90
    SELLER_POST_LIMIT = 60

    def __init__(self, get_response):
        """Initialize middleware with the next ASGI/WSGI callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Process one request through this middleware hook."""
        bucket, limit = self._resolve_bucket(request)
        if not bucket:
            return self.get_response(request)

        ip = self._client_ip(request)
        key = f'tf_rl:{bucket}:{ip}:{int(time.time()) // self.WINDOW}'
        count = cache.get(key, 0)
        if count >= limit:
            return self._rate_limit_response(request, bucket)
        cache.set(key, count + 1, self.WINDOW + 5)
        return self.get_response(request)

    def _resolve_bucket(self, request) -> tuple[str | None, int]:
        """Map the request path to a rate-limit bucket and ceiling."""
        path = request.path

        if path.endswith('/api/search/suggest/') or path.endswith('/api/search/suggest'):
            return 'search', self.SEARCH_LIMIT

        is_api = (
            path.startswith('/api/')
            or path.startswith('/en/api/')
            or path.startswith('/es/api/')
            or '/api/v1/' in path
        )
        if is_api:
            return 'api', self.API_LIMIT

        if (
            request.method == 'GET'
            and (path.endswith('/catalogo/') or path.endswith('/catalogo'))
            and request.GET.get('partial') == '1'
        ):
            return 'catalog_partial', self.CATALOG_PARTIAL_LIMIT

        if (
            request.method == 'POST'
            and '/mi-tienda/productos/' in path
            and '/toggle' in path
        ):
            return 'seller_toggle', self.SELLER_POST_LIMIT

        return None, 0

    @staticmethod
    def _wants_json(request) -> bool:
        """Return True when the client expects a JSON 429 body."""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return True
        accept = request.headers.get('Accept', '')
        return 'application/json' in accept

    def _rate_limit_response(self, request, bucket: str):
        """Build a 429 response with Retry-After for the active bucket."""
        retry_after = self.WINDOW
        if self._wants_json(request) or bucket in ('api', 'search', 'catalog_partial'):
            response = JsonResponse(
                {
                    'ok': False,
                    'error': 'rate_limit',
                    'retry_after': retry_after,
                    'message': 'Too many requests. Please wait and try again.',
                },
                status=429,
            )
        else:
            response = HttpResponse(
                'Rate limit exceeded. Please wait and try again.',
                status=429,
                content_type='text/plain; charset=utf-8',
            )
        response['Retry-After'] = str(retry_after)
        return response

    @staticmethod
    def _client_ip(request):
        """Best-effort client IP (rightmost XFF hop; see client_ip helper)."""
        from core.utils.client_ip import get_client_ip
        return get_client_ip(request)
