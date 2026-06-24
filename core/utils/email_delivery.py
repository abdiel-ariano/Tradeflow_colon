"""
Capa de entrega de correo: logging y registro en EmailDeliveryLog (Resend).
"""
from __future__ import annotations

import logging

from django.conf import settings

from core.enterprise_models import EmailDeliveryLog

log = logging.getLogger('tradeflow.email')


def validate_email_infrastructure() -> list[str]:
    """Devuelve lista de advertencias de configuración (vacía = OK)."""
    warnings = []
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    if not base or base.startswith('http://127.0.0.1') and not settings.DEBUG:
        warnings.append('PUBLIC_BASE_URL debe ser la URL pública HTTPS de producción.')
    if not (getattr(settings, 'RESEND_API_KEY', '') or '').strip() and not settings.DEBUG:
        warnings.append('RESEND_API_KEY no configurada; los correos no saldrán en producción.')
    if not getattr(settings, 'DEFAULT_FROM_EMAIL', ''):
        warnings.append('DEFAULT_FROM_EMAIL no está definido.')
    return warnings


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
    **_kwargs,
) -> bool:
    """
    Envía correo con registro en ``EmailDeliveryLog`` vía ``enviar_email_transaccional``.
    """
    from core.email_service import enviar_email_transaccional

    recipients = [r for r in (recipient_list or []) if r]
    if not recipients:
        return False

    html = html_message or message or ''
    text = message or ''
    last_error = ''

    for recipient in recipients:
        result = enviar_email_transaccional(
            recipient,
            subject,
            html,
            text,
            tipo=email_type,
        )
        if not result.ok:
            last_error = result.detail or 'email_delivery_failed'
            EmailDeliveryLog.objects.create(
                email_type=email_type[:40],
                recipient=recipient,
                subject=subject[:255],
                status='failed',
                error_message=last_error[:2000],
                backend=result.channel[:80],
            )
            log.error(
                'email_delivery_failed type=%s to=%s error=%s',
                email_type,
                recipient,
                last_error,
            )
            if not fail_silently:
                raise RuntimeError(last_error)
            return False

        EmailDeliveryLog.objects.create(
            email_type=email_type[:40],
            recipient=recipient,
            subject=subject[:255],
            status='sent',
            backend=f'resend:{result.channel[:90]}',
        )
        log.info('email_sent via=resend type=%s to=%s', email_type, recipient)

    return True
