"""Portal vendedor (/mi-tienda/): productos, ventas, planes SaaS y cotizaciones."""
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

from .common import _request_wants_json, log

@buyer_required
def portal_buyer(request):
    """Buyer portal entry — redirects into the public catalog flow."""
    return render(request, 'core/portal_buyer_temp.html', {
        'titulo_pagina': 'TradeFlow store',
    })


@seller_required
def seller_company_qr(request):
    """QR linking to this seller company in the public guest catalog."""
    try:
        company = Company.objects.get(owner=request.user)
    except Company.DoesNotExist:
        messages.error(request, 'No company linked to your account.')
        return redirect('portal_seller')

    catalog_url = request.build_absolute_uri(
        reverse('catalogo_publico') + f'?empresa={company.pk}'
    )
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(catalog_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0F2A44', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'core/seller_qr.html', {
        'company': company,
        'qr_base64': qr_base64,
        'catalog_url': catalog_url,
        'titulo_pagina': 'Company QR',
        'nav_activo': 'seller_qr',
    })


@seller_required
def seller_download_qr(request):
    """Download PNG QR for the seller company catalog URL."""
    try:
        company = Company.objects.get(owner=request.user)
    except Company.DoesNotExist:
        return redirect('portal_seller')

    catalog_url = request.build_absolute_uri(
        reverse('catalogo_publico') + f'?empresa={company.pk}'
    )
    qr = qrcode.QRCode(version=1, box_size=15, border=4)
    qr.add_data(catalog_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0F2A44', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    safe_name = re.sub(r'[^\w\-]+', '-', company.name).strip('-') or 'company'
    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="qr-{safe_name}.png"'
    return response


@seller_required
def portal_seller(request):
    """Seller portal home at ``/mi-tienda/`` after company onboarding."""
    import json as _json

    from ..utils.tradeflow_cache import (
        cached_seller_portal_dashboard,
        maybe_expire_pending_orders,
    )

    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    maybe_expire_pending_orders(min_interval=60)
    data = cached_seller_portal_dashboard(company.pk)

    return render(request, 'core/portal_seller.html', {
        'company': company,
        **data,
        'titulo_pagina': _('Seller dashboard'),
        'nav_activo': 'mi_tienda',
    })


@seller_required
@require_GET
def api_seller_dashboard(request):
    """Lightweight JSON polling for seller portal dashboard widgets."""
    from ..utils.tradeflow_cache import cached_seller_portal_dashboard

    company = _get_seller_company(request.user)
    if not company:
        return JsonResponse({'error': 'no_company'}, status=403)
    data = cached_seller_portal_dashboard(company.pk)
    return JsonResponse({
        'pending_confirm': data['pending_confirm'],
        'ordenes_semana': data['ordenes_semana'],
        'updated': False,
    })


@seller_required
@require_GET
def api_seller_order_timeline(request, pk):
    """JSON logistics timeline for seller order polling / realtime."""
    company = _get_seller_company(request.user)
    if not company:
        return JsonResponse({'error': 'no_company'}, status=403)
    orden = get_object_or_404(
        Order.objects.select_related('shipment').prefetch_related('logistics_events'),
        pk=pk,
    )
    if not orden.items.filter(product__company=company).exists():
        raise Http404
    from ..utils.order_timeline import build_order_timeline

    return JsonResponse(build_order_timeline(orden))


@seller_required
def seller_plan_consumo(request):
    """SaaS consumption dashboard and plan comparison for sellers."""
    import logging

    saas_log = logging.getLogger('tradeflow.saas')

    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    from core.utils.saas_billing import get_company_subscription

    sub = get_company_subscription(company)
    if sub and sub.status == 'past_due':
        return redirect('seller_trial_activation')

    from ..utils.saas_billing import build_plan_page_context_safe
    from ..utils.saas_platform import bootstrap_saas_for_company, get_saas_health

    health = bootstrap_saas_for_company(company)
    saas_log.info(
        'seller_plan_consumo company_id=%s plans=%s health_ok=%s issues=%s',
        company.pk,
        health.get('plans_count'),
        health.get('ok'),
        health.get('issues'),
    )

    ctx, page_error = build_plan_page_context_safe(company)
    ctx.update({
        'company': company,
        'titulo_pagina': _('TradeFlow growth'),
        'nav_activo': 'seller_plan',
        'saas_health': health,
        'saas_page_error': page_error,
    })

    if not ctx.get('plans_available') and not page_error:
        saas_log.warning(
            'seller_plan_consumo empty_plan_cards company_id=%s plans_in_db=%s',
            company.pk,
            health.get('plans_count'),
        )

    return render(request, 'core/seller_plan_consumo.html', ctx)


@seller_required
@require_POST
def seller_dispatch_order(request, pk):
    """One-click logistics dispatch (webhook + timeline update)."""
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp
    orden = get_object_or_404(
        Order.objects.select_related('shipment'),
        pk=pk,
    )
    if not orden.items.filter(product__company=company).exists():
        raise Http404
    from ..utils.order_permissions import assert_can_dispatch

    try:
        assert_can_dispatch(orden, company)
    except PermissionError as exc:
        messages.error(request, str(exc))
        return redirect('seller_detalle_venta', pk=pk)
    from ..utils.logistics_enterprise import enqueue_dispatch
    from ..utils.saas_billing import plan_allows_feature

    if not plan_allows_feature(company, 'webhooks'):
        messages.info(
            request,
            _('Dispatch recorded internally. Enable Corporate Pro for partner webhooks.'),
        )
    enqueue_dispatch(orden, company, request.user)
    messages.success(request, _('Dispatch started. Tracking updated.'))
    if _request_wants_json(request):
        from ..utils.order_timeline import build_order_timeline

        return JsonResponse({'ok': True, 'timeline': build_order_timeline(orden)})
    return redirect('seller_detalle_venta', pk=pk)


@seller_required
def seller_plan_checkout(request, plan_slug: str):
    """Plan payment screen for trial upgrade or post-trial activation."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    if plan_slug == 'ecosistema_enterprise':
        return redirect(f'{reverse("solicitud_acceso")}?plan=enterprise')

    from ..utils.saas_billing import (
        CheckoutMode,
        build_checkout_context,
        can_select_plan_for_activation,
        get_or_create_subscription,
        resolve_checkout_mode,
    )

    try:
        sub = get_or_create_subscription(company)
    except Exception:
        messages.error(request, _('No active subscription. Complete company setup first.'))
        return redirect('seller_onboarding_company')

    mode = resolve_checkout_mode(sub)
    ok, err = can_select_plan_for_activation(company, plan_slug, mode=mode)
    if not ok:
        if err == 'below_recommended_plan':
            messages.error(request, _('This plan is below your recommended tier based on trial sales.'))
        elif err == 'upgrade_requires_higher_plan':
            messages.info(request, _('Select a plan higher than your current one.'))
        elif err == 'plan_requires_commercial':
            return redirect(f'{reverse("solicitud_acceso")}?plan=enterprise')
        else:
            messages.error(request, _('Could not start checkout for this plan.'))
        if mode == CheckoutMode.TRIAL_ACTIVATION:
            return redirect('seller_trial_activation')
        return redirect('seller_plan_consumo')

    try:
        ctx = build_checkout_context(company, plan_slug)
    except ValueError as exc:
        if 'commercial' in str(exc):
            return redirect(f'{reverse("solicitud_acceso")}?plan=enterprise')
        messages.error(request, _('Could not start checkout.'))
        if mode == CheckoutMode.TRIAL_ACTIVATION:
            return redirect('seller_trial_activation')
        return redirect('seller_plan_consumo')

    ctx.update({
        'company': company,
        'titulo_pagina': _('Activate your plan') if ctx.get('is_trial_activation') else _('Plan payment'),
        'nav_activo': 'mi_tienda',
    })
    return render(request, 'core/seller_plan_checkout.html', ctx)


@seller_required
def seller_plan_checkout_resume(request):
    """Resume a pending seller plan checkout session."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp
    from ..utils.saas_billing import get_pending_checkout

    pending = get_pending_checkout(company)
    if not pending:
        messages.info(request, _('You have no pending payments.'))
        return redirect('seller_plan_consumo')
    return redirect('seller_plan_checkout', plan_slug=pending.target_plan.slug)


@seller_required
@require_POST
def seller_plan_checkout_pay(request, plan_slug: str):
    """Confirm the selected payment method for a SaaS plan."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    from ..utils.saas_billing import (
        allow_mock_plan_payment,
        complete_plan_checkout,
        get_pending_checkout,
        submit_bank_transfer_payment,
    )

    checkout = get_pending_checkout(company)
    if not checkout or checkout.target_plan.slug != plan_slug:
        messages.error(request, _('Invalid payment session. Choose your plan again.'))
        return redirect('seller_plan_consumo')

    provider = (request.POST.get('payment_method') or '').strip() or 'bank'
    if provider == 'stripe':
        messages.error(request, _('Card payments via Stripe are not available. Use bank transfer.'))
        return redirect('seller_plan_checkout', plan_slug=plan_slug)

    if provider == 'mock':
        if not allow_mock_plan_payment():
            messages.error(request, _('Demo card payment is disabled. Use bank transfer.'))
            return redirect('seller_plan_checkout', plan_slug=plan_slug)
        card_name = request.POST.get('card_name', '').strip()
        txn_ref = f'MOCK-{checkout.pk}' if card_name else f'MOCK-{checkout.pk}-demo'
        try:
            complete_plan_checkout(checkout, provider='mock', txn_ref=txn_ref)
        except ValueError as exc:
            if 'below_recommended' in str(exc):
                messages.error(request, _('Payment rejected: plan below your recommended tier.'))
            else:
                messages.error(request, _('Payment could not be completed.'))
            return redirect('seller_plan_checkout', plan_slug=plan_slug)
        except Exception:
            import logging
            logging.getLogger('tradeflow.saas').exception(
                'seller_plan_checkout_mock_unhandled company_id=%s plan=%s',
                getattr(company, 'pk', None),
                plan_slug,
            )
            messages.error(request, _('Payment could not be completed.'))
            return redirect('seller_plan_checkout', plan_slug=plan_slug)
        messages.success(
            request,
            _('Payment confirmed. Plan %(name)s is active on your account.')
            % {'name': checkout.target_plan.name},
        )
        return redirect('portal_seller')

    # bank transfer — stays pending
    transfer_ref = request.POST.get('transfer_reference', '').strip()
    seller_notes = request.POST.get('seller_notes', '').strip()
    proof = request.FILES.get('proof_file')
    try:
        submit_bank_transfer_payment(
            checkout,
            transfer_reference=transfer_ref,
            seller_notes=seller_notes,
            proof_file=proof,
        )
    except ValueError as exc:
        code = str(exc)
        if code == 'transfer_reference_required':
            messages.error(request, _('Enter your bank transfer reference (min. 4 characters).'))
        elif code == 'proof_too_large':
            messages.error(request, _('Proof file is too large (max 5 MB). Submit without it or use a smaller file.'))
        elif code == 'bank_transfer_save_failed':
            messages.error(
                request,
                _('Could not save transfer details. Confirm the reference and try again '
                  '(you can skip the proof file).'),
            )
        elif 'below_recommended' in code:
            messages.error(request, _('Payment rejected: plan below your recommended tier.'))
        else:
            messages.error(request, _('Could not submit bank transfer details.'))
        return redirect('seller_plan_checkout', plan_slug=plan_slug)
    except Exception:
        import logging
        logging.getLogger('tradeflow.saas').exception(
            'seller_plan_checkout_pay_unhandled company_id=%s plan=%s',
            getattr(company, 'pk', None),
            plan_slug,
        )
        messages.error(
            request,
            _('Could not submit bank transfer details. Please try again or contact support.'),
        )
        return redirect('seller_plan_checkout', plan_slug=plan_slug)

    messages.success(
        request,
        _('Transfer details received. Your plan activates after admin confirmation '
          '(usually 1–2 business days).'),
    )
    return redirect('seller_plan_consumo')


@seller_required
@require_POST
def seller_upgrade_plan(request):
    """Compatibility redirect from legacy upgrade forms to checkout."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp
    slug = request.POST.get('plan_slug', '').strip()
    if not slug:
        return redirect('seller_plan_consumo')
    return redirect('seller_plan_checkout', plan_slug=slug)


@seller_required
def seller_trial_activation(request):
    """Required post-trial screen (volume, recommended plan, activate)."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    from core.utils.saas_billing import get_company_subscription
    from core.utils.seller_lifecycle import build_trial_activation_context

    sub = get_company_subscription(company)
    if not sub or sub.status != 'past_due':
        return redirect('seller_plan_consumo')

    ctx = build_trial_activation_context(company)
    ctx.update({
        'titulo_pagina': _('Activate your TradeFlow plan'),
        'nav_activo': 'seller_plan',
    })
    return render(request, 'core/seller_trial_activation.html', ctx)


@seller_required
@require_POST
def seller_decline_continue(request):
    """Voluntary churn during grace — apply mid-tier cancel immediately."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    from core.utils.seller_lifecycle import apply_medium_churn

    apply_medium_churn(company)
    messages.info(request, _('Your seller account has been deactivated. Your data is preserved.'))
    return redirect('seller_account_inactive')


@seller_required
def seller_account_inactive(request):
    """Inactive seller account page (no operational portal access)."""
    company = _get_seller_company(request.user)
    return render(request, 'core/seller_account_inactive.html', {
        'company': company,
        'titulo_pagina': _('Account inactive'),
    })


@seller_required
def seller_predictive_insights(request):
    """Predictive AI panel — Ecosistema Enterprise plan only."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp
    from ..utils.saas_billing import plan_allows_feature
    from ..utils.predictive_insights import get_predictive_dashboard, optional_groq_narrative
    import json as _json

    if not plan_allows_feature(company, 'predictive_ai'):
        return render(request, 'core/seller_insights_upgrade.html', {
            'company': company,
            'titulo_pagina': _('Predictive insights'),
            'nav_activo': 'seller_insights',
        })

    dashboard = get_predictive_dashboard(company)
    narrative = optional_groq_narrative(dashboard)
    return render(request, 'core/seller_insights.html', {
        'company': company,
        'insights': dashboard,
        'narrative': narrative,
        'chart_labels': dashboard.get('daily_chart', {}).get('labels', []),
        'chart_values': dashboard.get('daily_chart', {}).get('values', []),
        'titulo_pagina': _('Predictive insights'),
        'nav_activo': 'seller_insights',
    })


def _optimize_product_image_from_request(request, product_form, product):
    """Validate then optimize an uploaded product image before storage save.

    Returns ``(product, ok)``. When ``ok`` is False the caller must not save.
    """
    if 'image' not in request.FILES:
        return product, True
    from django.core.exceptions import ValidationError as _ValidationError

    from ..models import Product
    from ..utils.media_storage import optimize_uploaded_image
    from ..utils.upload_security import UploadValidationError, validate_image_upload

    previous_name = ''
    if product.pk:
        previous_name = (
            Product.objects.filter(pk=product.pk).values_list('image', flat=True).first() or ''
        )

    uploaded = request.FILES['image']
    try:
        validate_image_upload(uploaded, max_bytes=5 * 1024 * 1024)
        product.image = optimize_uploaded_image(uploaded)
        return product, True
    except UploadValidationError as exc:
        messages.error(
            request,
            _('Imagen rechazada: %(detalle)s') % {'detalle': str(exc)},
        )
    except _ValidationError as exc:
        detalle = exc.message if hasattr(exc, 'message') else (
            exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
        )
        messages.error(request, _('Imagen rechazada: %(detalle)s') % {'detalle': detalle})

    if previous_name:
        product.image = previous_name
    else:
        product.image = None
    return product, False


def _get_seller_company(user):
    """Return the Company owned by the user, or None."""
    if not user.is_authenticated:
        return None
    return Company.objects.filter(owner=user).first()


def _seller_company_or_response(request, nav_activo='mi_tienda'):
    """Resolve seller company or render a missing-company notice."""
    company = _get_seller_company(request.user)
    if company:
        return company, None
    from core.utils.access_gating import seller_company_pending

    if seller_company_pending(request.user):
        return None, redirect('seller_onboarding_company')
    messages.warning(
        request,
        'Tu cuenta no está vinculada a una empresa. Completa el registro.',
    )
    ctx = {
        'titulo_pagina': 'My store',
        'nav_activo': nav_activo,
    }
    return None, render(request, 'core/seller_sin_empresa.html', ctx)


def _seller_low_stock_count(company):
    """Count company products at or below low-stock threshold."""
    n = 0
    qs = Inventory.objects.filter(product__company=company).select_related('product')
    for inv in qs:
        if inv.is_low_stock:
            n += 1
    return n


@seller_required
def seller_dashboard(request):
    """Seller metrics for products, stock, and recent orders."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    hoy         = timezone.now()
    hace_7_dias = hoy - timedelta(days=7)

    productos_qs = Product.objects.filter(company=company)
    total_productos  = productos_qs.count()
    activos          = productos_qs.filter(is_active=True).count()
    bajo_stock       = _seller_low_stock_count(company)

    ordenes_recientes = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')[:6]
    )

    ordenes_semana = (
        Order.objects.filter(
            items__product__company=company,
            created_at__gte=hace_7_dias,
        )
        .distinct()
        .count()
    )

    ventas_items = OrderItem.objects.filter(
        product__company=company,
        order__status__in=('paid', 'packed', 'shipped', 'delivered'),
        order__created_at__gte=hace_7_dias,
    )
    ventas_semana = ventas_items.aggregate(t=Sum('line_total'))['t'] or Decimal('0.00')

    context = {
        'company':           company,
        'total_productos':   total_productos,
        'productos_activos': activos,
        'bajo_stock':        bajo_stock,
        'ordenes_semana':    ordenes_semana,
        'ventas_semana':     ventas_semana,
        'ordenes_recientes': ordenes_recientes,
        'titulo_pagina':     'Seller dashboard',
        'nav_activo':        'mi_tienda',
    }
    return render(request, 'core/seller_dashboard.html', context)


