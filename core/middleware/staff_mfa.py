"""Require staff TOTP setup/verify when MFA is required or already enabled."""
from __future__ import annotations

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import get_language_from_path

from core.utils.saas_demo import user_is_read_only_saas_demo
from core.utils.staff_mfa import (
    session_mfa_ok,
    user_needs_staff_mfa,
    user_needs_staff_mfa_setup,
)

# Paths that must remain reachable while MFA is pending (language-prefix stripped).
_SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})
_MFA_ALLOW = (
    '/login/',
    '/logout/',
    '/staff-mfa/',
    '/health/',
    '/static/',
    '/media/',
    '/i18n/',
)


def _path_without_lang(path: str) -> str:
    """Strip an active i18n language prefix (e.g. ``/es/staff-mfa/`` → ``/staff-mfa/``)."""
    path = path or '/'
    lang = get_language_from_path(path)
    if not lang:
        return path
    prefix = f'/{lang}'
    if path == prefix:
        return '/'
    if path.startswith(prefix + '/'):
        return path[len(prefix):] or '/'
    return path


def _read_only_demo_response(request, bare_path: str):
    """Block writes and Django Admin for the public SaaS demo account."""
    if bare_path == '/admin' or bare_path.startswith('/admin/'):
        return redirect(reverse('admin_saas_dashboard'))

    if (
        request.method.upper() not in _SAFE_METHODS
        and not bare_path.startswith('/logout/')
    ):
        message = 'Read-only demo account.'
        if bare_path.startswith('/api/'):
            return JsonResponse({'error': message}, status=403)
        return HttpResponseForbidden(message)

    return None


class StaffMfaMiddleware:
    """Redirect staff to MFA setup or challenge until the session is verified."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        path = request.path or '/'
        bare = _path_without_lang(path)

        if (
            user is not None
            and user.is_authenticated
            and user_is_read_only_saas_demo(user)
        ):
            blocked_response = _read_only_demo_response(request, bare)
            if blocked_response is not None:
                return blocked_response

        if (
            user is not None
            and user.is_authenticated
            and user_needs_staff_mfa(user)
            and not session_mfa_ok(request)
            and not any(bare.startswith(p) for p in _MFA_ALLOW)
        ):
            next_q = f'?next={path}'
            if user_needs_staff_mfa_setup(user):
                return redirect(reverse('staff_mfa_setup') + next_q)
            return redirect(reverse('staff_mfa_verify') + next_q)
        return self.get_response(request)
