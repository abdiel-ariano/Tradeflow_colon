"""Tests for locale redirect middleware and catalog i18n."""
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(LANGUAGE_CODE='en')
class CatalogI18nTests(TestCase):
    def test_catalog_default_english_filters(self):
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Refine results')
        self.assertContains(response, 'Verified')
        self.assertNotContains(response, 'Refinar resultados')

    def test_catalog_spanish_via_language_switch(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('catalogo_publico')},
        )
        self.assertEqual(post_response.status_code, 302)
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Refinar resultados')
        self.assertContains(response, 'Verificado')
        self.assertContains(response, 'Catálogo')

    def test_spanish_cookie_redirects_unprefixed_catalog(self):
        self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('catalogo_publico')},
        )
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/es/catalogo/'))

    def test_marketplace_nav_language_switcher(self):
        response = self.client.get(reverse('catalogo_publico'))
        self.assertContains(response, 'bn-lang-switch')
        self.assertContains(response, 'name="language"')
        self.assertContains(response, 'value="es"')
        self.assertContains(response, 'value="en"')


@override_settings(LANGUAGE_CODE='en')
class LegalPageShellTests(TestCase):
    def test_legal_privacy_uses_marketplace_shell(self):
        response = self.client.get(reverse('legal_privacidad'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'legal-shell')
        self.assertContains(response, 'cat-nav tf-nav-alibaba')
        self.assertIn('max-age=3600', response.get('Cache-Control', ''))

    def test_legal_terms_table_of_contents(self):
        response = self.client.get(reverse('legal_terminos'))
        self.assertContains(response, 'legal-toc')
        self.assertContains(response, '#terms-service')

    def test_legal_page_full_width_shell(self):
        response = self.client.get(reverse('legal_privacidad'))
        self.assertContains(response, 'hm-marketplace-page--legal')
        self.assertNotContains(response, 'max-width: 1080px')
