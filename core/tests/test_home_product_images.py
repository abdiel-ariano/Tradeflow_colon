"""Home product image src — upload, AI reference, or catalog seed photo."""
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
        """Setup."""
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
        """Test product image src uses catalog seed when no upload."""
        url = product_image_src(self.product)
        self.assertIn('/static/images/catalog-seeds/electronics.jpg', url)

    def test_product_image_src_uses_catalog_seed_when_local_file_missing(self):
        """Test product image src uses catalog seed when local file missing."""
        self.product.image = 'products/demo/missing.jpg'
        self.product.save(update_fields=['image'])
        url = product_image_src(self.product)
        self.assertIn('/static/images/catalog-seeds/', url)

    def test_object_position_uses_pk_modulo_grid(self):
        """Test object position uses pk modulo grid."""
        from core.templatetags.tf_media import product_image_object_position

        pk = self.product.pk
        expected = f'{(pk % 5) * 20}% {((pk // 5) % 3) * 30}%'
        self.assertEqual(product_image_object_position(self.product), expected)
        other = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Other',
            sku='W-2',
            unit_price='50.00',
            currency='USD',
            is_active=True,
        )
        self.assertNotEqual(
            product_image_object_position(self.product),
            product_image_object_position(other),
        )

    def test_catalog_card_image_src_matches_product_image_src(self):
        """Test catalog card image src matches product image src."""
        self.assertEqual(catalog_card_image_src(self.product), product_image_src(self.product))
