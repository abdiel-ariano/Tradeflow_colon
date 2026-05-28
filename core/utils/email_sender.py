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
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from core.utils.email_delivery import deliver_mail as send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

from core.models import Order, UserProfile

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
            <td style="background-color:#0F2A44;padding:24px 24px;text-align:center;">
              <img src="{settings.PUBLIC_BASE_URL.rstrip('/')}/static/img/logo-icon-color.png" alt="TradeFlow Colón" width="120" height="auto" style="display:block;margin:0 auto 12px;max-height:48px;width:auto;height:48px;object-fit:contain;">
              <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.8);letter-spacing:0.04em;">Zona Libre de Colón · Panamá</p>
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

    if estado_nuevo == "awaiting_seller":
        headline = "Esperando confirmación de la empresa"
        plazo = ""
        if orden.seller_confirm_by:
            plazo = orden.seller_confirm_by.strftime("%d/%m/%Y %H:%M")
        parrafos = (
            f'<p style="margin:0 0 12px;">Hola {nombre},</p>'
            f'<p style="margin:0 0 12px;">Recibimos tu orden <strong style="color:#0F2A44;">{num}</strong>. '
            f"La empresa vendedora debe confirmarla antes del cobro."
            f'{f" Plazo: <strong>{_h(plazo)}</strong>." if plazo else ""}</p>'
        )
    elif estado_nuevo == "paid":
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


