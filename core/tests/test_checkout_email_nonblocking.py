"""Checkout redirects even when SMTP is unreachable on Railway.

Order creation must not fail closed on mail delivery; CFZ buyers still
need Order/Payment records when outbound email cannot connect.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import (
    Category,
    Company,
    Inventory,
    Order,
    Payment,
    Product,
    TransportCarrier,
    UserProfile,
)


class CheckoutEmailNonBlockingTests(TestCase):
    """Assert checkout succeeds despite SMTP network failures."""

    def setUp(self):
        """Create a verified buyer, in-stock SKU, and active carrier."""
        self.buyer = User.objects.create_user(
            username='buyer_checkout_email',
            email='buyer@example.com',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)
        company = Company.objects.create(name='Co', owner=self.buyer)
        cat = Category.objects.create(name='Cat')
        self.product = Product.objects.create(
            company=company,
            category=cat,
            name='Widget',
            sku='W-EMAIL-1',
            unit_price=Decimal('10.00'),
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=50, reserved_qty=0)
        self.carrier = TransportCarrier.objects.create(
            code='zlc-test-email',
            name='Test Carrier',
            base_shipping_cost=Decimal('5.00'),
            is_active=True,
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_checkout_redirects_when_smtp_unreachable(self):
        """Checkout still redirects and persists Order/Payment if SMTP dies."""
        # force_login avoids the django-axes authenticate() request requirement.
        # Production login goes through login_view which has a real request.
        self.client.force_login(self.buyer)
        session = self.client.session
        session['carrito'] = {
            str(self.product.pk): {
                'nombre': self.product.name,
                'precio': str(self.product.unit_price),
                'cantidad': 1,
                'subtotal': str(self.product.unit_price),
                'imagen': '',
            }
        }
        session.save()

        def _smtp_down(*_args, **_kwargs):
            """Simulate SMTP failure for the email nonblocking test."""
            raise OSError(101, 'Network is unreachable')

        with patch(
            'core.utils.email_delivery.get_connection',
            side_effect=_smtp_down,
        ):
            response = self.client.post(
                '/checkout/',
                {
                    'notas': '',
                    'transport_carrier': self.carrier.pk,
                    'buyer_latitude': '9.3667000',
                    'buyer_longitude': '-79.9000000',
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(buyer=self.buyer).exists())
        self.assertTrue(Payment.objects.filter(order__buyer=self.buyer).exists())
