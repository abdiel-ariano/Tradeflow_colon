"""
Verificación de OTP (EmailVerification) con mitigación de replay y bypass Expo.
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
    """Resultado estructurado de la verificación OTP."""

    ok: bool
    error_code: str = ''
    detail: str = ''
    role: str = ''


def otp_expires_at(verification: EmailVerification) -> datetime:
    """Calcula ``expires_at`` a partir de ``created_at`` y el TTL del handler."""
    return verification.created_at + timedelta(minutes=OTP_EXPIRY_MINUTES)


def _apply_expo_demo_bypass(user: User) -> None:
    """
    Bypass de onboarding en demo Expo: solicitud aprobada + cuenta activa.

  Mitiga bloqueos de ``pending_approval`` sin relajar flags globales en producción.
    """
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else 'buyer'
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
    log.info('expo_demo_bypass user_id=%s application=approved', user.pk)


def verify_user_otp(user: User, raw_code: str) -> OtpVerificationResult:
    """
    Valida OTP del usuario en transacción atómica.

    Mitigaciones:
    - ``select_for_update`` evita condiciones de carrera en doble POST.
    - Borrado del token tras éxito previene replay (A07:2021).
    - Expiración estricta vía ``expires_at`` / ``is_valid()``.
    """
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

            if getattr(settings, 'EXPO_DEMO_MODE', False):
                _apply_expo_demo_bypass(user)

            verification_id = verification.pk
            verification.delete()

            log.info(
                'otp_verified user_id=%s verification_id=%s expires_at=%s',
                user.pk,
                verification_id,
                expires_at.isoformat(),
            )

            role = profile.role or 'buyer'
            return OtpVerificationResult(ok=True, role=role)
    except Exception:
        log.exception('otp_verify_failed user_id=%s', user.pk)
        return OtpVerificationResult(
            ok=False,
            error_code='server_error',
            detail='Could not verify the code. Try again.',
        )
