"""Seller plan checkout: mock pay, bank transfer, and renewals.

Bank proof stays pending until admin approval; mock payments
exist for demos. Renewal cron moves elapsed paid periods.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.enterprise_models import CompanyPlanCheckout
from core.models import Company, UserProfile
from core.utils.saas_billing import (
    approve_plan_checkout,
    ensure_default_plans,
    ensure_demo_subscription,
    reject_plan_checkout,
    submit_bank_transfer_payment,
)
from core.utils.seller_lifecycle import mark_paid_period_elapsed, start_seller_trial


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    ALLOW_MOCK_PLAN_PAYMENT=True,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class SellerPlanCheckoutTests(TestCase):
    """Assert checkout page and mock payment when allowed."""

    def setUp(self):
        """Create active seller subscription with mock pay enabled."""
        ensure_default_plans()
        self.user = User.objects.create_user('seller_chk', password='x', email='s@test.com')
        UserProfile.objects.create(user=self.user, role='seller')
        self.company = Company.objects.create(name='Checkout Co', owner=self.user)
        ensure_demo_subscription(self.company, status='active')
        self.client = Client()
        self.client.force_login(self.user)

    def test_checkout_page_loads(self):
        """Render bank transfer fields and pending checkout row."""
        url = reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Bank transfer')
        self.assertContains(r, 'name="transfer_reference"')
        self.assertContains(r, 'TF-CHECKOUT-')
        self.assertContains(r, 'Order summary')
        self.assertContains(r, 'Transfer instructions')
        self.assertContains(r, 'Submit bank transfer')
        self.assertTrue(
            CompanyPlanCheckout.objects.filter(
                company=self.company,
                target_plan__slug='expansion',
                status='pending',
            ).exists()
        )

    def test_mock_payment_activates_plan(self):
        """Activate Expansion immediately via mock card payment."""
        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'}))
        pay_url = reverse('seller_plan_checkout_pay', kwargs={'plan_slug': 'expansion'})
        r = self.client.post(pay_url, {'payment_method': 'mock', 'card_name': 'Test User'})
        self.assertEqual(r.status_code, 302)
        self.company.subscription.refresh_from_db()
        self.assertEqual(self.company.subscription.plan.slug, 'expansion')
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        self.assertEqual(checkout.status, 'paid')

    def test_upgrade_redirects_to_checkout(self):
        """POST upgrade routes to /plan/pago/<slug>."""
        r = self.client.post(
            reverse('seller_upgrade_plan'),
            {'plan_slug': 'expansion'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn('/plan/pago/expansion', r.url)


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    ALLOW_MOCK_PLAN_PAYMENT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class SellerBankCheckoutTests(TestCase):
    """Assert bank transfer pending flow and admin review."""

    def setUp(self):
        """Create seller with mock pay disabled and a superuser."""
        ensure_default_plans()
        self.user = User.objects.create_user('seller_bank', password='x', email='bank@test.com')
        UserProfile.objects.create(user=self.user, role='seller')
        self.company = Company.objects.create(name='Bank Co', owner=self.user)
        ensure_demo_subscription(self.company, status='active')
        self.client = Client()
        self.client.force_login(self.user)
        self.admin = User.objects.create_superuser('admin_bank', 'a@test.com', 'x')

    def test_mock_rejected_when_disabled(self):
        """Keep checkout pending when mock payment is disabled."""
        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'}))
        pay_url = reverse('seller_plan_checkout_pay', kwargs={'plan_slug': 'expansion'})
        r = self.client.post(pay_url, {'payment_method': 'mock', 'card_name': 'Nope'})
        self.assertEqual(r.status_code, 302)
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        self.assertEqual(checkout.status, 'pending')
        self.company.subscription.refresh_from_db()
        self.assertEqual(self.company.subscription.plan.slug, 'digitalizate')

    def test_bank_submit_stays_pending(self):
        """Store bank reference without activating the plan yet."""
        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'}))
        pay_url = reverse('seller_plan_checkout_pay', kwargs={'plan_slug': 'expansion'})
        r = self.client.post(
            pay_url,
            {
                'payment_method': 'bank',
                'transfer_reference': 'TRX-998877',
                'seller_notes': 'Banco General',
            },
        )
        self.assertEqual(r.status_code, 302)
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        self.assertEqual(checkout.status, 'pending')
        self.assertEqual(checkout.provider, 'bank')
        self.assertEqual(checkout.transfer_reference, 'TRX-998877')
        self.company.subscription.refresh_from_db()
        self.assertEqual(self.company.subscription.plan.slug, 'digitalizate')

    def test_bank_submit_survives_proof_storage_error(self):
        """Keep transfer reference if proof_file storage fails."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'corporativo_pro'}))
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        proof = SimpleUploadedFile('receipt.pdf', b'%PDF-1.4 fake', content_type='application/pdf')

        real_save = CompanyPlanCheckout.save

        def flaky_save(self, *args, **kwargs):
            update_fields = kwargs.get('update_fields') or []
            if update_fields and 'proof_file' in update_fields:
                raise OSError('supabase upload failed')
            return real_save(self, *args, **kwargs)

        with patch.object(CompanyPlanCheckout, 'save', flaky_save):
            submit_bank_transfer_payment(
                checkout,
                transfer_reference='STOR-FAIL-99',
                proof_file=proof,
            )

        checkout.refresh_from_db()
        self.assertEqual(checkout.status, 'pending')
        self.assertEqual(checkout.transfer_reference, 'STOR-FAIL-99')
        self.assertEqual(checkout.provider, 'bank')

    def test_corporativo_pro_bank_http_no_500(self):
        """Accept Corporativo Pro bank POST without server errors."""
        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'corporativo_pro'}))
        pay_url = reverse('seller_plan_checkout_pay', kwargs={'plan_slug': 'corporativo_pro'})
        r = self.client.post(
            pay_url,
            {'payment_method': 'bank', 'transfer_reference': 'CORP-5555'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('/confirmar/', r.url)
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        self.assertEqual(checkout.transfer_reference, 'CORP-5555')
        self.assertEqual(checkout.status, 'pending')

    def test_admin_approve_activates_plan(self):
        """Admin approve marks checkout paid and upgrades plan."""
        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'}))
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        submit_bank_transfer_payment(
            checkout,
            transfer_reference='APPROVE-1234',
            seller_notes='ok',
        )
        sub = approve_plan_checkout(
            checkout,
            reviewed_by=self.admin,
            review_notes='funds_received',
        )
        self.assertEqual(sub.plan.slug, 'expansion')
        self.assertEqual(sub.status, 'active')
        checkout.refresh_from_db()
        self.assertEqual(checkout.status, 'paid')
        self.assertEqual(checkout.reviewed_by_id, self.admin.pk)

    def test_admin_reject_keeps_subscription(self):
        """Reject checkout without changing current plan."""
        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'}))
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        submit_bank_transfer_payment(checkout, transfer_reference='REJ-5555')
        reject_plan_checkout(checkout, reviewed_by=self.admin, review_notes='bad_proof')
        checkout.refresh_from_db()
        self.assertEqual(checkout.status, 'rejected')
        self.company.subscription.refresh_from_db()
        self.assertEqual(self.company.subscription.plan.slug, 'digitalizate')


class SellerRenewalCronTests(TestCase):
    """Assert paid-period elapsed helpers and renewal command."""

    def setUp(self):
        """Create seller company for renewal simulations."""
        ensure_default_plans()
        self.user = User.objects.create_user('seller_ren', password='x', email='ren@test.com')
        UserProfile.objects.create(user=self.user, role='seller', email_verificado=True)
        self.company = Company.objects.create(name='Ren Co', owner=self.user, ruc='8-REN-1')

    def test_mark_paid_period_elapsed(self):
        """Move elapsed paid subscriptions to past_due with grace."""
        from core.utils.saas_billing import activate_company_plan

        start_seller_trial(self.company)
        activate_company_plan(self.company, 'expansion', source='test', allow_same_plan=True)
        sub = self.company.subscription
        sub.current_period_end = timezone.now() - timedelta(hours=1)
        sub.save(update_fields=['current_period_end'])
        result = mark_paid_period_elapsed(self.company)
        self.assertIsNotNone(result)
        result.refresh_from_db()
        self.assertEqual(result.status, 'past_due')
        self.assertIsNotNone(result.grace_ends_at)
        self.assertEqual(result.recommended_plan_id, result.plan_id)

    def test_process_seller_subscriptions_renewal(self):
        """process_seller_subscriptions reports renewals=1."""
        from core.utils.saas_billing import activate_company_plan
        from io import StringIO

        start_seller_trial(self.company)
        activate_company_plan(self.company, 'expansion', source='test', allow_same_plan=True)
        sub = self.company.subscription
        sub.current_period_end = timezone.now() - timedelta(hours=2)
        sub.save(update_fields=['current_period_end'])

        out = StringIO()
        call_command('process_seller_subscriptions', stdout=out)
        self.company.subscription.refresh_from_db()
        self.assertEqual(self.company.subscription.status, 'past_due')
        self.assertIn('renewals=1', out.getvalue())
