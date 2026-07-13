"""
=============================================================================
TRADEFLOW COLÓN — core/utils/seller_lifecycle.py
=============================================================================
Ciclo de vida de suscripciones seller: trial gratuito, recomendación de plan
por volumen, gracia post-trial y baja media (churn).

CONTEXTO DE NEGOCIO
-------------------
Los vendedores nuevos reciben 30 días de prueba en el plan **Digitalízate**
sin cobro. Al vencer el trial:

1. Se calcula el volumen USD facturable vendido durante el periodo de prueba.
2. Se recomienda un plan mínimo según umbrales comerciales acordados.
3. La cuenta entra en **past_due** con 7 días de gracia para activar un plan
   igual o superior al recomendado (pago mock/banco en MVP; Stripe en fase 3b).
4. Si no pagan en la gracia, se aplica **baja media**: portal bloqueado,
   productos desactivados y empresa fuera del catálogo/mapa (datos en BD).

ESTADOS DE CompanySubscription.status
---------------------------------------
- ``trialing``  — Prueba Digitalízate vigente (días 0–30).
- ``active``    — Plan pagado y renovable.
- ``past_due``  — Trial vencido; gracia de activación (días 31–37).
- ``cancelled`` — Baja media; requiere reactivación comercial o nuevo pago.

INTEGRACIÓN
-----------
- ``start_seller_trial()`` — llamado al completar wizard de empresa.
- ``finalize_trial_period()`` — job diario al día 30.
- ``apply_medium_churn()`` — job diario al día 37 o "No continuar".
- ``seller_portal_access()`` — usado por ``seller_required`` decorator.
- ``company_marketplace_visible()`` — catálogo, mapa, merchandising.

CONFIGURACIÓN (settings.py)
-----------------------------
- ``SELLER_TRIAL_DAYS`` — duración del trial (default 30).
- ``SELLER_GRACE_DAYS`` — días de gracia post-trial (default 7).

AUDITORÍA
---------
Cambios de plan y pagos se registran en ``SubscriptionUpgradeLog`` y
``CompanyPlanCheckout`` (ver ``core/utils/saas_billing.py``).
=============================================================================
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
# Umbrales de recomendación post-trial (USD facturable en el periodo trial)
# -----------------------------------------------------------------------------
# Regla de negocio acordada con producto:
#   0 USD          → Digitalízate (sin ventas)
#   0.01–12 000    → Digitalízate
#   12 001–40 000  → Expansión
#   40 001–100 000 → Corporativo Pro
#   > 100 000      → Ecosistema Enterprise (CTA comercial, sin self-serve)
VOLUME_THRESHOLD_DIGITALIZATE_MAX = Decimal('12000.00')
VOLUME_THRESHOLD_EXPANSION_MAX = Decimal('40000.00')
VOLUME_THRESHOLD_CORPORATIVO_MAX = Decimal('100000.00')

# Slugs oficiales de planes (deben existir en SaasPlan tras ensure_default_plans).
PLAN_SLUG_DIGITALIZATE = 'digitalizate'
PLAN_SLUG_EXPANSION = 'expansion'
PLAN_SLUG_CORPORATIVO = 'corporativo_pro'
PLAN_SLUG_ENTERPRISE = 'ecosistema_enterprise'

# Estados que permiten visibilidad en marketplace público (incluye gracia).
MARKETPLACE_VISIBLE_STATUSES = ('trialing', 'past_due', 'active')

# Rutas del portal seller permitidas durante gracia (past_due).
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
    """Días de prueba gratuita Digitalízate (configurable vía SELLER_TRIAL_DAYS)."""
    return int(getattr(settings, 'SELLER_TRIAL_DAYS', 30))


def seller_grace_days() -> int:
    """Días de gracia post-trial antes de baja media (SELLER_GRACE_DAYS)."""
    return int(getattr(settings, 'SELLER_GRACE_DAYS', 7))


def recommend_plan_slug(volume_usd: Decimal) -> str:
    """
    Devuelve el slug del plan mínimo recomendado según volumen USD del trial.

    Args:
        volume_usd: Suma de ``OrderItem.line_total`` en estados facturables
            durante el periodo de prueba. Debe ser >= 0.

    Returns:
        str: Slug de ``SaasPlan`` (digitalizate, expansion, corporativo_pro,
            ecosistema_enterprise).

    Notas:
        - Volumen 0 → Digitalízate (seller sin ventas en trial).
        - Enterprise (>100k) requiere activación comercial, no checkout self-serve.
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
    """
    Calcula volumen USD y conteo de órdenes facturables durante el trial.

    Args:
        company: Empresa vendedora.
        sub: Suscripción en estado ``trialing`` o recién finalizada; usa
            ``current_period_start`` y ``current_period_end`` como ventana.

    Returns:
        tuple[Decimal, int]: (volumen_usd, cantidad_órdenes_distintas).
    """
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
    """
    Inicia el periodo de prueba Digitalízate para una empresa recién vinculada.

    Idempotente: si ya existe suscripción, no sobrescribe una activa o en trial.

    Args:
        company: Empresa con ``owner`` asignado (post-wizard).

    Returns:
        CompanySubscription: Registro con ``status=trialing``, ``auto_renew=False``.

    Raises:
        ValueError: Si la empresa ya tiene suscripción no cancelada incompatible.
    """
    ensure_default_plans()
    digitalizate = SaasPlan.objects.get(slug=PLAN_SLUG_DIGITALIZATE)
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
            # Reactivación desde cancelled: reiniciar trial comercial según política.
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
    """
    Cierra el trial al vencer ``current_period_end`` sin pago previo.

    Acciones:
    1. Calcula volumen trial y plan recomendado.
    2. Guarda snapshot en ``trial_volume_usd`` y FK ``recommended_plan``.
    3. Cambia ``status`` a ``past_due``.
    4. Establece ``grace_ends_at = now + SELLER_GRACE_DAYS``.

    Args:
        company: Empresa con suscripción ``trialing`` vencida.

    Returns:
        CompanySubscription actualizada, o None si no aplica (ya active/past_due).
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
    """
    Aplica baja media: cuenta inactiva, productos fuera del marketplace.

    Acciones:
    - ``subscription.status = cancelled``
    - ``Product.is_active = False`` para todos los productos de la empresa
    - Opcional: ``Company.is_verified = False`` (preserva datos en BD)

    Args:
        company: Empresa en ``past_due`` con gracia vencida, o cancelación voluntaria.

    Returns:
        CompanySubscription actualizada, o None si no había suscripción.
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
    """
    Indica si la empresa debe aparecer en catálogo, mapa y merchandising.

    Reglas:
    - Sin suscripción SaaS: **visible** (empresas legacy del catálogo seed /
      demo sin portal seller aún vinculado).
    - ``trialing``, ``active``: visible.
    - ``past_due``: visible mientras ``grace_ends_at >= now`` (días 31–37).
    - ``cancelled``: no visible (baja media).

    Args:
        company: Empresa vendedora.
        now: Timestamp de referencia (útil en tests).

    Returns:
        bool: True si productos activos de la empresa pueden mostrarse al público.
    """
    now = now or timezone.now()
    try:
        sub = company.subscription
    except CompanySubscription.DoesNotExist:
        # Grandfather: catálogo seed / empresas sin funnel seller siguen visibles.
        return True

    if sub.status not in MARKETPLACE_VISIBLE_STATUSES:
        return False

    if sub.status == 'past_due':
        if sub.grace_ends_at and sub.grace_ends_at < now:
            return False

    return True


