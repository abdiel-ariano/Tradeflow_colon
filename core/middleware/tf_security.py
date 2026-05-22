"""
Cabeceras de seguridad y rate limiting ligero para APIs sensibles.
"""
from __future__ import annotations

import time

from django.core.cache import cache
from django.http import HttpResponseForbidden


class SecurityHeadersMiddleware:
    """Refuerza cabeceras HTTP en respuestas HTML/API."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        if request.is_secure():
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response


class ApiRateLimitMiddleware:
    """Límite simple por IP en rutas /api/ (anti-abuso)."""

    LIMIT = 120
    WINDOW = 60

    def __init__(self, get_response):
        self.get_response = get_response

    SELLER_POST_LIMIT = 60

    def __call__(self, request):
        path = request.path
        is_api = (
            path.startswith('/api/')
            or path.startswith('/en/api/')
            or path.startswith('/es/api/')
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
