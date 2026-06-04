"""
Aprobación/rechazo centralizado de solicitudes de acceso (UserApplication).

Un único punto de verdad para que TODOS los caminos de revisión (enlace de
correo a revisores, panel /panel/applications/ y Django admin) tengan el mismo
efecto: actualizar estado, activar/desactivar la cuenta y notificar al
solicitante por correo (Supabase Edge Function con fallback Django).
"""
from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.utils import timezone

log = logging.getLogger(__name__)


def _vincular_cuenta(app):
    """Devuelve el User ligado a la solicitud, enlazándolo por correo si falta."""
    user = app.user if getattr(app, 'user_id', None) else None
    if user is None:
        user = User.objects.filter(email__iexact=(app.email or '').strip()).first()
        if user is not None:
            app.user = user
            app.save(update_fields=['user'])
    return user


def _activar_cuenta(app):
    """Activa la cuenta del solicitante y marca su correo como verificado."""
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


def aprobar_solicitud(app, *, notificar: bool = True):
    """Aprueba la solicitud: estado, fecha, activación de cuenta y aviso."""
    app.status = 'approved'
    app.reviewed_at = timezone.now()
    app.save(update_fields=['status', 'reviewed_at'])
    _activar_cuenta(app)
    if notificar:
        try:
            from core.utils.email_sender import enviar_solicitud_decision
            enviar_solicitud_decision(app, aprobada=True)
        except Exception as exc:  # noqa: BLE001 — el correo nunca debe romper el flujo
            log.exception('aprobar_solicitud notificación: %s', exc)
    return app


def rechazar_solicitud(app, *, notificar: bool = True):
    """Rechaza la solicitud: estado, fecha, desactivación de cuenta y aviso."""
    app.status = 'rejected'
    app.reviewed_at = timezone.now()
    app.save(update_fields=['status', 'reviewed_at'])
    user = app.user if getattr(app, 'user_id', None) else None
    if user is not None and user.is_active:
        user.is_active = False
        user.save(update_fields=['is_active'])
    if notificar:
        try:
            from core.utils.email_sender import enviar_solicitud_decision
            enviar_solicitud_decision(app, aprobada=False)
        except Exception as exc:  # noqa: BLE001
            log.exception('rechazar_solicitud notificación: %s', exc)
    return app