@seller_required
def seller_productos(request):
    """Legacy seller product list with filters for the company catalog."""
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    productos = (
        Product.objects.filter(company=company, is_active=True)
        .select_related('category', 'company')
        .defer('company__owner')
        .prefetch_related('inventory')
        .order_by('name')
    )

    buscar    = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar)
            | Q(description__icontains=buscar)
            | Q(sku__icontains=buscar)
        )
    if categoria:
        productos = productos.filter(category_id=categoria)

    paginator = Paginator(productos, 12)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'company':       company,
        'productos':     page_obj,
        'categorias':    Category.objects.all().order_by('name'),
        'buscar':        buscar,
        'cat_activa':    categoria,
        'titulo_pagina': 'My products',
        'nav_activo':    'seller_productos',
    }
    return render(request, 'core/seller_productos.html', context)


@seller_required
def seller_mis_productos(request):
    """Seller products dashboard with KPIs, chart, and filterable table."""
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    from ..utils.seller_analytics import seller_products_dashboard

    productos = (
        Product.objects.filter(company=company)
        .select_related('category', 'company')
        .defer('company__owner')
        .prefetch_related('inventory')
    )
    base_products = Product.objects.filter(company=company)
    count_all = base_products.count()
    count_active = base_products.filter(is_active=True).count()
    count_archived = base_products.filter(is_active=False).count()
    dash = seller_products_dashboard(company)

    catalog_tab = request.GET.get('tab', 'products').strip() or 'products'
    buscar = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    estado = request.GET.get('estado', 'activo').strip() or 'activo'
    if estado == 'archived':
        estado = 'inactivo'
    stock_f = request.GET.get('stock', '').strip()
    orden = request.GET.get('orden', 'nombre')
    created_f = request.GET.get('created', '').strip()

    tab_products = []
    tab_pricing_rows = []
    tab_shipping_rows = []
    tab_tax_rows = []

    if catalog_tab == 'products':
        if buscar:
            productos = productos.filter(
                Q(name__icontains=buscar)
                | Q(description__icontains=buscar)
                | Q(sku__icontains=buscar)
            )
        if categoria:
            productos = productos.filter(category_id=categoria)
        if estado == 'activo':
            productos = productos.filter(is_active=True)
        elif estado == 'inactivo':
            productos = productos.filter(is_active=False)
        elif estado != 'todos':
            productos = productos.filter(is_active=True)
            estado = 'activo'

        if created_f in ('7', '7d'):
            productos = productos.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif created_f in ('30', '30d'):
            productos = productos.filter(created_at__gte=timezone.now() - timedelta(days=30))
        elif created_f in ('90', '90d'):
            productos = productos.filter(created_at__gte=timezone.now() - timedelta(days=90))

        vendidos_ids = set(
            OrderItem.objects.filter(product__company=company)
            .values_list('product_id', flat=True)
        )
        if stock_f == 'bajo':
            low_ids = []
            for inv in Inventory.objects.filter(product__company=company).select_related('product'):
                if inv.is_low_stock:
                    low_ids.append(inv.product_id)
            productos = productos.filter(pk__in=low_ids or [0])
        elif stock_f == 'sin_ventas':
            productos = productos.exclude(pk__in=vendidos_ids)

        if orden == 'precio_asc':
            productos = productos.order_by('unit_price')
        elif orden == 'precio_desc':
            productos = productos.order_by('-unit_price')
        elif orden == 'stock':
            productos = productos.order_by('inventory__stock_qty')
        elif orden == 'created':
            productos = productos.order_by('-created_at')
        else:
            productos = productos.order_by('name')

        paginator = Paginator(productos, 15)
        page_obj = paginator.get_page(request.GET.get('page', 1))
    elif catalog_tab == 'features':
        tab_products = list(
            base_products.filter(Q(is_featured=True) | Q(is_bestseller=True))
            .select_related('category')
            .prefetch_related('inventory')
            .order_by('-merchandising_priority', 'name')[:80]
        )
        page_obj = tab_products
    elif catalog_tab == 'coupons':
        promo_qs = base_products.filter(is_active=True).select_related('category').prefetch_related('inventory')
        tab_products = [p for p in promo_qs.order_by('-discount_pct', 'name')[:120] if p.is_on_promo_now][:80]
        page_obj = tab_products
    elif catalog_tab == 'pricing':
        from django.db.models import Avg, Max, Min

        tab_pricing_rows = list(
            base_products.filter(is_active=True, category__isnull=False)
            .values('category__name')
            .annotate(
                products=Count('id'),
                min_price=Min('unit_price'),
                max_price=Max('unit_price'),
                avg_price=Avg('unit_price'),
            )
            .order_by('category__name')
        )
        page_obj = []
    elif catalog_tab == 'shipping':
        from ..models import Shipment

        tab_shipping_rows = list(
            Shipment.objects.filter(
                order__items__product__company=company,
            )
            .values('status', 'courier_name')
            .annotate(total=Count('id', distinct=True))
            .order_by('-total')[:20]
        )
        page_obj = []
    elif catalog_tab == 'tax':
        tab_tax_rows = list(
            base_products.filter(is_active=True, category__isnull=False)
            .values('category__name')
            .annotate(products=Count('id'), volume=Sum('unit_price'))
            .order_by('-products')[:30]
        )
        page_obj = []
    else:
        page_obj = []

    if catalog_tab != 'products':
        buscar = ''
        created_f = ''

    import json as _json

    return render(request, 'core/seller_mis_productos.html', {
        'company': company,
        'productos': page_obj,
        'categorias': Category.objects.all().order_by('name'),
        'buscar': buscar,
        'cat_activa': categoria,
        'estado_filtro': estado,
        'stock_filtro': stock_f,
        'orden': orden,
        'dash': dash,
        'count_all': count_all,
        'count_active': count_active,
        'count_archived': count_archived,
        'catalog_tab': catalog_tab,
        'created_filtro': created_f,
        'tab_products': tab_products,
        'tab_pricing_rows': tab_pricing_rows,
        'tab_shipping_rows': tab_shipping_rows,
        'tab_tax_rows': tab_tax_rows,
        'chart_cat_labels': dash['chart_cat_labels'],
        'chart_cat_values': dash['chart_cat_values'],
        'titulo_pagina': 'Product catalog',
        'nav_activo': 'seller_productos',
    })


