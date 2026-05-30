"""Tests de enforcement de límites SaaS mensuales."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.enterprise_models import SaasPlan
from core.models import (
    Category,
    Company,
    Inventory,
    Order,
    OrderItem,
    Product,
    UserProfile,
)
from core.utils.order_workflow import accept_seller_order
from core.utils.saas_billing import (
    VolumeLimitExceeded,
    assert_within_volume_limit,
    ensure_default_plans,
    get_or_create_subscription,
)
from core.utils.saas_billing import compute_monthly_volume


@override_settings(
    AXES_ENABLED=False,
    REQUIRE_EMAIL_VERIFICATION=False,
    REQUIRE_APPROVED_APPLICATION=False,
    CHECKOUT_AUTO_APPROVE=False,
)
class TestSaasVolumeLimits(TestCase):
    def setUp(self):
        ensure_default_plans()
        self.seller = User.objects.create_user('seller_lim', 'seller_lim@test.pa', 'pass')
        UserProfile.objects.create(user=self.seller, role='seller', email_verificado=True)
        self.company = Company.objects.create(
            name='Limit Co',
            ruc='LIM1',
            owner=self.seller,
            is_verified=True,
        )
        self.buyer = User.objects.create_user('buyer_lim', 'buyer_lim@test.pa', 'pass')
        UserProfile.objects.create(user=self.buyer, role='buyer', email_verificado=True)
        self.cat = Category.objects.create(name='Cat')
        self.product = Product.objects.create(
            company=self.company,
            category=self.cat,
            name='Item',
            sku='LIM-SKU',
            unit_price=Decimal('10000.00'),
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=100, reserved_qty=0)

    def _set_plan(self, slug: str):
        sub = get_or_create_subscription(self.company)
        sub.plan = SaasPlan.objects.get(slug=slug)
        sub.save(update_fields=['plan'])

    def _paid_order(self, amount: Decimal, number: str) -> Order:
        order = Order.objects.create(
            buyer=self.buyer,
            order_number=number,
            status='paid',
            seller_confirmation_status='accepted',
            confirming_company=self.company,
            subtotal=amount,
            total=amount,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            qty=1,
            unit_price_snapshot=amount,
        )
        return order

    def _awaiting_order(self, amount: Decimal, number: str) -> Order:
        order = Order.objects.create(
            buyer=self.buyer,
            order_number=number,
            status='awaiting_seller',
            seller_confirmation_status='pending',
            confirming_company=self.company,
            subtotal=amount,
            total=amount,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            qty=1,
            unit_price_snapshot=amount,
        )
        return order

    def test_digitalizate_blocks_confirm_over_limit(self):
        self._set_plan('digitalizate')
        self._paid_order(Decimal('15000.00'), 'TF-LIM-1')
        vol, _ = compute_monthly_volume(self.company)
        self.assertEqual(vol, Decimal('15000.00'))

        pending = self._awaiting_order(Decimal('100.00'), 'TF-LIM-2')
        with self.assertRaises(VolumeLimitExceeded):
            accept_seller_order(pending)

    def test_expansion_allows_under_50k(self):
        self._set_plan('expansion')
        self._paid_order(Decimal('40000.00'), 'TF-EXP-1')
        pending = self._awaiting_order(Decimal('5000.00'), 'TF-EXP-2')
        accept_seller_order(pending)
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'paid')

    def test_corporativo_pro_unlimited(self):
        self._set_plan('corporativo_pro')
        self._paid_order(Decimal('100000.00'), 'TF-PRO-1')
        pending = self._awaiting_order(Decimal('50000.00'), 'TF-PRO-2')
        accept_seller_order(pending)
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'paid')

    def test_assert_within_volume_at_exact_limit(self):
        self._set_plan('digitalizate')
        self._paid_order(Decimal('15000.00'), 'TF-EX-1')
        assert_within_volume_limit(self.company, Decimal('0'))
        with self.assertRaises(VolumeLimitExceeded):
            assert_within_volume_limit(self.company, Decimal('0.01'))
