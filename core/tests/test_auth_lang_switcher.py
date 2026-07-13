"""Auth pages respect the global language cookie without a local switcher."""

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation


@override_settings(LANGUAGE_CODE='en')
class AuthGlobalLanguageTests(TestCase):
    def setUp(self):
        # LocaleMiddleware leaves get_language() sticky across tests; reset so
        # reverse() does not emit /es/... prefixes into the next case.
        translation.activate(settings.LANGUAGE_CODE)

    def test_auth_pages_have_no_local_language_switcher(self):
        """Auth layouts rely on the global locale cookie, not a per-page switcher."""
        for name in ('login', 'password_reset', 'signup_buyer', 'signup_seller'):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'auth-lang-switch')

    def test_login_copy_follows_language_cookie(self):
        """Login title switches with django_language cookie."""
        en = self.client.get(reverse('login'))
        self.assertContains(en, 'Sign in to your account')
        self.assertNotContains(en, 'Iniciar sesión en tu cuenta')

        self.client.cookies['django_language'] = 'es'
        es = self.client.get('/es' + reverse('login'))
        self.assertEqual(es.status_code, 200)
        self.assertContains(es, 'Iniciar sesión en tu cuenta')
        self.assertNotContains(es, 'Sign in to your account')

    def test_recover_copy_follows_language_cookie(self):
        """Recover access title switches with django_language cookie."""
        en = self.client.get(reverse('password_reset'))
        self.assertContains(en, 'Recover access')
        self.assertContains(en, 'Send link')

        self.client.cookies['django_language'] = 'es'
        es = self.client.get('/es' + reverse('password_reset'))
        self.assertEqual(es.status_code, 200)
        self.assertContains(es, 'Recuperar acceso')
        self.assertContains(es, 'Enviar enlace')

    def test_es_cookie_redirects_unprefixed_auth_urls(self):
        """Cookie=es redirects unprefixed auth routes to /es/... (global preference)."""
        self.client.cookies['django_language'] = 'es'
        for name in ('login', 'password_reset', 'signup_buyer', 'signup_seller'):
            with self.subTest(page=name):
                path = reverse(name)
                response = self.client.get(path, follow=False)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, '/es' + path)
