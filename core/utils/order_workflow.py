"""Seller confirm/reject flow and inventory reservation release.

Accepting a CFZ B2B order checks SaaS volume caps, marks payment
approved, and rejects free reserved stock on decline or expiry.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import Order, Payment

log = logging.getLogger(__name__)


def release_order_inventory(orden: Order) -> None:
    """Release reserved inventory for each line on the order."""
    for item in orden.items.select_related('product__inventory'):
        inv = getattr(item.product, 'inventory', None)
        if inv:
            inv.release_reservation(item.qty)


def accept_seller_order(orden: Order) -> None:
    """Accept order: enforce volume caps, mark paid, approve payment."""
    from collections import defaultdict

    from core.utils.saas_billing import VolumeLimitExceeded, assert_within_volume_limit

    by_company: dict = defaultdict(lambda: Decimal('0.00'))
    for item in orden.items.select_related('product__company'):
        by_company[item.product.company] += item.line_total

    for company, amount in by_company.items():
        assert_within_volume_limit(company, additional_usd=amount)

    with transaction.atomic():
        orden.seller_confirmation_status = 'accepted'
        orden.confirmado_por_empresa = True
        orden.status = 'paid'
        orden.save(update_fields=[
            'seller_confirmation_status', 'confirmado_por_empresa', 'status', 'updated_at',
        ])
        payment = getattr(orden, 'payment', None)
        if payment:
            payment.status = 'approved'
            payment.paid_at = timezone.now()
            payment.save(update_fields=['status', 'paid_at'])
        else:
            Payment.objects.create(
                order=orden,
                provider='mock',
                status='approved',
                amount=orden.total,
                currency='USD',
                paid_at=timezone.now(),
                txn_ref=f'TF-CONF-{orden.order_number}',
            )


def reject_seller_order(orden: Order) -> None:
    """Reject order: cancel, free stock, reject pending payment."""
    with transaction.atomic():
        orden.seller_confirmation_status = 'rejected'
        orden.confirmado_por_empresa = False
        orden.status = 'cancelled'
        orden.save(update_fields=[
            'seller_confirmation_status', 'confirmado_por_empresa', 'status', 'updated_at',
        ])
        release_order_inventory(orden)
        payment = getattr(orden, 'payment', None)
        if payment and payment.status == 'pending':
            payment.status = 'rejected'
            payment.save(update_fields=['status'])


def expire_pending_orders() -> int:
    """Cancel awaiting_seller orders past ``seller_confirm_by``; return count."""
    now = timezone.now()
    qs = Order.objects.filter(
        status='awaiting_seller',
        seller_confirmation_status='pending',
        seller_confirm_by__lt=now,
    )
    n = 0
    for orden in qs:
        with transaction.atomic():
            orden.seller_confirmation_status = 'expired'
            orden.status = 'cancelled'
            orden.save(update_fields=['seller_confirmation_status', 'status', 'updated_at'])
            release_order_inventory(orden)
        n += 1
    return n


def seller_confirm_deadline(company):
    """Return the seller confirmation deadline datetime."""
    hours = getattr(company, 'order_confirm_hours', None) or 48
    return timezone.now() + timedelta(hours=hours)
