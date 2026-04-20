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
from django.shortcuts import redirect
from django.contrib import messages


def _get_role(user):
    """Devuelve el rol del usuario o None si no tiene perfil."""
    try:
        return user.profile.role
    except Exception:
        return None


def buyer_required(view_func):
    """Solo compradores. Sellers y admins son redirigidos a su portal."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        role = _get_role(request.user)
        if role == 'buyer':
            return view_func(request, *args, **kwargs)
        if role == 'seller':
            messages.info(request, 'Accede a tu portal de vendedor.')
            return redirect('/mi-tienda/')
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'No tienes permiso para acceder a esta sección.')
        return redirect('/')
    return wrapper


def seller_required(view_func):
    """Solo vendedores. Buyers son redirigidos a la tienda."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        role = _get_role(request.user)
        if role == 'seller':
            return view_func(request, *args, **kwargs)
        if role == 'admin' or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Esta sección es solo para vendedores.')
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
        messages.error(request, 'Acceso restringido a administradores.')
        return redirect('/')
    return wrapper