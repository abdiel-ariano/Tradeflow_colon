"""Tests de permisos operacionales sobre órdenes (seller)."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Company, Order, OrderItem, Product, UserProfile
from core.utils.order_permissions import get_seller_order_actions


class TestOrderPermissions(TestCase):
    def setUp(self):
        """Setup."""
        self.company = Company.objects.create(name='Co', ruc='1', is_verified=True)
        self.buyer = User.objects.create_user('b', 'b@t.pa', 'pass')
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)
        self.product = Product.objects.create(
            company=self.company,
            name='P',
            sku='S1',
            unit_price=Decimal('1'),
            currency='USD',
        )
        self.order = Order.objects.create(
            buyer=self.buyer,
            order_number='TF-T-1',
            status='cancelled',
            seller_confirmation_status='rejected',
            confirming_company=self.company,
            subtotal=Decimal('1'),
            total=Decimal('1'),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            qty=1,
            unit_price_snapshot=Decimal('1'),
        )

    def test_cancelled_order_cannot_dispatch(self):
        """Test cancelled order cannot dispatch."""
        actions = get_seller_order_actions(self.order, self.company)
        self.assertFalse(actions['can_dispatch'])
        self.assertTrue(actions['read_only'])

    def test_paid_accepted_can_dispatch(self):
        """Test paid accepted can dispatch."""
        self.order.status = 'paid'
        self.order.seller_confirmation_status = 'accepted'
        self.order.save()
        actions = get_seller_order_actions(self.order, self.company)
        self.assertTrue(actions['can_dispatch'])

    def test_awaiting_seller_cannot_dispatch(self):
        """Test awaiting seller cannot dispatch."""
        self.order.status = 'awaiting_seller'
        self.order.seller_confirmation_status = 'pending'
        self.order.save()
        actions = get_seller_order_actions(self.order, self.company)
        self.assertFalse(actions['can_dispatch'])
        self.assertTrue(actions['can_confirm'])
