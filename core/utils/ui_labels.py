"""Etiquetas visibles de estados y roles para la UI (gettext)."""
from __future__ import annotations

from django.utils.translation import gettext_lazy as _

ORDER_STATUS_LABELS = {
    'awaiting_seller': _('Awaiting seller'),
    'pending': _('Pending'),
    'paid': _('Paid'),
    'packed': _('Packed'),
    'shipped': _('Shipped'),
    'delivered': _('Delivered'),
    'cancelled': _('Cancelled'),
}

USER_ROLE_LABELS = {
    'buyer': _('Buyer'),
    'seller': _('Seller'),
    'admin': _('Administrator'),
}

VERIFICATION_STATUS_LABELS = {
    'pending': _('Pending review'),
    'verified': _('Verified'),
    'rejected': _('Requires correction'),
}


def order_status_label(status: str | None) -> str:
    if not status:
        return ''
    return str(ORDER_STATUS_LABELS.get(status, status.replace('_', ' ').title()))


def user_role_label(role: str | None) -> str:
    if not role:
        return ''
    return str(USER_ROLE_LABELS.get(role, role))


def verification_status_label(status: str | None) -> str:
    if not status:
        return ''
    return str(VERIFICATION_STATUS_LABELS.get(status, status))
