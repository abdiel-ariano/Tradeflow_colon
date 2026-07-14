"""
=============================================================================
TRADEFLOW COLÓN — core/utils/saas_billing.py
=============================================================================
Facturación SaaS por empresa: planes, límites, uso mensual y checkout.

MODOS DE CHECKOUT (CheckoutMode)
---------------------------------
- ``trial_upgrade``    — Seller en trial elige plan superior (días 0–30).
- ``trial_activation`` — Post-trial en gracia; activa plan ≥ recomendado
  (permite pagar Digitalízate aunque ya esté en trial con ese slug).
- ``plan_upgrade``     — Cuenta active; upgrade a plan superior.

PAGOS (sin Stripe — flujo propio)
---------------------------------
- ``mock`` — Solo si ``ALLOW_MOCK_PLAN_PAYMENT`` / DEBUG: activación inmediata.
- ``bank`` — Transferencia: checkout queda ``pending`` hasta que un admin apruebe.
  El seller envía referencia (+ comprobante opcional); admin usa
  ``approve_plan_checkout`` / Django Admin.

Stripe no está habilitado en este producto.

SUSCRIPCIONES
-------------
No crear suscripciones ``active`` gratis automáticamente. El trial inicia en
``start_seller_trial()`` (wizard seller). Usar ``get_company_subscription()`` para
lectura segura; ``get_or_create_subscription()`` solo tras pago o trial explícito.
=============================================================================
"""
from __future__ import annotations

import enum
import logging
from calendar import monthrange
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
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

# Precio mensual de checkout — alineado con copy comercial (saas_plan_catalog.py).
PLAN_MRR_USD = {
    'digitalizate': Decimal('49'),
    'expansion': Decimal('149'),
    'corporativo_pro': Decimal('349'),
    'ecosistema_enterprise': Decimal('799'),
}


class CheckoutMode(enum.StrEnum):
    """
    Modo de sesión de pago según estado de la suscripción.

    Determina validaciones en ``create_plan_checkout`` y copy en la UI.
    """
    TRIAL_UPGRADE = 'trial_upgrade'
    TRIAL_ACTIVATION = 'trial_activation'
    PLAN_UPGRADE = 'plan_upgrade'


def resolve_checkout_mode(sub: CompanySubscription) -> CheckoutMode:
    """
    Infiere el modo de checkout según ``subscription.status``.

    Raises:
        ValueError: Si el estado no permite checkout self-serve.
    """
    if sub.status == 'trialing':
        return CheckoutMode.TRIAL_UPGRADE
    if sub.status == 'past_due':
        return CheckoutMode.TRIAL_ACTIVATION
    if sub.status == 'active':
        return CheckoutMode.PLAN_UPGRADE
    raise ValueError('checkout_not_allowed_for_status')


def get_company_subscription(company: Company) -> CompanySubscription | None:
    """Devuelve la suscripción existente o None (sin crear registros)."""
    try:
        return company.subscription
    except CompanySubscription.DoesNotExist:
        return None


def get_or_create_subscription(company: Company) -> CompanySubscription:
    """
    Obtiene la suscripción de la empresa.

    IMPORTANTE: ya no crea planes ``active`` gratis. El trial debe iniciarse con
    ``start_seller_trial()`` tras el wizard seller, o ``activate_company_plan()``
    tras un pago exitoso.

    Raises:
        CompanySubscription.DoesNotExist: Si la empresa no tiene suscripción.
    """
    sub = get_company_subscription(company)
    if sub is None:
        raise CompanySubscription.DoesNotExist(
            f'Company {company.pk} has no subscription. '
            'Use start_seller_trial() or complete a plan checkout first.'
        )
    return sub


