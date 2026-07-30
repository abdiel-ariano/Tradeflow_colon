"""
Catálogo comercial de planes (copy y UX) — los límites USD viven solo en SaasPlan ORM.
"""
from __future__ import annotations

# Referencia autoritativa para asistente IA (Groq) y copy público de planes vendedor.
# Límites de Analítica IA: docs/ANALYTICS_AI_ENTITLEMENTS.md
# (código: core/utils/analytics_ai_entitlements.py).
SAAS_PLANS_AI_ROWS = (
    {
        'name': 'Digitalízate',
        'slug': 'digitalizate',
        'monthly_usd': 49,
        'commission': '5.0%',
        'billing_cap': 'Hasta USD 15,000 / mes',
        'access': (
            'Catálogo al 100% para Micro/PyMEs. Mapa digital con rastreo. '
            'Analítica IA Empresa: solo ventas propias; historial 6 meses, '
            '25 chats IA/día; forecast básico. Sin tope de filas. '
            'Sin benchmarks ni comparación con el mercado ZLC.'
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
            'agencias nacionales. TradeFlow Ads. Analítica IA Empresa ampliada: '
            'historial 12 meses, 50 chats IA/día; forecast. Sin tope de filas. '
            'Sigue sin benchmarks de mercado ZLC.'
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
            'Analítica IA Mercado: ventas propias + benchmarks anónimos ZLC; '
            'historial 18 meses, 80 chats IA/día. Sin tope de filas. '
            'Sin IA predictiva / cohortes / escenarios. '
            'Incluye 3 anuncios destacados mensuales fijos.'
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
            'multi-bodega y técnico 24/7. Analítica IA Ecosistema: mercado ZLC + '
            'predictiva + cohortes + escenarios; historial 36 meses, '
            '300 chats IA/día. Sin tope de filas '
            '(sin API de analytics por ahora). '
            'Máxima prioridad en búsquedas y 1 banner principal fijo mensual.'
        ),
    },
)


def build_saas_plans_ai_context() -> str:
    """Texto estructurado de planes para system prompts de Groq."""
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
            'IA Empresa: 6 meses · 25 chats/día (sin tope de filas)',
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
            'IA Empresa: 12 meses · 50 chats/día (sin tope de filas)',
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
            'IA Mercado ZLC: 18 meses · 80 chats/día',
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
            'IA Ecosistema: 36 meses · 300 chats/día',
            'Mercado ZLC + predictiva + cohortes + escenarios',
            'API enterprise y SLA dedicado',
            'Activación consultiva con ejecutivo',
            'Integración logística a medida',
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
        'analytics_ai_tier': getattr(plan, 'analytics_ai_tier', 'company'),
        'sort_order': plan.sort_order,
    }
