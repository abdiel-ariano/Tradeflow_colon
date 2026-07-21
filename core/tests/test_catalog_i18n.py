"""Locale redirect middleware and marketplace catalog i18n.

Spanish and English buyers share one CFZ catalog; prefix redirects,
filter copy, legal shells, and SEO meta must stay locale-consistent.
"""
from django.test import TestCase, override_settings
from django.urls import reverse

from core.utils.i18n_urls import tf_translate_url

from core.models import Category, Company, Product


@override_settings(LANGUAGE_CODE='en')
class CatalogI18nTests(TestCase):
    """Assert catalog/home locale switches, redirects, and Spanish copy."""

    @classmethod
    def setUpTestData(cls):
        """Seed featured products in two categories for locale pages."""
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
        """Clear cache so locale-sensitive pages are not sticky."""
        from django.core.cache import cache
        cache.clear()

    def test_catalog_default_english_filters(self):
        """Default English catalog shows Refine results / Verified filters."""
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Refine results')
        self.assertContains(response, 'Verified')
        self.assertNotContains(response, 'Refinar resultados')

    def test_catalog_spanish_via_language_switch(self):
        """Language switch to es renders Spanish catalog filter copy."""
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
        """Spanish cookie redirects bare /catalogo/ to the /es/ prefix."""
        self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('catalogo_publico')},
        )
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/es/catalogo/'))

    def test_spanish_home_hero_and_cards(self):
        """Spanish home shows ZLC wholesale hero and help CTAs."""
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
        """Marketplace nav exposes the EN/ES language form controls."""
        response = self.client.get(reverse('catalogo_publico'))
        self.assertContains(response, 'bn-lang-switch')
        self.assertContains(response, 'name="language"')
        self.assertContains(response, 'value="es"')
        self.assertContains(response, 'value="en"')

    def test_english_cookie_redirects_prefixed_home_to_unprefixed(self):
        """Switching back to en strips /es/ and restores English home copy."""
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
        """EN switch from /es/catalogo/ lands on unprefixed /catalogo/."""
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
        """Spanish home localizes category display names for navigation."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('home')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Electrónica y oficina')
        self.assertContains(response, 'Textiles y uniformes')

    def test_spanish_deals_page(self):
        """Spanish deals page shows wholesale/flash offer headings."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('marketplace_deals')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ofertas mayoristas de hoy')
        self.assertContains(response, 'Ofertas flash')

    def test_spanish_verified_suppliers_page(self):
        """Spanish verified-suppliers page shows ZLC directory copy."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('marketplace_verified_suppliers')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Proveedores verificados ZLC')
        self.assertContains(response, 'Directorio de proveedores')

    def test_spanish_about_page(self):
        """Spanish about page keeps TradeFlow Colón positioning copy."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('acerca_tradeflow')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'comercio mayorista no debería exigir un vuelo a Panamá')

    def test_marketplace_pages_cache_headers(self):
        """Marketing marketplace pages advertise one-hour Cache-Control."""
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
        """Spanish PDP shows localized specs and wholesale signup CTA."""
        product = Product.objects.first()
        post_response = self.client.post(
            reverse('set_language'),
            {
                'language': 'es',
                'next': reverse('catalogo_producto_detail', kwargs={'slug': product.slug}),
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
        """Spanish catalog meta description uses TradeFlow SEO phrasing."""
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
        """Spanish PDP footer uses Cómo comprar / Empresas verificadas."""
        product = Product.objects.first()
        post_response = self.client.post(
            reverse('set_language'),
            {
                'language': 'es',
                'next': reverse('catalogo_producto_detail', kwargs={'slug': product.slug}),
            },
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cómo comprar')
        self.assertContains(response, 'Empresas verificadas')
        self.assertNotContains(response, 'How to buy')


@override_settings(LANGUAGE_CODE='en')
class LegalPageShellTests(TestCase):
    """Assert legal pages reuse marketplace shell and Spanish bodies."""

    def test_legal_privacy_uses_marketplace_shell(self):
        """Privacy page uses legal-shell plus marketplace nav chrome."""
        response = self.client.get(reverse('legal_privacidad'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'legal-shell')
        self.assertContains(response, 'cat-nav tf-nav-alibaba')
        self.assertIn('max-age=3600', response.get('Cache-Control', ''))

    def test_legal_terms_table_of_contents(self):
        """Terms page includes an in-page table of contents anchors."""
        response = self.client.get(reverse('legal_terminos'))
        self.assertContains(response, 'legal-toc')
        self.assertContains(response, '#terms-service')

    def test_legal_page_full_width_shell(self):
        """Legal layout uses full-width shell, not a narrow content column."""
        response = self.client.get(reverse('legal_privacidad'))
        self.assertContains(response, 'hm-marketplace-page--legal')
        self.assertNotContains(response, 'max-width: 1080px')

    def test_spanish_legal_terms_body(self):
        """Spanish terms body uses platform service copy, not English."""
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
        """Spanish privacy body names TradeFlow Colón data handling."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('legal_privacidad')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TradeFlow Colón trata datos personales')
        self.assertContains(response, 'Datos que recopilamos')

    def test_spanish_legal_cookies_body(self):
        """Spanish cookies page explains essential cookie categories."""
        post_response = self.client.post(
            reverse('set_language'),
            {'language': 'es', 'next': reverse('legal_cookies')},
        )
        response = self.client.get(post_response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Las cookies son archivos pequeños')
        self.assertContains(response, 'Cookies esenciales')
