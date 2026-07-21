"""Platform health endpoints for load balancers and deploys.

Liveness and readiness probes stay outside i18n URL prefixes so
orchestration (Railway, k8s) can hit them without a locale segment.
Also serves RFC 9116 ``security.txt`` and ``robots.txt`` at the site root.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
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


def _public_origin(request) -> str:
    """Absolute site origin for Canonical/Policy URLs in security.txt."""
    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').rstrip('/')
    if base and '127.0.0.1' not in base and 'localhost' not in base:
        return base
    return request.build_absolute_uri('/').rstrip('/')


@require_GET
@cache_control(public=True, max_age=86400)
def security_txt(request):
    """RFC 9116 security.txt for vulnerability disclosure (Cloudflare insight)."""
    origin = _public_origin(request)
    expires = (datetime.now(timezone.utc) + timedelta(days=365)).strftime(
        '%Y-%m-%dT%H:%M:%S.000Z'
    )
    contact = (
        getattr(settings, 'TRADEFLOW_CONTACT_EMAIL', '') or 'security@tradeflow.pa'
    ).strip()
    # Prefer dedicated security mailbox when contact is a generic inbox.
    if contact and not contact.lower().startswith('security@'):
        security_contact = 'security@tradeflow.pa'
    else:
        security_contact = contact or 'security@tradeflow.pa'

    body = (
        f'Contact: mailto:{security_contact}\n'
        f'Expires: {expires}\n'
        'Preferred-Languages: es, en\n'
        f'Canonical: {origin}/.well-known/security.txt\n'
        f'Policy: {origin}/privacidad/\n'
        'Acknowledgments: https://github.com/abdiel-ariano/Tradeflow_colon/blob/master/SECURITY.md\n'
    )
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


@require_GET
@cache_control(public=True, max_age=86400)
def robots_txt(request):
    """Delegate to SEO robots (disallows + AI bots + sitemap.xml)."""
    from core.views.seo_public import robots_txt as seo_robots_txt

    return seo_robots_txt(request)
