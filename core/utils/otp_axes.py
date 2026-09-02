"""Helpers de bloqueo respaldados por AXES contra fuerza bruta de OTP.

Registra intentos fallidos de verificación para que atacantes no pulvericen
códigos contra correos de registro ZLC.
"""
from __future__ import annotations

import logging
from typing import Any

from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_client_ip_address, get_credentials, get_lockout_response
from django.http import HttpRequest, HttpResponse, JsonResponse

log = logging.getLogger('tradeflow.security')

OTP_AXES_SENDER = 'tradeflow.otp_verify'


def otp_axes_credentials(username: str) -> dict[str, Any]:
    """Construye credenciales AXES; el prefijo ``otp:`` aísla OTP de contadores de contraseña."""
    return get_credentials(username=f'otp:{username}')


def otp_axes_is_locked(request: HttpRequest, username: str) -> bool:
    """Devuelve True cuando AXES ha bloqueado intentos OTP para la petición."""
    credentials = otp_axes_credentials(username)
    return AxesProxyHandler.is_locked(request, credentials)


def otp_axes_record_failure(request: HttpRequest, username: str) -> int:
    """Registra un intento OTP fallido con AXES."""
    credentials = otp_axes_credentials(username)
    AxesProxyHandler.user_login_failed(OTP_AXES_SENDER, credentials, request=request)
    failures = AxesProxyHandler.get_failures(request, credentials)
    log.warning(
        'otp_verify_failed username=%s ip=%s failures=%s',
        username,
        get_client_ip_address(request),
        failures,
    )
    return failures


def otp_axes_reset(username: str, request: HttpRequest) -> None:
    """Limpia el estado de fallos AXES tras un OTP exitoso."""
    AxesProxyHandler.reset_attempts(
        username=f'otp:{username}',
        ip_address=get_client_ip_address(request),
    )


def otp_axes_lockout_response(
    request: HttpRequest,
    username: str,
    *,
    as_json: bool = False,
) -> HttpResponse:
    """Devuelve respuesta HTTP/JSON de bloqueo (cooloff desde ``AXES_COOLOFF_TIME``)."""
    credentials = otp_axes_credentials(username)
    if as_json:
        return JsonResponse(
            {
                'ok': False,
                'error': 'locked',
                'detail': 'Too many failed attempts. Try again later.',
            },
            status=429,
        )
    return get_lockout_response(request, credentials)
