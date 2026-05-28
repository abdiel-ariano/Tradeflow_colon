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
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from core.models import UserProfile
from core.utils.access_gating import (
    application_gate_status,
    email_verification_required,
    latest_application_for_email,
    onboarding_context,
    onboarding_redirect_name,
)
from core.utils.email_config import smtp_configured
from core.utils.email_sender import enviar_verificacion_email
from core.utils.email_verification import verify_email_code


def _verification_error_message(key: str) -> str:
    messages_map = {
        'invalid_format': _('Ingresa un código de 6 dígitos.'),
        'no_code': _('No hay código activo. Reenvía el correo de verificación.'),
        'expired': _('El código expiró. Solicita uno nuevo.'),
        'wrong_code': _('Código incorrecto. Revisa tu correo e intenta de nuevo.'),
    }
    return str(messages_map.get(key, _('No se pudo verificar el código.')))


@login_required
def onboarding_espera_verificacion(request):
    """Pantalla de espera hasta verificar correo (enlace o código OTP)."""
    if not email_verification_required(request.user):
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'tienda')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = _('Verifica tu correo')
    ctx['poll_url'] = reverse('api_onboarding_verification_status')
    ctx['smtp_configured'] = smtp_configured()
    ctx['env_file_path'] = str(settings.BASE_DIR / '.env')
    ctx['env_file_exists'] = (settings.BASE_DIR / '.env').is_file()
    last = request.session.get('verify_resend_at', 0)
    ctx['resend_cooldown_sec'] = max(0, int(60 - (time.time() - last)))
    return render(request, 'core/onboarding_espera_verificacion.html', ctx)


@login_required
@require_POST
def onboarding_verificar_codigo(request):
    """Valida el código de 6 dígitos enviado por correo."""
    if not email_verification_required(request.user):
        messages.info(request, _('Tu correo ya está verificado.'))
        return redirect('tienda')

    raw = (request.POST.get('codigo') or '').strip()
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        messages.error(request, _('Perfil no encontrado.'))
        return redirect('onboarding_espera_verificacion')

    ok, err_key = verify_email_code(profile, raw)
    if ok:
        messages.success(request, _('¡Correo verificado! Ya puedes usar la tienda.'))
        return redirect('tienda')

    messages.error(request, _verification_error_message(err_key))
    return redirect('onboarding_espera_verificacion')


@login_required
def onboarding_espera_aprobacion(request):
    """Solicitud en revisión — acceso limitado."""
    gate = application_gate_status(request.user.email or '')
    if gate not in ('pending', 'under_review'):
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = _('Aplicación en revisión')
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
    ctx['titulo_pagina'] = _('Acceso empresarial')
    return render(request, 'core/onboarding_solicitud_requerida.html', ctx)


@login_required
def onboarding_aplicacion_rechazada(request):
    gate = application_gate_status(request.user.email or '')
    if gate != 'rejected':
        nxt = onboarding_redirect_name(request.user)
        return redirect(nxt or 'home')

    ctx = onboarding_context(request.user)
    ctx['titulo_pagina'] = _('Solicitud no aprobada')
    return render(request, 'core/onboarding_aplicacion_rechazada.html', ctx)


@login_required
@require_POST
def onboarding_reenviar_verificacion(request):
    """Reenvío con cooldown anti-spam (sesión)."""
    if not email_verification_required(request.user):
        messages.info(request, _('Tu correo ya está verificado.'))
        return redirect('tienda')

    last = request.session.get('verify_resend_at', 0)
    now = time.time()
    if now - last < 60:
        wait = int(60 - (now - last))
        messages.warning(request, _('Espera %(sec)s s antes de reenviar.') % {'sec': wait})
        return redirect('onboarding_espera_verificacion')

    if not smtp_configured():
        messages.warning(
            request,
            _(
                'El servidor no tiene correo SMTP configurado. '
                'Revisa EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en el entorno.'
            ),
        )
        return redirect('onboarding_espera_verificacion')

    try:
        enviar_verificacion_email(request.user, request)
        request.session['verify_resend_at'] = now
        messages.success(request, _('Correo de verificación reenviado. Revisa bandeja y spam.'))
    except Exception:
        messages.error(
            request,
            _('No pudimos enviar el correo. Revisa la configuración SMTP o intenta más tarde.'),
        )
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
    return JsonResponse({
        'verified': verified,
        'redirect': reverse('tienda') if verified else '',
    })


def onboarding_solicitud_enviada(request):
    """Confirmación pública tras enviar solicitud de acceso."""
    return render(request, 'core/onboarding_solicitud_enviada.html', {
        'titulo_pagina': _('Solicitud recibida'),
    })
