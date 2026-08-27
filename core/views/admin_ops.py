"""Operaciones de administración: dashboard, órdenes, productos y empresas."""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
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
    EmailVerification, Transportista,
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

from .common import log

def _normalize_dashboard_dias(raw):
    """Normalize admin chart period to 7, 30, or 90 days."""
    try:
        d = int(raw)
    except (TypeError, ValueError):
        d = 7
    if d not in (7, 30, 90):
        d = 7
    return d


def _parse_dashboard_dias(request):
    """Read ``dias`` or legacy ``periodo`` from the request GET."""
    raw = request.GET.get('dias')
    if raw is None:
        raw = request.GET.get('periodo')
    return _normalize_dashboard_dias(raw)


def _dashboard_calendar_days(dias, now=None):
    """Build local-midnight [start, end) windows for chart buckets."""
    if now is None:
        now = timezone.now()
    dias = _normalize_dashboard_dias(dias)
    local_date = timezone.localtime(now).date()
    tzinfo = timezone.get_current_timezone()
    from ..utils.chart_labels import chart_axis_label

    days = []
    for i in range(dias):
        day_date = local_date - timedelta(days=dias - 1 - i)
        day_start = timezone.make_aware(
            datetime.combine(day_date, time.min), tzinfo
        )
        day_end = day_start + timedelta(days=1)
        label = chart_axis_label(day_date, dias=dias)
        days.append((day_start, day_end, label))
    return days


def _commercial_orders(queryset=None):
    """Return supplier-accepted purchase orders plus legacy settled orders."""
    qs = queryset if queryset is not None else Order.objects.all()
    return qs.filter(
        Q(seller_confirmation_status='accepted')
        | Q(status__in=('paid', 'packed', 'shipped', 'delivered')),
    ).distinct()


def _build_dashboard_charts_payload(dias, now=None):
    """Build Chart.js labels, daily series, and status counts.
    
    Buckets use project ``TIME_ZONE`` midnights. ``estados_data``
    counts orders created in the window; ``paid`` includes ``packed``.
    """
    if now is None:
        now = timezone.now()

    from ..utils.money_format import money_to_chart_float, quantize_money

    dias = _normalize_dashboard_dias(dias)
    calendar_days = _dashboard_calendar_days(dias, now=now)

    chart_labels = []
    ordenes_por_dia = []
    ingresos_por_dia = []

    for day_start, day_end, label in calendar_days:
        chart_labels.append(label)
        ordenes_por_dia.append(
            Order.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end
            ).count()
        )
        ing = (
            _commercial_orders(
                Order.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end,
                ),
            )
            .aggregate(t=Sum('total'))['t']
            or Decimal('0')
        )
        ingresos_por_dia.append(money_to_chart_float(ing))

    window_start = calendar_days[0][0] if calendar_days else timezone.localtime(now)
    qs = Order.objects.filter(created_at__gte=window_start)
    by_status = {row['status']: row['c'] for row in qs.values('status').annotate(c=Count('id'))}
    # awaiting_seller se agrupa con pendiente en la dona para no perder volumen del período.
    estados_data = {
        'pending': (
            by_status.get('pending', 0)
            + by_status.get('awaiting_seller', 0)
        ),
        'paid':      by_status.get('paid', 0) + by_status.get('packed', 0),
        'shipped':   by_status.get('shipped', 0),
        'delivered': by_status.get('delivered', 0),
        'cancelled': by_status.get('cancelled', 0),
    }

    order_ids_period = list(
        _commercial_orders(qs).values_list('id', flat=True)
    )
    items_period = OrderItem.objects.filter(order_id__in=order_ids_period)

    cat_rows = (
        items_period.values('product__category__name')
        .annotate(total=Sum('line_total'))
        .order_by('-total')[:6]
    )
    cat_grand = quantize_money(
        items_period.aggregate(t=Sum('line_total'))['t'] or 0
    )
    cat_grand_f = float(cat_grand)
    ventas_por_categoria = []
    for row in cat_rows:
        label = row['product__category__name'] or 'General'
        total_f = money_to_chart_float(row['total'] or 0)
        pct = round(100.0 * total_f / cat_grand_f, 1) if cat_grand_f > 0 else 0.0
        ventas_por_categoria.append({
            'label': label,
            'total': total_f,
            'pct': pct,
        })

    emp_rows = (
        items_period.values('product__company__name')
        .annotate(total=Sum('line_total'))
        .order_by('-total')[:8]
    )
    ventas_por_empresa = [
        {
            'label': row['product__company__name'] or 'No company',
            'total': money_to_chart_float(row['total'] or 0),
        }
        for row in emp_rows
    ]

    prod_rows = (
        items_period.values('product__name')
        .annotate(units=Sum('qty'))
        .order_by('-units')[:8]
    )
    productos_top = [
        {
            'label': row['product__name'] or 'Producto',
            'units': int(row['units'] or 0),
        }
        for row in prod_rows
    ]

    period_label = _('Last %(n)s days') % {'n': dias}

    return {
        'chart_labels':         chart_labels,
        'ordenes_por_dia':      ordenes_por_dia,
        'ingresos_por_dia':     ingresos_por_dia,
        'estados_data':         estados_data,
        'ventas_por_categoria': ventas_por_categoria,
        'ventas_por_empresa':   ventas_por_empresa,
        'productos_top':        productos_top,
        'ordenes_b2b':          qs.count(),
        'dias':                 dias,
        'period_label':         period_label,
    }