@seller_required
def seller_producto_nuevo(request):
    """Create a product and inventory row for the seller company."""
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    product_form = SellerProductForm()
    inv_form     = SellerInventoryForm()

    if request.method == 'POST':
        if is_volume_limit_reached(company):
            messages.error(
                request,
                _(
                    "You have reached your plan's monthly limit. "
                    'Upgrade your plan before publishing new products.'
                ),
            )
            return redirect('seller_plan_consumo')
        product_form = SellerProductForm(request.POST, request.FILES)
        inv_form     = SellerInventoryForm(request.POST)
        if product_form.is_valid() and inv_form.is_valid():
            product = product_form.save(commit=False)
            product.company = company
            product, img_ok = _optimize_product_image_from_request(
                request, product_form, product,
            )
            if not img_ok:
                messages.error(request, 'Please check the form data.')
            else:
                with transaction.atomic():
                    product.save()
                    inv = inv_form.save(commit=False)
                    inv.product = product
                    inv.reserved_qty = 0
                    inv.save()
                messages.success(request, f'Product "{product.name}" created successfully.')
                return redirect('seller_mis_productos')
        else:
            messages.error(request, 'Please check the form data.')

    context = {
        'company':        company,
        'product_form':   product_form,
        'inv_form':       inv_form,
        'titulo_pagina':  'New product',
        'nav_activo':     'seller_productos',
        'es_edicion':     False,
    }
    return render(request, 'core/seller_producto_form.html', context)


