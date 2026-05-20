"""
Métricas y agregados para dashboards del vendedor (productos, ventas, cotizaciones).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from ..models import Cotizacion, CotizacionItem, Inventory, Order, OrderItem, Product


def _month_start(now=None):
    now = now or timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def seller_products_dashboard(company):
    """KPIs, categorías y listado base para página de productos."""
    productos_qs = Product.objects.filter(company=company).select_related('category')
    total = productos_qs.count()
    activos = productos_qs.filter(is_active=True).count()

    bajo_stock = 0
    for inv in Inventory.objects.filter(product__company=company).select_related('product'):
        if inv.is_low_stock:
            bajo_stock += 1

    vendidos_ids = (
        OrderItem.objects.filter(product__company=company)
        .values_list('product_id', flat=True)
        .distinct()
    )
    sin_ventas = productos_qs.exclude(pk__in=vendidos_ids).count()

    cat_rows = (
        productos_qs.exclude(category__isnull=True)
        .values('category__name')
        .annotate(n=Count('id'))
        .order_by('-n')[:12]
    )
    cat_labels = [r['category__name'] or 'Sin categoría' for r in cat_rows]
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
    """Métricas de ventas, tendencia y órdenes filtrables."""
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

    # Tendencia últimos N días
    labels = []
    values = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).date()
        labels.append(d.strftime('%d/%m'))
        day_start = timezone.make_aware(datetime.combine(d, datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        total_dia = OrderItem.objects.filter(
            product__company=company,
            order__created_at__gte=day_start,
            order__created_at__lt=day_end,
            order__status__in=('paid', 'packed', 'shipped', 'delivered'),
        ).aggregate(t=Sum('line_total'))['t'] or Decimal('0')
        values.append(float(total_dia))

    return {
        'ventas_mes': ventas_mes,
        'ingresos_mes': ingresos_mes,
        'ticket_promedio': ticket_promedio,
        'chart_line_labels': labels,
        'chart_line_values': values,
        'ordenes_qs': ordenes_qs.order_by('-created_at'),
    }


def seller_quotes_dashboard(company):
    """Stats y columnas Kanban para cotizaciones."""
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


def cotizacion_monto_estimado(cot):
    """Suma líneas con precio ofertado o precio catálogo."""
    total = Decimal('0.00')
    for it in cot.items.select_related('product').all():
        precio = it.precio_ofertado or getattr(it.product, 'display_price', None) or it.product.unit_price
        total += precio * it.cantidad_solicitada
    return total
