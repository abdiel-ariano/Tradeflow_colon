"""Phase 0 demo seed naming, stock buckets, and catalog images.

Expo demos must look like real CFZ inventory: no lot suffixes,
varied stock, and category seed photos when uploads are absent.
"""
from decimal import Decimal
import random

from django.test import TestCase

from core.models import Category, Company, Product
from core.utils.product_seed_naming import build_seed_product_name, strip_lot_suffix
from core.utils.product_stock_seed import realistic_stock_qty


class ProductSeedNamingTests(TestCase):
    """Assert seed product name builders."""

    def test_strip_lot_suffix(self):
        """Remove trailing lot NNN suffixes from titles."""
        self.assertEqual(
            strip_lot_suffix('Universal Docking Station — lot 284'),
            'Universal Docking Station',
        )

    def test_build_seed_product_name_has_no_lot(self):
        """Build seed names without lot markers in the title."""
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
        """Differentiate same SKU titles across seller companies."""
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
    """Assert realistic_stock_qty spans low and high buckets."""

    def test_realistic_stock_spans_buckets(self):
        """Sample both scarce and bulk stock quantities."""
        rng = random.Random(99)
        samples = [realistic_stock_qty(rng) for _ in range(200)]
        lows = [s for s in samples if s <= 15]
        highs = [s for s in samples if s >= 1000]
        self.assertGreater(len(lows), 10)
        self.assertGreater(len(highs), 10)


class ProductImageSrcPhase0Tests(TestCase):
    """Assert product_image_src falls back to catalog seeds."""

    def setUp(self):
        """Create active product without an uploaded image."""
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
        """Serve electronics catalog-seed URL when no upload exists."""
        from core.templatetags.tf_media import product_image_src

        url = product_image_src(self.product)
        self.assertIn('/static/images/catalog-seeds/electronics.jpg', url)
