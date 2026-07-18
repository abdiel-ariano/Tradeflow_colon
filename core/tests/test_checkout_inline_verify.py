"""Checkout inline email verification and OTP auto-send.

Unverified buyers can open checkout UI with an inline OTP panel, but
POST still gates order placement until the email is confirmed.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import (
    Category,
    Company,
    Inventory,
    Product,
    TransportCarrier,
    UserProfile,
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    REQUIRE_EMAIL_VERIFICATION=True,
    EXPO_DEMO_MODE=False,
    AXES_ENABLED=False,
    CHECKOUT_AUTO_APPROVE=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class CheckoutInlineVerifyTests(TestCase):
    """Assert inline verify UI, auto OTP send, and POST gate."""

    def setUp(self):
        """Log in an unverified buyer with a cart line and carrier."""
        self.company = Company.objects.create(name='Co ZLC', ruc='999', is_verified=True)
        self.carrier = TransportCarrier.objects.create(
            code='inline-carrier',
            name='Inline Carrier',
            base_shipping_cost=Decimal('5.00'),
        )
        cat = Category.objects.create(name='Cat')
        self.product = Product.objects.create(
            company=self.company,
            category=cat,
            name='Widget',
            sku='W-INLINE',
            unit_price=Decimal('12.00'),
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=20, reserved_qty=0)
        self.user = User.objects.create_user(
            username='inline_buyer',
            email='inline@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=self.user,
            role='buyer',
            email_verificado=False,
        )
        self.client = Client()
        self.client.force_login(self.user)
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

    def test_checkout_get_renders_inline_verify_without_redirect(self):
        """GET /checkout/ shows inline verify UI instead of bouncing away."""
        resp = self.client.get('/checkout/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Verify your email')
        self.assertContains(resp, 'id="otp-code"')

    @patch('core.email_service._send_via_resend')
    def test_checkout_get_auto_sends_otp(self, mock_resend):
        """GET /checkout/ auto-sends an OTP when Resend is configured."""
        from core.email_service import EmailSendResult

        mock_resend.return_value = EmailSendResult(ok=True, channel='resend', detail='test-id')
        with override_settings(RESEND_API_KEY='re_test_key'):
            resp = self.client.get('/checkout/')
        self.assertEqual(resp.status_code, 200)
        mock_resend.assert_called_once()

    @patch('core.email_service._send_via_resend')
    def test_verify_page_get_auto_sends_otp(self, mock_resend):
        """GET verify page also auto-sends an OTP via Resend."""
        from core.email_service import EmailSendResult

        mock_resend.return_value = EmailSendResult(ok=True, channel='resend', detail='test-id')
        with override_settings(RESEND_API_KEY='re_test_key'):
            resp = self.client.get(reverse('verificar_codigo'))
        self.assertEqual(resp.status_code, 200)
        mock_resend.assert_called_once()

    def test_checkout_post_still_requires_verification(self):
        """POST checkout redirects to /verificar until email is confirmed."""
        resp = self.client.post(
            '/checkout/',
            {
                'notas': '',
                'transport_carrier': self.carrier.pk,
                'buyer_latitude': '9.3667000',
                'buyer_longitude': '-79.9000000',
                'location_consent': '1',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/verificar', resp['Location'])
