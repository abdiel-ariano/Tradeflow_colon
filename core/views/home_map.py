"""Home pública, APIs de búsqueda/asistente, mapa ZLC y QR de visitante."""
from __future__ import annotations

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import base64
import html as html_module
import io
import json
import logging
import re
import unicodedata
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import cache_control, never_cache

import qrcode
from django.core import signing

from ..decorators import admin_required, buyer_checkout, buyer_required, catalog_access, guest_or_buyer_cart, seller_required
from ..forms import SellerProductForm, SellerInventoryForm
from ..email_service import enviar_codigo_verificacion as enviar_codigo_email
from ..models import (
    UserProfile, Company, Category, Product, Inventory,
    Address, Order, OrderItem, Payment, Shipment, Document,
    Cotizacion, CotizacionItem, TransportCarrier, UserApplication,
    EmailVerification,
)
from ..utils.email_sender import (
    enviar_bienvenida,
    enviar_cambio_estado,
    enviar_confirmacion_orden,
    enviar_orden_pendiente_vendedor,
    enviar_solicitud_recibida,
    enviar_solicitud_a_revisores,
    enviar_solicitud_decision,
)
from ..utils.saas_billing import VolumeLimitExceeded, is_volume_limit_reached
from ..utils.media_storage import product_image_url
from ..utils.order_workflow import (
    accept_seller_order,
    reject_seller_order,
    seller_confirm_deadline,
    expire_pending_orders,
)
from ..utils.pdf_generator import (
    generar_cotizacion_pdf,
    generar_factura_pdf,
    generar_packing_list_pdf,
)

from .common import _redirect_by_role, log

def home_view(request):
    """Public PreExpo landing with merchandising, CMS, and live stats."""
    if request.user.is_authenticated:
        try:
            role = request.user.profile.role
        except Exception:
            role = None
        if request.user.is_superuser or role == 'admin':
            return redirect('dashboard')
        if role == 'seller':
            # Portal solo si ya puede operar; si falta empresa, mostrar home
            # pública para poder salir del wizard sin bucle de redirección.
            from core.utils.access_gating import seller_onboarding_redirect_name

            if not seller_onboarding_redirect_name(request.user):
                return redirect('portal_seller')

    from django.utils.translation import get_language
    from core.utils.tradeflow_cache import cached_guest_home_context

    context = cached_guest_home_context(get_language())
    context['show_cart_actions'] = True
    stats = context.get('stats') or {}
    context['catalogo_stats'] = stats
    response = render(request, 'core/home.html', context)
    # private: sesión/carrito de invitados; no compartir en CDN.
    response['Cache-Control'] = 'private, max-age=60'
    return response


@require_GET
@cache_control(public=True, max_age=60)
def api_home_merchandising(request):
    """Public JSON merchandising payload for lightweight home clients."""
    from core.utils.tradeflow_cache import cached_api_home_merchandising

    return JsonResponse(cached_api_home_merchandising())


_ASSISTANT_FALLBACK = (
    "I can still help from the live TradeFlow catalog while AI enrichment is unavailable."
)


def _assistant_system_prompt() -> str:
    """Backward-compatible access to the single authoritative B2B prompt."""
    from core.utils.ai_assistant import SYSTEM_PROMPT

    return SYSTEM_PROMPT


def _asistente_respuesta_html(text: str) -> str:
    """Escape assistant text for safe HTML chat bubbles."""
    safe = escape(text).replace('\n', '<br>')
    return (
        '<div class="tf-bot-card">'
        f'<p style="margin:0;line-height:1.55;">{safe}</p>'
        '</div>'
    )


def _asistente_json_payload(respuesta: str, *, ok: bool = True, status: int = 200):
    """Wrap assistant text in the AJAX JSON response shape."""
    return JsonResponse(
        {
            'ok': ok,
            'respuesta': respuesta,
            'respuesta_html': _asistente_respuesta_html(respuesta),
        },
        status=status,
    )


