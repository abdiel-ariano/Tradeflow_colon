"""Stripe-hosted Checkout for approved TradeFlow purchase orders.

The integration is intentionally restricted to Stripe test mode.  The cart
remains quote-first: buyers pay only after accepting a supplier quotation and
creating a purchase order with a final server-side total.
"""
from __future__ import annotations

import hashlib
import logging
import string
from decimal import Decimal, ROUND_HALF_UP

import stripe
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ..decorators import buyer_required
from ..models import Inventory, Order, Payment

log = logging.getLogger(__name__)


class StripeTestConfigurationError(RuntimeError):
    """Raised when Stripe sandbox configuration is missing or unsafe."""


def stripe_test_checkout_enabled() -> bool:
    """Return whether the test-only Checkout integration can be displayed."""
    key = getattr(settings, 'STRIPE_TEST_SECRET_KEY', '').strip()
    return bool(
        getattr(settings, 'STRIPE_TEST_MODE', False)
        and key.startswith(('sk_test_', 'rk_test_'))
    )


def _stripe_client() -> stripe.StripeClient:
    """Create an isolated Stripe client and reject live credentials."""
    key = getattr(settings, 'STRIPE_TEST_SECRET_KEY', '').strip()
    if not getattr(settings, 'STRIPE_TEST_MODE', False):
        raise StripeTestConfigurationError('Stripe test checkout is disabled.')
    if not key.startswith(('sk_test_', 'rk_test_')):
        raise StripeTestConfigurationError(
            'Stripe test checkout requires an sk_test_ or rk_test_ key.',
        )
    return stripe.StripeClient(key, max_network_retries=2)


def _stripe_options(*, idempotency_key: str | None = None) -> dict:
    """Build per-request Stripe options with the pinned API version."""
    options = {
        'stripe_version': getattr(
            settings,
            'STRIPE_API_VERSION',
            '2026-07-29.dahlia',
        ),
    }
    if idempotency_key:
        options['idempotency_key'] = idempotency_key
    return options


