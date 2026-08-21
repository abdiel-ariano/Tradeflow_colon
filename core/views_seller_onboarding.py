"""B2B company identity, documentary review and seller activation.

New business accounts register a Panamanian company after email OTP.
No account is described as verified until a staff reviewer approves the
submitted RUC/DV and supporting document. Seller capabilities activate only
after that decision; legacy seller accounts keep their compatibility path.
"""
from __future__ import annotations

import logging
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.models import Company, CompanyMembership, UserProfile
from core.utils.access_gating import b2b_company_for_user
from core.utils.seller_lifecycle import start_seller_trial

log = logging.getLogger('tradeflow.seller_onboarding')

# Basic syntax only. Government/business-registry confirmation remains manual.
RUC_PATTERN = re.compile(r'^[A-Z0-9Ñ.\-]{3,50}$', re.UNICODE)
DV_PATTERN = re.compile(r'^[A-Z0-9\-]{1,20}$', re.UNICODE)
BUSINESS_ROLES = {'buyer', 'seller', 'both'}


def _get_business_profile(user) -> UserProfile | None:
    """Return a new B2B profile or a compatible legacy seller profile."""
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if profile.business_role_intent not in BUSINESS_ROLES and profile.role != 'seller':
        return None
    return profile


def _form_context(
    *,
    name='',
    legal_name='',
    ruc='',
    dv='',
    business_email='',
    business_phone='',
    address='',
    business_role='both',
) -> dict:
    """Build template context for the company onboarding form."""
    return {
        'titulo_pagina': 'Verifica tu empresa',
        'form_name': name,
        'form_legal_name': legal_name,
        'form_ruc': ruc,
        'form_dv': dv,
        'form_business_email': business_email,
        'form_business_phone': business_phone,
        'form_address': address,
        'form_business_role': business_role if business_role in BUSINESS_ROLES else 'both',
    }


def _safe_verification_document(uploaded):
    """Validate a PDF/image used as manual company evidence."""
    if not uploaded:
        return None
    from core.utils.upload_security import UploadValidationError, validate_proof_upload

    try:
        return validate_proof_upload(uploaded, max_bytes=8 * 1024 * 1024)
    except UploadValidationError:
        return None


def _safe_logo_file(uploaded) -> object | None:
    """Return the upload only when it passes image security checks.

    Empty file inputs and storage-rejected payloads must not 500 the
    company registration step.
    """
    if not uploaded:
        return None
    from core.utils.upload_security import UploadValidationError, validate_image_upload

    try:
        return validate_image_upload(uploaded, max_bytes=5 * 1024 * 1024)
    except UploadValidationError:
        log.warning(
            'seller_onboarding_logo_rejected name=%s size=%s',
            getattr(uploaded, 'name', ''),
            getattr(uploaded, 'size', None),
        )
        return None


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
    """Show identity form, verification state or activate a verified seller."""
    profile = _get_business_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')

    existing = b2b_company_for_user(request.user)
    if existing:
        correcting_rejection = (
            existing.verification_status == 'rejected'
            and request.GET.get('corregir') == '1'
        )
        if existing.verification_status in ('pending', 'rejected') and not correcting_rejection:
            return redirect('company_verification_status')
        if existing.verification_status == 'verified':
            if existing.can_sell:
                try:
                    start_seller_trial(existing)
                except Exception as exc:
                    log.error(
                        'b2b_verified_company_activation_failed company_id=%s err=%s',
                        existing.pk,
                        exc,
                        exc_info=True,
                    )
                    messages.error(request, 'La empresa está verificada, pero no pudimos activar el portal.')
                    return redirect('company_verification_status')
                return redirect('portal_seller')
            return redirect('catalogo_publico')
        context = _form_context(
            name=existing.name,
            legal_name=existing.legal_name,
            ruc=existing.ruc,
            dv=existing.dv,
            business_email=existing.business_email or request.user.email,
            business_phone=existing.business_phone,
            address=existing.address_text,
            business_role=existing.business_role,
        )
        return render(request, 'core/seller_onboarding_company.html', context)

    return render(
        request,
        'core/seller_onboarding_company.html',
        _form_context(
            business_email=request.user.email,
            business_role=profile.business_role_intent or 'both',
        ),
    )


