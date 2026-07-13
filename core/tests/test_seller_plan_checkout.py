"""Checkout de planes seller."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import CompanyPlanCheckout
from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, ensure_demo_subscription


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class SellerPlanCheckoutTests(TestCase):
    def setUp(self):
        """Setup."""
        ensure_default_plans()
        self.user = User.objects.create_user('seller_chk', password='x', email='s@test.com')
        UserProfile.objects.create(user=self.user, role='seller')
        self.company = Company.objects.create(name='Checkout Co', owner=self.user)
        ensure_demo_subscription(self.company, status='active')
        self.client = Client()
        self.client.force_login(self.user)

    def test_checkout_page_loads(self):
        """Test checkout page loads."""
        url = reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Pay and activate')
        self.assertTrue(
            CompanyPlanCheckout.objects.filter(
                company=self.company,
                target_plan__slug='expansion',
                status='pending',
            ).exists()
        )

    def test_payment_activates_plan(self):
        """Test payment activates plan."""
        self.client.get(reverse('seller_plan_checkout', kwargs={'plan_slug': 'expansion'}))
        pay_url = reverse('seller_plan_checkout_pay', kwargs={'plan_slug': 'expansion'})
        r = self.client.post(pay_url, {'payment_method': 'mock', 'card_name': 'Test User'})
        self.assertEqual(r.status_code, 302)
        self.company.subscription.refresh_from_db()
        self.assertEqual(self.company.subscription.plan.slug, 'expansion')
        checkout = CompanyPlanCheckout.objects.filter(company=self.company).latest('created_at')
        self.assertEqual(checkout.status, 'paid')

    def test_upgrade_redirects_to_checkout(self):
        """Test upgrade redirects to checkout."""
        r = self.client.post(
            reverse('seller_upgrade_plan'),
            {'plan_slug': 'expansion'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn('/plan/pago/expansion', r.url)
