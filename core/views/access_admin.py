"""Solicitudes de acceso, revisión de aplicaciones y panel SaaS admin."""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import base64
import html as html_module
import io
import json
import logging
import re
import unicodedata
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import cache_control, never_cache

import qrcode
from django.core import signing

from ..decorators import admin_required, buyer_checkout, buyer_required, catalog_access, guest_or_buyer_cart, seller_required
from ..forms import SellerProductForm, SellerInventoryForm
from ..email_service import enviar_codigo_verificacion as enviar_codigo_email
from ..models import (
    UserProfile, Company, Category, Product, Inventory,
    Address, Order, OrderItem, Payment, Shipment, Document,
    Cotizacion, CotizacionItem, TransportCarrier, UserApplication,
    EmailVerification,
)
from ..utils.email_sender import (
    enviar_bienvenida,
    enviar_cambio_estado,
    enviar_confirmacion_orden,
    enviar_orden_pendiente_vendedor,
    enviar_solicitud_recibida,
    enviar_solicitud_a_revisores,
    enviar_solicitud_decision,
)
from ..utils.saas_billing import VolumeLimitExceeded, is_volume_limit_reached
from ..utils.saas_demo import user_is_read_only_saas_demo
from ..utils.media_storage import product_image_url
from ..utils.order_workflow import (
    accept_seller_order,
    reject_seller_order,
    seller_confirm_deadline,
    expire_pending_orders,
)
from ..utils.pdf_generator import (
    generar_cotizacion_pdf,
    generar_factura_pdf,
    generar_packing_list_pdf,
)

from .common import log
from .seller_store import _get_seller_company

def solicitud_acceso(request):
    """Public business access application for the marketplace."""
    plan_intent = (request.GET.get('plan') or request.POST.get('requested_plan_slug') or '').strip().lower()
    if plan_intent in ('enterprise', 'ecosistema_enterprise'):
        plan_intent = 'ecosistema_enterprise'
    else:
        plan_intent = plan_intent[:40]

    form_defaults = {
        'form_full_name': '',
        'form_email': '',
        'form_phone': '',
        'form_company_name': '',
        'form_ruc': '',
        'form_message': '',
        'form_role': 'seller' if plan_intent == 'ecosistema_enterprise' else 'buyer',
    }
    if request.user.is_authenticated:
        full = (request.user.get_full_name() or '').strip()
        form_defaults['form_full_name'] = full or request.user.username
        form_defaults['form_email'] = (request.user.email or '').strip()

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        # Compat: plantillas antiguas usaban corporate_email
        email = (
            request.POST.get('email', '')
            or request.POST.get('corporate_email', '')
        ).strip().lower()
        phone = request.POST.get('phone', '').strip()
        role = (request.POST.get('role') or 'buyer').strip()
        company_name = request.POST.get('company_name', '').strip()
        message = request.POST.get('message', '').strip()
        ruc = request.POST.get('ruc', '').strip()
        req_plan = (request.POST.get('requested_plan_slug', '') or plan_intent).strip()
        if req_plan in ('enterprise', 'ecosistema_enterprise'):
            req_plan = 'ecosistema_enterprise'

        form_defaults.update({
            'form_full_name': full_name,
            'form_email': email,
            'form_phone': phone,
            'form_company_name': company_name,
            'form_ruc': ruc,
            'form_message': message,
            'form_role': role if role in ('buyer', 'seller') else form_defaults['form_role'],
        })

        if not full_name or not email:
            messages.error(request, _('Name and email are required.'))
        elif not company_name:
            messages.error(request, _('Company name is required.'))
        elif not phone:
            messages.error(request, _('Phone is required.'))
        elif not ruc:
            messages.error(request, _('RUC is required.'))
        elif role not in ('buyer', 'seller'):
            messages.error(request, _('Invalid role.'))
        else:
            existing = UserApplication.objects.filter(
                email__iexact=email,
                status='pending',
            ).first()
            if existing:
                messages.info(
                    request,
                    _(
                        'You already have an application under review. '
                        'We will email you when it is approved.'
                    ),
                )
                if request.user.is_authenticated:
                    return redirect('onboarding_espera_aprobacion')
                return redirect(
                    f'{reverse("solicitud_acceso")}?plan=enterprise'
                    if req_plan == 'ecosistema_enterprise'
                    else 'solicitud_acceso'
                )

            if ruc:
                ruc_line = f'RUC: {ruc}'
                message = f'{ruc_line}\n{message}'.strip() if message else ruc_line

            app = UserApplication.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=full_name,
                email=email,
                phone=phone,
                role=role,
                company_name=company_name,
                message=message,
                requested_plan_slug=req_plan[:40],
            )
            company_owner = _get_seller_company(request.user) if request.user.is_authenticated else None
            if req_plan == 'ecosistema_enterprise' and company_owner:
                from ..utils.saas_billing import create_enterprise_commercial_request

                try:
                    create_enterprise_commercial_request(
                        company_owner,
                        contact_name=full_name,
                        contact_email=email,
                        message=message,
                        user_application=app,
                    )
                except Exception:
                    log.exception('enterprise_commercial_request_failed app_id=%s', app.pk)

            try:
                enviar_solicitud_recibida(app)
                enviar_solicitud_a_revisores(app)
            except Exception:
                log.exception('Email solicitud acceso')
                messages.warning(
                    request,
                    _(
                        'Application saved, but email could not be sent. '
                        'Configure RESEND_API_KEY and verify sender domain in Resend.'
                    ),
                )
            else:
                messages.success(
                    request,
                    _('Application submitted. Check your email for confirmation.'),
                )
            if request.user.is_authenticated:
                return redirect('onboarding_espera_aprobacion')
            return redirect('onboarding_solicitud_enviada')

    return render(request, 'core/solicitud_acceso.html', {
        'titulo_pagina': _('Enterprise application') if plan_intent == 'ecosistema_enterprise' else _('Access application'),
        'plan_intent': plan_intent,
        'is_enterprise_intent': plan_intent == 'ecosistema_enterprise',
        **form_defaults,
    })


