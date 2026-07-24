"""Integration tests for the branded TradeFlow Django Admin."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import (
    AdCreditAccount,
    ApiAuditLog,
    LogisticsDispatchQueue,
    LogisticsEvent,
)
from core.models import Order, Product, UserProfile


class TradeFlowAdminSiteTests(TestCase):
    """Verify access, branding, model coverage, and demo safety."""

    def setUp(self):
        """Create an authenticated staff operator with the TradeFlow role."""
        self.operator = User.objects.create_user(
            username="tf.operator",
            password="StrongTestPassword123!",
            is_staff=True,
        )
        UserProfile.objects.update_or_create(
            user=self.operator,
            defaults={"role": "admin"},
        )
        self.client.force_login(self.operator)

    def test_admin_index_uses_tradeflow_branding(self):
        """The root admin view renders the branded operational dashboard."""
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administración integral")
        self.assertContains(response, "css/tradeflow_admin.css")
        self.assertContains(response, "Centro de control")

    def test_tradeflow_admin_can_view_business_and_user_models(self):
        """An operator can inspect both marketplace and account records."""
        urls = (
            reverse("admin:core_order_changelist"),
            reverse("admin:core_product_changelist"),
            reverse("admin:auth_user_changelist"),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_operational_models_are_registered(self):
        """Audit, advertising, and logistics records appear in the admin."""
        required_models = (
            AdCreditAccount,
            ApiAuditLog,
            LogisticsDispatchQueue,
            LogisticsEvent,
            Order,
            Product,
        )

        for model in required_models:
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    @override_settings(SAAS_READ_ONLY_DEMO_USERNAME="tf.operator")
    def test_demo_operator_cannot_mutate_records(self):
        """The configured demo keeps visibility without write permissions."""
        product_admin = admin.site._registry[Product]
        request = self.client.get(reverse("admin:index")).wsgi_request
        request.user = self.operator

        self.assertTrue(product_admin.has_view_permission(request))
        self.assertFalse(product_admin.has_add_permission(request))
        self.assertFalse(product_admin.has_change_permission(request))
        self.assertFalse(product_admin.has_delete_permission(request))
