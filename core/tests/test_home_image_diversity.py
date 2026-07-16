"""Home rows avoid duplicate fallback photos in one visible section.

When many SKUs share a category seed, merchandising must diversify
crops/fingerprints so CFZ home grids do not look copy-pasted.
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from core import merchandising as merch
from core.models import Category, Company, Product
from core.templatetags.tf_media import product_image_object_position


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
)
class HomeImageDiversityTests(TestCase):
    """Assert object-position variety and unique image fingerprints."""

    def setUp(self):
        """Seed bestsellers across two categories for diversity picks."""
        self.company = Company.objects.create(name='ZLC Trading', is_verified=True)
        self.electronics = Category.objects.create(name='Electronics & Office')
        self.gaming = Category.objects.create(name='Gaming & Peripherals')
        self.products = []
        for i in range(12):
            cat = self.electronics if i < 8 else self.gaming
            self.products.append(
                Product.objects.create(
                    company=self.company,
                    category=cat,
                    name=f'Widget {i}',
                    sku=f'W-{i:02d}',
                    unit_price=Decimal('25.00'),
                    currency='USD',
                    is_active=True,
                    is_bestseller=True,
                    merchandising_priority=20 - i,
                )
            )

    def test_object_position_varies_by_product_pk(self):
        """object-position CSS values differ across nearby product PKs."""
        positions = {product_image_object_position(p) for p in self.products[:8]}
        self.assertGreater(len(positions), 1)

    def test_pick_unique_products_skips_duplicate_seed_images(self):
        """diverse_images mode skips cards that share a seed fingerprint."""
        seen: set[int] = set()
        picked = merch._pick_unique_products(self.products, seen, 8, diverse_images=True)
        fingerprints = [merch._product_image_fingerprint(p) for p in picked]
        self.assertEqual(len(fingerprints), len(set(fingerprints)))
        # Two category seeds (electronics + gaming) — at most one card per seed.
        self.assertLessEqual(len(picked), 2)

    def test_pick_unique_products_diverse_row_from_bestsellers_pool(self):
        """Bestsellers pool picks keep unique fingerprints when diversified."""
        seen: set[int] = set()
        pool = merch.bestsellers(24)
        picked = merch._pick_unique_products(pool, seen, 8, diverse_images=True)
        fingerprints = [merch._product_image_fingerprint(p) for p in picked]
        self.assertEqual(len(fingerprints), len(set(fingerprints)))

    def test_build_guest_home_bestsellers_no_duplicate_fingerprints(self):
        """Guest home bestsellers (CMS or fallback) do not repeat images."""
        ctx = merch.build_guest_home_context('en')
        for section in ctx['promo_sections']:
            if section['section'].section_type != 'bestsellers':
                continue
            fps = [merch._product_image_fingerprint(p) for p in section['products']]
            self.assertEqual(len(fps), len(set(fps)), 'CMS bestsellers row repeats images')

        fps = [merch._product_image_fingerprint(p) for p in ctx['bestsellers']]
        if len(fps) > 1:
            self.assertEqual(len(fps), len(set(fps)))
