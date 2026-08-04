"""SaaS datastore health and degraded plan-page resilience.

Seller plan pages must render even when usage snapshots fail,
so CFZ operators can still select a plan after schema drift.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import (
    build_plan_page_context_safe,
    ensure_default_plans,
    plan_monthly_price,
)
from core.utils.saas_plan_catalog import marketing_for_plan
from core.utils.saas_platform import bootstrap_saas_datastore, get_saas_health


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class SaasPlatformHealthTests(TestCase):
    """Assert health, bootstrap, and safe plan context."""

    def setUp(self):
        """Create seller company and ensure default SaaS plans."""
        ensure_default_plans()
        self.user = User.objects.create_user('saas_h', password='x', email='h@test.com')
        UserProfile.objects.create(user=self.user, role='seller')
        self.company = Company.objects.create(name='Health Co', owner=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    def test_health_reports_plans(self):
        """Report exactly the three official plans and ready checkout table."""
        health = get_saas_health()
        self.assertEqual(health['plans_count'], 3)
        self.assertTrue(health['checkout_table_ready'])

    def test_bootstrap_creates_plans_if_missing(self):
        """Recreate default plans when the table is emptied."""
        SaasPlan.objects.all().delete()
        health = bootstrap_saas_datastore()
        self.assertEqual(health['plans_count'], 3)

    def test_official_plan_prices_limits_and_entitlements(self):
        """Keep commercial copy and backend access aligned for every tier."""
        plans = {
            plan.slug: plan
            for plan in SaasPlan.objects.filter(is_active=True)
        }
        self.assertEqual(
            set(plans),
            {'digitalizate', 'expansion', 'corporativo_pro'},
        )

        digitalize = plans['digitalizate']
        self.assertEqual(digitalize.name, 'Digitalize')
        self.assertEqual(
            digitalize.monthly_volume_limit_usd,
            Decimal('15000.00'),
        )
        self.assertEqual(digitalize.ad_credits_monthly, 50)
        self.assertFalse(digitalize.api_access)

        expansion = plans['expansion']
        self.assertEqual(expansion.monthly_volume_limit_usd, Decimal('50000.00'))
        self.assertEqual(expansion.ad_credits_monthly, 200)
        self.assertTrue(expansion.api_access)
        self.assertFalse(expansion.predictive_ai)

        corporate = plans['corporativo_pro']
        self.assertIsNone(corporate.monthly_volume_limit_usd)
        self.assertEqual(corporate.ad_credits_monthly, 500)
        self.assertTrue(corporate.api_access)
        self.assertTrue(corporate.logistics_webhooks)
        self.assertTrue(corporate.predictive_ai)
        self.assertTrue(corporate.priority_support)

        self.assertEqual(plan_monthly_price('digitalizate'), Decimal('49.99'))
        self.assertEqual(plan_monthly_price('expansion'), Decimal('135.99'))
        self.assertEqual(plan_monthly_price('corporativo_pro'), Decimal('230.99'))
        self.assertEqual(marketing_for_plan(digitalize)['commission'], '5%')
        self.assertEqual(marketing_for_plan(expansion)['commission'], '4%')
        self.assertEqual(marketing_for_plan(corporate)['commission'], '3.5%')

    def test_plan_page_renders_with_content(self):
        """Render the complete English three-plan comparison."""
        r = self.client.get(reverse('seller_plan_consumo'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'sp-plans-page')
        self.assertContains(r, 'sp-plan-card-v2')
        self.assertContains(r, 'USD 49.99')
        self.assertContains(r, 'USD 135.99')
        self.assertContains(r, 'USD 230.99')
        self.assertContains(r, '+ 5% commission')
        self.assertContains(r, '+ 4% commission')
        self.assertContains(r, '+ 3.5% commission')
        self.assertContains(r, 'Everything included in Digitalize')
        self.assertContains(r, 'Three fixed featured ads every month')
        self.assertNotContains(r, 'Digitalízate')
        self.assertNotContains(r, 'Enterprise Ecosystem')

    def test_safe_context_on_snapshot_failure(self):
        """Mark saas_degraded when usage snapshot raises DB errors."""
        from django.db.utils import OperationalError

        with patch(
            'core.utils.saas_billing.subscription_usage_snapshot',
            side_effect=OperationalError('no such table'),
        ):
            ctx, err = build_plan_page_context_safe(self.company)
        self.assertEqual(err, 'database_schema')
        self.assertTrue(ctx.get('saas_degraded'))
