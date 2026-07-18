"""CSRF / method gates for admin order status and application review."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    Category,
    Company,
    Order,
    Product,
    UserApplication,
    UserProfile,
)


@override_settings(
    STAFF_MFA_REQUIRED=False,
    EXPO_DEMO_MODE=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
)
class AdminMutationMethodTests(TestCase):
    """Assert dangerous admin mutations are not GET-able."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='sec_admin',
            email='sec_admin@example.com',
            password='TestPass123!',
            is_staff=True,
            is_superuser=True,
        )
        UserProfile.objects.get_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'email_verificado': True},
        )
        UserProfile.objects.filter(user=self.admin).update(role='admin', email_verificado=True)
        buyer = User.objects.create_user(
            username='sec_buyer',
            email='sec_buyer@example.com',
            password='TestPass123!',
        )
        UserProfile.objects.get_or_create(user=buyer, defaults={'role': 'buyer'})
        company = Company.objects.create(name='Sec Co', owner=buyer)
        cat = Category.objects.create(name='Sec Cat')
        Product.objects.create(
            company=company,
            category=cat,
            name='Sec Widget',
            sku='SEC-1',
            unit_price=Decimal('10.00'),
            is_active=True,
        )
        self.order = Order.objects.create(
            buyer=buyer,
            shipping_cost=Decimal('0'),
            status='pending',
        )
        self.app = UserApplication.objects.create(
            full_name='Applicant',
            email='applicant@example.com',
            company_name='App Co',
            role='seller',
            status='pending',
        )

    def test_cambiar_estado_orden_rejects_get(self):
        """GET must not mutate order status (POST-only)."""
        self.client.force_login(self.admin)
        url = reverse(
            'cambiar_estado_orden',
            kwargs={'pk': self.order.pk, 'estado': 'paid'},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

    def test_cambiar_estado_orden_post_updates(self):
        """POST + CSRF updates the order status."""
        self.client.force_login(self.admin)
        url = reverse(
            'cambiar_estado_orden',
            kwargs={'pk': self.order.pk, 'estado': 'paid'},
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_revisar_solicitud_get_does_not_approve(self):
        """GET shows confirm UI and leaves application pending."""
        self.client.force_login(self.admin)
        url = reverse(
            'revisar_solicitud',
            kwargs={'token': self.app.review_token, 'accion': 'aprobar'},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'csrfmiddlewaretoken')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'pending')

    def test_revisar_solicitud_post_approves(self):
        """POST confirm records the application decision."""
        self.client.force_login(self.admin)
        url = reverse(
            'revisar_solicitud',
            kwargs={'token': self.app.review_token, 'accion': 'aprobar'},
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.app.refresh_from_db()
        self.assertNotEqual(self.app.status, 'pending')
