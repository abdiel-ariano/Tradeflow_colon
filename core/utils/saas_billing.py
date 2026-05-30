"""
Facturación SaaS por empresa: planes, límites y uso mensual.
"""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.utils import DatabaseError, OperationalError, ProgrammingError
from django.utils import timezone

log = logging.getLogger('tradeflow.saas')

from core.enterprise_models import (
    AdCreditAccount,
    CompanyBillingUsage,
    CompanyPlanCheckout,
    CompanyPlanCommercialRequest,
    CompanySubscription,
    SaasPlan,
    SubscriptionUpgradeLog,
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

# Precio mensual público (checkout; Stripe futuro)
PLAN_MRR_USD = {
    'digitalizate': Decimal('40'),
    'expansion': Decimal('200'),
    'corporativo_pro': Decimal('800'),
    'ecosistema_enterprise': Decimal('2500'),
}


def plan_monthly_price(slug: str) -> Decimal:
    return PLAN_MRR_USD.get(slug, Decimal('0'))


def _period_bounds(now=None):
    now = now or timezone.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def _safe_pending_checkout(company: Company) -> CompanyPlanCheckout | None:
    """Checkout pendiente; tolera migración 0017 no aplicada."""
    try:
        return (
            CompanyPlanCheckout.objects.filter(company=company, status='pending')
            .select_related('target_plan', 'from_plan')
            .order_by('-created_at')
            .first()
        )
    except (OperationalError, ProgrammingError) as exc:
        log.warning(
            'saas_checkout_table_unavailable company_id=%s: %s',
            company.pk,
            exc,
        )
        return None


def ensure_default_plans() -> int:
    """Crea planes oficiales si no existen. Retorna cantidad de planes activos."""
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
    count = SaasPlan.objects.filter(is_active=True).count()
    log.info('saas_ensure_default_plans active_plans=%s', count)
    return count


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

    growth_signal = 'optimal'
    growth_message = 'Your operation is progressing within the TradeFlow ecosystem.'
    if warning == 'approaching':
        growth_signal = 'accelerating'
        growth_message = 'Your commercial volume is accelerating — consider expanding capacity.'
    elif warning == 'limit':
        growth_signal = 'expand'
        growth_message = 'Upgrade your plan to keep scaling without operational friction.'

    pending_checkout = _safe_pending_checkout(company)

    activity_pct = min(pct or 0, 100) if pct is not None else (35 if not plan.is_unlimited else 100)
    flow_steps = _build_seller_flow_steps(
        plan=plan,
        next_plan=next_plan,
        activity_pct=activity_pct,
        warning=warning,
        pending_checkout=pending_checkout,
    )
    journey_pct = flow_steps[-1]['cumulative_pct'] if flow_steps else 0

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
        'growth_signal': growth_signal,
        'growth_message': growth_message,
        'meter_width_pct': min(pct or 0, 100) if pct is not None else None,
        'show_public_meter': not plan.is_unlimited and pct is not None,
        'pending_checkout': pending_checkout,
        'flow_steps': flow_steps,
        'journey_pct': journey_pct,
        'activity_label': _activity_label(activity_pct, warning),
    }


def _activity_label(pct: float, warning: str | None) -> str:
    if warning == 'limit':
        return 'Period capacity at maximum'
    if warning == 'approaching':
        return 'Commercial activity growing'
    if pct >= 50:
        return 'Healthy commercial pace'
    return 'Room to accelerate sales'


def _build_seller_flow_steps(
    *,
    plan: SaasPlan,
    next_plan: SaasPlan | None,
    activity_pct: float,
    warning: str | None,
    pending_checkout: CompanyPlanCheckout | None,
) -> list[dict]:
    """Pasos visibles del recorrido seller (barras segmentadas)."""
    if pending_checkout:
        return [
            {
                'key': 'plan',
                'label': 'Plan selected',
                'detail': pending_checkout.target_plan.name,
                'status': 'done',
                'pct': 100,
                'cumulative_pct': 33,
            },
            {
                'key': 'pay',
                'label': 'Payment',
                'detail': 'Complete checkout',
                'status': 'current',
                'pct': 45,
                'cumulative_pct': 66,
            },
            {
                'key': 'live',
                'label': 'Activation',
                'detail': 'Plan live',
                'status': 'upcoming',
                'pct': 0,
                'cumulative_pct': 100,
            },
        ]

    steps = [
        {
            'key': 'operate',
            'label': 'Operation',
            'detail': plan.name,
            'status': 'done',
            'pct': 100,
            'cumulative_pct': 25,
        },
        {
            'key': 'activity',
            'label': 'Activity',
            'detail': _activity_label(activity_pct, warning),
            'status': 'current' if warning != 'limit' else 'current',
            'pct': round(activity_pct, 1),
            'cumulative_pct': 25 + round(activity_pct * 0.45, 1),
        },
    ]
    if next_plan:
        upgrade_ready = warning in ('approaching', 'limit')
        steps.append({
            'key': 'grow',
            'label': 'Next tier',
            'detail': next_plan.name,
            'status': 'current' if upgrade_ready else 'upcoming',
            'pct': 100 if upgrade_ready else max(15, int(activity_pct * 0.5)),
            'cumulative_pct': 100,
        })
    else:
        steps.append({
            'key': 'grow',
            'label': 'Ecosystem',
            'detail': 'Maximum operational tier',
            'status': 'done',
            'pct': 100,
            'cumulative_pct': 100,
        })
    return steps


