"""
Pantallas premium de onboarding: verificación y aprobación empresarial.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.models import UserProfile
from core.utils.access_gating import (
    application_gate_status,
    email_verification_required,
    latest_application_for_email,
    onboarding_context,
    onboarding_redirect_name,
)


@login_required
def onboarding_espera_verificacion(request):
    """Compatibilidad: redirige al flujo Resend / código de 6 dígitos."""
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
    """Compatibilidad: delega reenvío Resend."""
    from core.views import enviar_codigo
    return enviar_codigo(request)


@login_required
def onboarding_espera_aprobacion(request):
    """Solicitud en revisión — acceso limitado."""
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
