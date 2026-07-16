"""API rate limits for search suggest and catalog AJAX partials.

Public CFZ catalog endpoints must return 429 JSON before abusive
clients overwhelm search or partial rendering.
"""
import json

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.middleware.tf_security import ApiRateLimitMiddleware


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
)
class ApiRateLimitMiddlewareTests(SimpleTestCase):
    """Assert ApiRateLimitMiddleware 429 responses."""

    def setUp(self):
        """Clear cache and wrap middleware with a 200 handler."""
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = ApiRateLimitMiddleware(lambda request: self._ok(request))

    @staticmethod
    def _ok(request):
        """Return a plain 200 response."""
        from django.http import HttpResponse

        return HttpResponse('ok')

    def test_search_suggest_returns_429_json_when_exceeded(self):
        """Block search suggest after SEARCH_LIMIT with rate_limit JSON."""
        for _ in range(ApiRateLimitMiddleware.SEARCH_LIMIT):
            response = self.middleware(self.factory.get('/api/search/suggest/?q=ups'))
            self.assertEqual(response.status_code, 200)

        blocked = self.middleware(self.factory.get('/api/search/suggest/?q=ups'))
        self.assertEqual(blocked.status_code, 429)
        payload = json.loads(blocked.content)
        self.assertEqual(payload['error'], 'rate_limit')
        self.assertIn('Retry-After', blocked)

    def test_catalog_partial_returns_429_json_when_exceeded(self):
        """Block catalog AJAX partials after CATALOG_PARTIAL_LIMIT."""
        req = self.factory.get('/catalogo/?partial=1', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        for _ in range(ApiRateLimitMiddleware.CATALOG_PARTIAL_LIMIT):
            response = self.middleware(req)
            self.assertEqual(response.status_code, 200)

        blocked = self.middleware(req)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(json.loads(blocked.content)['error'], 'rate_limit')
