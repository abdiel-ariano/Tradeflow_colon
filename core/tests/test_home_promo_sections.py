"""Home CMS promo sections — rendering and deduplication."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from core import merchandising as merch
from core.models import Category, Company, HomePromoSection, Product


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
)
class HomePromoSectionHelpersTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='ZLC Demo', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.products = []
        for i in range(6):
            self.products.append(
                Product.objects.create(
                    company=self.company,
                    category=self.category,
                    name=f'Product {i}',
                    sku=f'P-{i}',
                    unit_price='100.00',
                    currency='USD',
                    is_active=True,
                    is_bestseller=i < 4,
                )
            )

    def test_active_home_section_types(self):
        HomePromoSection.objects.create(
            slug='test-deals',
            section_type='daily_deals',
            title_es='Ofertas',
            is_active=True,
        )
        types = merch.active_home_section_types()
        self.assertIn('daily_deals', types)

    def test_resolve_section_products_manual_override(self):
        section = HomePromoSection.objects.create(
            slug='manual-row',
            section_type='product_row',
            title_es='Fila manual',
            is_active=True,
            max_items=4,
        )
        section.products.set(self.products[:2])
        resolved = merch.resolve_section_products(section)
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0].pk, self.products[0].pk)

    def test_resolve_section_products_bestsellers_fallback(self):
        section = HomePromoSection.objects.create(
            slug='auto-best',
            section_type='bestsellers',
            title_es='Más vendidos',
            is_active=True,
            max_items=4,
        )
        resolved = merch.resolve_section_products(section)
        self.assertGreaterEqual(len(resolved), 1)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
)
class HomePromoRenderingTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        now = timezone.now()
        self.company = Company.objects.create(name='CFZ Seller', is_verified=True)
        self.category = Category.objects.create(name='Home Goods')
        self.promo_products = []
        for i in range(4):
            product = Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Deal Product {i}',
                sku=f'D-{i}',
                unit_price='80.00',
                promo_price=Decimal('60.00'),
                promo_starts_at=now - timedelta(days=1),
                promo_ends_at=now + timedelta(days=30),
                currency='USD',
                is_active=True,
            )
            self.promo_products.append(product)

        self.bestseller_section = HomePromoSection.objects.create(
            slug='cms-bestsellers',
            section_type='bestsellers',
            title_es='Top ZLC',
            title_en='Top ZLC',
            is_active=True,
            sort_order=0,
            max_items=4,
        )
        self.bestseller_section.products.set(self.promo_products)

        self.deals_section = HomePromoSection.objects.create(
            slug='cms-deals',
            section_type='daily_deals',
            title_es='Ofertas CMS',
            title_en='CMS Deals',
            is_active=True,
            sort_order=1,
            max_items=4,
        )
        self.deals_section.products.set([
            Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Deal Only {i}',
                sku=f'DO-{i}',
                unit_price='70.00',
                promo_price=Decimal('55.00'),
                promo_starts_at=now - timedelta(days=1),
                promo_ends_at=now + timedelta(days=30),
                currency='USD',
                is_active=True,
            )
            for i in range(4)
        ])

    def test_home_renders_cms_promo_sections(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        rows = response.context.get('home_product_rows', [])
        self.assertGreaterEqual(len(rows), 2, msg=[r.get('dom_id') for r in rows])
        self.assertIn('hm-promo-cms-bestsellers', content, msg='bestsellers row missing')
        self.assertIn('hm-promo-cms-deals', content, msg='deals row missing')
        self.assertIn('Top ZLC', content, msg='bestsellers title missing')
        self.assertIn('CMS Deals', content, msg='deals title missing')

    def test_home_hides_fallback_deals_when_cms_has_daily_deals(self):
        response = self.client.get('/')
        self.assertFalse(response.context['show_daily_deals_strip'])
        self.assertNotContains(response, 'id="hm-deals"')

    def test_home_hides_fallback_bestsellers_when_cms_has_bestsellers(self):
        response = self.client.get('/')
        self.assertFalse(response.context['show_bestsellers_section'])
        self.assertNotContains(response, 'id="hm-bestsellers"')

    def test_home_shows_fallback_bestsellers_without_cms(self):
        from django.core.cache import cache
        HomePromoSection.objects.all().delete()
        cache.clear()
        for i in range(5):
            Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Best {i}',
                sku=f'B-{i}',
                unit_price='50.00',
                currency='USD',
                is_active=True,
                is_bestseller=True,
            )
        response = self.client.get('/')
        self.assertTrue(response.context['show_bestsellers_section'])
        self.assertIn('hm-bestsellers', response.content.decode())

    def test_home_renders_alibaba_bento_layout(self):
        response = self.client.get('/')
        self.assertContains(response, 'hm-bento')
        self.assertContains(response, 'hm-alibaba')
        self.assertNotContains(response, 'id="hm-hero"')
