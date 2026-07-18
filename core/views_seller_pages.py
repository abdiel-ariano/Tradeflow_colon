"""Seller portal shell pages beyond the main sales dashboard.

Dashboard-style screens for CFZ sellers: balances, customers, tax
stubs, disputes, setup guide, global search, and payment analytics.
Some routes are fully wired; others scaffold future portal features.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .decorators import seller_required
from .models import Cotizacion, Order, OrderItem, Product
from .views import _seller_company_or_response
from .utils.seller_analytics import seller_portal_dashboard, seller_sales_dashboard


def _seller_ctx(company, nav_activo: str, titulo: str, **extra):
    """Build shared template context for seller shell pages."""
    return {
        'company': company,
        'nav_activo': nav_activo,
        'titulo_pagina': titulo,
        **extra,
    }


@seller_required
@require_GET
def seller_balances(request):
    """Show monthly sales income and payment approval totals.

    Aggregates approved vs pending Payment rows for the seller company
    so CFZ merchants can reconcile marketplace cash flow.
    """
    company, resp = _seller_company_or_response(request, 'seller_balances')
    if resp:
        return resp
    from .models import Payment

    sales = seller_sales_dashboard(company)
    order_ids = OrderItem.objects.filter(product__company=company).values_list('order_id', flat=True).distinct()
    payments = Payment.objects.filter(order_id__in=order_ids)
    approved_total = payments.filter(status='approved').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    pending_total = payments.filter(status='pending').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    recent_payments = list(
        payments.select_related('order', 'order__buyer')
        .order_by('-paid_at', '-order__created_at')[:12]
    )
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
            approved_total=approved_total,
            pending_total=pending_total,
            recent_payments=recent_payments,
        ),
    )


@seller_required
@require_GET
def seller_customers(request):
    """List buyers who quoted or purchased from this seller company.

    Merges Order and Cotizacion activity per buyer so sellers see
    spend, quote volume, and optional name/email search filters.
    """
    company, resp = _seller_company_or_response(request, 'seller_customers')
    if resp:
        return resp

    order_buyers = (
        Order.objects.filter(items__product__company=company)
        .values('buyer_id')
        .annotate(
            orders_count=Count('id', distinct=True),
            total_spent=Sum('total'),
            last_order_at=Max('created_at'),
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
            'last_order_at': row.get('last_order_at'),
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
                'last_order_at': stats.get('last_order_at'),
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
    """Render CFZ export tax overview tabs (scaffold for compliance)."""
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
    """Show catalog and order counts for seller data export tooling."""
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
    """List orders awaiting seller confirmation or dispute action.

    Surfaces ``awaiting_seller`` / ``paid`` rows still pending
    confirmation so merchants clear the post-payment SLA queue.
    """
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
    """Render the integrations marketplace shell for future seller apps."""
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
    """Checklist for first catalog publish, QR share, quotes, and sale.

    Marks each onboarding step done from live Company/Product/Order
    and Cotizacion state so new CFZ sellers see progress in-portal.
    """
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
    """Search products, orders, buyers, and quotes for one company.

    Combines ORM filters with AI tip/suggestion payload so sellers
    find catalog and CRM records from a single portal search box.
    """
    company, resp = _seller_company_or_response(request, 'seller_search')
    if resp:
        return resp

    from .utils.ai_search import build_search_response

    q = request.GET.get('q', '').strip()
    products = []
    orders = []
    customers = []
    quotes = []
    ai_payload = {}
    if q:
        ai_payload = build_search_response('seller', q, request, limit=10)
        products = list(
            Product.objects.filter(company=company)
            .filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(description__icontains=q))
            .order_by('name')[:20]
        )
        orders = list(
            Order.objects.filter(
                items__product__company=company,
            )
            .filter(Q(order_number__icontains=q) | Q(buyer__username__icontains=q) | Q(buyer__email__icontains=q))
            .distinct()
            .select_related('buyer')
            .order_by('-created_at')[:20]
        )
        quotes = list(
            Cotizacion.objects.filter(empresa=company, numero__icontains=q)
            .select_related('buyer')
            .order_by('-created_at')[:15]
        )
        buyer_ids = set(
            Order.objects.filter(items__product__company=company).values_list('buyer_id', flat=True)
        )
        customers = list(
            User.objects.filter(pk__in=buyer_ids).filter(
                Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )[:15]
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
            search_customers=customers,
            search_quotes=quotes,
            ai_tip=ai_payload.get('tip', ''),
            ai_related=ai_payload.get('related', []),
            ai_suggestions=ai_payload.get('suggestions', []),
        ),
    )


@seller_required
@require_GET
def seller_reporting(request):
    """Payment acceptance analytics for a selectable day window.

    Charts approval rates and revenue so sellers tune checkout
    performance without leaving the portal shell.
    """
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
        ),
    )
