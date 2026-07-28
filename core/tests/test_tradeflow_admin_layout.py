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
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.operator,
            defaults={"role": "admin"},
        )
        self.client.force_login(self.operator)

    def test_native_list_uses_shared_header_and_layout_styles(self):
        """A changelist renders the stable header and final layout layer."""
        response = self.client.get(
            reverse("admin:core_payment_changelist")
        )
        stylesheet = finders.find("css/tradeflow_admin_layout.css")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tf-admin-user-tools")
        self.assertContains(response, "Marketplace")
        self.assertContains(response, "Seguridad")
        self.assertContains(response, "css/tradeflow_admin_layout.css")
        self.assertIsNotNone(stylesheet)

        css = Path(stylesheet).read_text(encoding="utf-8")
        self.assertIn("--tf-admin-filter-width: 272px", css)
        self.assertIn("grid-template-columns:", css)
        self.assertIn("width: 100% !important", css)
        self.assertIn("position: fixed !important", css)
        self.assertIn(
            ".changelist-form-container:has(#changelist-filter)",
            css,
        )
        self.assertIn("overflow-x: visible !important", css)

    def test_dashboard_uses_the_same_full_width_shell(self):
        """The administration index does not fall back to Django's width."""
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tf-admin-dashboard")
        self.assertContains(response, "tf-admin-user-tools")
        self.assertContains(response, "css/tradeflow_admin_layout.css")
