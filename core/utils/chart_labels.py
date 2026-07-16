"""Short Spanish axis labels for seller and admin chart widgets.

Keeps weekday and window labels compact (3-letter caps) for dashboard
SVG/canvas axes.
"""
from __future__ import annotations

import datetime as dt

# Python weekday(): Monday=0 … Sunday=6
WEEKDAY_LABELS_ES = ('LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM')


def chart_weekday_label(day_date: dt.date) -> str:
    """Return a 3-letter Spanish weekday label for ``date``."""
    return WEEKDAY_LABELS_ES[day_date.weekday()]


def chart_axis_label(day_date: dt.date, *, dias: int) -> str:
    """Return an axis label for the requested chart window."""
    if dias <= 7:
        return chart_weekday_label(day_date)
    return day_date.strftime('%d/%m')
