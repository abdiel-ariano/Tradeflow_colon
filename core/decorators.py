"""
=============================================================================
TRADEFLOW COLÓN — core/decorators.py
=============================================================================
Decoradores de control de acceso por rol.

USO en views.py:
    from .decorators import buyer_required, seller_required, admin_required

    @buyer_required
    def checkout(request):
        ...
=============================================================================
"""
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from core.utils.access_gating import onboarding_redirect_name, safe_intent_next


def _request_wants_json(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


def _get_role(user):
    """Devuelve el rol del usuario o None si no tiene perfil."""
    try:
        return user.profile.role
    except Exception:
        return None


def _gated_redirect(request, route: str):
    """Redirige a onboarding/verificación preservando ?next= cuando aplica."""
    if route == 'verificar_codigo':
        nxt = safe_intent_next(request)
        if nxt:
            return redirect(f"{reverse(route)}?{urlencode({'next': nxt})}")
    return redirect(route)


def _enforce_onboarding(request, scope='restricted'):
    """Redirige si el usuario no cumple requisitos del scope indicado."""
    route = onboarding_redirect_name(request.user, scope=scope)
    if route:
        return _gated_redirect(request, route)
    return None


def catalog_access(view_func):
    """Catálogo y carrito de sesión visibles para invitados y compradores."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Wrapper."""
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
    """Carrito en sesión: invitados y usuarios autenticados (sin bloqueo por OTP)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Wrapper."""
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
    """Checkout: GET permite ver la página con verificación inline; POST exige email."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Wrapper."""
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
    """Checkout, pedidos y cotizaciones: login + verificación de email."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Wrapper."""
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
    """Solo vendedores. Buyers son redirigidos a la tienda."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Wrapper."""
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        blocked = _enforce_onboarding(request, scope='restricted')
        if blocked:
            return blocked
        role = _get_role(request.user)
        if role == 'seller':
            return view_func(request, *args, **kwargs)
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'This section is for sellers only.')
        return redirect('catalogo_publico')
    return wrapper


def admin_required(view_func):
    """Solo administradores."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        """Wrapper."""
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        role = _get_role(request.user)
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access restricted to administrators.')
        return redirect('/')
    return wrapper