@login_required
@admin_required
def revisar_solicitud(request, token, accion):
    """Approve or reject an access application (staff + token; POST confirm)."""
    app = get_object_or_404(UserApplication, review_token=token)
    if app.status not in ('pending',):
        messages.info(request, _('This application has already been reviewed.'))
        return redirect('home')

    if accion == 'aprobar':
        aprobada = True
    elif accion == 'rechazar':
        aprobada = False
    else:
        raise Http404

    # GET shows a confirmation screen so emailed links cannot mutate via prefetch.
    if request.method != 'POST':
        return render(request, 'core/revisar_solicitud_confirm.html', {
            'app': app,
            'accion': accion,
            'aprobada': aprobada,
            'titulo_pagina': _('Review application'),
        })

    if aprobada and app.requested_plan_slug == 'ecosistema_enterprise':
        from ..models import Company
        from ..utils.saas_billing import approve_commercial_request

        company = Company.objects.filter(owner__email__iexact=app.email).first()
        if company:
            pending = company.plan_commercial_requests.filter(
                status__in=('pending', 'en_revision'),
                requested_plan__slug='ecosistema_enterprise',
            ).order_by('-created_at').first()
            if pending:
                approve_commercial_request(pending)
            else:
                from ..utils.saas_billing import activate_company_plan

                try:
                    activate_company_plan(
                        company,
                        'ecosistema_enterprise',
                        source='commercial',
                        notes=f'user_application:{app.pk}',
                    )
                except ValueError:
                    log.exception('Enterprise activation on approve')

    from ..utils.application_review import (
        aprobar_solicitud,
        mensaje_fallo_correo,
        rechazar_solicitud,
    )
    if aprobada:
        _app_result, email_result = aprobar_solicitud(app, notificar=True)
    else:
        _app_result, email_result = rechazar_solicitud(app, notificar=True)

    warn = mensaje_fallo_correo(email_result)
    if warn:
        messages.warning(request, warn)
    else:
        messages.success(request, _('Decision recorded and email sent to the applicant.'))
    return redirect('home')


