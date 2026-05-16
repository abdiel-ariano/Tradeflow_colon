"""
=============================================================================
ACCIÓN: REEMPLAZAR
DESTINO: core/utils/email_sender.py
=============================================================================
TradeFlow Colón — Notificaciones por correo al comprador (HTML + texto plano).

Dependencias: Django ``send_mail``, ``settings.DEFAULT_FROM_EMAIL``,
``settings.PUBLIC_BASE_URL`` (URL absoluta para el botón "Ver mi orden").
En desarrollo suele usarse ``EMAIL_BACKEND`` consola.
=============================================================================
"""
from __future__ import annotations

import html as html_std
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from core.models import Order

log = logging.getLogger(__name__)


def _public_base_url() -> str:
    """
    Base pública del sitio para construir enlaces en correos (sin barra final).

    Returns:
        str: Valor de ``settings.PUBLIC_BASE_URL`` o ``http://127.0.0.1:8000``.
    """
    base = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    return (base or "http://127.0.0.1:8000").rstrip("/")


def _order_detail_absolute_url(orden: Order) -> str:
    """
    URL absoluta a la vista ``detalle_mi_orden`` para el comprador.

    Args:
        orden: Orden con ``pk`` persistido.

    Returns:
        str: URL completa.
    """
    path = reverse("detalle_mi_orden", kwargs={"pk": orden.pk})
    return _public_base_url() + path


def _h(s: str) -> str:
    """Escapa texto para inserción segura en HTML."""
    return html_std.escape(str(s), quote=True)


