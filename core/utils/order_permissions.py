"""
Centralized operational rules for orders (seller).
Prevents UI/backend drift and invalid actions.
"""
from __future__ import annotations

from django.utils.translation import gettext_lazy as _

TERMINAL_ORDER_STATUSES = frozenset({'cancelled', 'delivered'})
DISPATCH_ALLOWED_STATUSES = frozenset({'paid'})
CONFIRM_ALLOWED_STATUS = 'awaiting_seller'


def get_seller_order_actions(order, company) -> dict:
    """
    Returns UI flags and messages for the seller portal.

    Args:
        order: Order instance
        company: authenticated seller's Company
    """
    has_lines = order.items.filter(product__company=company).exists()
    if not has_lines:
        return _actions_false(_('This order does not include products from your company.'))

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
                f'Monthly plan limit reached (USD {exc.limit}). '
                f'This sale would add USD {exc.additional}.'
            )

    can_dispatch, dispatch_reason = _dispatch_permission(order, read_only, seller_st)

    if read_only:
        hint = _('Order is read-only (%(status)s).') % {
            'status': order.get_status_display(),
        }
    elif can_confirm:
        hint = _('Confirm or reject before shipping.')
    elif can_dispatch:
        hint = _('Ready for logistics dispatch.')
    elif order.status == 'packed':
        hint = _('Dispatch already recorded. See timeline for tracking.')
    elif seller_st == 'rejected':
        hint = _('Order rejected by your company.')
    elif seller_st == 'expired':
        hint = _('Confirmation deadline expired.')
    else:
        hint = dispatch_reason or _('No actions available for this status.')

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
        return False, _('The order is closed or cancelled.')
    if seller_st in ('rejected', 'expired'):
        return False, _('Cannot ship a rejected or expired order.')
    if seller_st == 'pending':
        return False, _('You must confirm the order before shipping.')
    if seller_st != 'accepted':
        return False, _('Seller confirmation still pending.')
    if order.status not in DISPATCH_ALLOWED_STATUSES:
        if order.status == 'packed':
            return False, _('Dispatch has already been started.')
        if order.status == 'awaiting_seller':
            return False, _('The order is still awaiting confirmation.')
        return False, _('Status %(status)s does not allow dispatch.') % {
            'status': order.get_status_display(),
        }
    shipment = getattr(order, 'shipment', None)
    if shipment and shipment.status == 'in_transit':
        return False, _('Shipment is already in transit.')
    return True, ''


def assert_can_dispatch(order, company) -> None:
    """Backend validation; raises PermissionError if the action is invalid."""
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
