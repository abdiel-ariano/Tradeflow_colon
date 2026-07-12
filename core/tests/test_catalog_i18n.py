"""Tests for locale redirect middleware and catalog i18n."""
from django.test import TestCase, override_settings
from django.urls import reverse

from core.utils.i18n_urls import tf_translate_url

from core.models import Category, Company, Product


@override_settings(LANGUAGE_CODE='en')
class CatalogI18nTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name='CFZ Trading', is_verified=True)
        cls.electronics = Category.objects.create(name='Electronics & Office')
        cls.textiles = Category.objects.create(name='Textiles & Uniforms')
        for i, cat in enumerate((cls.electronics, cls.textiles)):
            Product.objects.create(
                company=company,
                category=cat,
                name=f'Widget {i}',
                sku=f'W-{i}',
                unit_price='42.00',
                currency='USD',
                is_active=True,
                is_featured=True,
                merchandising_priority=20 - i,
            )

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
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

    def test_spanish_home_hero_and_cards(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('home')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'marketplace mayorista de las Américas')
        self.assertContains(response, 'Proveedores verificados ZLC')
        self.assertContains(response, 'Cómo funciona TradeFlow')
        self.assertContains(response, 'Centro de ayuda')

    def test_marketplace_nav_language_switcher(self):
        response = self.client.get(reverse('catalogo_publico'))
        self.assertContains(response, 'bn-lang-switch')
        self.assertContains(response, 'name="language"')
        self.assertContains(response, 'value="es"')
        self.assertContains(response, 'value="en"')

    def test_english_cookie_redirects_prefixed_home_to_unprefixed(self):
        self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('home')},
        )
        es_home = self.client.get('/es/')
        self.assertEqual(es_home.status_code, 200)

        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': tf_translate_url('/es/', 'en')},
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response.url, '/')

        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CFZ verified suppliers')
        self.assertNotContains(response, 'Proveedores verificados ZLC')

    def test_english_switch_from_es_catalog(self):
        self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('catalogo_publico')},
        )
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'en', 'next': tf_translate_url('/es/catalogo/', 'en')},
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response.url, '/catalogo/')

    def test_spanish_home_category_labels(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('home')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Electrónica y oficina')
        self.assertContains(response, 'Textiles y uniformes')


    def test_spanish_deals_page(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('marketplace_deals')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ofertas mayoristas de hoy')
        self.assertContains(response, 'Ofertas flash')

    def test_spanish_verified_suppliers_page(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('marketplace_verified_suppliers')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Proveedores verificados ZLC')
        self.assertContains(response, 'Directorio de proveedores')

    def test_spanish_about_page(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('acerca_tradeflow')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'comercio mayorista no debería exigir un vuelo a Panamá')

    def test_marketplace_pages_cache_headers(self):
        for url_name in (
            'marketplace_deals',
            'marketplace_verified_suppliers',
            'marketplace_order_protection',
            'acerca_tradeflow',
        ):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertIn('max-age=3600', response.get('Cache-Control', ''))


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

    def test_spanish_legal_terms_body(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('legal_terminos')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'El uso de la Plataforma implica')
        self.assertContains(response, 'Descripción del servicio')
        self.assertNotContains(response, 'Use of the Platform implies')

    def test_spanish_legal_privacy_body(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('legal_privacidad')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TradeFlow Colón trata datos personales')
        self.assertContains(response, 'Datos que recopilamos')

    def test_spanish_legal_cookies_body(self):
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('legal_cookies')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Las cookies son archivos pequeños')
        self.assertContains(response, 'Cookies esenciales')
