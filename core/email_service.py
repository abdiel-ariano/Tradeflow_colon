"""Transactional email delivery via Resend for TradeFlow Colón.

OTP verification and other lifecycle mail fall back to Django's console
backend only when RESEND_API_KEY is missing and DEBUG is True.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import resend as resend_sdk
from django.conf import settings

log = logging.getLogger('tradeflow.email')


@dataclass
class EmailSendResult:
    """Outcome of a single outbound email attempt."""

    ok: bool
    channel: str
    detail: str = ''


def _verification_html(code: str) -> str:
    """Build branded HTML body for an email verification OTP."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:24px;background:#0F2A44;font-family:Montserrat,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;">
    <tr>
      <td style="background:#1B3B63;border-radius:16px;padding:32px;text-align:center;border:2px solid #2E5B8A;">
        <p style="color:#F2F3F5;font-size:14px;margin:0 0 8px;">TradeFlow Colón</p>
        <h1 style="color:#ffffff;font-size:22px;margin:0 0 24px;">Tu código de verificación</h1>
        <p style="color:#F26522;font-size:48px;font-weight:700;letter-spacing:10px;margin:0 0 16px;">{code}</p>
        <p style="color:#F2F3F5;font-size:13px;margin:0;">Válido por 10 minutos. No compartas este código.</p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_via_resend(email: str, subject: str, html: str, text: str) -> EmailSendResult:
    """Send one message through the Resend HTTP API."""
    api_key = (getattr(settings, 'RESEND_API_KEY', '') or '').strip()
    if not api_key:
        log.warning('RESEND_API_KEY no configurada; correo no enviado a %s', email)
        return EmailSendResult(ok=False, channel='resend', detail='resend_not_configured')

    try:
        resend_sdk.api_key = api_key
        params = {
            'from': (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip(),
            'to': [email],
            'subject': subject,
            'html': html,
            'text': text or '',
        }
        response = resend_sdk.Emails.send(params)
        message_id = response.get('id') if isinstance(response, dict) else getattr(response, 'id', None)
        log.info('email_sent via=resend id=%s to=%s', message_id, email)
        return EmailSendResult(ok=True, channel='resend', detail=str(message_id or ''))
    except Exception as exc:
        log.error('email_delivery_failed via=resend to=%s error=%s', email, exc)
        return EmailSendResult(ok=False, channel='resend', detail=str(exc)[:500])


def _send_via_console(email: str, subject: str, html: str, text: str) -> EmailSendResult:
    """Fall back to Django send_mail (console backend in local DEBUG)."""
    from django.core.mail import send_mail

    try:
        send_mail(
            subject=subject,
            message=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html,
            fail_silently=False,
        )
        backend = getattr(settings, 'EMAIL_BACKEND', 'django')
        return EmailSendResult(ok=True, channel=f'django:{backend.split(".")[-1]}')
    except Exception as exc:
        log.exception('Console email backend failed: %s', exc)
        return EmailSendResult(ok=False, channel='django', detail=str(exc)[:500])


def enviar_email_transaccional(
    email: str,
    subject: str,
    html: str,
    text: str,
    tipo: str = 'transactional',
) -> EmailSendResult:
    """Send transactional mail via Resend; console only in DEBUG if unset."""
    if not (email or '').strip():
        return EmailSendResult(ok=False, channel='none', detail='empty_recipient')

    result = _send_via_resend(email, subject, html, text)
    if result.ok:
        log.info('email sent via=resend type=%s to=%s', tipo, email)
        return result

    if result.detail == 'resend_not_configured' and settings.DEBUG:
        console_result = _send_via_console(email, subject, html, text)
        if console_result.ok:
            log.info('email sent via=console (DEBUG) type=%s to=%s', tipo, email)
        return console_result

    log.error(
        'email_delivery_failed type=%s to=%s error=%s',
        tipo,
        email,
        result.detail,
    )
    return result


def enviar_codigo_verificacion(email: str, code: str) -> EmailSendResult:
    """Send a 10-minute email verification OTP for account onboarding."""
    subject = 'Tu código de verificación — TradeFlow Colón'
    text = (
        f'Tu código de verificación en TradeFlow Colón es: {code}\n\n'
        'Válido por 10 minutos.\n\n'
        '— Zona Libre de Colón, Panamá'
    )
    html = _verification_html(code)
    return enviar_email_transaccional(email, subject, html, text, tipo='verification_code')
