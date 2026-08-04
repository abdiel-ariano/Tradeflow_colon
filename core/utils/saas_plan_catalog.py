"""Authoritative commercial copy for TradeFlow seller SaaS plans.

The database fields enforce volume limits and feature access. This module owns
the English plan names, monthly prices, commissions, descriptions, and benefits
shown in the seller portal and supplied to the AI assistant.
"""
from __future__ import annotations

from decimal import Decimal


SAAS_PLANS_AI_ROWS = (
    {
        'name': 'Digitalize',
        'slug': 'digitalizate',
        'monthly_usd': Decimal('49.99'),
        'commission': '5%',
        'billing_cap': 'Up to USD 15,000 in monthly sales volume',
        'description': (
            'Digitalize provides the essential tools a company needs to start '
            'managing and selling online from one seller dashboard.'
        ),
        'benefits': (
            'Product and inventory management',
            'Orders, quotations, customers, and payments',
            'Basic sales reports',
            'Access to the promotional module',
            '50 TradeFlow Ads credits per month',
            'Up to USD 15,000 in monthly sales volume',
        ),
        'badge': '',
        'featured': False,
        'icon': 'storefront',
        'tier_label': 'Essential seller tools',
    },
    {
        'name': 'Expansion',
        'slug': 'expansion',
        'monthly_usd': Decimal('135.99'),
        'commission': '4%',
        'billing_cap': 'Up to USD 50,000 in monthly sales volume',
        'description': (
            'Expansion includes everything in Digitalize and adds more '
            'automation, commercial visibility, and operational capacity.'
        ),
        'benefits': (
            'Everything included in Digitalize',
            'Advanced customer and sales analytics',
            'TradeFlow Ads with 200 monthly credits',
            'One-click dispatch to national agencies',
            'Data management and report exports',
            'API access for business integrations',
            'Up to USD 50,000 in monthly sales volume',
        ),
        'badge': 'Most popular',
        'featured': True,
        'icon': 'rocket_launch',
        'tier_label': 'Automation and growth',
    },
    {
        'name': 'Corporate Pro',
        'slug': 'corporativo_pro',
        'monthly_usd': Decimal('230.99'),
        'commission': '3.5%',
        'billing_cap': 'Unlimited monthly sales volume',
        'description': (
            'Corporate Pro includes everything in Digitalize and Expansion. '
            'It is designed for companies that require advanced intelligence, '
            'integrations, and unrestricted growth.'
        ),
        'benefits': (
            'Everything included in Digitalize and Expansion',
            'Unlimited monthly sales volume',
            'Predictive sales insights powered by AI',
            'Advanced market studies and reporting',
            'API access and logistics webhooks',
            'Priority operational support',
            '500 TradeFlow Ads credits per month',
            'Three fixed featured ads every month',
        ),
        'badge': 'Advanced',
        'featured': False,
        'icon': 'insights',
        'tier_label': 'Intelligence and scale',
    },
)

PLAN_CATALOG_BY_SLUG = {
    row['slug']: row
    for row in SAAS_PLANS_AI_ROWS
}


def monthly_price_for_slug(slug: str) -> Decimal:
    """Return the official monthly USD price for a seller plan slug."""
    row = PLAN_CATALOG_BY_SLUG.get(slug)
    return row['monthly_usd'] if row else Decimal('0.00')


def build_saas_plans_ai_context() -> str:
    """Build the official seller-plan context supplied to the AI assistant."""
    lines = [
        'TradeFlow Colón offers exactly three tailored seller SaaS plans. '
        'Use only the figures and benefits below:',
        '',
    ]
    for row in SAAS_PLANS_AI_ROWS:
        lines.extend([
            f"• {row['name']}",
            f"  - Monthly subscription: USD {row['monthly_usd']:.2f}",
            f"  - Commission: {row['commission']}",
            f"  - Sales volume: {row['billing_cap']}",
            f"  - Positioning: {row['description']}",
            '  - Included features:',
        ])
        lines.extend(f'    • {benefit}' for benefit in row['benefits'])
        lines.append('')
    lines.append(
        'Expansion includes all Digitalize features. Corporate Pro includes '
        'all Digitalize and Expansion features. Upgrading never removes access.'
    )
    return '\n'.join(lines)


def marketing_for_plan(plan) -> dict:
    """Combine a SaaS plan row with authoritative English commercial copy."""
    base = PLAN_CATALOG_BY_SLUG.get(plan.slug, {})
    return {
        'slug': plan.slug,
        'name': base.get('name', plan.name),
        'tagline': base.get('description', plan.name),
        'description': base.get('description', plan.name),
        'commission': base.get('commission', ''),
        'billing_cap': base.get('billing_cap', ''),
        'badge': base.get('badge', ''),
        'featured': base.get('featured', False),
        'icon': base.get('icon', 'workspace_premium'),
        'benefits': list(base.get('benefits', ())),
        'cta': 'activate',
        'tier_label': base.get('tier_label', ''),
        'ad_credits': plan.ad_credits_monthly,
        'has_api': plan.api_access,
        'has_webhooks': plan.logistics_webhooks,
        'has_predictive': plan.predictive_ai,
        'has_priority_support': plan.priority_support,
        'sort_order': plan.sort_order,
    }
