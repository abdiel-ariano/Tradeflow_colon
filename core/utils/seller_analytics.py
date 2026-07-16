"""Seller dashboard aggregates: products, sales, quotes, payments.

Powers Mi Tienda KPIs for CFZ companies without exposing other sellers'
data.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from ..models import Cotizacion, CotizacionItem, Inventory, Order, OrderItem, Product


def _month_start(now=None):
    """Return timezone-aware start of the current calendar month."""
    now = now or timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def seller_product_kpis(company) -> dict:
    """Return live catalog KPI counts (total / active products)."""
    productos_qs = Product.objects.filter(company=company)
    return {
        'kpi_total': productos_qs.count(),
        'kpi_activos': productos_qs.filter(is_active=True).count(),
    }


def seller_products_dashboard(company):
    """Build KPIs, categories, and product list context for seller products."""
    productos_qs = Product.objects.filter(company=company).select_related('category')
    kpis = seller_product_kpis(company)
    total = kpis['kpi_total']
    activos = kpis['kpi_activos']
    activos_qs = productos_qs.filter(is_active=True)

    bajo_stock = 0
    for inv in Inventory.objects.filter(
        product__company=company,
        product__is_active=True,
    ).select_related('product'):
        if inv.is_low_stock:
            bajo_stock += 1

    vendidos_ids = (
        OrderItem.objects.filter(product__company=company)
        .values_list('product_id', flat=True)
        .distinct()
    )
    sin_ventas = activos_qs.exclude(pk__in=vendidos_ids).count()

    cat_rows = (
        activos_qs.exclude(category__isnull=True)
        .values('category__name')
        .annotate(n=Count('id'))
        .order_by('-n')[:12]
    )
    cat_labels = [r['category__name'] or 'Uncategorized' for r in cat_rows]
    cat_values = [r['n'] for r in cat_rows]

    return {
        'kpi_total': total,
        'kpi_activos': activos,
        'kpi_bajo_stock': bajo_stock,
        'kpi_sin_ventas': sin_ventas,
        'chart_cat_labels': cat_labels,
        'chart_cat_values': cat_values,
    }


def seller_sales_dashboard(company, days=30):
    """Build sales metrics, trend series, and filterable orders for the seller."""
    now = timezone.now()
    month_start = _month_start(now)
    desde = now - timedelta(days=days)

    ordenes_qs = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
    )

    ordenes_mes = ordenes_qs.filter(created_at__gte=month_start)
    ventas_mes = ordenes_mes.count()

    items_mes = OrderItem.objects.filter(
        product__company=company,
        order__created_at__gte=month_start,
        order__status__in=('paid', 'packed', 'shipped', 'delivered'),
    )
    ingresos_mes = items_mes.aggregate(t=Sum('line_total'))['t'] or Decimal('0.00')
    n_items_mes = items_mes.count()
    ticket_promedio = (
        (ingresos_mes / n_items_mes).quantize(Decimal('0.01'))
        if n_items_mes
        else Decimal('0.00')
    )

    # Trend over the last N days
    labels = []
    values = []
    from .chart_labels import chart_axis_label

    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).date()
        labels.append(chart_axis_label(d, dias=min(days, 7) if days <= 7 else 30))
        day_start = timezone.make_aware(datetime.combine(d, datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        from .money_format import money_to_chart_float

        total_dia = OrderItem.objects.filter(
            product__company=company,
            order__created_at__gte=day_start,
            order__created_at__lt=day_end,
            order__status__in=('paid', 'packed', 'shipped', 'delivered'),
        ).aggregate(t=Sum('line_total'))['t'] or Decimal('0')
        values.append(money_to_chart_float(total_dia))

    return {
        'ventas_mes': ventas_mes,
        'ingresos_mes': ingresos_mes,
        'ticket_promedio': ticket_promedio,
        'chart_line_labels': labels,
        'chart_line_values': values,
        'ordenes_qs': ordenes_qs.order_by('-created_at'),
    }


def seller_quotes_dashboard(company):
    """Build quote stats and Kanban columns for the seller."""
    qs = Cotizacion.objects.filter(empresa=company).select_related('buyer', 'order')
    now = timezone.now()
    month_start = _month_start(now)

    del_mes = qs.filter(created_at__gte=month_start).count()
    aceptadas = qs.filter(estado='aceptada').count()
    respondidas = qs.filter(estado='respondida').count()
    total_cerrables = qs.filter(estado__in=('respondida', 'aceptada', 'rechazada')).count()
    tasa_conversion = (
        round(100 * aceptadas / total_cerrables, 1) if total_cerrables else 0
    )

    monto_cotizado = Decimal('0.00')
    for cot in qs.prefetch_related('items')[:200]:
        for it in cot.items.all():
            if it.precio_ofertado:
                monto_cotizado += it.precio_ofertado * it.cantidad_solicitada

    kanban = {
        'pendiente': list(qs.filter(estado='pendiente')[:20]),
        'enviada': list(qs.filter(estado='respondida')[:20]),
        'aceptada': list(qs.filter(estado='aceptada')[:20]),
        'rechazada': list(qs.filter(estado='rechazada')[:20]),
    }

    return {
        'cotizaciones_mes': del_mes,
        'tasa_conversion': tasa_conversion,
        'monto_cotizado': monto_cotizado,
        'kanban': kanban,
        'lista': qs.annotate(n_items=Count('items')).order_by('-created_at'),
    }


def seller_portal_dashboard(company, days=30):
    """Build unified metrics for the main seller portal home."""
    sales = seller_sales_dashboard(company, days=days)
    products = seller_products_dashboard(company)
    quotes = seller_quotes_dashboard(company)
    now = timezone.now()
    hace_7 = now - timedelta(days=7)

    ordenes_semana = (
        Order.objects.filter(
            items__product__company=company,
            created_at__gte=hace_7,
        )
        .distinct()
        .count()
    )

    pending_confirm = (
        Order.objects.filter(
            items__product__company=company,
            status='awaiting_seller',
            seller_confirmation_status='pending',
        )
        .distinct()
        .count()
    )

    ordenes_recientes = list(sales['ordenes_qs'][:8])

    order_status_rows = (
        Order.objects.filter(
            items__product__company=company,
            created_at__gte=now - timedelta(days=days),
        )
        .distinct()
        .values('status')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    status_map = dict(Order.STATUS_CHOICES)
    status_labels = [str(status_map.get(r['status'], r['status'])) for r in order_status_rows]
    status_values = [r['n'] for r in order_status_rows]

    week_labels = []
    week_orders = []
    from .chart_labels import chart_weekday_label

    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).date()
        week_labels.append(chart_weekday_label(d))
        week_orders.append(
            Order.objects.filter(
                items__product__company=company,
                created_at__date=d,
            )
            .distinct()
            .count()
        )

    return {
        'ventas_mes': sales['ventas_mes'],
        'ingresos_mes': sales['ingresos_mes'],
        'ticket_promedio': sales['ticket_promedio'],
        'ordenes_semana': ordenes_semana,
        'pending_confirm': pending_confirm,
        'total_productos': products['kpi_total'],
        'productos_activos': products['kpi_activos'],
        'bajo_stock': products['kpi_bajo_stock'],
        'cotizaciones_mes': quotes['cotizaciones_mes'],
        'tasa_conversion': quotes['tasa_conversion'],
        'chart_revenue_labels': sales['chart_line_labels'],
        'chart_revenue_values': sales['chart_line_values'],
        'chart_status_labels': status_labels,
        'chart_status_values': status_values,
        'chart_week_labels': week_labels,
        'chart_week_orders': week_orders,
        'chart_cat_labels': products['chart_cat_labels'],
        'chart_cat_values': products['chart_cat_values'],
        'ordenes_recientes': ordenes_recientes,
        'cotizaciones_recientes': list(quotes['lista'][:6]),
    }


def cotizacion_monto_estimado(cot):
    """Sum quote lines using offered price or catalog price fallback."""
    total = Decimal('0.00')
    for it in cot.items.select_related('product').all():
        precio = it.precio_ofertado or getattr(it.product, 'display_price', None) or it.product.unit_price
        total += precio * it.cantidad_solicitada
    return total


def seller_payments_analytics(company, days=90):
    """Build payment success rates, volume, and gaps for seller analytics."""
    from ..models import Payment

    now = timezone.now()
    since = now - timedelta(days=days)
    prev_since = since - timedelta(days=days)

    order_ids = (
        OrderItem.objects.filter(product__company=company)
        .values_list('order_id', flat=True)
        .distinct()
    )
    payments_qs = Payment.objects.filter(
        order_id__in=order_ids,
        order__created_at__gte=since,
    ).select_related('order')
    prev_payments_qs = Payment.objects.filter(
        order_id__in=order_ids,
        order__created_at__gte=prev_since,
        order__created_at__lt=since,
    )

    total = payments_qs.count()
    approved = payments_qs.filter(status='approved').count()
    rejected = payments_qs.filter(status='rejected').count()
    pending = payments_qs.filter(status='pending').count()
    refunded = payments_qs.filter(status='refunded').count()
    success_rate = round(100.0 * approved / total, 1) if total else 0.0

    prev_total = prev_payments_qs.count()
    prev_approved = prev_payments_qs.filter(status='approved').count()
    prev_success_rate = round(100.0 * prev_approved / prev_total, 1) if prev_total else 0.0
    rate_delta = round(success_rate - prev_success_rate, 1)

    ingresos_period = payments_qs.filter(status='approved').aggregate(
        t=Sum('amount'),
    )['t'] or Decimal('0.00')
    prev_ingresos = prev_payments_qs.filter(status='approved').aggregate(
        t=Sum('amount'),
    )['t'] or Decimal('0.00')

    provider_rows = list(
        payments_qs.values('provider')
        .annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected')),
        )
        .order_by('-total')
    )
    for row in provider_rows:
        row['rate'] = round(100.0 * row['approved'] / row['total'], 1) if row['total'] else 0.0
        row['provider_label'] = dict(Payment.PROVIDER_CHOICES).get(row['provider'], row['provider'])

    from .chart_labels import chart_axis_label
    from .money_format import money_to_chart_float

    chart_labels = []
    chart_success = []
    chart_revenue = []
    for i in range(min(days, 30) - 1, -1, -1):
        d = (now - timedelta(days=i)).date()
        chart_labels.append(chart_axis_label(d, dias=30))
        day_start = timezone.make_aware(datetime.combine(d, datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        day_payments = payments_qs.filter(
            order__created_at__gte=day_start,
            order__created_at__lt=day_end,
        )
        day_total = day_payments.count()
        day_ok = day_payments.filter(status='approved').count()
        chart_success.append(round(100.0 * day_ok / day_total, 1) if day_total else 0.0)
        day_rev = day_payments.filter(status='approved').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        chart_revenue.append(money_to_chart_float(day_rev))

    cancelled_orders = Order.objects.filter(
        pk__in=order_ids,
        created_at__gte=since,
        status='cancelled',
    ).count()
    awaiting = Order.objects.filter(
        pk__in=order_ids,
        created_at__gte=since,
        status__in=('awaiting_seller', 'pending'),
    ).count()

    return {
        'days': days,
        'total_orders': total,
        'success_count': approved,
        'cancelled_count': cancelled_orders,
        'rejected_count': rejected,
        'pending_count': pending,
        'refunded_count': refunded,
        'awaiting_count': awaiting,
        'success_rate': success_rate,
        'prev_success_rate': prev_success_rate,
        'rate_delta': rate_delta,
        'ingresos_period': ingresos_period,
        'prev_ingresos': prev_ingresos,
        'provider_rows': provider_rows,
        'chart_labels': chart_labels,
        'chart_values': chart_success,
        'chart_revenue_values': chart_revenue,
        'has_chart_data': any(v > 0 for v in chart_success) or total > 0,
    }
