"""Tests for locale redirect middleware and catalog i18n."""
from django.test import TestCase, override_settings
from django.urls import reverse

from core.utils.i18n_urls import tf_translate_url

from core.models import Category, Company, Product


@override_settings(LANGUAGE_CODE='en')
class CatalogI18nTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Setuptestdata."""
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
        """Setup."""
        from django.core.cache import cache
        cache.clear()
    def test_catalog_default_english_filters(self):
        """Test catalog default english filters."""
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Refine results')
        self.assertContains(response, 'Verified')
        self.assertNotContains(response, 'Refinar resultados')

    def test_catalog_spanish_via_language_switch(self):
        """Test catalog spanish via language switch."""
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
        """Test spanish cookie redirects unprefixed catalog."""
        self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('catalogo_publico')},
        )
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/es/catalogo/'))

    def test_spanish_home_hero_and_cards(self):
        """Test spanish home hero and cards."""
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
        """Test marketplace nav language switcher."""
        response = self.client.get(reverse('catalogo_publico'))
        self.assertContains(response, 'bn-lang-switch')
        self.assertContains(response, 'name="language"')
        self.assertContains(response, 'value="es"')
        self.assertContains(response, 'value="en"')

    def test_english_cookie_redirects_prefixed_home_to_unprefixed(self):
        """Test english cookie redirects prefixed home to unprefixed."""
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
        """Test english switch from es catalog."""
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
        """Test spanish home category labels."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('home')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Electrónica y oficina')
        self.assertContains(response, 'Textiles y uniformes')


    def test_spanish_deals_page(self):
        """Test spanish deals page."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('marketplace_deals')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ofertas mayoristas de hoy')
        self.assertContains(response, 'Ofertas flash')

    def test_spanish_verified_suppliers_page(self):
        """Test spanish verified suppliers page."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('marketplace_verified_suppliers')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Proveedores verificados ZLC')
        self.assertContains(response, 'Directorio de proveedores')

    def test_spanish_about_page(self):
        """Test spanish about page."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('acerca_tradeflow')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'comercio mayorista no debería exigir un vuelo a Panamá')

    def test_marketplace_pages_cache_headers(self):
        """Test marketplace pages cache headers."""
        for url_name in (
            'marketplace_deals',
            'marketplace_verified_suppliers',
            'marketplace_order_protection',
            'acerca_tradeflow',
        ):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertIn('max-age=3600', response.get('Cache-Control', ''))

    def test_spanish_product_detail_page(self):
        """Test spanish product detail page."""
        product = Product.objects.first()
        post_response = self.client.post(
            reverse('set_language'),
            {
                'language': 'es',
                'next': reverse('catalogo_producto_detail', args=[product.pk]),
            },
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Descripción')
        self.assertContains(response, 'Especificaciones')
        self.assertContains(response, 'Regístrate para ver precios mayoristas')
        self.assertContains(response, 'Electrónica y oficina')
        self.assertNotContains(response, 'Sign up to view wholesale pricing')

    def test_spanish_catalog_meta_description(self):
        """Test spanish catalog meta description."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('catalogo_publico')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'inventario transparente en TradeFlow',
        )
        self.assertNotContains(response, 'transparent inventory on TradeFlow')

    def test_spanish_default_footer_on_product_detail(self):
        """Test spanish default footer on product detail."""
        product = Product.objects.first()
        post_response = self.client.post(
            reverse('set_language'),
            {
                'language': 'es',
                'next': reverse('catalogo_producto_detail', args=[product.pk]),
            },
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cómo comprar')
        self.assertContains(response, 'Empresas verificadas')
        self.assertNotContains(response, 'How to buy')


@override_settings(LANGUAGE_CODE='en')
class LegalPageShellTests(TestCase):
    def test_legal_privacy_uses_marketplace_shell(self):
        """Test legal privacy uses marketplace shell."""
        response = self.client.get(reverse('legal_privacidad'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'legal-shell')
        self.assertContains(response, 'cat-nav tf-nav-alibaba')
        self.assertIn('max-age=3600', response.get('Cache-Control', ''))

    def test_legal_terms_table_of_contents(self):
        """Test legal terms table of contents."""
        response = self.client.get(reverse('legal_terminos'))
        self.assertContains(response, 'legal-toc')
        self.assertContains(response, '#terms-service')

    def test_legal_page_full_width_shell(self):
        """Test legal page full width shell."""
        response = self.client.get(reverse('legal_privacidad'))
        self.assertContains(response, 'hm-marketplace-page--legal')
        self.assertNotContains(response, 'max-width: 1080px')

    def test_spanish_legal_terms_body(self):
        """Test spanish legal terms body."""
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
        """Test spanish legal privacy body."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('legal_privacidad')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TradeFlow Colón trata datos personales')
        self.assertContains(response, 'Datos que recopilamos')

    def test_spanish_legal_cookies_body(self):
        """Test spanish legal cookies body."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('legal_cookies')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Las cookies son archivos pequeños')
        self.assertContains(response, 'Cookies esenciales')
