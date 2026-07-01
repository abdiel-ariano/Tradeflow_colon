"""Home product image src — uploaded URL or bundled category seed."""
from django.test import TestCase, override_settings

from core.models import Category, Company, Product
from core.templatetags.tf_media import catalog_card_image_src, product_image_src


@override_settings(
    DEBUG=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
)
class HomeProductImageSrcTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Demo Co', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Widget',
            sku='W-1',
            unit_price='100.00',
            currency='USD',
            is_active=True,
        )

    def test_product_image_src_uses_catalog_seed_when_no_upload(self):
        url = product_image_src(self.product)
        self.assertIn('/static/images/catalog-seeds/electronics.jpg', url)

    def test_product_image_src_uses_catalog_seed_when_local_file_missing(self):
        self.product.image = 'products/demo/missing.jpg'
        self.product.save(update_fields=['image'])
        url = product_image_src(self.product)
        self.assertIn('/static/images/catalog-seeds/', url)

    def test_catalog_card_image_src_matches_product_image_src(self):
        self.assertEqual(catalog_card_image_src(self.product), product_image_src(self.product))
