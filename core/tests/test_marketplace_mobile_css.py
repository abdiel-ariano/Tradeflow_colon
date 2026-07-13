"""Mobile marketplace pages should not cause horizontal document overflow."""
from django.test import TestCase, override_settings

from core.models import Category, Company, Inventory, Product


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
)
class MarketplaceMobileCssTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name='Mobile Co', is_verified=True)
        cat = Category.objects.create(name='Electronics')
        product = Product.objects.create(
            company=company,
            category=cat,
            name='Mobile Widget',
            sku='MW-1',
            unit_price='12.00',
            currency='USD',
            is_active=True,
            is_featured=True,
        )
        Inventory.objects.create(product=product, stock_qty=10)

    def test_home_and_catalog_include_mobile_css(self):
        for path in ('/', '/catalogo/', '/verified-suppliers/', '/acerca/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'marketplace-mobile.css')
