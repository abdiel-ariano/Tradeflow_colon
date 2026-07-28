"""Tests for language, typography, and compact admin navigation."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


class TradeFlowAdminNavigationTests(TestCase):
    """Keep both administrative shells visually and linguistically aligned."""

    def setUp(self):
        """Create a staff operator with the platform administrator role."""
        self.operator = User.objects.create_user(
            username="navigation.operator",
            password="StrongNavigationPassword123!",
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.operator,
            defaults={"role": "admin"},
        )
        self.client.force_login(self.operator)

    def test_native_admin_uses_product_language_and_typefaces(self):
        """Django lists keep the established English and font contract."""
        response = self.client.get(
            reverse("admin:core_payment_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Control center")
        self.assertContains(response, "Executive metrics")
        self.assertContains(response, "Companies and users")
        self.assertContains(response, "Sign out")
        self.assertContains(response, "family=DM+Serif+Display")
        self.assertNotContains(response, ">Métricas ejecutivas<")
        self.assertNotContains(response, ">Empresas y usuarios<")

    def test_custom_dashboard_loads_the_shared_accordion(self):
        """The existing dashboard receives the same grouped navigation."""
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tradeflow_admin_nav.js")
        self.assertContains(response, "Companies and users")
        self.assertContains(response, "SaaS and audit")

    def test_accordion_assets_are_available_and_route_aware(self):
        """Static assets group links and preserve the active destination."""
        script_path = finders.find("js/tradeflow_admin_nav.js")
        stylesheet_path = finders.find("css/tradeflow_admin.css")
        layout_path = finders.find("css/tradeflow_admin_layout.css")

        self.assertIsNotNone(script_path)
        self.assertIsNotNone(stylesheet_path)
        self.assertIsNotNone(layout_path)

        script = Path(script_path).read_text(encoding="utf-8")
        stylesheet = Path(stylesheet_path).read_text(encoding="utf-8")
        layout = Path(layout_path).read_text(encoding="utf-8")

        self.assertIn("buildAccordion", script)
        self.assertIn("data-accordion-ready", script)
        self.assertIn("tradeflow-admin-group", script)
        self.assertIn(".tf-rail-group__summary", stylesheet)
        self.assertIn('"DM Serif Display"', layout)
        self.assertIn('"Montserrat"', layout)
