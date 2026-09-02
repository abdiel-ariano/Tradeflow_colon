"""Locale URL rewriting for EN/ES marketplace paths.

Buyers switch language without losing catalog filters or query
strings; default-language cookies strip redundant /es/ prefixes.
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from core.utils.i18n_urls import tf_translate_url


@override_settings(LANGUAGE_CODE='en')
class TfTranslateUrlTests(TestCase):
    """Assert tf_translate_url maps prefixed and bare paths."""

    def test_es_home_to_english(self):
        """Map Spanish home prefix to English root."""
        self.assertEqual(tf_translate_url('/es/', 'en'), '/')

    def test_es_catalog_to_english(self):
        """Strip /es/ from catalog when targeting English."""
        self.assertEqual(tf_translate_url('/es/catalogo/', 'en'), '/catalogo/')

    def test_english_catalog_to_spanish(self):
        """Prefix catalog with /es/ when targeting Spanish."""
        self.assertEqual(tf_translate_url('/catalogo/', 'es'), '/es/catalogo/')

    def test_preserves_querystring(self):
        """Keep search query strings across language switches."""
        url = tf_translate_url('/es/catalogo/?buscar=hub', 'en')
        self.assertEqual(url, '/catalogo/?buscar=hub')


@override_settings(LANGUAGE_CODE='en')
class TfLanguageMiddlewareTests(TestCase):
    """Assert language middleware redirects for default locale."""

    def test_default_language_strips_es_prefix_without_cookie(self):
        """Redirect /es/ to / when no language cookie is set."""
        self.assertEqual(translation.get_language_from_path('/es/'), 'es')
        response = self.client.get('/es/', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_prefixed_url_redirects_when_cookie_is_default_language(self):
        """Redirect /es/ home when cookie is English."""
        self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': '/'},
        )
        self.assertEqual(self.client.cookies['django_language'].value, 'en')
        response = self.client.get('/es/', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_prefixed_catalog_redirects_when_cookie_is_default_language(self):
        """Redirect /es/catalogo/ when cookie is English."""
        self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': '/catalogo/'},
        )
        response = self.client.get('/es/catalogo/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/catalogo/')

    def test_set_language_en_from_es_home(self):
        """set_language from Spanish home lands on English root."""
        self.client.cookies['django_language'] = 'es'
        response = self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': '/es/'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
