"""
Context processors: cart badge, JS strings, and public Supabase config.
"""
from __future__ import annotations

from django.conf import settings


def cart_badge(request):
    """Cart count for navbar (buyers only)."""
    if not request.user.is_authenticated:
        return {'carrito_count': 0}
    try:
        role = request.user.profile.role
    except Exception:
        role = None
    if request.user.is_superuser or role == 'admin' or role != 'buyer':
        return {'carrito_count': 0}
    carrito = request.session.get('carrito', {})
    count = sum(int(item.get('cantidad', 0) or 0) for item in carrito.values())
    return {'carrito_count': count}


def tf_i18n(request):
    """UI strings for client scripts (TF_I18N)."""
    payload = {
        'close': 'Close',
        'cartTitle': 'Cart',
        'slide': 'Slide',
        'addedToCart': 'Product added to cart',
        'cartAddedShort': 'Added to cart',
        'cartError': 'Could not add to cart',
        'networkError': 'Connection error',
        'orders': 'Orders',
        'products': 'Products',
        'companies': 'Companies',
        'emptySection': 'No products in this section yet.',
        'chartOrders': 'Orders',
        'chartUsd': 'USD',
        'chartPending': 'Pending',
        'chartPaid': 'Paid',
        'chartShipped': 'Shipped',
        'chartDelivered': 'Delivered',
        'chartCancelled': 'Cancelled',
        'chartLoadError': 'Could not load Chart.js. Reload the page.',
        'chartDataError': 'Chart data is incomplete.',
        'chartUpdateError': 'Could not update charts.',
        'chartInitError': 'Could not initialize charts.',
        'csvDownloaded': 'CSV file downloaded successfully.',
        'geoConfirmed': 'Location confirmed.',
        'geoDenied': 'Location permission denied.',
        'geoUnsupported': 'Your browser does not support geolocation.',
        'awaitingSeller': 'Awaiting company confirmation',
        'orderUpdated': 'Order status updated',
    }
    return {'tf_i18n': payload}


def enterprise_saas(request):
    """SaaS plan, monthly usage, and ad credits for seller portal."""
    import logging

    log = logging.getLogger('tradeflow.saas')

    if not request.user.is_authenticated:
        return {}
    try:
        role = request.user.profile.role
    except Exception:
        return {}
    if role not in ('seller', 'admin') and not request.user.is_superuser:
        return {}
    from core.models import Company

    company = Company.objects.filter(owner=request.user).first()
    if not company:
        return {'saas_snapshot': None}
    try:
        from core.utils.saas_billing import subscription_usage_snapshot

        snap = subscription_usage_snapshot(company)
        return {'saas_snapshot': snap, 'saas_company': company}
    except Exception as exc:
        log.warning(
            'enterprise_saas_context_failed user_id=%s company_id=%s: %s',
            request.user.pk,
            company.pk,
            exc,
            exc_info=True,
        )
        return {'saas_snapshot': None, 'saas_company': company}


def supabase_public(request):
    """Public Supabase keys for Realtime on the frontend."""
    url = getattr(settings, 'SUPABASE_URL', '') or ''
    anon = getattr(settings, 'SUPABASE_ANON_KEY', '') or ''
    return {
        'SUPABASE_PUBLIC_URL': url,
        'SUPABASE_ANON_KEY': anon,
        'SUPABASE_REALTIME_ENABLED': bool(url and anon),
    }
