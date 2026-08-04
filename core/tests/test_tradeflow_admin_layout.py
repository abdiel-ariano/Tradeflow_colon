"""Regression coverage for the unified TradeFlow Unfold shell."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


class TradeFlowAdminLayoutTests(TestCase):
    """Ensure native and analytical admin pages share one visual shell."""

    def setUp(self):
        """Create a staff operator authorized to open admin pages."""
        self.operator = User.objects.create_user(
            username='layout.operator',
            password='StrongLayoutPassword123!',
            first_name='Patricia',
            last_name='Vásquez',
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.operator,
            defaults={'role': 'admin'},
        )
        self.client.force_login(self.operator)

    def test_native_list_uses_unfold_and_tradeflow_tokens(self):
        """A changelist renders Unfold with the final TradeFlow stylesheet."""
        response = self.client.get(
            reverse('admin:core_payment_changelist')
        )
        stylesheet_path = finders.find('css/tradeflow_unfold.css')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertContains(response, 'unfold/css/styles.css')
        self.assertContains(response, 'css/tradeflow_unfold.css')
        self.assertContains(response, 'family=Montserrat')
        self.assertContains(response, 'Patricia Vásquez')
        self.assertNotContains(response, 'id="admRail"')
        self.assertNotContains(response, 'tradeflow_admin_unified.css')
        self.assertIsNotNone(stylesheet_path)

        stylesheet = Path(stylesheet_path).read_text(encoding='utf-8')
        self.assertIn('--tf-admin-navy: #0f2a44', stylesheet)
        self.assertIn('--tf-admin-orange: #f26522', stylesheet)
        self.assertIn('#nav-sidebar', stylesheet)
        self.assertIn('.tf-admin-workspace', stylesheet)

    def test_admin_index_uses_the_same_full_width_shell(self):
        """The admin index cannot fall back to the former custom rail."""
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tf-admin-dashboard')
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertContains(response, 'css/tradeflow_unfold.css')
        self.assertNotContains(response, 'id="admRail"')
        self.assertNotContains(response, 'tf-system-rail')

    def test_sales_dashboard_uses_unfold_without_nested_navigation(self):
        """The analytical dashboard mounts inside the native admin shell."""
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertContains(response, 'tf-admin-workspace')
        self.assertContains(response, 'CFZ sales dashboard')
        self.assertNotContains(response, 'id="admRail"')
        self.assertNotContains(response, 'tradeflow_admin_continuity.css')

