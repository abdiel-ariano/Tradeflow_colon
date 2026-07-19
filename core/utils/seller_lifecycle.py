"""Trial de vendedor, gracia post-trial, recomendación de plan y churn.

Los vendedores ZLC nuevos obtienen 30 días en Digitalízate; la gracia sin pago
termina en churn medio (portal bloqueado, productos fuera del marketplace).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from core.enterprise_models import CompanySubscription, SaasPlan, SubscriptionUpgradeLog
from core.models import Company, OrderItem, Product
from core.utils.saas_billing import BILLABLE_ORDER_STATUSES, ensure_default_plans

log = logging.getLogger('tradeflow.seller_lifecycle')

# -----------------------------------------------------------------------------
# Post-trial recommendation thresholds (billable USD during the trial)
# -----------------------------------------------------------------------------
# Product-agreed recommendation bands:
#   0 USD          → Digitalízate (no sales)
#   0.01–12 000    → Digitalízate
#   12 001–40 000  → Expansión
#   40 001–100 000 → Corporativo Pro
#   > 100 000      → Ecosistema Enterprise (commercial CTA, no self-serve)
VOLUME_THRESHOLD_DIGITALIZATE_MAX = Decimal('12000.00')
VOLUME_THRESHOLD_EXPANSION_MAX = Decimal('40000.00')
VOLUME_THRESHOLD_CORPORATIVO_MAX = Decimal('100000.00')

# Slugs oficiales de planes (deben existir en SaasPlan tras ensure_default_plans).
PLAN_SLUG_DIGITALIZATE = 'digitalizate'
PLAN_SLUG_EXPANSION = 'expansion'
PLAN_SLUG_CORPORATIVO = 'corporativo_pro'
PLAN_SLUG_ENTERPRISE = 'ecosistema_enterprise'

# Statuses that allow public marketplace visibility (includes grace).
MARKETPLACE_VISIBLE_STATUSES = ('trialing', 'past_due', 'active')

# Seller portal routes allowed during grace (past_due).
# Cualquier otra ruta bajo /mi-tienda/ redirige a seller_trial_activation.
GRACE_PERIOD_ROUTE_NAMES = frozenset({
    'seller_trial_activation',
    'seller_plan_checkout',
    'seller_plan_checkout_pay',
    'seller_plan_checkout_resume',
    'seller_decline_continue',
    'logout',
    'logout_view',
})


def seller_trial_days() -> int:
    """Devuelve la duración del trial gratuito Digitalízate (SELLER_TRIAL_DAYS)."""
    return int(getattr(settings, 'SELLER_TRIAL_DAYS', 30))


def seller_grace_days() -> int:
    """Devuelve los días de gracia post-trial antes del churn medio."""
    return int(getattr(settings, 'SELLER_GRACE_DAYS', 7))


def recommend_plan_slug(volume_usd: Decimal) -> str:
    """Devuelve el slug mínimo de plan recomendado según el volumen facturable USD del trial.


    Cero ventas mapean a Digitalízate; >100k mapea a Enterprise (CTA comercial).
    """
    vol = Decimal(volume_usd or 0).quantize(Decimal('0.01'))
    if vol <= VOLUME_THRESHOLD_DIGITALIZATE_MAX:
        return PLAN_SLUG_DIGITALIZATE
    if vol <= VOLUME_THRESHOLD_EXPANSION_MAX:
        return PLAN_SLUG_EXPANSION
    if vol <= VOLUME_THRESHOLD_CORPORATIVO_MAX:
        return PLAN_SLUG_CORPORATIVO
    return PLAN_SLUG_ENTERPRISE


def compute_trial_volume(company: Company, sub: CompanySubscription) -> tuple[Decimal, int]:
    """Devuelve el volumen facturable USD y el conteo de pedidos distintos en la ventana del trial."""
    period_start = sub.current_period_start
    period_end = sub.current_period_end
    qs = OrderItem.objects.filter(
        product__company=company,
        order__created_at__gte=period_start,
        order__created_at__lte=period_end,
        order__status__in=BILLABLE_ORDER_STATUSES,
    )
    agg = qs.aggregate(vol=Sum('line_total'))
    vol = (agg['vol'] or Decimal('0.00')).quantize(Decimal('0.01'))
    orders = qs.values('order_id').distinct().count()
    return vol, orders


def start_seller_trial(company: Company) -> CompanySubscription:
    """Inicia el trial Digitalízate para una empresa recién vinculada.


    Idempotente para trialing/active/past_due; puede reiniciar trial desde cancelled.
    """
    ensure_default_plans()
    try:
        digitalizate = SaasPlan.objects.get(slug=PLAN_SLUG_DIGITALIZATE)
    except SaasPlan.DoesNotExist as exc:
        log.error('start_seller_trial_missing_plan company_id=%s', company.pk)
        raise ValueError('saas_plan_digitalizate_missing') from exc

    now = timezone.now()
    trial_end = now + timedelta(days=seller_trial_days())

    with transaction.atomic():
        try:
            existing = company.subscription
        except CompanySubscription.DoesNotExist:
            existing = None

        if existing:
            if existing.status in ('trialing', 'active', 'past_due'):
                log.info(
                    'start_seller_trial_skip company_id=%s status=%s',
                    company.pk,
                    existing.status,
                )
                return existing
            # Reactivation from cancelled: restart commercial trial per policy.
            existing.plan = digitalizate
            existing.status = 'trialing'
            existing.current_period_start = now
            existing.current_period_end = trial_end
            existing.auto_renew = False
            existing.trial_volume_usd = None
            existing.recommended_plan = None
            existing.grace_ends_at = None
            existing.upgraded_at = None
            existing.save()
            log.info('start_seller_trial_reactivated company_id=%s', company.pk)
            return existing

        sub = CompanySubscription.objects.create(
            company=company,
            plan=digitalizate,
            status='trialing',
            current_period_start=now,
            current_period_end=trial_end,
            auto_renew=False,
        )
        SubscriptionUpgradeLog.objects.create(
            company=company,
            from_plan=None,
            to_plan=digitalizate,
            source='self_serve',
            notes='trial_started',
        )
        log.info(
            'start_seller_trial_created company_id=%s ends_at=%s',
            company.pk,
            trial_end.isoformat(),
        )
        return sub


def finalize_trial_period(company: Company) -> CompanySubscription | None:
    """Cierra un trial vencido: captura volumen, recomienda plan y entra en gracia.


    Pone ``past_due`` y ``grace_ends_at`` cuando ``current_period_end`` ya pasó.
    """
    ensure_default_plans()
    try:
        sub = company.subscription
    except CompanySubscription.DoesNotExist:
        log.warning('finalize_trial_no_subscription company_id=%s', company.pk)
        return None

    if sub.status != 'trialing':
        return None

    now = timezone.now()
    if sub.current_period_end > now:
        return None

    volume, _orders = compute_trial_volume(company, sub)
    rec_slug = recommend_plan_slug(volume)
    recommended = SaasPlan.objects.get(slug=rec_slug)

    with transaction.atomic():
        sub.trial_volume_usd = volume
        sub.recommended_plan = recommended
        sub.status = 'past_due'
        sub.grace_ends_at = now + timedelta(days=seller_grace_days())
        sub.auto_renew = False
        sub.save(update_fields=[
            'trial_volume_usd',
            'recommended_plan',
            'status',
            'grace_ends_at',
            'auto_renew',
        ])

    log.info(
        'finalize_trial_period company_id=%s volume=%s recommended=%s grace_until=%s',
        company.pk,
        volume,
        rec_slug,
        sub.grace_ends_at.isoformat(),
    )
    return sub


def apply_medium_churn(company: Company) -> CompanySubscription | None:
    """Aplica churn medio: cancela sub, desactiva productos y limpia verificación.


    Conserva los datos de la empresa en BD pero quita visibilidad en el marketplace ZLC.
    """
    try:
        sub = company.subscription
    except CompanySubscription.DoesNotExist:
        return None

    if sub.status == 'cancelled':
        return sub

    with transaction.atomic():
        sub.status = 'cancelled'
        sub.auto_renew = False
        sub.save(update_fields=['status', 'auto_renew'])
        deactivated = Product.objects.filter(company=company, is_active=True).update(
            is_active=False,
        )
        if company.is_verified:
            company.is_verified = False
            company.save(update_fields=['is_verified'])

    log.info(
        'apply_medium_churn company_id=%s products_deactivated=%s',
        company.pk,
        deactivated,
    )
    return sub


def company_marketplace_visible(company: Company, *, now=None) -> bool:
    """Devuelve si la empresa puede aparecer en catálogo, mapa y merchandising.


    Empresas legadas sin suscripción siguen visibles; cancelled o gracia vencida no.
    """
    now = now or timezone.now()
    try:
        sub = company.subscription
    except CompanySubscription.DoesNotExist:
        # Grandfather: seed catalog / companies without seller funnel stay visible.
        return True

    if sub.status not in MARKETPLACE_VISIBLE_STATUSES:
        return False

    if sub.status == 'past_due':
        if sub.grace_ends_at and sub.grace_ends_at < now:
            return False

    return True


def marketplace_active_company_ids_uncached(*, now=None) -> list[int]:
    """Consulta ORM de IDs de empresas visibles (sin caché)."""
    now = now or timezone.now()
    cancelled_or_expired = Company.objects.filter(
        Q(subscription__status='cancelled')
        | Q(
            subscription__status='past_due',
            subscription__grace_ends_at__lt=now,
        )
    ).values_list('pk', flat=True)
    return list(
        Company.objects.exclude(pk__in=cancelled_or_expired).values_list('pk', flat=True)
    )


def marketplace_active_company_ids(*, now=None) -> list[int]:
    """Devuelve IDs de empresas visibles (caché corta vía tradeflow_cache)."""
    if now is not None:
        return marketplace_active_company_ids_uncached(now=now)
    from core.utils.tradeflow_cache import cached_marketplace_active_company_ids

    return cached_marketplace_active_company_ids()


def seller_portal_access(company: Company | None, *, route_name: str = '') -> str | None:
    """Devuelve un nombre de ruta de redirección, o None si el acceso al portal está permitido.


    Los vendedores ``past_due`` solo pueden llegar a rutas de activación/checkout de gracia.
    """
    if not company:
        return 'seller_onboarding_company'

    try:
        sub = company.subscription
    except CompanySubscription.DoesNotExist:
        return 'seller_onboarding_company'

    if sub.status == 'cancelled':
        if route_name == 'seller_account_inactive':
            return None
        return 'seller_account_inactive'

    if sub.status == 'past_due':
        if route_name in GRACE_PERIOD_ROUTE_NAMES:
            return None
        return 'seller_trial_activation'

    # trialing and active: full access
    return None


def mark_paid_period_elapsed(company) -> CompanySubscription | None:
    """Mueve periodos active vencidos a past_due con gracia para renovación bancaria."""
    try:
        sub = company.subscription
    except CompanySubscription.DoesNotExist:
        return None

    now = timezone.now()
    if sub.status != 'active' or sub.current_period_end > now:
        return None

    with transaction.atomic():
        sub.status = 'past_due'
        sub.recommended_plan = sub.plan
        sub.grace_ends_at = now + timedelta(days=seller_grace_days())
        sub.auto_renew = False
        sub.save(update_fields=[
            'status', 'recommended_plan', 'grace_ends_at', 'auto_renew',
        ])

    log.info(
        'paid_period_elapsed company_id=%s plan=%s grace_until=%s',
        company.pk,
        sub.plan.slug,
        sub.grace_ends_at.isoformat(),
    )
    return sub


def trial_days_remaining(sub: CompanySubscription, *, now=None) -> int:
    """Devuelve días enteros restantes de trial (0 si no está en trial)."""
    now = now or timezone.now()
    if sub.status != 'trialing':
        return 0
    delta = sub.current_period_end - now
    return max(0, delta.days)


def grace_days_remaining(sub: CompanySubscription, *, now=None) -> int:
    """Devuelve días enteros restantes de gracia post-trial (0 si no aplica)."""
    now = now or timezone.now()
    if sub.status != 'past_due' or not sub.grace_ends_at:
        return 0
    delta = sub.grace_ends_at - now
    return max(0, delta.days)


def build_trial_activation_context(company: Company) -> dict:
    """Construye contexto para la pantalla de activación post-trial (planes seleccionables)."""
    from core.utils.saas_billing import plan_monthly_price
    from core.utils.saas_plan_catalog import marketing_for_plan

    ensure_default_plans()
    sub = company.subscription
    recommended = sub.recommended_plan or sub.plan
    rec_slug = recommended.slug
    volume = sub.trial_volume_usd or Decimal('0.00')

    plan_cards = []
    for plan in SaasPlan.objects.filter(is_active=True).order_by('sort_order'):
        marketing = marketing_for_plan(plan)
        is_recommended = plan.slug == rec_slug
        is_enterprise = marketing.get('cta') == 'commercial'
        # No downgrade: recommended plan or higher only (sort_order).
        can_select = plan.sort_order >= recommended.sort_order and not is_enterprise
        plan_cards.append({
            **marketing,
            'is_recommended': is_recommended,
            'can_select': can_select,
            'can_select_reason': (
                'Plan inferior al recomendado por tu volumen de ventas.'
                if not can_select and not is_enterprise
                else ''
            ),
            'monthly_price_usd': float(plan_monthly_price(plan.slug)),
        })

    return {
        'company': company,
        'subscription': sub,
        'trial_volume_usd': volume,
        'recommended_plan': recommended,
        'grace_days_left': grace_days_remaining(sub),
        'plan_cards': plan_cards,
    }
