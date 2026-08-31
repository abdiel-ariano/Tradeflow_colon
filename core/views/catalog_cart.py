"""Catálogo público, carrito de sesión, checkout, órdenes de compra y RFQ."""
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
    Address, Order, OrderItem, Shipment, Document,
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
from ..utils.product_availability import (
    public_availability_label,
    public_availability_status,
)
from ..utils.product_pdp_content import parse_product_description_sections

from .common import _request_wants_json, log

@admin_required
def api_productos(request):
    """Admin-only legacy JSON product listing with private inventory data."""
    productos = (
        Product.objects.filter(is_active=True)
        .select_related('category', 'company', 'inventory')
        .defer('company__owner')
    )
    buscar = request.GET.get('q', '')
    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar) | Q(sku__icontains=buscar)
        )
    data = [
        {
            'id':        p.id,
            'nombre':    p.name,
            'precio':    str(p.unit_price),
            'currency':  p.currency,
            'stock':     p.available_qty,
            'categoria': p.category.name if p.category else 'Uncategorized',
            'empresa':   p.company.name,
        }
        for p in productos[:20]
    ]
    return JsonResponse({'productos': data})


def _get_carrito(request):
    """Load the session cart dict for guest or buyer checkout."""
    return request.session.get('carrito', {})


def _save_carrito(request, carrito):
    """Persist the session cart and mark the session modified."""
    request.session['carrito'] = carrito
    request.session.modified = True
    _sync_cart_activity_profile(request, carrito)


