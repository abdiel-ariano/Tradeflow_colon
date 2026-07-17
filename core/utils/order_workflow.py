"""Flujo de confirmar/rechazar del vendedor y liberación de reserva de inventario.

Aceptar un pedido B2B ZLC verifica topes de volumen SaaS, marca el pago
aprobado y libera stock reservado al rechazar o expirar.
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
    """Libera el inventario reservado de cada línea del pedido."""
    for item in orden.items.select_related('product__inventory'):
        inv = getattr(item.product, 'inventory', None)
        if inv:
            inv.release_reservation(item.qty)


def accept_seller_order(orden: Order) -> None:
    """Acepta el pedido: aplica topes de volumen, marca pagado y aprueba el pago."""
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
    """Rechaza el pedido: cancela, libera stock y rechaza el pago pendiente."""
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
    """Cancela pedidos awaiting_seller pasados de ``seller_confirm_by``; devuelve el conteo."""
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
    """Devuelve el datetime límite de confirmación del vendedor."""
    hours = getattr(company, 'order_confirm_hours', None) or 48
    return timezone.now() + timedelta(hours=hours)
