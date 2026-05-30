"""
Envío de correo transaccional: Supabase Edge Function → fallback Django send_mail.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail

from core.supabase_client import get_supabase_client

log = logging.getLogger('tradeflow.email')


@dataclass
class EmailSendResult:
    ok: bool
    channel: str
    detail: str = ''


def _verification_html(code: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:24px;background:#404b57;font-family:Montserrat,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;">
    <tr>
      <td style="background:#404b57;border-radius:16px;padding:32px;text-align:center;border:2px solid #62929a;">
        <p style="color:#d9cab3;font-size:14px;margin:0 0 8px;">TradeFlow Colón</p>
        <h1 style="color:#ffffff;font-size:22px;margin:0 0 24px;">Your verification code</h1>
        <p style="color:#ffffff;font-size:42px;font-weight:700;letter-spacing:8px;margin:0 0 16px;">{code}</p>
        <p style="color:#d9cab3;font-size:13px;margin:0;">Valid for 15 minutes</p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_via_supabase(email: str, subject: str, html: str, text: str) -> EmailSendResult:
    client = get_supabase_client()
    if client is None:
        return EmailSendResult(ok=False, channel='supabase', detail='client_not_configured')

    function_name = getattr(settings, 'SUPABASE_EMAIL_FUNCTION', 'send-transactional-email')
    payload = {
        'to': email,
        'subject': subject,
        'html': html,
        'text': text,
        'type': 'verification_code',
    }
    try:
        response = client.functions.invoke(
            function_name,
            invoke_options={'body': payload},
        )
        status = getattr(response, 'status', None) or getattr(response, 'status_code', 200)
        if status and int(status) >= 400:
            return EmailSendResult(
                ok=False,
                channel='supabase',
                detail=f'function_status_{status}',
            )
        return EmailSendResult(ok=True, channel='supabase')
    except Exception as exc:
        log.warning('Supabase email function falló (%s): %s', function_name, exc)
        return EmailSendResult(ok=False, channel='supabase', detail=str(exc)[:500])


def _send_via_django(email: str, subject: str, html: str, text: str) -> EmailSendResult:
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
        log.exception('Django send_mail falló: %s', exc)
        return EmailSendResult(ok=False, channel='django', detail=str(exc)[:500])


def enviar_codigo_verificacion(email: str, code: str) -> EmailSendResult:
    """
    Envía el código OTP al correo indicado.

    Intenta Supabase (Edge Function); si falla, usa ``send_mail`` de Django.
    """
    subject = 'Your verification code — TradeFlow Colón'
    text = (
        f'Your TradeFlow Colón verification code is: {code}\n\n'
        'Valid for 15 minutes.\n\n'
        '— Colón Free Zone, Panama'
    )
    html = _verification_html(code)

    supabase_result = _send_via_supabase(email, subject, html, text)
    if supabase_result.ok:
        log.info('verification_email sent via=supabase to=%s', email)
        return supabase_result

    django_result = _send_via_django(email, subject, html, text)
    if django_result.ok:
        log.info(
            'verification_email sent via=django (supabase fallback) to=%s supabase_detail=%s',
            email,
            supabase_result.detail,
        )
    return django_result
