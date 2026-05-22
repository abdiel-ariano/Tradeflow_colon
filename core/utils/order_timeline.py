"""
Timeline logística para órdenes (seller / tracking).
"""
from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext as _


TIMELINE_STEPS = (
    ('received', _('Pedido recibido'), 'inbox'),
    ('processing', _('Procesando'), 'sync'),
    ('preparing', _('Preparando envío'), 'inventory_2'),
    ('in_transit', _('En camino'), 'local_shipping'),
    ('hub', _('En centro logístico'), 'warehouse'),
    ('delivered', _('Entregado'), 'check_circle'),
    ('cancelled', _('Cancelado'), 'cancel'),
)


def _step_index(status: str, shipment_status: str | None, cancelled: bool) -> int:
    if cancelled or status == 'cancelled':
        return 6
    mapping = {
        'awaiting_seller': 0,
        'pending': 1,
        'paid': 2,
        'packed': 2,
        'shipped': 3,
        'delivered': 5,
    }
    idx = mapping.get(status, 1)
    if status == 'shipped' and shipment_status == 'in_transit':
        idx = 4
    if status == 'shipped' and shipment_status == 'label':
        idx = 3
    return idx


def build_order_timeline(orden) -> dict:
    """Construye pasos del timeline con estado activo/completado."""
    shipment = getattr(orden, 'shipment', None)
    ship_st = shipment.status if shipment else None
    cancelled = orden.status == 'cancelled'
    active_idx = _step_index(orden.status, ship_st, cancelled)

    steps = []
    for i, (key, label, icon) in enumerate(TIMELINE_STEPS):
        if key == 'cancelled' and not cancelled:
            continue
        if key == 'cancelled':
            state = 'active' if cancelled else 'upcoming'
        elif i < active_idx:
            state = 'done'
        elif i == active_idx:
            state = 'active'
        else:
            state = 'upcoming'
        steps.append({
            'key': key,
            'label': str(label),
            'icon': icon,
            'state': state,
        })

    return {
        'order_id': orden.pk,
        'order_number': orden.order_number,
        'status': orden.status,
        'updated_at': orden.updated_at.isoformat() if orden.updated_at else None,
        'steps': steps,
    }
