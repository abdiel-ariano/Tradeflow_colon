"""Home merchandising — product deduplication across scroll sections."""
from decimal import Decimal

from django.test import TestCase, override_settings

from core import merchandising as merch
from core.models import Category, Company, Product


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
)
class HomeProductDeduplicationTests(TestCase):
    def setUp(self):
        """Setup."""
        self.company = Company.objects.create(name='ZLC Trading', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.products = []
        for i in range(20):
            self.products.append(
                Product.objects.create(
                    company=self.company,
                    category=self.category,
                    name=f'Widget {i}',
                    sku=f'W-{i:02d}',
                    unit_price=Decimal('25.00'),
                    currency='USD',
                    is_active=True,
                    is_featured=i < 8,
                    is_bestseller=i < 12,
                    merchandising_priority=20 - i,
                )
            )

    def test_build_guest_home_context_deduplicates_scroll_products(self):
        """Test build guest home context deduplicates scroll products."""
        ctx = merch.build_guest_home_context('en')

        featured_pks = {p.pk for p in ctx['featured_products']}
        deals_pks = {p.pk for p in ctx['daily_deals']}
        bestsellers_pks = {p.pk for p in ctx['bestsellers']}
        breadth_pks = {p.pk for p in ctx['catalog_breadth_products']}

        self.assertGreaterEqual(len(featured_pks), 1)

        overlap_deals = featured_pks & deals_pks
        self.assertEqual(overlap_deals, set(), f'daily_deals repeats featured: {overlap_deals}')

        overlap_best = (featured_pks | deals_pks) & bestsellers_pks
        self.assertEqual(overlap_best, set(), f'bestsellers repeats earlier: {overlap_best}')

        earlier = featured_pks | deals_pks | bestsellers_pks
        for section in ctx['promo_sections']:
            section_pks = {p.pk for p in section['products']}
            self.assertFalse(
                section_pks & earlier,
                f'promo section {section["section"].slug} repeats earlier products',
            )
            earlier |= section_pks

        overlap_breadth = earlier & breadth_pks
        self.assertEqual(overlap_breadth, set(), f'catalog breadth repeats earlier: {overlap_breadth}')

        category_pks: list[int] = []
        for row in ctx['category_spotlights']:
            for product in row['products']:
                self.assertNotIn(
                    product.pk,
                    earlier,
                    'category spotlight repeats earlier scroll product',
                )
                category_pks.append(product.pk)
        self.assertEqual(len(category_pks), len(set(category_pks)))

    def test_hero_collage_uses_featured_products(self):
        """Test hero collage uses featured products."""
        ctx = merch.build_guest_home_context('en')
        collage = ctx.get('hero_collage_products', [])
        self.assertGreaterEqual(len(collage), 1)
        featured_pks = {p.pk for p in ctx['featured_products']}
        for product in collage:
            self.assertIn(product.pk, featured_pks)
