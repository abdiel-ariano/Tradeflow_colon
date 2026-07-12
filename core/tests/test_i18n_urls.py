"""Tests for tf_translate_url helper."""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from core.utils.i18n_urls import tf_translate_url


@override_settings(LANGUAGE_CODE='en')
class TfTranslateUrlTests(TestCase):
    def test_es_home_to_english(self):
        self.assertEqual(tf_translate_url('/es/', 'en'), '/')

    def test_es_catalog_to_english(self):
        self.assertEqual(tf_translate_url('/es/catalogo/', 'en'), '/catalogo/')

    def test_english_catalog_to_spanish(self):
        self.assertEqual(tf_translate_url('/catalogo/', 'es'), '/es/catalogo/')

    def test_preserves_querystring(self):
        url = tf_translate_url('/es/catalogo/?buscar=hub', 'en')
        self.assertEqual(url, '/catalogo/?buscar=hub')


@override_settings(LANGUAGE_CODE='en')
class TfLanguageMiddlewareTests(TestCase):
    def test_default_language_strips_es_prefix_without_cookie(self):
        self.assertEqual(translation.get_language_from_path('/es/'), 'es')
        response = self.client.get('/es/', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_prefixed_url_redirects_when_cookie_is_default_language(self):
        self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': '/'},
        )
        self.assertEqual(self.client.cookies['django_language'].value, 'en')
        response = self.client.get('/es/', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_prefixed_catalog_redirects_when_cookie_is_default_language(self):
        self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': '/catalogo/'},
        )
        response = self.client.get('/es/catalogo/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/catalogo/')

    def test_set_language_en_from_es_home(self):
        self.client.cookies['django_language'] = 'es'
        response = self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': '/es/'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
