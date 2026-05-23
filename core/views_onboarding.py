"""
Pantallas premium de onboarding: verificación y aprobación empresarial.
"""
from __future__ import annotations

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.models import UserProfile
from core.utils.access_gating import (
    application_gate_status,
    email_verification_required,
    latest_application_for_email,
    onboarding_context,
    onboarding_redirect_name,
)
from core.utils.email_sender import enviar_verificacion_email


@login_required
def onboarding_espera_verificacion(request):
    """Pantalla de espera hasta verificar correo."""
    if not email_verification_required(request.user):
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = 'Verifica tu correo'
    from django.urls import reverse
    ctx['poll_url'] = reverse('api_onboarding_verification_status')
    return render(request, 'core/onboarding_espera_verificacion.html', ctx)


@login_required
def onboarding_espera_aprobacion(request):
    """Solicitud en revisión — acceso limitado."""
    gate = application_gate_status(request.user.email or '')
    if gate not in ('pending', 'under_review'):
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = 'Aplicación en revisión'
    return render(request, 'core/onboarding_espera_aprobacion.html', ctx)


@login_required
def onboarding_solicitud_requerida(request):
    """Debe completar solicitud de acceso empresarial."""
    gate = application_gate_status(request.user.email or '')
    if gate is None:
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')
    if gate in ('pending', 'under_review'):
        return redirect('onboarding_espera_aprobacion')
    if gate == 'rejected':
        return redirect('onboarding_aplicacion_rechazada')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = 'Acceso empresarial'
    return render(request, 'core/onboarding_solicitud_requerida.html', ctx)


@login_required
def onboarding_aplicacion_rechazada(request):
    gate = application_gate_status(request.user.email or '')
    if gate != 'rejected':
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = 'Solicitud no aprobada'
    return render(request, 'core/onboarding_aplicacion_rechazada.html', ctx)


@login_required
@require_POST
def onboarding_reenviar_verificacion(request):
    """Reenvío con cooldown anti-spam (sesión)."""
    if not email_verification_required(request.user):
        messages.info(request, 'Tu correo ya está verificado.')
        return redirect('home')

    last = request.session.get('verify_resend_at', 0)
    now = time.time()
    if now - last < 60:
        wait = int(60 - (now - last))
        messages.warning(request, f'Espera {wait}s antes de reenviar.')
        return redirect('onboarding_espera_verificacion')

    try:
        enviar_verificacion_email(request.user, request)
        request.session['verify_resend_at'] = now
        messages.success(request, 'Correo de verificación reenviado.')
    except Exception:
        messages.error(request, 'No pudimos enviar el correo. Intenta más tarde.')
    return redirect('onboarding_espera_verificacion')


@login_required
@require_GET
def api_onboarding_verification_status(request):
    """Polling ligero para detectar verificación sin recargar sesión."""
    try:
        profile = UserProfile.objects.get(user=request.user)
        verified = profile.email_verificado
    except UserProfile.DoesNotExist:
        verified = False
    from django.urls import reverse
    return JsonResponse({
        'verified': verified,
        'redirect': reverse('home') if verified else '',
    })


def onboarding_solicitud_enviada(request):
    """Confirmación pública tras enviar solicitud de acceso."""
    return render(request, 'core/onboarding_solicitud_enviada.html', {
        'titulo_pagina': 'Solicitud recibida',
    })
