"""Platform health endpoints for load balancers and deploys.

Liveness and readiness probes stay outside i18n URL prefixes so
orchestration (Railway, k8s) can hit them without a locale segment.
Also serves RFC 9116, crawler, PWA, and Android trust resources.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from io import BytesIO

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_GET

from PIL import Image

from core.utils.platform_health import platform_health_payload


_ANDROID_PACKAGE_DEFAULT = 'com.tradeflowcolon.app'
_PWA_ICON_SIZES = {192, 512}
_SHA256_FINGERPRINT = re.compile(
    r'^(?:[0-9A-F]{2}:){31}[0-9A-F]{2}$'
)


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



def _android_fingerprints() -> list[str]:
    """Return configured, normalized Android SHA-256 fingerprints."""
    raw_value = getattr(
        settings,
        'ANDROID_SHA256_CERT_FINGERPRINTS',
        '',
    )
    candidates = str(raw_value or '').upper().split(',')
    return [
        value.strip()
        for value in candidates
        if _SHA256_FINGERPRINT.fullmatch(value.strip())
    ]


@require_GET
@cache_control(public=True, max_age=86400)
def web_app_manifest(request):
    """Describe the installable TradeFlow PWA for browsers and Android."""
    manifest = {
        'id': '/',
        'name': 'TradeFlow Colón',
        'short_name': 'TradeFlow',
        'description': (
            'Marketplace B2B para compradores y vendedores de la '
            'Zona Libre de Colón.'
        ),
        'lang': 'es',
        'dir': 'ltr',
        'start_url': '/?source=installed-app',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'any',
        'background_color': '#F2F3F5',
        'theme_color': '#0F2A44',
        'categories': ['business', 'shopping'],
        'icons': [
            {
                'src': '/pwa/icon-192.png',
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any',
            },
            {
                'src': '/pwa/icon-512.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any maskable',
            },
        ],
    }
    return JsonResponse(
        manifest,
        content_type='application/manifest+json',
    )


@require_GET
@cache_control(public=True, max_age=2592000)
def pwa_icon(request, size: int):
    """Resize the canonical logo to an Android-compatible PWA icon."""
    if size not in _PWA_ICON_SIZES:
        raise Http404('Unsupported PWA icon size.')

    source_path = finders.find('img/logo-icon-color.png')
    if not source_path:
        raise Http404('Canonical TradeFlow icon not found.')

    with Image.open(source_path) as source_image:
        icon = source_image.convert('RGBA').resize(
            (size, size),
            Image.Resampling.LANCZOS,
        )

    output = BytesIO()
    icon.save(output, format='PNG', optimize=True)
    return HttpResponse(
        output.getvalue(),
        content_type='image/png',
    )


@require_GET
@never_cache
def service_worker(request):
    """Serve the root-scoped worker without caching authenticated content."""
    body = render_to_string('pwa/service-worker.js')
    response = HttpResponse(
        body,
        content_type='application/javascript; charset=utf-8',
    )
    response['Service-Worker-Allowed'] = '/'
    return response


@require_GET
@cache_control(public=True, max_age=3600)
def offline_page(request):
    """Render a public fallback when Android temporarily loses connectivity."""
    context = {
        'csp_nonce': getattr(request, 'csp_nonce', ''),
    }
    body = render_to_string('pwa/offline.html', context)
    return HttpResponse(body, content_type='text/html; charset=utf-8')


@require_GET
@cache_control(public=True, max_age=3600)
def assetlinks_json(request):
    """Publish the Android certificate relationship for TWA verification."""
    package_name = (
        getattr(settings, 'ANDROID_APP_PACKAGE', '')
        or _ANDROID_PACKAGE_DEFAULT
    ).strip()
    fingerprints = _android_fingerprints()
    payload = []
    if fingerprints:
        payload.append(
            {
                'relation': [
                    'delegate_permission/common.handle_all_urls',
                ],
                'target': {
                    'namespace': 'android_app',
                    'package_name': package_name,
                    'sha256_cert_fingerprints': fingerprints,
                },
            }
        )
    return JsonResponse(payload, safe=False)


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
    """Robots policy: allow marketplace crawl; discourage common AI scrapers."""
    origin = _public_origin(request)
    body = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Disallow: /mi-tienda/
Disallow: /checkout/
Disallow: /carrito/
Disallow: /login/
Disallow: /signup/
Disallow: /accounts/
Disallow: /verificar/
Disallow: /staff-mfa/

# AI / training crawlers (Cloudflare Security Insights companion)
User-agent: GPTBot
Disallow: /

User-agent: ChatGPT-User
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Claude-Web
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: meta-externalagent
Disallow: /

User-agent: Amazonbot
Disallow: /

Sitemap: {origin}/
"""
    return HttpResponse(body, content_type='text/plain; charset=utf-8')