@seller_required
def seller_agregar_producto(request):
    """Alias for product create used by the primary seller portal URL."""
    return seller_producto_nuevo(request)


@seller_required
def seller_producto_editar(request, pk):
    """Edit a seller company product and its inventory."""
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    product = get_object_or_404(
        Product.objects.select_related('company')
        .defer('company__owner')
        .prefetch_related('inventory'),
        pk=pk,
        company=company,
    )

    try:
        inventory = product.inventory
    except Inventory.DoesNotExist:
        inventory = Inventory(product=product, stock_qty=0, reserved_qty=0, low_stock_alert=5)
        inventory.save()

    product_form = SellerProductForm(request.POST or None, request.FILES or None, instance=product)
    inv_form     = SellerInventoryForm(request.POST or None, instance=inventory)

    if request.method == 'POST':
        if product_form.is_valid() and inv_form.is_valid():
            product = product_form.save(commit=False)
            product, img_ok = _optimize_product_image_from_request(
                request, product_form, product,
            )
            if img_ok:
                with transaction.atomic():
                    product.save()
                    inv_form.save()
                messages.success(request, 'Changes saved.')
                return redirect('seller_mis_productos')
        messages.error(request, 'Please check the form data.')

    context = {
        'company':        company,
        'product':        product,
        'product_form':   product_form,
        'inv_form':       inv_form,
        'titulo_pagina':  f'Edit: {product.name}',
        'nav_activo':     'seller_productos',
        'es_edicion':     True,
    }
    return render(request, 'core/seller_producto_form.html', context)


