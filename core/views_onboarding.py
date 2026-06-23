"""
Pantallas premium de onboarding: verificación y aprobación empresarial.
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.email_service import enviar_codigo_verificacion
from core.models import UserProfile
from core.utils.otp_handler import generate_user_otp

log = logging.getLogger('tradeflow.onboarding')

SESSION_PENDING_VERIFY_USER_ID = 'pending_verify_user_id'
from core.utils.access_gating import (
    application_gate_status,
    email_verification_required,
    latest_application_for_email,
    onboarding_context,
    onboarding_redirect_name,
)


def _store_pending_verification_session(request: HttpRequest, user) -> None:
    """Contexto de sesión para que /verificar/ identifique la cuenta en validación."""
    request.session[SESSION_PENDING_VERIFY_USER_ID] = user.pk
    request.session['pending_verify_email'] = user.email or ''
    request.session.modified = True


def finalize_signup_with_otp(request: HttpRequest, user) -> HttpResponse:
    """
    Tras registro exitoso en modo demo (EXPO_DEMO_MODE): genera OTP, envía correo
    vía Resend y redirige a /verificar/ sin abortar el flujo si el correo falla.
    """
    _store_pending_verification_session(request, user)

    try:
        otp_code = generate_user_otp(user)
    except Exception:
        log.exception('signup_otp_generate_failed user_id=%s', user.pk)
        messages.warning(
            request,
            'Account created, but we could not generate a verification code. '
            'Use "Resend code" on the next screen.',
        )
        return redirect('verificar_codigo')

    try:
        result = enviar_codigo_verificacion(user.email, otp_code)
        if result.ok:
            messages.success(
                request,
                f'We sent a 6-digit code to {user.email}. Check your inbox and spam folder.',
            )
        else:
            log.warning(
                'signup_otp_email_failed user_id=%s channel=%s detail=%s',
                user.pk,
                result.channel,
                result.detail,
            )
            messages.warning(
                request,
                'Your account was created, but we could not send the verification email. '
                'Request a new code on the next screen if needed.',
            )
    except Exception:
        log.exception('signup_otp_email_exception user_id=%s email=%s', user.pk, user.email)
        messages.warning(
            request,
            'Your account was created, but the email service is temporarily unavailable. '
            'You can still enter your code or request a new one.',
        )

    return redirect('verificar_codigo')


def _redirect_active_verified_user(request):
    """Skip onboarding gates for approved, verified accounts."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return None
    if (
        request.user.is_active
        and profile.email_verificado
        and profile.role
    ):
        from core.views import _redirect_by_role
        return redirect(_redirect_by_role(request.user))
    return None


@login_required
def onboarding_espera_verificacion(request):
    """Compatibilidad: redirige al flujo de código de 6 dígitos."""
    bypass = _redirect_active_verified_user(request)
    if bypass:
        return bypass
    return redirect('verificar_codigo')


@login_required
@require_POST
def onboarding_verificar_codigo(request):
    """Compatibilidad: delega al flujo /verificar/."""
    from core.views import verificar_codigo
    return verificar_codigo(request)


@login_required
@require_POST
def onboarding_reenviar_verificacion(request):
    """Compatibilidad: delega reenvío de código por correo."""
    from core.views import enviar_codigo
    return enviar_codigo(request)


@login_required
def onboarding_espera_aprobacion(request):
    """Solicitud en revisión — acceso limitado."""
    bypass = _redirect_active_verified_user(request)
    if bypass:
        return bypass
    gate = application_gate_status(request.user.email or '')
    if gate not in ('pending', 'under_review'):
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = 'Application under review'
    return render(request, 'core/onboarding_espera_aprobacion.html', ctx)


@login_required
def onboarding_solicitud_requerida(request):
    """Debe completar solicitud de acceso empresarial."""
    bypass = _redirect_active_verified_user(request)
    if bypass:
        return bypass
    gate = application_gate_status(request.user.email or '')
    if gate is None:
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')
    if gate in ('pending', 'under_review'):
        return redirect('onboarding_espera_aprobacion')
    if gate == 'rejected':
        return redirect('onboarding_aplicacion_rechazada')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = 'Business access'
    return render(request, 'core/onboarding_solicitud_requerida.html', ctx)


@login_required
def onboarding_aplicacion_rechazada(request):
    bypass = _redirect_active_verified_user(request)
    if bypass:
        return bypass
    gate = application_gate_status(request.user.email or '')
    if gate != 'rejected':
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = 'Application not approved'
    return render(request, 'core/onboarding_aplicacion_rechazada.html', ctx)


@login_required
@require_GET
def api_onboarding_verification_status(request):
    """Polling ligero para detectar verificación sin recargar sesión."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        verified = profile.email_verificado
    except UserProfile.DoesNotExist:
        verified = False
    return JsonResponse({
        'verified': verified,
        'redirect': reverse('tienda') if verified else '',
    })


def onboarding_solicitud_enviada(request):
    """Confirmación pública tras enviar solicitud de acceso."""
    return render(request, 'core/onboarding_solicitud_enviada.html', {
        'titulo_pagina': 'Application received',
    })