def _object_value(obj, name, default=None):
    """Read a StripeObject or dict value without trusting redirect data."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _metadata_value(session, name, default=None):
    """Read one metadata value from a Stripe Checkout Session."""
    metadata = _object_value(session, 'metadata', {}) or {}
    if isinstance(metadata, dict):
        return metadata.get(name, default)
    return getattr(metadata, name, default)


def _money_to_minor_units(amount: Decimal) -> int:
    """Convert a two-decimal Decimal amount to Stripe minor units."""
    return int(
        (Decimal(amount) * Decimal('100')).quantize(
            Decimal('1'),
            rounding=ROUND_HALF_UP,
        ),
    )


def _integration_identifier(payment: Payment) -> str:
    """Return a stable identifier ending in eight pseudorandom letters."""
    source = f'{settings.SECRET_KEY}:{payment.pk}'.encode('utf-8')
    digest = hashlib.sha256(source).digest()
    suffix = ''.join(string.ascii_lowercase[byte % 26] for byte in digest[:8])
    return f'tradeflow_order_{suffix}'


def _checkout_line_items(order: Order) -> list[dict]:
    """Build Checkout line items from immutable order price snapshots."""
    order_items = list(order.items.select_related('product').all())
    if not order_items:
        raise ValueError('The order has no products.')

    # Stripe recommends consolidating very large one-time carts.
    if len(order_items) > 95:
        line_items = [{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': f'TradeFlow order {order.order_number}'[:127],
                },
                'unit_amount': _money_to_minor_units(order.subtotal),
            },
            'quantity': 1,
        }]
    else:
        line_items = []
        for item in order_items:
            unit_amount = _money_to_minor_units(item.unit_price_snapshot)
            if unit_amount <= 0:
                raise ValueError('Every order line must have a positive price.')
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': item.product.name[:127],
                    },
                    'unit_amount': unit_amount,
                },
                'quantity': item.qty,
            })

    if order.shipping_cost > 0:
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': 'Shipping'},
                'unit_amount': _money_to_minor_units(order.shipping_cost),
            },
            'quantity': 1,
        })
    return line_items


def _payable_order(order_pk: int, buyer_id: int) -> Order:
    """Load a buyer-owned order whose supplier has accepted the terms."""
    return get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        pk=order_pk,
        buyer_id=buyer_id,
        status='pending',
        seller_confirmation_status='accepted',
    )


def _session_order_id(session) -> int:
    """Return the validated internal order id stored in session metadata."""
    raw_order_id = _metadata_value(session, 'order_id')
    try:
        return int(raw_order_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('Stripe session is missing a valid order id.') from exc


@transaction.atomic
def _record_paid_checkout(session) -> tuple[Order, bool]:
    """Idempotently mark a verified test Checkout Session as paid."""
    if _object_value(session, 'livemode') is not False:
        raise ValueError('Only Stripe test-mode sessions are accepted.')
    if _object_value(session, 'payment_status') != 'paid':
        raise ValueError('Stripe has not marked this Checkout Session as paid.')

    order_id = _session_order_id(session)
    order = (
        Order.objects.select_for_update()
        .prefetch_related('items__product')
        .get(pk=order_id)
    )

    reference = str(_object_value(session, 'client_reference_id', '') or '')
    if reference and reference != str(order.pk):
        raise ValueError('Stripe client reference does not match the order.')

    expected_amount = _money_to_minor_units(order.total)
    if _object_value(session, 'amount_total') != expected_amount:
        raise ValueError('Stripe amount does not match the order total.')
    if str(_object_value(session, 'currency', '')).lower() != 'usd':
        raise ValueError('Stripe currency does not match the order currency.')
    if order.seller_confirmation_status != 'accepted':
        raise ValueError('The supplier has not accepted this order.')
    if order.status not in ('pending', 'paid'):
        raise ValueError('The order is not payable.')

    payment, _ = Payment.objects.select_for_update().get_or_create(
        order=order,
        defaults={
            'provider': 'stripe',
            'status': 'pending',
            'amount': order.total,
            'currency': 'USD',
        },
    )
    if payment.provider != 'stripe':
        raise ValueError('The order already uses another payment method.')
    if payment.status == 'approved':
        return order, False

    for item in order.items.select_related('product').all():
        inventory = (
            Inventory.objects.select_for_update()
            .filter(product_id=item.product_id)
            .first()
        )
        if inventory is not None:
            inventory.confirm_sale(item.qty)

    payment.status = 'approved'
    payment.amount = order.total
    payment.currency = 'USD'
    payment.paid_at = timezone.now()
    payment.txn_ref = str(_object_value(session, 'id', ''))[:200]
    payment.save(
        update_fields=[
            'status',
            'amount',
            'currency',
            'paid_at',
            'txn_ref',
        ],
    )
    order.status = 'paid'
    order.save(update_fields=['status', 'updated_at'])
    return order, True


@buyer_required
@require_POST
def stripe_checkout_start(request, order_pk):
    """Create or resume a Stripe-hosted test Checkout Session."""
    order = _payable_order(order_pk, request.user.pk)

    try:
        client = _stripe_client()
    except StripeTestConfigurationError as exc:
        log.warning('Stripe test checkout configuration error: %s', exc)
        messages.error(request, 'Stripe test payment is not configured.')
        return redirect('detalle_mi_orden', pk=order.pk)

    payment, created = Payment.objects.get_or_create(
        order=order,
        defaults={
            'provider': 'stripe',
            'status': 'pending',
            'amount': order.total,
            'currency': 'USD',
        },
    )
    if not created and payment.provider != 'stripe':
        messages.error(request, 'This order already uses another payment method.')
        return redirect('detalle_mi_orden', pk=order.pk)
    if payment.status == 'approved' or order.status == 'paid':
        messages.info(request, 'This order has already been paid.')
        return redirect('detalle_mi_orden', pk=order.pk)

    if payment.txn_ref.startswith('cs_'):
        try:
            existing = client.v1.checkout.sessions.retrieve(
                payment.txn_ref,
                options=_stripe_options(),
            )
            if (
                _object_value(existing, 'status') == 'open'
                and _object_value(existing, 'url')
            ):
                return redirect(_object_value(existing, 'url'))
            if _object_value(existing, 'payment_status') == 'paid':
                _record_paid_checkout(existing)
                return redirect('detalle_mi_orden', pk=order.pk)
        except (stripe.StripeError, ValueError):
            log.info(
                'Could not resume Stripe test session for order %s.',
                order.order_number,
                exc_info=True,
            )

    params = {
        'mode': 'payment',
        'line_items': _checkout_line_items(order),
        'success_url': (
            request.build_absolute_uri(reverse('stripe_checkout_success'))
            + '?session_id={CHECKOUT_SESSION_ID}'
        ),
        'cancel_url': request.build_absolute_uri(
            reverse('detalle_mi_orden', args=[order.pk]),
        ) + '?stripe=cancelled',
        'client_reference_id': str(order.pk),
        'billing_address_collection': 'required',
        'submit_type': 'pay',
        'integration_identifier': _integration_identifier(payment),
        'metadata': {
            'order_id': str(order.pk),
            'order_number': order.order_number,
            'environment': 'test',
        },
        'payment_intent_data': {
            'metadata': {
                'order_id': str(order.pk),
                'order_number': order.order_number,
                'environment': 'test',
            },
        },
        'custom_text': {
            'submit': {
                'message': 'Stripe test mode: no real funds will be charged.',
            },
        },
    }
    if request.user.email:
        params['customer_email'] = request.user.email

    try:
        session = client.v1.checkout.sessions.create(
            params=params,
            options=_stripe_options(
                idempotency_key=(
                    f'tradeflow-order-{order.pk}-payment-{payment.pk}'
                ),
            ),
        )
    except stripe.StripeError:
        log.exception(
            'Stripe test Checkout Session creation failed for order %s.',
            order.order_number,
        )
        messages.error(
            request,
            'Stripe could not start the test payment. Please try again.',
        )
        return redirect('detalle_mi_orden', pk=order.pk)

    session_url = _object_value(session, 'url')
    session_id = str(_object_value(session, 'id', '') or '')
    if not session_url or not session_id.startswith('cs_'):
        log.error('Stripe returned an incomplete Checkout Session.')
        messages.error(request, 'Stripe returned an invalid test session.')
        return redirect('detalle_mi_orden', pk=order.pk)

    payment.txn_ref = session_id[:200]
    payment.amount = order.total
    payment.currency = 'USD'
    payment.status = 'pending'
    payment.save(
        update_fields=['txn_ref', 'amount', 'currency', 'status'],
    )
    return redirect(session_url)


@buyer_required
@require_GET
def stripe_checkout_success(request):
    """Verify a returned Checkout Session and show the paid order."""
    session_id = request.GET.get('session_id', '').strip()
    if not session_id.startswith('cs_'):
        messages.error(request, 'Stripe returned an invalid session.')
        return redirect('mis_ordenes')

    try:
        client = _stripe_client()
        session = client.v1.checkout.sessions.retrieve(
            session_id,
            options=_stripe_options(),
        )
        order_id = _session_order_id(session)
        get_object_or_404(Order, pk=order_id, buyer=request.user)
        order, changed = _record_paid_checkout(session)
    except StripeTestConfigurationError:
        messages.error(request, 'Stripe test payment is not configured.')
        return redirect('mis_ordenes')
    except stripe.StripeError:
        log.exception('Stripe test Checkout Session verification failed.')
        messages.error(request, 'Stripe could not verify the test payment.')
        return redirect('mis_ordenes')
    except (Order.DoesNotExist, ValueError):
        log.warning('Rejected invalid Stripe test Checkout return.', exc_info=True)
        messages.error(request, 'The Stripe test payment could not be validated.')
        return redirect('mis_ordenes')

    if changed:
        messages.success(request, 'Stripe test payment approved.')
    else:
        messages.info(request, 'Stripe test payment was already recorded.')
    return redirect('detalle_mi_orden', pk=order.pk)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Verify and process Stripe test Checkout events."""
    webhook_secret = getattr(
        settings,
        'STRIPE_TEST_WEBHOOK_SECRET',
        '',
    ).strip()
    if not getattr(settings, 'STRIPE_TEST_MODE', False) or not webhook_secret:
        return HttpResponse(status=503)

    signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            signature,
            webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)

    event_type = _object_value(event, 'type', '')
    if event_type in {
        'checkout.session.completed',
        'checkout.session.async_payment_succeeded',
    }:
        data = _object_value(event, 'data', {}) or {}
        session = _object_value(data, 'object')
        try:
            _record_paid_checkout(session)
        except (Order.DoesNotExist, ValueError):
            log.warning('Rejected invalid Stripe test webhook.', exc_info=True)
            return HttpResponse(status=400)

    return HttpResponse(status=200)