def _charts_json(payload):
    """Serialize the dashboard chart payload for templates or APIs."""
    return json.dumps(payload, ensure_ascii=False, cls=DjangoJSONEncoder)


def _dashboard_revenue_qs():
    """Base queryset for factual admin commercial-volume KPIs.

    Delivered-only mode reports completed revenue. The default reports
    supplier-accepted purchase-order volume, including legacy settled orders.
    """
    if settings.DASHBOARD_KPI_REVENUE_DELIVERED_ONLY:
        return Order.objects.filter(status='delivered')
    return _commercial_orders()


def _period_delta_pct(current, previous):
    """Format percent change between the current and prior period."""
    try:
        cur = float(current)
        prev = float(previous)
    except (TypeError, ValueError):
        return "n/a"
    if prev <= 0:
        return "nuevo" if cur > 0 else "sin base"
    pct = (cur - prev) / prev * 100.0
    return f"{pct:+.1f}%"


@admin_required
def api_dashboard_stats(request):
    """JSON daily series and status counts for the admin dashboard."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    dias = _normalize_dashboard_dias(request.GET.get('dias'))
    payload = _build_dashboard_charts_payload(dias)
    return JsonResponse(payload, encoder=DjangoJSONEncoder)


@admin_required
def dashboard(request):
    """Admin panel with KPIs and 7/30/90-day Chart.js period selector."""
    hoy = timezone.now()
    dias = _parse_dashboard_dias(request)

    first_day = (hoy - timedelta(days=dias - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    inicio_actual = first_day
    inicio_anterior = first_day - timedelta(days=dias)
    inicio_prev_end = first_day

    total_ordenes = Order.objects.count()
    ordenes_semana = Order.objects.filter(created_at__gte=inicio_actual).count()
    ordenes_periodo_prev = Order.objects.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
    ).count()

    revenue_qs = _dashboard_revenue_qs()
    ingresos_total = revenue_qs.aggregate(t=Sum('total'))['t'] or Decimal('0')
    ingresos_semana = revenue_qs.filter(created_at__gte=inicio_actual).aggregate(
        t=Sum('total')
    )['t'] or Decimal('0')
    ingresos_periodo_prev = revenue_qs.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    ordenes_activas_periodo = (
        Order.objects.filter(created_at__gte=inicio_actual)
        .exclude(status='cancelled')
        .count()
    )
    ordenes_entregadas_periodo = Order.objects.filter(
        created_at__gte=inicio_actual, status='delivered'
    ).count()
    pct_entregadas_periodo = (
        round(Decimal(100) * ordenes_entregadas_periodo / ordenes_activas_periodo, 1)
        if ordenes_activas_periodo
        else Decimal('0')
    )

    dashboard_modo_pruebas = not settings.DASHBOARD_KPI_REVENUE_DELIVERED_ONLY
    if dashboard_modo_pruebas:
        kpi_ingresos_label = 'Accepted commercial volume (period)'
        kpi_ingresos_sub = 'Supplier-accepted purchase orders'
    else:
        kpi_ingresos_label = 'Delivered revenue (period)'
        kpi_ingresos_sub = 'Delivered orders only'

    total_productos = Product.objects.filter(is_active=True).count()
    total_empresas = Company.objects.count()
    ordenes_recientes = Order.objects.select_related('buyer').order_by('-created_at')[:10]

    clientes_activos = Order.objects.values('buyer').distinct().count()
    clientes_periodo = Order.objects.filter(created_at__gte=inicio_actual).values('buyer').distinct().count()
    clientes_periodo_prev = (
        Order.objects.filter(
            created_at__gte=inicio_anterior,
            created_at__lt=inicio_prev_end,
        )
        .values('buyer')
        .distinct()
        .count()
    )

    entregadas = Order.objects.filter(status='delivered').count()
    tasa_conversion = Decimal('0')
    if total_ordenes > 0:
        tasa_conversion = round(Decimal(100) * entregadas / total_ordenes, 1)

    tot_cur = Order.objects.filter(created_at__gte=inicio_actual).count()
    del_cur = Order.objects.filter(created_at__gte=inicio_actual, status='delivered').count()
    tasa_periodo = round(Decimal(100) * del_cur / tot_cur, 1) if tot_cur else Decimal('0')
    tot_prev = Order.objects.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
    ).count()
    del_prev = Order.objects.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
        status='delivered',
    ).count()
    tasa_periodo_prev = round(Decimal(100) * del_prev / tot_prev, 1) if tot_prev else Decimal('0')
    tasa_delta_pp = tasa_periodo - tasa_periodo_prev

    from ..utils.money_format import format_money_usd as _fmt_usd, quantize_money as _q_money

    ingresos_total = _q_money(ingresos_total)
    ingresos_semana = _q_money(ingresos_semana)

    charts = _build_dashboard_charts_payload(dias, now=hoy)
    chart_labels = charts['chart_labels']
    ordenes_por_dia = charts['ordenes_por_dia']
    ingresos_por_dia = charts['ingresos_por_dia']
    estados_data = charts['estados_data']

    ordenes_b2b = Order.objects.filter(created_at__gte=inicio_actual).count()

    usuarios_plataforma = User.objects.filter(is_active=True).count()
    usuarios_login_periodo = User.objects.filter(
        is_active=True,
        last_login__isnull=False,
        last_login__gte=inicio_actual,
    ).count()

    actividad = []
    for o in Order.objects.select_related('buyer').order_by('-created_at')[:8]:
        actividad.append(
            {
                'ts': o.created_at,
                'icon': 'receipt_long',
                'titulo': f'Order {o.order_number}',
                'detalle': (o.buyer.get_full_name() or o.buyer.username) + ' · ' + o.get_status_display(),
            }
        )
    for u in User.objects.order_by('-date_joined')[:6]:
        actividad.append(
            {
                'ts': u.date_joined,
                'icon': 'person_add',
                'titulo': f'Usuario {u.username}',
                'detalle': u.email or '—',
            }
        )
    actividad.sort(key=lambda x: x['ts'], reverse=True)
    actividad = actividad[:12]

    from ..enterprise_models import CompanyPlanCommercialRequest

    work_apps = list(
        UserApplication.objects.filter(status='pending').order_by('-created_at')[:5]
    )
    work_carriers = list(
        Transportista.objects.filter(estado='pendiente').order_by('-fecha_aplicacion')[:5]
    )
    work_saas = list(
        CompanyPlanCommercialRequest.objects.filter(status__in=('pending', 'en_revision'))
        .select_related('company', 'requested_plan')
        .order_by('-created_at')[:5]
    )
    work_orders = list(
        Order.objects.filter(status__in=('pending', 'awaiting_seller', 'paid', 'packed'))
        .select_related('buyer')
        .order_by('-updated_at')[:5]
    )
    work_queue = {
        'applications_count': UserApplication.objects.filter(status='pending').count(),
        'carriers_count': Transportista.objects.filter(estado='pendiente').count(),
        'saas_count': CompanyPlanCommercialRequest.objects.filter(
            status__in=('pending', 'en_revision'),
        ).count(),
        'orders_count': Order.objects.filter(
            status__in=('pending', 'awaiting_seller', 'paid', 'packed'),
        ).count(),
        'applications': work_apps,
        'carriers': work_carriers,
        'saas_requests': work_saas,
        'orders': work_orders,
    }

    context = {
        'total_ordenes':        total_ordenes,
        'ordenes_semana':       ordenes_semana,
        'ordenes_delta_label':  _period_delta_pct(ordenes_semana, ordenes_periodo_prev),
        'ingresos_total':       ingresos_total,
        'ingresos_semana':      ingresos_semana,
        'ingresos_delta_label': _period_delta_pct(
            float(ingresos_semana), float(ingresos_periodo_prev)
        ),
        'total_productos':      total_productos,
        'total_empresas':       total_empresas,
        'ordenes_recientes':    ordenes_recientes,
        'chart_labels':         chart_labels,
        'ordenes_por_dia':      ordenes_por_dia,
        'ingresos_por_dia':     ingresos_por_dia,
        'estados_data':         estados_data,
        'chart_labels_json':    json.dumps(chart_labels),
        'ordenes_por_dia_json': json.dumps(ordenes_por_dia),
        'ingresos_por_dia_json': json.dumps(ingresos_por_dia),
        'estados_data_json':    json.dumps(estados_data),
        'charts_initial':       charts,
        'charts_initial_json':  _charts_json(charts),
        'api_dashboard_stats_url': reverse('api_dashboard_stats'),
        'ordenes_b2b':          ordenes_b2b,
        'usuarios_plataforma':  usuarios_plataforma,
        'usuarios_login_periodo': usuarios_login_periodo,
        'actividad_reciente':   actividad,
        'clientes_activos':     clientes_activos,
        'clientes_periodo':     clientes_periodo,
        'clientes_delta_label': _period_delta_pct(clientes_periodo, clientes_periodo_prev),
        'tasa_conversion':      tasa_conversion,
        'tasa_periodo':         tasa_periodo,
        'tasa_delta_pp':        tasa_delta_pp,
        'tasa_delta_pp_fmt':    f'{tasa_delta_pp:+.1f}',
        'periodo_activo':       dias,
        'dias_activo':          dias,
        'periodo_label':        charts.get('period_label', ''),
        'titulo_pagina':        'Dashboard',
        'nav_activo':           'dashboard',
        'dashboard_modo_pruebas': dashboard_modo_pruebas,
        'kpi_ingresos_label':   kpi_ingresos_label,
        'kpi_ingresos_sub':     kpi_ingresos_sub,
        'ordenes_activas_periodo': ordenes_activas_periodo,
        'ordenes_entregadas_periodo': ordenes_entregadas_periodo,
        'pct_entregadas_periodo': pct_entregadas_periodo,
        'ingresos_semana_fmt': _fmt_usd(ingresos_semana),
        'ingresos_total_fmt': _fmt_usd(ingresos_total),
        'work_queue': work_queue,
    }
    return render(request, 'core/dashboard.html', context)


@admin_required
def lista_ordenes(request):
    """Admin list of marketplace orders with filters and pagination."""
    ordenes = (
        Order.objects.select_related('buyer')
        .annotate(item_count=Count('items', distinct=True))
        .order_by('-created_at')
    )
    buscar  = request.GET.get('buscar', '')
    estado  = request.GET.get('estado', '')

    if buscar:
        ordenes = ordenes.filter(
            Q(order_number__icontains=buscar) |
            Q(buyer__first_name__icontains=buscar) |
            Q(buyer__last_name__icontains=buscar) |
            Q(buyer__username__icontains=buscar)
        )
    if estado:
        ordenes = ordenes.filter(status=estado)

    paginator = Paginator(ordenes, 10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    from urllib.parse import urlencode

    filtros_q = {}
    if buscar:
        filtros_q['buscar'] = buscar
    if estado:
        filtros_q['estado'] = estado
    orden_filtros_query = urlencode(filtros_q)

    estado_opciones = [{'value': '', 'label': 'All statuses', 'selected': not bool(estado)}]
    for val, label in Order.STATUS_CHOICES:
        estado_opciones.append({
            'value':    val,
            'label':    label,
            'selected': bool(estado) and estado == val,
        })

    context = {
        'ordenes':             page_obj,
        'buscar':              buscar,
        'estado_actual':       estado,
        'estado_opciones':     estado_opciones,
        'orden_filtros_query': orden_filtros_query,
        'titulo_pagina':       'Order management',
        'nav_activo':          'ordenes',
    }
    return render(request, 'core/ordenes.html', context)


@admin_required
def detalle_orden(request, pk):
    """Admin detail for a single order, items, and logistics."""
    orden = get_object_or_404(
        Order.objects.select_related('buyer', 'ship_address').prefetch_related(
            Prefetch(
                'items',
                queryset=OrderItem.objects.select_related(
                    'product', 'product__company', 'product__category'
                ).order_by('id'),
            ),
            'documents',
        ),
        pk=pk,
    )
    # Materializar líneas en una lista para evitar inconsistencias con prefetch
    # o caché de relación inversa en plantillas con órdenes muy grandes (simulación anual).
    orden_items = list(orden.items.all())
    otros_estados = [(v, lbl) for v, lbl in Order.STATUS_CHOICES if v != orden.status]
    try:
        pago = Payment.objects.get(order=orden)
    except Payment.DoesNotExist:
        pago = None
    try:
        envio = Shipment.objects.get(order=orden)
    except Shipment.DoesNotExist:
        envio = None
    context = {
        'orden':           orden,
        'orden_items':     orden_items,
        'pago':            pago,
        'envio':           envio,
        'otros_estados':   otros_estados,
        'titulo_pagina':   f'Order {orden.order_number}',
        'nav_activo':      'ordenes',
    }
    return render(request, 'core/detalle_orden.html', context)


@admin_required
@require_POST
def cambiar_estado_orden(request, pk, estado):
    """Admin transition of an order status with email side effects (POST + CSRF)."""
    orden = get_object_or_404(Order, pk=pk)
    estados_validos = [e[0] for e in Order.STATUS_CHOICES]

    if estado in estados_validos:
        estado_anterior = orden.status
        orden.status = estado
        orden.save(update_fields=['status', 'updated_at'])
        if estado == 'delivered':
            pago = getattr(orden, 'payment', None)
            if pago and pago.status == 'pending':
                pago.status  = 'approved'
                pago.paid_at = timezone.now()
                pago.save(update_fields=['status', 'paid_at'])
        messages.success(request, f'Order updated to "{orden.get_status_display()}".')
        try:
            enviar_cambio_estado(orden, estado_anterior)
        except Exception:
            log.exception('No se pudo enviar email de cambio de estado.')
    else:
        messages.error(request, 'Invalid status.')

    return redirect('detalle_orden', pk=pk)


@admin_required
def nueva_orden_paso1(request):
    """Admin new-order wizard step 1 — choose buyer/company."""
    request.session.pop('wizard_buyer_id', None)
    request.session.pop('wizard_items', None)

    compradores = User.objects.filter(is_active=True).order_by('username')

    if request.method == 'POST':
        buyer_id = request.POST.get('buyer_id')
        if not buyer_id:
            messages.error(request, 'You must select a buyer.')
        else:
            request.session['wizard_buyer_id'] = int(buyer_id)
            return redirect('nueva_orden_paso2')

    return render(request, 'core/nueva_orden_paso1.html', {
        'compradores':   compradores,
        'titulo_pagina': 'New order — Step 1',
        'nav_activo':    'ordenes',
        'paso_actual':   1,
    })


@admin_required
def nueva_orden_paso2(request):
    """Admin new-order wizard step 2 — select catalog products."""
    if not request.session.get('wizard_buyer_id'):
        messages.error(request, 'Complete step 1 first.')
        return redirect('nueva_orden_paso1')

    productos  = (
        Product.objects.filter(is_active=True)
        .select_related('category', 'company', 'inventory')
        .defer('company__owner')
        .order_by('name')
    )
    categorias = Category.objects.all()

    buscar    = request.GET.get('buscar', '')
    categoria = request.GET.get('categoria', '')
    if buscar:
        productos = productos.filter(Q(name__icontains=buscar) | Q(sku__icontains=buscar))
    if categoria:
        productos = productos.filter(category__id=categoria)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'agregar':
            producto_id = request.POST.get('producto_id')
            cantidad    = int(request.POST.get('cantidad', 1))
            try:
                producto = Product.objects.select_related('inventory').get(
                    pk=producto_id, is_active=True
                )
            except Product.DoesNotExist:
                messages.error(request, 'Product not found.')
                return redirect('nueva_orden_paso2')

            disponible = producto.available_qty
            if cantidad < 1:
                messages.error(request, 'Quantity must be at least 1.')
            elif cantidad > disponible:
                messages.error(request, f'Insufficient stock. Available: {disponible}.')
            else:
                items = request.session.get('wizard_items', [])
                encontrado = False
                for item in items:
                    if item['producto_id'] == int(producto_id):
                        nueva_cant = item['cantidad'] + cantidad
                        item['cantidad'] = min(nueva_cant, disponible)
                        item['subtotal'] = str(float(item['precio']) * item['cantidad'])
                        encontrado = True
                        break
                if not encontrado:
                    items.append({
                        'producto_id': int(producto_id),
                        'nombre':      producto.name,
                        'precio':      str(producto.unit_price),
                        'cantidad':    cantidad,
                        'subtotal':    str(float(producto.unit_price) * cantidad),
                    })
                request.session['wizard_items'] = items
                request.session.modified = True
                messages.success(request, f'"{producto.name}" added.')

        elif action == 'quitar':
            producto_id = int(request.POST.get('producto_id'))
            items = [
                i for i in request.session.get('wizard_items', [])
                if i['producto_id'] != producto_id
            ]
            request.session['wizard_items'] = items
            request.session.modified = True

        elif action == 'continuar':
            if not request.session.get('wizard_items'):
                messages.error(request, 'Add at least one product.')
            else:
                return redirect('nueva_orden_paso3')

        return redirect('nueva_orden_paso2')

    items_sesion  = request.session.get('wizard_items', [])
    total_carrito = sum(float(i['subtotal']) for i in items_sesion)

    return render(request, 'core/nueva_orden_paso2.html', {
        'productos':     productos,
        'categorias':    categorias,
        'buscar':        buscar,
        'cat_activa':    categoria,
        'items_carrito': items_sesion,
        'total_carrito': total_carrito,
        'titulo_pagina': 'New order — Step 2',
        'nav_activo':    'ordenes',
        'paso_actual':   2,
    })


@admin_required
def nueva_orden_paso3(request):
    """Admin new-order wizard step 3 — confirm and create the order."""
    from decimal import Decimal
    buyer_id = request.session.get('wizard_buyer_id')
    items = request.session.get('wizard_items', [])

    if not buyer_id or not items:
        messages.error(request, 'Session expired. Start the order again.')
        return redirect('nueva_orden_paso1')

    buyer       = get_object_or_404(User, pk=buyer_id)
    direcciones = Address.objects.filter(user=buyer)
    subtotal    = sum(float(i['subtotal']) for i in items)

    if request.method == 'POST':
        shipping_cost = Decimal(request.POST.get('shipping_cost', 0) or 0)
        address_id    = request.POST.get('address_id') or None
        notas         = request.POST.get('notas', '')

        ship_address = None
        if address_id:
            try:
                ship_address = Address.objects.get(pk=address_id, user=buyer)
            except Address.DoesNotExist:
                pass

        orden = Order.objects.create(
            buyer=buyer, ship_address=ship_address,
            order_type='b2b', shipping_cost=shipping_cost,
            notes=notas, status='pending',
        )

        for item_data in items:
            try:
                producto = Product.objects.select_related('inventory').get(
                    pk=item_data['producto_id']
                )
                cantidad = item_data['cantidad']
                if producto.available_qty >= cantidad:
                    OrderItem.objects.create(
                        order=orden, product=producto,
                        qty=cantidad,
                        unit_price_snapshot=producto.unit_price,
                    )
                    if hasattr(producto, 'inventory'):
                        producto.inventory.reserve(cantidad)
                else:
                    messages.warning(
                        request,
                        f'Insufficient stock for "{producto.name}", item skipped.'
                    )
            except Product.DoesNotExist:
                pass

        orden.recalculate_totals()
        orden.shipping_cost = shipping_cost
        orden.total = orden.subtotal + shipping_cost
        orden.save(update_fields=['shipping_cost', 'total'])

        for key in ('wizard_buyer_id', 'wizard_items'):
            request.session.pop(key, None)

        messages.success(
            request,
            f'Order {orden.order_number} created pending payment and logistics.',
        )
        return redirect('detalle_orden', pk=orden.pk)

    return render(request, 'core/nueva_orden_paso3.html', {
        'buyer':         buyer,
        'items':         items,
        'subtotal':      subtotal,
        'direcciones':   direcciones,
        'titulo_pagina': 'New order — Step 3',
        'nav_activo':    'ordenes',
        'paso_actual':   3,
    })


@admin_required
def lista_productos(request):
    """Admin catalog product list across CFZ companies (dense table)."""
    productos = (
        Product.objects.select_related('company', 'category')
        .defer('company__owner')
        .prefetch_related('inventory')
        .order_by('name')
    )
    buscar = request.GET.get('buscar', '')
    categoria = request.GET.get('categoria', '')
    empresa = request.GET.get('empresa', '')
    activo = request.GET.get('activo', '')

    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar)
            | Q(description__icontains=buscar)
            | Q(sku__icontains=buscar)
        )
    if categoria:
        productos = productos.filter(category__id=categoria)
    if empresa:
        productos = productos.filter(company__id=empresa)
    if activo == '1':
        productos = productos.filter(is_active=True)
    elif activo == '0':
        productos = productos.filter(is_active=False)

    paginator = Paginator(productos, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    categorias = Category.objects.all()
    categorias_opciones = [
        {
            'id': c.pk,
            'name': c.name,
            'selected': bool(categoria and str(c.pk) == str(categoria)),
        }
        for c in categorias
    ]
    empresas_opciones = [
        {
            'id': c.pk,
            'name': c.name,
            'selected': bool(empresa and str(c.pk) == str(empresa)),
        }
        for c in Company.objects.order_by('name')[:200]
    ]

    from urllib.parse import urlencode

    prod_filtros = {}
    if buscar:
        prod_filtros['buscar'] = buscar
    if categoria:
        prod_filtros['categoria'] = categoria
    if empresa:
        prod_filtros['empresa'] = empresa
    if activo:
        prod_filtros['activo'] = activo
    producto_filtros_query = urlencode(prod_filtros)

    return render(request, 'core/productos.html', {
        'productos': page_obj,
        'categorias_opciones': categorias_opciones,
        'empresas_opciones': empresas_opciones,
        'buscar': buscar,
        'cat_activa': categoria,
        'empresa_activa': empresa,
        'activo_filtro': activo,
        'producto_filtros_query': producto_filtros_query,
        'titulo_pagina': 'Product catalog',
        'nav_activo': 'productos',
    })


@admin_required
@require_POST
def admin_toggle_product_active(request, pk):
    """Toggle Product.is_active from the admin catalog table."""
    producto = get_object_or_404(Product, pk=pk)
    producto.is_active = not producto.is_active
    producto.save(update_fields=['is_active'])
    state = 'active' if producto.is_active else 'inactive'
    messages.success(request, f'Product “{producto.name}” marked {state}.')
    next_url = request.POST.get('next') or reverse('lista_productos')
    return redirect(next_url)


@admin_required
def lista_empresas(request):
    """Admin directory of CFZ seller companies with search/verify filters."""
    empresas = Company.objects.annotate(
        total_productos=Count('products')
    ).order_by('name')
    buscar = (request.GET.get('buscar') or '').strip()
    verificado = request.GET.get('verificado', '')
    if buscar:
        empresas = empresas.filter(
            Q(name__icontains=buscar) | Q(ruc__icontains=buscar)
        )
    if verificado == '1':
        empresas = empresas.filter(verification_status='verified')
    elif verificado == '0':
        empresas = empresas.exclude(verification_status='verified')

    paginator = Paginator(empresas, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    from urllib.parse import urlencode

    filtros = {}
    if buscar:
        filtros['buscar'] = buscar
    if verificado:
        filtros['verificado'] = verificado
    empresa_filtros_query = urlencode(filtros)

    return render(request, 'core/empresas.html', {
        'empresas': page_obj,
        'buscar': buscar,
        'verificado_filtro': verificado,
        'empresa_filtros_query': empresa_filtros_query,
        'titulo_pagina': 'Companies',
        'nav_activo': 'empresas',
    })


def _admin_post_next_url(request, fallback: str) -> str:
    """Return a safe post-action redirect target from ``next`` POST field."""
    from django.utils.http import url_has_allowed_host_and_scheme

    next_url = (request.POST.get('next') or '').strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback


@admin_required
@require_POST
def admin_toggle_company_verified(request, pk):
    """Toggle company verification using ``verification_status`` as canonical state."""
    empresa = get_object_or_404(Company, pk=pk)
    next_url = _admin_post_next_url(request, reverse('lista_empresas'))

    try:
        if empresa.verification_status == 'verified':
            empresa.return_to_pending_review()
            messages.success(
                request,
                f'Company “{empresa.name}” returned to pending review.',
            )
        else:
            empresa.mark_verified(request.user)
            messages.success(
                request,
                f'Company “{empresa.name}” marked verified.',
            )
    except ValidationError as exc:
        missing = empresa.verification_missing_fields()
        if missing:
            detail = ', '.join(missing)
        elif getattr(exc, 'message_dict', None):
            detail = '; '.join(
                str(msg)
                for msgs in exc.message_dict.values()
                for msg in (msgs if isinstance(msgs, (list, tuple)) else [msgs])
            )
        else:
            detail = str(exc)
        messages.error(
            request,
            f'Cannot verify “{empresa.name}”. Missing or invalid: {detail}.',
        )

    return redirect(next_url)


@admin_required
def admin_empresa_detalle(request, pk):
    """Company ops sheet: overview, products, recent orders."""
    empresa = get_object_or_404(Company, pk=pk)
    tab = (request.GET.get('tab') or 'overview').strip()
    productos = (
        Product.objects.filter(company=empresa)
        .select_related('category')
        .prefetch_related('inventory')
        .order_by('name')[:50]
    )
    ordenes = (
        Order.objects.filter(items__product__company=empresa)
        .select_related('buyer')
        .distinct()
        .order_by('-created_at')[:20]
    )
    subscription = None
    try:
        subscription = empresa.subscription
    except Exception:
        subscription = None
    return render(request, 'core/admin_empresa_detalle.html', {
        'empresa': empresa,
        'tab': tab,
        'productos': productos,
        'ordenes': ordenes,
        'subscription': subscription,
        'titulo_pagina': empresa.name,
        'nav_activo': 'empresas',
    })


@admin_required
def admin_panel_search(request):
    """Global admin search across companies, orders, and applications."""
    q = (request.GET.get('q') or '').strip()
    companies = []
    orders = []
    applications = []
    if len(q) >= 2:
        companies = list(
            Company.objects.filter(Q(name__icontains=q) | Q(ruc__icontains=q))
            .order_by('name')[:15]
        )
        orders = list(
            Order.objects.filter(
                Q(order_number__icontains=q)
                | Q(buyer__email__icontains=q)
                | Q(buyer__username__icontains=q)
            )
            .select_related('buyer')
            .order_by('-created_at')[:15]
        )
        applications = list(
            UserApplication.objects.filter(
                Q(email__icontains=q)
                | Q(full_name__icontains=q)
                | Q(company_name__icontains=q)
            ).order_by('-created_at')[:15]
        )
    return render(request, 'core/admin_panel_search.html', {
        'q': q,
        'companies': companies,
        'orders': orders,
        'applications': applications,
        'titulo_pagina': 'Admin search',
        'nav_activo': 'panel_search',
    })
