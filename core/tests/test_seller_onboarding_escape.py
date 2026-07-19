"""Incomplete sellers must escape company wizard without redirect loops."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile
from core.utils.access_gating import onboarding_redirect_name


@override_settings(
    DEBUG=True,
    REQUIRE_EMAIL_VERIFICATION=False,
    EXPO_DEMO_MODE=False,
    AXES_ENABLED=False,
)
class SellerOnboardingEscapeTests(TestCase):
    """Assert browse/home escape hatches while portal stays gated."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='escape_seller',
            email='escape@seller.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=self.user,
            role='seller',
            email_verificado=True,
        )
        self.client.force_login(self.user)

    def test_browse_scope_does_not_force_company_wizard(self):
        """Browse gate ignores pending company setup."""
        self.assertIsNone(onboarding_redirect_name(self.user, scope='browse'))
        self.assertEqual(
            onboarding_redirect_name(self.user, scope='restricted'),
            'seller_onboarding_company',
        )

    def test_home_and_catalog_do_not_loop_to_wizard(self):
        """Home and catalog stay reachable without company data."""
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        catalog = self.client.get('/catalogo/')
        self.assertEqual(catalog.status_code, 200)
        self.assertNotIn('/onboarding/vendedor/', catalog.get('Location', ''))

    def test_portal_still_requires_company_wizard(self):
        """Seller portal keeps forcing company onboarding."""
        portal = self.client.get(reverse('portal_seller'))
        self.assertEqual(portal.status_code, 302)
        self.assertIn('/onboarding/vendedor/', portal.url)

    def test_wizard_exposes_escape_links(self):
        """Company form offers continue-later (home) and logout."""
        resp = self.client.get(reverse('seller_onboarding_company'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Continuar más tarde')
        self.assertContains(resp, reverse('home'))
        self.assertContains(resp, reverse('logout'))
