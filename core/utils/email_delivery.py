"""
Capa enterprise de entrega de correo: logging, validación y reintentos controlados.
"""
from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection

from core.enterprise_models import EmailDeliveryLog
from core.utils.email_config import smtp_configured

log = logging.getLogger('tradeflow.email')

SMTP_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
CONSOLE_BACKEND = 'django.core.mail.backends.console.EmailBackend'


def _resolve_mail_backend() -> tuple[str, str]:
    """(backend_path, channel_label) — smtp si hay credenciales en .env."""
    if smtp_configured():
        return SMTP_BACKEND, 'smtp'
    configured = getattr(settings, 'EMAIL_BACKEND', CONSOLE_BACKEND) or CONSOLE_BACKEND
    if 'smtp' in configured.lower():
        return configured, 'smtp'
    return configured, 'console'


def validate_email_infrastructure() -> list[str]:
    """Devuelve lista de advertencias de configuración (vacía = OK)."""
    warnings = []
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip().rstrip('/')
    if not base or base.startswith('http://127.0.0.1') and not settings.DEBUG:
        warnings.append('PUBLIC_BASE_URL debe ser la URL pública HTTPS de producción.')
    if not getattr(settings, 'EMAIL_USE_REAL_SMTP', False) and not settings.DEBUG:
        warnings.append('SMTP no configurado; los correos no saldrán en producción.')
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
    Envía correo con registro en ``EmailDeliveryLog`` y un reintento opcional.

    Returns:
        bool: True si el envío fue exitoso.
    """
    settings_backend = getattr(settings, 'EMAIL_BACKEND', '')
    mail_backend, channel = _resolve_mail_backend()
    recipient = recipient_list[0] if recipient_list else ''
    last_error = ''

    for attempt in range(1, max_attempts + 1):
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
            connection = get_connection(backend=mail_backend, fail_silently=False)
            msg.connection = connection
            msg.send(fail_silently=False)
            EmailDeliveryLog.objects.create(
                email_type=email_type[:40],
                recipient=recipient,
                subject=subject[:255],
                status='sent',
                backend=f'{channel}:{mail_backend[:100]}',
            )
            if channel == 'console':
                log.warning(
                    'email_sent CONSOLA (no Gmail) type=%s to=%s — '
                    'revisa la terminal de runserver o configura .env con bootstrap_dotenv.py',
                    email_type,
                    recipient,
                )
            else:
                log.info('email_sent via=smtp type=%s to=%s', email_type, recipient)
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
            if attempt < max_attempts:
                time.sleep(0.6)

    EmailDeliveryLog.objects.create(
        email_type=email_type[:40],
        recipient=recipient,
        subject=subject[:255],
        status='failed',
        error_message=last_error[:2000],
        backend=f'{channel}:{settings_backend[:80]}',
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
