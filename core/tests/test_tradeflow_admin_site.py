"""Integration tests for the branded TradeFlow Django Admin."""
from __future__ import annotations

from pathlib import Path

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from core.enterprise_models import (
    AdCreditAccount,
    ApiAuditLog,
    LogisticsDispatchQueue,
    LogisticsEvent,
)
from core.models import Order, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=["testserver", "localhost", "*"],
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    STAFF_MFA_REQUIRED=False,
)
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

    def test_admin_index_routes_to_ops_dashboard(self):
        """The root admin URL hands operators to the ops dashboard."""
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_ops_dashboard_keeps_tradeflow_branding(self):
        """The operational dashboard remains the branded home for admins."""
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tradeflow_admin_ops.css")
        self.assertContains(response, 'id="admRail"')
        self.assertNotContains(response, "Advanced CRUD")
        self.assertNotContains(response, "Full administration")

    def test_native_admin_uses_consistent_tradeflow_styles(self):
        """Native lists load the stable light TradeFlow presentation layer."""
        response = self.client.get(
            reverse("admin:core_inventory_changelist")
        )
        stylesheet = finders.find("css/tradeflow_admin_native.css")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "css/tradeflow_admin_native.css")
        self.assertContains(response, "family=Montserrat")
        self.assertIsNotNone(stylesheet)

        css = Path(stylesheet).read_text(encoding="utf-8")
        self.assertIn('html[data-theme="dark"]', css)
        self.assertIn("--tf-system-rail-width: 252px", css)
        self.assertIn("#result_list tbody tr:nth-child(even)", css)

    def test_admin_changelist_stays_on_shared_ops_rail(self):
        """Deep Django Admin pages keep the ops rail, not a second IA."""
        response = self.client.get(reverse("admin:core_product_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="admRail"')
        self.assertContains(response, reverse("dashboard"))
        self.assertContains(response, reverse("lista_ordenes"))
        self.assertNotContains(response, "Advanced CRUD")
        self.assertContains(response, "Operations")

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
        request = self.client.get(
            reverse("admin:core_product_changelist")
        ).wsgi_request
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
        response = self.client.get(reverse("admin:core_product_changelist"))
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

        response = self.client.get(reverse("admin:core_product_changelist"))
        self.operator.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.operator.is_staff)

    def test_authenticated_admin_login_opens_ops_dashboard(self):
        """An administrator enters the ops dashboard after login."""
        response = self.client.get(reverse("login"))

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
