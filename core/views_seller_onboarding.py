"""B2B company identity, documentary review and seller activation.

New business accounts register a Panamanian company after email OTP.
No account is described as verified until a staff reviewer approves the
submitted RUC/DV and supporting document. Seller capabilities activate only
after that decision; legacy seller accounts keep their compatibility path.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Company, CompanyMembership, UserProfile
from core.utils.access_gating import b2b_company_for_user
from core.utils.seller_lifecycle import start_seller_trial

log = logging.getLogger('tradeflow.seller_onboarding')

# Basic syntax only. Government/business-registry confirmation remains manual.
RUC_PATTERN = re.compile(r'^[A-Z0-9Ñ.\-]{3,50}$', re.UNICODE)
DV_PATTERN = re.compile(r'^[A-Z0-9\-]{1,20}$', re.UNICODE)
BUSINESS_ROLES = {'buyer', 'seller', 'both'}
_DEMO_VERIFICATION_PDF = b'%PDF-1.4\n% TradeFlow demo company verification stub\n'


def _expo_demo_mode_active() -> bool:
    """Return True when Expo/demo bypasses are enabled via environment."""
    return getattr(settings, 'EXPO_DEMO_MODE', False)


def _demo_verification_document():
    """Minimal PDF accepted by upload security for demo walkthroughs."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        'demo-aviso-operacion.pdf',
        _DEMO_VERIFICATION_PDF,
        content_type='application/pdf',
    )


def _business_role_for_profile(profile: UserProfile) -> str:
    """Return explicit B2B intent, falling back to the legacy marketplace role."""
    if profile.business_role_intent in BUSINESS_ROLES:
        return profile.business_role_intent
    if profile.role in ('buyer', 'seller'):
        return profile.role
    return ''


def _get_business_profile(user) -> UserProfile | None:
    """Return a B2B profile, including compatible legacy buyers and sellers."""
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    if not _business_role_for_profile(profile):
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
        'expo_demo_mode': _expo_demo_mode_active(),
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


def _resolve_verification_document(
    uploaded,
    *,
    existing_company: Company | None,
) -> object | None:
    """Return a safe upload, reuse existing evidence, or a demo stub."""
    safe_document = _safe_verification_document(uploaded)
    if safe_document:
        return safe_document
    if existing_company and existing_company.verification_document:
        return None
    if _expo_demo_mode_active():
        if uploaded:
            log.info(
                'expo_demo_company_doc_replaced invalid_upload=%s',
                getattr(uploaded, 'name', ''),
            )
        return _demo_verification_document()
    return None


def _finalize_company_verification(company: Company, user) -> None:
    """Submit for manual review, or auto-verify instantly in Expo demo mode."""
    if company.verification_status == 'verified':
        return
    if _expo_demo_mode_active():
        if not company.verification_document:
            company.verification_document = _demo_verification_document()
            company.save(update_fields=['verification_document'])
        company.mark_verified(user)
        if company.can_sell:
            try:
                start_seller_trial(company)
            except Exception as exc:
                log.warning(
                    'expo_demo_seller_trial_failed company_id=%s err=%s',
                    company.pk,
                    exc,
                    exc_info=True,
                )
        log.info('expo_demo_company_verified company_id=%s user_id=%s', company.pk, user.pk)
        return
    company.submit_for_verification()


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
            business_role=_business_role_for_profile(profile) or 'both',
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
    business_role = (request.POST.get('business_role') or _business_role_for_profile(profile)).strip()
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
    existing_company = b2b_company_for_user(request.user)
    safe_document = _resolve_verification_document(
        verification_document,
        existing_company=existing_company,
    )
    if not _expo_demo_mode_active():
        if verification_document and not safe_document:
            errors.append('El documento debe ser un PDF o una imagen válida de máximo 8 MB.')
        elif not safe_document and not (
            existing_company and existing_company.verification_document
        ):
            errors.append(
                'Adjunta un aviso de operación, registro público o documento '
                'equivalente en PDF o imagen.'
            )

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
        auto_verified_demo = (
            _expo_demo_mode_active() and company.verification_status != 'verified'
        )
        _finalize_company_verification(company, request.user)

        profile.business_role_intent = business_role
        profile_updates = ['business_role_intent']
        if profile.onboarding_completed_at is None:
            profile.onboarding_completed_at = timezone.now()
            profile_updates.append('onboarding_completed_at')
        profile.save(update_fields=profile_updates)
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

    if auto_verified_demo and company.verification_status == 'verified':
        messages.success(
            request,
            'Modo demo: empresa verificada al instante. Ya puedes continuar con el flujo B2B.',
        )
    elif company.verification_status == 'verified':
        messages.success(
            request,
            'Empresa verificada vinculada correctamente. No requiere una nueva revisión.',
        )
    else:
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
        has_membership = CompanyMembership.objects.filter(
            company=existing,
            user=user,
        ).exists()
        authorized = existing.owner_id == user.pk or has_membership
        claimable = existing.owner_id is None and not existing.memberships.exists()

        if existing.verification_status == 'verified' and not authorized:
            messages.error(
                request,
                'Este RUC ya está verificado y requiere autorización manual para '
                'vincular un nuevo representante. Contacta a soporte@tradeflowcolon.com.',
            )
            return None
        if not authorized and not claimable:
            messages.error(
                request,
                'Este RUC ya está vinculado a otra cuenta. '
                'Contacta a soporte@tradeflowcolon.com.',
            )
            return None

        if existing.verification_status == 'verified':
            identity_changed = (
                Company.normalize_identifier(existing.dv) != dv
                or (existing.legal_name or '').strip().casefold()
                != legal_name.strip().casefold()
            )
            if identity_changed:
                messages.error(
                    request,
                    'Los datos legales no coinciden con la empresa verificada. '
                    'Contacta a soporte@tradeflowcolon.com para actualizarlos.',
                )
                return None
            existing.business_email = business_email
            existing.business_phone = business_phone
            existing.business_role = business_role
            existing.address_text = address
            if existing.owner_id is None:
                existing.owner = user
            existing.save(update_fields=[
                'business_email',
                'business_phone',
                'business_role',
                'address_text',
                'owner',
            ])
        else:
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

    if (
        _expo_demo_mode_active()
        and company.verification_status in ('draft', 'pending', 'rejected')
    ):
        _finalize_company_verification(company, request.user)
        company.refresh_from_db()
        messages.info(
            request,
            'Modo demo: verificación empresarial completada automáticamente.',
        )

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
