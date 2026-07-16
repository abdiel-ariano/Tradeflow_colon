"""Build human-readable order progress steps for buyer/seller UI.

Maps CFZ order statuses to a linear timeline with current-step index.
"""
from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext as _


TIMELINE_STEPS = (
    ('received', _('Order received'), 'inbox'),
    ('processing', _('Processing'), 'sync'),
    ('preparing', _('Preparing shipment'), 'inventory_2'),
    ('dispatched', _('Shipped'), 'local_shipping'),
    ('in_transit', _('In transit'), 'delivery_truck_speed'),
    ('hub', _('At logistics hub'), 'warehouse'),
    ('delivered', _('Delivered'), 'check_circle'),
    ('incident', _('Incident'), 'warning'),
    ('cancelled', _('Cancelled'), 'cancel'),
)


def _step_index(status: str, shipment_status: str | None, cancelled: bool, has_dispatch: bool) -> int:
    """Return the timeline step index for an order status code."""
    if cancelled or status == 'cancelled':
        return 8
    mapping = {
        'awaiting_seller': 0,
        'pending': 1,
        'paid': 2,
        'packed': 3,
        'shipped': 5,
        'delivered': 7,
    }
    idx = mapping.get(status, 1)
    if status == 'packed' and has_dispatch:
        idx = 4
    if status == 'shipped' and shipment_status == 'in_transit':
        idx = 5
    if status == 'shipped' and shipment_status == 'label':
        idx = 4
    return idx


def build_order_timeline(orden) -> dict:
    """Construye pasos del timeline con estado activo/completado."""
    shipment = getattr(orden, 'shipment', None)
    ship_st = shipment.status if shipment else None
    cancelled = orden.status == 'cancelled'
    has_dispatch = orden.logistics_events.filter(event_type='dispatched').exists()
    has_incident = orden.logistics_events.filter(event_type='incident').exists()
    active_idx = _step_index(orden.status, ship_st, cancelled, has_dispatch)

    steps = []
    for i, (key, label, icon) in enumerate(TIMELINE_STEPS):
        if key == 'cancelled' and not cancelled:
            continue
        if key == 'incident' and not has_incident:
            continue
        if key == 'cancelled':
            state = 'active' if cancelled else 'upcoming'
        elif key == 'incident' and has_incident:
            state = 'active'
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

    extra_events = []
    for ev in orden.logistics_events.order_by('created_at')[:20]:
        extra_events.append({
            'type': ev.event_type,
            'label': ev.label,
            'at': ev.created_at.isoformat(),
            'source': ev.source,
        })

    return {
        'order_id': orden.pk,
        'order_number': orden.order_number,
        'status': orden.status,
        'updated_at': orden.updated_at.isoformat() if orden.updated_at else None,
        'steps': steps,
        'events': extra_events,
    }
