"""Require staff TOTP setup/verify when MFA is required or already enabled."""
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import get_language_from_path

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
            and user_needs_staff_mfa(user)
            and not session_mfa_ok(request)
            and not any(bare.startswith(p) for p in _MFA_ALLOW)
        ):
            next_q = f'?next={path}'
            if user_needs_staff_mfa_setup(user):
                return redirect(reverse('staff_mfa_setup') + next_q)
            return redirect(reverse('staff_mfa_verify') + next_q)
        return self.get_response(request)
