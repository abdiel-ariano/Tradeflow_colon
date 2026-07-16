"""Seller journey progress steps inside usage snapshots.

Plan and onboarding UIs show flow_steps and journey_pct so CFZ
sellers know what remains before a healthy storefront.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, ensure_demo_subscription, subscription_usage_snapshot


class SellerFlowStepsTests(TestCase):
    """Assert subscription_usage_snapshot includes journey fields."""

    def test_flow_steps_present(self):
        """Expose at least three flow_steps and a journey_pct."""
        ensure_default_plans()
        user = User.objects.create_user('f1', password='x')
        UserProfile.objects.create(user=user, role='seller')
        company = Company.objects.create(name='Flow Co', owner=user)
        ensure_demo_subscription(company)
        snap = subscription_usage_snapshot(company)
        self.assertIn('flow_steps', snap)
        self.assertGreaterEqual(len(snap['flow_steps']), 3)
        self.assertIn('journey_pct', snap)
