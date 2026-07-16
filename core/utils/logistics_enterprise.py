"""Dispatch CFZ shipments, logistics events, and signed webhooks.

Moves paid orders into packed/in-transit and notifies seller WMS
endpoints with SSRF-safe outbound validation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal

import urllib.request

from django.utils import timezone

from core.enterprise_models import LogisticsDispatchQueue, LogisticsEvent, LogisticsWebhookConfig
from core.models import Order, Shipment

log = logging.getLogger(__name__)


def record_logistics_event(order: Order, event_type: str, label: str = '', payload=None, source='system'):
    """Persist a logistics timeline event for the order."""
    return LogisticsEvent.objects.create(
        order=order,
        event_type=event_type,
        label=label or event_type,
        payload=payload or {},
        source=source,
    )


def sign_payload(secret: str, body: bytes) -> str:
    """Return HMAC-SHA256 hex signature for webhook body bytes."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def build_dispatch_payload(order: Order, company) -> dict:
    """Build JSON payload for a company order.dispatch webhook."""
    shipment = getattr(order, 'shipment', None)
    lines = list(
        order.items.filter(product__company=company).select_related('product')[:50]
    )
    return {
        'event': 'order.dispatch',
        'order_number': order.order_number,
        'order_id': order.pk,
        'status': order.status,
        'company_id': company.pk,
        'buyer': {
            'name': order.buyer.get_full_name() or order.buyer.username,
            'email': order.buyer.email,
        },
        'shipment': {
            'tracking': shipment.tracking_number if shipment else '',
            'weight_kg': str(shipment.weight_kg) if shipment and shipment.weight_kg else None,
            'warehouse': shipment.warehouse_code if shipment else '',
            'route': shipment.route_code if shipment else '',
        },
        'lines': [
            {'sku': li.product.sku, 'name': li.product.name, 'qty': li.qty}
            for li in lines
        ],
        'dispatched_at': timezone.now().isoformat(),
    }


def enqueue_dispatch(order: Order, company, actor_user=None) -> LogisticsDispatchQueue:
    """Queue dispatch, advance order/shipment, and POST signed webhook."""
    payload = build_dispatch_payload(order, company)
    body = json.dumps(payload, default=str).encode()
    webhook = (
        LogisticsWebhookConfig.objects.filter(company=company, is_active=True).first()
        or LogisticsWebhookConfig.objects.filter(company__isnull=True, is_active=True).first()
    )
    signature = ''
    if webhook:
        signature = sign_payload(webhook.signing_secret, body)

    dispatch = LogisticsDispatchQueue.objects.create(
        order=order,
        company=company,
        payload=payload,
        signature=signature,
    )
    record_logistics_event(
        order,
        'dispatched',
        label='Despacho iniciado',
        payload={'dispatch_id': dispatch.pk},
        source='seller',
    )
    if order.status == 'paid':
        order.status = 'packed'
        order.save(update_fields=['status', 'updated_at'])

    shipment, created = Shipment.objects.get_or_create(order=order)
    if not shipment.tracking_number:
        shipment.tracking_number = f'TF-{order.order_number}'
    shipment.status = 'in_transit'
    shipment.shipped_at = timezone.now()
    shipment.save(update_fields=['tracking_number', 'status', 'shipped_at'])

    _process_dispatch_queue(dispatch, webhook)
    return dispatch


def _process_dispatch_queue(dispatch: LogisticsDispatchQueue, webhook: LogisticsWebhookConfig | None):
    """POST the dispatch payload or mark sent when no webhook is configured."""
    if not webhook or not webhook.endpoint_url:
        dispatch.status = 'sent'
        dispatch.sent_at = timezone.now()
        dispatch.save(update_fields=['status', 'sent_at'])
        return

    # SSRF defense (OWASP A10:2021): the seller configures `endpoint_url`
    # freely. Validate it does not target private IPs, cloud metadata
    # services, sensitive ports, etc. BEFORE making the request.
    from django.core.exceptions import ValidationError as _ValidationError

    from core.utils.url_validator import validate_outbound_url

    try:
        validate_outbound_url(webhook.endpoint_url)
    except _ValidationError as exc:
        dispatch.attempts += 1
        dispatch.status = 'failed'
        dispatch.last_error = f'SSRF rechazado: {exc.message if hasattr(exc, "message") else exc}'[:500]
        dispatch.save(update_fields=['status', 'attempts', 'last_error'])
        log.warning(
            'Webhook URL bloqueada por SSRF guard webhook_id=%s url=%s reason=%s',
            webhook.pk, webhook.endpoint_url, dispatch.last_error,
        )
        return

    body = json.dumps(dispatch.payload, default=str).encode()
    try:
        req = urllib.request.Request(
            webhook.endpoint_url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'X-TradeFlow-Signature': dispatch.signature,
                'X-TradeFlow-Event': 'order.dispatch',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if 200 <= resp.status < 300:
                dispatch.status = 'sent'
                dispatch.sent_at = timezone.now()
            else:
                dispatch.status = 'failed'
                dispatch.last_error = f'HTTP {resp.status}'
        dispatch.attempts += 1
        dispatch.save(update_fields=['status', 'sent_at', 'attempts', 'last_error'])
    except Exception as exc:
        dispatch.attempts += 1
        dispatch.status = 'failed'
        dispatch.last_error = str(exc)[:500]
        dispatch.save(update_fields=['status', 'attempts', 'last_error'])
        log.exception('Webhook dispatch failed order=%s', dispatch.order_id)
