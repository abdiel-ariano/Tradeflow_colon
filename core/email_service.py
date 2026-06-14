"""
Transactional email: Supabase Edge Function (opcional) → Gmail SMTP → consola.
"""
from __future__ import annotations

import logging
import json as _json
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

log = logging.getLogger('tradeflow.email')

_LEGACY_SUPABASE_TYPES = frozenset({
    'verification_code',
    'transactional',
})


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


def _supabase_email_enabled() -> bool:
    return bool(
        getattr(settings, 'SUPABASE_EMAIL_ENABLED', True)
        and getattr(settings, 'SUPABASE_CONFIGURED', False)
    )


def _is_non_retryable_delivery_error(detail: str) -> bool:
    """Errores de política del proveedor en Edge Function — no reintentar SMTP."""
    d = (detail or '').lower()
    return (
        'validation_error' in d
        or 'verify a domain' in d
        or 'only send testing emails' in d
        or 'statuscode":403' in d
        or 'statuscode": 403' in d
    )


def _supabase_type_for_edge(tipo: str) -> str:
    if tipo in _LEGACY_SUPABASE_TYPES:
        return tipo
    return 'transactional'


def _build_supabase_payload(
    email: str,
    subject: str,
    html: str,
    text: str,
    tipo: str,
) -> dict:
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''
    return {
        'to': email,
        'recipient': email,
        'subject': subject,
        'html': html,
        'text': text,
        'type': tipo,
        'email_type': tipo,
        'from': from_email,
        'from_email': from_email,
    }


def _invoke_supabase_function(payload: dict) -> tuple[bool, str]:
    supabase_url = getattr(settings, 'SUPABASE_URL', '') or ''
    service_key = getattr(settings, 'SUPABASE_SERVICE_KEY', '') or ''
    function_name = getattr(settings, 'SUPABASE_EMAIL_FUNCTION', 'send-transactional-email')

    if not supabase_url or not service_key:
        return False, 'client_not_configured'

    url = f'{supabase_url.rstrip("/")}/functions/v1/{function_name}'
    body = _json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
    }
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        # The Edge Function relays via SMTP from Supabase's network, which can
        # take a few seconds; allow enough time so it isn't reported as failed.
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status >= 400:
                return False, f'function_status_{resp.status}'
            return True, ''
    except urllib.error.HTTPError as exc:
        detail = f'HTTP Error {exc.code}: {exc.reason}'
        try:
            err_body = exc.read().decode('utf-8', errors='replace')[:800]
            if err_body:
                detail = f'{detail} — {err_body}'
        except Exception:
            pass
        log.warning(
            'Supabase Edge Function failed (%s): %s',
            function_name,
            detail,
        )
        return False, detail
    except Exception as exc:
        log.warning('Supabase Edge Function failed (%s): %s', function_name, exc)
        return False, str(exc)[:500]


def _send_via_supabase(
    email: str,
    subject: str,
    html: str,
    text: str,
    tipo: str = 'transactional',
) -> EmailSendResult:
    if not _supabase_email_enabled():
        return EmailSendResult(ok=False, channel='supabase', detail='supabase_email_disabled')

    edge_type = _supabase_type_for_edge(tipo)
    payload = _build_supabase_payload(email, subject, html, text, edge_type)
    ok, detail = _invoke_supabase_function(payload)
    if ok:
        return EmailSendResult(ok=True, channel='supabase')

    if edge_type != tipo and edge_type != 'transactional':
        payload_retry = _build_supabase_payload(email, subject, html, text, 'transactional')
        ok_retry, detail_retry = _invoke_supabase_function(payload_retry)
        if ok_retry:
            return EmailSendResult(ok=True, channel='supabase')
        detail = detail_retry or detail

    return EmailSendResult(ok=False, channel='supabase', detail=detail or 'supabase_failed')


def _send_via_django(
    email: str,
    subject: str,
    html: str,
    text: str,
    *,
    email_type: str = 'transactional',
) -> EmailSendResult:
    from core.utils.email_delivery import deliver_mail

    if not getattr(settings, 'EMAIL_SMTP_CONFIGURED', False):
        return EmailSendResult(
            ok=False,
            channel='django',
            detail=(
                'smtp_not_configured: set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD '
                '(Gmail App Password) on Railway, or enable SUPABASE_EMAIL_ENABLED.'
            ),
        )

    try:
        deliver_mail(
            subject=subject,
            message=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html,
            email_type=email_type,
            fail_silently=False,
            skip_supabase=True,
        )
        backend = getattr(settings, 'EMAIL_BACKEND', 'django')
        return EmailSendResult(ok=True, channel=f'django:{backend.split(".")[-1]}')
    except Exception as exc:
        log.exception('Django email fallback failed: %s', exc)
        return EmailSendResult(ok=False, channel='django', detail=str(exc)[:500])


def enviar_email_transaccional(
    email: str,
    subject: str,
    html: str,
    text: str,
    tipo: str = 'transactional',
) -> EmailSendResult:
    """
    Envía correo: Supabase Edge Function (si está activa) y luego Gmail SMTP.
    """
    if not (email or '').strip():
        return EmailSendResult(ok=False, channel='none', detail='empty_recipient')

    supabase_result = None
    if _supabase_email_enabled():
        supabase_result = _send_via_supabase(email, subject, html, text, tipo)
        if supabase_result.ok:
            log.info('email sent via=supabase type=%s to=%s', tipo, email)
            return supabase_result

        if _is_non_retryable_delivery_error(supabase_result.detail):
            log.error(
                'Supabase email rejected (type=%s to=%s): %s',
                tipo,
                email,
                supabase_result.detail[:400],
            )
    else:
        supabase_result = EmailSendResult(
            ok=False,
            channel='supabase',
            detail='supabase_email_disabled',
        )

    log.warning(
        'Supabase failed (type=%s detail=%s), trying Gmail SMTP for %s',
        tipo,
        supabase_result.detail,
        email,
    )
    django_result = _send_via_django(email, subject, html, text, email_type=tipo)
    if django_result.ok:
        log.info('email sent via=gmail fallback type=%s to=%s', tipo, email)
    return django_result


def enviar_codigo_verificacion(email: str, code: str) -> EmailSendResult:
    """Send OTP code (Supabase first, then Gmail SMTP)."""
    subject = 'Your verification code — TradeFlow Colón'
    text = (
        f'Your TradeFlow Colón verification code is: {code}\n\n'
        'Valid for 15 minutes.\n\n'
        '— Colón Free Zone, Panama'
    )
    html = _verification_html(code)
    return enviar_email_transaccional(email, subject, html, text, tipo='verification_code')
