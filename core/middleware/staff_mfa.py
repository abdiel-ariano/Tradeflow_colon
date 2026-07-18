"""Require staff TOTP setup/verify when MFA is required or already enabled."""
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse

from core.utils.staff_mfa import (
    session_mfa_ok,
    user_needs_staff_mfa,
    user_needs_staff_mfa_setup,
)

# Paths that must remain reachable while MFA is pending.
_MFA_ALLOW = (
    '/login/',
    '/logout/',
    '/staff-mfa/',
    '/health/',
    '/static/',
    '/media/',
    '/i18n/',
)


class StaffMfaMiddleware:
    """Redirect staff to MFA setup or challenge until the session is verified."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        path = request.path or '/'
        if (
            user is not None
            and user.is_authenticated
            and user_needs_staff_mfa(user)
            and not session_mfa_ok(request)
            and not any(path.startswith(p) for p in _MFA_ALLOW)
        ):
            next_q = f'?next={path}'
            if user_needs_staff_mfa_setup(user):
                return redirect(reverse('staff_mfa_setup') + next_q)
            return redirect(reverse('staff_mfa_verify') + next_q)
        return self.get_response(request)
