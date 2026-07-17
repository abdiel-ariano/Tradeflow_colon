"""Etiquetas cortas en español para ejes de gráficas de vendedor y admin.

Mantiene días de la semana y ventanas compactos (3 letras) para ejes SVG/canvas
del dashboard.
"""
from __future__ import annotations

import datetime as dt

# Python weekday(): Monday=0 … Sunday=6
WEEKDAY_LABELS_ES = ('LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM')


def chart_weekday_label(day_date: dt.date) -> str:
    """Devuelve la etiqueta de día de la semana en español (3 letras) para ``date``."""
    return WEEKDAY_LABELS_ES[day_date.weekday()]


def chart_axis_label(day_date: dt.date, *, dias: int) -> str:
    """Devuelve la etiqueta de eje según la ventana de gráfica solicitada."""
    if dias <= 7:
        return chart_weekday_label(day_date)
    return day_date.strftime('%d/%m')
