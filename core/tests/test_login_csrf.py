"""Login CSRF and cache headers — production proxy safety."""

from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    CSRF_TRUSTED_ORIGINS=[],
    CSRF_COOKIE_SECURE=False,
)
class LoginCsrfSettingsTests(TestCase):
    def test_csrf_trusted_origins_include_public_base_and_www(self):
        from tradeflow_colon import settings

        origins = settings._build_csrf_trusted_origins()
        self.assertIn('https://tradeflowcolon.com', origins)
        self.assertIn('https://www.tradeflowcolon.com', origins)


@override_settings(CSRF_COOKIE_SECURE=False)
class LoginViewCacheTests(TestCase):
    def test_login_get_is_not_publicly_cacheable(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        cache_control = response.get('Cache-Control', '')
        self.assertIn('no-cache', cache_control)
        self.assertIn('no-store', cache_control)

    def test_login_post_succeeds_with_csrf_token(self):
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
