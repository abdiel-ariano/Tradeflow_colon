"""Diagnóstico y resiliencia SaaS."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import build_plan_page_context_safe, ensure_default_plans
from core.utils.saas_platform import bootstrap_saas_datastore, get_saas_health


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class SaasPlatformHealthTests(TestCase):
    def setUp(self):
        ensure_default_plans()
        self.user = User.objects.create_user('saas_h', password='x', email='h@test.com')
        UserProfile.objects.create(user=self.user, role='seller')
        self.company = Company.objects.create(name='Health Co', owner=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    def test_health_reports_plans(self):
        health = get_saas_health()
        self.assertGreaterEqual(health['plans_count'], 4)
        self.assertTrue(health['checkout_table_ready'])

    def test_bootstrap_creates_plans_if_missing(self):
        SaasPlan.objects.all().delete()
        health = bootstrap_saas_datastore()
        self.assertGreaterEqual(health['plans_count'], 4)

    def test_plan_page_renders_with_content(self):
        r = self.client.get(reverse('seller_plan_consumo'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'sp-plans-page')
        self.assertContains(r, 'sp-plan-card-v2')

    def test_safe_context_on_snapshot_failure(self):
        from django.db.utils import OperationalError

        with patch(
            'core.utils.saas_billing.subscription_usage_snapshot',
            side_effect=OperationalError('no such table'),
        ):
            ctx, err = build_plan_page_context_safe(self.company)
        self.assertEqual(err, 'database_schema')
        self.assertTrue(ctx.get('saas_degraded'))
