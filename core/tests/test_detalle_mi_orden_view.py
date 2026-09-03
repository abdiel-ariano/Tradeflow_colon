"""Buyer order detail page (detalle_mi_orden) regressions.

Buyers must open their own paid CFZ orders with line items visible so
post-checkout tracking stays trustworthy.
"""
from decimal import Decimal

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
    REQUIRE_EMAIL_VERIFICATION=False,
    AXES_ENABLED=False,
)
class DetalleMiOrdenViewTests(TestCase):
    """Assert order detail renders for the owning buyer."""

    def setUp(self):
        """Create a paid order with one line and approved payment."""
        self.company = Company.objects.create(name='Co', ruc='1', is_verified=True)
        cat = Category.objects.create(name='Cat')
        self.product = Product.objects.create(
            company=self.company,
            category=cat,
            name='Widget',
            sku='W-913',
            unit_price=Decimal('10.00'),
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=10, reserved_qty=0)
        self.buyer = User.objects.create_user(
            username='buyer_913',
            email='buyer913@test.pa',
            password='TestPass123!',
        )
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)
        self.orden = Order.objects.create(
            buyer=self.buyer,
            order_type='b2b',
            shipping_cost=Decimal('5.00'),
            status='paid',
        )
        OrderItem.objects.create(
            order=self.orden,
            product=self.product,
            qty=1,
            unit_price_snapshot=Decimal('10.00'),
        )
        self.orden.recalculate_totals()
        Payment.objects.create(
            order=self.orden,
            provider='mock',
            status='approved',
            amount=self.orden.total,
            currency='USD',
            txn_ref='cs_test_reference_that_must_wrap_inside_the_payment_card',
        )
        self.client.force_login(self.buyer)

    def test_detalle_mi_orden_renders_200(self):
        """Owning buyer gets 200 with order number and product name."""
        url = reverse('detalle_mi_orden', kwargs={'pk': self.orden.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.orden.order_number)
        self.assertContains(resp, 'Widget')
        self.assertContains(resp, 'info-fila--reference')
        self.assertContains(
            resp,
            'cs_test_reference_that_must_wrap_inside_the_payment_card',
        )
