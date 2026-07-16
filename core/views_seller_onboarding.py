"""Seller company onboarding and Digitalízate trial activation.

After signup and OTP, sellers without a ``Company.owner`` link must
register CFZ company details (name, RUC, address, optional logo), then
``start_seller_trial`` unlocks the seller portal (``/mi-tienda/``).

Unlike buyer onboarding, this wizard cannot be skipped.
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

# RUC / registry: letters, digits, hyphens, dots, slash (common CFZ forms).
RUC_PATTERN = re.compile(r'^[\w\-./]{5,50}$', re.UNICODE)


def _get_seller_profile(user) -> UserProfile | None:
    """Return the seller profile, or None for non-sellers."""
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.role != 'seller':
        return None
    return profile


def _form_context(*, name='', ruc='', address='') -> dict:
    """Build template context for the company onboarding form."""
    return {
        'titulo_pagina': 'Configura tu empresa',
        'form_name': name,
        'form_ruc': ruc,
        'form_address': address,
    }


def _safe_logo_file(uploaded) -> object | None:
    """Return the upload only when it has a usable name and size.

    Empty file inputs and storage-rejected payloads must not 500 the
    company registration step.
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
    """Attach a logo without failing company creation on storage errors."""
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
    """Show company form or resume a stuck trial into the seller portal.

    If the company exists but subscription/trial never persisted, start
    the trial and redirect to ``portal_seller``.
    """
    profile = _get_seller_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')

    if not seller_company_pending(request.user):
        return redirect('portal_seller')

    # Recovery: company created but trial not persisted (partial failure).
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
    """Validate company fields, link or create by RUC, start the trial.

    Business and storage errors re-render the form with messages instead
    of returning a bare 500.
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
            # Business error already messaged (RUC owned by another user).
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
    """Link an orphan RUC company or create a new unverified Company.

    Returns None when the RUC already belongs to another owner (message
    already attached to ``request``).
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
