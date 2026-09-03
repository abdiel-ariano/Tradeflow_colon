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
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
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
                    messages.error(request, _('The company is verified, but we could not activate the portal.'))
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
            name=(request.user.first_name or '').strip(),
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
        errors.append(_('Company name is required (minimum 2 characters).'))
    if not legal_name or len(legal_name) < 3:
        errors.append(_('Registered legal name is required.'))
    if not ruc:
        errors.append(_('RUC is required.'))
    elif not RUC_PATTERN.fullmatch(ruc):
        errors.append(_('RUC may only contain letters, numbers, periods, and hyphens.'))
    if not dv:
        errors.append(_('Verifier digit (DV) is required.'))
    elif not DV_PATTERN.fullmatch(dv):
        errors.append(_('DV may only contain letters, numbers, and hyphens.'))
    try:
        validate_email(business_email)
    except ValidationError:
        errors.append(_('Enter a valid business email address.'))
    if business_role not in BUSINESS_ROLES:
        errors.append(_('Select whether the company will buy, sell, or do both on TradeFlow.'))
    if not address:
        errors.append(_('Business address is required.'))
    existing_company = b2b_company_for_user(request.user)
    safe_document = _resolve_verification_document(
        verification_document,
        existing_company=existing_company,
    )
    if not _expo_demo_mode_active():
        if verification_document and not safe_document:
            errors.append(_('The document must be a valid PDF or image up to 8 MB.'))
        elif not safe_document and not (
            existing_company and existing_company.verification_document
        ):
            errors.append(
                _(
                    'Attach an operating notice, public registry certificate, or '
                    'equivalent document in PDF or image format.'
                )
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
            _(
                'We could not save your company due to a database error. '
                'If the problem continues, email support@tradeflowcolon.com.'
            ),
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
            _('An error occurred while registering the company. Review the details and try again.'),
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
            _('Demo mode: company verified instantly. You can continue with the B2B flow.'),
        )
    elif company.verification_status == 'verified':
        messages.success(
            request,
            _('Verified company linked successfully. No new review is required.'),
        )
    else:
        messages.success(
            request,
            _('We received your information. The company is pending manual review.'),
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
                _(
                    'This RUC is already verified and requires manual authorization to '
                    'link a new representative. Contact support@tradeflowcolon.com.'
                ),
            )
            return None
        if not authorized and not claimable:
            messages.error(
                request,
                _(
                    'This RUC is already linked to another account. '
                    'Contact support@tradeflowcolon.com.'
                ),
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
                    _(
                        'Legal details do not match the verified company. '
                        'Contact support@tradeflowcolon.com to update them.'
                    ),
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
        messages.info(request, _('Existing company linked to your account.'))
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
    messages.success(request, _('Company registered successfully.'))
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
            _('Demo mode: business verification completed automatically.'),
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


@login_required
@require_GET
def api_company_verification_status(request: HttpRequest) -> JsonResponse:
    """Read-only poll for the applicant company verification wait screen."""
    company = b2b_company_for_user(request.user)
    if company is None:
        return JsonResponse({'error': 'no_company'}, status=404)

    from core.utils.company_verification_status import company_verification_payload

    payload = company_verification_payload(request.user, company)
    response = JsonResponse(payload)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response
