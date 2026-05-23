"""
Reglas centralizadas de acciones operacionales sobre órdenes (seller).
Evita desincronía UI/backend y acciones inválidas.
"""
from __future__ import annotations

from django.utils.translation import gettext_lazy as _

TERMINAL_ORDER_STATUSES = frozenset({'cancelled', 'delivered'})
DISPATCH_ALLOWED_STATUSES = frozenset({'paid'})
CONFIRM_ALLOWED_STATUS = 'awaiting_seller'


def get_seller_order_actions(order, company) -> dict:
    """
    Devuelve flags de UI y mensajes para el portal seller.

    Args:
        order: instancia Order
        company: Company del vendedor autenticado
    """
    has_lines = order.items.filter(product__company=company).exists()
    if not has_lines:
        return _actions_false(_('Esta orden no incluye productos de tu empresa.'))

    read_only = order.status in TERMINAL_ORDER_STATUSES
    seller_st = order.seller_confirmation_status

    can_reject = (
        not read_only
        and order.status == CONFIRM_ALLOWED_STATUS
        and seller_st == 'pending'
        and order.confirming_company_id == company.pk
    )
    can_confirm = can_reject
    confirm_block_reason = ''
    if can_confirm:
        from core.utils.saas_billing import order_company_subtotal, would_exceed_volume_limit

        exceeds, exc = would_exceed_volume_limit(
            company,
            order_company_subtotal(order, company),
        )
        if exceeds and exc:
            can_confirm = False
            confirm_block_reason = (
                f'Límite mensual del plan alcanzado (USD {exc.limit}). '
                f'Esta venta añadiría USD {exc.additional}.'
            )

    can_dispatch, dispatch_reason = _dispatch_permission(order, read_only, seller_st)

    if read_only:
        hint = _('Orden en solo lectura (%(status)s).') % {
            'status': order.get_status_display(),
        }
    elif can_confirm:
        hint = _('Confirma o rechaza antes de despachar.')
    elif can_dispatch:
        hint = _('Lista para despacho logístico.')
    elif order.status == 'packed':
        hint = _('Despacho ya registrado. Seguimiento en timeline.')
    elif seller_st == 'rejected':
        hint = _('Orden rechazada por tu empresa.')
    elif seller_st == 'expired':
        hint = _('Plazo de confirmación expirado.')
    else:
        hint = dispatch_reason or _('Sin acciones disponibles para este estado.')

    return {
        'can_confirm': can_confirm,
        'can_reject': can_reject,
        'can_dispatch': can_dispatch,
        'read_only': read_only,
        'status_hint': hint,
        'dispatch_block_reason': dispatch_reason,
        'confirm_block_reason': confirm_block_reason,
    }


def _dispatch_permission(order, read_only: bool, seller_st: str) -> tuple[bool, str]:
    if read_only:
        return False, _('La orden está cerrada o cancelada.')
    if seller_st in ('rejected', 'expired'):
        return False, _('No se puede despachar una orden rechazada o expirada.')
    if seller_st == 'pending':
        return False, _('Debes confirmar el pedido antes de despachar.')
    if seller_st != 'accepted':
        return False, _('Confirmación del vendedor pendiente.')
    if order.status not in DISPATCH_ALLOWED_STATUSES:
        if order.status == 'packed':
            return False, _('El despacho ya fue iniciado.')
        if order.status == 'awaiting_seller':
            return False, _('La orden aún espera confirmación.')
        return False, _('Estado %(status)s no permite despacho.') % {
            'status': order.get_status_display(),
        }
    shipment = getattr(order, 'shipment', None)
    if shipment and shipment.status == 'in_transit':
        return False, _('El envío ya está en tránsito.')
    return True, ''


def assert_can_dispatch(order, company) -> None:
    """Validación backend; lanza PermissionError si la acción no es válida."""
    actions = get_seller_order_actions(order, company)
    if not actions['can_dispatch']:
        raise PermissionError(actions['dispatch_block_reason'] or 'dispatch_not_allowed')


def _actions_false(reason: str) -> dict:
    return {
        'can_confirm': False,
        'can_reject': False,
        'can_dispatch': False,
        'read_only': True,
        'status_hint': reason,
        'dispatch_block_reason': reason,
    }