def activate_company_plan(
    company: Company,
    plan_slug: str,
    *,
    source: str = 'self_serve',
    notes: str = '',
) -> CompanySubscription:
    """
    Activa o actualiza plan en Supabase (CompanySubscription + historial + créditos ads).
    """
    from django.db import transaction

    from core.utils.ads_ranking import ensure_ad_credits
    from core.utils.saas_plan_catalog import marketing_for_plan

    ensure_default_plans()
    plan = SaasPlan.objects.filter(slug=plan_slug, is_active=True).first()
    if not plan:
        raise ValueError(f'plan_not_found:{plan_slug}')
    if marketing_for_plan(plan).get('cta') == 'commercial' and source != 'commercial':
        raise ValueError('plan_requires_commercial_activation')

    with transaction.atomic():
        sub = get_or_create_subscription(company)
        from_plan = sub.plan
        if from_plan.pk == plan.pk:
            return sub
        sub.plan = plan
        sub.status = 'active'
        sub.upgraded_at = timezone.now()
        start, _ = _period_bounds()
        sub.current_period_start = start
        sub.save(update_fields=['plan', 'status', 'upgraded_at', 'current_period_start'])
        SubscriptionUpgradeLog.objects.create(
            company=company,
            from_plan=from_plan,
            to_plan=plan,
            source=source,
            notes=notes[:255],
        )
        ensure_ad_credits(company, plan.ad_credits_monthly)
        refresh_billing_usage(company)
    return sub


def create_plan_checkout(company: Company, plan_slug: str) -> CompanyPlanCheckout:
    """Inicia checkout persistente para upgrade de plan."""
    from datetime import timedelta

    ensure_default_plans()
    from core.utils.saas_plan_catalog import marketing_for_plan

    plan = SaasPlan.objects.filter(slug=plan_slug, is_active=True).first()
    if not plan:
        raise ValueError('plan_not_found')
    if marketing_for_plan(plan).get('cta') == 'commercial':
        raise ValueError('plan_requires_commercial')

    sub = get_or_create_subscription(company)
    if sub.plan.slug == plan_slug:
        raise ValueError('already_on_plan')

    try:
        CompanyPlanCheckout.objects.filter(company=company, status='pending').update(
            status='cancelled',
        )
    except (OperationalError, ProgrammingError) as exc:
        log.warning('saas_checkout_cancel_pending_failed: %s', exc)
        raise ValueError('checkout_table_unavailable') from exc

    amount = plan_monthly_price(plan_slug)
    now = timezone.now()
    try:
        return CompanyPlanCheckout.objects.create(
            company=company,
            from_plan=sub.plan,
            target_plan=plan,
            amount_usd=amount,
            status='pending',
            expires_at=now + timedelta(hours=48),
        )
    except (OperationalError, ProgrammingError) as exc:
        log.warning('saas_checkout_create_failed: %s', exc)
        raise ValueError('checkout_table_unavailable') from exc


def get_pending_checkout(company: Company) -> CompanyPlanCheckout | None:
    return _safe_pending_checkout(company)


def complete_plan_checkout(
    checkout: CompanyPlanCheckout,
    *,
    provider: str = 'mock',
    txn_ref: str = '',
) -> CompanySubscription:
    """Marca pago y activa plan (Supabase)."""
    from django.db import transaction

    if checkout.status != 'pending':
        raise ValueError('checkout_not_pending')

    with transaction.atomic():
        checkout.status = 'paid'
        checkout.provider = provider
        checkout.txn_ref = (txn_ref or f'TF-{checkout.pk}-{timezone.now().strftime("%Y%m%d%H%M")}')[:120]
        checkout.paid_at = timezone.now()
        checkout.save(update_fields=['status', 'provider', 'txn_ref', 'paid_at'])
        return activate_company_plan(
            checkout.company,
            checkout.target_plan.slug,
            source='self_serve',
            notes=f'checkout:{checkout.pk}',
        )


