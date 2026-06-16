"""
Capa de entrega de correo: logging, validación y reintentos (Gmail SMTP / consola).
"""
from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection

from core.enterprise_models import EmailDeliveryLog

log = logging.getLogger('tradeflow.email')


def validate_email_infrastructure() -> list[str]:
    """Devuelve lista de advertencias de configuración (vacía = OK)."""
    warnings = []
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    if not base or base.startswith('http://127.0.0.1') and not settings.DEBUG:
        warnings.append('PUBLIC_BASE_URL debe ser la URL pública HTTPS de producción.')
    if (
        not getattr(settings, 'EMAIL_USE_REAL_SMTP', False)
        and not getattr(settings, 'SUPABASE_CONFIGURED', False)
        and not settings.DEBUG
    ):
        warnings.append(
            'Sin Supabase email ni EMAIL_HOST_* (Gmail); '
            'los correos fallarán en producción.'
        )
    elif not getattr(settings, 'EMAIL_USE_REAL_SMTP', False) and not settings.DEBUG:
        warnings.append(
            'Gmail SMTP no configurado; el fallback no podrá enviar si Supabase falla.'
        )
    if not getattr(settings, 'DEFAULT_FROM_EMAIL', ''):
        warnings.append('DEFAULT_FROM_EMAIL no está definido.')
    return warnings


def _try_supabase_delivery(
    subject: str,
    message: str,
    recipient_list: list,
    html_message: str | None,
    email_type: str,
) -> bool:
    """Envía vía Supabase Edge Function (HTTPS) si está habilitada.

    Devuelve True solo si TODOS los destinatarios se enviaron por Supabase.
    Es la ruta que funciona en hosts que bloquean el SMTP saliente (Railway).
    """
    try:
        # Import perezoso para evitar import circular con email_service.
        from core.email_service import _send_via_supabase, _supabase_email_enabled
    except Exception:  # pragma: no cover
        return False
    if not _supabase_email_enabled():
        return False
    recipients = [r for r in (recipient_list or []) if r]
    if not recipients:
        return False
    html = html_message or message or ''
    text = message or ''
    for r in recipients:
        result = _send_via_supabase(r, subject, html, text, email_type)
        if not result.ok:
            log.warning(
                'supabase_delivery_failed type=%s to=%s detail=%s',
                email_type, r, result.detail,
            )
            return False
    return True


def deliver_mail(
    subject: str,
    message: str,
    from_email: str,
    recipient_list: list,
    *,
    html_message: str | None = None,
    email_type: str = 'transactional',
    fail_silently: bool = False,
    max_attempts: int = 2,
    skip_supabase: bool = False,
    **_kwargs,
) -> bool:
    """
    Envía correo con registro en ``EmailDeliveryLog`` y un reintento opcional.

    Intenta primero la Supabase Edge Function (HTTPS) y, si no, Gmail SMTP
    (``EMAIL_BACKEND`` de Django).
    """
    backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
    channel = 'gmail' if getattr(settings, 'EMAIL_SMTP_CONFIGURED', False) else 'django'
    recipient = recipient_list[0] if recipient_list else ''
    last_error = ''

    # Canal preferido: Supabase Edge Function (funciona aunque el host bloquee
    # el SMTP saliente). Solo se intenta si está habilitada y configurada.
    if not skip_supabase and _try_supabase_delivery(
        subject, message, recipient_list, html_message, email_type
    ):
        EmailDeliveryLog.objects.create(
            email_type=email_type[:40],
            recipient=recipient,
            subject=subject[:255],
            status='sent',
            backend='supabase',
        )
        log.info('email_sent via=supabase type=%s to=%s', email_type, recipient)
        return True

    from core.utils.email_config import django_smtp_fallback_enabled

    if not django_smtp_fallback_enabled():
        last_error = (
            'smtp_fallback_disabled: on Railway use SUPABASE_EMAIL_ENABLED=true '
            'and send-transactional-email Edge Function.'
        )
        EmailDeliveryLog.objects.create(
            email_type=email_type[:40],
            recipient=recipient,
            subject=subject[:255],
            status='failed',
            error_message=last_error[:2000],
            backend=backend[:80],
        )
        log.error('email_delivery_failed type=%s to=%s error=%s', email_type, recipient, last_error)
        if not fail_silently:
            raise RuntimeError(last_error)
        return False

    # Do not block HTTP requests (checkout, status changes) on long SMTP timeouts.
    attempts = 1 if fail_silently else max_attempts
    base_timeout = getattr(settings, 'EMAIL_TIMEOUT', 10)
    timeout = min(base_timeout, 4) if fail_silently else base_timeout

    for attempt in range(1, attempts + 1):
        try:
            if html_message:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=from_email,
                    to=recipient_list,
                )
                msg.attach_alternative(html_message, 'text/html')
            else:
                msg = EmailMessage(
                    subject=subject,
                    body=message,
                    from_email=from_email,
                    to=recipient_list,
                )
            msg.connection = get_connection(fail_silently=False, timeout=timeout)
            msg.send(fail_silently=False)
            EmailDeliveryLog.objects.create(
                email_type=email_type[:40],
                recipient=recipient,
                subject=subject[:255],
                status='sent',
                backend=f'{channel}:{backend[:100]}',
            )
            log.info('email_sent via=%s type=%s to=%s', channel, email_type, recipient)
            return True
        except Exception as exc:
            last_error = str(exc)
            log.warning(
                'email_attempt_failed type=%s to=%s attempt=%s error=%s',
                email_type,
                recipient,
                attempt,
                last_error,
            )
            if attempt < attempts and not fail_silently:
                time.sleep(0.6)

    EmailDeliveryLog.objects.create(
        email_type=email_type[:40],
        recipient=recipient,
        subject=subject[:255],
        status='failed',
        error_message=last_error[:2000],
        backend=backend[:80],
    )
    log.error(
        'email_delivery_failed type=%s to=%s error=%s',
        email_type,
        recipient,
        last_error,
    )
    if not fail_silently:
        raise RuntimeError(last_error or 'email_delivery_failed')
    return False
