"""Read-only helpers for company verification status APIs and UI."""
from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from core.utils.access_gating import application_gate_status, b2b_company_for_user


RECENT_SUBMISSION_WINDOW = timedelta(hours=24)


def pending_companies_count() -> int:
    from core.models import Company

    return Company.objects.filter(verification_status='pending').count()


def is_recent_submission(submitted_at) -> bool:
    """True when submitted or resubmitted within the last 24 hours."""
    if not submitted_at:
        return False
    return submitted_at >= timezone.now() - RECENT_SUBMISSION_WINDOW


def authorized_continue_url(user, company) -> str:
    """Return the next safe destination after company verification."""
    gate = application_gate_status(
        user.email or '',
        role=getattr(getattr(user, 'profile', None), 'role', None),
    )
    if gate in ('pending', 'under_review'):
        return reverse('onboarding_espera_aprobacion')
    if gate == 'required':
        return reverse('onboarding_solicitud_requerida')
    if gate == 'rejected':
        return reverse('onboarding_aplicacion_rechazada')

    if company.verification_status != 'verified':
        return reverse('company_verification_status')

    if company.can_sell:
        from core.enterprise_models import CompanySubscription

        try:
            company.subscription
        except CompanySubscription.DoesNotExist:
            return reverse('company_onboarding')
        return reverse('portal_seller')

    return reverse('catalogo_publico')


def applicant_access_block(user) -> dict | None:
    """Describe non-company gates that still block full marketplace access."""
    try:
        role = user.profile.role
    except Exception:
        role = None
    gate = application_gate_status(user.email or '', role=role)
    if gate in ('pending', 'under_review'):
        return {
            'code': 'application_pending',
            'message': (
                'Tu empresa fue verificada, pero tu solicitud de acceso al '
                'marketplace sigue en revisión.'
            ),
            'continue_url': reverse('onboarding_espera_aprobacion'),
        }
    if gate == 'required':
        return {
            'code': 'application_required',
            'message': (
                'Tu empresa fue verificada. Completa la solicitud de acceso '
                'empresarial para continuar.'
            ),
            'continue_url': reverse('onboarding_solicitud_requerida'),
        }
    if gate == 'rejected':
        return {
            'code': 'application_rejected',
            'message': (
                'Tu empresa fue verificada, pero la solicitud de acceso no fue '
                'aprobada. Contacta a soporte si crees que es un error.'
            ),
            'continue_url': reverse('onboarding_aplicacion_rechazada'),
        }
    return None


def company_verification_payload(user, company) -> dict:
    """Serialize company verification state for applicant polling."""
    status = company.verification_status
    payload = {
        'company_id': company.pk,
        'verification_status': status,
        'submitted_at': (
            company.verification_submitted_at.isoformat()
            if company.verification_submitted_at
            else None
        ),
        'verified_at': (
            company.verified_at.isoformat() if company.verified_at else None
        ),
        'is_recent_submission': is_recent_submission(
            company.verification_submitted_at,
        ),
        'continue_url': '',
        'access_block': None,
        'rejection_message': '',
        'poll_active': status in ('draft', 'pending'),
    }

    if status == 'verified':
        block = applicant_access_block(user)
        if block:
            payload['access_block'] = block
            payload['continue_url'] = block['continue_url']
            payload['poll_active'] = False
        else:
            payload['continue_url'] = authorized_continue_url(user, company)
            payload['poll_active'] = False
    elif status == 'rejected':
        payload['rejection_message'] = (
            'La información enviada requiere corrección. '
            'Actualiza los datos o documentos y vuelve a enviar la empresa.'
        )
        payload['continue_url'] = reverse('company_onboarding') + '?corregir=1'
        payload['poll_active'] = False
    elif status == 'pending':
        payload['poll_active'] = True

    return payload


def assert_company_owned_by_user(user, company) -> bool:
    """True when the user may read this company's verification status."""
    owned = b2b_company_for_user(user)
    return owned is not None and owned.pk == company.pk
