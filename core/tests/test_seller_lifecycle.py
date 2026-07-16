"""Seller trial, plan recommendation, grace, and medium churn.

Digitalízate trials convert to past_due with recommendations;
expired grace hides the company from the public marketplace.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.enterprise_models import CompanySubscription, SaasPlan
from core.models import Company, UserProfile
from core.utils.saas_billing import ensure_default_plans
from core.utils.seller_lifecycle import (
    apply_medium_churn,
    company_marketplace_visible,
    finalize_trial_period,
    recommend_plan_slug,
    start_seller_trial,
)


class SellerLifecycleTests(TestCase):
    """Assert trial start, finalize, recommend, and churn helpers."""

    def setUp(self):
        """Create seller company after ensuring default SaaS plans."""
        ensure_default_plans()
        self.user = User.objects.create_user('seller_lc', password='x', email='lc@test.com')
        UserProfile.objects.create(user=self.user, role='seller', email_verificado=True)
        self.company = Company.objects.create(name='LC Co', owner=self.user, ruc='8-LC-1')

    def test_recommend_plan_slug_thresholds(self):
        """Map trial volume USD to the correct plan slug."""
        self.assertEqual(recommend_plan_slug(Decimal('0')), 'digitalizate')
        self.assertEqual(recommend_plan_slug(Decimal('12000')), 'digitalizate')
        self.assertEqual(recommend_plan_slug(Decimal('12001')), 'expansion')
        self.assertEqual(recommend_plan_slug(Decimal('40001')), 'corporativo_pro')
        self.assertEqual(recommend_plan_slug(Decimal('100001')), 'ecosistema_enterprise')

    def test_start_seller_trial_creates_trialing(self):
        """Start Digitalízate trial without auto_renew."""
        sub = start_seller_trial(self.company)
        self.assertEqual(sub.status, 'trialing')
        self.assertEqual(sub.plan.slug, 'digitalizate')
        self.assertFalse(sub.auto_renew)
        self.assertGreater(sub.current_period_end, timezone.now())

    def test_finalize_trial_moves_to_past_due(self):
        """Move expired trials to past_due with grace and recommend."""
        sub = start_seller_trial(self.company)
        sub.current_period_end = timezone.now() - timedelta(hours=1)
        sub.save(update_fields=['current_period_end'])
        result = finalize_trial_period(self.company)
        self.assertIsNotNone(result)
        result.refresh_from_db()
        self.assertEqual(result.status, 'past_due')
        self.assertIsNotNone(result.recommended_plan)
        self.assertIsNotNone(result.grace_ends_at)

    def test_medium_churn_hides_from_marketplace(self):
        """Cancel after grace and hide company from marketplace."""
        sub = start_seller_trial(self.company)
        sub.status = 'past_due'
        sub.grace_ends_at = timezone.now() - timedelta(days=1)
        sub.save()
        apply_medium_churn(self.company)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'cancelled')
        self.assertFalse(company_marketplace_visible(self.company))
