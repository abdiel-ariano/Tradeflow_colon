"""Formatea montos USD para catálogo B2B ZLC y copy de correo.

Los precios del marketplace son USD; los helpers mantienen dos decimales
consistentes en plantillas y el asistente de IA.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEY_QUANT = Decimal('0.01')


def quantize_money(value) -> Decimal:
    """Redondea un valor a dos decimales para montos USD."""
    if value is None:
        return Decimal('0.00')
    if isinstance(value, Decimal):
        dec = value
    else:
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal('0.00')
    return dec.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def format_money_usd(value, *, include_prefix: bool = True) -> str:
    """Formatea un monto como cadena USD con dos decimales."""
    dec = quantize_money(value)
    sign = '-' if dec < 0 else ''
    dec = abs(dec)
    whole, cents = divmod(dec, 1)
    whole_int = int(whole)
    cents_str = f'{int((cents * 100).quantize(Decimal("1"))):02d}'
    whole_str = f'{whole_int:,}'
    body = f'{sign}{whole_str}.{cents_str}'
    if include_prefix:
        return f'USD {body}'
    return body


def money_to_chart_float(value) -> float:
    """Serializa un valor monetario como float para Chart.js (máx. dos decimales)."""
    return float(quantize_money(value))
