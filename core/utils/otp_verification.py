"""Valida y consume códigos OTP de correo de forma atómica.

La verificación de un solo uso marca el correo del perfil como verificado
para rutas ZLC restringidas.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from core.models import EmailVerification, UserApplication, UserProfile
from core.utils.otp_handler import OTP_EXPIRY_MINUTES

log = logging.getLogger('tradeflow.auth')


@dataclass(frozen=True)
class OtpVerificationResult:
    """Resultado inmutable de un intento de verificar OTP (ok, códigos, user)."""

    ok: bool
    error_code: str = ''
    detail: str = ''
    role: str = ''


def otp_expires_at(verification: EmailVerification) -> datetime:
    """Devuelve el datetime de expiración de una fila OTP."""
    return verification.created_at + timedelta(minutes=OTP_EXPIRY_MINUTES)


def _apply_expo_demo_bypass(user: User) -> None:
    """Aprueba la solicitud y activa la cuenta para el bypass demo Expo.

    Evita callejones sin salida de ``pending_approval`` sin relajar flags de producción.
    """
    _apply_self_serve_activation(user, approve_all_roles=True)


def _apply_self_serve_activation(user: User, *, approve_all_roles: bool = False) -> None:
    """Activa compradores verificados sin esperar aprobación manual de la solicitud."""
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else 'buyer'
    if role != 'buyer' and not approve_all_roles:
        return
    UserApplication.objects.update_or_create(
        user=user,
        defaults={
            'status': 'approved',
            'email': (user.email or '').strip(),
            'full_name': (user.get_full_name() or user.username).strip(),
            'role': role,
            'reviewed_at': timezone.now(),
        },
    )
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])
    log.info('self_serve_activation user_id=%s role=%s', user.pk, role)


def verify_user_otp(user: User, raw_code: str) -> OtpVerificationResult:
    """Valida y consume un OTP de forma atómica; marca el correo como verificado."""
    code = (raw_code or '').strip()
    if len(code) != 6 or not code.isdigit():
        return OtpVerificationResult(
            ok=False,
            error_code='invalid_format',
            detail='OTP must be exactly 6 digits.',
        )

    try:
        with transaction.atomic():
            verification = (
                EmailVerification.objects.select_for_update()
                .filter(user=user, code=code, is_used=False)
                .order_by('-created_at')
                .first()
            )
            now = timezone.now()
            if verification is None:
                return OtpVerificationResult(
                    ok=False,
                    error_code='invalid_or_expired',
                    detail='Invalid or expired verification code.',
                )

            expires_at = otp_expires_at(verification)
            if now > expires_at or not verification.is_valid():
                return OtpVerificationResult(
                    ok=False,
                    error_code='invalid_or_expired',
                    detail='Invalid or expired verification code.',
                )

            profile, _ = UserProfile.objects.select_for_update().get_or_create(
                user=user,
                defaults={'role': 'buyer', 'email_verificado': False},
            )
            profile.email_verificado = True
            profile.token_verificacion = None
            profile.codigo_verificacion_email = ''
            profile.codigo_verificacion_expira = None
            profile.save(
                update_fields=[
                    'email_verificado',
                    'token_verificacion',
                    'codigo_verificacion_email',
                    'codigo_verificacion_expira',
                ],
            )

            role = profile.role or 'buyer'
            if getattr(settings, 'EXPO_DEMO_MODE', False):
                _apply_expo_demo_bypass(user)
            elif role == 'buyer':
                _apply_self_serve_activation(user)

            verification_id = verification.pk
            verification.delete()

            log.info(
                'otp_verified user_id=%s verification_id=%s expires_at=%s',
                user.pk,
                verification_id,
                expires_at.isoformat(),
            )

            return OtpVerificationResult(ok=True, role=role)
    except Exception:
        log.exception('otp_verify_failed user_id=%s', user.pk)
        return OtpVerificationResult(
            ok=False,
            error_code='server_error',
            detail='Could not verify the code. Try again.',
        )
