"""Tests for TradeFlow navigation rendered by Django Unfold."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


class TradeFlowAdminNavigationTests(TestCase):
    """Keep every administrative route on one navigation contract."""

    def setUp(self):
        """Create a staff operator with the platform administrator role."""
        self.operator = User.objects.create_user(
            username='navigation.operator',
            password='StrongNavigationPassword123!',
            first_name='Patricia',
            last_name='Vásquez',
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.operator,
            defaults={'role': 'admin'},
        )
        self.client.force_login(self.operator)

    def test_native_admin_exposes_grouped_operational_navigation(self):
        """Unfold renders the critical modules in collapsible groups."""
        response = self.client.get(
            reverse('admin:core_payment_changelist')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertContains(response, 'Sales dashboard')
        self.assertContains(response, 'Companies and users')
        self.assertContains(response, 'SaaS and platform')
        self.assertContains(response, 'Audit')
        self.assertContains(response, 'css/tradeflow_unfold.css')
        self.assertNotContains(response, 'tradeflow_admin_nav.js')
        self.assertNotContains(response, 'id="admRail"')

    def test_dashboard_and_saas_use_the_native_sidebar(self):
        """Custom analytical routes keep Unfold instead of nesting a rail."""
        routes = ('dashboard', 'admin_saas_dashboard')

        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="nav-sidebar"')
                self.assertContains(response, 'css/tradeflow_unfold.css')
                self.assertNotContains(response, 'id="admRail"')
                self.assertNotContains(
                    response,
                    'tradeflow_admin_unified.css',
                )

    def test_sidebar_configuration_uses_unfold_as_the_single_owner(self):
        """Settings keep Unfold before Django Admin and define all groups."""
        self.assertEqual(settings.INSTALLED_APPS[0], 'unfold')
        sidebar = settings.UNFOLD['SIDEBAR']
        titles = [str(group['title']) for group in sidebar['navigation']]

        self.assertTrue(sidebar['show_search'])
        self.assertFalse(sidebar['show_all_applications'])
        self.assertEqual(
            titles,
            [
                'Summary',
                'Commerce',
                'Companies and users',
                'Logistics',
                'SaaS and platform',
                'Audit',
            ],
        )
