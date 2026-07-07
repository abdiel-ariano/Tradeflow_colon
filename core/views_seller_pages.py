"""
Páginas del panel seller — shell tipo dashboard (Home, Balances, Tax, etc.).
Algunas son funcionales; otras son base para features futuras.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .decorators import seller_required
from .models import Cotizacion, Order, OrderItem, Product
from .views import _seller_company_or_response
from .utils.seller_analytics import seller_portal_dashboard, seller_sales_dashboard


def _seller_ctx(company, nav_activo: str, titulo: str, **extra):
    return {
        'company': company,
        'nav_activo': nav_activo,
        'titulo_pagina': titulo,
        **extra,
    }


@seller_required
@require_GET
def seller_balances(request):
    """Balances: ingresos y resumen financiero del seller."""
    company, resp = _seller_company_or_response(request, 'seller_balances')
    if resp:
        return resp
    sales = seller_sales_dashboard(company)
    return render(
        request,
        'core/seller_balances.html',
        _seller_ctx(
            company,
            'seller_balances',
            'Balances',
            ingresos_mes=sales['ingresos_mes'],
            ventas_mes=sales['ventas_mes'],
            ticket_promedio=sales['ticket_promedio'],
        ),
    )


@seller_required
@require_GET
def seller_customers(request):
    """Listado de compradores que han cotizado o comprado."""
    company, resp = _seller_company_or_response(request, 'seller_customers')
    if resp:
        return resp

    order_buyers = (
        Order.objects.filter(items__product__company=company)
        .values('buyer_id')
        .annotate(
            orders_count=Count('id', distinct=True),
            total_spent=Sum('total'),
            last_order=Count('id'),
        )
    )
    buyer_stats: dict[int, dict] = {}
    for row in order_buyers:
        bid = row['buyer_id']
        if not bid:
            continue
        buyer_stats[bid] = {
            'orders_count': row['orders_count'],
            'total_spent': row['total_spent'] or Decimal('0'),
            'quotes_count': 0,
        }

    quote_rows = (
        Cotizacion.objects.filter(empresa=company)
        .values('buyer_id')
        .annotate(quotes_count=Count('id'))
    )
    for row in quote_rows:
        bid = row['buyer_id']
        if not bid:
            continue
        if bid not in buyer_stats:
            buyer_stats[bid] = {
                'orders_count': 0,
                'total_spent': Decimal('0'),
                'quotes_count': row['quotes_count'],
            }
        else:
            buyer_stats[bid]['quotes_count'] = row['quotes_count']

    buyers = []
    if buyer_stats:
        users = {
            u.pk: u
            for u in User.objects.filter(pk__in=buyer_stats.keys()).only(
                'id', 'username', 'first_name', 'last_name', 'email',
            )
        }
        for bid, stats in buyer_stats.items():
            user = users.get(bid)
            if not user:
                continue
            buyers.append({
                'user': user,
                'orders_count': stats['orders_count'],
                'quotes_count': stats['quotes_count'],
                'total_spent': stats['total_spent'],
            })
    buyers.sort(key=lambda b: b['total_spent'], reverse=True)

    q = request.GET.get('q', '').strip()
    if q:
        ql = q.lower()
        buyers = [
            b for b in buyers
            if ql in (b['user'].username or '').lower()
            or ql in (b['user'].email or '').lower()
            or ql in (b['user'].get_full_name() or '').lower()
        ]

    return render(
        request,
        'core/seller_customers.html',
        _seller_ctx(company, 'seller_customers', 'Customers', customers=buyers, search_q=q),
    )


@seller_required
@require_GET
def seller_tax(request):
    """Tax — overview (CFZ export compliance; expansión futura)."""
    company, resp = _seller_company_or_response(request, 'seller_tax')
    if resp:
        return resp
    tab = request.GET.get('tab', 'overview')
    return render(
        request,
        'core/seller_tax.html',
        _seller_ctx(company, 'seller_tax', 'Tax', active_tab=tab),
    )


@seller_required
@require_GET
def seller_data_management(request):
    """Exportación y gestión de datos del seller."""
    company, resp = _seller_company_or_response(request, 'seller_data')
    if resp:
        return resp
    product_count = Product.objects.filter(company=company).count()
    order_count = (
        Order.objects.filter(items__product__company=company).distinct().count()
    )
    return render(
        request,
        'core/seller_data_management.html',
        _seller_ctx(
            company,
            'seller_data',
            'Data management',
            product_count=product_count,
            order_count=order_count,
        ),
    )


@seller_required
@require_GET
def seller_disputes(request):
    """Órdenes que requieren acción del seller (disputas / confirmación)."""
    company, resp = _seller_company_or_response(request, 'seller_disputes')
    if resp:
        return resp
    ordenes = (
        Order.objects.filter(
            items__product__company=company,
            status__in=('awaiting_seller', 'paid'),
            seller_confirmation_status='pending',
        )
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')[:50]
    )
    return render(
        request,
        'core/seller_disputes.html',
        _seller_ctx(company, 'seller_disputes', 'Disputes', ordenes=ordenes),
    )


@seller_required
@require_GET
def seller_apps(request):
    """Marketplace de integraciones (base para futuras apps)."""
    company, resp = _seller_company_or_response(request, 'seller_apps')
    if resp:
        return resp
    return render(
        request,
        'core/seller_apps.html',
        _seller_ctx(company, 'seller_apps', 'Apps'),
    )


@seller_required
@require_GET
def seller_setup_guide(request):
    """Guía de configuración inicial del seller."""
    company, resp = _seller_company_or_response(request, 'seller_setup')
    if resp:
        return resp

    has_products = Product.objects.filter(company=company, is_active=True).exists()
    has_sales = OrderItem.objects.filter(product__company=company).exists()
    has_quotes = Cotizacion.objects.filter(empresa=company).exists()
    profile_ok = bool(company.name and company.ruc)

    steps = [
        {
            'id': 'profile',
            'title': 'Complete company profile',
            'done': profile_ok,
            'url_name': 'mi_perfil',
        },
        {
            'id': 'catalog',
            'title': 'Publish your first product',
            'done': has_products,
            'url_name': 'seller_agregar_producto',
        },
        {
            'id': 'qr',
            'title': 'Share your catalog QR',
            'done': has_products,
            'url_name': 'seller_company_qr',
        },
        {
            'id': 'quotes',
            'title': 'Respond to a quote request',
            'done': has_quotes,
            'url_name': 'seller_cotizaciones',
        },
        {
            'id': 'sales',
            'title': 'Complete your first sale',
            'done': has_sales,
            'url_name': 'seller_mis_ventas',
        },
    ]
    done_count = sum(1 for s in steps if s['done'])
    return render(
        request,
        'core/seller_setup_guide.html',
        _seller_ctx(
            company,
            'seller_setup',
            'Setup guide',
            setup_steps=steps,
            setup_done=done_count,
            setup_total=len(steps),
        ),
    )


@seller_required
@require_GET
def seller_global_search(request):
    """Búsqueda global en productos y órdenes del seller."""
    company, resp = _seller_company_or_response(request, 'seller_search')
    if resp:
        return resp

    q = request.GET.get('q', '').strip()
    products = []
    orders = []
    if q:
        products = list(
            Product.objects.filter(company=company)
            .filter(Q(name__icontains=q) | Q(sku__icontains=q))
            .order_by('name')[:20]
        )
        orders = list(
            Order.objects.filter(
                items__product__company=company,
                order_number__icontains=q,
            )
            .distinct()
            .select_related('buyer')
            .order_by('-created_at')[:20]
        )

    return render(
        request,
        'core/seller_search.html',
        _seller_ctx(
            company,
            'seller_search',
            'Search',
            search_q=q,
            search_products=products,
            search_orders=orders,
        ),
    )


@seller_required
@require_GET
def seller_reporting(request):
    """Payments analytics — aceptación y rendimiento de pagos."""
    import json as _json

    company, resp = _seller_company_or_response(request, 'seller_reporting')
    if resp:
        return resp

    from .utils.seller_analytics import seller_payments_analytics

    analytics_tab = request.GET.get('tab', 'acceptance').strip() or 'acceptance'
    days = 90
    try:
        days = int(request.GET.get('days', '90'))
    except (TypeError, ValueError):
        days = 90
    days = max(7, min(days, 365))

    data = seller_payments_analytics(company, days=days)
    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)
    return render(
        request,
        'core/seller_payments_analytics.html',
        _seller_ctx(
            company,
            'seller_reporting',
            'Payments analytics',
            analytics_tab=analytics_tab,
            analytics_days=days,
            period_start=period_start,
            period_end=period_end,
            **data,
            chart_labels_json=_json.dumps(data['chart_labels']),
            chart_values_json=_json.dumps(data['chart_values']),
        ),
    )
