"""
Transactional email: Supabase Edge Function → Django send_mail fallback.
"""
from __future__ import annotations

import logging
import json as _json
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail

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
<body style="margin:0;padding:24px;background:#0F2A44;font-family:Montserrat,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;">
    <tr>
      <td style="background:#1B3B63;border-radius:16px;padding:32px;text-align:center;border:2px solid #2E5B8A;">
        <p style="color:#F2F3F5;font-size:14px;margin:0 0 8px;">TradeFlow Colón</p>
        <h1 style="color:#ffffff;font-size:22px;margin:0 0 24px;">Your verification code</h1>
        <p style="color:#F26522;font-size:48px;font-weight:700;letter-spacing:10px;margin:0 0 16px;">{code}</p>
        <p style="color:#F2F3F5;font-size:13px;margin:0;">Valid for 15 minutes. Do not share this code.</p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_via_supabase(email: str, subject: str, html: str, text: str) -> EmailSendResult:
    supabase_url  = getattr(settings, 'SUPABASE_URL', '') or ''
    service_key   = getattr(settings, 'SUPABASE_SERVICE_KEY', '') or ''
    function_name = getattr(settings, 'SUPABASE_EMAIL_FUNCTION', 'send-transactional-email')

    if not supabase_url or not service_key:
        return EmailSendResult(ok=False, channel='supabase', detail='client_not_configured')

    url = f'{supabase_url.rstrip("/")}/functions/v1/{function_name}'
    payload = _json.dumps({
        'to': email,
        'subject': subject,
        'html': html,
        'text': text,
        'type': 'verification_code',
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {service_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            if status >= 400:
                return EmailSendResult(
                    ok=False,
                    channel='supabase',
                    detail=f'function_status_{status}',
                )
            return EmailSendResult(ok=True, channel='supabase')
    except Exception as exc:
        log.warning('Supabase Edge Function failed (%s): %s', function_name, exc)
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
        log.exception('Django send_mail failed: %s', exc)
        return EmailSendResult(ok=False, channel='django', detail=str(exc)[:500])


def enviar_codigo_verificacion(email: str, code: str) -> EmailSendResult:
    """
    Send OTP code to the given email.
    Tries Supabase Edge Function first; falls back to Django send_mail.
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

    log.warning(
        'Supabase failed (detail=%s), trying Django fallback for %s',
        supabase_result.detail,
        email,
    )
    django_result = _send_via_django(email, subject, html, text)
    if django_result.ok:
        log.info('verification_email sent via=django fallback to=%s', email)
    return django_result
