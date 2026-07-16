"""Buyer and seller transactional emails for CFZ marketplace events.

Order confirmations, status changes, access decisions, cart reminders,
and seller trial notices — HTML plus plain text with brand shell.
"""
from __future__ import annotations

import html as html_std
import logging
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from core.utils.email_delivery import deliver_mail as send_mail
from core.email_service import enviar_email_transaccional
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

from core.models import Order, UserProfile
from core.utils.contact import email_template_context, tradeflow_contact_email

log = logging.getLogger(__name__)


def _public_base_url() -> str:
    """Return PUBLIC_BASE_URL without a trailing slash for email links."""
    base = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    return (base or "http://127.0.0.1:8000").rstrip("/")


def _order_detail_absolute_url(orden: Order) -> str:
    """Return absolute buyer order-detail URL for an order."""
    path = reverse("detalle_mi_orden", kwargs={"pk": orden.pk})
    return _public_base_url() + path


def _h(s: str) -> str:
    """Escape text for safe HTML email insertion."""
    return html_std.escape(str(s), quote=True)


def _render_email_shell(title_inner: str, inner_html: str) -> str:
    """Wrap inner HTML in the TradeFlow responsive email chrome."""
    return f"""<!DOCTYPE html>
<html lang="en">
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
              <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.8);letter-spacing:0.04em;">Colón Free Zone · Panama</p>
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
              <p style="margin:0;">Need help? Write to us at {tradeflow_contact_email()}</p>
              <p style="margin:8px 0 0;">This message was generated automatically; do not reply directly to this sender.</p>
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
    """Build HTML order-confirmation body with line items and totals."""
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
        '<th align="left" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">Product</th>'
        '<th align="right" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">Qty.</th>'
        '<th align="right" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">Unit price</th>'
        '<th align="right" style="padding:8px;border-bottom:2px solid #0F2A44;color:#0F2A44;">Subtotal</th>'
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    totals = (
        f'<p style="margin:12px 0 4px;text-align:right;color:#374151;">Subtotal: <strong>USD {_h(orden.subtotal)}</strong></p>'
        f'<p style="margin:0 0 4px;text-align:right;color:#374151;">Shipping: <strong>USD {_h(orden.shipping_cost)}</strong></p>'
        f'<p style="margin:0;text-align:right;font-size:18px;color:#F26522;"><strong>Total USD {_h(orden.total)}</strong></p>'
    )
    cta = (
        f'<p style="margin:24px 0 16px;text-align:center;">'
        f'<a href="{_h(ver_orden_url)}" style="display:inline-block;padding:12px 24px;background-color:#F26522;'
        f'color:#FFFFFF;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">View my order</a>'
        f"</p>"
    )
    title = f"<p style=\"margin:0 0 8px;font-size:16px;font-weight:600;color:#0F2A44;\">Hello {nombre}</p>"
    lead = f'<p style="margin:0 0 16px;">Your order <strong style="color:#0F2A44;">{num}</strong> was successfully registered.</p>'
    inner = lead + table_html + totals + cta
    return _render_email_shell(title, inner)


def _confirmacion_plain(orden: Order, items: list, ver_orden_url: str) -> str:
    """Build plain-text order-confirmation body (multipart alternative)."""
    buyer = orden.buyer
    lines = [
        f"Hello {buyer.get_full_name() or buyer.username},",
        "",
        f"Your order {orden.order_number} was successfully registered.",
        "",
    ]
    for it in items:
        lines.append(f"  - {it.product.name} × {it.qty}  →  USD {it.line_total}")
    lines.extend(
        [
            "",
            f"Subtotal: USD {orden.subtotal}",
            f"Shipping: USD {orden.shipping_cost}",
            f"Total: USD {orden.total}",
            "",
            f"View my order: {ver_orden_url}",
            "",
            "TradeFlow Colón — Colón Free Zone, Panama",
        ]
    )
    return "\n".join(lines)


def enviar_confirmacion_orden(orden: Order) -> None:
    """Email the buyer an HTML order confirmation with USD line totals."""
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
    subject = f"TradeFlow Colón — Order confirmation {orden.order_number}"

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
            fail_silently=True,
        )
    except Exception as exc:
        log.exception("enviar_confirmacion_orden falló: %s", exc)


def _mensaje_cambio_estado(orden: Order, estado_anterior: str) -> tuple[str, str]:
    """Return subject and full HTML for an order status-change notice."""
    num = _h(orden.order_number)
    buyer = orden.buyer
    nombre = _h(buyer.get_full_name() or buyer.username)
    estado_nuevo = orden.status

    if estado_anterior == estado_nuevo:
        return ("", "")

    headline = "Order update"
    parrafos = ""

    if estado_nuevo == "awaiting_seller":
        headline = "Awaiting company confirmation"
        plazo = ""
        if orden.seller_confirm_by:
            plazo = orden.seller_confirm_by.strftime("%d/%m/%Y %H:%M")
        parrafos = (
            f'<p style="margin:0 0 12px;">Hello {nombre},</p>'
            f'<p style="margin:0 0 12px;">We received your order <strong style="color:#0F2A44;">{num}</strong>. '
            f"The selling company must confirm it before payment is collected."
            f'{f" Deadline: <strong>{_h(plazo)}</strong>." if plazo else ""}</p>'
        )
    elif estado_nuevo == "paid":
        headline = "Your payment was confirmed"
        parrafos = (
            f'<p style="margin:0 0 12px;">Hello {nombre},</p>'
            f'<p style="margin:0 0 12px;">We confirmed payment for your order <strong style="color:#0F2A44;">{num}</strong>. '
            f"We will prepare your order for shipping.</p>"
        )
    elif estado_nuevo == "shipped":
        headline = "Your order is on its way"
        parrafos = (
            f'<p style="margin:0 0 12px;">Hello {nombre},</p>'
            f'<p style="margin:0 0 12px;">Your order <strong style="color:#0F2A44;">{num}</strong> has been shipped. '
            f"You will receive it soon at the address provided.</p>"
        )
    elif estado_nuevo == "delivered":
        headline = "Your order was delivered"
        parrafos = (
            f'<p style="margin:0 0 12px;">Hello {nombre},</p>'
            f'<p style="margin:0 0 12px;">Your order <strong style="color:#0F2A44;">{num}</strong> is marked as delivered. '
            f"Thank you for trusting TradeFlow Colón.</p>"
        )
    else:
        prev_label = dict(Order.STATUS_CHOICES).get(estado_anterior, estado_anterior)
        new_label = orden.get_status_display()
        parrafos = (
            f'<p style="margin:0 0 12px;">Hello {nombre},</p>'
            f'<p style="margin:0 0 12px;">The status of your order <strong style="color:#0F2A44;">{num}</strong> has changed '
            f"from <strong>{_h(prev_label)}</strong> to <strong>{_h(new_label)}</strong>.</p>"
        )

    ver_url = _order_detail_absolute_url(orden)
    cta = (
        f'<p style="margin:20px 0 0;text-align:center;">'
        f'<a href="{_h(ver_url)}" style="display:inline-block;padding:10px 20px;background-color:#F26522;'
        f'color:#FFFFFF;text-decoration:none;border-radius:8px;font-weight:600;font-size:13px;">View my order</a></p>'
    )
    inner = (
        f'<p style="margin:0 0 8px;font-size:18px;font-weight:700;color:#0F2A44;">{_h(headline)}</p>'
        + parrafos
        + f'<p style="margin:12px 0 0;color:#374151;">Order total: <strong>USD {_h(orden.total)}</strong></p>'
        + cta
    )
    subject = f"TradeFlow Colón — {headline} ({orden.order_number})"
    return subject, _render_email_shell("", inner)


def _cambio_estado_plain(orden: Order, estado_anterior: str, headline: str) -> str:
    """Build plain-text body for an order status-change notice."""
    buyer = orden.buyer
    prev_label = dict(Order.STATUS_CHOICES).get(estado_anterior, estado_anterior)
    lines = [
        f"Hello {buyer.get_full_name() or buyer.username},",
        "",
        headline,
        "",
        f"Order: {orden.order_number}",
        f"Previous status: {prev_label}",
        f"Current status: {orden.get_status_display()}",
        f"Total: USD {orden.total}",
        "",
        f"View order: {_order_detail_absolute_url(orden)}",
        "",
        "TradeFlow Colón — Colón Free Zone, Panama",
    ]
    return "\n".join(lines)


def enviar_verificacion_email(user: User, request) -> dict:
    """Send email OTP via Resend (console fallback in DEBUG without API key)."""
    from core.email_service import enviar_codigo_verificacion
    from core.models import EmailVerification

    verification = EmailVerification.generate_for(user)
    verify_url = request.build_absolute_uri(reverse('verificar_codigo'))
    result = enviar_codigo_verificacion(user.email, verification.code)
    if not result.ok:
        raise RuntimeError(result.detail or 'email_send_failed')
    return {
        'code': verification.code,
        'link': verify_url,
        'channel': result.channel,
        'recipient': user.email,
    }


def enviar_bienvenida(user: User) -> None:
    """Send welcome email after successful email verification."""
    base = _public_base_url()
    es_seller = False
    try:
        es_seller = user.profile.role == 'seller'
    except UserProfile.DoesNotExist:
        pass
    html_message = render_to_string(
        'core/emails/bienvenida.html',
        email_template_context({
            'user': user,
            'es_seller': es_seller,
            'site_url': base,
            'url_tienda': base + reverse('catalogo_publico'),
            'url_panel': base + reverse('portal_seller'),
        }),
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
    """Notify the buyer when order status changes (paid/shipped/delivered)."""
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
            fail_silently=True,
        )
    except Exception as exc:
        log.exception("enviar_cambio_estado falló: %s", exc)


def enviar_orden_pendiente_vendedor(orden: Order) -> None:
    """Email the seller that a CFZ order awaits confirmation."""
    company = orden.confirming_company
    if not company or not company.owner or not company.owner.email:
        log.info('enviar_orden_pendiente_vendedor: sin email de vendedor')
        return
    base = _public_base_url()
    path = reverse('seller_detalle_venta', kwargs={'pk': orden.pk})
    url = base + path
    plazo = orden.seller_confirm_by.strftime('%d/%m/%Y %H:%M') if orden.seller_confirm_by else '—'
    subject = f'TradeFlow — New order {orden.order_number} pending confirmation'
    body = (
        f'Hello,\n\n'
        f'New order {orden.order_number} from '
        f'{orden.buyer.get_full_name() or orden.buyer.username}.\n'
        f'Confirm before: {plazo}\n\n'
        f'View and confirm: {url}\n'
    )
    inner = (
        f'<p>New order <strong>{_h(orden.order_number)}</strong> pending confirmation.</p>'
        f'<p>Deadline: <strong>{_h(plazo)}</strong></p>'
        f'<p><a href="{_h(url)}">Open in My Store</a></p>'
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[company.owner.email],
            html_message=_render_email_shell('New order', inner),
            fail_silently=True,
        )
    except Exception as exc:
        log.exception('enviar_orden_pendiente_vendedor: %s', exc)


def enviar_solicitud_recibida(app) -> None:
    """Confirm to the applicant that their access request was received."""
    from core.models import UserApplication

    if not isinstance(app, UserApplication):
        return
    subject = 'TradeFlow — Access request received'
    text = (
        f'Hello {app.full_name},\n\n'
        'We received your request. We will notify you by email when it has been reviewed.\n'
    )
    inner = (
        f'<h1 style="margin:0 0 12px;font-size:20px;color:#0F2A44;">Request received</h1>'
        f'<p style="margin:0 0 8px;color:#374151;">Hello {_h(app.full_name)},</p>'
        f'<p style="margin:0;color:#374151;">We received your access request. '
        f'We will notify you by email as soon as it has been reviewed.</p>'
    )
    try:
        enviar_email_transaccional(
            app.email, subject, _render_email_shell(subject, inner), text,
            tipo='access_received',
        )
    except Exception as exc:
        log.exception('enviar_solicitud_recibida: %s', exc)


def enviar_solicitud_a_revisores(app) -> None:
    """Email admins approve/reject magic links for a new application."""
    from core.models import UserApplication

    reviewers = list(getattr(settings, 'APPLICATION_REVIEW_EMAILS', []) or [])
    if not reviewers and settings.DEFAULT_FROM_EMAIL:
        reviewers = [settings.DEFAULT_FROM_EMAIL]
    if not reviewers:
        log.warning('APPLICATION_REVIEW_EMAILS vacío — no se notifica revisores')
        return
    base = _public_base_url()
    approve = base + reverse('revisar_solicitud', kwargs={'token': app.review_token, 'accion': 'aprobar'})
    reject = base + reverse('revisar_solicitud', kwargs={'token': app.review_token, 'accion': 'rechazar'})
    subject = f'TradeFlow — New application: {app.full_name}'
    body = (
        f'Application from {app.full_name} ({app.email})\n'
        f'Role: {app.get_role_display()}\n'
        f'Company: {app.company_name}\n\n'
        f'Approve: {approve}\n'
        f'Reject: {reject}\n'
    )
    inner = (
        f'<h1 style="margin:0 0 12px;font-size:20px;color:#0F2A44;">New access request</h1>'
        f'<p style="margin:0 0 4px;color:#374151;"><strong>{_h(app.full_name)}</strong> ({_h(app.email)})</p>'
        f'<p style="margin:0 0 4px;color:#374151;">Role: {_h(app.get_role_display())}</p>'
        f'<p style="margin:0 0 16px;color:#374151;">Company: {_h(app.company_name)}</p>'
        f'<p style="margin:0 0 8px;"><a href="{_h(approve)}" '
        f'style="display:inline-block;background:#10B981;color:#fff;text-decoration:none;'
        f'padding:10px 18px;border-radius:8px;font-weight:600;margin-right:8px;">Approve</a>'
        f'<a href="{_h(reject)}" '
        f'style="display:inline-block;background:#EF4444;color:#fff;text-decoration:none;'
        f'padding:10px 18px;border-radius:8px;font-weight:600;">Reject</a></p>'
    )
    try:
        for reviewer in reviewers:
            enviar_email_transaccional(
                reviewer, subject, _render_email_shell(subject, inner), body,
                tipo='access_review',
            )
    except Exception as exc:
        log.exception('enviar_solicitud_a_revisores: %s', exc)


def enviar_aplicacion_transportista_recibida(transportista) -> None:
    """Confirm receipt of a carrier (transportista) application."""
    email = (transportista.email_contacto or '').strip()
    if not email:
        return
    html = render_to_string(
        'core/emails/aplicacion_transportista_recibida.html',
        {'transportista': transportista},
    )
    try:
        send_mail(
            subject='TradeFlow — Carrier application received',
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
    """Notify a carrier applicant of approval or rejection."""
    email = (transportista.email_contacto or '').strip()
    if not email:
        return
    html = render_to_string(
        'core/emails/resultado_transportista.html',
        email_template_context({
            'transportista': transportista,
            'aprobado': aprobado,
            'signup_url': _public_base_url() + reverse('signup'),
        }),
    )
    subject = (
        'Welcome to TradeFlow!' if aprobado
        else 'Application update — TradeFlow'
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


def enviar_solicitud_decision(app, aprobada: bool):
    """Notify the applicant of approval or rejection via Resend."""
    from core.email_service import EmailSendResult, enviar_email_transaccional
    base = _public_base_url()
    if aprobada:
        tiene_cuenta = bool(getattr(app, 'user_id', None)) or User.objects.filter(
            email__iexact=(app.email or '').strip()
        ).exists()
        if tiene_cuenta:
            link = base + reverse('login')
            cta_label = 'Sign in'
            extra = 'You can now sign in with this email and start using the platform.'
        else:
            link = base + reverse('signup')
            cta_label = 'Create account'
            extra = 'Create your account with this same email to start using the platform.'
        subject = 'TradeFlow — Application approved'
        msg = (
            f'Hello {app.full_name},\n\n'
            f'Great news! Your access request was approved.\n'
            f'{extra}\n{link}\n'
        )
        inner = (
            f'<h1 style="margin:0 0 12px;font-size:20px;color:#0F2A44;">You\'re approved \U0001F389</h1>'
            f'<p style="margin:0 0 8px;color:#374151;">Hello {_h(app.full_name)},</p>'
            f'<p style="margin:0 0 20px;color:#374151;">Your access request was approved. {_h(extra)}</p>'
            f'<p style="margin:0 0 8px;"><a href="{_h(link)}" '
            f'style="display:inline-block;background:#F26522;color:#fff;text-decoration:none;'
            f'padding:12px 22px;border-radius:8px;font-weight:600;">{cta_label}</a></p>'
        )
    else:
        subject = 'TradeFlow — Application not approved'
        msg = (
            f'Hello {app.full_name},\n\n'
            'We cannot approve your application at this time. '
            f'Contact {tradeflow_contact_email()} if you have questions.\n'
        )
        contact = tradeflow_contact_email()
        inner = (
            f'<h1 style="margin:0 0 12px;font-size:20px;color:#0F2A44;">Application update</h1>'
            f'<p style="margin:0 0 8px;color:#374151;">Hello {_h(app.full_name)},</p>'
            f'<p style="margin:0;color:#374151;">We cannot approve your application at this stage. '
            f'Contact <a href="mailto:{_h(contact)}">{_h(contact)}</a> if you have questions.</p>'
        )
    try:
        return enviar_email_transaccional(
            app.email, subject, _render_email_shell(subject, inner), msg,
            tipo='access_decision',
        )
    except Exception as exc:
        log.exception('enviar_solicitud_decision: %s', exc)
        return EmailSendResult(ok=False, channel='error', detail=str(exc)[:500])


def _cart_preview_items(carrito: dict, limit: int = 3) -> list[dict]:
    """Return first N cart lines for abandonment email preview."""
    preview = []
    for item in list(carrito.values())[:limit]:
        preview.append({
            'nombre': item.get('nombre', 'Producto'),
            'cantidad': item.get('cantidad', 1),
            'subtotal': item.get('subtotal', ''),
        })
    return preview


def enviar_carrito_abandonado(user: User, carrito: dict) -> bool:
    """Send abandoned-cart reminder when checkout has stalled."""
    if not carrito:
        return False
    to_email = (user.email or '').strip()
    if not to_email:
        return False

    base = _public_base_url()
    items_count = sum(int(i.get('cantidad', 0) or 0) for i in carrito.values())
    preview = _cart_preview_items(carrito)
    total = _calcular_total_carrito(carrito)

    html_message = render_to_string(
        'core/emails/carrito_abandonado.html',
        email_template_context({
            'user': user,
            'site_url': base,
            'items_count': items_count,
            'cart_preview': preview,
            'extra_items_count': max(0, len(carrito) - len(preview)),
            'cart_total': f'{total:.2f}',
            'url_carrito': base + reverse('ver_carrito'),
            'url_tienda': base + reverse('catalogo_publico'),
        }),
    )
    plain = strip_tags(html_message)
    try:
        return send_mail(
            subject='¿Se te olvidó algo? — TradeFlow Colón',
            message=plain,
            from_email=getattr(
                settings,
                'DEFAULT_FROM_EMAIL',
                'TradeFlow <no-reply@tradeflow.pa>',
            ),
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=True,
            email_type='cart_reminder',
        )
    except Exception as exc:
        log.exception('enviar_carrito_abandonado falló: %s', exc)
        return False


def _calcular_total_carrito(carrito: dict):
    """Sum cart line subtots as Decimal for email copy."""
    from decimal import Decimal
    total = Decimal('0.00')
    for item in carrito.values():
        total += Decimal(str(item.get('subtotal', '0') or '0'))
    return total


def _promociones_empresas_context(limit: int = 4) -> list[dict]:
    """Build featured CFZ company promo rows for marketing email."""
    from django.db.models import Count, F, Q

    from core.models import Company, Product

    base = _public_base_url()
    promos = []
    companies = (
        Company.objects.filter(is_verified=True, products__is_active=True)
        .annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .distinct()
        .order_by('-is_featured', '-num_productos')[:limit]
    )
    for company in companies:
        product = (
            Product.objects.filter(
                company=company,
                is_active=True,
                promo_price__isnull=False,
                promo_price__lt=F('unit_price'),
            )
            .order_by('-merchandising_priority', 'name')
            .first()
        )
        if not product:
            product = (
                Product.objects.filter(company=company, is_active=True)
                .order_by('-merchandising_priority', '-is_featured', 'name')
                .first()
            )
        price = None
        product_name = None
        if product:
            product_name = product.name
            price_val = product.promo_price if product.promo_price else product.unit_price
            if price_val is not None:
                price = f'{price_val:.2f}'
        promos.append({
            'company_name': company.name,
            'tagline': getattr(company, 'tagline_es', '') or '',
            'is_verified': company.is_verified,
            'product_name': product_name,
            'price': price,
            'url': base + reverse('catalogo_publico') + f'?empresa={company.pk}',
        })
    return promos


def enviar_promociones_empresas(user: User) -> bool:
    """Email verified CFZ company promotions to a buyer."""
    to_email = (user.email or '').strip()
    if not to_email:
        return False

    base = _public_base_url()
    promociones = _promociones_empresas_context()
    html_message = render_to_string(
        'core/emails/promociones_empresas.html',
        email_template_context({
            'user': user,
            'site_url': base,
            'promociones': promociones,
            'url_catalogo': base + reverse('catalogo_publico') + '?orden=promo',
        }),
    )
    plain = strip_tags(html_message)
    try:
        return send_mail(
            subject='Promociones CFZ — TradeFlow Colón',
            message=plain,
            from_email=getattr(
                settings,
                'DEFAULT_FROM_EMAIL',
                'TradeFlow <no-reply@tradeflow.pa>',
            ),
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=True,
            email_type='company_promotions',
        )
    except Exception as exc:
        log.exception('enviar_promociones_empresas falló: %s', exc)
        return False


def enviar_trial_finalizado(company) -> bool:
    """Notify the company owner that the seller trial ended (7-day grace)."""
    owner = company.owner
    if not owner or not owner.email:
        return False
    try:
        sub = company.subscription
        recommended = sub.recommended_plan.name if sub.recommended_plan else sub.plan.name
    except Exception:
        recommended = 'Digitalízate'

    activation_url = _public_base_url() + reverse('seller_trial_activation')
    subject = 'Tu prueba TradeFlow terminó — activa tu plan'
    inner = (
        f'<p>Hola { _h(owner.first_name or owner.username) },</p>'
        f'<p>Tu periodo de prueba gratuita en TradeFlow Colón ha finalizado.</p>'
        f'<p>Según tu volumen de ventas, recomendamos el plan <strong>{_h(recommended)}</strong>.</p>'
        f'<p>Tienes 7 días para activar un plan igual o superior antes de que tu tienda '
        f'deje de aparecer en el marketplace.</p>'
        f'<p><a href="{_h(activation_url)}" style="color:#F26522;font-weight:600;">Activar mi plan</a></p>'
    )
    html_message = _render_email_shell('Trial finalizado', inner)
    plain = strip_tags(html_message)
    try:
        return send_mail(
            subject=subject,
            message=plain,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'TradeFlow <no-reply@tradeflow.pa>'),
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=True,
            email_type='seller_trial_ended',
        )
    except Exception as exc:
        log.exception('enviar_trial_finalizado falló company_id=%s: %s', company.pk, exc)
        return False


def enviar_grace_recordatorio(company, days_left: int) -> bool:
    """Remind a past_due seller how many grace days remain before churn."""
    owner = company.owner
    if not owner or not owner.email:
        return False

    activation_url = _public_base_url() + reverse('seller_trial_activation')
    subject = f'Quedan {days_left} día(s) para activar tu plan TradeFlow'
    inner = (
        f'<p>Hola { _h(owner.first_name or owner.username) },</p>'
        f'<p>Te quedan <strong>{days_left}</strong> día(s) para activar tu plan y mantener '
        f'tu tienda visible en el catálogo y mapa de la ZLC.</p>'
        f'<p><a href="{_h(activation_url)}" style="color:#F26522;font-weight:600;">Activar ahora</a></p>'
    )
    html_message = _render_email_shell('Recordatorio de activación', inner)
    plain = strip_tags(html_message)
    try:
        return send_mail(
            subject=subject,
            message=plain,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'TradeFlow <no-reply@tradeflow.pa>'),
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=True,
            email_type='seller_grace_reminder',
        )
    except Exception as exc:
        log.exception('enviar_grace_recordatorio falló company_id=%s: %s', company.pk, exc)
        return False
