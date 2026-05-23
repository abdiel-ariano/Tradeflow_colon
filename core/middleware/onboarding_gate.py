"""
Middleware de onboarding: verificación de email y solicitud aprobada.
"""
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse

from core.utils.access_gating import (
    is_protected_path,
    is_public_path,
    normalize_path,
    onboarding_redirect_name,
)


class OnboardingGateMiddleware:
    """Redirige usuarios incompletos fuera de rutas operativas."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = normalize_path(request.path)

        if request.method == 'GET' and request.user.is_authenticated:
            if not is_public_path(path) and is_protected_path(path):
                route = onboarding_redirect_name(request.user)
                if route:
                    target = reverse(route)
                    if not request.path.startswith(target):
                        return redirect(route)

        return self.get_response(request)
