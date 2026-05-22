"""
Flujo de confirmación de órdenes por el vendedor y liberación de inventario.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.models import Order, Payment

log = logging.getLogger(__name__)


def release_order_inventory(orden: Order) -> None:
    """Libera reservas de inventario de los ítems de la orden."""
    for item in orden.items.select_related('product__inventory'):
        inv = getattr(item.product, 'inventory', None)
        if inv:
            inv.release_reservation(item.qty)


def accept_seller_order(orden: Order) -> None:
    """Confirma orden: pasa a pagada y aprueba el pago."""
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
    """Rechaza orden: cancela y libera stock."""
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
    """Marca como expiradas órdenes awaiting_seller fuera de plazo."""
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
    hours = getattr(company, 'order_confirm_hours', None) or 48
    return timezone.now() + timedelta(hours=hours)
