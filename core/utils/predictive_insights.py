"""
IA predictiva Enterprise: forecast de ventas y alertas de stock (ORM, sin inventar cifras).
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from core.enterprise_models import CompanyPredictiveSnapshot
from core.models import Company, Inventory, OrderItem, Product
from core.utils.saas_billing import BILLABLE_ORDER_STATUSES

log = logging.getLogger('tradeflow.predictive')

CACHE_HOURS = 6


def _period_key(now=None) -> str:
    now = now or timezone.now()
    return now.strftime('%Y-%m')


def _daily_revenue_series(company: Company, days: int = 60) -> list[tuple[str, float]]:
    """Ingresos USD por día (últimos N días) para la empresa."""
    now = timezone.now()
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    agg = (
        OrderItem.objects.filter(
            product__company=company,
            order__created_at__gte=start,
            order__status__in=BILLABLE_ORDER_STATUSES,
        )
        .values('order__created_at__date')
        .annotate(total=Sum('line_total'))
        .order_by('order__created_at__date')
    )
    return [
        (str(r['order__created_at__date']), float(r['total'] or 0))
        for r in agg
    ]


def _linear_forecast_30d(daily: list[tuple[str, float]]) -> dict:
    """
    Tendencia lineal simple sobre serie diaria → proyección 30 días.
    """
    if not daily:
        return {
            'forecast_total_usd': 0.0,
            'forecast_daily_avg_usd': 0.0,
            'trend': 'flat',
            'confidence': 'low',
        }

    values = [v for _, v in daily]
    n = len(values)
    if n == 1:
        avg = values[0]
        return {
            'forecast_total_usd': round(avg * 30, 2),
            'forecast_daily_avg_usd': round(avg, 2),
            'trend': 'flat',
            'confidence': 'low',
        }

    # Regresión y = a + b*x sobre índices 0..n-1
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((x - mean_x) ** 2 for x in xs) or 1.0
    b = num / den
    a = mean_y - b * mean_x

    future_days = 30
    future_start = n
    projected = [max(0.0, a + b * (future_start + i)) for i in range(future_days)]
    total = sum(projected)

    if b > mean_y * 0.02:
        trend = 'up'
    elif b < -mean_y * 0.02:
        trend = 'down'
    else:
        trend = 'flat'

    confidence = 'high' if n >= 14 else ('medium' if n >= 7 else 'low')

    return {
        'forecast_total_usd': round(total, 2),
        'forecast_daily_avg_usd': round(total / future_days, 2),
        'trend': trend,
        'confidence': confidence,
    }


def _top_skus_forecast(company: Company, limit: int = 5) -> list[dict]:
    """Top SKUs por volumen reciente con proyección lineal 30d."""
    from django.db.models import Sum

    since = timezone.now() - timedelta(days=60)
    rows = (
        OrderItem.objects.filter(
            product__company=company,
            order__created_at__gte=since,
            order__status__in=BILLABLE_ORDER_STATUSES,
        )
        .values('product_id', 'product__name', 'product__sku')
        .annotate(revenue=Sum('line_total'), units=Sum('qty'))
        .order_by('-revenue')[:limit]
    )
    out = []
    for r in rows:
        rev = float(r['revenue'] or 0)
        # Proporción simple: extrapolar 30d desde ventana 60d
        forecast = round(rev * 0.5, 2) if rev else 0.0
        out.append({
            'product_id': r['product_id'],
            'name': r['product__name'],
            'sku': r['product__sku'] or '',
            'revenue_60d_usd': round(rev, 2),
            'units_60d': int(r['units'] or 0),
            'forecast_30d_usd': forecast,
        })
    return out


def _stock_alerts(company: Company) -> list[dict]:
    """Días estimados hasta agotar stock por SKU."""
    since = timezone.now() - timedelta(days=30)
    alerts = []
    for inv in Inventory.objects.filter(product__company=company).select_related('product'):
        product = inv.product
        if not product.is_active:
            continue
        available = inv.available_qty
        if available <= 0:
            alerts.append({
                'product_id': product.pk,
                'name': product.name,
                'sku': product.sku,
                'available': 0,
                'days_until_stockout': 0,
                'severity': 'critical',
                'message': 'Sin stock disponible',
            })
            continue

        sold = (
            OrderItem.objects.filter(
                product=product,
                order__created_at__gte=since,
                order__status__in=BILLABLE_ORDER_STATUSES,
            ).aggregate(total=Sum('qty'))['total']
            or 0
        )
        if sold <= 0:
            continue
        daily_rate = float(sold) / 30.0
        if daily_rate <= 0:
            continue
        days_left = int(available / daily_rate)
        if days_left <= 14:
            severity = 'critical' if days_left <= 7 else 'warning'
            alerts.append({
                'product_id': product.pk,
                'name': product.name,
                'sku': product.sku,
                'available': available,
                'days_until_stockout': days_left,
                'severity': severity,
                'message': f'Reponer pronto (~{days_left} días)',
            })
    alerts.sort(key=lambda x: x['days_until_stockout'])
    return alerts[:12]


def compute_predictive_payload(company: Company) -> dict:
    """Calcula insights desde el ORM (sin LLM)."""
    daily = _daily_revenue_series(company)
    forecast = _linear_forecast_30d(daily)
    chart_labels = [d[0] for d in daily[-30:]]
    chart_values = [d[1] for d in daily[-30:]]

    return {
        'generated_at': timezone.now().isoformat(),
        'forecast_30d': forecast,
        'daily_chart': {'labels': chart_labels, 'values': chart_values},
        'top_skus': _top_skus_forecast(company),
        'stock_alerts': _stock_alerts(company),
    }


def get_predictive_dashboard(company: Company, *, force_refresh: bool = False) -> dict:
    """Devuelve payload cacheado o recalculado."""
    key = _period_key()
    if not force_refresh:
        snap = CompanyPredictiveSnapshot.objects.filter(
            company=company,
            period_key=key,
        ).first()
        if snap and (timezone.now() - snap.computed_at).total_seconds() < CACHE_HOURS * 3600:
            payload = snap.payload
            payload['_cached'] = True
            return payload

    payload = compute_predictive_payload(company)
    CompanyPredictiveSnapshot.objects.update_or_create(
        company=company,
        period_key=key,
        defaults={'payload': payload},
    )
    payload['_cached'] = False
    return payload


def optional_groq_narrative(payload: dict) -> str:
    """
    Narrativa opcional sobre cifras ya calculadas (Groq). No inventa métricas.
    """
    from django.conf import settings

    api_key = getattr(settings, 'GROQ_API_KEY', '') or ''
    if not api_key:
        return ''

    try:
        import urllib.request

        f = payload.get('forecast_30d', {})
        alerts = payload.get('stock_alerts', [])
        prompt = (
            'Resume en 2 frases profesionales (español) estos datos predictivos TradeFlow '
            f'sin inventar cifras: forecast_30d={json.dumps(f)}, '
            f'alertas_stock={len(alerts)} SKUs críticos.'
        )
        body = json.dumps({
            'model': getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant'),
            'messages': [
                {'role': 'system', 'content': 'Solo usa los números proporcionados.'},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': 180,
        }).encode()
        req = urllib.request.Request(
            'https://api.groq.com/openai/v1/chat/completions',
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data['choices'][0]['message']['content'].strip()
    except Exception as exc:
        log.debug('groq narrative skipped: %s', exc)
        return ''