@seller_required
def seller_editar_producto(request, pk):
    """Alias for product edit used by the primary seller portal URL."""
    return seller_producto_editar(request, pk)


@seller_required
def seller_toggle_producto(request, pk):
    """Activate or deactivate a seller product (POST; JSON for AJAX)."""
    if request.method != 'POST':
        return redirect('seller_mis_productos')
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp
    product = get_object_or_404(Product, pk=pk, company=company)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])
    estado = _('active') if product.is_active else _('inactive')
    if _request_wants_json(request):
        from ..utils.seller_analytics import seller_product_kpis

        kpis = seller_product_kpis(company)
        return JsonResponse({
            'ok': True,
            'id': product.pk,
            'is_active': product.is_active,
            'kpi_total': kpis['kpi_total'],
            'kpi_activos': kpis['kpi_activos'],
            'message': _('Product "%(name)s" is now %(estado)s.') % {
                'name': product.name,
                'estado': estado,
            },
        })
    messages.success(
        request,
        _('Product "%(name)s" is now %(estado)s.') % {'name': product.name, 'estado': estado},
    )
    return redirect('seller_mis_productos')


@seller_required
def seller_ventas(request):
    """Legacy list of orders that include this company's products."""
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    ordenes = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')
    )

    estado = request.GET.get('estado', '').strip()
    if estado:
        ordenes = ordenes.filter(status=estado)

    paginator = Paginator(ordenes, 10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'company':        company,
        'ordenes':        page_obj,
        'estado_actual':  estado,
        'status_choices': Order.STATUS_CHOICES,
        'titulo_pagina':  'My sales',
        'nav_activo':     'seller_ventas',
    }
    return render(request, 'core/seller_ventas.html', context)