def _sync_cart_activity_profile(request, carrito):
    """Mirror cart snapshot onto the buyer profile for abandonment mail."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return
    try:
        profile = user.profile
    except Exception:
        return
    if profile.role != 'buyer':
        return

    from django.utils import timezone

    count = _contar_items(carrito)
    profile.cart_items_count = count
    if count > 0:
        profile.cart_last_activity_at = timezone.now()
        profile.cart_reminder_sent_at = None
    else:
        profile.cart_last_activity_at = None
        profile.cart_reminder_sent_at = None
    profile.save(
        update_fields=[
            'cart_items_count',
            'cart_last_activity_at',
            'cart_reminder_sent_at',
        ],
    )


def _calcular_total(carrito):
    """Sum line subtotals for the session cart."""
    total = Decimal('0.00')
    for item in carrito.values():
        total += Decimal(item['subtotal'])
    return total


def _contar_items(carrito):
    """Count total units across session cart lines."""
    return sum(item['cantidad'] for item in carrito.values())


def _carrito_items_with_products(carrito):
    """Enrich session cart lines with Product rows for image fallbacks."""
    ids = []
    for key in carrito:
        try:
            ids.append(int(key))
        except (TypeError, ValueError):
            continue
    products = {}
    if ids:
        products = {
            p.pk: p
            for p in Product.objects.filter(pk__in=ids).select_related('category', 'company')
        }
    items = []
    for prod_id, item in carrito.items():
        try:
            pk = int(prod_id)
        except (TypeError, ValueError):
            pk = None
        items.append({
            'prod_id': prod_id,
            'item': item,
            'product': products.get(pk) if pk is not None else None,
        })
    return items


def _carrito_json_payload(
    carrito,
    *,
    line_product_id=None,
    line=None,
    disponible=None,
    removed=False,
    message='',
    ok=True,
):
    """Build a JSON body for cart AJAX responses."""
    payload = {
        'ok': ok,
        'message': str(message) if message else '',
        'carrito_count': _contar_items(carrito),
        'subtotal': str(_calcular_total(carrito)),
        'carrito_empty': not bool(carrito),
    }
    if removed and line_product_id is not None:
        payload['removed'] = str(line_product_id)
    elif line is not None and line_product_id is not None:
        payload['line'] = {
            'product_id': str(line_product_id),
            'cantidad': line['cantidad'],
            'precio': line['precio'],
            'subtotal': line['subtotal'],
        }
    return payload


def _tienda_pagination_slots(page_obj, on_each_side=2, on_ends=1):
    """Build elided page slots for the public catalog pager."""
    if not page_obj.has_other_pages():
        return []
    paginator = page_obj.paginator
    slots = []
    for entry in paginator.get_elided_page_range(
        page_obj.number, on_each_side=on_each_side, on_ends=on_ends
    ):
        if isinstance(entry, int):
            slots.append({'type': 'page', 'num': entry})
        else:
            slots.append({'type': 'ellipsis'})
    return slots


def _catalogo_filter_querystring(request, *, omit=()):
    """Active catalog filters as a query string (omit page/partial)."""
    qcopy = request.GET.copy()
    for key in ('page', 'partial', *omit):
        qcopy.pop(key, None)
    return qcopy.urlencode()


def _catalog_url_from_tienda_query(request):
    """Map legacy ``/tienda/`` query params to ``/catalogo/`` equivalents."""
    q = request.GET.copy()

    def _first(value):
        """Return the first non-empty query value from a MultiValueDict."""
        if value is None:
            return None
        if isinstance(value, list):
            return value[0] if value else None
        return value

    tab = _first(q.pop('tab', None))
    if tab is None:
        if q.get('destacados') == '1':
            tab = 'destacados'
        elif q.get('ofertas') == '1':
            tab = 'ofertas'
    q.pop('destacados', None)
    q.pop('ofertas', None)

    if tab == 'ofertas':
        q['on_sale'] = '1'
    elif tab == 'destacados':
        q['featured'] = '1'
    elif tab == 'bestsellers':
        q['bestseller'] = '1'

    q.pop('vista', None)

    orden = _first(q.pop('orden', None))
    if orden and orden != 'nombre' and orden in (
        'precio_asc', 'precio_desc', 'novedades', 'relevancia',
    ):
        q['orden'] = orden

    qs = q.urlencode()
    base = reverse('catalogo_publico')
    return f'{base}?{qs}' if qs else base


@catalog_access
def catalogo_publico(request):
    """Public read-only guest catalog with filters and product grid.
    
    No login required; cart/inquiry actions use session storage
    until OTP and checkout.
    """
    from decimal import Decimal, InvalidOperation

    from django.db.models import Case, DecimalField, F, IntegerField, When

    from .. import merchandising as merch
    from core.utils.tradeflow_cache import (
        cached_catalog_categories,
        cached_catalog_empresas,
        cached_category_spotlights,
        cached_marketplace_categories_context,
        cached_verified_company_count,
    )

    catalogo_base = merch.active_products_base()
    stats = merch.home_stats()
    is_guest = not request.user.is_authenticated
    if is_guest:
        role = None
    else:
        try:
            role = request.user.profile.role
        except Exception:
            role = None
    show_cart_actions = is_guest or role in ('buyer', 'admin') or request.user.is_superuser
    verified_empresas = cached_verified_company_count()

    buscar = request.GET.get('buscar', '').strip()
    categorias_sel = [c for c in request.GET.getlist('categoria') if c.strip()]
    empresa = request.GET.get('empresa', '').strip()
    precio_min = request.GET.get('precio_min', '').strip()
    precio_max = request.GET.get('precio_max', '').strip()
    solo_stock = request.GET.get('stock', '') in ('1', 'true', 'on')
    solo_stock_low = request.GET.get('stock_low', '') in ('1', 'true', 'on')
    solo_on_sale = request.GET.get('on_sale', '') in ('1', 'true', 'on')
    solo_verificado = request.GET.get('verificado', '') == '1'
    solo_featured = request.GET.get('featured', '') in ('1', 'true', 'on')
    solo_bestseller = request.GET.get('bestseller', '') in ('1', 'true', 'on')
    orden = request.GET.get('orden', 'relevancia').strip() or 'relevancia'

    productos = catalogo_base.annotate(
        sort_price=Case(
            When(
                promo_price__isnull=False,
                promo_price__lt=F('unit_price'),
                then=F('promo_price'),
            ),
            default=F('unit_price'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        avail_qty=Case(
            When(inventory__isnull=False, then=F('inventory__stock_qty') - F('inventory__reserved_qty')),
            default=0,
            output_field=IntegerField(),
        ),
    )

    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar)
            | Q(description__icontains=buscar)
            | Q(sku__icontains=buscar)
        )

    if categorias_sel:
        productos = productos.filter(category_id__in=categorias_sel)

    if empresa:
        productos = productos.filter(company_id=empresa)

    if solo_stock:
        productos = productos.filter(avail_qty__gt=0)

    if solo_stock_low:
        productos = productos.filter(
            avail_qty__gt=0,
            avail_qty__lte=F('inventory__low_stock_alert'),
        )

    if solo_on_sale:
        productos = productos.filter(
            promo_price__isnull=False,
            promo_price__lt=F('unit_price'),
        )

    if solo_featured:
        productos = productos.filter(is_featured=True)

    if solo_bestseller:
        productos = productos.filter(is_bestseller=True)

    if solo_verificado:
        productos = productos.filter(company__is_verified=True)

    try:
        if precio_min:
            productos = productos.filter(sort_price__gte=Decimal(precio_min))
    except (InvalidOperation, ValueError):
        precio_min = ''

    try:
        if precio_max:
            productos = productos.filter(sort_price__lte=Decimal(precio_max))
    except (InvalidOperation, ValueError):
        precio_max = ''

    orden_map = {
        'relevancia': None,
        'precio_asc': 'sort_price',
        'precio_desc': '-sort_price',
        'novedades': '-created_at',
    }
    orden_key = orden if orden in orden_map else 'relevancia'
    if orden_key == 'relevancia':
        from ..utils.ads_ranking import annotate_sponsored_score

        productos = annotate_sponsored_score(productos).order_by('-sponsored_score', 'name')
    else:
        productos = productos.order_by(orden_map[orden_key])

    total_resultados = productos.count()
    paginator = Paginator(productos, 24)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    categorias = cached_catalog_categories()
    empresas = cached_catalog_empresas()

    sugerencias = [
        c.name
        for c in sorted(
            categorias,
            key=lambda c: (-getattr(c, 'num_productos', 0), c.name),
        )[:5]
    ]
    if not sugerencias:
        sugerencias = ['Electronics', 'Textiles', 'Logistics', 'Spare parts']

    qcopy = request.GET.copy()
    qcopy.pop('page', None)
    qcopy.pop('partial', None)
    catalogo_params = qcopy.urlencode()

    meta_description = _(
        'Explore %(products)s wholesale products from %(companies)s verified '
        'Colón Free Zone companies. B2B catalog with transparent inventory on TradeFlow.'
    ) % {
        'products': stats['productos'],
        'companies': verified_empresas or stats['empresas'],
    }

    context = {
        'productos': page_obj,
        'buscar': buscar,
        'categorias': categorias,
        'categorias_sel': categorias_sel,
        'empresas': empresas,
        'empresa': empresa,
        'precio_min': precio_min,
        'precio_max': precio_max,
        'solo_stock': solo_stock,
        'solo_stock_low': solo_stock_low,
        'solo_on_sale': solo_on_sale,
        'solo_verificado': solo_verificado,
        'orden': orden_key,
        'catalogo_params': catalogo_params,
        'catalogo_q_sin_categoria': _catalogo_filter_querystring(request, omit=('categoria',)),
        'catalogo_stats': stats,
        'verified_empresas': verified_empresas,
        'total_resultados': total_resultados,
        'sugerencias': sugerencias,
        'pagination_slots': _tienda_pagination_slots(page_obj),
        'meta_description': meta_description,
        'titulo_pagina': _('Catalog'),
        'nav_activo': 'catalogo',
        'carrito_count': _contar_items(_get_carrito(request)),
        'category_spotlights': cached_category_spotlights(4, 4),
        'show_cart_actions': show_cart_actions,
        'is_guest_catalog': is_guest,
    }
    context.update(cached_marketplace_categories_context())

    is_partial = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.GET.get('partial') == '1'
    )
    if is_partial:
        return render(request, 'core/catalogo_publico_partial.html', context)
    response = render(request, 'core/catalogo_publico.html', context)
    if is_guest:
        # private: carrito/sesión de invitados; no CDN compartida.
        response['Cache-Control'] = 'private, max-age=30'
    return response


@catalog_access
def tienda(request):
    """Legacy ``/tienda/`` URL — permanent redirect to the guest catalog."""
    return redirect(_catalog_url_from_tienda_query(request), permanent=True)


@catalog_access
def catalogo_producto_detail(request, pk):
    """Public product detail for the guest catalog (login optional)."""
    from django.templatetags.static import static
    from django.urls import reverse

    product = get_object_or_404(
        Product.objects.select_related('company', 'category', 'inventory'),
        pk=pk,
        is_active=True,
    )
    is_guest = not request.user.is_authenticated
    role = None
    if not is_guest:
        try:
            role = request.user.profile.role
        except Exception:
            role = None
    show_cart_actions = is_guest or role in ('buyer', 'admin') or request.user.is_superuser

    related_products = list(
        Product.objects.filter(is_active=True, category=product.category_id)
        .exclude(pk=product.pk)
        .select_related('company', 'category', 'inventory')
        .order_by('-merchandising_priority', '-is_featured', 'name')[:4]
    )
    if len(related_products) < 4:
        existing_ids = [p.pk for p in related_products]
        extra = list(
            Product.objects.filter(is_active=True, company=product.company_id)
            .exclude(pk=product.pk)
            .exclude(pk__in=existing_ids)
            .select_related('company', 'category', 'inventory')
            .order_by('-merchandising_priority', 'name')[: 4 - len(related_products)]
        )
        related_products.extend(extra)

    company = product.company
    stock_status = public_availability_status(product.available_qty)
    stock_label = public_availability_label(product.available_qty)
    can_request_quote = show_cart_actions and stock_status != 'out'
    pdp_description = parse_product_description_sections(product.description)

    img = product_image_url(product)
    if img:
        og_image = img if img.startswith('http') else request.build_absolute_uri(img)
    else:
        og_image = request.build_absolute_uri(static('images/placeholder-producto.svg'))

    meta_description = (
        product.description[:155].strip()
        if product.description
        else _(
            '%(name)s from %(company)s in the Colón Free Zone — TradeFlow Colón.'
        ) % {'name': product.name, 'company': company.name}
    )

    return render(
        request,
        'core/catalogo_producto_detail.html',
        {
            'product': product,
            'company': company,
            'show_cart_actions': show_cart_actions,
            'is_guest': is_guest,
            'related_products': related_products,
            'stock_status': stock_status,
            'stock_label': stock_label,
            'can_request_quote': can_request_quote,
            'pdp_description': pdp_description,
            'meta_description': meta_description,
            'og_image': og_image,
            'canonical_url': request.build_absolute_uri(
                reverse('catalogo_producto_detail', args=[product.pk]),
            ),
            'titulo_pagina': product.name,
            'nav_activo': 'tienda',
        },
    )


# Alias legacy (misma ruta, nombre anterior)
catalogo_producto = catalogo_producto_detail


def _append_product_to_carrito(request, producto_id, cantidad=1, *, success_template=None):
    """Add or increment a product in the session cart."""
    cantidad = int(cantidad)
    producto = get_object_or_404(
        Product.objects.select_related('inventory'),
        pk=producto_id,
        is_active=True,
    )
    disponible = producto.available_qty
    precio = producto.display_price

    if cantidad < 1:
        return False, {'message': _('Quantity must be at least 1.'), 'status': 400}

    if disponible == 0:
        return False, {
            'message': _('"%(name)s" has no stock available.') % {'name': producto.name},
            'status': 400,
        }

    carrito = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key in carrito:
        nueva_cantidad = carrito[producto_key]['cantidad'] + cantidad
        if nueva_cantidad > disponible:
            nueva_cantidad = disponible
        carrito[producto_key]['cantidad'] = nueva_cantidad
        carrito[producto_key]['subtotal'] = str(Decimal(precio) * nueva_cantidad)
    else:
        if cantidad > disponible:
            cantidad = disponible
        carrito[producto_key] = {
            'nombre': producto.name,
            'precio': str(precio),
            'cantidad': cantidad,
            'subtotal': str(precio * cantidad),
            'imagen': product_image_url(producto) or '',
        }

    _save_carrito(request, carrito)
    if success_template:
        ok_msg = success_template % {'name': producto.name}
    else:
        ok_msg = _('"%(name)s" added to inquiry cart.') % {'name': producto.name}
    return True, {
        'message': ok_msg,
        'carrito_count': _contar_items(carrito),
        'producto_id': producto_id,
        'cantidad_en_carrito': carrito[producto_key]['cantidad'],
    }


@catalog_access
def catalogo_agregar_inquiry(request, producto_id):
    """Add to the session inquiry cart from the guest catalog."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': _('Method not allowed.')}, status=405)

    try:
        cantidad = int(request.POST.get('cantidad', 1))
    except (TypeError, ValueError):
        cantidad = 1

    ok, payload = _append_product_to_carrito(
        request,
        producto_id,
        cantidad,
        success_template=_('"%(name)s" added to inquiry cart.'),
    )
    if not ok:
        status = payload.pop('status', 400)
        if _request_wants_json(request):
            return JsonResponse({'ok': False, **payload}, status=status)
        messages.error(request, payload.get('message', ''))
        return redirect('catalogo_publico')

    if _request_wants_json(request):
        return JsonResponse({'ok': True, **payload})
    messages.success(request, payload['message'])
    return redirect('catalogo_publico')


