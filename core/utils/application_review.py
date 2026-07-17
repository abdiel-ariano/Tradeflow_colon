"""Aprueba o rechaza filas ``UserApplication`` y notifica a los solicitantes."""
from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.utils import timezone

log = logging.getLogger(__name__)


def _vincular_cuenta(app):
    """Devuelve el User vinculado a la solicitud, asociándolo por correo si hace falta."""
    user = app.user if getattr(app, 'user_id', None) else None
    if user is None:
        user = User.objects.filter(email__iexact=(app.email or '').strip()).first()
        if user is not None:
            app.user = user
            app.save(update_fields=['user'])
    return user


def _activar_cuenta(app):
    """Activa la cuenta del solicitante y marca el correo como verificado."""
    user = _vincular_cuenta(app)
    if user is None:
        return None
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])
    profile = getattr(user, 'profile', None)
    if profile is not None and hasattr(profile, 'email_verificado') and not profile.email_verificado:
        profile.email_verificado = True
        profile.save(update_fields=['email_verificado'])
    return user


def mensaje_fallo_correo(email_result) -> str:
    """Texto orientado al admin cuando la decisión se guardó pero falló el envío de correo."""
    from core.utils.email_config import explain_email_failure

    if email_result is None or getattr(email_result, 'ok', True):
        return ''
    detail = getattr(email_result, 'detail', '') or ''
    explanation = explain_email_failure(detail)
    return (
        'The application was processed, but the email could not be sent to the applicant. '
        f'{explanation}'
    )


def _notificar_decision(app, *, aprobada: bool):
    """Envía el correo de decisión; nunca lanza (la aprobación ya está confirmada)."""
    try:
        from core.utils.email_sender import enviar_solicitud_decision

        return enviar_solicitud_decision(app, aprobada=aprobada)
    except Exception as exc:  # noqa: BLE001
        log.exception('notificar_decision: %s', exc)
        from core.email_service import EmailSendResult

        return EmailSendResult(ok=False, channel='error', detail=str(exc)[:500])


def aprobar_solicitud(app, *, notificar: bool = True):
    """Aprueba la solicitud: estado, marca de tiempo, activa cuenta y notifica."""
    app.status = 'approved'
    app.reviewed_at = timezone.now()
    app.save(update_fields=['status', 'reviewed_at'])
    _activar_cuenta(app)
    email_result = None
    if notificar:
        email_result = _notificar_decision(app, aprobada=True)
    return app, email_result


def rechazar_solicitud(app, *, notificar: bool = True):
    """Rechaza la solicitud: estado, marca de tiempo, desactiva cuenta y notifica."""
    app.status = 'rejected'
    app.reviewed_at = timezone.now()
    app.save(update_fields=['status', 'reviewed_at'])
    user = app.user if getattr(app, 'user_id', None) else None
    if user is not None and user.is_active:
        user.is_active = False
        user.save(update_fields=['is_active'])
    email_result = None
    if notificar:
        email_result = _notificar_decision(app, aprobada=False)
    return app, email_result
