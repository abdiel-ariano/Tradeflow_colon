"""Tests de gates del portal seller según estado de suscripción."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, ensure_demo_subscription
from core.utils.seller_lifecycle import start_seller_trial


@override_settings(
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=True,
)
class SellerTrialGatesTests(TestCase):
    def setUp(self):
        ensure_default_plans()
        self.user = User.objects.create_user('seller_gate', password='x', email='gate@test.com')
        UserProfile.objects.create(user=self.user, role='seller', email_verificado=True)
        self.company = Company.objects.create(name='Gate Co', owner=self.user, ruc='8-G-1')
        self.client = Client()
        self.client.force_login(self.user)

    def test_trialing_portal_accessible(self):
        start_seller_trial(self.company)
        r = self.client.get(reverse('portal_seller'))
        self.assertEqual(r.status_code, 200)

    def test_past_due_redirects_to_activation(self):
        sub = start_seller_trial(self.company)
        sub.status = 'past_due'
        sub.grace_ends_at = timezone.now() + timedelta(days=5)
        sub.recommended_plan = sub.plan
        sub.save()
        r = self.client.get(reverse('portal_seller'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/plan/activar/', r.url)

    def test_cancelled_shows_inactive_page(self):
        ensure_demo_subscription(self.company, status='cancelled')
        r = self.client.get(reverse('portal_seller'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/cuenta-inactiva/', r.url)