@guest_or_buyer_cart
def agregar_al_carrito(request, producto_id):
    """Add a product to the cart or increase its quantity."""
    if request.method != 'POST':
        return redirect('catalogo_publico')

    try:
        cantidad = int(request.POST.get('cantidad', 1))
    except (TypeError, ValueError):
        cantidad = 1

    ok, payload = _append_product_to_carrito(request, producto_id, cantidad)
    if not ok:
        status = payload.pop('status', 400)
        if _request_wants_json(request):
            return JsonResponse({'ok': False, **payload}, status=status)
        messages.error(request, payload.get('message', ''))
        return redirect('catalogo_publico')

    if _request_wants_json(request):
        return JsonResponse({'ok': True, **payload})
    messages.success(request, payload['message'])
    return redirect('catalogo_publico')


@guest_or_buyer_cart
def quitar_del_carrito(request, producto_id):
    """Remove a product line from the session cart."""
    if request.method != 'POST':
        return redirect('ver_carrito')

    carrito     = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key in carrito:
        nombre = carrito[producto_key]['nombre']
        del carrito[producto_key]
        _save_carrito(request, carrito)
        ok_msg = _('"%(name)s" removed from cart.') % {'name': nombre}
        if _request_wants_json(request):
            return JsonResponse({
                'ok': True,
                'message': ok_msg,
                'carrito_count': _contar_items(carrito),
            })
        messages.info(request, ok_msg)

    if _request_wants_json(request):
        return JsonResponse({'ok': True, 'message': '', 'carrito_count': _contar_items(carrito)})
    return redirect('ver_carrito')


