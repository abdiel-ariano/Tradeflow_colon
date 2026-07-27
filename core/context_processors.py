"""Template context processors for TradeFlow Colón UI shells.

Inject cart badges, CSP nonces, public Supabase keys, SaaS snapshots,
and localized JS string maps into every rendered template.
"""
from __future__ import annotations

from django.conf import settings


def csp_nonce_context(request):
    """Expose the per-request CSP nonce for inline script/style tags.

    SecurityHeadersMiddleware sets ``request.csp_nonce`` before the view.
    Templates must render it on every inline ``<script>`` and ``<style>``
    so the CSP ``'nonce-...'`` directive authorizes them.
    """
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


def demo_catalog_context(request):
    """Expose whether public commercial data must be marked as simulated.

    The flag is configuration-only and performs no database query, keeping the
    processor safe for every public, buyer, seller, and administrative request.
    """
    enabled = getattr(settings, 'DEMO_CATALOG_DISCLOSURE', False)
    return {'demo_catalog_enabled': bool(enabled)}


def pending_applications_badge(request):
    """Count pending UserApplication rows for admin navbar badges."""
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
    """Session inquiry-cart line count for the buyer navbar badge."""
    carrito = request.session.get('carrito', {})
    count = sum(int(item.get('cantidad', 0) or 0) for item in carrito.values())
    if not request.user.is_authenticated:
        return {'carrito_count': count}
    try:
        role = request.user.profile.role
    except Exception:
        role = None
    if request.user.is_superuser or role == 'admin' or role != 'buyer':
        return {'carrito_count': 0}
    return {'carrito_count': count}


def tradeflow_contact(request):
    """Public support email for footer, legal pages, and contact links."""
    from core.utils.contact import tradeflow_contact_email

    email = tradeflow_contact_email()
    return {'tradeflow_contact_email': email}


def tf_i18n(request):
    """Localized UI string map for client scripts (``TF_I18N`` payload)."""
    from django.utils import translation
    from django.utils.translation import gettext as _

    from core.utils.contact import tradeflow_contact_email

    contact = tradeflow_contact_email()
    language = getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
    with translation.override(language):
        payload = {
            'contactEmail': contact,
            'close': _('Close'),
            'cartTitle': _('Cart'),
            'slide': _('Slide'),
            'addedToCart': _('Product added to cart'),
            'cartAddedShort': _('Added to cart'),
            'cartError': _('Could not add to cart'),
            'networkError': _('Connection error'),
            'orders': _('Orders'),
            'products': _('Products'),
            'companies': _('Companies'),
            'emptySection': _('No products in this section yet.'),
            'chartOrders': _('Orders'),
            'chartUsd': _('USD'),
            'chartPending': _('Pending'),
            'chartPaid': _('Paid'),
            'chartShipped': _('Shipped'),
            'chartDelivered': _('Delivered'),
            'chartCancelled': _('Cancelled'),
            'chartLoadError': _('Could not load Chart.js. Reload the page.'),
            'chartDataError': _('Chart data is incomplete.'),
            'chartUpdateError': _('Could not update charts.'),
            'chartInitError': _('Could not initialize charts.'),
            'csvDownloaded': _('CSV file downloaded successfully.'),
            'geoConfirmed': _('Location confirmed.'),
            'geoGettingLocation': _('Getting location…'),
            'geoConfirmRequired': _('You must confirm your location to continue.'),
            'geoDenied': _('Location permission denied.'),
            'geoUnsupported': _('Your browser does not support geolocation.'),
            'awaitingSeller': _('Awaiting company confirmation'),
            'orderUpdated': _('Order status updated'),
            'processing': _('Processing…'),
            'supportEmailPrompt': _('We will improve it. Email us at %(email)s') % {'email': contact},
            'catalogSortRelevance': _('Best match'),
            'catalogSortPriceAsc': _('Price: low to high'),
            'catalogSortPriceDesc': _('Price: high to low'),
            'catalogSortNewest': _('Newest'),
            'catalogChipVerified': _('Verified'),
            'catalogChipStock': _('In stock'),
            'catalogChipStockLow': _('Low stock'),
            'catalogChipOnSale': _('On sale'),
            'catalogSearchPrefix': _('Search:'),
            'catalogCategoryFallback': _('Category'),
            'catalogSupplierFallback': _('Supplier'),
            'catalogPriceMinPrefix': _('Min. $'),
            'catalogPriceMaxPrefix': _('Max. $'),
            'catalogClearAll': _('Clear all'),
            'catalogRateLimit': _('Too many requests — wait a moment and try again.'),
            'catalogImageSearchSoon': _('Image search coming soon — use text search for now.'),
            'catalogAddedToCart': _('Added to inquiry cart'),
            'catalogCartError': _('Could not add to inquiry cart'),
            'catalogNetworkError': _('Connection error — try again'),
            'cartAdding': _('Adding…'),
            'aiSearchEmpty': _('No suggestions — press Enter to search.'),
            'aiSearchStart': _('Start typing to see AI recommendations.'),
            'aiSearchUnavailable': _('Suggestions unavailable — press Enter to search.'),
            'aiSearchRateLimit': _('Too many searches — wait a moment and try again.'),
            'aiSearchAsk': _('Ask AI'),
            'aiSearchAskAbout': _('Ask AI about this search'),
            'aiSearchProducts': _('Products'),
            'aiSearchCategories': _('Categories'),
            'aiSearchCompanies': _('Companies'),
            'aiSearchOrders': _('Orders'),
            'aiSearchQuotes': _('Quotes'),
            'aiSearchCustomers': _('Customers'),
            'aiSearchActions': _('Quick actions'),
            'aiSearchSuggestions': _('Suggestions'),
        }
    return {'tf_i18n': payload}


