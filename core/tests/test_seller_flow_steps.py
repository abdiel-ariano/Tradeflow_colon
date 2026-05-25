"""Barras de recorrido seller."""
from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans, get_or_create_subscription, subscription_usage_snapshot


class SellerFlowStepsTests(TestCase):
    def test_flow_steps_present(self):
        ensure_default_plans()
        user = User.objects.create_user('f1', password='x')
        UserProfile.objects.create(user=user, role='seller')
        company = Company.objects.create(name='Flow Co', owner=user)
        get_or_create_subscription(company)
        snap = subscription_usage_snapshot(company)
        self.assertIn('flow_steps', snap)
        self.assertGreaterEqual(len(snap['flow_steps']), 3)
        self.assertIn('journey_pct', snap)