@guest_or_buyer_cart
def ver_carrito(request):
    """Render the current guest/buyer session cart."""
    carrito = _get_carrito(request)
    total   = _calcular_total(carrito)

    subtotal = total
    envio = Decimal('0') if subtotal >= Decimal('500') or not carrito else Decimal('99')
    impuestos = (subtotal * Decimal('0.16')).quantize(Decimal('0.01'))
    total_general = (subtotal + envio + impuestos).quantize(Decimal('0.01'))

    context = {
        'carrito':       carrito,
        'carrito_items': _carrito_items_with_products(carrito),
        'total':         total,
        'subtotal':      subtotal,
        'envio':         envio,
        'impuestos':     impuestos,
        'total_general': total_general,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'My cart',
        'nav_activo':    'tienda',
    }
    return render(request, 'core/carrito.html', context)


@guest_or_buyer_cart
@require_POST
def actualizar_cantidad_carrito(request, producto_id):
    """Update quantity for one session cart line."""
    wants_json = _request_wants_json(request)
    try:
        cantidad = int(request.POST.get('cantidad', 0))
    except (TypeError, ValueError):
        cantidad = 0

    carrito = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key not in carrito:
        msg = _('Product not found in cart.')
        if wants_json:
            return JsonResponse(
                _carrito_json_payload(carrito, message=msg, ok=False),
                status=404,
            )
        messages.error(request, msg)
        return redirect('ver_carrito')

    producto = get_object_or_404(
        Product.objects.select_related('inventory'),
        pk=producto_id,
        is_active=True,
    )
    disponible = producto.available_qty

    if cantidad <= 0:
        nombre = carrito[producto_key]['nombre']
        del carrito[producto_key]
        _save_carrito(request, carrito)
        msg = _('"%(name)s" removed from cart.') % {'name': nombre}
        if wants_json:
            return JsonResponse(_carrito_json_payload(
                carrito,
                line_product_id=producto_id,
                removed=True,
                message=msg,
            ))
        messages.success(request, msg)
        return redirect('ver_carrito')

    if cantidad > disponible:
        msg = _('Requested quantity exceeds available stock.')
        if wants_json:
            return JsonResponse(
                _carrito_json_payload(
                    carrito,
                    line_product_id=producto_id,
                    line=carrito[producto_key],
                    message=msg,
                    ok=False,
                ),
                status=400,
            )
        messages.error(request, msg)
        return redirect('ver_carrito')

    precio = Decimal(carrito[producto_key]['precio'])
    carrito[producto_key]['cantidad'] = cantidad
    carrito[producto_key]['subtotal'] = str((precio * cantidad).quantize(Decimal('0.01')))
    _save_carrito(request, carrito)
    line = carrito[producto_key]
    if wants_json:
        return JsonResponse(_carrito_json_payload(
            carrito,
            line_product_id=producto_id,
            line=line,
        ))
    return redirect('ver_carrito')


