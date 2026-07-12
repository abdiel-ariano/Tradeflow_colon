"""
Filtros de plantilla para montos USD.
"""
from django import template

from core.utils.money_format import format_money_usd, quantize_money

register = template.Library()


@register.filter(name='money_usd')
def money_usd_filter(value):
    """``USD 1,234.56``"""
    return format_money_usd(value)


@register.filter(name='money_amount')
def money_amount_filter(value):
    """Solo número ``1,234.56`` (sin prefijo)."""
    return format_money_usd(value, include_prefix=False)


@register.filter(name='quantize_money')
def quantize_money_filter(value):
    """Quantize money filter."""
    return quantize_money(value)
