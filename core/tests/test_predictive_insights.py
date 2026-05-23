"""Tests de acceso a insights predictivos Enterprise."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, get_or_create_subscription


@override_settings(
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class TestPredictiveInsightsAccess(TestCase):
    def setUp(self):
        ensure_default_plans()
        self.client = Client()
        self.user = User.objects.create_user('ent_seller', 'ent@test.pa', 'pass')
        UserProfile.objects.create(user=self.user, role='seller', email_verificado=True)
        self.company = Company.objects.create(
            name='Ent Co',
            ruc='ENT1',
            owner=self.user,
            is_verified=True,
        )
        self.client.login(username='ent_seller', password='pass')

    def test_non_enterprise_sees_upgrade_page(self):
        get_or_create_subscription(self.company)
        resp = self.client.get(reverse('seller_predictive_insights'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ecosistema Enterprise')

    def test_enterprise_sees_insights_panel(self):
        sub = get_or_create_subscription(self.company)
        sub.plan = SaasPlan.objects.get(slug='ecosistema_enterprise')
        sub.save(update_fields=['plan'])
        resp = self.client.get(reverse('seller_predictive_insights'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Forecast 30')
