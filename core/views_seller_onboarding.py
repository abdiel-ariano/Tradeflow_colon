"""
=============================================================================
TRADEFLOW COLÓN — core/views_seller_onboarding.py
=============================================================================
Wizard de onboarding vendedor: vinculación de empresa y inicio del trial.

FLUJO
-----
1. Seller completa signup + verificación OTP.
2. Redirigido aquí si no tiene ``Company.owner``.
3. Formulario: nombre, RUC, dirección, logo opcional.
4. Lógica RUC:
   - Empresa existente sin owner → asignar ``owner=request.user``.
   - Empresa con otro owner → error (contactar soporte).
   - RUC nuevo → ``Company.objects.create(owner=user, is_verified=False)``.
5. ``start_seller_trial(company)`` → redirect a ``portal_seller``.

El wizard es obligatorio; no hay ruta de omitir (a diferencia del buyer).
=============================================================================
"""
from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.models import Company, UserProfile
from core.utils.access_gating import seller_company_pending
from core.utils.seller_lifecycle import start_seller_trial

RUC_MIN_LEN = 5
RUC_MAX_LEN = 50
RUC_PATTERN = re.compile(r'^[\w\-\.]{5,50}$')


def _get_seller_profile(user) -> UserProfile | None:
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.role != 'seller':
        return None
    return profile


@login_required
@require_GET
def seller_onboarding_company(request: HttpRequest) -> HttpResponse:
    """
    Paso único — datos de empresa y activación del trial Digitalízate.

    GET: muestra formulario. POST: ver ``seller_onboarding_company_post``.
    """
    profile = _get_seller_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')

    if not seller_company_pending(request.user):
        return redirect('portal_seller')

    return render(request, 'core/seller_onboarding_company.html', {
        'titulo_pagina': 'Configura tu empresa',
        'form_name': '',
        'form_ruc': '',
        'form_address': '',
    })


@login_required
@require_POST
def seller_onboarding_company_post(request: HttpRequest) -> HttpResponse:
    """Procesa el formulario de empresa y arranca el trial de 30 días."""
    profile = _get_seller_profile(request.user)
    if not profile or not seller_company_pending(request.user):
        return redirect('portal_seller')

    name = (request.POST.get('name') or '').strip()
    ruc = (request.POST.get('ruc') or '').strip()
    address = (request.POST.get('address_text') or '').strip()
    logo = request.FILES.get('logo')

    errors = []
    if not name or len(name) < 2:
        errors.append('El nombre de la empresa es obligatorio (mínimo 2 caracteres).')
    if not ruc:
        errors.append('El RUC o registro mercantil es obligatorio.')
    elif not RUC_PATTERN.match(ruc):
        errors.append('Formato de RUC no válido.')
    if not address:
        errors.append('La dirección en la ZLC es obligatoria.')

    if errors:
        for msg in errors:
            messages.error(request, msg)
        return render(request, 'core/seller_onboarding_company.html', {
            'titulo_pagina': 'Configura tu empresa',
            'form_name': name,
            'form_ruc': ruc,
            'form_address': address,
        })

    existing = Company.objects.filter(ruc__iexact=ruc).first()
    if existing:
        if existing.owner_id and existing.owner_id != request.user.pk:
            messages.error(
                request,
                'Este RUC ya está vinculado a otra cuenta. Contacta a soporte@tradeflowcolon.com.',
            )
            return render(request, 'core/seller_onboarding_company.html', {
                'titulo_pagina': 'Configura tu empresa',
                'form_name': name,
                'form_ruc': ruc,
                'form_address': address,
            })
        existing.name = name
        existing.address_text = address
        existing.owner = request.user
        if logo:
            existing.logo = logo
        existing.save()
        company = existing
        messages.info(request, 'Empresa existente vinculada a tu cuenta.')
    else:
        company = Company.objects.create(
            name=name,
            ruc=ruc,
            address_text=address,
            owner=request.user,
            is_verified=False,
        )
        if logo:
            company.logo = logo
            company.save(update_fields=['logo'])
        messages.success(request, 'Empresa registrada correctamente.')

    start_seller_trial(company)
    messages.success(
        request,
        '¡Bienvenido! Tienes 30 días de prueba gratis en el plan Digitalízate.',
    )
    return redirect('portal_seller')
