"""Hot-path cache: company IDs, spotlights, mega-menu, seller dash, session flag."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Category, Company, Product, UserProfile
from core.utils.saas_billing import ensure_demo_subscription, subscription_usage_snapshot
from core.utils.tradeflow_cache import (
    ACTIVE_COMPANY_IDS_KEY,
    MEGA_MENU_KEY,
    SELLER_DASH_KEY,
    SPOTLIGHTS_KEY,
    cached_buyer_mega_menu_panels,
    cached_category_spotlights,
    cached_marketplace_active_company_ids,
    cached_seller_portal_dashboard,
    invalidate_merchandising_cache,
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'tradeflow-perf-cache',
        }
    },
    CACHE_TTL_ACTIVE_COMPANIES=120,
    CACHE_TTL_SPOTLIGHTS=120,
    CACHE_TTL_MEGA_MENU=180,
    CACHE_TTL_SELLER_DASH=45,
    SESSION_SAVE_EVERY_REQUEST=False,
)
class PerfHotpathCacheTests(TestCase):
    """Assert new shared fragments warm and invalidate correctly."""

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(name='Perf Co', is_verified=True)
        ensure_demo_subscription(self.company)
        self.category = Category.objects.create(name='Perf Cat')
        for i in range(4):
            Product.objects.create(
                company=self.company,
                category=self.category,
                name=f'Perf Item {i}',
                sku=f'PERF-{i}',
                unit_price='10.00',
                currency='USD',
                is_active=True,
            )

    def test_active_company_ids_cached(self):
        """Warm ACTIVE_COMPANY_IDS_KEY on second call."""
        first = cached_marketplace_active_company_ids()
        second = cached_marketplace_active_company_ids()
        self.assertIn(self.company.pk, first)
        self.assertEqual(first, second)
        self.assertIsNotNone(cache.get(ACTIVE_COMPANY_IDS_KEY))

    def test_spotlights_and_mega_menu_cached(self):
        """Warm spotlight and mega-menu keys."""
        rows = cached_category_spotlights(4, 4)
        self.assertTrue(rows)
        self.assertIsNotNone(cache.get(SPOTLIGHTS_KEY.format(per=4, cats=4)))
        panels = cached_buyer_mega_menu_panels(8, 6)
        self.assertTrue(panels)
        self.assertIsNotNone(cache.get(MEGA_MENU_KEY.format(cats=8, per=6)))

    def test_invalidate_clears_new_merch_keys(self):
        """invalidate_merchandising_cache drops company/spotlight/mega keys."""
        cached_marketplace_active_company_ids()
        cached_category_spotlights(4, 4)
        cached_buyer_mega_menu_panels()
        invalidate_merchandising_cache()
        self.assertIsNone(cache.get(ACTIVE_COMPANY_IDS_KEY))
        self.assertIsNone(cache.get(SPOTLIGHTS_KEY.format(per=4, cats=4)))
        self.assertIsNone(cache.get(MEGA_MENU_KEY.format(cats=8, per=6)))

    def test_saas_snapshot_refresh_false_skips_rewrite(self):
        """refresh=False reuses existing monthly usage row."""
        snap1 = subscription_usage_snapshot(self.company, refresh=True)
        snap2 = subscription_usage_snapshot(self.company, refresh=False)
        self.assertIsNotNone(snap1['usage'])
        self.assertEqual(snap1['usage'].pk, snap2['usage'].pk)

    def test_seller_dashboard_cached_and_portal_200(self):
        """Portal home uses cached dash payload and responds 200."""
        owner = User.objects.create_user(
            username='perf_seller',
            email='perf@seller.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=owner, role='seller', email_verificado=True)
        self.company.owner = owner
        self.company.save(update_fields=['owner'])
        data = cached_seller_portal_dashboard(self.company.pk)
        self.assertIn('ordenes_semana', data)
        self.assertIsNotNone(
            cache.get(SELLER_DASH_KEY.format(company_id=self.company.pk, days=30))
        )
        client = Client()
        client.force_login(owner)
        resp = client.get(reverse('portal_seller'))
        self.assertEqual(resp.status_code, 200)
