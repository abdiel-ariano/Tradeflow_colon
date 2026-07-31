"""Catálogo comercial y beneficios acumulativos de los planes SaaS.

Los precios y permisos operativos se definen en el módulo saas_billing. Este
módulo mantiene el texto comercial que consumen la pantalla de planes y el
asistente de inteligencia artificial.
"""
from __future__ import annotations


PLAN_ORDER = (
    "digitalizate",
    "expansion",
    "corporativo_pro",
)

SECTION_LABELS = {
    "administration": {
        "label": "Administración",
        "icon": "settings",
    },
    "sales": {
        "label": "Ventas",
        "icon": "trending_up",
    },
    "resources": {
        "label": "Recursos de la aplicación",
        "icon": "deployed_code",
    },
}

SAAS_PLANS_AI_ROWS = (
    {
        "name": "Digitalize",
        "slug": "digitalizate",
        "monthly_usd": "49.99",
        "commission": "5.0%",
        "billing_cap": "Hasta USD 15,000 / mes",
        "access": (
            "Operación esencial del catálogo, inventario, pedidos, "
            "cotizaciones, indicadores y 50 créditos TradeFlow Ads al mes."
        ),
    },
    {
        "name": "Expansion",
        "slug": "expansion",
        "monthly_usd": "135.99",
        "commission": "4.0%",
        "billing_cap": "Hasta USD 50,000 / mes",
        "access": (
            "Incluye Digitalize y agrega despacho logístico, acceso API, "
            "analítica ampliada y 200 créditos TradeFlow Ads al mes."
        ),
    },
    {
        "name": "Corporate Pro",
        "slug": "corporativo_pro",
        "monthly_usd": "230.99",
        "commission": "3.5%",
        "billing_cap": "Ilimitado",
        "access": (
            "Incluye Digitalize y Expansion; agrega analítica predictiva, "
            "webhooks logísticos, soporte prioritario y 500 créditos "
            "TradeFlow Ads al mes."
        ),
    },
)


PLAN_MARKETING = {
    "digitalizate": {
        "name": "Digitalize",
        "tagline": "Control esencial para iniciar la operación digital",
        "badge": "",
        "featured": False,
        "icon": "storefront",
        "tier_label": "Inicio digital",
        "includes_label": "Funciones esenciales para comenzar",
        "benefit_sections": {
            "administration": (
                "Centraliza productos e inventario en Mi Tienda.",
                "Gestiona pedidos y cotizaciones desde un solo portal.",
            ),
            "sales": (
                "Publica una vitrina B2B profesional en TradeFlow.",
                "Consulta indicadores operativos de tus ventas.",
            ),
            "resources": (
                "Opera hasta USD 15,000 de volumen mensual.",
                "Recibe 50 créditos TradeFlow Ads cada mes.",
            ),
        },
    },
    "expansion": {
        "name": "Expansion",
        "tagline": "Automatización y visibilidad para crecer",
        "badge": "Más popular",
        "featured": True,
        "icon": "rocket_launch",
        "tier_label": "Crecimiento",
        "includes_label": "Incluye todo Digitalize, más:",
        "benefit_sections": {
            "administration": (
                "Automatiza el despacho logístico en un clic.",
                "Conecta integraciones clave mediante la API.",
            ),
            "sales": (
                "Amplía la visibilidad con TradeFlow Ads.",
                "Profundiza el análisis de clientes y ventas.",
            ),
            "resources": (
                "Eleva el volumen mensual hasta USD 50,000.",
                "Recibe 200 créditos TradeFlow Ads cada mes.",
            ),
        },
    },
    "corporativo_pro": {
        "name": "Corporate Pro",
        "tagline": "Inteligencia y capacidad para operaciones avanzadas",
        "badge": "Máximo control",
        "featured": False,
        "icon": "insights",
        "tier_label": "Operación avanzada",
        "includes_label": "Incluye Digitalize y Expansion, más:",
        "benefit_sections": {
            "administration": (
                "Anticipa tendencias con analítica predictiva.",
                "Integra aliados mediante webhooks logísticos.",
                "Obtén soporte prioritario para la operación.",
            ),
            "sales": (
                "Accede a estudios de mercado y métricas avanzadas.",
                "Refuerza campañas con más recursos publicitarios.",
            ),
            "resources": (
                "Opera sin límite de volumen mensual.",
                "Recibe 500 créditos TradeFlow Ads cada mes.",
            ),
        },
    },
}


def build_saas_plans_ai_context() -> str:
    """Construye el contexto oficial de planes para los prompts de Groq."""
    lines = [
        (
            "Seller SaaS plans for TradeFlow Colón "
            "(use ONLY these figures; do not invent prices):"
        ),
        "",
    ]
    for row in SAAS_PLANS_AI_ROWS:
        lines.extend(
            [
                f"• {row['name']}",
                f"  - Fixed investment: USD {row['monthly_usd']} / month",
                f"  - Commission: {row['commission']}",
                f"  - Monthly billing cap: {row['billing_cap']}",
                f"  - Administration, sales and resources: {row['access']}",
                "",
            ]
        )
    lines.append(
        "To become a seller: complete the business registration and activate "
        "one of the three plans from the seller portal."
    )
    return "\n".join(lines)


def _build_benefit_sections(plan_slug: str) -> list[dict]:
    """Agrupa beneficios acumulados e identifica los propios del plan."""
    if plan_slug not in PLAN_ORDER:
        return []

    selected_index = PLAN_ORDER.index(plan_slug)
    included_slugs = PLAN_ORDER[: selected_index + 1]
    sections = []

    for section_key, section_meta in SECTION_LABELS.items():
        items = []
        for source_slug in included_slugs:
            source_plan = PLAN_MARKETING[source_slug]
            for benefit in source_plan["benefit_sections"][section_key]:
                items.append(
                    {
                        "text": benefit,
                        "is_new": source_slug == plan_slug,
                        "source_plan": source_plan["name"],
                    }
                )

        sections.append(
            {
                "key": section_key,
                "label": section_meta["label"],
                "icon": section_meta["icon"],
                "items": items,
            }
        )

    return sections


def marketing_for_plan(plan) -> dict:
    """Combina permisos ORM y beneficios acumulativos para una tarjeta."""
    base = PLAN_MARKETING.get(plan.slug, {})
    sections = _build_benefit_sections(plan.slug)
    benefits = [
        item["text"]
        for section in sections
        for item in section["items"]
    ]

    return {
        "slug": plan.slug,
        "name": base.get("name", plan.name),
        "tagline": base.get("tagline", plan.name),
        "badge": base.get("badge", ""),
        "featured": base.get("featured", False),
        "icon": base.get("icon", "workspace_premium"),
        "benefits": benefits,
        "benefit_sections": sections,
        "includes_label": base.get("includes_label", ""),
        "cta": "activate",
        "tier_label": base.get("tier_label", ""),
        "ad_credits": plan.ad_credits_monthly,
        "has_api": plan.api_access,
        "has_webhooks": plan.logistics_webhooks,
        "has_predictive": plan.predictive_ai,
        "sort_order": plan.sort_order,
    }
}