@guest_or_buyer_cart
@require_POST
def vaciar_carrito(request):
    """Clear all products from the session cart."""
    _save_carrito(request, {})
    messages.success(request, _('Cart cleared.'))
    return redirect('ver_carrito')


@buyer_checkout
def checkout(request):
    """Review the inquiry cart and create one formal RFQ per supplier.

    This quote-first step never creates an order, payment, shipment, or
    inventory reservation. Each verified supplier receives its own pending
    Cotizacion containing only that company's products.
    """
    from core.utils.access_gating import user_needs_otp_verification

    carrito = _get_carrito(request)
    if not carrito:
        messages.warning(request, _('Your cart is empty.'))
        return redirect('catalogo_publico')

    product_ids = []
    for raw_id in carrito:
        try:
            product_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    products = {
        product.pk: product
        for product in (
            Product.objects.filter(
                pk__in=product_ids,
                is_active=True,
                company__verification_status='verified',
            )
            .select_related('company')
        )
    }

    grouped = {}
    skipped_count = 0
    for raw_id, item_data in carrito.items():
        try:
            product = products.get(int(raw_id))
        except (TypeError, ValueError):
            product = None
        if product is None or not product.company_id:
            skipped_count += 1
            continue

        try:
            qty = max(1, int(item_data.get('cantidad', 1)))
        except (TypeError, ValueError):
            qty = 1

        reference_price = product.display_price
        reference_total = reference_price * qty
        group = grouped.setdefault(
            product.company_id,
            {
                'company': product.company,
                'items': [],
                'reference_subtotal': Decimal('0.00'),
            },
        )
        group['items'].append(
            {
                'product': product,
                'quantity': qty,
                'reference_price': reference_price,
                'reference_total': reference_total,
            },
        )
        group['reference_subtotal'] += reference_total

    rfq_groups = sorted(
        grouped.values(),
        key=lambda group: group['company'].name.lower(),
    )
    if not rfq_groups:
        messages.error(
            request,
            _(
                'The inquiry cart has no active products from verified suppliers. '
                'Review the catalog and try again.'
            ),
        )
        return redirect('ver_carrito')

    reference_subtotal = sum(
        (group['reference_subtotal'] for group in rfq_groups),
        Decimal('0.00'),
    )
    products_count = sum(len(group['items']) for group in rfq_groups)

    if request.method == 'POST':
        try:
            validity_days = int(request.POST.get('validez_dias', '30') or '30')
        except (TypeError, ValueError):
            validity_days = 30
        validity_days = min(max(validity_days, 1), 90)
        buyer_notes = request.POST.get('notas', '').strip()
        batch = uuid.uuid4().hex[:12]
        created_quotes = []

        with transaction.atomic():
            for group in rfq_groups:
                quote = Cotizacion.objects.create(
                    buyer=request.user,
                    empresa=group['company'],
                    notas_buyer=buyer_notes,
                    validez_dias=validity_days,
                    lote=batch,
                )
                CotizacionItem.objects.bulk_create(
                    [
                        CotizacionItem(
                            cotizacion=quote,
                            product=line['product'],
                            cantidad_solicitada=line['quantity'],
                        )
                        for line in group['items']
                    ],
                )
                created_quotes.append(quote)

        _save_carrito(request, {})
        messages.success(
            request,
            _('%(count)s formal quote request(s) sent to verified suppliers.')
            % {'count': len(created_quotes)},
        )
        return redirect('mis_cotizaciones')

    context = {
        'carrito': carrito,
        'rfq_groups': rfq_groups,
        'suppliers_count': len(rfq_groups),
        'products_count': products_count,
        'skipped_count': skipped_count,
        'subtotal': reference_subtotal,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': _('Request for Quotation'),
        'nav_activo': 'tienda',
    }

    if user_needs_otp_verification(request.user):
        from core.auth_views import _verify_context
        from core.utils.email_config import explain_email_failure
        from core.utils.otp_delivery import ensure_otp_sent

        verify_ctx = _verify_context(request)
        verify_ctx['next_url'] = reverse('checkout')
        verify_ctx['verify_for_checkout'] = True
        verify_ctx['inline'] = True
        ok, status = ensure_otp_sent(request, request.user)
        if ok and status == 'sent':
            messages.success(
                request,
                _('We sent a 6-digit code to %(email)s. Check your inbox and spam folder.')
                % {'email': request.user.email},
            )
        elif not ok and status not in ('no_email',):
            messages.error(request, explain_email_failure(status))
        context['needs_email_verify'] = True
        context.update(verify_ctx)

    return render(request, 'core/checkout.html', context)