def build_checkout_context(company: Company, plan_slug: str) -> dict:
    """Contexto para pantalla de pago del plan."""
    from core.utils.saas_plan_catalog import marketing_for_plan

    ensure_default_plans()
    plan = SaasPlan.objects.get(slug=plan_slug, is_active=True)
    sub = get_or_create_subscription(company)
    marketing = marketing_for_plan(plan)
    checkout = get_pending_checkout(company)
    if not checkout or checkout.target_plan_id != plan.pk:
        checkout = create_plan_checkout(company, plan_slug)

    return {
        'checkout': checkout,
        'target_plan': plan,
        'from_plan': sub.plan,
        'marketing': marketing,
        'amount': checkout.amount_usd,
        'saas': subscription_usage_snapshot(company),
    }


def create_enterprise_commercial_request(
    company: Company,
    *,
    contact_name: str,
    contact_email: str,
    message: str = '',
    user_application=None,
) -> CompanyPlanCommercialRequest:
    """Registra solicitud Enterprise en Supabase."""
    ensure_default_plans()
    plan = SaasPlan.objects.get(slug='ecosistema_enterprise')
    return CompanyPlanCommercialRequest.objects.create(
        company=company,
        requested_plan=plan,
        status='pending',
        contact_name=contact_name[:120],
        contact_email=contact_email,
        company_legal_name=company.name[:200],
        message=message,
        user_application=user_application,
    )


def reject_commercial_request(req: CompanyPlanCommercialRequest, *, notes: str = '') -> CompanyPlanCommercialRequest:
    """Rechaza solicitud comercial (persistente en Supabase)."""
    req.status = 'rejected'
    req.reviewed_at = timezone.now()
    req.save(update_fields=['status', 'reviewed_at'])
    return req


def approve_commercial_request(req: CompanyPlanCommercialRequest) -> CompanySubscription:
    """Aprueba solicitud comercial y activa plan Enterprise en Supabase."""
    from django.db import transaction

    with transaction.atomic():
        req.status = 'approved'
        req.reviewed_at = timezone.now()
        req.save(update_fields=['status', 'reviewed_at'])
        return activate_company_plan(
            req.company,
            req.requested_plan.slug,
            source='commercial',
            notes=f'commercial_request:{req.pk}',
        )


def build_plan_page_context(company: Company) -> dict:
    """Contexto completo para página de planes (marketing sin topes USD)."""
    from core.utils.saas_plan_catalog import marketing_for_plan

    ensure_default_plans()
    snap = subscription_usage_snapshot(company)
    current_slug = snap['plan'].slug
    cards = []
    for plan in SaasPlan.objects.filter(is_active=True).order_by('sort_order'):
        m = marketing_for_plan(plan)
        m['is_current'] = plan.slug == current_slug
        m['can_upgrade'] = plan.sort_order > snap['plan'].sort_order
        m['monthly_price_usd'] = float(plan_monthly_price(plan.slug))
        cards.append(m)

    try:
        pending_enterprise = CompanyPlanCommercialRequest.objects.filter(
            company=company,
            requested_plan__slug='ecosistema_enterprise',
            status__in=('pending', 'en_revision'),
        ).first()
    except (OperationalError, ProgrammingError) as exc:
        log.warning('saas_commercial_request_query_failed: %s', exc)
        pending_enterprise = None

    try:
        upgrade_history = list(
            SubscriptionUpgradeLog.objects.filter(company=company)
            .select_related('from_plan', 'to_plan')[:8]
        )
    except (OperationalError, ProgrammingError) as exc:
        log.warning('saas_upgrade_history_query_failed: %s', exc)
        upgrade_history = []

    return {
        'saas': snap,
        'saas_snapshot': snap,
        'plan_cards': cards,
        'plans_available': len(cards) > 0,
        'pending_enterprise': pending_enterprise,
        'upgrade_history': upgrade_history,
    }


def build_plan_page_context_safe(company: Company) -> tuple[dict, str | None]:
    """
    Construye contexto de planes; retorna (contexto, mensaje_error|None).
    Nunca deja la vista sin contexto mínimo.
    """
    try:
        return build_plan_page_context(company), None
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        log.error(
            'saas_plan_page_db_error company_id=%s: %s',
            company.pk,
            exc,
            exc_info=True,
        )
        err = 'database_schema'
    except Exception as exc:
        log.error(
            'saas_plan_page_unexpected company_id=%s: %s',
            company.pk,
            exc,
            exc_info=True,
        )
        err = 'unexpected'

    ensure_default_plans()
    return {
        'saas': None,
        'saas_snapshot': None,
        'plan_cards': [],
        'plans_available': False,
        'pending_enterprise': None,
        'upgrade_history': [],
        'saas_degraded': True,
    }, err


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
