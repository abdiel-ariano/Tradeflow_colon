"""Home marketplace — catalog-style product cards on landing."""
from django.test import TestCase, override_settings

from core.models import Category, Company, Product


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    TRADEFLOW_USE_PICSUM_RUNTIME=False,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class HomeMarketplaceCardsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='CFZ Trading', is_verified=True)
        self.category = Category.objects.create(name='Electronics & Office')
        for i in range(8):
            Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Marketplace Widget {i}',
                sku=f'MW-{i:02d}',
                unit_price='42.00',
                currency='USD',
                is_active=True,
                is_featured=True,
                is_bestseller=i < 6,
                merchandising_priority=30 - i,
            )

    def test_home_uses_catalog_marketplace_cards(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('hm-marketplace', html)
        self.assertIn('product-grid', html)
        self.assertIn('product-card', html)
        self.assertIn('btn-inquiry', html)
        self.assertIn('card-moq', html)
        self.assertIn('CFZ Verified', html)
        self.assertIn('home-marketplace.css', html)
        self.assertNotIn('tf-pcard--featured-dense', html)
        self.assertNotIn('picsum.photos', html)

    def test_home_has_marketplace_search_and_trust_strip(self):
        response = self.client.get('/')
        self.assertContains(response, 'hm-mkt-search')
        self.assertContains(response, 'trust-strip')
        self.assertContains(response, 'Request for Quotation')

    def test_home_passes_trending_categories(self):
        response = self.client.get('/')
        categories = response.context.get('marketplace_trending_categories', [])
        self.assertGreaterEqual(len(categories), 1)
        self.assertEqual(categories[0].name, 'Electronics & Office')
