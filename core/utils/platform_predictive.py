"""
IA predictiva a nivel plataforma (panel admin): series mensuales y proyección.
Persistencia opcional vía agregación ORM; no inventa datos sin historial.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from core.models import Order

MONTHS_EN = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

# Backward-compatible alias
MONTHS_ES = MONTHS_EN


def _month_start(year: int, month: int):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime(year, month, 1), tz)


def _platform_monthly_revenue(months_back: int = 9) -> list[dict]:
    """Ingresos USD por mes calendario (órdenes no canceladas)."""
    now = timezone.localtime(timezone.now())
    rows = []
    y, m = now.year, now.month
    for _ in range(months_back):
        start = _month_start(y, m)
        last = monthrange(y, m)[1]
        end = start.replace(day=last, hour=23, minute=59, second=59, microsecond=999999)
        total = (
            Order.objects.filter(
                created_at__gte=start,
                created_at__lte=end,
            )
            .exclude(status='cancelled')
            .aggregate(t=Sum('total'))['t']
            or Decimal('0')
        )
        rows.append({
            'year': y,
            'month': m,
            'label': MONTHS_EN[m - 1],
            'key': f'{y}-{m:02d}',
            'revenue_usd': float(total),
        })
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    rows.reverse()
    return rows


def _linear_regression_forecast(values: list[float], forecast_count: int = 3) -> list[float]:
    """Regresión lineal y = a + b*x; devuelve forecast_count puntos futuros."""
    n = len(values)
    if n == 0:
        return [0.0] * forecast_count
    if n == 1:
        return [values[0]] * forecast_count
    xs = list(range(n))
    sum_x = sum(xs)
    sum_y = sum(values)
    sum_xy = sum(xs[i] * values[i] for i in range(n))
    sum_x2 = sum(x * x for x in xs)
    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        b = 0.0
    else:
        b = (n * sum_xy - sum_x * sum_y) / denom
    a = (sum_y - b * sum_x) / n
    return [max(0.0, a + b * (n + i)) for i in range(forecast_count)]


def _confidence_pct(n_points: int, trend: str) -> int:
    base = min(95, 55 + n_points * 4)
    if trend == 'flat':
        base -= 8
    return max(40, min(95, base))


def build_platform_predictive_payload() -> dict:
    """
    Payload para hero predictivo del admin: 9 meses reales + 3 proyectados.
    """
    history = _platform_monthly_revenue(9)
    values = [r['revenue_usd'] for r in history]
    forecasts = _linear_regression_forecast(values, 3)

    n = len(values)
    if n >= 2:
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(values) / n
        num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        den = sum((x - mean_x) ** 2 for x in xs) or 1.0
        slope = num / den
    else:
        slope = 0.0

    if slope > (sum(values) / max(n, 1)) * 0.02:
        trend = 'up'
    elif slope < -(sum(values) / max(n, 1)) * 0.02:
        trend = 'down'
    else:
        trend = 'flat'

    now = timezone.localtime(timezone.now())
    next_m = now.month + 1
    next_y = now.year
    if next_m > 12:
        next_m = 1
        next_y += 1

    predicted_next = forecasts[0] if forecasts else 0.0
    prev_month = values[-2] if len(values) >= 2 else values[-1] if values else 0
    cur_month = values[-1] if values else 0
    trend_pct = 0.0
    if prev_month > 0:
        trend_pct = round(100.0 * (cur_month - prev_month) / prev_month, 1)

    chart = []
    for r in history:
        chart.append({
            'month': r['label'],
            'key': r['key'],
            'real': r['revenue_usd'],
            'predicted': None,
            'is_today_boundary': r['key'] == f'{now.year}-{now.month:02d}',
        })

    fy, fm = now.year, now.month
    for i, val in enumerate(forecasts):
        fm += 1
        if fm > 12:
            fm = 1
            fy += 1
        chart.append({
            'month': MONTHS_EN[fm - 1],
            'key': f'{fy}-{fm:02d}',
            'real': None,
            'predicted': round(val, 2),
            'is_today_boundary': i == 0,
        })

    enterprise_snapshots = 0
    try:
        from core.enterprise_models import CompanyPredictiveSnapshot

        enterprise_snapshots = CompanyPredictiveSnapshot.objects.filter(
            period_key=_period_key_now(),
        ).count()
    except Exception:
        pass

    return {
        'next_month_label': MONTHS_EN[next_m - 1],
        'predicted_amount_usd': round(predicted_next, 2),
        'confidence_pct': _confidence_pct(n, trend),
        'monthly_trend_pct': trend_pct,
        'trend': trend,
        'trend_label': 'Tendencia positiva' if trend == 'up' else (
            'Tendencia estable' if trend == 'flat' else 'Tendencia a vigilar'
        ),
        'chart': chart,
        'historical_sales': values,
        'enterprise_snapshots_active': enterprise_snapshots,
        'predictive_ai_active': True,
    }


def _period_key_now() -> str:
    return timezone.now().strftime('%Y-%m')
