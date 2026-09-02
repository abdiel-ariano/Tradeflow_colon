"""Home marketplace Alibaba-style layout regression tests.

Guest home must ship hm-alibaba sections, catalog seed photos, and
TradeFlow Colón CTAs without legacy Shopify landing chrome.
"""
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
    """Assert Alibaba home markup, media, categories, and about page."""

    def setUp(self):
        """Clear cache and seed featured bestsellers for the home grid."""
        from django.core.cache import cache
        cache.clear()
        self.company = Company.objects.create(name='CFZ Trading', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
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

    def test_home_is_alibaba_marketplace_layout(self):
        """Home uses hm-alibaba shell with gateway hero and product cards."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('hm-alibaba', html)
        self.assertIn('hm-gateway', html)
        self.assertIn('product-card', html)
        self.assertIn('btn-inquiry', html)
        self.assertNotIn('hm-shopify', html)
        self.assertNotIn('<header class="sh-header">', html)
        self.assertNotIn('sh-hero__title', html)
        self.assertNotContains(response, 'picsum.photos')

    def test_home_has_alibaba_sections_and_catalog(self):
        """Home includes suppliers, trust bar, and TradeFlow Colón CTA."""
        response = self.client.get('/')
        self.assertContains(response, 'hm-alibaba')
        self.assertContains(response, 'hm-suppliers')
        self.assertContains(response, 'hm-trust')
        self.assertContains(response, 'TradeFlow Colón')
        self.assertContains(response, 'Register your company')

    def test_home_copy_is_company_first_b2b(self):
        """Public home presents company verification, not consumer onboarding."""
        response = self.client.get('/')
        self.assertContains(response, 'Register your company')
        self.assertContains(response, 'CFZ verified suppliers')
        self.assertContains(response, 'RFQ before you buy')
        self.assertNotContains(response, 'Create free buyer account')
        self.assertNotContains(response, 'Categories for you')
        self.assertNotContains(response, 'New buyer favorites')

    def test_home_uses_visual_media_not_picsum_runtime(self):
        """Home cards render hm-visual assets without external Picsum URLs."""
        response = self.client.get('/')
        html = response.content.decode()
        self.assertIn('hm-visual', html)
        self.assertNotIn('picsum.photos', html)

    def test_home_loads_marketplace_js(self):
        """Home loads Alibaba marketplace interaction scripts."""
        response = self.client.get('/')
        self.assertContains(response, 'tf-home-marketplace.js')
        self.assertContains(response, 'tf-home-alibaba.js')

    def test_home_passes_sidebar_categories(self):
        """Home context includes at least one sidebar category for browse."""
        response = self.client.get('/')
        categories = response.context.get('sidebar_categories', [])
        self.assertGreaterEqual(len(categories), 1)

    def test_about_tradeflow_page(self):
        """/acerca/ renders the About TradeFlow Colón marketing page."""
        response = self.client.get('/acerca/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'About TradeFlow Colón')