@buyer_required
def mis_ordenes(request):
    """Buyer order history for the authenticated account."""
    ordenes = (
        Order.objects
        .filter(buyer=request.user)
        .select_related('buyer')
        .prefetch_related('items__product')
        .order_by('-created_at')
    )

    # Filtro opcional por estado
    estado = request.GET.get('estado', '').strip()
    if estado:
        ordenes = ordenes.filter(status=estado)

    paginator = Paginator(ordenes, 8)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'ordenes':        page_obj,
        'estado_actual':  estado,
        'status_choices': Order.STATUS_CHOICES,
        'carrito_count':  _contar_items(_get_carrito(request)),
        'titulo_pagina':  'My orders',
        'nav_activo':     'mis_ordenes',
    }
    return render(request, 'core/mis_ordenes.html', context)


@buyer_required
def detalle_mi_orden(request, pk):
    """Buyer detail for one of their marketplace orders."""
    orden = get_object_or_404(
        Order.objects.select_related('buyer', 'ship_address').prefetch_related(
            Prefetch(
                'items',
                queryset=OrderItem.objects.select_related('product__company').defer(
                    'product__company__owner'
                ),
            )
        ),
        pk=pk,
        buyer=request.user,  # Clave de seguridad
    )

    context = {
        'orden':         orden,
        'pago':          getattr(orden, 'payment', None),
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': f'Order {orden.order_number}',
        'nav_activo':    'mis_ordenes',
    }
    return render(request, 'core/detalle_mi_orden.html', context)


@login_required
def descargar_factura(request, orden_pk):
    """Generate and download the order invoice PDF."""
    orden = get_object_or_404(
        Order.objects.select_related('buyer').prefetch_related('items__product__company'),
        pk=orden_pk,
    )
    if orden.buyer_id != request.user.id and not (
        request.user.is_superuser or getattr(getattr(request.user, 'profile', None), 'role', None) == 'admin'
    ):
        raise Http404()

    pdf_bytes = generar_factura_pdf(orden)
    filename = f"factura_{orden.order_number}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def descargar_packing_list(request, orden_pk):
    """Download the packing-list PDF for an order."""
    orden = get_object_or_404(
        Order.objects.select_related('buyer').prefetch_related('items__product__company'),
        pk=orden_pk,
    )
    if orden.buyer_id != request.user.id and not (
        request.user.is_superuser or getattr(getattr(request.user, 'profile', None), 'role', None) == 'admin'
    ):
        raise Http404()

    pdf_bytes = generar_packing_list_pdf(orden)
    filename = f"packing_list_{orden.order_number}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def descargar_cotizacion_pdf(request, pk):
    """Download the formal RFQ PDF (buyer owner only)."""
    cotizacion = get_object_or_404(
        Cotizacion.objects.select_related('buyer', 'empresa').prefetch_related(
            'items__product',
        ),
        pk=pk,
        buyer=request.user,
    )
    pdf_bytes = generar_cotizacion_pdf(cotizacion)
    filename = f"cotizacion_{cotizacion.numero}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@buyer_required