def enterprise_saas(request):
    """Seller SaaS plan, monthly usage, and ad credits for the portal."""
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

        # Read-mostly on HTML: avoid recomputing monthly volume every request.
        snap = subscription_usage_snapshot(company, refresh=False)
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
    """Anon Supabase URL/key for browser Realtime subscriptions."""
    url = getattr(settings, 'SUPABASE_URL', '') or ''
    anon = getattr(settings, 'SUPABASE_ANON_KEY', '') or ''
    return {
        'SUPABASE_PUBLIC_URL': url,
        'SUPABASE_ANON_KEY': anon,
        'SUPABASE_REALTIME_ENABLED': bool(url and anon),
    }


def tf_asset_version(request):
    """Asset version string for static cache busting (``?v=``)."""
    return {'tf_asset_version': getattr(settings, 'TRADEFLOW_ASSET_VERSION', '1')}


def tf_user_role(request):
    """Expose marketplace role without raising when ``UserProfile`` is missing.

    ``base.html`` and shell templates must not touch
    ``request.user.profile`` directly — a RelatedObjectDoesNotExist there
    becomes HTTP 500 right after login/OAuth for incomplete accounts.

    Also exposes ``tf_seller_onboarding_pending`` so marketplace home/catalog
    can use the public shell instead of stacking the seller dashboard nav.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'tf_user_role': '',
            'tf_has_profile': False,
            'tf_seller_onboarding_pending': False,
            'tf_admin_read_only_demo': False,
            'tf_admin_expo_demo': False,
        }
    try:
        role = request.user.profile.role or ''
    except Exception:
        return {
            'tf_user_role': '',
            'tf_has_profile': False,
            'tf_seller_onboarding_pending': False,
            'tf_admin_read_only_demo': False,
            'tf_admin_expo_demo': False,
        }
    pending = False
    if role == 'seller':
        try:
            from core.utils.access_gating import seller_company_pending

            pending = seller_company_pending(request.user)
        except Exception:
            pending = False
    read_only_demo = False
    expo_demo = False
    if role == 'admin' or request.user.is_superuser:
        from core.utils.saas_demo import (
            user_is_expo_demo_admin,
            user_is_read_only_saas_demo,
        )

        read_only_demo = user_is_read_only_saas_demo(request.user)
        expo_demo = user_is_expo_demo_admin(request.user)
    return {
        'tf_user_role': role,
        'tf_has_profile': True,
        'tf_seller_onboarding_pending': pending,
        'tf_admin_read_only_demo': read_only_demo,
        'tf_admin_expo_demo': expo_demo,
    }


def nav_header_categories(request):
    """Cached top categories with active products for the public header."""
    from core.utils.tradeflow_cache import cached_nav_categories

    return {'nav_header_categories': cached_nav_categories()}


def buyer_mega_menu_context(request):
    """Buyer navbar mega-menu panels for authenticated buyers only.

    Skips the merchandising query for sellers and admins so portal pages
    do not pay for catalog navigation data they never render.
    """
    if not request.user.is_authenticated:
        return {}
    try:
        role = request.user.profile.role
        if role not in (None, 'buyer'):
            return {}
    except Exception:
        return {}
    from core.utils.tradeflow_cache import cached_buyer_mega_menu_panels

    return {'buyer_mega_menu_panels': cached_buyer_mega_menu_panels()}


def social_auth_context(request):
    """Enabled OAuth provider slugs for login and signup templates."""
    from core.social_auth import provider_is_enabled, social_auth_enabled

    providers = []
    if social_auth_enabled():
        if provider_is_enabled('google'):
            providers.append('google')
        if provider_is_enabled('microsoft'):
            providers.append('microsoft')
        if provider_is_enabled('linkedin'):
            providers.append('linkedin')
    return {
        'social_auth_enabled': bool(providers),
        'social_auth_providers': providers,
    }

