"""Concrete product references and truthful catalog fallbacks."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Category, Company, Product
from core.templatetags.tf_media import (
    product_image_category_seed_src,
    product_image_is_reference,
    product_image_src,
)
from core.utils.demo_product_images import (
    assign_catalog_seed_image,
    catalog_seed_bytes,
    category_keyword,
    product_reference_key,
    variant_image_bytes,
)


@override_settings(
    DEBUG=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
)
class CatalogSeedImageTests(TestCase):
    """Assert reference matching, safe fallbacks, and legacy seed utilities."""

    def setUp(self):
        """Create an electronics product without an uploaded image."""
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

    def test_unmatched_product_uses_category_icon_not_generic_photo(self):
        url = product_image_src(self.product)
        self.assertIn('/static/images/category-icons/electronics.svg', url)
        self.assertNotIn('catalog-seeds', url)
        self.assertNotIn('picsum.photos', url)

    def test_concrete_reference_matches_product_family(self):
        self.product.name = 'Aluminum 11-in-1 USB-C Hub — lot 776'
        self.product.save(update_fields=['name'])

        self.assertEqual(product_reference_key(self.product), 'usb_c_hub')
        self.assertIn(
            '/static/assets/products/reference/usb-c-hub.webp',
            product_image_src(self.product),
        )
        self.assertTrue(product_image_is_reference(self.product))

    def test_textile_reference_matches_clothing_families(self):
        cases = (
            (
                'Industrial Cargo Pants — lot 101',
                'industrial_cargo_pants',
                'industrial-cargo-pants.webp',
            ),
            (
                'Corporate Dry-Fit Polo — lot 102',
                'corporate_dry_fit_polo',
                'corporate-dry-fit-polo.webp',
            ),
            (
                'Staff Waterproof Jacket — lot 103',
                'staff_waterproof_jacket',
                'staff-waterproof-jacket.webp',
            ),
        )

        for name, expected_key, filename in cases:
            with self.subTest(name=name):
                self.product.name = name
                self.assertEqual(
                    product_reference_key(self.product),
                    expected_key,
                )
                self.assertIn(
                    f'/static/assets/products/reference/{filename}',
                    product_image_src(self.product),
                )

    def test_extended_textile_references_cover_remaining_families(self):
        cases = (
            (
                '300-Thread Hospitality Set — lot 201',
                'hospitality_set_300_thread',
                'hospitality-set-300-thread.webp',
            ),
            (
                'Rigid Executive Briefcase — lot 202',
                'rigid_executive_briefcase',
                'rigid-executive-briefcase.webp',
            ),
            (
                'Top-Grain Leather Belt — lot 203',
                'top_grain_leather_belt',
                'top-grain-leather-belt.webp',
            ),
            (
                'Travel Organizer Set — lot 204',
                'travel_organizer_set',
                'travel-organizer-set.webp',
            ),
        )

        for name, expected_key, filename in cases:
            with self.subTest(name=name):
                self.product.name = name
                self.assertEqual(
                    product_reference_key(self.product),
                    expected_key,
                )
                self.assertIn(
                    f'/static/assets/products/reference/{filename}',
                    product_image_src(self.product),
                )

    def test_concrete_reference_replaces_generated_demo_media(self):
        self.product.name = '1500VA Interactive UPS — lot 204'
        self.product.save(update_fields=['name'])
        assign_catalog_seed_image(self.product)
        self.product.refresh_from_db()

        self.assertTrue(self.product.image.name.startswith('products/demo/'))
        self.assertIn(
            '/static/assets/products/reference/ups-1500va.webp',
            product_image_src(self.product),
        )

    def test_real_supplier_upload_keeps_priority_over_reference(self):
        self.product.name = 'Aluminum 11-in-1 USB-C Hub'
        self.product.image = 'products/supplier/usb-c-hub.webp'
        self.product.save(update_fields=['name', 'image'])

        with (
            patch('core.utils.media_storage.local_media_file_exists', return_value=True),
            patch(
                'core.utils.media_storage.product_image_url',
                return_value='/media/products/supplier/usb-c-hub.webp',
            ),
        ):
            self.assertEqual(
                product_image_src(self.product),
                '/media/products/supplier/usb-c-hub.webp',
            )
            self.assertFalse(product_image_is_reference(self.product))

    def test_category_seed_filter_remains_available_for_commands(self):
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
