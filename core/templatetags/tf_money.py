"""Template filters for USD money display on the marketplace.

Catalog cards, quotes, and seller dashboards share one formatter so
ZLC B2B prices stay consistent across locales.
"""
from django import template

from core.utils.money_format import format_money_usd, quantize_money

register = template.Library()


@register.filter(name='money_usd')
def money_usd_filter(value):
    """Format as ``USD 1,234.56`` for storefront and invoice UIs."""
    return format_money_usd(value)


@register.filter(name='money_amount')
def money_amount_filter(value):
    """Format the numeric amount only (no ``USD`` prefix)."""
    return format_money_usd(value, include_prefix=False)


@register.filter(name='quantize_money')
def quantize_money_filter(value):
    """Quantize a Decimal/string amount to marketplace money precision."""
    return quantize_money(value)
