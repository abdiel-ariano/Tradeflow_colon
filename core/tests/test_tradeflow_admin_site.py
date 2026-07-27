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

    def test_admin_index_exposes_persistent_operational_navigation(self):
        """Critical modules are visible directly in the left navigation."""
        response = self.client.get(reverse("admin:index"))
        expected_links = (
            reverse("admin:core_order_changelist"),
            reverse("admin:core_payment_changelist"),
            reverse("admin:core_product_changelist"),
            reverse("admin:core_inventory_changelist"),
            reverse("admin:core_company_changelist"),
            reverse("admin:auth_user_changelist"),
            reverse("admin:core_shipment_changelist"),
            reverse("admin:core_saasplan_changelist"),
            reverse("admin:core_apiauditlog_changelist"),
        )

        for url in expected_links:
            with self.subTest(url=url):
                self.assertContains(response, f'href="{url}"')

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

    def test_operator_cannot_modify_django_superuser(self):
        """A platform operator cannot promote or alter a superuser account."""
        protected_user = User.objects.create_superuser(
            username="protected.root",
            password="StrongTestPassword456!",
            email="root@example.com",
        )
        user_admin = admin.site._registry[User]
        request = self.client.get(reverse("admin:index")).wsgi_request
        request.user = self.operator

        self.assertTrue(user_admin.has_view_permission(request, protected_user))
        self.assertFalse(
            user_admin.has_change_permission(request, protected_user)
        )
        self.assertFalse(
            user_admin.has_delete_permission(request, protected_user)
        )

    @override_settings(
        EXPO_DEMO_MODE=False,
        SAAS_DEMO_ADMIN_USERNAME="tf.operator",
    )
    def test_configured_demo_operator_has_full_crud(self):
        """The configured demo remains a complete administrator."""
        product_admin = admin.site._registry[Product]
        response = self.client.get(reverse("admin:index"))
        request = response.wsgi_request
        request.user = self.operator

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "solo lectura")
        self.assertNotContains(response, "Modo Expo")
        self.assertTrue(product_admin.has_view_permission(request))
        self.assertTrue(product_admin.has_add_permission(request))
        self.assertTrue(product_admin.has_change_permission(request))
        self.assertTrue(product_admin.has_delete_permission(request))

    @override_settings(
        EXPO_DEMO_MODE=False,
        SAAS_DEMO_ADMIN_USERNAME="tf.operator",
    )
    def test_demo_admin_recovers_existing_staff_access(self):
        """Existing demo data is repaired without rerunning the seed command."""
        self.operator.is_staff = False
        self.operator.save(update_fields=["is_staff"])
        self.operator.groups.clear()

        response = self.client.get(reverse("admin:index"))
        self.operator.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.operator.is_staff)

    def test_authenticated_admin_login_opens_django_admin(self):
        """An administrator enters the integral Django Admin after login."""
        response = self.client.get(reverse("login"))

        self.assertRedirects(
            response,
            reverse("admin:index"),
            fetch_redirect_response=False,
        )
