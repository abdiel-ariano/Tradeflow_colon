"""Auth pages must expose the shared ES/EN language switcher."""

from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(LANGUAGE_CODE='en')
class AuthLangSwitcherTests(TestCase):
    AUTH_URL_NAMES = (
        'login',
        'password_reset',
        'signup_buyer',
        'signup_seller',
    )

    def test_auth_pages_include_language_switcher(self):
        """Each auth-only page renders the shared ES/EN switcher."""
        for name in self.AUTH_URL_NAMES:
            with self.subTest(page=name):
                path = reverse(name)
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'auth-lang-switch')
                self.assertContains(response, reverse('set_language'))
                self.assertContains(response, f'name="next" value="{path}"')

    def test_set_language_from_login_returns_to_login(self):
        """Switching language from /login/ redirects back to the locale login URL."""
        login_path = reverse('login')
        response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': login_path},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/es' + login_path)
        self.assertEqual(self.client.cookies['django_language'].value, 'es')

        response = self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': '/es' + login_path},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, login_path)
