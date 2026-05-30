"""
=============================================================================
TRADEFLOW COLÓN — core/decorators.py
=============================================================================
Decoradores de control de acceso por rol.

USO en views.py:
    from .decorators import buyer_required, seller_required, admin_required

    @buyer_required
    def tienda(request):
        ...

    @admin_required
    def dashboard(request):
        ...
=============================================================================
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from core.utils.access_gating import onboarding_redirect_name


def _get_role(user):
    """Devuelve el rol del usuario o None si no tiene perfil."""
    try:
        return user.profile.role
    except Exception:
        return None


def _enforce_onboarding(request):
    """Redirige si email o solicitud no cumplen requisitos enterprise."""
    route = onboarding_redirect_name(request.user)
    if route:
        return redirect(route)
    return None


def buyer_required(view_func):
    """Solo compradores. Sellers y admins son redirigidos a su portal."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        blocked = _enforce_onboarding(request)
        if blocked:
            return blocked
        role = _get_role(request.user)
        if role == 'buyer':
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
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        blocked = _enforce_onboarding(request)
        if blocked:
            return blocked
        role = _get_role(request.user)
        if role == 'seller':
            return view_func(request, *args, **kwargs)
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'This section is for sellers only.')
        return redirect('/tienda/')
    return wrapper


def admin_required(view_func):
    """Solo administradores."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        role = _get_role(request.user)
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Access restricted to administrators.')
        return redirect('/')
    return wrapper