@login_required
@require_POST
def seller_onboarding_company_post(request: HttpRequest) -> HttpResponse:
    """Register company identity and submit it for a human review."""
    profile = _get_business_profile(request.user)
    if not profile:
        return redirect('catalogo_publico')

    name = (request.POST.get('name') or '').strip()
    legal_name = (request.POST.get('legal_name') or '').strip()
    ruc = Company.normalize_identifier(request.POST.get('ruc'))
    dv = Company.normalize_identifier(request.POST.get('dv'))
    business_email = (request.POST.get('business_email') or '').strip()
    business_phone = (request.POST.get('business_phone') or '').strip()
    business_role = (request.POST.get('business_role') or profile.business_role_intent or '').strip()
    address = (request.POST.get('address_text') or '').strip()
    logo = request.FILES.get('logo')
    verification_document = request.FILES.get('verification_document')

    errors = []
    if not name or len(name) < 2:
        errors.append('El nombre de la empresa es obligatorio (mínimo 2 caracteres).')
    if not legal_name or len(legal_name) < 3:
        errors.append('La razón social registrada es obligatoria.')
    if not ruc:
        errors.append('El RUC es obligatorio.')
    elif not RUC_PATTERN.fullmatch(ruc):
        errors.append('El RUC solo puede contener letras, números, puntos y guiones.')
    if not dv:
        errors.append('El dígito verificador (DV) es obligatorio.')
    elif not DV_PATTERN.fullmatch(dv):
        errors.append('El DV solo puede contener letras, números y guiones.')
    try:
        validate_email(business_email)
    except ValidationError:
        errors.append('Ingresa un correo empresarial válido.')
    if business_role not in BUSINESS_ROLES:
        errors.append('Selecciona si la empresa comprará, venderá o realizará ambas actividades.')
    if not address:
        errors.append('La dirección comercial es obligatoria.')
    safe_document = _safe_verification_document(verification_document)
    existing_company = b2b_company_for_user(request.user)
    if verification_document and not safe_document:
        errors.append('El documento debe ser un PDF o una imagen válida de máximo 8 MB.')
    elif not safe_document and not (
        existing_company and existing_company.verification_document
    ):
        errors.append('Adjunta un aviso de operación, registro público o documento equivalente en PDF o imagen.')

    if errors:
        for msg in errors:
            messages.error(request, msg)
        return render(
            request,
            'core/seller_onboarding_company.html',
            _form_context(
                name=name,
                legal_name=legal_name,
                ruc=ruc,
                dv=dv,
                business_email=business_email,
                business_phone=business_phone,
                address=address,
                business_role=business_role,
            ),
        )

    try:
        company = _resolve_or_create_company(
            user=request.user,
            name=name,
            legal_name=legal_name,
            ruc=ruc,
            dv=dv,
            business_email=business_email,
            business_phone=business_phone,
            business_role=business_role,
            address=address,
            verification_document=safe_document,
            logo=logo,
            request=request,
        )
        if company is None:
            # Business error already messaged (RUC owned by another user).
            return render(
                request,
                'core/seller_onboarding_company.html',
                _form_context(
                    name=name, legal_name=legal_name, ruc=ruc, dv=dv,
                    business_email=business_email, business_phone=business_phone,
                    address=address, business_role=business_role,
                ),
            )
        company.submit_for_verification()
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
            _form_context(
                name=name, legal_name=legal_name, ruc=ruc, dv=dv,
                business_email=business_email, business_phone=business_phone,
                address=address, business_role=business_role,
            ),
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
            'Ocurrió un error al registrar la empresa. '
            'Revisa los datos e inténtalo de nuevo.',
        )
        return render(
            request,
            'core/seller_onboarding_company.html',
            _form_context(
                name=name, legal_name=legal_name, ruc=ruc, dv=dv,
                business_email=business_email, business_phone=business_phone,
                address=address, business_role=business_role,
            ),
        )

    messages.success(
        request,
        'Recibimos la información. La empresa quedó pendiente de revisión manual.',
    )
    log.info(
        'seller_onboarding_completed user_id=%s company_id=%s',
        request.user.pk,
        company.pk,
    )
    return redirect('company_verification_status')


def _resolve_or_create_company(
    *,
    user,
    name: str,
    legal_name: str,
    ruc: str,
    dv: str,
    business_email: str,
    business_phone: str,
    business_role: str,
    address: str,
    verification_document,
    logo,
    request,
) -> Company | None:
    """Link an authorized RUC company or create a draft B2B company.

    Returns None when the RUC already belongs to another owner (message
    already attached to ``request``).
    """
    existing = Company.objects.filter(ruc__iexact=ruc).first()
    if existing:
        authorized = (
            existing.owner_id == user.pk
            or CompanyMembership.objects.filter(company=existing, user=user).exists()
            or (existing.owner_id is None and not existing.memberships.exists())
        )
        if not authorized:
            messages.error(
                request,
                'Este RUC ya está vinculado a otra cuenta. '
                'Contacta a soporte@tradeflowcolon.com.',
            )
            return None
        existing.name = name
        existing.legal_name = legal_name
        existing.dv = dv
        existing.business_email = business_email
        existing.business_phone = business_phone
        existing.business_role = business_role
        existing.address_text = address
        existing.owner = user
        existing.verification_status = 'draft'
        if verification_document:
            existing.verification_document = verification_document
        existing.save()
        CompanyMembership.objects.get_or_create(
            company=existing,
            user=user,
            defaults={'role': 'owner', 'status': 'active'},
        )
        _attach_logo(existing, logo)
        messages.info(request, 'Empresa existente vinculada a tu cuenta.')
        return existing

    company = Company.objects.create(
        name=name,
        legal_name=legal_name,
        ruc=ruc,
        dv=dv,
        business_email=business_email,
        business_phone=business_phone,
        business_role=business_role,
        address_text=address,
        owner=user,
        verification_document=verification_document,
        verification_status='draft',
    )
    CompanyMembership.objects.create(
        company=company,
        user=user,
        role='owner',
        status='active',
    )
    _attach_logo(company, logo)
    messages.success(request, 'Empresa registrada correctamente.')
    return company


@login_required
@require_GET
def company_verification_status(request: HttpRequest) -> HttpResponse:
    """Show the auditable company review state and activate verified sellers."""
    company = b2b_company_for_user(request.user)
    if company is None:
        return redirect('company_onboarding')

    activation_error = False
    if company.verification_status == 'verified' and company.can_sell:
        try:
            start_seller_trial(company)
        except Exception as exc:
            activation_error = True
            log.error(
                'b2b_verified_company_activation_failed company_id=%s err=%s',
                company.pk,
                exc,
                exc_info=True,
            )

    return render(request, 'core/company_verification_status.html', {
        'company': company,
        'activation_error': activation_error,
    })