@admin_required
def admin_saas_dashboard(request):
    """Admin React panel for SaaS plans, companies, and predictive AI."""
    import logging

    log = logging.getLogger('tradeflow.saas')
    ctx = {'nav_activo': 'saas', 'saas_preview': None, 'saas_plans_count': 0}
    ctx['api_admin_saas_stats_url'] = reverse('api_admin_saas_stats')
    ctx['saas_read_only_demo'] = user_is_read_only_saas_demo(request.user)

    try:
        from core.enterprise_models import SaasPlan
        from core.utils.saas_admin_metrics import build_saas_admin_payload
        from core.utils.saas_platform import bootstrap_saas_datastore

        health = bootstrap_saas_datastore(seed_subscriptions=False)
        ctx['saas_plans_count'] = health.get('plans_count', 0)
        if health.get('ok'):
            ctx['saas_preview'] = build_saas_admin_payload()
        else:
            log.warning('admin_saas_dashboard health issues: %s', health.get('issues'))
    except Exception as exc:
        log.error('admin_saas_dashboard preview_failed: %s', exc, exc_info=True)

    log.info(
        'admin_saas_dashboard render plans=%s preview=%s',
        ctx['saas_plans_count'],
        bool(ctx['saas_preview']),
    )
    return render(request, 'core/admin_saas_dashboard.html', ctx)


@admin_required
def api_admin_saas_stats(request):
    """Aggregated JSON for the admin SaaS dashboard."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    from ..utils.saas_admin_metrics import build_saas_admin_payload

    payload = build_saas_admin_payload()
    payload['read_only_demo'] = user_is_read_only_saas_demo(request.user)
    return JsonResponse(payload, encoder=DjangoJSONEncoder)


@admin_required
def api_admin_saas_request_action(request, pk: int):
    """Approve or reject a commercial plan request (POST)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    if user_is_read_only_saas_demo(request.user):
        return JsonResponse({'error': 'Read-only demo account.'}, status=403)
    import json

    from ..enterprise_models import CompanyPlanCommercialRequest
    from ..utils.saas_billing import approve_commercial_request, reject_commercial_request

    try:
        body = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        body = {}
    action = (body.get('action') or request.POST.get('action') or '').strip().lower()

    req = CompanyPlanCommercialRequest.objects.filter(pk=pk).select_related(
        'company', 'requested_plan'
    ).first()
    if not req:
        return JsonResponse({'error': 'Application not found'}, status=404)
    if req.status not in ('pending', 'en_revision'):
        return JsonResponse({'error': 'Application has already been processed'}, status=400)

    if action == 'approve':
        approve_commercial_request(req)
        return JsonResponse({
            'ok': True,
            'status': 'approved',
            'message': f'Plan {req.requested_plan.name} activado para {req.company.name}.',
        })
    if action == 'reject':
        reject_commercial_request(req)
        return JsonResponse({
            'ok': True,
            'status': 'rejected',
            'message': f'Application from {req.company.name} rejected.',
        })
    return JsonResponse({'error': 'Invalid action'}, status=400)


def pending_approval_view(request):
    """Waiting room after signup while admin approval is pending."""
    return render(request, 'core/pending_approval.html')


@admin_required
def admin_applications_view(request):
    """Admin list to review company access applications."""
    try:
        from ..models import UserApplication
        status_filter = request.GET.get('status', '')
        applications = UserApplication.objects.all().order_by('-created_at')
        if status_filter:
            applications = applications.filter(status=status_filter)
        pending_count = UserApplication.objects.filter(status='pending').count()
        return render(request, 'core/admin_applications.html', {
            'applications': applications,
            'pending_count': pending_count,
            'current_filter': status_filter,
            'nav_activo': 'admin_applications',
        })
    except Exception as e:
        log.exception('Error in admin_applications_view: %s', e)
        raise


@admin_required
def approve_application_view(request, pk):
    """Approve an application, activate the account, and notify."""
    from ..models import UserApplication
    from ..utils.application_review import aprobar_solicitud, mensaje_fallo_correo
    if request.method == 'POST':
        try:
            app = UserApplication.objects.get(pk=pk)
            _, email_result = aprobar_solicitud(app, notificar=True)
            warn = mensaje_fallo_correo(email_result)
            if warn:
                messages.warning(request, warn)
            else:
                messages.success(
                    request,
                    'Application approved. The applicant has been notified by email.',
                )
        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')
    return redirect('admin_applications')


@admin_required
def reject_application_view(request, pk):
    """Reject an application and notify the applicant."""
    from ..models import UserApplication
    from ..utils.application_review import mensaje_fallo_correo, rechazar_solicitud
    if request.method == 'POST':
        try:
            app = UserApplication.objects.get(pk=pk)
            _, email_result = rechazar_solicitud(app, notificar=True)
            warn = mensaje_fallo_correo(email_result)
            if warn:
                messages.warning(request, warn)
            else:
                messages.success(
                    request,
                    'Application rejected. The applicant has been notified by email.',
                )
        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')
    return redirect('admin_applications')
