"""Seller company onboarding wizard and trial bootstrap.

New CFZ sellers create a company + Digitalízate trial; DB and
empty-logo errors must stay on the form instead of 500s.
"""
from django.db import IntegrityError
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
    """Assert wizard POST, error handling, and portal redirect."""

    def setUp(self):
        """Log in a seller without a company yet."""
        ensure_default_plans()
        self.user = User.objects.create_user('seller_ob', password='x', email='ob@test.com')
        UserProfile.objects.create(user=self.user, role='seller', email_verificado=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_wizard_creates_company_and_trial(self):
        """Create company and trialing subscription from wizard POST."""
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

    def test_wizard_survives_empty_logo_upload(self):
        """Accept empty logo uploads without returning 500."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        empty = SimpleUploadedFile('logo.png', b'', content_type='image/png')
        url = reverse('seller_onboarding_company_post')
        r = self.client.post(url, {
            'name': 'Empresa Logo Vacio',
            'ruc': '8-OB-LOGO',
            'address_text': 'Local 2',
            'logo': empty,
        })
        self.assertEqual(r.status_code, 302, msg=r.content[:500] if r.status_code >= 400 else '')
        self.assertTrue(Company.objects.filter(owner=self.user, ruc='8-OB-LOGO').exists())

    def test_wizard_db_error_renders_form_not_500(self):
        """Show database error message on IntegrityError."""
        from unittest.mock import patch

        url = reverse('seller_onboarding_company_post')
        with patch(
            'core.views_seller_onboarding.Company.objects.create',
            side_effect=IntegrityError('simulated'),
        ):
            r = self.client.post(url, {
                'name': 'Empresa Fail',
                'ruc': '8-OB-FAIL',
                'address_text': 'Local 3',
            })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'error de base de datos')

    def test_pending_seller_redirected_to_wizard(self):
        """Redirect sellers without companies to onboarding."""
        r = self.client.get(reverse('portal_seller'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/onboarding/vendedor/', r.url)
