"""Fase 0 SEO: robots.txt, sitemap, noindex, PUBLIC_BASE_URL canonicals."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Category, Company, Product, UserProfile
from core.utils.seo import (
    absolute_reverse,
    demo_catalog_blocks_indexing,
    should_noindex_path,
)


@override_settings(
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    DEMO_CATALOG_DISCLOSURE=False,
    CSRF_COOKIE_SECURE=False,
)
class SeoRobotsSitemapTests(TestCase):
    """robots.txt and sitemap.xml discovery endpoints."""

    def test_robots_txt_lists_sitemap_and_disallows_private(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('Sitemap: https://tradeflowcolon.com/sitemap.xml', body)
        self.assertIn('Disallow: /admin/', body)
        self.assertIn('Disallow: /login/', body)
        self.assertIn('Disallow: /carrito/', body)
        self.assertNotIn('Disallow: /catalogo/', body)

    def test_sitemap_includes_home_and_products(self):
        company = Company.objects.create(name='SEO Co', ruc='8-SEO-1')
        cat = Category.objects.create(name='SEO Cat')
        product = Product.objects.create(
            name='SEO Product',
            sku='SEO-1',
            company=company,
            category=cat,
            unit_price=10,
            is_active=True,
        )
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('https://tradeflowcolon.com/', body)
        self.assertIn('https://tradeflowcolon.com/catalogo/', body)
        self.assertIn(
            f'https://tradeflowcolon.com/catalogo/producto/{product.slug}/',
            body,
        )


@override_settings(
    PUBLIC_BASE_URL='https://tradeflowcolon.com',
    DEMO_CATALOG_DISCLOSURE=True,
    CSRF_COOKIE_SECURE=False,
)
class SeoDemoNoindexTests(TestCase):
    """Demo disclosure blocks catalog indexing and sitemap products."""

    def test_robots_disallows_catalog_when_demo(self):
        response = self.client.get('/robots.txt')
        body = response.content.decode('utf-8')
        self.assertIn('Disallow: /catalogo/', body)

    def test_sitemap_omits_catalog_when_demo(self):
        response = self.client.get('/sitemap.xml')
        body = response.content.decode('utf-8')
        self.assertIn('https://tradeflowcolon.com/', body)
        self.assertNotIn('/catalogo/', body)

    def test_login_has_noindex_robots_meta(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'noindex')

    def test_catalog_has_noindex_when_demo(self):
        response = self.client.get(reverse('catalogo_publico'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'noindex')


class SeoHelperTests(TestCase):
    """Unit checks for path policy helpers."""

    def test_should_noindex_auth_paths(self):
        self.assertTrue(should_noindex_path('/login/'))
        self.assertTrue(should_noindex_path('/es/login/'))
        self.assertTrue(should_noindex_path('/carrito/'))
        self.assertFalse(should_noindex_path('/'))
        self.assertFalse(should_noindex_path('/acerca/'))

    @override_settings(PUBLIC_BASE_URL='https://tradeflowcolon.com')
    def test_absolute_reverse_uses_public_base(self):
        self.assertEqual(
            absolute_reverse('acerca_tradeflow'),
            'https://tradeflowcolon.com/acerca/',
        )
