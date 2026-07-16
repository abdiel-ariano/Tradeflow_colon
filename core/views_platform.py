"""Platform health endpoints for load balancers and deploys.

Liveness and readiness probes stay outside i18n URL prefixes so
orchestration (Railway, k8s) can hit them without a locale segment.
"""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core.utils.platform_health import platform_health_payload


@require_GET
def health_live(request):
    """Confirm the Django process is accepting HTTP traffic."""
    return JsonResponse({'status': 'alive'})


@require_GET
def health_ready(request):
    """Gate traffic until DB and critical settings are reachable.

    Returns HTTP 503 when ``platform_health_payload`` reports failure so
    the load balancer stops routing CFZ marketplace requests early.
    """
    payload = platform_health_payload()
    code = 200 if payload['status'] == 'ok' else 503
    return JsonResponse(payload, status=code)
