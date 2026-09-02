"""Login CSRF origins and anti-cache headers for production.

CDN/proxy layers must not cache the login form; www and apex
origins both need CSRF trust for CFZ operators and buyers.
"""

from django.contrib.auth.models import User
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

    def test_csrf_origins_for_host_skips_wildcards(self):
        """Ignore Railway-style leading-dot ALLOWED_HOSTS entries."""
        from tradeflow_colon.settings import _csrf_origins_for_host

        self.assertEqual(_csrf_origins_for_host('.up.railway.app'), [])
        self.assertEqual(
            _csrf_origins_for_host('demo.up.railway.app'),
            ['https://demo.up.railway.app'],
        )


@override_settings(CSRF_COOKIE_SECURE=False, CSRF_COOKIE_HTTPONLY=False)
class LoginViewCacheTests(TestCase):
    """Assert login responses refuse public caching and accept CSRF."""

    def test_login_get_is_not_publicly_cacheable(self):
        """Send no-cache/no-store on GET /login/."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        cache_control = response.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)

    def test_login_get_sets_csrf_cookie(self):
        """Ensure the login GET always issues a csrftoken cookie."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', response.cookies)

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

    def test_login_csrf_failure_redirects_with_message(self):
        """Auth CSRF failures redirect to login instead of a bare 403 page."""
        User.objects.create_user(username='demo_seller', password='Demo1234!')
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('login'))
        response = client.post(
            reverse('login'),
            {
                'username': 'demo_seller',
                'password': 'Demo1234!',
                'csrfmiddlewaretoken': 'stale-or-forged-token',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        follow = client.get(response.url)
        self.assertContains(follow, 'Security check expired', status_code=200)
