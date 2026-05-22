"""
Métricas y series para el dashboard del comprador (estilo Shopify Analytics).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from ..models import Cotizacion, Order, OrderItem


def _month_start(now=None):
    now = now or timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def buyer_dashboard(user, days=30):
    """KPIs, gráficas y actividad reciente del comprador."""
    now = timezone.now()
    month_start = _month_start(now)
    desde = now - timedelta(days=days)

    ordenes_qs = (
        Order.objects.filter(buyer=user)
        .select_related('transport_carrier')
        .prefetch_related('items__product__company')
        .order_by('-created_at')
    )

    ordenes_mes = ordenes_qs.filter(created_at__gte=month_start)
    total_ordenes = ordenes_qs.count()
    pendientes = ordenes_qs.filter(
        status__in=('pending', 'awaiting_seller'),
    ).count()
    en_transito = ordenes_qs.filter(status__in=('paid', 'packed', 'shipped')).count()
    entregadas = ordenes_qs.filter(status='delivered').count()

    gasto_mes = ordenes_mes.exclude(status='cancelled').aggregate(
        t=Sum('total'),
    )['t'] or Decimal('0.00')

    cot_qs = Cotizacion.objects.filter(buyer=user)
    cot_pendientes = cot_qs.filter(estado='pendiente').count()
    cot_aprobadas = cot_qs.filter(estado='aceptada').count()
    cot_total = cot_qs.count()

    # Órdenes por día (últimos 7 días)
    line_labels = []
    line_values = []
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).date()
        line_labels.append(d.strftime('%d/%m'))
        cnt = ordenes_qs.filter(created_at__date=d).count()
        line_values.append(cnt)

    # Distribución por estado (ventana)
    status_rows = (
        ordenes_qs.filter(created_at__gte=desde)
        .values('status')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    status_labels = []
    status_values = []
    status_map = dict(Order.STATUS_CHOICES)
    for row in status_rows:
        status_labels.append(str(status_map.get(row['status'], row['status'])))
        status_values.append(row['n'])

    # Empresas más activas (por líneas de pedido)
    company_rows = (
        OrderItem.objects.filter(order__buyer=user, order__created_at__gte=desde)
        .exclude(order__status='cancelled')
        .values('product__company__name')
        .annotate(n=Count('id'))
        .order_by('-n')[:6]
    )
    company_labels = [r['product__company__name'] or '—' for r in company_rows]
    company_values = [r['n'] for r in company_rows]

    recent_orders = list(ordenes_qs[:8])
    recent_quotes = list(
        cot_qs.select_related('empresa').order_by('-created_at')[:5],
    )

    alerts = []
    for o in ordenes_qs.filter(status='awaiting_seller')[:5]:
        if o.seller_confirm_by and o.seller_confirm_by > now:
            alerts.append({
                'type': 'confirm',
                'order_id': o.pk,
                'order_number': o.order_number,
                'deadline': o.seller_confirm_by.isoformat(),
            })

    return {
        'kpi_total_ordenes': total_ordenes,
        'kpi_pendientes': pendientes,
        'kpi_en_transito': en_transito,
        'kpi_entregadas': entregadas,
        'kpi_gasto_mes': gasto_mes,
        'kpi_cot_pendientes': cot_pendientes,
        'kpi_cot_aprobadas': cot_aprobadas,
        'kpi_cot_total': cot_total,
        'chart_line_labels': line_labels,
        'chart_line_values': line_values,
        'chart_status_labels': status_labels,
        'chart_status_values': status_values,
        'chart_company_labels': company_labels,
        'chart_company_values': company_values,
        'recent_orders': recent_orders,
        'recent_quotes': recent_quotes,
        'alerts': alerts,
    }