@seller_required
def seller_mis_ventas(request):
    """Seller sales dashboard with metrics, chart, and CSV export."""
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    from ..utils.order_workflow import expire_pending_orders

    expire_pending_orders()

    from ..utils.seller_analytics import seller_sales_dashboard

    import json as _json

    dash = seller_sales_dashboard(company, days=30)
    ordenes = dash['ordenes_qs']

    estado = request.GET.get('estado', '').strip()
    pago = request.GET.get('pago', '').strip()
    desde = request.GET.get('desde', '').strip()
    hasta = request.GET.get('hasta', '').strip()

    if estado:
        ordenes = ordenes.filter(status=estado)
    if desde:
        try:
            d = datetime.strptime(desde, '%Y-%m-%d').date()
            ordenes = ordenes.filter(created_at__date__gte=d)
        except ValueError:
            pass
    if hasta:
        try:
            d = datetime.strptime(hasta, '%Y-%m-%d').date()
            ordenes = ordenes.filter(created_at__date__lte=d)
        except ValueError:
            pass
    if pago == 'pagado':
        ordenes = ordenes.filter(status__in=('paid', 'packed', 'shipped', 'delivered'))
    elif pago == 'pendiente':
        ordenes = ordenes.filter(status='pending')

    paginator = Paginator(ordenes, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'core/seller_mis_ventas.html', {
        'company': company,
        'ordenes': page_obj,
        'estado_actual': estado,
        'pago_filtro': pago,
        'desde': desde,
        'hasta': hasta,
        'status_choices': Order.STATUS_CHOICES,
        'ventas_mes': dash['ventas_mes'],
        'ingresos_mes': dash['ingresos_mes'],
        'ticket_promedio': dash['ticket_promedio'],
        'chart_line_labels': dash['chart_line_labels'],
        'chart_line_values': dash['chart_line_values'],
        'titulo_pagina': 'Mis ventas',
        'nav_activo': 'seller_ventas',
    })


