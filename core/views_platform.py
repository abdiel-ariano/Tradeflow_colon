"""
Vistas de plataforma: health checks (sin i18n).
"""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core.utils.platform_health import platform_health_payload


@require_GET
def health_live(request):
    """Liveness — proceso activo."""
    return JsonResponse({'status': 'alive'})


@require_GET
def health_ready(request):
    """Readiness — DB y configuración crítica."""
    payload = platform_health_payload()
    code = 200 if payload['status'] == 'ok' else 503
    return JsonResponse(payload, status=code)
