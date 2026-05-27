"""
Etiquetas de eje X para gráficos (español, 3 letras mayúsculas).
"""
from __future__ import annotations

import datetime as dt

# Python weekday(): Monday=0 … Sunday=6
WEEKDAY_LABELS_ES = ('LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM')


def chart_weekday_label(day_date: dt.date) -> str:
    """Ej. JUE para un ``date``."""
    return WEEKDAY_LABELS_ES[day_date.weekday()]


def chart_axis_label(day_date: dt.date, *, dias: int) -> str:
    """
    Etiqueta de eje según ventana.

    - 7 días: LUN, MAR, MIÉ…
    - 30/90: dd/mm
    """
    if dias <= 7:
        return chart_weekday_label(day_date)
    return day_date.strftime('%d/%m')
