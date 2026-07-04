"""Home marketplace — Alibaba-style unified product-first landing."""
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

    def test_home_is_product_first_alibaba_layout(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('hm-alibaba', html)
        self.assertIn('hm-bento', html)
        self.assertIn('product-card', html)
        self.assertIn('btn-inquiry', html)
        self.assertIn('home-alibaba.css', html)
        self.assertNotContains(response, 'id="hm-hero"')
        self.assertNotContains(response, 'hm-mkt-search')
        self.assertNotContains(response, 'class="tf-pcard ')
        self.assertNotContains(response, 'picsum.photos')

    def test_home_has_bento_and_product_rows(self):
        response = self.client.get('/')
        self.assertContains(response, 'hm-bento')
        self.assertContains(response, 'hm-product-row')
        self.assertContains(response, 'hm-cat-discover')
        self.assertContains(response, 'Categories for you')
        self.assertContains(response, 'Products for you')

    def test_home_uses_catalog_seed_photos_not_svg_icons(self):
        response = self.client.get('/')
        html = response.content.decode()
        self.assertIn('/static/images/catalog-seeds/', html)
        self.assertNotIn('/static/images/category-icons/', html)

    def test_home_has_no_infinite_shimmer_overlays(self):
        response = self.client.get('/')
        self.assertNotContains(response, 'hm-media__shimmer')
        self.assertContains(response, 'hm-visual is-loaded')
        self.assertContains(response, 'tf-home-marketplace.js')
        response = self.client.get('/')
        self.assertContains(response, 'hm-cat-modal')
        self.assertContains(response, 'data-cat-modal-open')
        self.assertContains(response, 'View all')

    def test_home_passes_sidebar_categories(self):
        response = self.client.get('/')
        categories = response.context.get('sidebar_categories', [])
        self.assertGreaterEqual(len(categories), 1)

    def test_about_tradeflow_page(self):
        response = self.client.get('/acerca/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'About TradeFlow Colón')
        self.assertContains(response, 'hm-about-hero')
        self.assertContains(response, 'Why choose TradeFlow')
