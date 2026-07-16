"""Role and onboarding access decorators for TradeFlow Colón views.

Gates catalog, cart, checkout, seller portal, and admin routes by login,
email verification, company onboarding, and SaaS subscription state.
"""
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from core.utils.access_gating import onboarding_redirect_name, safe_intent_next


def _request_wants_json(request):
    """Return True when the client expects a JSON error body."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


def _get_role(user):
    """Return the user's profile role, or None if missing."""
    try:
        return user.profile.role
    except Exception:
        return None


def _gated_redirect(request, route: str):
    """Redirect to an onboarding route, preserving ``?next=`` for OTP."""
    if route == 'verificar_codigo':
        nxt = safe_intent_next(request)
        if nxt:
            return redirect(f"{reverse(route)}?{urlencode({'next': nxt})}")
    return redirect(route)


def _enforce_onboarding(request, scope='restricted'):
    """Redirect when the user fails the given onboarding scope."""
    route = onboarding_redirect_name(request.user, scope=scope)
    if route:
        return _gated_redirect(request, route)
    return None


def catalog_access(view_func):
    """Allow guests and buyers on catalog/cart; send sellers to portal."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Gate the view to authenticated CFZ sellers only."""
        if not request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        blocked = _enforce_onboarding(request, scope='browse')
        if blocked:
            if request.method == 'POST' and _request_wants_json(request):
                from django.http import JsonResponse
                from django.utils.translation import gettext as _
                return JsonResponse(
                    {'ok': False, 'message': _('Complete your account setup to continue.')},
                    status=403,
                )
            return blocked
        role = _get_role(request.user)
        if role in (None, 'buyer'):
            return view_func(request, *args, **kwargs)
        if role == 'seller':
            if request.method == 'POST' and _request_wants_json(request):
                from django.http import JsonResponse
                from django.utils.translation import gettext as _
                return JsonResponse(
                    {'ok': False, 'message': _('Go to your seller portal.')},
                    status=403,
                )
            messages.info(request, 'Go to your seller portal.')
            return redirect('/mi-tienda/')
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'You do not have permission to access this section.')
        return redirect('/')
    return wrapper


def guest_or_buyer_cart(view_func):
    """Allow guests and non-sellers on session cart endpoints."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Gate the view to buyers with an approved company path."""
        if not request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        blocked = _enforce_onboarding(request, scope='browse')
        if blocked:
            if request.method == 'POST' and _request_wants_json(request):
                from django.http import JsonResponse
                from django.utils.translation import gettext as _
                return JsonResponse(
                    {'ok': False, 'message': _('Complete your account setup to continue.')},
                    status=403,
                )
            return blocked
        role = _get_role(request.user)
        if role == 'seller':
            if request.method == 'POST' and _request_wants_json(request):
                from django.http import JsonResponse
                from django.utils.translation import gettext as _
                return JsonResponse(
                    {'ok': False, 'message': _('Go to your seller portal.')},
                    status=403,
                )
            messages.info(request, 'Go to your seller portal.')
            return redirect('/mi-tienda/')
        return view_func(request, *args, **kwargs)
    return wrapper


def buyer_checkout(view_func):
    """Gate checkout: GET uses browse scope; POST requires full verification."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Require verified email before the marketplace action runs."""
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        scope = 'browse' if request.method == 'GET' else 'restricted'
        blocked = _enforce_onboarding(request, scope=scope)
        if blocked:
            return blocked
        role = _get_role(request.user)
        if role in (None, 'buyer'):
            return view_func(request, *args, **kwargs)
        if role == 'seller':
            messages.info(request, 'Go to your seller portal.')
            return redirect('/mi-tienda/')
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'You do not have permission to access this section.')
        return redirect('/')
    return wrapper


def buyer_required(view_func):
    """Require login and email verification for buyer orders and quotes."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Require an active seller SaaS plan for this portal page."""
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        blocked = _enforce_onboarding(request, scope='restricted')
        if blocked:
            return blocked
        role = _get_role(request.user)
        if role in (None, 'buyer'):
            return view_func(request, *args, **kwargs)
        if role == 'seller':
            messages.info(request, 'Go to your seller portal.')
            return redirect('/mi-tienda/')
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'You do not have permission to access this section.')
        return redirect('/')
    return wrapper


def seller_required(view_func):
    """Require a seller with company record and valid subscription access.

    Gate order: login/OTP/onboarding, then company wizard if missing
    ``Company.owner``, then trial/grace/cancelled via ``seller_portal_access``.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Block trial-expired sellers from mutating storefront data."""
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        blocked = _enforce_onboarding(request, scope='restricted')
        if blocked:
            return blocked
        role = _get_role(request.user)
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if role != 'seller':
            messages.error(request, 'This section is for sellers only.')
            return redirect('catalogo_publico')

        from core.models import Company
        from core.utils.seller_lifecycle import seller_portal_access

        company = Company.objects.filter(owner=request.user).first()
        route_name = request.resolver_match.url_name if request.resolver_match else ''
        portal_block = seller_portal_access(company, route_name=route_name)
        if portal_block:
            if portal_block == 'seller_onboarding_company':
                messages.info(request, 'Completa los datos de tu empresa para continuar.')
            elif portal_block == 'seller_trial_activation':
                messages.warning(
                    request,
                    'Tu periodo de prueba terminó. Activa un plan para seguir operando.',
                )
            elif portal_block == 'seller_account_inactive':
                messages.error(request, 'Tu cuenta seller está inactiva.')
            return redirect(portal_block)

        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Restrict the view to staff admins and superusers."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Restrict the view to staff or TradeFlow platform admins."""
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        role = _get_role(request.user)
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access restricted to administrators.')
        return redirect('/')
    return wrapper