@require_GET
def api_search_suggest(request):
    """JSON typeahead for catalog and header search bars."""
    from ..utils.ai_search import build_search_response

    scope = (request.GET.get('scope') or 'public').strip().lower()
    if scope not in ('public', 'seller', 'buyer', 'admin'):
        scope = 'public'

    if scope == 'seller':
        if not request.user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'auth_required'}, status=401)
        try:
            if request.user.profile.role != 'seller' and not request.user.is_superuser:
                return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    elif scope == 'admin':
        if not request.user.is_authenticated or not (
            request.user.is_superuser
            or getattr(getattr(request.user, 'profile', None), 'role', None) == 'admin'
        ):
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    q = (request.GET.get('q') or '').strip()
    try:
        limit = int(request.GET.get('limit', '8'))
    except (TypeError, ValueError):
        limit = 8
    limit = max(1, min(limit, 12))

    payload = build_search_response(scope, q, request, limit=limit)
    status = 200 if payload.get('ok', True) else 403
    return JsonResponse(payload, status=status)


@require_POST
def api_asistente(request):
    """AJAX chat endpoint for the CFZ marketplace AI assistant."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _asistente_json_payload(
            'Invalid request format.',
            ok=False,
            status=400,
        )

    mensaje = (data.get('mensaje') or '').strip()
    historial = data.get('historial') or []
    contexto = (data.get('contexto') or '').strip().lower()

    if not mensaje:
        return _asistente_json_payload(
            'Please enter a message.',
            ok=False,
            status=400,
        )

    if len(mensaje) > 500:
        return _asistente_json_payload(
            'Message is too long (max 500 characters).',
            ok=False,
            status=400,
        )

    # The catalog-backed assistant is authoritative and always available.
    # Groq enriches its answer when configured, but upstream failures are handled
    # inside consultar_asistente and never disconnect the public chat.
    from core.utils.ai_assistant import consultar_asistente

    hist = []
    if isinstance(historial, list):
        for item in historial[-6:]:
            if not isinstance(item, dict):
                continue
            role = item.get('role')
            content = (item.get('content') or '').strip()
            if role in ('user', 'assistant') and content:
                hist.append({'role': role, 'content': content[:500]})

    company = None
    if contexto == 'seller' and request.user.is_authenticated:
        from .seller_store import _get_seller_company

        company = _get_seller_company(request.user)

    try:
        result = consultar_asistente(
            mensaje,
            historial=hist,
            user=request.user if request.user.is_authenticated else None,
            company=company,
        )
        respuesta = (result.get('respuesta') or '').strip() or (
            'I could not process your request.'
        )
        payload = {
            'ok': True,
            'respuesta': respuesta,
            'respuesta_html': (
                result.get('respuesta_html')
                or _asistente_respuesta_html(respuesta)
            ),
        }
        for key in ('confianza', 'categoria', 'baja_confianza'):
            if key in result:
                payload[key] = result[key]
        return JsonResponse(payload)
    except Exception as exc:
        logging.getLogger('tradeflow.ai').exception(
            'api_asistente local fallback failed: %s', exc,
        )
        return _asistente_json_payload(
            'I could not load the marketplace catalog right now. Please try again.',
            ok=False,
            status=503,
        )


# ── Sal firmado para QR de visitante ZLC (pre-registro) ─────────────────────
_QR_SALT = 'tradeflow.zlc.visitante'


_CFZ_DEFAULT_LAT = 9.3667


_CFZ_DEFAULT_LNG = -79.9000


def _cfz_map_marker_payload(request) -> dict:
    """Build Leaflet marker JSON for the free OSM company map."""
    markers = []
    from core.utils.seller_lifecycle import company_marketplace_visible, marketplace_active_company_ids

    visible_ids = marketplace_active_company_ids()
    empresas = Company.objects.filter(pk__in=visible_ids).annotate(
        n_activos=Count('products', filter=Q(products__is_active=True))
    ).order_by('name')

    for company in empresas:
        if not company_marketplace_visible(company):
            continue
        lat = float(company.latitud) if company.latitud is not None else _CFZ_DEFAULT_LAT
        lng = float(company.longitud) if company.longitud is not None else _CFZ_DEFAULT_LNG
        if lat == _CFZ_DEFAULT_LAT and lng == _CFZ_DEFAULT_LNG:
            lat += ((company.pk % 17) - 8) * 0.00018
            lng += ((company.pk % 23) - 11) * 0.00014

        cats = Category.objects.filter(
            products__company=company, products__is_active=True
        ).distinct()[:6]
        cat_txt = ', '.join(c.name for c in cats) or ''
        catalog_url = request.build_absolute_uri(
            reverse('catalogo_publico') + '?empresa=' + str(company.pk)
        )
        markers.append({
            'id': company.pk,
            'name': company.name,
            'lat': round(lat, 6),
            'lng': round(lng, 6),
            'verified': bool(company.is_verified),
            'products': company.n_activos,
            'categories': cat_txt,
            'catalog_url': catalog_url,
        })

    return {
        'center': {'lat': _CFZ_DEFAULT_LAT, 'lng': _CFZ_DEFAULT_LNG, 'zoom': 13},
        'markers': markers,
        'labels': {
            'verified': _('Verified seller'),
            'pending': _('Pending verification'),
            'products': _('products'),
            'view_catalog': _('View catalog'),
            'filter_placeholder': _('Filter companies…'),
            'verified_only': _('Verified only'),
            'companies_count': _('%(count)s companies on map'),
            'no_results': _('No companies match your filter'),
        },
    }


def mapa_zlc(request):
    """Interactive CFZ company map (Leaflet + OpenStreetMap)."""
    return render(request, 'core/mapa_zlc.html', {
        'map_payload': _cfz_map_marker_payload(request),
        'titulo_pagina': 'CFZ Map',
        'nav_activo': 'mapa_zlc',
        'marketplace_nav_active': 'map',
    })


def visitante_zlc_verificacion(request):
    """Public visitor check-in page reading signed token ``t``."""
    token = (request.GET.get('t') or '').strip()
    if not token:
        return render(
            request,
            'core/visitante_zlc_verificacion.html',
            {'error': 'Incomplete or invalid link.'},
            status=400,
        )
    try:
        payload = signing.loads(token, salt=_QR_SALT, max_age=60 * 60 * 24 * 365 * 3)
        uid = int(payload['uid'])
        subject = User.objects.select_related('profile').get(pk=uid, is_active=True)
    except (
        signing.BadSignature,
        signing.SignatureExpired,
        User.DoesNotExist,
        KeyError,
        TypeError,
        ValueError,
    ):
        return render(
            request,
            'core/visitante_zlc_verificacion.html',
            {'error': 'Code expired or altered. Request a new QR in TradeFlow.'},
            status=404,
        )

    profile = getattr(subject, 'profile', None)
    return render(
        request,
        'core/visitante_zlc_verificacion.html',
        {'error': None, 'subject': subject, 'profile': profile},
    )


def _visitante_qr_verify_url(request) -> str:
    """Absolute signed URL embedded in the visitor QR PNG."""
    from urllib.parse import urlencode

    token = signing.dumps({'uid': request.user.pk}, salt=_QR_SALT)
    base = request.build_absolute_uri(reverse('visitante_zlc_verificacion'))
    return base + '?' + urlencode({'t': token})


def _qr_png_bytes(payload: str) -> bytes:
    """Render a QR code PNG for the given payload string."""
    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0F2A44', back_color='#FFFFFF')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@login_required
def mi_qr(request):
    """Buyer page with large visitor QR, instructions, and download."""
    verify_url = _visitante_qr_verify_url(request)
    png = _qr_png_bytes(verify_url)
    b64 = base64.b64encode(png).decode('ascii')
    profile = getattr(request.user, 'profile', None)
    return render(request, 'core/mi_qr.html', {
        'verify_url':     verify_url,
        'qr_data_uri':    'data:image/png;base64,' + b64,
        'generated_at':   timezone.now(),
        'profile':        profile,
        'titulo_pagina':  'My CFZ QR code',
        'nav_activo':     'mi_qr',
    })


@login_required
def generar_qr_visitante(request):
    """Return the visitor QR PNG for download or embed."""
    verify_url = _visitante_qr_verify_url(request)
    png = _qr_png_bytes(verify_url)
    resp = HttpResponse(png, content_type='image/png')
    resp['Content-Disposition'] = 'attachment; filename="tradeflow-zlc-qr.png"'
    return resp
