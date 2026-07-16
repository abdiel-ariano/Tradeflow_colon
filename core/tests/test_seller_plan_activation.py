"""Post-trial plan activation without allowing downgrades.

Past-due sellers may pay at or above the recommended plan so
volume from the trial informs CFZ SaaS upgrades.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.enterprise_models import CompanyPlanCheckout, SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import (
    can_select_plan_for_activation,
    CheckoutMode,
    ensure_default_plans,
    get_or_create_subscription,
)
from core.utils.seller_lifecycle import finalize_trial_period, start_seller_trial


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    ALLOW_MOCK_PLAN_PAYMENT=True,
)
class SellerPlanActivationTests(TestCase):
    """Assert activation eligibility and checkout payment paths."""

    def setUp(self):
        """Start a seller trial and log the owner in."""
        ensure_default_plans()
        self.user = User.objects.create_user('seller_act', password='x', email='act@test.com')
        UserProfile.objects.create(user=self.user, role='seller', email_verificado=True)
        self.company = Company.objects.create(name='Act Co', owner=self.user, ruc='8-A-1')
        start_seller_trial(self.company)
        self.client = Client()
        self.client.force_login(self.user)

    def _move_to_past_due_zero_sales(self):
        """Expire trial and finalize into past_due with zero sales."""
        sub = self.company.subscription
        sub.current_period_end = timezone.now() - timedelta(hours=1)
        sub.save(update_fields=['current_period_end'])
        finalize_trial_period(self.company)
        self.company.subscription.refresh_from_db()

    def test_past_due_zero_sales_can_pay_digitalizate(self):
        """Allow Digitalízate checkout when recommendation is entry."""
        self._move_to_past_due_zero_sales()
        ok, err = can_select_plan_for_activation(
            self.company,
            'digitalizate',
            mode=CheckoutMode.TRIAL_ACTIVATION,
        )
        self.assertTrue(ok, err)
        r = self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'digitalizate'}))
        self.assertEqual(r.status_code, 200)

    def test_past_due_high_volume_blocks_digitalizate(self):
        """Block Digitalízate when Expansion is recommended."""
        self._move_to_past_due_zero_sales()
        sub = self.company.subscription
        expansion = SaasPlan.objects.get(slug='expansion')
        sub.trial_volume_usd = Decimal('28000')
        sub.recommended_plan = expansion
        sub.save()
        ok, err = can_select_plan_for_activation(
            self.company,
            'digitalizate',
            mode=CheckoutMode.TRIAL_ACTIVATION,
        )
        self.assertFalse(ok)
        self.assertEqual(err, 'below_recommended_plan')

    def test_trial_upgrade_payment_activates(self):
        """complete_plan_checkout activates Expansion from trial."""
        from core.utils.saas_billing import create_plan_checkout, complete_plan_checkout, CheckoutMode

        checkout = create_plan_checkout(self.company, 'expansion', mode=CheckoutMode.TRIAL_UPGRADE)
        sub = complete_plan_checkout(checkout, provider='mock', txn_ref='TEST')
        self.assertEqual(sub.status, 'active')
        self.assertEqual(sub.plan.slug, 'expansion')
        checkout.refresh_from_db()
        self.assertEqual(checkout.status, 'paid')

    def test_trial_upgrade_http_payment_activates(self):
        """HTTP mock pay activates Expansion and marks checkout paid."""
        get_r = self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'}))
        self.assertEqual(get_r.status_code, 200)
        pay_url = reverse('seller_plan_checkout_pay', kwargs={'plan_slug': 'expansion'})
        r = self.client.post(pay_url, {'payment_method': 'mock', 'card_name': 'Test'})
        self.assertEqual(r.status_code, 302, msg=f'redirect={r.url}')
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        self.assertEqual(checkout.status, 'paid')
        self.company.subscription.refresh_from_db()
        sub = self.company.subscription
        self.assertEqual(sub.status, 'active')
        self.assertEqual(sub.plan.slug, 'expansion')
