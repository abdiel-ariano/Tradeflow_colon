"""
=============================================================================
core/utils/email_sender.py — TradeFlow Colón
Envío de notificaciones por correo (desarrollo: consola vía EMAIL_BACKEND).
=============================================================================
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from core.models import Order

log = logging.getLogger(__name__)


def enviar_confirmacion_orden(orden: Order) -> None:
    """
    Envía un correo al comprador cuando se crea una orden (post-checkout).

    Incluye número de orden, listado breve de productos y total en USD.

    Args:
        orden: Instancia de Order ya persistida con ítems y totales calculados.
    """
    try:
        orden.refresh_from_db()
        items = list(orden.items.select_related("product").all())
    except Exception as exc:
        log.warning("enviar_confirmacion_orden: no se pudo cargar la orden: %s", exc)
        return

    buyer = orden.buyer
    to_email = (buyer.email or "").strip()
    if not to_email:
        log.info("enviar_confirmacion_orden: comprador sin email, se omite envío.")
        return

    lines = []
    for it in items:
        lines.append(f"  - {it.product.name} × {it.qty}  →  USD {it.line_total}")
    body = (
        f"Hola {buyer.get_full_name() or buyer.username},\n\n"
        f"Tu orden {orden.order_number} ha sido registrada correctamente.\n\n"
        f"Detalle:\n" + "\n".join(lines) + "\n\n"
        f"Subtotal: USD {orden.subtotal}\n"
        f"Envío: USD {orden.shipping_cost}\n"
        f"Total: USD {orden.total}\n\n"
        f"Estado actual: {orden.get_status_display()}\n\n"
        f"Gracias por comprar en TradeFlow Colón.\n"
    )
    try:
        send_mail(
            subject=f"TradeFlow Colón — Confirmación de orden {orden.order_number}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@tradeflow.pa"),
            recipient_list=[to_email],
            fail_silently=False,
        )
    except Exception as exc:
        log.exception("enviar_confirmacion_orden falló: %s", exc)


def enviar_cambio_estado(orden: Order, estado_anterior: str) -> None:
    """
    Notifica al comprador cuando la orden cambia de estado administrativo.

    Args:
        orden: Orden tras actualizar el campo status.
        estado_anterior: Valor del campo status antes del cambio (código interno).
    """
    if estado_anterior == orden.status:
        return

    buyer = orden.buyer
    to_email = (buyer.email or "").strip()
    if not to_email:
        log.info("enviar_cambio_estado: comprador sin email, se omite envío.")
        return

    prev_label = dict(Order.STATUS_CHOICES).get(estado_anterior, estado_anterior)
    new_label = orden.get_status_display()
    body = (
        f"Hola {buyer.get_full_name() or buyer.username},\n\n"
        f"El estado de tu orden {orden.order_number} ha sido actualizado.\n\n"
        f"Anterior: {prev_label}\n"
        f"Actual: {new_label}\n\n"
        f"Total de la orden: USD {orden.total}\n\n"
        f"TradeFlow Colón — Zona Libre de Colón, Panamá\n"
    )
    try:
        send_mail(
            subject=f"TradeFlow Colón — Actualización de orden {orden.order_number}",
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@tradeflow.pa"),
            recipient_list=[to_email],
            fail_silently=False,
        )
    except Exception as exc:
        log.exception("enviar_cambio_estado falló: %s", exc)
