"""Regression coverage for the full-width TradeFlow admin shell."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=["testserver", "localhost", "*"],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    STAFF_MFA_REQUIRED=False,
)
class TradeFlowAdminLayoutTests(TestCase):
    """Ensure every native admin view keeps the shared TradeFlow layout."""

    def setUp(self):
        """Create a staff operator authorized to open native admin pages."""
        self.operator = User.objects.create_user(
            username="layout.operator",
            password="StrongLayoutPassword123!",
            first_name="Patricia",
            last_name="Vásquez",
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.operator,
            defaults={"role": "admin"},
        )
        self.client.force_login(self.operator)

    def test_native_list_uses_the_compact_header_and_full_canvas(self):
        """A changelist keeps the final header and full-width layout layer."""
        response = self.client.get(
            reverse("admin:core_payment_changelist")
        )
        layout_path = finders.find("css/tradeflow_admin_layout.css")
        continuity_path = finders.find(
            "css/tradeflow_admin_continuity.css"
        )
        unified_path = finders.find(
            "css/tradeflow_admin_unified.css"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'data-tf-admin-header="shared"',
        )
        self.assertContains(response, 'id="admRail"')
        self.assertContains(response, 'data-rail-accordion="multi"')
        self.assertContains(response, 'aria-controls="admRail"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(
            response,
            "css/tradeflow_admin_continuity.css",
        )
        self.assertContains(
            response,
            "css/tradeflow_admin_unified.css",
        )
        self.assertContains(response, "Operations")
        self.assertNotContains(response, "Advanced CRUD")
        self.assertNotContains(response, 'id="nav-sidebar"')
        self.assertNotContains(response, "tf-admin-header-link")
        self.assertIsNotNone(layout_path)
        self.assertIsNotNone(continuity_path)
        self.assertIsNotNone(unified_path)

        layout = Path(layout_path).read_text(encoding="utf-8")
        continuity = Path(continuity_path).read_text(encoding="utf-8")
        unified = Path(unified_path).read_text(encoding="utf-8")

        self.assertIn("--tf-admin-filter-width: 272px", layout)
        self.assertIn("position: fixed !important", layout)
        self.assertIn("width: 100% !important", continuity)
        self.assertIn("overflow-x: visible !important", continuity)
        self.assertIn(
            "width: calc(100vw - var(--tf-admin-rail-width))",
            continuity,
        )
        self.assertIn("body.tf-admin-unified", unified)
        self.assertIn("--tf-admin-header-height: 64px", unified)
        self.assertIn("--tf-admin-rail-width: 252px", unified)
        self.assertIn(".adm-shell.adm-shell--rail-narrow", unified)
        self.assertIn("tf-admin-drawer-open", unified)
        self.assertIn("overflow: hidden !important", unified)

    def test_admin_index_routes_into_ops_dashboard_shell(self):
        """/admin/ no longer renders a second dashboard shell."""
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'id="admRail"')
        self.assertContains(
            dashboard,
            'data-tf-admin-header="shared"',
        )
        self.assertContains(
            dashboard,
            "css/tradeflow_admin_continuity.css",
        )
        self.assertContains(
            dashboard,
            "css/tradeflow_admin_unified.css",
        )
        self.assertNotContains(dashboard, "tf-system-rail")
        self.assertNotContains(dashboard, "Full administration")
