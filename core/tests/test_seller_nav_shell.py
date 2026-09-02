"""Seller chrome: marketplace outside portal, no navy tf-nav-seller."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Company, UserProfile
from core.utils.seller_lifecycle import start_seller_trial


@override_settings(
    DEBUG=True,
    REQUIRE_EMAIL_VERIFICATION=False,
    EXPO_DEMO_MODE=False,
    AXES_ENABLED=False,
)
class SellerNavShellTests(TestCase):
    """Assert retired navy seller top-nav is gone from seller surfaces."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='nav_seller',
            email='nav@seller.pa',
            password='TestPass123!',
            first_name='Nav',
            last_name='Seller',
        )
        UserProfile.objects.create(
            user=self.user,
            role='seller',
            email_verificado=True,
        )
        self.company = Company.objects.create(
            name='Nav Seller Co',
            ruc='8-NAV-1',
            owner=self.user,
        )
        start_seller_trial(self.company)
        self.client.force_login(self.user)

    def test_profile_uses_marketplace_nav_not_navy_seller(self):
        """/perfil/ for sellers uses marketplace chrome."""
        resp = self.client.get(reverse('mi_perfil'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertNotIn('id="tf-nav-seller"', body)
        self.assertNotIn('class="tf-nav tf-navbar"', body)
        self.assertIn('cat-catalog-nav', body)
        self.assertIn('Seller portal', body)

    def test_portal_has_workspace_shell_without_navy_top_nav(self):
        """/mi-tienda/ keeps sidebar shell and omits navy top nav markup."""
        resp = self.client.get(reverse('portal_seller'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertNotIn('id="tf-nav-seller"', body)
        self.assertNotIn('class="tf-nav tf-navbar"', body)
        self.assertIn('sp-dash-shell', body)
        self.assertIn('sp-dash-side', body)

    def test_onboarding_company_has_no_navy_seller_nav(self):
        """Incomplete sellers never see the retired navy seller bar."""
        pending = User.objects.create_user(
            username='pending_nav',
            email='pending_nav@seller.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=pending,
            role='seller',
            email_verificado=True,
        )
        self.client.force_login(pending)
        resp = self.client.get(reverse('seller_onboarding_company'))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertNotIn('id="tf-nav-seller"', body)
        self.assertNotIn('class="tf-nav tf-navbar"', body)
        self.assertIn('cat-catalog-nav', body)
