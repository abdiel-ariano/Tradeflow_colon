"""Guest home and merchandising server-side cache helpers.

Public CFZ landing must stay fast under load; product saves
invalidate merchandising keys, and missing DB cache tables
must not 500 the homepage.
"""
from django.core.cache import cache
from django.test import TestCase, override_settings

from core import merchandising as merch
from core.models import Category, Company, Product
from core.utils.tradeflow_cache import (
    HOME_CTX_KEY,
    HOME_STATS_KEY,
    cached_guest_home_context,
    cached_home_stats,
    invalidate_merchandising_cache,
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'tradeflow-test-cache',
        }
    },
    CACHE_TTL_HOME=120,
    CACHE_TTL_STATS=300,
)
class TradeflowCacheTests(TestCase):
    """Assert cache populate, invalidate, and home resilience."""

    def setUp(self):
        """Clear cache and seed featured/bestseller products."""
        cache.clear()
        self.company = Company.objects.create(name='Cache Co', is_verified=True)
        self.category = Category.objects.create(name='Gadgets')
        for i in range(6):
            Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Item {i}',
                sku=f'C-{i}',
                unit_price='25.00',
                currency='USD',
                is_active=True,
                is_featured=i < 3,
                is_bestseller=i < 4,
            )

    def test_home_stats_cached_on_second_call(self):
        """Populate HOME_STATS_KEY after cached_home_stats."""
        first = cached_home_stats()
        second = cached_home_stats()
        self.assertEqual(first['productos'], 6)
        self.assertEqual(second['productos'], 6)
        self.assertIsNotNone(cache.get(HOME_STATS_KEY))

    def test_guest_home_context_cached_per_language(self):
        """Cache guest home context under a language-specific key."""
        ctx_en = cached_guest_home_context('en')
        ctx_en_again = cached_guest_home_context('en')
        self.assertEqual(len(ctx_en['featured_products']), len(ctx_en_again['featured_products']))
        self.assertIsNotNone(cache.get(HOME_CTX_KEY.format(lang='en')))

    def test_invalidate_clears_home_cache(self):
        """invalidate_merchandising_cache clears home keys."""
        cached_guest_home_context('es')
        cached_home_stats()
        invalidate_merchandising_cache()
        self.assertIsNone(cache.get(HOME_CTX_KEY.format(lang='es')))
        self.assertIsNone(cache.get(HOME_STATS_KEY))

    def test_product_save_invalidates_cache(self):
        """Clear home context cache when a product is created."""
        cached_guest_home_context('es')
        Product.objects.create(
            company=self.company,
            category=self.category,
            name='New SKU',
            sku='NEW-1',
            unit_price='10.00',
            currency='USD',
            is_active=True,
        )
        self.assertIsNone(cache.get(HOME_CTX_KEY.format(lang='es')))

    def test_build_guest_home_context_has_merchandising_keys(self):
        """Include promo and featured product keys in guest context."""
        ctx = merch.build_guest_home_context('en')
        self.assertIn('promo_sections', ctx)
        self.assertIn('catalog_breadth_products', ctx)
        self.assertGreaterEqual(len(ctx['featured_products']), 1)

    def test_home_view_uses_cache_for_guest(self):
        """Warm home context cache on anonymous GET /."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(cache.get(HOME_CTX_KEY.format(lang='en')))

    @override_settings(
        CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
                'LOCATION': 'tradeflow_cache_missing',
            }
        }
    )
    def test_home_view_works_when_cache_table_missing(self):
        """Serve home 200 when DatabaseCache table is missing."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