def solicitar_cotizacion(request):
    """Buyer requests a formal quote from a CFZ seller company."""
    empresas = (
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('name')
    )

    empresa_id = request.GET.get('empresa', '').strip()
    empresa_obj = None
    productos_emp = []
    if empresa_id:
        empresa_obj = get_object_or_404(Company, pk=int(empresa_id))
        productos_emp = (
            Product.objects.filter(company=empresa_obj, is_active=True)
            .select_related('category', 'inventory')
            .defer('company__owner')
            .order_by('name')
        )

    if request.method == 'POST':
        eid = request.POST.get('empresa_id', '').strip()
        if not eid:
            messages.error(request, 'Select a company.')
            return redirect('solicitar_cotizacion')
        empresa_dest = get_object_or_404(Company, pk=int(eid))
        try:
            validez = int(request.POST.get('validez_dias', '30') or '30')
        except ValueError:
            validez = 30
        if validez < 1:
            validez = 1
        notas_buyer = request.POST.get('notas_buyer', '').strip()

        lines = []
        seen = set()
        for key, raw in request.POST.items():
            if not key.startswith('qty_'):
                continue
            try:
                pid = int(key.replace('qty_', '', 1))
            except ValueError:
                continue
            try:
                qty = int(raw or '0')
            except ValueError:
                qty = 0
            if qty <= 0 or pid in seen:
                continue
            seen.add(pid)
            prod = Product.objects.filter(
                pk=pid, company=empresa_dest, is_active=True
            ).first()
            if prod:
                lines.append((prod, qty))

        if not lines:
            messages.error(request, 'Specify at least one product with quantity greater than zero.')
            return redirect(f"{reverse('solicitar_cotizacion')}?empresa={empresa_dest.pk}")

        with transaction.atomic():
            cot = Cotizacion.objects.create(
                buyer=request.user,
                empresa=empresa_dest,
                notas_buyer=notas_buyer,
                validez_dias=validez,
            )
            for prod, qty in lines:
                CotizacionItem.objects.create(
                    cotizacion=cot,
                    product=prod,
                    cantidad_solicitada=qty,
                )

        messages.success(request, f'Quote {cot.numero} sent to {empresa_dest.name}.')
        return redirect('detalle_cotizacion', pk=cot.pk)

    context = {
        'empresas': empresas,
        'empresa_obj': empresa_obj,
        'empresa_id': empresa_id,
        'productos_emp': productos_emp,
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': 'New quote',
        'nav_activo': 'mis_cotizaciones',
    }
    return render(request, 'core/cotizacion_form.html', context)


def _normalizar_nombre(texto):
    """Normalize a name to match the same SKU across companies."""
    base = (texto or '').strip().lower()
    base = ''.join(
        c for c in unicodedata.normalize('NFKD', base)
        if not unicodedata.combining(c)
    )
    return ' '.join(base.split())


def _empresas_con_producto(base_product, limite=25):
    """Return [(company, product)] for sellers offering the same item."""
    nombre_norm = _normalizar_nombre(base_product.name)
    sku_norm = (base_product.sku or '').strip().lower()

    filtro = Q(name__iexact=(base_product.name or '').strip())
    if sku_norm:
        filtro |= Q(sku__iexact=(base_product.sku or '').strip())
    palabras = [p for p in nombre_norm.split() if len(p) >= 3]
    if palabras:
        filtro |= Q(name__icontains=palabras[0])

    candidatos = (
        Product.objects.filter(is_active=True)
        .filter(filtro)
        .select_related('company', 'inventory')
    )

    mejor_por_empresa = {}
    for prod in candidatos:
        if not prod.company_id:
            continue
        coincide_nombre = _normalizar_nombre(prod.name) == nombre_norm
        coincide_sku = bool(sku_norm) and (prod.sku or '').strip().lower() == sku_norm
        if not (coincide_nombre or coincide_sku):
            continue
        actual = mejor_por_empresa.get(prod.company_id)
        if actual is None or prod.display_price < actual.display_price:
            mejor_por_empresa[prod.company_id] = prod

    resultado = [(p.company, p) for p in mejor_por_empresa.values()]
    resultado.sort(key=lambda par: (par[1].display_price, par[0].name.lower()))
    return resultado[:limite]


@buyer_required
@require_POST
def solicitar_cotizacion_automatica(request, producto_id):
    """Auto-RFQ every company that sells the same product."""
    base = get_object_or_404(
        Product.objects.select_related('company'),
        pk=producto_id,
        is_active=True,
    )

    try:
        qty = int(request.POST.get('cantidad', '1') or '1')
    except (TypeError, ValueError):
        qty = 1
    if qty < 1:
        qty = 1
    notas_buyer = request.POST.get('notas_buyer', '').strip()

    matches = _empresas_con_producto(base)
    if not matches:
        messages.error(
            request,
            'We found no companies selling this product to quote.',
        )
        return redirect('catalogo_publico')

    lote = uuid.uuid4().hex[:12]
    nota_auto = 'Automatic quote generated with the current catalog price.'
    creadas = 0
    with transaction.atomic():
        for company, prod in matches:
            cot = Cotizacion.objects.create(
                buyer=request.user,
                empresa=company,
                estado='respondida',
                es_automatica=True,
                lote=lote,
                notas_buyer=notas_buyer,
                notas_seller=nota_auto,
                validez_dias=30,
            )
            CotizacionItem.objects.create(
                cotizacion=cot,
                product=prod,
                cantidad_solicitada=qty,
                precio_ofertado=prod.display_price,
            )
            creadas += 1

    messages.success(
        request,
        f'We generated {creadas} automatic quote(s) for "{base.name}". '
        f'Compare them and choose the best one.',
    )
    return redirect('comparar_cotizaciones', lote=lote)


