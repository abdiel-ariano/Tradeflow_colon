"""
Vistas de autenticación y verificación OTP.

Ubicación: ``core/auth_views.py`` (no ``core/views/auth.py`` — ``core/views.py``
es módulo plano y no permite subpaquetes ``core.views.auth``).
"""
from __future__ import annotations

import logging
import re

from axes.decorators import axes_dispatch
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from core.utils.email_sender import enviar_bienvenida
from core.utils.otp_axes import (
    otp_axes_is_locked,
    otp_axes_lockout_response,
    otp_axes_record_failure,
    otp_axes_reset,
)
from core.utils.otp_verification import verify_user_otp

log = logging.getLogger('tradeflow.auth')
security_log = logging.getLogger('tradeflow.security')

AUTH_MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'
OTP_CODE_PATTERN = re.compile(r'^\d{6}$')


def _wants_json(request: HttpRequest) -> bool:
    if request.GET.get('format') == 'json':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


def _redirect_by_role(user) -> str:
    """Destino post-verificación según rol."""
    from django.urls import reverse

    try:
        role = user.profile.role
    except Exception:
        role = 'buyer'
    if role == 'admin' or user.is_superuser:
        return reverse('dashboard')
    if role == 'seller':
        return reverse('portal_seller')
    return reverse('tienda')


def _verify_context(request: HttpRequest) -> dict[str, str]:
    masked = request.user.email or ''
    if '@' in masked:
        local, domain = masked.split('@', 1)
        if len(local) > 2:
            masked = f'{local[0]}***{local[-1]}@{domain}'
    return {'masked_email': masked}


def _json_error(error_code: str, detail: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'ok': False, 'error': error_code, 'detail': detail}, status=status)


def _email_verification_gate_active(user) -> bool:
    """OTP requerido — misma regla que onboarding middleware y decoradores."""
    from core.utils.access_gating import email_verification_required

    return email_verification_required(user)


@login_required
@axes_dispatch
@require_http_methods(['GET', 'POST'])
def verify_otp_view(request: HttpRequest) -> HttpResponse:
    """
    Verificación OTP por email (GET formulario / POST código).

    Seguridad:
    - ``@login_required``: solo el titular de sesión puede verificar.
    - ``@axes_dispatch``: bloqueo tras 5 fallos (``AXES_FAILURE_LIMIT``) + cooloff 1 h.
    - Token de un solo uso: borrado en DB tras éxito (anti-replay).
    - ``transaction.atomic()`` en ``verify_user_otp`` (consistencia perfil + OTP).
    """
    if not _email_verification_gate_active(request.user):
        dest = _redirect_by_role(request.user)
        if _wants_json(request):
            return JsonResponse({'ok': True, 'redirect': dest})
        return redirect(dest)

    try:
        profile = request.user.profile
    except Exception:
        from core.social_auth import user_needs_oauth_role

        if user_needs_oauth_role(request.user):
            return redirect('oauth_complete_signup')
        if _wants_json(request):
            return _json_error('profile_missing', 'User profile not found.', 400)
        from django.contrib import messages

        messages.error(request, 'Profile not found.')
        return redirect('signup')

    if profile.email_verified:
        dest = _redirect_by_role(request.user)
        if _wants_json(request):
            return JsonResponse({'ok': True, 'redirect': dest, 'already_verified': True})
        return redirect(dest)

    username = request.user.username
    if otp_axes_is_locked(request, username):
        security_log.warning('otp_verify_locked user=%s', username)
        return otp_axes_lockout_response(request, username, as_json=_wants_json(request))

    if request.method == 'GET':
        return render(request, 'core/verificar_codigo.html', _verify_context(request))

    raw = (request.POST.get('codigo') or request.POST.get('code') or '').strip()
    if not OTP_CODE_PATTERN.fullmatch(raw):
        otp_axes_record_failure(request, username)
        if _wants_json(request):
            return _json_error('invalid_format', 'Enter a 6-digit code.')
        from django.contrib import messages

        messages.error(request, 'Enter a 6-digit code.')
        return render(request, 'core/verificar_codigo.html', _verify_context(request))

    result = verify_user_otp(request.user, raw)
    if not result.ok:
        failures = otp_axes_record_failure(request, username)
        if otp_axes_is_locked(request, username):
            return otp_axes_lockout_response(request, username, as_json=_wants_json(request))
        detail = result.detail or 'Invalid or expired code.'
        if _wants_json(request):
            return _json_error(
                result.error_code or 'invalid_or_expired',
                detail,
                status=400,
            )
        from django.contrib import messages

        messages.error(request, detail)
        return render(
            request,
            'core/verificar_codigo.html',
            {**_verify_context(request), 'failures': failures},
        )

    otp_axes_reset(username, request)
    login(request, request.user, backend=AUTH_MODEL_BACKEND)

    # Refrescar ORM en memoria tras la transacción OTP (evita gate obsoleto).
    request.user.refresh_from_db()
    try:
        request.user.profile.refresh_from_db()
    except Exception:
        pass

    try:
        enviar_bienvenida(request.user)
    except Exception:
        log.exception('welcome_email_after_otp user_id=%s', request.user.pk)

    dest = _redirect_by_role(request.user)
    from core.utils.access_gating import onboarding_redirect_name

    gate = onboarding_redirect_name(request.user, scope='restricted')
    if gate:
        from django.urls import reverse

        dest = reverse(gate)

    if _wants_json(request):
        return JsonResponse(
            {
                'ok': True,
                'redirect': dest,
                'role': result.role,
            },
        )

    from django.contrib import messages

    messages.success(request, 'Email verified! You can continue now.')
    return redirect(dest)
