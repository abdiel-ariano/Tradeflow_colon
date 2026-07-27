"""Helpers compartidos del paquete de vistas (auth redirect, next URL, logging)."""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.urls import reverse


AUTH_MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'


NOMBRE_REGEX = re.compile(r"^[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s'\-]{2,50}$")


USERNAME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9._]{2,29}$")


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


log = logging.getLogger(__name__)


def _redirect_by_role(user):
    """Home URL after login or when an authenticated user hits ``/``.
    
    Admins go to ``/dashboard/`` (never public home) to avoid
    redirect loops. Sellers and buyers may still need onboarding
    before the seller portal or guest catalog.
    """
    try:
        role = user.profile.role
    except Exception:
        role = None

    if user.is_superuser or role == 'admin':
        return reverse('admin:index')
    if role == 'seller':
        from core.utils.access_gating import seller_onboarding_redirect_name
        seller_route = seller_onboarding_redirect_name(user)
        if seller_route:
            return reverse(seller_route)
        return reverse('portal_seller')
    from core.utils.access_gating import buyer_onboarding_redirect_name
    buyer_route = buyer_onboarding_redirect_name(user)
    if buyer_route:
        return reverse(buyer_route)
    return reverse('catalogo_publico')


def _login_template_context(**extra):
    """Shared context for ``core/login.html`` (OTP gate flags, extras)."""
    ctx = {
        'require_email_verification': settings.REQUIRE_EMAIL_VERIFICATION,
    }
    ctx.update(extra)
    return ctx


def _safe_next_url(request, raw_next: str = '') -> str:
    """Normalize ``?next=``, blocking open redirects and login/home loops."""
    next_url = (raw_next or request.GET.get('next') or '').strip()
    if not next_url.startswith('/') or next_url.startswith('//') or '://' in next_url:
        return ''
    home_path = reverse('home')
    login_path = reverse('login')
    if (
        next_url in (home_path, '/')
        or next_url == login_path
        or next_url.startswith(login_path + '?')
    ):
        return ''
    return next_url


def _request_wants_json(request):
    """Return True when the client expects a JSON cart/API body."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept
