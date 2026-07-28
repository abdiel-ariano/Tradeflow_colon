"""Tests for the shared TradeFlow administration navigation."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


class TradeFlowAdminNavigationTests(TestCase):
    """Keep every administrative route on one visual navigation contract."""

    def setUp(self):
        """Create a staff operator with the platform administrator role."""
        self.operator = User.objects.create_user(
            username="navigation.operator",
            password="StrongNavigationPassword123!",
            first_name="Patricia",
            last_name="Vásquez",
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.operator,
            defaults={"role": "admin"},
        )
        self.client.force_login(self.operator)

    def test_native_admin_uses_the_shared_header_and_rail(self):
        """A Django list renders the same compact shell as the dashboard."""
        response = self.client.get(
            reverse("admin:core_payment_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="admRail"')
        self.assertContains(
            response,
            'data-tf-admin-header="shared"',
        )
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Companies and users")
        self.assertContains(response, "SaaS and platform")
        self.assertContains(response, "Sign out")
        self.assertContains(
            response,
            "css/tradeflow_admin_continuity.css",
        )
        self.assertContains(
            response,
            "css/tradeflow_admin_unified.css",
        )
        self.assertNotContains(response, "DM+Serif+Display")
        self.assertNotContains(response, "tf-system-rail")

    def test_dashboard_uses_the_same_header_and_rail_assets(self):
        """The sales dashboard renders the exact shared rail component."""
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="admRail"')
        self.assertContains(response, "tradeflow_admin_nav.js")
        self.assertContains(
            response,
            "css/tradeflow_admin_continuity.css",
        )
        self.assertContains(
            response,
            "css/tradeflow_admin_unified.css",
        )
        self.assertContains(response, "Companies and users")
        self.assertContains(response, "SaaS and platform")
        self.assertNotContains(response, "js/admin_rail.js")

    def test_accordion_assets_are_route_aware(self):
        """Static assets preserve the active module and visual contract."""
        script_path = finders.find("js/tradeflow_admin_nav.js")
        theme_path = finders.find("css/tradeflow_admin.css")
        layout_path = finders.find("css/tradeflow_admin_layout.css")
        continuity_path = finders.find(
            "css/tradeflow_admin_continuity.css"
        )
        unified_path = finders.find(
            "css/tradeflow_admin_unified.css"
        )

        self.assertIsNotNone(script_path)
        self.assertIsNotNone(theme_path)
        self.assertIsNotNone(layout_path)
        self.assertIsNotNone(continuity_path)
        self.assertIsNotNone(unified_path)

        script = Path(script_path).read_text(encoding="utf-8")
        theme = Path(theme_path).read_text(encoding="utf-8")
        layout = Path(layout_path).read_text(encoding="utf-8")
        continuity = Path(continuity_path).read_text(encoding="utf-8")
        unified = Path(unified_path).read_text(encoding="utf-8")

        self.assertIn("highlightSharedRail", script)
        self.assertIn("routeMatches", script)
        self.assertIn("buildAccordion", script)
        self.assertIn("tradeflow-admin-group", script)
        self.assertIn(".tf-rail-group__summary", theme)
        self.assertIn('"Montserrat"', layout)
        self.assertNotIn('"DM Serif Display"', layout)
        self.assertIn("--tf-admin-header-height: 64px", continuity)
        self.assertIn("--tf-admin-rail-width: 252px", continuity)
        self.assertIn("#header.tf-admin-header", unified)
        self.assertIn("--tf-admin-header-height: 64px", unified)
        self.assertIn("--tf-admin-rail-width: 252px", unified)