def ensure_demo_subscription(
    company: Company,
    *,
    status: str = 'active',
    plan_slug: str = 'digitalizate',
) -> CompanySubscription:
    """
    Crea o actualiza suscripción para datos de demo / tests legacy.

    Uso exclusivo en ``cargar_demo`` y tests que necesitan empresa operativa
    sin pasar por el wizard completo.
    """
    ensure_default_plans()
    plan = SaasPlan.objects.get(slug=plan_slug)
    now = timezone.now()
    _, month_end = _period_bounds(now)
    sub = get_company_subscription(company)
    if sub:
        sub.plan = plan
        sub.status = status
        sub.current_period_start = now
        sub.current_period_end = month_end + timedelta(days=32)
        sub.auto_renew = status == 'active'
        sub.save()
        return sub
    return CompanySubscription.objects.create(
        company=company,
        plan=plan,
        status=status,
        current_period_start=now,
        current_period_end=month_end + timedelta(days=32),
        auto_renew=status == 'active',
    )


def can_select_plan_for_activation(
    company: Company,
    target_slug: str,
    *,
    mode: CheckoutMode | None = None,
) -> tuple[bool, str]:
    """
    Valida si el seller puede pagar ``target_slug`` según modo y recomendación.

    Regla crítica post-trial: ``target.sort_order >= recommended.sort_order``
    (no downgrade). Durante trial upgrade: solo planes superiores a Digitalízate.

    Returns:
        tuple[bool, str]: (permitido, mensaje_error_vacío_si_ok)
    """
    ensure_default_plans()
    sub = get_company_subscription(company)
    if not sub:
        return False, 'no_subscription'

    target = SaasPlan.objects.filter(slug=target_slug, is_active=True).first()
    if not target:
        return False, 'plan_not_found'

    from core.utils.saas_plan_catalog import marketing_for_plan

    if marketing_for_plan(target).get('cta') == 'commercial':
        return False, 'plan_requires_commercial'

    mode = mode or resolve_checkout_mode(sub)

    if mode == CheckoutMode.TRIAL_UPGRADE:
        if target.sort_order <= sub.plan.sort_order:
            return False, 'upgrade_requires_higher_plan'
        return True, ''

    if mode == CheckoutMode.TRIAL_ACTIVATION:
        recommended = sub.recommended_plan or sub.plan
        if target.sort_order < recommended.sort_order:
            return False, 'below_recommended_plan'
        return True, ''

    if mode == CheckoutMode.PLAN_UPGRADE:
        if target.sort_order <= sub.plan.sort_order:
            return False, 'upgrade_requires_higher_plan'
        return True, ''

    return False, 'invalid_mode'


def plan_monthly_price(slug: str) -> Decimal:
    """Plan monthly price."""
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
        ('digitalizate', 'Digitalize', Decimal('15000'), 50, False, False, False, 1),
        ('expansion', 'Expansion', Decimal('50000'), 200, True, False, False, 2),
        ('corporativo_pro', 'Corporate Pro', None, 500, True, True, False, 3),
        ('ecosistema_enterprise', 'Enterprise Ecosystem', None, 2000, True, True, True, 4),
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


def get_or_create_subscription_legacy(company: Company) -> CompanySubscription:
    """Alias retrocompatible: delega a ``ensure_demo_subscription`` para tests."""
    return ensure_demo_subscription(company)


def compute_monthly_volume(company: Company, now=None) -> tuple[Decimal, int]:
    """Volumen USD y conteo de órdenes del mes (líneas de la empresa)."""
    start, end = _period_bounds(now)
    qs = OrderItem.objects.filter(
        product__company=company,
        order__created_at__gte=start,
        order__created_at__lte=end,
        order__status__in=BILLABLE_ORDER_STATUSES,
    )
    agg = qs.aggregate(vol=Sum('line_total'))
    vol = agg['vol'] or Decimal('0.00')
    orders = qs.values('order_id').distinct().count()
    return vol.quantize(Decimal('0.01')), orders


