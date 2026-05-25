"""
Catálogo comercial de planes (copy y UX) — los límites USD viven solo en SaasPlan ORM.
"""
from __future__ import annotations

PLAN_MARKETING = {
    'digitalizate': {
        'tagline': 'Digitalización empresarial en la ZLC',
        'badge': '',
        'featured': False,
        'icon': 'storefront',
        'benefits': [
            'Catálogo digital completo y trazable',
            'Presencia B2B profesional en TradeFlow',
            'Ventas organizadas y confirmación empresarial',
            'Analytics operativos esenciales',
            'Crecimiento inicial dentro del ecosistema',
        ],
        'cta': 'activate',
        'tier_label': 'Inicio digital',
    },
    'expansion': {
        'tagline': 'Automatización y visibilidad comercial',
        'badge': 'Más popular',
        'featured': True,
        'icon': 'rocket_launch',
        'benefits': [
            'TradeFlow Ads y mayor visibilidad',
            'Despacho logístico en 1 clic',
            'Automatización de operaciones',
            'API para integraciones clave',
            'Escala tu volumen con confianza',
        ],
        'cta': 'activate',
        'tier_label': 'Recomendado',
    },
    'corporativo_pro': {
        'tagline': 'Inteligencia y operaciones avanzadas',
        'badge': 'Pro',
        'featured': False,
        'icon': 'insights',
        'benefits': [
            'Estudios de mercado y métricas profundas',
            'Webhooks logísticos a aliados',
            'Créditos publicitarios ampliados',
            'Soporte prioritario operativo',
            'Herramientas premium para tu equipo',
        ],
        'cta': 'activate',
        'tier_label': 'Operaciones Pro',
    },
    'ecosistema_enterprise': {
        'tagline': 'Estrategia corporativa y ecosistema completo',
        'badge': 'Enterprise',
        'featured': False,
        'icon': 'corporate_fare',
        'benefits': [
            'IA predictiva sobre tus datos reales',
            'API enterprise y SLA dedicado',
            'Activación consultiva con ejecutivo',
            'Integración logística a medida',
            'Preparado para expansión regional',
        ],
        'cta': 'commercial',
        'tier_label': 'Consultivo',
    },
}


def marketing_for_plan(plan) -> dict:
    """Fusiona SaasPlan ORM con copy comercial (sin exponer topes USD)."""
    base = PLAN_MARKETING.get(plan.slug, {})
    return {
        'slug': plan.slug,
        'name': plan.name,
        'tagline': base.get('tagline', plan.name),
        'badge': base.get('badge', ''),
        'featured': base.get('featured', False),
        'icon': base.get('icon', 'workspace_premium'),
        'benefits': base.get('benefits', []),
        'cta': base.get('cta', 'activate'),
        'tier_label': base.get('tier_label', ''),
        'ad_credits': plan.ad_credits_monthly,
        'has_api': plan.api_access,
        'has_webhooks': plan.logistics_webhooks,
        'has_predictive': plan.predictive_ai,
        'sort_order': plan.sort_order,
    }
