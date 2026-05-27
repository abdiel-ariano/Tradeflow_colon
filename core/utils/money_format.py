"""
Formateo monetario unificado (USD, 2 decimales, sin float en negocio).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEY_QUANT = Decimal('0.01')


def quantize_money(value) -> Decimal:
    """Redondea a 2 decimales para montos USD."""
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
    """
    Devuelve ``USD 658,238.34`` (coma miles, punto decimal, un solo prefijo).

    Args:
        value: Monto numérico o Decimal.
        include_prefix: Si False, solo el número formateado.
    """
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
    """Serializa montos para Chart.js (máx. 2 decimales)."""
    return float(quantize_money(value))
