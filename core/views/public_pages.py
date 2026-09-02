"""Páginas públicas legales y de marketing del marketplace."""
from __future__ import annotations

from django.conf import settings
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

from .catalog_cart import _contar_items, _get_carrito

@require_GET
@cache_control(public=True, max_age=3600)
def legal_terminos(request):
    """Terms of Use for the TradeFlow Colón marketplace."""
    return render(request, 'core/legal_terminos.html')


@require_GET
@cache_control(public=True, max_age=3600)
def legal_politicas_seguridad(request):
    """Términos de Uso y Política de Seguridad — documento completo (HTML estático)."""
    doc_path = settings.BASE_DIR / 'static' / 'legal' / 'politicas-seguridad-uso.html'
    if not doc_path.is_file():
        raise Http404('Document not found.')
    return HttpResponse(
        doc_path.read_bytes(),
        content_type='text/html; charset=utf-8',
    )


@cache_control(public=True, max_age=3600)
def acerca_tradeflow(request):
    """About TradeFlow — brand, ZLC, and buyer/seller programs."""
    from core.merchandising import home_stats

    stats = home_stats()
    return render(
        request,
        'core/acerca_tradeflow.html',
        {
            'stats': stats,
            'catalogo_stats': stats,
            'marketplace_nav_active': 'about',
        },
    )


def _marketplace_page_context(request):
    """Shared context for public marketplace marketing pages."""
    from core.merchandising import home_stats

    stats = home_stats()
    return {
        'stats': stats,
        'catalogo_stats': stats,
        'carrito_count': _contar_items(_get_carrito(request)),
    }


@cache_control(public=True, max_age=3600)
@catalog_access
def marketplace_verified_suppliers(request):
    """CFZ verified supplier directory marketing page."""
    from django.db.models import Count, Q

    from core import merchandising as merch
    from core.models import Company
    from core.utils.tradeflow_cache import cached_marketplace_categories_context

    ctx = _marketplace_page_context(request)
    ctx['marketplace_nav_active'] = 'verified'
    ctx.update(cached_marketplace_categories_context())

    empresas = list(
        Company.objects.filter(is_verified=True)
        .annotate(num_productos=Count('products', filter=Q(products__is_active=True)))
        .filter(num_productos__gt=0)
        .order_by('-carousel_priority', '-num_productos', 'name')
    )
    if len(empresas) > 4:
        destacadas = empresas[:3]
        empresas_grid = empresas[3:]
    else:
        destacadas = []
        empresas_grid = empresas
    merch.spotlight_products_for_companies(empresas, limit_per=4)
    ctx['empresas'] = empresas
    ctx['empresas_destacadas'] = destacadas
    ctx['empresas_grid'] = empresas_grid
    return render(request, 'core/marketplace_verified_suppliers.html', ctx)


@cache_control(public=True, max_age=3600)
@catalog_access
def marketplace_deals(request):
    """Active wholesale promotions marketing page."""
    from core import merchandising as merch
    from core.utils.tradeflow_cache import cached_marketplace_categories_context

    ctx = _marketplace_page_context(request)
    ctx['marketplace_nav_active'] = 'deals'
    ctx.update(cached_marketplace_categories_context())
    deals = merch.deals_page_products(48)
    ctx['daily_deals'] = deals
    ctx['spotlight_deals'] = deals[:8]
    ctx['deal_count'] = len([p for p in deals if p.is_on_promo_now])
    if ctx['deal_count'] == 0:
        ctx['deal_count'] = len(deals)
    return render(request, 'core/marketplace_deals.html', ctx)


@cache_control(public=True, max_age=3600)
@catalog_access
def marketplace_order_protection(request):
    """Explain the factual RFQ-to-purchase-order workflow."""
    from core.utils.tradeflow_cache import cached_marketplace_categories_context

    ctx = _marketplace_page_context(request)
    ctx['marketplace_nav_active'] = 'protection'
    ctx.update(cached_marketplace_categories_context())
    return render(request, 'core/marketplace_order_protection.html', ctx)


@require_GET
@cache_control(public=True, max_age=3600)
def legal_privacidad(request):
    """Privacy policy and data processing notice."""
    return render(request, 'core/legal_privacidad.html')


@require_GET
@cache_control(public=True, max_age=3600)
def legal_cookies(request):
    """Cookie policy and similar technologies notice."""
    return render(request, 'core/legal_cookies.html')
