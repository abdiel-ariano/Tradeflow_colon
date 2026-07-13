"""Verified suppliers public page — layout and guest access."""
from django.test import TestCase, override_settings

from core.models import Category, Company, Inventory, Product


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
)
class MarketplaceVerifiedSuppliersPageTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Electronics')
        for i in range(5):
            company = Company.objects.create(
                name=f'CFZ Supplier {i}',
                is_verified=True,
                carousel_priority=10 - i,
            )
            product = Product.objects.create(
                company=company,
                category=self.category,
                name=f'SKU {i}',
                sku=f'VS-{i}',
                unit_price='20.00',
                currency='USD',
                is_active=True,
            )
            Inventory.objects.create(product=product, stock_qty=20)

    def test_guest_sees_verified_directory_ui(self):
        response = self.client.get('/verified-suppliers/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mkt-verified-hero')
        self.assertContains(response, 'TradeFlow')
        self.assertContains(response, 'CFZ verified suppliers')
        self.assertContains(response, 'mkt-verified-trust')
        self.assertContains(response, 'mkt-vendor-grid')
        self.assertContains(response, 'mkt-verified-filter')
        self.assertContains(response, 'marketplace-verified.css')
        self.assertContains(response, 'CFZ Supplier')

    def test_featured_and_grid_split_when_enough_suppliers(self):
        response = self.client.get('/verified-suppliers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['empresas_destacadas']), 3)
        self.assertEqual(len(response.context['empresas_grid']), 2)
        self.assertContains(response, 'Featured storefronts')