@seller_required
def seller_export_ventas_csv(request):
    """Export seller sales transactions as CSV."""
    import csv

    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    ordenes = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')
    )
    estado = request.GET.get('estado', '').strip()
    if estado:
        ordenes = ordenes.filter(status=estado)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="ventas_{company.pk}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(['ID', 'Fecha', 'Cliente', 'Monto', 'Estado', 'Tipo'])
    for o in ordenes[:500]:
        sub = sum(
            li.line_total
            for li in o.items.filter(product__company=company)
        )
        writer.writerow([
            o.order_number,
            o.created_at.strftime('%Y-%m-%d %H:%M'),
            o.buyer.get_full_name() or o.buyer.username,
            sub,
            o.get_status_display(),
            o.get_order_type_display(),
        ])
    return response


@seller_required
@require_GET
def seller_export_productos_csv(request):
    """Export the seller catalog as CSV."""
    import csv

    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    estado = request.GET.get('estado', '').strip()
    productos = Product.objects.filter(company=company).select_related('category').prefetch_related('inventory')
    if estado == 'activo':
        productos = productos.filter(is_active=True)
    elif estado in ('inactivo', 'archived'):
        productos = productos.filter(is_active=False)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="productos_{company.pk}.csv"'
    writer = csv.writer(response)
    writer.writerow(['SKU', 'Name', 'Category', 'Price', 'Currency', 'Stock', 'Status', 'Created'])
    for p in productos.order_by('name')[:2000]:
        stock = p.inventory.stock_qty if hasattr(p, 'inventory') and p.inventory else 0
        writer.writerow([
            p.sku or '',
            p.name,
            p.category.name if p.category else '',
            p.unit_price,
            p.currency,
            stock,
            'Active' if p.is_active else 'Archived',
            p.created_at.strftime('%Y-%m-%d'),
        ])
    return response


@seller_required
@require_GET
def seller_export_precios_csv(request):
    """Export seller catalog prices as CSV."""
    import csv

    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    productos = Product.objects.filter(company=company, is_active=True).order_by('name')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="precios_{company.pk}.csv"'
    writer = csv.writer(response)
    writer.writerow(['SKU', 'Name', 'Unit price', 'Currency', 'Promo price', 'Discount %'])
    for p in productos[:2000]:
        writer.writerow([
            p.sku or '',
            p.name,
            p.unit_price,
            p.currency,
            p.display_price,
            p.discount_pct if p.is_on_promo_now else 0,
        ])
    return response


