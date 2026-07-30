"""
Entitlements de Analítica IA por plan SaaS.

Tiers (sin API de analytics por ahora):
- company   → Digitalízate / Expansión: solo datos de la empresa
- market    → Corporativo Pro: empresa + benchmarks ZLC anónimos
- enterprise→ Ecosistema Enterprise: market + predictiva + cuotas altas

Documentación: docs/ANALYTICS_AI_ENTITLEMENTS.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

TIER_COMPANY = 'company'
TIER_MARKET = 'market'
TIER_ENTERPRISE = 'enterprise'

TIER_CHOICES = (
    (TIER_COMPANY, 'Company AI (own data only)'),
    (TIER_MARKET, 'Market AI (own + ZLC benchmarks)'),
    (TIER_ENTERPRISE, 'Ecosystem AI (market + predictive)'),
)

# Fallback por slug si el ORM aún no tiene analytics_ai_tier poblado.
PLAN_SLUG_TO_TIER = {
    'digitalizate': TIER_COMPANY,
    'expansion': TIER_COMPANY,
    'corporativo_pro': TIER_MARKET,
    'ecosistema_enterprise': TIER_ENTERPRISE,
}


@dataclass(frozen=True)
class AnalyticsAiEntitlement:
    """Límites y alcance de la IA de análisis para un plan.

    No hay tope de filas: se cargan todas las ventas dentro del historial del plan.
    """

    tier: str
    label: str
    history_months: int
    chat_per_day: int
    allow_market: bool
    allow_forecast: bool
    allow_predictive: bool
    allow_cohorts: bool
    allow_scenarios: bool


_ENTITLEMENTS: dict[str, AnalyticsAiEntitlement] = {
    TIER_COMPANY: AnalyticsAiEntitlement(
        tier=TIER_COMPANY,
        label='IA Empresa',
        history_months=6,
        chat_per_day=25,
        allow_market=False,
        allow_forecast=True,
        allow_predictive=False,
        allow_cohorts=False,
        allow_scenarios=False,
    ),
    TIER_MARKET: AnalyticsAiEntitlement(
        tier=TIER_MARKET,
        label='IA Mercado',
        history_months=18,
        chat_per_day=80,
        allow_market=True,
        allow_forecast=True,
        allow_predictive=False,
        allow_cohorts=False,
        allow_scenarios=False,
    ),
    TIER_ENTERPRISE: AnalyticsAiEntitlement(
        tier=TIER_ENTERPRISE,
        label='IA Ecosistema',
        history_months=36,
        chat_per_day=300,
        allow_market=True,
        allow_forecast=True,
        allow_predictive=True,
        allow_cohorts=True,
        allow_scenarios=True,
    ),
}

# Expansión: mismo alcance company, más historial y chat.
_EXPANSION_OVERRIDE = AnalyticsAiEntitlement(
    tier=TIER_COMPANY,
    label='IA Empresa',
    history_months=12,
    chat_per_day=50,
    allow_market=False,
    allow_forecast=True,
    allow_predictive=False,
    allow_cohorts=False,
    allow_scenarios=False,
)

_MARKET_INTENT_HINTS = (
    'mercado',
    'market',
    'zlc',
    'zona libre',
    'competidor',
    'competencia',
    'benchmark',
    'industria',
    'promedio del mercado',
    'otras empresas',
    'otros sellers',
    'categoría en la zlc',
)


def normalize_tier(raw: str | None) -> str:
    """Normalize unknown values to company."""
    if raw in _ENTITLEMENTS:
        return raw
    return TIER_COMPANY


def entitlement_for_tier(tier: str, *, plan_slug: str = '') -> AnalyticsAiEntitlement:
    """Resolve entitlement limits for a tier (+ Expansión override)."""
    tier = normalize_tier(tier)
    if plan_slug == 'expansion' and tier == TIER_COMPANY:
        return _EXPANSION_OVERRIDE
    return _ENTITLEMENTS[tier]


def tier_for_plan(plan) -> str:
    """Resolve analytics AI tier from SaasPlan instance or slug string."""
    if plan is None:
        return TIER_COMPANY
    if isinstance(plan, str):
        return PLAN_SLUG_TO_TIER.get(plan, TIER_COMPANY)
    stored = getattr(plan, 'analytics_ai_tier', None) or ''
    if stored in _ENTITLEMENTS:
        return stored
    return PLAN_SLUG_TO_TIER.get(getattr(plan, 'slug', ''), TIER_COMPANY)


def entitlement_for_company(company) -> AnalyticsAiEntitlement:
    """Entitlement for a seller company from its subscription plan."""
    from core.utils.saas_billing import subscription_usage_snapshot

    snap = subscription_usage_snapshot(company)
    plan = snap.get('plan')
    slug = getattr(plan, 'slug', '') if plan else ''
    return entitlement_for_tier(tier_for_plan(plan), plan_slug=slug)


def history_cutoff(ent: AnalyticsAiEntitlement):
    """Timezone-aware datetime cutoff for sales history."""
    return timezone.now() - timedelta(days=30 * int(ent.history_months))


def message_requests_market(message: str) -> bool:
    """Heuristic: user is asking for market / competitor context."""
    text = (message or '').strip().lower()
    if not text:
        return False
    return any(hint in text for hint in _MARKET_INTENT_HINTS)


def chat_quota_key(company_id: int) -> str:
    day = timezone.localdate().isoformat()
    return f'analytics:ai:chat:{company_id}:{day}'


def chat_used_today(company_id: int) -> int:
    return int(cache.get(chat_quota_key(company_id), 0) or 0)


def consume_chat_quota(company_id: int, ent: AnalyticsAiEntitlement) -> tuple[bool, int, int]:
    """
    Atomically-ish increment daily chat usage.

    Returns (allowed, used_after, limit).
    """
    key = chat_quota_key(company_id)
    used = chat_used_today(company_id)
    if used >= ent.chat_per_day:
        return False, used, ent.chat_per_day
    try:
        new_used = cache.incr(key)
    except ValueError:
        cache.set(key, used + 1, timeout=60 * 60 * 36)
        new_used = used + 1
    return True, int(new_used), ent.chat_per_day


def market_denied_message(ent: AnalyticsAiEntitlement) -> str:
    """User-facing upgrade hint when market questions are blocked."""
    return (
        f'Tu plan ({ent.label}) solo analiza datos de tu empresa. '
        'Para comparar ventas con el mercado general de la ZLC, '
        'actualiza a Corporativo Pro o Ecosistema Enterprise.'
    )


def chat_quota_denied_message(used: int, limit: int) -> str:
    return (
        f'Alcanzaste el límite diario de chat IA ({used}/{limit}). '
        'Vuelve mañana o actualiza tu plan para más capacidad.'
    )
