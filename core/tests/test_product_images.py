"""Product image assignment and enterprise-year seed media.

Demo catalogs need local media files so CFZ storefronts are not
blank during expo and operator verify_media checks.
"""
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from core.models import Category, Company, Order, Product
from core.utils.demo_product_images import assign_product_image
from core.utils.enterprise_year_simulator import (
    ORDER_NUM_PREFIX,
    SIM_RUC_PREFIX,
    clear_enterprise_year_simulation,
)
from core.utils.media_storage import local_media_file_exists


class RegenerateProductImagesTests(TestCase):
    """Assert assign_product_image and management commands."""

    def setUp(self):
        """Create a company product ready for image assignment."""
        self.company = Company.objects.create(
            name='Image Test Co',
            ruc='8-IMG-TEST-001',
            address_text='ZLC',
            is_verified=True,
        )
        self.category = Category.objects.create(name='Test Cat')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Smartphone Samsung Galaxy',
            description='Test',
            sku='IMG-001',
            unit_price='99.00',
            currency='USD',
        )

    def test_assign_product_image_writes_file(self):
        """Write a non-empty productos/ media file for the SKU."""
        rel = assign_product_image(self.product)
        self.assertTrue(rel.startswith('productos/'))
        self.assertTrue(local_media_file_exists(rel))
        full = Path(settings.MEDIA_ROOT) / rel
        self.assertGreater(full.stat().st_size, 0)

    def test_regenerate_product_images_command(self):
        """regenerate_product_images fills product.image paths."""
        call_command('regenerate_product_images', '--limit', '1')
        self.product.refresh_from_db()
        self.assertTrue(self.product.image)
        self.assertTrue(local_media_file_exists(self.product.image.name))

    def test_verify_media_command(self):
        """verify_media runs successfully against assigned files."""
        rel = assign_product_image(self.product)
        self.product.image = rel
        self.product.save(update_fields=['image'])
        call_command('verify_media', '--limit', '5')


class SeedEnterpriseYearImageTests(TestCase):
    """Assert seed_enterprise_year --with-images creates media."""

    def test_demo_seed_with_images(self):
        """Seed demo companies with product images, then clear."""
        clear_enterprise_year_simulation()
        call_command(
            'seed_enterprise_year',
            '--clear',
            '--scale=demo',
            '--with-images',
            '--seed=7',
        )
        products = Product.objects.filter(company__ruc__startswith=SIM_RUC_PREFIX)
        self.assertGreater(products.count(), 0)
        with_images = [p for p in products if p.image]
        self.assertGreater(len(with_images), 0)
        sample = with_images[0]
        self.assertTrue(sample.image.name.startswith('productos/'))
        self.assertTrue(local_media_file_exists(sample.image.name))

        clear_enterprise_year_simulation()
        self.assertEqual(Company.objects.filter(ruc__startswith=SIM_RUC_PREFIX).count(), 0)
        self.assertEqual(Order.objects.filter(order_number__startswith=ORDER_NUM_PREFIX).count(), 0)
