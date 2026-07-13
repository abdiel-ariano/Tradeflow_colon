"""Home marketplace — Shopify landing from Figma."""
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
        from django.core.cache import cache
        cache.clear()
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

    def test_home_is_shopify_landing_layout(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('hm-shopify', html)
        self.assertIn('hm-marketplace-hero', html)
        self.assertIn('hm-hero-carousel', html)
        self.assertIn('hm-quad-cards', html)
        self.assertNotIn('<header class="sh-header">', html)
        self.assertIn('sh-build', html)
        self.assertIn('product-card', html)
        self.assertIn('btn-inquiry', html)
        self.assertNotIn('sh-hero__title', html)
        self.assertNotIn('hm-feed-carousel', html)
        self.assertNotIn('hm-alibaba', html)
        self.assertNotContains(response, 'picsum.photos')

    def test_home_has_shopify_sections_and_catalog(self):
        response = self.client.get('/')
        self.assertContains(response, 'hm-shopify')
        self.assertContains(response, 'sh-rfq')
        self.assertContains(response, 'sh-stats')
        self.assertContains(response, 'sh-catalog')
        self.assertContains(response, 'TradeFlow Colón')
        self.assertContains(response, 'Create account')

    def test_home_uses_catalog_seed_photos_not_svg_icons(self):
        response = self.client.get('/')
        html = response.content.decode()
        self.assertTrue(
            '/static/images/catalog-seeds/' in html or 'shopify-landing/' in html
        )

    def test_home_has_no_infinite_shimmer_overlays(self):
        response = self.client.get('/')
        self.assertNotContains(response, 'hm-media__shimmer')
        self.assertContains(response, 'tf-home-marketplace.js')

    def test_home_passes_sidebar_categories(self):
        response = self.client.get('/')
        categories = response.context.get('sidebar_categories', [])
        self.assertGreaterEqual(len(categories), 1)

    def test_about_tradeflow_page(self):
        response = self.client.get('/acerca/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'About TradeFlow Colón')
        self.assertContains(response, 'marketplace-about.css')
        self.assertContains(response, 'marketplace-about.js')
        self.assertContains(response, 'mkt-about-cinematic')
        self.assertContains(response, 'data-about-root')