def enviar_verificacion_email(user: User, request) -> None:
    """
    Envía email de verificación al registrarse.

    Genera código OTP de 6 dígitos y token UUID para enlace. El código expira
    en 24 horas (``codigo_verificacion_expira``).

    Args:
        user: Instancia de User recién creado.
        request: HttpRequest para construir URL absoluta.
    """
    from core.utils.email_verification import assign_email_verification_code

    profile = user.profile
    verification_code = assign_email_verification_code(profile, hours=24)
    token = str(uuid.uuid4()).replace('-', '')
    profile.token_verificacion = token
    profile.save(update_fields=['token_verificacion'])

    link = request.build_absolute_uri(
        reverse('verificar_email', kwargs={'token': token})
    )

    html_message = render_to_string(
        'core/emails/verificacion_email.html',
        {
            'user': user,
            'link': link,
            'verification_code': verification_code,
            'expiracion': '24 horas',
            'public_base_url': getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/'),
        },
    )

    from core.utils.email_config import smtp_configured

    if not smtp_configured():
        log.warning(
            'Verificación SIN Gmail (consola): usuario=%s email=%s código=%s URL=%s',
            user.username,
            user.email,
            verification_code,
            link,
        )

    try:
        send_mail(
            subject='Verifica tu cuenta en TradeFlow Colón',
            message=strip_tags(html_message),
            from_email=getattr(
                settings,
                'DEFAULT_FROM_EMAIL',
                'TradeFlow <no-reply@tradeflow.pa>',
            ),
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as exc:
        log.exception('enviar_verificacion_email falló: %s', exc)
        raise


def enviar_bienvenida(user: User) -> None:
    """
    Email de bienvenida después de verificar el email.

    Incluye enlaces para comenzar según el rol del usuario.
    """
    base = _public_base_url()
    es_seller = False
    try:
        es_seller = user.profile.role == 'seller'
    except UserProfile.DoesNotExist:
        pass
    html_message = render_to_string(
        'core/emails/bienvenida.html',
        {
            'user': user,
            'es_seller': es_seller,
            'url_tienda': base + reverse('tienda'),
            'url_panel': base + reverse('portal_seller'),
        },
    )
    try:
        send_mail(
            subject='¡Bienvenido a TradeFlow Colón!',
            message=strip_tags(html_message),
            from_email=getattr(
                settings,
                'DEFAULT_FROM_EMAIL',
                'TradeFlow <no-reply@tradeflow.pa>',
            ),
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as exc:
        log.exception('enviar_bienvenida falló: %s', exc)


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


def enviar_orden_pendiente_vendedor(orden: Order) -> None:
    """Avisa al vendedor que hay una orden por confirmar."""
    company = orden.confirming_company
    if not company or not company.owner or not company.owner.email:
        log.info('enviar_orden_pendiente_vendedor: sin email de vendedor')
        return
    base = _public_base_url()
    path = reverse('seller_detalle_venta', kwargs={'pk': orden.pk})
    url = base + path
    plazo = orden.seller_confirm_by.strftime('%d/%m/%Y %H:%M') if orden.seller_confirm_by else '—'
    subject = f'TradeFlow — Nueva orden {orden.order_number} por confirmar'
    body = (
        f'Hola,\n\n'
        f'Nueva orden {orden.order_number} de '
        f'{orden.buyer.get_full_name() or orden.buyer.username}.\n'
        f'Confirmar antes de: {plazo}\n\n'
        f'Ver y confirmar: {url}\n'
    )
    inner = (
        f'<p>Nueva orden <strong>{_h(orden.order_number)}</strong> pendiente de confirmación.</p>'
        f'<p>Plazo: <strong>{_h(plazo)}</strong></p>'
        f'<p><a href="{_h(url)}">Abrir en Mi Tienda</a></p>'
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[company.owner.email],
            html_message=_render_email_shell('Nueva orden', inner),
            fail_silently=False,
        )
    except Exception as exc:
        log.exception('enviar_orden_pendiente_vendedor: %s', exc)


def enviar_solicitud_recibida(app) -> None:
    """Confirma al solicitante que recibimos su solicitud."""
    from core.models import UserApplication

    if not isinstance(app, UserApplication):
        return
    try:
        send_mail(
            subject='TradeFlow — Solicitud de acceso recibida',
            message=(
                f'Hola {app.full_name},\n\n'
                'Recibimos tu solicitud. Te avisaremos por correo cuando sea revisada.\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[app.email],
            fail_silently=False,
        )
    except Exception as exc:
        log.exception('enviar_solicitud_recibida: %s', exc)


def enviar_solicitud_a_revisores(app) -> None:
    """Envía a administradores enlaces para aprobar o rechazar."""
    from core.models import UserApplication

    reviewers = list(getattr(settings, 'APPLICATION_REVIEW_EMAILS', []) or [])
    if not reviewers:
        reviewers = [settings.EMAIL_HOST_USER] if settings.EMAIL_HOST_USER else []
    if not reviewers:
        log.warning('APPLICATION_REVIEW_EMAILS vacío — no se notifica revisores')
        return
    base = _public_base_url()
    approve = base + reverse('revisar_solicitud', kwargs={'token': app.review_token, 'accion': 'aprobar'})
    reject = base + reverse('revisar_solicitud', kwargs={'token': app.review_token, 'accion': 'rechazar'})
    subject = f'TradeFlow — Nueva solicitud: {app.full_name}'
    body = (
        f'Solicitud de {app.full_name} ({app.email})\n'
        f'Rol: {app.get_role_display()}\n'
        f'Empresa: {app.company_name}\n\n'
        f'Aprobar: {approve}\n'
        f'Rechazar: {reject}\n'
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=reviewers,
            fail_silently=False,
        )
    except Exception as exc:
        log.exception('enviar_solicitud_a_revisores: %s', exc)


def enviar_aplicacion_transportista_recibida(transportista) -> None:
    """Confirma recepción de solicitud de transportista."""
    email = (transportista.email_contacto or '').strip()
    if not email:
        return
    html = render_to_string(
        'core/emails/aplicacion_transportista_recibida.html',
        {'transportista': transportista},
    )
    try:
        send_mail(
            subject='TradeFlow — Solicitud de transportista recibida',
            message=strip_tags(html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html,
            fail_silently=False,
        )
    except Exception as exc:
        log.exception('enviar_aplicacion_transportista_recibida: %s', exc)
        raise


def enviar_resultado_aplicacion_transportista(transportista, aprobado: bool) -> None:
    """Notifica aprobación o rechazo de transportista."""
    email = (transportista.email_contacto or '').strip()
    if not email:
        return
    html = render_to_string(
        'core/emails/resultado_transportista.html',
        {
            'transportista': transportista,
            'aprobado': aprobado,
            'signup_url': _public_base_url() + reverse('signup'),
        },
    )
    subject = (
        '¡Bienvenido a TradeFlow!' if aprobado
        else 'Actualización de tu solicitud — TradeFlow'
    )
    try:
        send_mail(
            subject=subject,
            message=strip_tags(html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html,
            fail_silently=False,
        )
    except Exception as exc:
        log.exception('enviar_resultado_aplicacion_transportista: %s', exc)
        raise


def enviar_solicitud_decision(app, aprobada: bool) -> None:
    """Notifica al solicitante la decisión."""
    base = _public_base_url()
    if aprobada:
        link = base + reverse('signup')
        msg = (
            f'Hola {app.full_name},\n\n'
            f'Tu solicitud fue aprobada. Crea tu cuenta en: {link}\n'
        )
        html = f'<p>Tu solicitud fue <strong>aprobada</strong>.</p><p><a href="{_h(link)}">Registrarse</a></p>'
        subject = 'TradeFlow — Solicitud aprobada'
    else:
        msg = (
            f'Hola {app.full_name},\n\n'
            'En este momento no podemos aprobar tu solicitud. '
            'Contacta a soporte@tradeflow.pa si tienes preguntas.\n'
        )
        html = '<p>Tu solicitud no fue aprobada en esta etapa.</p>'
        subject = 'TradeFlow — Solicitud no aprobada'
    try:
        send_mail(
            subject=subject,
            message=msg,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[app.email],
            html_message=_render_email_shell(subject, html),
            fail_silently=False,
        )
    except Exception as exc:
        log.exception('enviar_solicitud_decision: %s', exc)
