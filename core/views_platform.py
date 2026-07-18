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
    Detailed config is staff-only (or ``?detail=1`` with shared token).
    """
    from django.conf import settings

    detail_token = (getattr(settings, 'HEALTH_DETAIL_TOKEN', '') or '').strip()
    want_detail = False
    if request.user.is_authenticated and (
        request.user.is_staff or request.user.is_superuser
    ):
        want_detail = True
    elif detail_token and request.GET.get('detail') == '1':
        want_detail = request.GET.get('token', '') == detail_token

    payload = platform_health_payload(detailed=want_detail)
    code = 200 if payload['status'] == 'ok' else 503
    return JsonResponse(payload, status=code)