def refresh_billing_usage(company: Company, now=None) -> CompanyBillingUsage:
    """Refresh billing usage."""
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
    sub = get_company_subscription(company)
    if not sub:
        ensure_default_plans()
        digitalizate = SaasPlan.objects.get(slug='digitalizate')
        return {
            'subscription': None,
            'plan': digitalizate,
            'usage': None,
            'volume_usd': Decimal('0.00'),
            'limit_usd': digitalizate.monthly_volume_limit_usd,
            'usage_pct': None,
            'warning': None,
            'is_unlimited': digitalizate.is_unlimited,
            'next_plan': None,
            'ad_credits_balance': digitalizate.ad_credits_monthly,
            'api_enabled': False,
            'webhooks_enabled': False,
            'predictive_ai_enabled': False,
            'volume_blocked': False,
            'growth_signal': 'optimal',
            'growth_message': 'Complete company setup to start your trial.',
            'meter_width_pct': None,
            'show_public_meter': False,
            'pending_checkout': None,
            'flow_steps': [],
            'journey_pct': 0,
            'activity_label': 'Setup pending',
            'trial_days_left': 0,
            'grace_days_left': 0,
            'subscription_status': None,
        }

    from core.utils.seller_lifecycle import grace_days_remaining, trial_days_remaining

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

    # Durante trial solo se ofrecen upgrades; en active el siguiente tier habitual.
    if sub.status == 'trialing':
        next_plan = (
            SaasPlan.objects.filter(sort_order__gt=plan.sort_order, is_active=True)
            .order_by('sort_order')
            .first()
        )
    else:
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
        'trial_days_left': trial_days_remaining(sub),
        'grace_days_left': grace_days_remaining(sub),
        'subscription_status': sub.status,
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
    source: str = 'checkout',
    notes: str = '',
    allow_same_plan: bool = False,
) -> CompanySubscription:
    """
    Activa plan tras pago exitoso o aprobación comercial.

    Efectos en la suscripción:
    - ``status = active``
    - ``auto_renew = True``
    - ``current_period_end = now + 30 días`` (ciclo mensual)
    - Limpia ``grace_ends_at`` y ``recommended_plan`` (fin de trial/gracia)
    - Registra ``SubscriptionUpgradeLog`` y recarga créditos ads

    Args:
        allow_same_plan: True en ``trial_activation`` cuando el recomendado es
            Digitalízate (mismo slug que el trial).
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
        if from_plan.pk == plan.pk and not allow_same_plan:
            if sub.status == 'active':
                return sub
            # Mismo plan pero activación desde trial/gracia → continuar abajo.

        now = timezone.now()
        sub.plan = plan
        sub.status = 'active'
        sub.auto_renew = True
        sub.upgraded_at = now
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.grace_ends_at = None
        sub.recommended_plan = None
        sub.save(update_fields=[
            'plan', 'status', 'auto_renew', 'upgraded_at',
            'current_period_start', 'current_period_end',
            'grace_ends_at', 'recommended_plan',
        ])
        SubscriptionUpgradeLog.objects.create(
            company=company,
            from_plan=from_plan,
            to_plan=plan,
            source=source if source in ('self_serve', 'checkout', 'commercial', 'admin') else 'checkout',
            notes=notes[:255],
        )
        ensure_ad_credits(company, plan.ad_credits_monthly)
        refresh_billing_usage(company)
    return sub


def create_plan_checkout(
    company: Company,
    plan_slug: str,
    *,
    mode: CheckoutMode | None = None,
) -> CompanyPlanCheckout:
    """
    Crea sesión de pago persistente (48h) según modo de checkout.

    Validaciones por modo — ver ``can_select_plan_for_activation``.
    """
    ensure_default_plans()
    from core.utils.saas_plan_catalog import marketing_for_plan

    plan = SaasPlan.objects.filter(slug=plan_slug, is_active=True).first()
    if not plan:
        raise ValueError('plan_not_found')
    if marketing_for_plan(plan).get('cta') == 'commercial':
        raise ValueError('plan_requires_commercial')

    sub = get_or_create_subscription(company)
    mode = mode or resolve_checkout_mode(sub)

    ok, err = can_select_plan_for_activation(company, plan_slug, mode=mode)
    if not ok:
        raise ValueError(err)

    # En upgrade/activation normal, mismo slug bloqueado salvo trial_activation.
    if (
        sub.plan.slug == plan_slug
        and mode != CheckoutMode.TRIAL_ACTIVATION
    ):
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
    """Get pending checkout."""
    return _safe_pending_checkout(company)


def allow_mock_plan_payment() -> bool:
    """
    True si se permite activar planes con tarjeta demo (mock).

    Producción: False (solo transferencia bancaria pending + admin).
    Local/CI: True vía DEBUG o ``ALLOW_MOCK_PLAN_PAYMENT=true``.
    """
    if getattr(settings, 'ALLOW_MOCK_PLAN_PAYMENT', None) is not None:
        return bool(settings.ALLOW_MOCK_PLAN_PAYMENT)
    return bool(getattr(settings, 'DEBUG', False))


def bank_transfer_instructions() -> dict:
    """Datos bancarios públicos para el checkout (config vía settings/.env)."""
    return {
        'bank_name': getattr(settings, 'SELLER_BANK_NAME', 'Banco General'),
        'account_name': getattr(settings, 'SELLER_BANK_ACCOUNT_NAME', 'TradeFlow Colón'),
        'account_number': getattr(settings, 'SELLER_BANK_ACCOUNT_NUMBER', ''),
        'account_type': getattr(settings, 'SELLER_BANK_ACCOUNT_TYPE', 'Corriente'),
        'swift': getattr(settings, 'SELLER_BANK_SWIFT', ''),
        'currency': getattr(settings, 'SELLER_BANK_CURRENCY', 'USD'),
        'instructions': getattr(
            settings,
            'SELLER_BANK_INSTRUCTIONS',
            'Transfiere el monto exacto e indica el número de referencia del checkout '
            'en el concepto. Un administrador confirmará el pago en 1–2 días hábiles.',
        ),
    }


def submit_bank_transfer_payment(
    checkout: CompanyPlanCheckout,
    *,
    transfer_reference: str,
    seller_notes: str = '',
    proof_file=None,
) -> CompanyPlanCheckout:
    """
    Registra la transferencia del seller. El checkout **permanece pending**.

    No activa el plan: eso lo hace ``approve_plan_checkout`` (admin).
    """
    from django.db import DatabaseError, IntegrityError

    if checkout.status != 'pending':
        raise ValueError('checkout_not_pending')

    ref = (transfer_reference or '').strip()
    if len(ref) < 4:
        raise ValueError('transfer_reference_required')

    company = checkout.company
    sub = get_company_subscription(company)
    if not sub:
        raise ValueError('no_subscription')

    mode = resolve_checkout_mode(sub)
    ok, err = can_select_plan_for_activation(
        company,
        checkout.target_plan.slug,
        mode=mode,
    )
    if not ok:
        raise ValueError(err)

    checkout.provider = 'bank'
    checkout.transfer_reference = ref[:120]
    checkout.seller_notes = (seller_notes or '')[:255]
    checkout.txn_ref = f'BANK-PENDING-{checkout.pk}'[:120]
    update_fields = [
        'provider', 'transfer_reference', 'seller_notes', 'txn_ref',
    ]

    # Comprobante es opcional: un fallo de Storage no debe tumbar todo el pago.
    max_proof = 5 * 1024 * 1024
    if proof_file and getattr(proof_file, 'size', 0):
        if proof_file.size > max_proof:
            log.warning(
                'bank_transfer_proof_too_large checkout_id=%s size=%s',
                checkout.pk,
                proof_file.size,
            )
            raise ValueError('proof_too_large')
        try:
            checkout.proof_file = proof_file
            update_fields.append('proof_file')
        except Exception as exc:
            log.warning(
                'bank_transfer_proof_assign_failed checkout_id=%s: %s',
                checkout.pk,
                exc,
            )

    try:
        checkout.save(update_fields=update_fields)
    except (OperationalError, ProgrammingError, DatabaseError, IntegrityError) as exc:
        # Si falla por el archivo, reintentar sin proof (texto de referencia sí importa).
        if 'proof_file' in update_fields:
            log.warning(
                'bank_transfer_save_with_proof_failed checkout_id=%s: %s — retry without proof',
                checkout.pk,
                exc,
            )
            checkout.proof_file = None
            update_fields = [
                'provider', 'transfer_reference', 'seller_notes', 'txn_ref',
            ]
            try:
                checkout.save(update_fields=update_fields)
            except (OperationalError, ProgrammingError, DatabaseError, IntegrityError) as exc2:
                log.exception(
                    'bank_transfer_save_failed checkout_id=%s: %s',
                    checkout.pk,
                    exc2,
                )
                raise ValueError('bank_transfer_save_failed') from exc2
        else:
            log.exception(
                'bank_transfer_save_failed checkout_id=%s: %s',
                checkout.pk,
                exc,
            )
            raise ValueError('bank_transfer_save_failed') from exc
    except Exception as exc:
        # Storage backends a veces lanzan OSError / ClientError fuera de DatabaseError.
        if 'proof_file' in update_fields:
            log.warning(
                'bank_transfer_storage_failed checkout_id=%s: %s — retry without proof',
                checkout.pk,
                exc,
            )
            try:
                checkout.proof_file = None
                checkout.save(update_fields=[
                    'provider', 'transfer_reference', 'seller_notes', 'txn_ref',
                ])
            except Exception as exc2:
                log.exception(
                    'bank_transfer_save_failed checkout_id=%s: %s',
                    checkout.pk,
                    exc2,
                )
                raise ValueError('bank_transfer_save_failed') from exc2
        else:
            log.exception(
                'bank_transfer_save_failed checkout_id=%s: %s',
                checkout.pk,
                exc,
            )
            raise ValueError('bank_transfer_save_failed') from exc

    log.info(
        'bank_transfer_submitted checkout_id=%s company_id=%s ref=%s',
        checkout.pk,
        company.pk,
        checkout.transfer_reference,
    )
    return checkout


def approve_plan_checkout(
    checkout: CompanyPlanCheckout,
    *,
    reviewed_by=None,
    review_notes: str = '',
) -> CompanySubscription:
    """
    Admin confirma transferencia recibida → marca paid y activa el plan.
    """
    if checkout.status != 'pending':
        raise ValueError('checkout_not_pending')
    if checkout.provider != 'bank' and not allow_mock_plan_payment():
        # Solo bank en producción; mock puede aprobarse en demo si quedó pending.
        if checkout.provider != 'mock':
            raise ValueError('checkout_provider_not_approvable')

    txn = checkout.transfer_reference or checkout.txn_ref or f'ADMIN-{checkout.pk}'
    sub = complete_plan_checkout(
        checkout,
        provider='bank' if checkout.provider == 'bank' else checkout.provider,
        txn_ref=txn,
    )
    checkout.refresh_from_db()
    checkout.reviewed_at = timezone.now()
    checkout.reviewed_by = reviewed_by
    checkout.review_notes = (review_notes or 'approved')[:255]
    checkout.save(update_fields=['reviewed_at', 'reviewed_by', 'review_notes'])
    log.info(
        'plan_checkout_approved checkout_id=%s by=%s',
        checkout.pk,
        getattr(reviewed_by, 'pk', None),
    )
    return sub


def reject_plan_checkout(
    checkout: CompanyPlanCheckout,
    *,
    reviewed_by=None,
    review_notes: str = '',
) -> CompanyPlanCheckout:
    """Admin rechaza comprobante/transferencia; el seller puede abrir un checkout nuevo."""
    if checkout.status != 'pending':
        raise ValueError('checkout_not_pending')
    checkout.status = 'rejected'
    checkout.reviewed_at = timezone.now()
    checkout.reviewed_by = reviewed_by
    checkout.review_notes = (review_notes or 'rejected')[:255]
    checkout.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'review_notes'])
    log.info(
        'plan_checkout_rejected checkout_id=%s by=%s',
        checkout.pk,
        getattr(reviewed_by, 'pk', None),
    )
    return checkout


def complete_plan_checkout(
    checkout: CompanyPlanCheckout,
    *,
    provider: str = 'mock',
    txn_ref: str = '',
) -> CompanySubscription:
    """
    Marca pago como exitoso y activa el plan objetivo.

    Re-valida permisos antes de activar (defensa en profundidad ante manipulación
    de formularios). Tras éxito: ``auto_renew=True`` y ciclo mensual de 30 días.
    """
    from django.db import transaction

    if checkout.status != 'pending':
        raise ValueError('checkout_not_pending')

    company = checkout.company
    sub = get_company_subscription(company)
    if not sub:
        raise ValueError('no_subscription')

    mode = resolve_checkout_mode(sub)
    ok, err = can_select_plan_for_activation(
        company,
        checkout.target_plan.slug,
        mode=mode,
    )
    if not ok:
        raise ValueError(err)

    allow_same = mode == CheckoutMode.TRIAL_ACTIVATION

    with transaction.atomic():
        checkout.status = 'paid'
        checkout.provider = provider
        checkout.txn_ref = (txn_ref or f'TF-{checkout.pk}-{timezone.now().strftime("%Y%m%d%H%M")}')[:120]
        checkout.paid_at = timezone.now()
        checkout.save(update_fields=['status', 'provider', 'txn_ref', 'paid_at'])
        return activate_company_plan(
            company,
            checkout.target_plan.slug,
            source='checkout',
            notes=f'checkout:{checkout.pk};provider:{provider}',
            allow_same_plan=allow_same,
        )


def build_checkout_context(company: Company, plan_slug: str) -> dict:
    """Contexto para pantalla de pago del plan."""
    from core.utils.saas_plan_catalog import marketing_for_plan

    ensure_default_plans()
    plan = SaasPlan.objects.get(slug=plan_slug, is_active=True)
    sub = get_or_create_subscription(company)
    mode = resolve_checkout_mode(sub)
    marketing = marketing_for_plan(plan)
    checkout = get_pending_checkout(company)
    if not checkout or checkout.target_plan_id != plan.pk:
        checkout = create_plan_checkout(company, plan_slug, mode=mode)

    return {
        'checkout': checkout,
        'target_plan': plan,
        'from_plan': sub.plan,
        'marketing': marketing,
        'amount': checkout.amount_usd,
        'saas': subscription_usage_snapshot(company),
        'checkout_mode': mode.value,
        'is_trial_activation': mode == CheckoutMode.TRIAL_ACTIVATION,
        'is_trial_upgrade': mode == CheckoutMode.TRIAL_UPGRADE,
        'allow_mock_payment': allow_mock_plan_payment(),
        'bank_transfer': bank_transfer_instructions(),
        'transfer_already_submitted': bool(checkout.transfer_reference),
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
    sub = snap.get('subscription')
    current_slug = snap['plan'].slug
    status = snap.get('subscription_status')
    recommended = sub.recommended_plan if sub else None

    cards = []
    for plan in SaasPlan.objects.filter(is_active=True).order_by('sort_order'):
        m = marketing_for_plan(plan)
        m['is_current'] = (
            plan.slug == current_slug and status == 'active'
        )
        # Trial: solo planes superiores a Digitalízate.
        if status == 'trialing':
            m['can_upgrade'] = plan.sort_order > snap['plan'].sort_order
        elif status == 'past_due' and recommended:
            m['can_upgrade'] = plan.sort_order >= recommended.sort_order
            m['is_recommended'] = plan.slug == recommended.slug
        else:
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
    sub = get_company_subscription(company)
    if not sub or sub.plan.is_unlimited:
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
    sub = get_company_subscription(company)
    if not sub or sub.plan.is_unlimited:
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
    """Plan allows feature."""
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