def _render_email_shell(title_inner: str, inner_html: str) -> str:
    """
    Envuelve fragmento HTML en un layout responsive simple con marca TradeFlow.

    Args:
        title_inner: Texto breve del bloque principal (ya escapado o seguro).
        inner_html: Cuerpo HTML interior (filas, párrafos, etc.).

    Returns:
        str: Documento HTML completo del correo.
    """
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TradeFlow Colón</title>
</head>
<body style="margin:0;padding:0;background-color:#F2F3F5;font-family:Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#F2F3F5;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background-color:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #D1D5DB;">
          <tr>
            <td style="background-color:#0F2A44;padding:20px 24px;">
              <p style="margin:0;font-size:18px;font-weight:700;color:#FFFFFF;">TradeFlow Colón</p>
              <p style="margin:8px 0 0;font-size:12px;color:rgba(255,255,255,0.75);">Zona Libre de Colón, Panamá</p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px;color:#374151;font-size:15px;line-height:1.5;">
              {title_inner}
              {inner_html}
            </td>
          </tr>
          <tr>
            <td style="padding:16px 24px 24px;border-top:1px solid #E5E7EB;font-size:12px;color:#6B7A88;">
              <p style="margin:0;">¿Necesitas ayuda? Escríbenos a soporte@tradeflow.pa</p>
              <p style="margin:8px 0 0;">Este mensaje fue generado automáticamente; no respondas directamente a este remitente.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _confirmacion_html(orden: Order, items: list, ver_orden_url: str) -> str:
    """
    HTML del correo de confirmación de orden con tabla de productos y totales.

    Args:
        orden: Orden con totales actualizados.
        items: Lista de ``OrderItem`` con ``product`` cargado.
        ver_orden_url: URL absoluta al detalle para el comprador.

    Returns:
        str: HTML completo.
    """
    buyer = orden.buyer
    nombre = _h(buyer.get_full_name() or buyer.username)
    num = _h(orden.order_number)
    rows = []
    for it in items:
        rows.append(
            "<tr>"
            f'<td style="padding:10px 8px;border-bottom:1px solid #E5E7EB;">{_h(it.product.name)}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #E5E7EB;text-align:right;">{_h(it.qty)}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #E5E7EB;text-align:right;">USD {_h(it.unit_price_snapshot)}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid #E5E7EB;text-align:right;font-weight:600;">USD {_h(it.line_total)}</td>'
            "</tr>"
        )
    table_html = (
        '<table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:14px;margin:16px 0;">'
        "<thead><tr>"
        '<th align="left" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">Producto</th>'
        '<th align="right" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">Cant.</th>'
        '<th align="right" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">P. unit.</th>'
        '<th align="right" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">Subtotal</th>'
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    totals = (
        f'<p style="margin:12px 0 4px;text-align:right;color:#374151;">Subtotal: <strong>USD {_h(orden.subtotal)}</strong></p>'
        f'<p style="margin:0 0 4px;text-align:right;color:#374151;">Envío: <strong>USD {_h(orden.shipping_cost)}</strong></p>'
        f'<p style="margin:0;text-align:right;font-size:18px;color:#F26522;"><strong>Total USD {_h(orden.total)}</strong></p>'
    )
    cta = (
        f'<p style="margin:24px 0 16px;text-align:center;">'
        f'<a href="{_h(ver_orden_url)}" style="display:inline-block;padding:12px 24px;background-color:#F26522;'
        f'color:#FFFFFF;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">Ver mi orden</a>'
        f"</p>"
    )
    title = f"<p style=\"margin:0 0 8px;font-size:16px;font-weight:600;color:#0F2A44;\">Hola {nombre}</p>"
    lead = f'<p style="margin:0 0 16px;">Tu orden <strong style="color:#0F2A44;">{num}</strong> fue registrada correctamente.</p>'
    inner = lead + table_html + totals + cta
    return _render_email_shell(title, inner)


def _confirmacion_plain(orden: Order, items: list, ver_orden_url: str) -> str:
    """Versión texto plano del correo de confirmación (multipart/alternative)."""
    buyer = orden.buyer
    lines = [
        f"Hola {buyer.get_full_name() or buyer.username},",
        "",
        f"Tu orden {orden.order_number} fue registrada correctamente.",
        "",
    ]
    for it in items:
        lines.append(f"  - {it.product.name} × {it.qty}  →  USD {it.line_total}")
    lines.extend(
        [
            "",
            f"Subtotal: USD {orden.subtotal}",
            f"Envío: USD {orden.shipping_cost}",
            f"Total: USD {orden.total}",
            "",
            f"Ver mi orden: {ver_orden_url}",
            "",
            "TradeFlow Colón — Zona Libre de Colón, Panamá",
        ]
    )
    return "\n".join(lines)


def enviar_confirmacion_orden(orden: Order) -> None:
    """
    Envía email HTML al buyer cuando crea una orden.

    Incluye: número orden, tabla de productos, subtotal, envío y total en USD.
    Diseño con colores TradeFlow (cabecera #0F2A44, CTA naranja #F26522).

    Args:
        orden: Instancia de ``Order`` persistida con ítems y totales.
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

    ver_url = _order_detail_absolute_url(orden)
    html_body = _confirmacion_html(orden, items, ver_url)
    plain_body = _confirmacion_plain(orden, items, ver_url)
    subject = f"TradeFlow Colón — Confirmación de orden {orden.order_number}"

    try:
        send_mail(
            subject=subject,
            message=plain_body,
            from_email=getattr(
                settings,
                "DEFAULT_FROM_EMAIL",
                "TradeFlow <no-reply@tradeflow.pa>",
            ),
            recipient_list=[to_email],
            html_message=html_body,
            fail_silently=False,
        )
    except Exception as exc:
        log.exception("enviar_confirmacion_orden falló: %s", exc)


def _mensaje_cambio_estado(orden: Order, estado_anterior: str) -> tuple[str, str]:
    """
    Devuelve asunto y HTML interior (sin wrapper) según el nuevo estado de la orden.

    Args:
        orden: Orden tras el cambio de estado.
        estado_anterior: Código ``status`` previo.

    Returns:
        tuple: (asunto, documento HTML completo del correo).
    """
    num = _h(orden.order_number)
    buyer = orden.buyer
    nombre = _h(buyer.get_full_name() or buyer.username)
    estado_nuevo = orden.status

    if estado_anterior == estado_nuevo:
        return ("", "")

    headline = "Actualización de tu orden"
    parrafos = ""

    if estado_nuevo == "paid":
        headline = "Tu pago fue confirmado"
        parrafos = (
            f'<p style="margin:0 0 12px;">Hola {nombre},</p>'
            f'<p style="margin:0 0 12px;">Confirmamos el pago de tu orden <strong style="color:#0F2A44;">{num}</strong>. '
            f"Prepararemos tu pedido para envío.</p>"
        )
    elif estado_nuevo == "shipped":
        headline = "Tu pedido está en camino"
        parrafos = (
            f'<p style="margin:0 0 12px;">Hola {nombre},</p>'
            f'<p style="margin:0 0 12px;">Tu orden <strong style="color:#0F2A44;">{num}</strong> ya fue despachada. '
            f"Pronto recibirás el pedido en la dirección indicada.</p>"
        )
    elif estado_nuevo == "delivered":
        headline = "Tu pedido fue entregado"
        parrafos = (
            f'<p style="margin:0 0 12px;">Hola {nombre},</p>'
            f'<p style="margin:0 0 12px;">Tu orden <strong style="color:#0F2A44;">{num}</strong> figura como entregada. '
            f"Gracias por confiar en TradeFlow Colón.</p>"
        )
    else:
        prev_label = dict(Order.STATUS_CHOICES).get(estado_anterior, estado_anterior)
        new_label = orden.get_status_display()
        parrafos = (
            f'<p style="margin:0 0 12px;">Hola {nombre},</p>'
            f'<p style="margin:0 0 12px;">El estado de tu orden <strong style="color:#0F2A44;">{num}</strong> ha cambiado '
            f"de <strong>{_h(prev_label)}</strong> a <strong>{_h(new_label)}</strong>.</p>"
        )

    ver_url = _order_detail_absolute_url(orden)
    cta = (
        f'<p style="margin:20px 0 0;text-align:center;">'
        f'<a href="{_h(ver_url)}" style="display:inline-block;padding:10px 20px;background-color:#F26522;'
        f'color:#FFFFFF;text-decoration:none;border-radius:8px;font-weight:600;font-size:13px;">Ver mi orden</a></p>'
    )
    inner = (
        f'<p style="margin:0 0 8px;font-size:18px;font-weight:700;color:#0F2A44;">{_h(headline)}</p>'
        + parrafos
        + f'<p style="margin:12px 0 0;color:#374151;">Total de la orden: <strong>USD {_h(orden.total)}</strong></p>'
        + cta
    )
    subject = f"TradeFlow Colón — {headline} ({orden.order_number})"
    return subject, _render_email_shell("", inner)


def _cambio_estado_plain(orden: Order, estado_anterior: str, headline: str) -> str:
    """Texto plano para notificación de cambio de estado."""
    buyer = orden.buyer
    prev_label = dict(Order.STATUS_CHOICES).get(estado_anterior, estado_anterior)
    lines = [
        f"Hola {buyer.get_full_name() or buyer.username},",
        "",
        headline,
        "",
        f"Orden: {orden.order_number}",
        f"Estado anterior: {prev_label}",
        f"Estado actual: {orden.get_status_display()}",
        f"Total: USD {orden.total}",
        "",
        f"Ver pedido: {_order_detail_absolute_url(orden)}",
        "",
        "TradeFlow Colón — Zona Libre de Colón, Panamá",
    ]
    return "\n".join(lines)


def enviar_cambio_estado(orden: Order, estado_anterior: str) -> None:
    """
    Notifica al buyer cuando su orden cambia de estado.

    Mensajes destacados para ``paid``, ``shipped`` y ``delivered``; el resto
    usa un aviso genérico con etiquetas legibles.

    Args:
        orden: Orden después de actualizar ``status``.
        estado_anterior: Valor de ``status`` antes del cambio.
    """
    if estado_anterior == orden.status:
        return

    buyer = orden.buyer
    to_email = (buyer.email or "").strip()
    if not to_email:
        log.info("enviar_cambio_estado: comprador sin email, se omite envío.")
        return

    subject, html_body = _mensaje_cambio_estado(orden, estado_anterior)
    if not subject:
        return

    # Extraer headline del subject para el cuerpo plano
    headline = subject.replace(f"TradeFlow Colón — ", "").split(" (")[0]
    plain_body = _cambio_estado_plain(orden, estado_anterior, headline)

    try:
        send_mail(
            subject=subject,
            message=plain_body,
            from_email=getattr(
                settings,
                "DEFAULT_FROM_EMAIL",
                "TradeFlow <no-reply@tradeflow.pa>",
            ),
            recipient_list=[to_email],
            html_message=html_body,
            fail_silently=False,
        )
    except Exception as exc:
        log.exception("enviar_cambio_estado falló: %s", exc)
