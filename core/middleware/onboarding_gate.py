"""Redirect incomplete accounts away from protected marketplace routes.

Authenticated buyers and sellers must finish email verification and
application approval before operational CFZ paths are available.
"""
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlencode

from core.utils.access_gating import (
    is_protected_path,
    is_public_path,
    normalize_path,
    onboarding_redirect_name,
    safe_intent_next,
    should_inline_verify_at_checkout,
)


class OnboardingGateMiddleware:
    """Send unfinished users to OTP or approval before protected GET pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = normalize_path(request.path)

        if request.method == 'GET' and request.user.is_authenticated:
            if not is_public_path(path) and is_protected_path(path):
                route = onboarding_redirect_name(request.user)
                if route and should_inline_verify_at_checkout(path, route):
                    route = None
                if route:
                    target = reverse(route)
                    if not request.path.startswith(target):
                        if route == 'verificar_codigo':
                            nxt = safe_intent_next(request)
                            if nxt:
                                return redirect(f"{target}?{urlencode({'next': nxt})}")
                        return redirect(route)

        return self.get_response(request)