def marketplace_active_company_ids(*, now=None) -> list[int]:
    """
    IDs de empresas visibles en superficies públicas del marketplace.

    Incluye:
    - Empresas **sin** ``CompanySubscription`` (legacy / seed).
    - Empresas con status trialing | active.
    - Empresas past_due aún dentro de gracia.

    Excluye ``cancelled`` y gracia vencida.
    """
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


def seller_portal_access(company: Company | None, *, route_name: str = '') -> str | None:
    """
    Determina si el vendedor puede acceder a la ruta solicitada del portal.

    Args:
        company: Empresa del seller (None si aún no completó wizard).
        route_name: Nombre de ruta Django de la vista actual.

    Returns:
        str | None: Nombre de ruta de redirect, o None si el acceso está permitido.

    Matriz de acceso:
    - Sin empresa → ``seller_onboarding_company``
    - ``trialing`` / ``active`` → acceso completo (None)
    - ``past_due`` → solo rutas en GRACE_PERIOD_ROUTE_NAMES
    - ``cancelled`` → ``seller_account_inactive``
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

    # trialing y active: acceso completo
    return None


def trial_days_remaining(sub: CompanySubscription, *, now=None) -> int:
    """Días enteros restantes de trial (0 si ya venció)."""
    now = now or timezone.now()
    if sub.status != 'trialing':
        return 0
    delta = sub.current_period_end - now
    return max(0, delta.days)


def grace_days_remaining(sub: CompanySubscription, *, now=None) -> int:
    """Días enteros restantes de gracia post-trial (0 si no aplica)."""
    now = now or timezone.now()
    if sub.status != 'past_due' or not sub.grace_ends_at:
        return 0
    delta = sub.grace_ends_at - now
    return max(0, delta.days)


def build_trial_activation_context(company: Company) -> dict:
    """
    Contexto para la pantalla de activación post-trial (seller_trial_activation).

    Incluye volumen, plan recomendado, planes seleccionables y días de gracia.
    """
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
        # No downgrade: solo plan recomendado o superior (sort_order).
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
