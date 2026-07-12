"""Phase 0 seed credibility — product naming and stock."""
from decimal import Decimal
import random

from django.test import TestCase

from core.models import Category, Company, Product
from core.utils.product_seed_naming import build_seed_product_name, strip_lot_suffix
from core.utils.product_stock_seed import realistic_stock_qty


class ProductSeedNamingTests(TestCase):
    def test_strip_lot_suffix(self):
        """Test strip lot suffix."""
        self.assertEqual(
            strip_lot_suffix('Universal Docking Station — lot 284'),
            'Universal Docking Station',
        )

    def test_build_seed_product_name_has_no_lot(self):
        """Test build seed product name has no lot."""
        rng = random.Random(7)
        name = build_seed_product_name(
            company_name='Panamax Electronics B2B',
            base_title='Cat6 Wiring Kit',
            description='305m CCA-certified for installations.',
            product_index=3,
            rng=rng,
        )
        self.assertNotRegex(name, r'lot\s+\d+', msg=name)
        self.assertIn('Cat6 Wiring Kit', name)

    def test_different_companies_get_distinct_prefixes(self):
        """Test different companies get distinct prefixes."""
        rng = random.Random(1)
        a = build_seed_product_name(
            company_name='Panamax Electronics B2B',
            base_title='Universal Docking Station',
            description='Dual display, fast laptop charging.',
            product_index=1,
            rng=rng,
        )
        b = build_seed_product_name(
            company_name='Canal Side Accessories',
            base_title='Universal Docking Station',
            description='Dual display, fast laptop charging.',
            product_index=1,
            rng=rng,
        )
        self.assertNotEqual(a, b)


class ProductStockSeedTests(TestCase):
    def test_realistic_stock_spans_buckets(self):
        """Test realistic stock spans buckets."""
        rng = random.Random(99)
        samples = [realistic_stock_qty(rng) for _ in range(200)]
        lows = [s for s in samples if s <= 15]
        highs = [s for s in samples if s >= 1000]
        self.assertGreater(len(lows), 10)
        self.assertGreater(len(highs), 10)


class ProductImageSrcPhase0Tests(TestCase):
    def setUp(self):
        """Setup."""
        self.company = Company.objects.create(name='ZLC Trading', is_verified=True)
        self.category = Category.objects.create(name='Electronics & Office')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Test Widget',
            sku='W-1',
            unit_price=Decimal('25.00'),
            currency='USD',
            is_active=True,
        )

    def test_product_image_src_uses_catalog_seed_without_upload(self):
        """Test product image src uses catalog seed without upload."""
        from core.templatetags.tf_media import product_image_src

        url = product_image_src(self.product)
        self.assertIn('/static/images/catalog-seeds/electronics.jpg', url)
