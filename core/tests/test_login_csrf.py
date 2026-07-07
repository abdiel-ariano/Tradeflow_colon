"""Login CSRF and cache headers — production proxy safety."""

from django.test import Client, TestCase, override_settings
from django.urls import reverse


class LoginCsrfSettingsTests(TestCase):
    def test_csrf_trusted_origins_builder_adds_www_variant(self):
        from tradeflow_colon.settings import _csrf_origins_for_base

        origins = _csrf_origins_for_base('https://tradeflowcolon.com', [])
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
