"""B2B company onboarding, manual verification and activation."""
from django.db import IntegrityError
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from core.enterprise_models import CompanySubscription
from core.models import Company, CompanyMembership, UserProfile
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

    def _proof(self):
        """Return a minimal PDF accepted by the upload security gate."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(
            'aviso-operacion.pdf',
            b'%PDF-1.4\nTradeFlow test document',
            content_type='application/pdf',
        )

    def _company_payload(self, **overrides):
        data = {
            'name': 'Nueva Empresa ZLC',
            'legal_name': 'Nueva Empresa ZLC, S.A.',
            'ruc': '8-OB-999',
            'dv': '12',
            'business_email': 'empresa@test.pa',
            'business_phone': '+50760000000',
            'business_role': 'seller',
            'address_text': 'Local 1, ZLC',
            'verification_document': self._proof(),
        }
        data.update(overrides)
        return data

    def test_wizard_creates_pending_company_and_owner_membership(self):
        """Company is pending, not verified or activated, after submission."""
        url = reverse('company_onboarding_post')
        r = self.client.post(url, {
            **self._company_payload(),
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('/onboarding/empresa/estado/', r.url)
        company = Company.objects.get(owner=self.user)
        self.assertEqual(company.name, 'Nueva Empresa ZLC')
        self.assertEqual(company.verification_status, 'pending')
        self.assertFalse(company.is_verified)
        self.assertFalse(CompanySubscription.objects.filter(company=company).exists())
        membership = CompanyMembership.objects.get(company=company, user=self.user)
        self.assertEqual(membership.role, 'owner')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.business_role_intent, 'seller')
        self.assertIsNotNone(self.user.profile.onboarding_completed_at)

    def test_wizard_survives_empty_logo_upload(self):
        """Accept empty logo uploads without returning 500."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        empty = SimpleUploadedFile('logo.png', b'', content_type='image/png')
        url = reverse('company_onboarding_post')
        r = self.client.post(url, self._company_payload(
            name='Empresa Logo Vacio',
            legal_name='Empresa Logo Vacio, S.A.',
            ruc='8-OB-LOGO',
            address_text='Local 2',
            logo=empty,
        ))
        self.assertEqual(r.status_code, 302, msg=r.content[:500] if r.status_code >= 400 else '')
        self.assertTrue(Company.objects.filter(owner=self.user, ruc='8-OB-LOGO').exists())

    def test_wizard_db_error_renders_form_not_500(self):
        """Show database error message on IntegrityError."""
        from unittest.mock import patch

        url = reverse('company_onboarding_post')
        with patch(
            'core.views_seller_onboarding.Company.objects.create',
            side_effect=IntegrityError('simulated'),
        ):
            r = self.client.post(url, self._company_payload(
                name='Empresa Fail',
                legal_name='Empresa Fail, S.A.',
                ruc='8-OB-FAIL',
                address_text='Local 3',
            ))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'database error')

    def test_invalid_document_is_rejected_before_storage(self):
        """Reject a renamed executable/HTML payload instead of creating a company."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        invalid = SimpleUploadedFile(
            'aviso-operacion.pdf',
            b'<html><script>alert(1)</script></html>',
            content_type='application/pdf',
        )
        r = self.client.post(
            reverse('company_onboarding_post'),
            self._company_payload(
                ruc='8-OB-BADFILE',
                verification_document=invalid,
            ),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'valid PDF or image')
        self.assertFalse(Company.objects.filter(ruc='8-OB-BADFILE').exists())

    def test_ruc_owned_by_another_account_cannot_be_claimed(self):
        """Do not let a second account replace the owner of an existing RUC."""
        other = User.objects.create_user('other_owner', password='x')
        Company.objects.create(
            name='Empresa Existente',
            legal_name='Empresa Existente, S.A.',
            ruc='8-OB-OWNED',
            dv='10',
            business_email='legal@existente.pa',
            verification_document='companies/verification/existing.pdf',
            owner=other,
        )

        r = self.client.post(
            reverse('company_onboarding_post'),
            self._company_payload(ruc='8-OB-OWNED'),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'already linked to another account')
        self.assertEqual(Company.objects.get(ruc='8-OB-OWNED').owner, other)

    def test_verified_company_owner_is_not_downgraded_on_reassociation(self):
        """An authorized representative keeps the company's verified identity."""
        reviewer = User.objects.create_user('verified_reviewer', password='x', is_staff=True)
        company = Company.objects.create(
            name='Nueva Empresa ZLC',
            legal_name='Nueva Empresa ZLC, S.A.',
            ruc='8-OB-999',
            dv='12',
            business_email='original@test.pa',
            verification_document='companies/verification/existing.pdf',
            owner=self.user,
            business_role='seller',
        )
        company.mark_verified(reviewer)

        response = self.client.post(
            reverse('company_onboarding_post'),
            self._company_payload(),
        )

        self.assertEqual(response.status_code, 302)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'verified')
        self.assertTrue(company.is_verified)
        self.assertTrue(
            CompanyMembership.objects.filter(company=company, user=self.user).exists()
        )

    def test_unowned_verified_ruc_requires_manual_authorization(self):
        """Knowing a verified RUC is insufficient to claim its company account."""
        reviewer = User.objects.create_user('claim_reviewer', password='x', is_staff=True)
        company = Company.objects.create(
            name='Empresa Verificada',
            legal_name='Empresa Verificada, S.A.',
            ruc='8-OB-VERIFIED',
            dv='12',
            business_email='legal@verified.pa',
            verification_document='companies/verification/verified.pdf',
            business_role='seller',
        )
        company.mark_verified(reviewer)

        response = self.client.post(
            reverse('company_onboarding_post'),
            self._company_payload(
                ruc='8-OB-VERIFIED',
                name='Intento de Reclamo',
                legal_name='Empresa Verificada, S.A.',
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already verified')
        company.refresh_from_db()
        self.assertIsNone(company.owner_id)
        self.assertEqual(company.verification_status, 'verified')
        self.assertFalse(
            CompanyMembership.objects.filter(company=company, user=self.user).exists()
        )

    def test_pending_seller_redirected_to_wizard(self):
        """Redirect sellers without companies to onboarding."""
        r = self.client.get(reverse('portal_seller'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/onboarding/empresa/', r.url)

    def test_verified_seller_activates_trial_from_status(self):
        """Subscription starts only after a human reviewer verifies the company."""
        self.client.post(reverse('company_onboarding_post'), self._company_payload())
        company = Company.objects.get(owner=self.user)
        reviewer = User.objects.create_user('reviewer_ob', password='x', is_staff=True)
        company.mark_verified(reviewer)

        r = self.client.get(reverse('company_verification_status'))
        self.assertEqual(r.status_code, 200)
        sub = CompanySubscription.objects.get(company=company)
        self.assertEqual(sub.status, 'trialing')

    def test_buyer_company_uses_same_real_verification_flow(self):
        """A B2B buyer creates a company instead of consumer preferences."""
        self.user.profile.role = 'buyer'
        self.user.profile.business_role_intent = 'buyer'
        self.user.profile.save(update_fields=['role', 'business_role_intent'])

        r = self.client.post(
            reverse('company_onboarding_post'),
            self._company_payload(business_role='buyer'),
        )
        self.assertEqual(r.status_code, 302)
        company = Company.objects.get(owner=self.user)
        self.assertTrue(company.can_buy)
        self.assertFalse(company.can_sell)
        self.assertEqual(company.verification_status, 'pending')


    def test_legacy_buyer_uses_company_identity_instead_of_consumer_wizard(self):
        """Legacy buyers are treated as businesses and asked for RUC/DV."""
        profile = self.user.profile
        profile.role = 'buyer'
        profile.business_role_intent = ''
        profile.onboarding_completed_at = None
        profile.save(update_fields=[
            'role', 'business_role_intent', 'onboarding_completed_at',
        ])

        response = self.client.get(reverse('company_onboarding'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form_business_role'], 'buyer')

    def test_consumer_buyer_wizard_route_names_are_retired(self):
        """No post-login path can send a business into the old B2C wizard."""
        with self.assertRaises(NoReverseMatch):
            reverse('buyer_onboarding_step1')


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=True,
    EXPO_DEMO_MODE=True,
)
class SellerOnboardingExpoDemoTests(TestCase):
    """Company KYB auto-verifies in Expo demo mode for walkthroughs."""

    def setUp(self):
        ensure_default_plans()
        self.user = User.objects.create_user('seller_demo', password='x', email='demo@test.com')
        UserProfile.objects.create(user=self.user, role='buyer', email_verificado=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _company_payload(self, **overrides):
        data = {
            'name': 'Centro Superate Motta',
            'legal_name': 'Centro Superate Motta Colón, S.A.',
            'ruc': '8-DEMO-001',
            'dv': '12',
            'business_email': 'demo.onboarding@test.pa',
            'business_phone': '+50760000000',
            'business_role': 'buyer',
            'address_text': 'Colón, ZLC, Local demo 12',
        }
        data.update(overrides)
        return data

    def test_expo_demo_verifies_company_without_document(self):
        """Demo mode skips manual review and does not require an upload."""
        response = self.client.post(
            reverse('company_onboarding_post'),
            self._company_payload(),
        )
        self.assertEqual(response.status_code, 302)
        company = Company.objects.get(owner=self.user)
        self.assertEqual(company.verification_status, 'verified')
        self.assertTrue(company.is_verified)
        self.assertTrue(company.verification_document.name)

    def test_expo_demo_replaces_invalid_document_with_stub(self):
        """Invalid uploads do not block demo walkthroughs."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        invalid = SimpleUploadedFile(
            'aviso-operacion.pdf',
            b'<html><script>alert(1)</script></html>',
            content_type='application/pdf',
        )
        response = self.client.post(
            reverse('company_onboarding_post'),
            {
                **self._company_payload(ruc='8-DEMO-002'),
                'verification_document': invalid,
            },
        )
        self.assertEqual(response.status_code, 302)
        company = Company.objects.get(ruc='8-DEMO-002')
        self.assertEqual(company.verification_status, 'verified')

    def test_expo_demo_unblocks_pending_company_on_status_page(self):
        """Accounts stuck in pending before the flag get verified on status load."""
        company = Company.objects.create(
            name='Empresa Pendiente',
            legal_name='Empresa Pendiente, S.A.',
            ruc='8-DEMO-PENDING',
            dv='12',
            business_email='pending@test.pa',
            verification_document='companies/verification/existing.pdf',
            owner=self.user,
            business_role='buyer',
            verification_status='pending',
        )
        CompanyMembership.objects.create(
            company=company,
            user=self.user,
            role='owner',
            status='active',
        )

        response = self.client.get(reverse('company_verification_status'))

        self.assertEqual(response.status_code, 200)
        company.refresh_from_db()
        self.assertEqual(company.verification_status, 'verified')
