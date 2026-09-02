"""Require staff TOTP setup/verify when MFA is required or enabled."""
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import get_language_from_path

from core.utils.saas_demo import user_is_demo_admin
from core.utils.staff_mfa import (
    session_mfa_ok,
    user_needs_staff_mfa,
    user_needs_staff_mfa_setup,
)

# Paths that must remain reachable while MFA is pending (language-prefix stripped).
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
    """Strip an active i18n language prefix from a request path."""
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


class StaffMfaMiddleware:
    """Restore demo access and enforce MFA for regular staff accounts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        path = request.path or '/'
        bare = _path_without_lang(path)

        if (
            user is not None
            and user.is_authenticated
            and user_is_demo_admin(user)
            and not user.is_staff
        ):
            from core.utils.admin_permissions import sync_user_admin_access

            sync_user_admin_access(user)

        if (
            user is not None
            and user.is_authenticated
            and user_needs_staff_mfa(user)
            and not session_mfa_ok(request)
            and not any(bare.startswith(prefix) for prefix in _MFA_ALLOW)
        ):
            next_query = f'?next={path}'
            if user_needs_staff_mfa_setup(user):
                return redirect(reverse('staff_mfa_setup') + next_query)
            return redirect(reverse('staff_mfa_verify') + next_query)
        return self.get_response(request)
