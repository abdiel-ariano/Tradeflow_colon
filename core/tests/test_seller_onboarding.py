"""Tests del wizard de onboarding seller."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import CompanySubscription
from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=True,
)
class SellerOnboardingTests(TestCase):
    def setUp(self):
        ensure_default_plans()
        self.user = User.objects.create_user('seller_ob', password='x', email='ob@test.com')
        UserProfile.objects.create(user=self.user, role='seller', email_verificado=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_wizard_creates_company_and_trial(self):
        url = reverse('seller_onboarding_company_post')
        r = self.client.post(url, {
            'name': 'Nueva Empresa ZLC',
            'ruc': '8-OB-999',
            'address_text': 'Local 1, ZLC',
        })
        self.assertEqual(r.status_code, 302)
        company = Company.objects.get(owner=self.user)
        self.assertEqual(company.name, 'Nueva Empresa ZLC')
        sub = CompanySubscription.objects.get(company=company)
        self.assertEqual(sub.status, 'trialing')

    def test_pending_seller_redirected_to_wizard(self):
        r = self.client.get(reverse('portal_seller'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/onboarding/vendedor/', r.url)