@seller_required
def seller_venta_detalle(request, pk):
    """Order detail limited to line items for this seller company."""
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    orden = get_object_or_404(
        Order.objects.select_related(
            'buyer', 'ship_address', 'transport_carrier', 'confirming_company', 'shipment',
        ).prefetch_related('logistics_events'),
        pk=pk,
    )
    lineas = list(
        orden.items.filter(product__company=company)
        .select_related('product')
        .order_by('id')
    )
    if not lineas:
        raise Http404('Order not found or has no products from your company.')

    from ..utils.order_permissions import get_seller_order_actions

    order_actions = get_seller_order_actions(orden, company)
    puede_confirmar = order_actions['can_confirm']

    if request.method == 'POST' and request.POST.get('accion') == 'despachar':
        messages.error(request, _('Use the dispatch button in the logistics section.'))
        return redirect('seller_detalle_venta', pk=pk)

    if request.method == 'POST' and puede_confirmar:
        accion = request.POST.get('accion', '')
        estado_prev = orden.status
        if accion == 'aceptar':
            try:
                accept_seller_order(orden)
            except VolumeLimitExceeded as exc:
                messages.error(
                    request,
                    _(
                        'Monthly plan limit reached (USD %(limit)s). '
                        'Upgrade your plan to confirm this sale of USD %(add)s.'
                    ) % {'limit': exc.limit, 'add': exc.additional},
                )
                return redirect('seller_plan_consumo')
            messages.success(request, _('Order confirmed. The buyer was notified.'))
            try:
                enviar_cambio_estado(orden, estado_prev)
                enviar_confirmacion_orden(orden)
            except Exception:
                log.exception('Email post-confirmación vendedor')
        elif accion == 'rechazar':
            reject_seller_order(orden)
            messages.warning(request, _('Order rejected. Reserved inventory was released.'))
            try:
                enviar_cambio_estado(orden, estado_prev)
            except Exception:
                log.exception('Email rechazo orden')
        return redirect('seller_detalle_venta', pk=pk)

    subtotal_vendedor = sum((li.line_total for li in lineas), Decimal('0.00'))

    from ..utils.order_timeline import build_order_timeline

    context = {
        'company': company,
        'orden': orden,
        'lineas_vendedor': lineas,
        'subtotal_vendedor': subtotal_vendedor,
        'pago': getattr(orden, 'payment', None),
        'puede_confirmar': puede_confirmar,
        'order_actions': order_actions,
        'maps_url': orden.maps_url_buyer(),
        'titulo_pagina': f'Sale {orden.order_number}',
        'nav_activo': 'seller_ventas',
        'timeline_initial': build_order_timeline(orden),
    }
    return render(request, 'core/seller_venta_detalle.html', context)


@seller_required
def seller_detalle_venta(request, pk):
    """Alias for sale detail used by the primary seller portal URL."""
    return seller_venta_detalle(request, pk)


@seller_required
def seller_cotizaciones(request):
    """Seller RFQ Kanban pipeline and stats in the portal."""
    company, resp = _seller_company_or_response(request, 'seller_cotizaciones')
    if resp:
        return resp

    from ..utils.seller_analytics import (
        cotizacion_monto_estimado,
        seller_quotes_dashboard,
    )

    dash = seller_quotes_dashboard(company)
    lista = dash['lista'].annotate(n_items=Count('items'))

    cot_rows = []
    for cot in lista[:50]:
        cot_rows.append({
            'obj': cot,
            'monto': cotizacion_monto_estimado(cot),
        })

    context = {
        'company': company,
        'cotizaciones': lista,
        'cot_rows': cot_rows,
        'kanban': dash['kanban'],
        'cotizaciones_mes': dash['cotizaciones_mes'],
        'tasa_conversion': dash['tasa_conversion'],
        'monto_cotizado': dash['monto_cotizado'],
        'titulo_pagina': 'Received quotes',
        'nav_activo': 'seller_cotizaciones',
    }
    return render(request, 'core/seller_cotizaciones.html', context)


@seller_required
def seller_responder_cotizacion(request, pk):
    """Seller replies with unit prices and notes per RFQ line."""
    company, resp = _seller_company_or_response(request, 'seller_cotizaciones')
    if resp:
        return resp

    cot = get_object_or_404(
        Cotizacion.objects.prefetch_related(
            Prefetch(
                'items',
                queryset=CotizacionItem.objects.select_related('product').defer(
                    'product__company__owner'
                ),
            )
        ),
        pk=pk,
        empresa=company,
    )

    if request.method == 'POST':
        if cot.estado not in ('pendiente', 'respondida'):
            messages.warning(request, 'This quote no longer accepts changes.')
            return redirect('seller_cotizaciones')

        notas_seller = request.POST.get('notas_seller', '').strip()
        items_list = list(cot.items.all())
        with transaction.atomic():
            for it in items_list:
                key = f'precio_{it.pk}'
                raw = request.POST.get(key, '').strip()
                if raw:
                    try:
                        it.precio_ofertado = Decimal(raw)
                    except (InvalidOperation, ValueError):
                        messages.error(request, f'Invalid price on line: {it.product.name}')
                        return redirect('seller_responder_cotizacion', pk=cot.pk)
                    it.save(update_fields=['precio_ofertado'])
            cot.notas_seller = notas_seller
            if items_list and all(x.precio_ofertado is not None for x in items_list):
                cot.estado = 'respondida'
            cot.save(update_fields=['notas_seller', 'estado', 'updated_at'])

        messages.success(request, 'Quote updated.')
        return redirect('seller_cotizaciones')

    context = {
        'company': company,
        'cot': cot,
        'titulo_pagina': f'Respond to {cot.numero}',
        'nav_activo': 'seller_cotizaciones',
    }
    return render(request, 'core/seller_responder_cotizacion.html', context)
