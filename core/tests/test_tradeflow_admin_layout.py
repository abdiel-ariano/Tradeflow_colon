"""Regression coverage for the full-width TradeFlow admin shell."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


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

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tf-admin-user-tools")
        self.assertContains(response, "tf-admin-user-avatar")
        self.assertContains(response, "Patricia Vásquez")
        self.assertContains(response, "Sign out")
        self.assertContains(
            response,
            "css/tradeflow_admin_continuity.css",
        )
        self.assertNotContains(response, "tf-admin-header-link")
        self.assertIsNotNone(layout_path)
        self.assertIsNotNone(continuity_path)

        layout = Path(layout_path).read_text(encoding="utf-8")
        continuity = Path(continuity_path).read_text(encoding="utf-8")

        self.assertIn("--tf-admin-filter-width: 272px", layout)
        self.assertIn("position: fixed !important", layout)
        self.assertIn("width: 100% !important", continuity)
        self.assertIn("overflow-x: visible !important", continuity)
        self.assertIn(
            "width: calc(100vw - var(--tf-admin-rail-width))",
            continuity,
        )

    def test_admin_index_uses_the_same_full_width_shell(self):
        """The administration index cannot fall back to a second shell."""
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tf-admin-dashboard")
        self.assertContains(response, 'id="admRail"')
        self.assertContains(response, "tf-admin-user-tools")
        self.assertContains(
            response,
            "css/tradeflow_admin_continuity.css",
        )
        self.assertNotContains(response, "tf-system-rail")
