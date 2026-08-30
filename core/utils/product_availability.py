"""Public buyer availability labels without exposing exact inventory counts."""
from __future__ import annotations

from django.utils.translation import gettext as _

# Threshold aligned with legacy PDP/card low-stock styling.
LOW_STOCK_THRESHOLD = 5


def public_availability_status(available_qty: int) -> str:
    """Return a qualitative availability code for buyer-facing UI."""
    if available_qty <= 0:
        return 'out'
    if available_qty <= LOW_STOCK_THRESHOLD:
        return 'low'
    return 'ok'


def public_availability_label(available_qty: int) -> str:
    """Return a translated availability label without unit counts."""
    status = public_availability_status(available_qty)
    if status == 'out':
        return _('Out of stock')
    if status == 'low':
        return _('Limited availability')
    return _('In stock')


def public_availability_heading() -> str:
    """Translated column/field label for qualitative availability."""
    return _('Availability')
