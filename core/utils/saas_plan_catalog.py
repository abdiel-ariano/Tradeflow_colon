"""Marketing copy for SaaS plans (limits stay in billing ORM).

UI and AI prompts show feature stories without leaking USD volume caps
that belong only in billing enforcement.
"""
from __future__ import annotations

# Authoritative copy for AI assistant (Groq) and public seller plan marketing.
SAAS_PLANS_AI_ROWS = (
    {
        'name': 'Digitalízate',
        'slug': 'digitalizate',
        'monthly_usd': 49,
        'commission': '5.0%',
        'billing_cap': 'Hasta USD 15,000 / mes',
        'access': (
            'Catálogo al 100% para Micro/PyMEs. Mapa digital con rastreo. '
            'Reporte básico de ventas propias y acceso al módulo promocional '
            "'Top 3 Buscados de la ZLC'."
        ),
    },
    {
        'name': 'Expansión',
        'slug': 'expansion',
        'monthly_usd': 149,
        'commission': '4.0%',
        'billing_cap': 'Hasta USD 50,000 / mes',
        'access': (
            'Catálogo al 100% para Empresas Medianas. Despacho en 1 clic a '
            'agencias nacionales. Desbloqueo del gestor TradeFlow Ads para '
            'comprar anuncios destacados.'
        ),
    },
    {
        'name': 'Corporativo Pro',
        'slug': 'corporativo_pro',
        'monthly_usd': 349,
        'commission': '3.5%',
        'billing_cap': 'Ilimitado',
        'access': (
            'Catálogo ilimitado. Automatización de guías y etiquetas de envío. '
            'Estudio de Mercado Completo de la ZLC. Incluye 3 anuncios destacados '
            'mensuales fijos.'
        ),
    },
    {
        'name': 'Ecosistema Enterprise',
        'slug': 'ecosistema_enterprise',
        'monthly_usd': 799,
        'commission': '3.0%',
        'billing_cap': 'Ilimitado',
        'access': (
            'Sincronización por API con el ERP interno de la empresa. Soporte '
            'multi-bodega y técnico 24/7. Máxima prioridad en búsquedas y 1 banner '
            'principal fijo mensual.'
        ),
    },
)


def build_saas_plans_ai_context() -> str:
    """Build structured plan text for Groq system prompts (no volume caps)."""
    lines = [
        'Seller SaaS plans for TradeFlow Colón (use ONLY these figures; do not invent prices):',
        '',
    ]
    for row in SAAS_PLANS_AI_ROWS:
        lines.extend([
            f"• {row['name']}",
            f"  - Fixed investment: USD {row['monthly_usd']} / month",
            f"  - Commission: {row['commission']}",
            f"  - Monthly billing cap: {row['billing_cap']}",
            f"  - Logistics, data & ads access: {row['access']}",
            '',
        ])
    lines.append(
        'To become a seller: business sign-up, access application if required, '
        'then activate a plan from the seller portal. '
        'Ecosistema Enterprise may require commercial approval.'
    )
    return '\n'.join(lines)


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
    """Merge SaasPlan ORM row with marketing copy for UI cards."""
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
