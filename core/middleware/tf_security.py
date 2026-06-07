"""
Cabeceras de seguridad y rate limiting ligero para APIs sensibles.
"""
from __future__ import annotations

import logging
import secrets
import time

from django.core.cache import cache
from django.http import HttpResponseForbidden

# Permite a vendor scripts (Leaflet, supabase-js, Bootstrap, Chart.js)
# que cargamos vía <script src="https://..."></script> seguir funcionando
# con CSP strict. Si en futuro se mueven a self-hosted, quitar de aqui.
_CSP_SCRIPT_CDN = "https://cdn.jsdelivr.net https://unpkg.com"


class SecurityHeadersMiddleware:
    """Refuerza cabeceras HTTP en respuestas HTML/API.

    Genera un nonce CSP nuevo por request (`request.csp_nonce`) y lo
    incluye en el header Content-Security-Policy en lugar de
    `'unsafe-inline'`. Las plantillas deben renderizar el nonce en TODOS
    sus `<script>` y `<style>` inline:

        <script nonce="{{ csp_nonce }}"> ... </script>
        <style nonce="{{ csp_nonce }}">  ... </style>

    El context processor `core.context_processors.csp_nonce_context`
    expone `csp_nonce` a todas las plantillas.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generamos el nonce ANTES del view para que el context processor
        # y las plantillas puedan leerlo. 16 bytes -> 22 chars base64-url.
        request.csp_nonce = secrets.token_urlsafe(16)

        response = self.get_response(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        # Permissions-Policy: deshabilita APIs que la app NO usa.
        # `geolocation=(self)` porque checkout y seleccionar_transportista lo usan.
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=(self), payment=(), '
            'usb=(), magnetometer=(), gyroscope=(), accelerometer=()',
        )
        # Aislamiento cross-origin (Spectre + popup exfil)
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')

        # ── Exclusiones de CSP strict ────────────────────────────────────
        # `/admin/`        -> Django admin tiene sus propios inline scripts/styles.
        # `/mapa/` (Folium) -> genera iframe srcdoc con inline scripts/styles que
        #                      no podemos noncear (libreria externa).
        _path = request.path
        _is_admin = _path.startswith('/admin/')
        _is_folium_map = (
            _path == '/mapa/' or _path.startswith('/mapa/')
            or _path.startswith('/en/mapa/') or _path.startswith('/es/mapa/')
        )
        if not _is_admin:
            nonce = request.csp_nonce
            if _is_folium_map:
                # CSP relajado para que Folium pueda ejecutar su Leaflet inline.
                response.headers.setdefault(
                    'Content-Security-Policy',
                    "default-src 'self'; "
                    "img-src 'self' data: https: blob:; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    f"script-src 'self' 'unsafe-inline' {_CSP_SCRIPT_CDN}; "
                    "connect-src 'self' https: wss:; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self';",
                )
            else:
                # CSP strict con nonce.
                response.headers.setdefault(
                    'Content-Security-Policy',
                    "default-src 'self'; "
                    "img-src 'self' data: https: blob:; "
                    f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    f"script-src 'self' 'nonce-{nonce}' {_CSP_SCRIPT_CDN}; "
                    "connect-src 'self' https: wss:; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self';",
                )
        if request.is_secure():
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response


class SecurityEventLogMiddleware:
    """Logging estructurado de eventos relevantes para auditoria de seguridad.

    OWASP A09:2021 — Security Logging and Monitoring Failures.

    Eventos capturados:
      - 401/403: intento de acceso no autorizado.
      - 404 en /admin/: scan de admin panels.
      - 429: rate limit hit.
      - 5xx: errores del servidor (indicador de explotacion).
      - 301/302 desde /admin/* sin auth: probing de admin.
    """

    SENSITIVE_PATHS = ('/admin/', '/api/admin/')

    def __init__(self, get_response):
        self.get_response = get_response
        self.log = logging.getLogger('tradeflow.security')

    def __call__(self, request):
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
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()[:45]
        return request.META.get('REMOTE_ADDR', '')[:45]


class ApiRateLimitMiddleware:
    """Límite simple por IP en rutas /api/ (anti-abuso)."""

    LIMIT = 120
    WINDOW = 60
    SELLER_POST_LIMIT = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        is_api = (
            path.startswith('/api/')
            or path.startswith('/en/api/')
            or path.startswith('/es/api/')
            or '/api/v1/' in path
        )
        is_seller_mutation = (
            request.method == 'POST'
            and '/mi-tienda/productos/' in path
            and '/toggle' in path
        )
        if is_api or is_seller_mutation:
            ip = self._client_ip(request)
            bucket = 'seller' if is_seller_mutation else 'api'
            limit = self.SELLER_POST_LIMIT if is_seller_mutation else self.LIMIT
            key = f'tf_rl:{bucket}:{ip}:{int(time.time()) // self.WINDOW}'
            count = cache.get(key, 0)
            if count >= limit:
                return HttpResponseForbidden('Rate limit exceeded')
            cache.set(key, count + 1, self.WINDOW + 5)
        return self.get_response(request)

    @staticmethod
    def _client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()[:45]
        return request.META.get('REMOTE_ADDR', '')[:45]
