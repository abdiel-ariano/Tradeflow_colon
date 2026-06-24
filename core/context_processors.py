"""
Context processors: cart badge, JS strings, and public Supabase config.
"""
from __future__ import annotations

from django.conf import settings


def csp_nonce_context(request):
    """Expone `csp_nonce` (string) en todas las plantillas.

    `SecurityHeadersMiddleware` lo asigna a `request.csp_nonce` antes del
    view. Las plantillas DEBEN renderizarlo en cada `<script>` y `<style>`
    inline para que la CSP `'nonce-...'` los autorize.
    """
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


def pending_applications_badge(request):
    """Pending access applications count for admin navbar."""
    if not request.user.is_authenticated:
        return {'pending_applications_count': 0}
    if not (request.user.is_superuser or getattr(request.user, 'is_staff', False)):
        try:
            if request.user.profile.role != 'admin':
                return {'pending_applications_count': 0}
        except Exception:
            return {'pending_applications_count': 0}
    from core.models import UserApplication

    count = UserApplication.objects.filter(status='pending').count()
    return {'pending_applications_count': count}


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


def tradeflow_contact(request):
    """Public contact email (footer, legal pages, support links)."""
    from core.utils.contact import tradeflow_contact_email

    email = tradeflow_contact_email()
    return {'tradeflow_contact_email': email}


def tf_i18n(request):
    """UI strings for client scripts (TF_I18N)."""
    from core.utils.contact import tradeflow_contact_email

    contact = tradeflow_contact_email()
    payload = {
        'contactEmail': contact,
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
        'processing': 'Processing…',
        'supportEmailPrompt': f'We will improve it. Email us at {contact}',
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


def tf_asset_version(request):
    """Version string for static asset cache busting (?v=)."""
    return {'tf_asset_version': getattr(settings, 'TRADEFLOW_ASSET_VERSION', '1')}


def nav_header_categories(request):
    """Top categorías con productos activos — dropdown del header público."""
    from django.db.models import Count, Q

    from core.models import Category

    categories = list(
        Category.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('-num_productos', 'name')[:10]
    )
    return {'nav_header_categories': categories}
