"""Home product image src — uploaded URL or picsum demo fallback."""
from django.test import TestCase

from core.models import Category, Company, Product
from core.templatetags.tf_media import product_image_src


class ProductImageSrcTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Demo Co', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='USB Hub Wholesale',
            sku='HUB-1',
            unit_price='25.00',
            currency='USD',
            is_active=True,
        )

    def test_product_image_src_uses_picsum_when_no_upload(self):
        url = product_image_src(self.product)
        self.assertTrue(url.startswith('https://picsum.photos/seed/'))
        self.assertIn('400/300', url)

    def test_product_image_src_uses_picsum_when_local_file_missing(self):
        self.product.image = 'productos/missing_file.png'
        self.product.save(update_fields=['image'])
        url = product_image_src(self.product)
        self.assertTrue(url.startswith('https://picsum.photos/seed/'))

    def test_catalog_card_image_src_matches_product_image_src(self):
        from core.templatetags.tf_media import catalog_card_image_src

        self.assertEqual(catalog_card_image_src(self.product), product_image_src(self.product))
