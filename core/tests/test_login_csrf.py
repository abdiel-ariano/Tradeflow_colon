"""Login CSRF origins and anti-cache headers for production.

CDN/proxy layers must not cache the login form; www and apex
origins both need CSRF trust for CFZ operators and buyers.
"""

from django.test import Client, TestCase, override_settings
from django.urls import reverse


class LoginCsrfSettingsTests(TestCase):
    """Assert CSRF trusted-origin builder covers www variants."""

    def test_csrf_trusted_origins_builder_adds_www_variant(self):
        """Include both apex and www HTTPS origins for the base host."""
        from tradeflow_colon.settings import _csrf_origins_for_base

        origins = _csrf_origins_for_base('https://tradeflowcolon.com', [])
        self.assertIn('https://tradeflowcolon.com', origins)
        self.assertIn('https://www.tradeflowcolon.com', origins)


@override_settings(CSRF_COOKIE_SECURE=False)
class LoginViewCacheTests(TestCase):
    """Assert login responses refuse public caching and accept CSRF."""

    def test_login_get_is_not_publicly_cacheable(self):
        """Send no-cache/no-store on GET /login/."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        cache_control = response.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)

    def test_login_post_succeeds_with_csrf_token(self):
        """Accept POST login when csrftoken cookie is present."""
        client = Client(enforce_csrf_checks=True)
        login_get = client.get(reverse('login'))
        self.assertEqual(login_get.status_code, 200)
        token = login_get.cookies['csrftoken'].value
        response = client.post(
            reverse('login'),
            {'username': 'nobody', 'password': 'wrong', 'csrfmiddlewaretoken': token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.status_code, 403)
