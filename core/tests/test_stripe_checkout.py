"""Tests for the test-only Stripe Checkout integration."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    Category,
    Company,
    Inventory,
    Order,
    OrderItem,
    Payment,
    Product,
    UserProfile,
)


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    STAFF_MFA_REQUIRED=False,
    AUTHENTICATION_BACKENDS=[
        'django.contrib.auth.backends.ModelBackend',
    ],
    STATICFILES_STORAGE=(
        'django.contrib.staticfiles.storage.StaticFilesStorage'
    ),
    STRIPE_TEST_MODE=True,
    STRIPE_TEST_SECRET_KEY='sk_test_tradeflow_unit_tests',
    STRIPE_TEST_WEBHOOK_SECRET='whsec_tradeflow_unit_tests',
    STRIPE_API_VERSION='2026-07-29.dahlia',
)
class StripeCheckoutTests(TestCase):
    """Exercise permissions, session creation, and idempotent completion."""

    def setUp(self):
        """Create a buyer-owned, accepted, pending order."""
        self.buyer = User.objects.create_user(
            username='stripe_buyer',
            email='stripe.buyer@example.com',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=self.buyer,
            role='buyer',
            business_role_intent='buyer',
            email_verificado=True,
        )
        Company.objects.create(
            name='Stripe Test Buyer',
            legal_name='Stripe Test Buyer, S.A.',
            ruc='8-BUYER-STRIPE',
            dv='10',
            business_email=self.buyer.email,
            business_role='buyer',
            owner=self.buyer,
            verification_status='verified',
            is_verified=True,
        )
        self.company = Company.objects.create(
            name='Stripe Test Supplier',
            ruc='8-TEST-STRIPE',
            verification_status='verified',
            is_verified=True,
        )
        category = Category.objects.create(name='Stripe test products')
        self.product = Product.objects.create(
            company=self.company,
            category=category,
            name='Test wholesale product',
            sku='STRIPE-TEST-1',
            unit_price=Decimal('10.00'),
            currency='USD',
            is_active=True,
        )
        self.inventory = Inventory.objects.create(
            product=self.product,
            stock_qty=10,
            reserved_qty=2,
        )
        self.order = Order.objects.create(
            buyer=self.buyer,
            status='pending',
            confirming_company=self.company,
            seller_confirmation_status='accepted',
            confirmado_por_empresa=True,
            shipping_cost=Decimal('0.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            qty=2,
            unit_price_snapshot=Decimal('10.00'),
        )
        self.order.recalculate_totals()
        self.order.save(
            update_fields=['subtotal', 'total', 'updated_at'],
        )
        self.client.login(
            username='stripe_buyer',
            password='TestPass123!',
        )

    @staticmethod
    def _session(**overrides):
        """Return a complete test Checkout Session-like object."""
        values = {
            'id': 'cs_test_tradeflow_123',
            'url': 'https://checkout.stripe.com/c/pay/cs_test_tradeflow_123',
            'status': 'complete',
            'payment_status': 'paid',
            'livemode': False,
            'amount_total': 2000,
            'currency': 'usd',
            'client_reference_id': '',
            'metadata': {'order_id': ''},
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_cart_displays_stripe_sandbox_after_quote_explanation(self):
        """The cart advertises Stripe without charging preliminary prices."""
        session = self.client.session
        session['carrito'] = {
            str(self.product.pk): {
                'nombre': self.product.name,
                'precio': '10.00',
                'cantidad': 2,
                'subtotal': '20.00',
                'imagen': '',
            },
        }
        session.save()

        response = self.client.get(reverse('ver_carrito'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stripe')
        self.assertContains(response, 'Test mode')
        self.assertContains(response, 'After you accept')

    def test_pending_order_displays_stripe_test_button(self):
        """An accepted pending order exposes the test Checkout action."""
        response = self.client.get(
            reverse('detalle_mi_orden', args=[self.order.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pay with Stripe')
        self.assertContains(response, 'Pay with Stripe — test')

    @patch('core.views.stripe_checkout._stripe_client')
    def test_start_creates_pending_payment_and_redirects(self, client_factory):
        """Checkout uses server-side snapshots and dynamic payment methods."""
        stripe_client = MagicMock()
        stripe_client.v1.checkout.sessions.create.return_value = self._session(
            status='open',
            payment_status='unpaid',
            metadata={'order_id': str(self.order.pk)},
            client_reference_id=str(self.order.pk),
        )
        client_factory.return_value = stripe_client

        response = self.client.post(
            reverse('stripe_checkout_start', args=[self.order.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            'https://checkout.stripe.com/c/pay/cs_test_tradeflow_123',
        )
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.provider, 'stripe')
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.amount, Decimal('20.00'))
        self.assertEqual(payment.txn_ref, 'cs_test_tradeflow_123')

        kwargs = stripe_client.v1.checkout.sessions.create.call_args.kwargs
        params = kwargs['params']
        self.assertNotIn('payment_method_types', params)
        self.assertEqual(params['mode'], 'payment')
        self.assertEqual(params['client_reference_id'], str(self.order.pk))
        self.assertEqual(
            params['line_items'][0]['price_data']['unit_amount'],
            1000,
        )
        self.assertEqual(params['line_items'][0]['quantity'], 2)
        self.assertRegex(
            params['integration_identifier'],
            r'^tradeflow_order_[a-z]{8}$',
        )
        self.assertEqual(
            kwargs['options']['stripe_version'],
            '2026-07-29.dahlia',
        )
        self.assertIn('idempotency_key', kwargs['options'])

    @patch('core.views.stripe_checkout._stripe_client')
    def test_success_verifies_and_records_payment_once(self, client_factory):
        """A verified test session pays the order exactly once."""
        checkout_session = self._session(
            metadata={'order_id': str(self.order.pk)},
            client_reference_id=str(self.order.pk),
        )
        stripe_client = MagicMock()
        stripe_client.v1.checkout.sessions.retrieve.return_value = (
            checkout_session
        )
        client_factory.return_value = stripe_client
        Payment.objects.create(
            order=self.order,
            provider='stripe',
            status='pending',
            amount=self.order.total,
            currency='USD',
            txn_ref=checkout_session.id,
        )
        url = (
            reverse('stripe_checkout_success')
            + f'?session_id={checkout_session.id}'
        )

        first_response = self.client.get(url)
        second_response = self.client.get(url)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.order.refresh_from_db()
        payment = Payment.objects.get(order=self.order)
        self.inventory.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(payment.status, 'approved')
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(self.inventory.stock_qty, 8)
        self.assertEqual(self.inventory.reserved_qty, 0)

    def test_live_key_is_rejected(self):
        """The sandbox feature never accepts a live Stripe credential."""
        with override_settings(STRIPE_TEST_SECRET_KEY='sk_live_forbidden'):
            response = self.client.post(
                reverse('stripe_checkout_start', args=[self.order.pk]),
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

    def test_other_buyer_cannot_pay_order(self):
        """A buyer cannot start Checkout for another buyer's order."""
        other = User.objects.create_user(
            username='other_stripe_buyer',
            email='other@example.com',
            password='TestPass123!',
        )
        UserProfile.objects.create(
            user=other,
            role='buyer',
            business_role_intent='buyer',
            email_verificado=True,
        )
        Company.objects.create(
            name='Other Stripe Test Buyer',
            legal_name='Other Stripe Test Buyer, S.A.',
            ruc='8-OTHER-STRIPE',
            dv='11',
            business_email=other.email,
            business_role='buyer',
            owner=other,
            verification_status='verified',
            is_verified=True,
        )
        self.client.logout()
        self.client.login(
            username='other_stripe_buyer',
            password='TestPass123!',
        )

        response = self.client.post(
            reverse('stripe_checkout_start', args=[self.order.pk]),
        )

        self.assertEqual(response.status_code, 404)

    @patch('core.views.stripe_checkout.stripe.Webhook.construct_event')
    def test_webhook_rejects_invalid_signature(self, construct_event):
        """Unsigned or malformed webhook payloads are rejected."""
        construct_event.side_effect = ValueError('invalid signature')

        response = self.client.post(
            reverse('stripe_webhook'),
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid',
        )

        self.assertEqual(response.status_code, 400)
