"""
API v1 enterprise — inventario, precios y auditoría.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from core.models import Product
from core.utils.api_enterprise import (
    SCOPE_INVENTORY_READ,
    SCOPE_PRICING_WRITE,
    audit_api_call,
    authenticate_api_key,
    require_scope,
)
from core.utils.saas_billing import plan_allows_feature


@require_http_methods(['GET'])
def api_v1_inventory(request):
    """JSON API endpoint: v1 inventory."""
    key, err = authenticate_api_key(request)
    if err:
        return err
    if not plan_allows_feature(key.company, 'api'):
        audit_api_call(key, key.company, request, 403)
        return JsonResponse({'error': 'plan_forbidden'}, status=403)
    if not require_scope(key, SCOPE_INVENTORY_READ):
        audit_api_call(key, key.company, request, 403)
        return JsonResponse({'error': 'scope_forbidden'}, status=403)

    products = Product.objects.filter(company=key.company).select_related('inventory')[:500]
    data = [
        {
            'id': p.pk,
            'sku': p.sku,
            'name': p.name,
            'active': p.is_active,
            'price': str(p.unit_price),
            'stock': p.inventory.stock_qty if hasattr(p, 'inventory') else 0,
        }
        for p in products
    ]
    audit_api_call(key, key.company, request, 200)
    return JsonResponse({'products': data})


@require_http_methods(['POST'])
def api_v1_pricing_sync(request):
    """JSON API endpoint: v1 pricing sync."""
    key, err = authenticate_api_key(request)
    if err:
        return err
    if not plan_allows_feature(key.company, 'api'):
        audit_api_call(key, key.company, request, 403)
        return JsonResponse({'error': 'plan_forbidden'}, status=403)
    if not require_scope(key, SCOPE_PRICING_WRITE):
        audit_api_call(key, key.company, request, 403)
        return JsonResponse({'error': 'scope_forbidden'}, status=403)

    try:
        body = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        audit_api_call(key, key.company, request, 400)
        return JsonResponse({'error': 'invalid_json'}, status=400)

    updated = 0
    for row in body.get('items', [])[:100]:
        pid = row.get('id')
        price = row.get('price')
        if pid is None or price is None:
            continue
        try:
            prod = Product.objects.get(pk=int(pid), company=key.company)
            prod.unit_price = price
            prod.save(update_fields=['unit_price'])
            updated += 1
        except (Product.DoesNotExist, ValueError, TypeError):
            continue

    audit_api_call(key, key.company, request, 200)
    return JsonResponse({'updated': updated})


@require_GET
def api_v1_health(request):
    """JSON API endpoint: v1 health."""
    return JsonResponse({'status': 'ok', 'service': 'tradeflow-api-v1'})