@buyer_required
def comparar_cotizaciones(request, lote):
    """Compare automatic quotes created in the same RFQ batch."""
    cots = (
        Cotizacion.objects.filter(buyer=request.user, lote=lote)
        .select_related('empresa', 'order')
        .prefetch_related(
            Prefetch(
                'items',
                queryset=CotizacionItem.objects.select_related('product'),
            )
        )
        .order_by('created_at')
    )
    cots = list(cots)
    if not cots:
        messages.warning(request, 'We could not find that quote comparison.')
        return redirect('mis_cotizaciones')

    filas = []
    for c in cots:
        items = list(c.items.all())
        total = sum((it.linea_total or Decimal('0.00')) for it in items)
        filas.append({'cot': c, 'items': items, 'total': total})
    filas.sort(key=lambda f: f['total'])
    for i, fila in enumerate(filas):
        fila['mejor_precio'] = (i == 0)

    primer_item = filas[0]['items'][0] if filas[0]['items'] else None
    producto_nombre = primer_item.product.name if primer_item else 'product'
    cantidad = primer_item.cantidad_solicitada if primer_item else 1

    context = {
        'filas': filas,
        'lote': lote,
        'producto_nombre': producto_nombre,
        'cantidad': cantidad,
        'total_empresas': len(filas),
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': f'Compare quotes — {producto_nombre}',
        'nav_activo': 'mis_cotizaciones',
    }
    return render(request, 'core/comparar_cotizaciones.html', context)


@buyer_required
def mis_cotizaciones(request):
    """List the buyer's RFQs with company, status, and dates."""
    lista = (
        Cotizacion.objects.filter(buyer=request.user)
        .select_related('empresa', 'order')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    context = {
        'cotizaciones': lista,
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': 'My quotes',
        'nav_activo': 'mis_cotizaciones',
    }
    return render(request, 'core/mis_cotizaciones.html', context)


@buyer_required
def detalle_cotizacion(request, pk):
    """RFQ detail with line items and offered prices when answered."""
    cot = get_object_or_404(
        Cotizacion.objects.select_related('empresa', 'buyer', 'order').prefetch_related(
            Prefetch(
                'items',
                queryset=CotizacionItem.objects.select_related('product', 'product__category').defer(
                    'product__company__owner'
                ),
            )
        ),
        pk=pk,
        buyer=request.user,
    )

    if request.method == 'POST':
        accion = request.POST.get('accion', '').strip()
        if accion == 'rechazar' and cot.estado in ('pendiente', 'respondida'):
            cot.estado = 'rechazada'
            cot.save(update_fields=['estado', 'updated_at'])
            messages.info(request, 'Quote marked as rejected.')
            return redirect('detalle_cotizacion', pk=cot.pk)

        if accion == 'convertir' and cot.estado == 'respondida' and not cot.order_id:
            items = list(cot.items.all())
            if not items or any(it.precio_ofertado is None for it in items):
                messages.error(request, 'Quote does not have complete pricing to create the order.')
                return redirect('detalle_cotizacion', pk=cot.pk)

            addr = Address.objects.filter(user=request.user).order_by('-is_default', 'id').first()

            with transaction.atomic():
                orden = Order.objects.create(
                    buyer=request.user,
                    ship_address=addr,
                    order_type='b2b',
                    shipping_cost=Decimal('0.00'),
                    notes=f'Generated from quote {cot.numero}',
                    status='pending',
                    confirming_company=cot.empresa,
                    seller_confirmation_status='accepted',
                    confirmado_por_empresa=True,
                )
                items_ok = 0
                for it in items:
                    prod = it.product
                    qty = it.cantidad_solicitada
                    if prod.available_qty < qty:
                        orden.delete()
                        messages.error(
                            request,
                            f'Insufficient stock for "{prod.name}". Order was not created.',
                        )
                        return redirect('detalle_cotizacion', pk=cot.pk)
                    OrderItem.objects.create(
                        order=orden,
                        product=prod,
                        qty=qty,
                        unit_price_snapshot=it.precio_ofertado,
                    )
                    if hasattr(prod, 'inventory'):
                        prod.inventory.reserve(qty)
                    items_ok += 1

                if items_ok == 0:
                    orden.delete()
                    messages.error(request, 'Could not create the order.')
                    return redirect('detalle_cotizacion', pk=cot.pk)

                orden.recalculate_totals()
                orden.save(update_fields=['subtotal', 'total', 'updated_at'])
                # Accepting a supplier quote creates a pending purchase order.
                # Payment is a later, explicit business event; never fabricate one.
                cot.order = orden
                cot.estado = 'aceptada'
                cot.save(update_fields=['order', 'estado', 'updated_at'])

            messages.success(
                request,
                f'Purchase order {orden.order_number} created from the accepted supplier quote. '
                'Payment and logistics remain pending; no payment has been recorded.',
            )
            return redirect('detalle_mi_orden', pk=orden.pk)

        return redirect('detalle_cotizacion', pk=cot.pk)

    total_ofertado = Decimal('0.00')
    for it in cot.items.all():
        if it.linea_total is not None:
            total_ofertado += it.linea_total

    valida_hasta = cot.created_at + timedelta(days=cot.validez_dias)

    orden_detail_url = ''
    if cot.order_id:
        orden_detail_url = reverse('detalle_mi_orden', args=[cot.order_id])

    context = {
        'cot': cot,
        'total_ofertado': total_ofertado,
        'valida_hasta': valida_hasta,
        'orden_detail_url': orden_detail_url,
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': f'Quote {cot.numero}',
        'nav_activo': 'mis_cotizaciones',
    }
    return render(request, 'core/detalle_cotizacion.html', context)
