"""Corporate Pro predictive insights portal access gates.

Only Corporate Pro subscribers see forecasts; lower
plans get an upgrade surface instead of empty analytics.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, ensure_demo_subscription


@override_settings(
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class TestPredictiveInsightsAccess(TestCase):
    """Assert upgrade vs insights panel by SaaS plan."""

    def setUp(self):
        """Create verified seller company on a demo subscription."""
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

    def test_digitalize_sees_corporate_pro_upgrade_page(self):
        """Show Corporate Pro upgrade messaging on Digitalize."""
        ensure_demo_subscription(self.company)
        resp = self.client.get(reverse('seller_predictive_insights'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Available on Corporate Pro')

    def test_corporate_pro_sees_insights_panel(self):
        """Render the 30-day forecast panel for Corporate Pro subscribers."""
        sub = ensure_demo_subscription(self.company)
        sub.plan = SaasPlan.objects.get(slug='corporativo_pro')
        sub.save(update_fields=['plan'])
        resp = self.client.get(reverse('seller_predictive_insights'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '30-day forecast')
