"""Bundled catalog seed images — no runtime picsum in production."""
from django.test import TestCase, override_settings

from core.models import Category, Company, Product
from core.templatetags.tf_media import product_image_category_seed_src, product_image_src
from core.utils.demo_product_images import (
    assign_catalog_seed_image,
    catalog_seed_bytes,
    category_keyword,
    variant_image_bytes,
)


@override_settings(
    DEBUG=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
)
class CatalogSeedImageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Seed Co', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='USB Hub Pack',
            sku='USB-1',
            unit_price='40.00',
            currency='USD',
            is_active=True,
        )

    def test_category_keyword_maps_electronics(self):
        self.assertEqual(category_keyword(self.product), 'electronics')

    def test_catalog_seed_bytes_loads_bundled_file(self):
        data = catalog_seed_bytes('electronics')
        self.assertGreater(len(data), 1000)

    def test_product_image_src_uses_category_icon_not_picsum(self):
        url = product_image_src(self.product)
        self.assertIn('/static/images/category-icons/electronics.svg', url)
        self.assertNotIn('picsum.photos', url)

    def test_category_seed_filter_returns_jpeg_path(self):
        self.assertIn(
            '/static/images/catalog-seeds/electronics.jpg',
            product_image_category_seed_src(self.product),
        )

    def test_variant_bytes_differs_per_product_pk(self):
        others = [
            Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Cable Pack {i}',
                sku=f'USB-{i}',
                unit_price='30.00',
                currency='USD',
                is_active=True,
            )
            for i in range(2, 8)
        ]
        base = variant_image_bytes(self.product)
        self.assertTrue(
            any(variant_image_bytes(p) != base for p in others),
            'Expected at least one per-PK crop variant to differ',
        )

    def test_assign_catalog_seed_image_writes_media_file(self):
        rel = assign_catalog_seed_image(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name.replace('\\', '/'), rel)
        self.assertTrue(rel.startswith('products/demo/'))

    @override_settings(DEBUG=True, TRADEFLOW_USE_PICSUM_RUNTIME=True)
    def test_picsum_enabled_in_debug_when_flag_set(self):
        url = product_image_src(self.product)
        self.assertIn('picsum.photos', url)
