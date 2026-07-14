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

NOTAS DE PRODUCCIÓN
-------------------
- El logo es opcional: fallos de Storage (Supabase) NO deben tumbar el registro.
- Toda excepción no esperada se captura, se registra con ``exc_info`` y se
  muestra un mensaje amigable (evita Server Error 500 opaco en el formulario).
=============================================================================
"""
from __future__ import annotations

import logging
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.models import Company, UserProfile
from core.utils.access_gating import seller_company_pending
from core.utils.seller_lifecycle import start_seller_trial

log = logging.getLogger('tradeflow.seller_onboarding')

# RUC / registro: letras, números, guiones, puntos y slash (formatos ZLC comunes).
RUC_PATTERN = re.compile(r'^[\w\-./]{5,50}$', re.UNICODE)


def _get_seller_profile(user) -> UserProfile | None:
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.role != 'seller':
        return None
    return profile


def _form_context(*, name='', ruc='', address='') -> dict:
    return {
        'titulo_pagina': 'Configura tu empresa',
        'form_name': name,
        'form_ruc': ruc,
        'form_address': address,
    }


def _safe_logo_file(uploaded) -> object | None:
    """
    Devuelve el archivo solo si es un upload usable.

    Evita 500 cuando el navegador envía un ``<input type="file">`` vacío o
    cuando el backend de Storage no puede aceptar el archivo.
    """
    if not uploaded:
        return None
    size = getattr(uploaded, 'size', None)
    if size is None or size <= 0:
        return None
    name = (getattr(uploaded, 'name', '') or '').strip()
    if not name:
        return None
    return uploaded


def _attach_logo(company: Company, logo) -> None:
    """Adjunta logo sin abortar el alta de empresa si el storage falla."""
    logo = _safe_logo_file(logo)
    if not logo:
        return
    try:
        company.logo = logo
        company.save(update_fields=['logo'])
    except Exception as exc:
        log.warning(
            'seller_onboarding_logo_failed company_id=%s err=%s',
            company.pk,
            exc,
            exc_info=True,
        )


@login_required
@require_GET
def seller_onboarding_company(request: HttpRequest) -> HttpResponse:
    """
    Paso único — datos de empresa y activación del trial Digitalízate.

    GET: muestra formulario. Si ya hay empresa propia sin suscripción (POST
    parcial fallido), arranca el trial automáticamente y entra al portal.
    """
    profile = _get_seller_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')

    if not seller_company_pending(request.user):
        return redirect('portal_seller')

    # Recuperación: empresa creada pero trial no persistido (500 intermedio).
    existing = Company.objects.filter(owner=request.user).first()
    if existing:
        from core.enterprise_models import CompanySubscription

        try:
            _ = existing.subscription
        except CompanySubscription.DoesNotExist:
            try:
                start_seller_trial(existing)
                messages.success(
                    request,
                    '¡Bienvenido! Tienes 30 días de prueba gratis en el plan Digitalízate.',
                )
                return redirect('portal_seller')
            except Exception as exc:
                log.error(
                    'seller_onboarding_resume_trial_failed user_id=%s company_id=%s err=%s',
                    request.user.pk,
                    existing.pk,
                    exc,
                    exc_info=True,
                )
                messages.error(
                    request,
                    'Tu empresa está registrada pero no pudimos activar el trial. '
                    'Reinténtalo o contacta soporte.',
                )
                return render(
                    request,
                    'core/seller_onboarding_company.html',
                    _form_context(
                        name=existing.name,
                        ruc=existing.ruc,
                        address=existing.address_text,
                    ),
                )

    return render(request, 'core/seller_onboarding_company.html', _form_context())


@login_required
@require_POST
def seller_onboarding_company_post(request: HttpRequest) -> HttpResponse:
    """
    Procesa el formulario de empresa y arranca el trial de 30 días.

    Nunca debe devolver 500 por errores de negocio o storage: captura, loguea
    y re-renderiza el formulario con mensaje claro.
    """
    profile = _get_seller_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')
    if not seller_company_pending(request.user):
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
        errors.append(
            'Formato de RUC no válido. Usa letras, números, guiones o puntos '
            '(mínimo 5 caracteres).'
        )
    if not address:
        errors.append('La dirección en la ZLC es obligatoria.')

    if errors:
        for msg in errors:
            messages.error(request, msg)
        return render(
            request,
            'core/seller_onboarding_company.html',
            _form_context(name=name, ruc=ruc, address=address),
        )

    try:
        company = _resolve_or_create_company(
            user=request.user,
            name=name,
            ruc=ruc,
            address=address,
            logo=logo,
            request=request,
        )
        if company is None:
            # Error de negocio ya comunicado (RUC con otro owner).
            return render(
                request,
                'core/seller_onboarding_company.html',
                _form_context(name=name, ruc=ruc, address=address),
            )

        start_seller_trial(company)
    except (IntegrityError, DatabaseError) as exc:
        log.error(
            'seller_onboarding_db_error user_id=%s ruc=%s err=%s',
            request.user.pk,
            ruc,
            exc,
            exc_info=True,
        )
        messages.error(
            request,
            'No pudimos guardar tu empresa por un error de base de datos. '
            'Si el problema continúa, escribe a soporte@tradeflowcolon.com.',
        )
        return render(
            request,
            'core/seller_onboarding_company.html',
            _form_context(name=name, ruc=ruc, address=address),
        )
    except Exception as exc:
        log.error(
            'seller_onboarding_unexpected user_id=%s ruc=%s err=%s',
            request.user.pk,
            ruc,
            exc,
            exc_info=True,
        )
        messages.error(
            request,
            'Ocurrió un error al activar tu cuenta seller. '
            'Revisa los datos e inténtalo de nuevo.',
        )
        return render(
            request,
            'core/seller_onboarding_company.html',
            _form_context(name=name, ruc=ruc, address=address),
        )

    messages.success(
        request,
        '¡Bienvenido! Tienes 30 días de prueba gratis en el plan Digitalízate.',
    )
    log.info(
        'seller_onboarding_completed user_id=%s company_id=%s',
        request.user.pk,
        company.pk,
    )
    return redirect('portal_seller')


def _resolve_or_create_company(
    *,
    user,
    name: str,
    ruc: str,
    address: str,
    logo,
    request,
) -> Company | None:
    """
    Vincula o crea la empresa según RUC.

    Returns:
        Company o None si el RUC ya pertenece a otro usuario (mensaje en request).
    """
    existing = Company.objects.filter(ruc__iexact=ruc).first()
    if existing:
        if existing.owner_id and existing.owner_id != user.pk:
            messages.error(
                request,
                'Este RUC ya está vinculado a otra cuenta. '
                'Contacta a soporte@tradeflowcolon.com.',
            )
            return None
        existing.name = name
        existing.address_text = address
        existing.owner = user
        existing.save(update_fields=['name', 'address_text', 'owner'])
        _attach_logo(existing, logo)
        messages.info(request, 'Empresa existente vinculada a tu cuenta.')
        return existing

    company = Company.objects.create(
        name=name,
        ruc=ruc,
        address_text=address,
        owner=user,
        is_verified=False,
    )
    _attach_logo(company, logo)
    messages.success(request, 'Empresa registrada correctamente.')
    return company
