"""
Facturación SaaS por empresa: planes, límites y uso mensual.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from core.enterprise_models import (
    AdCreditAccount,
    CompanyBillingUsage,
    CompanySubscription,
    SaasPlan,
)
from core.models import Company, OrderItem

# Órdenes que cuentan hacia el volumen mensual facturable del plan.
BILLABLE_ORDER_STATUSES = ('paid', 'packed', 'shipped', 'delivered')


class VolumeLimitExceeded(Exception):
    """La empresa superaría el techo mensual del plan SaaS."""

    def __init__(
        self,
        company: Company,
        limit: Decimal,
        current: Decimal,
        additional: Decimal,
    ):
        self.company = company
        self.limit = limit
        self.current = current
        self.additional = additional
        self.projected = (current + additional).quantize(Decimal('0.01'))
        super().__init__('volume_limit_exceeded')


PLAN_LIMITS = {
    'digitalizate': Decimal('15000'),
    'expansion': Decimal('50000'),
    'corporativo_pro': None,
    'ecosistema_enterprise': None,
}


def _period_bounds(now=None):
    now = now or timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def ensure_default_plans():
    """Crea planes oficiales si no existen."""
    defaults = [
        ('digitalizate', 'Digitalízate', Decimal('15000'), 50, False, False, False, 1),
        ('expansion', 'Expansión', Decimal('50000'), 200, True, False, False, 2),
        ('corporativo_pro', 'Corporativo Pro', None, 500, True, True, False, 3),
        ('ecosistema_enterprise', 'Ecosistema Enterprise', None, 2000, True, True, True, 4),
    ]
    for slug, name, limit, credits, api, webhooks, predictive, order in defaults:
        SaasPlan.objects.update_or_create(
            slug=slug,
            defaults={
                'name': name,
                'monthly_volume_limit_usd': limit,
                'ad_credits_monthly': credits,
                'api_access': api,
                'logistics_webhooks': webhooks,
                'predictive_ai': predictive,
                'priority_support': slug in ('corporativo_pro', 'ecosistema_enterprise'),
                'sort_order': order,
                'is_active': True,
            },
        )


def get_or_create_subscription(company: Company) -> CompanySubscription:
    ensure_default_plans()
    try:
        return company.subscription
    except CompanySubscription.DoesNotExist:
        plan = SaasPlan.objects.get(slug='digitalizate')
        start, end = _period_bounds()
        end = end + timedelta(days=32)
        return CompanySubscription.objects.create(
            company=company,
            plan=plan,
            status='active',
            current_period_start=start,
            current_period_end=end,
        )


def compute_monthly_volume(company: Company, now=None) -> tuple[Decimal, int]:
    """Volumen USD y conteo de órdenes del mes (líneas de la empresa)."""
    start, end = _period_bounds(now)
    qs = OrderItem.objects.filter(
        product__company=company,
        order__created_at__gte=start,
        order__created_at__lte=end,
        order__status__in=BILLABLE_ORDER_STATUSES,
    )
    agg = qs.aggregate(vol=Sum('line_total'), n=Sum('order_id'))
    vol = agg['vol'] or Decimal('0.00')
    orders = qs.values('order_id').distinct().count()
    return vol.quantize(Decimal('0.01')), orders


def refresh_billing_usage(company: Company, now=None) -> CompanyBillingUsage:
    now = now or timezone.now()
    vol, orders = compute_monthly_volume(company, now)
    usage, _ = CompanyBillingUsage.objects.update_or_create(
        company=company,
        period_year=now.year,
        period_month=now.month,
        defaults={'volume_usd': vol, 'orders_count': orders},
    )
    return usage


def subscription_usage_snapshot(company: Company) -> dict:
    """Contexto para UI seller: plan, uso, warnings, siguiente tier."""
    sub = get_or_create_subscription(company)
    usage = refresh_billing_usage(company)
    plan = sub.plan
    limit = plan.monthly_volume_limit_usd
    vol = usage.volume_usd
    pct = None
    warning = None
    if limit and limit > 0:
        pct = float((vol / limit) * 100)
        if pct >= 100:
            warning = 'limit'
        elif pct >= 80:
            warning = 'approaching'
    next_plan = (
        SaasPlan.objects.filter(sort_order__gt=plan.sort_order, is_active=True)
        .order_by('sort_order')
        .first()
    )
    try:
        ad_balance = company.ad_credits.balance
    except AdCreditAccount.DoesNotExist:
        ad_balance = plan.ad_credits_monthly

    return {
        'subscription': sub,
        'plan': plan,
        'usage': usage,
        'volume_usd': vol,
        'limit_usd': limit,
        'usage_pct': pct,
        'warning': warning,
        'is_unlimited': plan.is_unlimited,
        'next_plan': next_plan,
        'ad_credits_balance': ad_balance,
        'api_enabled': plan.api_access,
        'webhooks_enabled': plan.logistics_webhooks,
        'predictive_ai_enabled': plan.predictive_ai,
        'volume_blocked': warning == 'limit',
    }


def assert_within_volume_limit(company: Company, additional_usd: Decimal = Decimal('0')) -> None:
    """
    Lanza ``VolumeLimitExceeded`` si el volumen del mes + adicional supera el techo.

    Planes ilimitados no aplican restricción.
    """
    sub = get_or_create_subscription(company)
    if sub.plan.is_unlimited:
        return
    limit = sub.plan.monthly_volume_limit_usd
    if not limit or limit <= 0:
        return
    current, _ = compute_monthly_volume(company)
    projected = current + additional_usd
    if projected > limit:
        raise VolumeLimitExceeded(company, limit, current, additional_usd)


def is_volume_limit_reached(company: Company) -> bool:
    """True si no queda margen para nuevas operaciones que incrementen volumen."""
    sub = get_or_create_subscription(company)
    if sub.plan.is_unlimited:
        return False
    limit = sub.plan.monthly_volume_limit_usd
    if not limit:
        return False
    current, _ = compute_monthly_volume(company)
    return current >= limit


def would_exceed_volume_limit(
    company: Company,
    additional_usd: Decimal,
) -> tuple[bool, VolumeLimitExceeded | None]:
    """Devuelve (True, exc) si additional_usd superaría el techo."""
    try:
        assert_within_volume_limit(company, additional_usd)
        return False, None
    except VolumeLimitExceeded as exc:
        return True, exc


def order_company_subtotal(order, company: Company) -> Decimal:
    """Subtotal USD de líneas de la empresa en una orden."""
    total = Decimal('0.00')
    for item in order.items.filter(product__company=company):
        total += item.line_total
    return total.quantize(Decimal('0.01'))


def plan_allows_feature(company: Company, feature: str) -> bool:
    snap = subscription_usage_snapshot(company)
    plan = snap['plan']
    if feature == 'api':
        return plan.api_access
    if feature == 'webhooks':
        return plan.logistics_webhooks
    if feature == 'unlimited_volume':
        return plan.is_unlimited
    if feature == 'predictive_ai':
        return plan.predictive_ai
    return True
