"""
=============================================================================
TRADEFLOW COLÓN — core/views.py  (v5 — Portal vendedor + Roles)
=============================================================================
Incluye: autenticación, admin, portal comprador (tienda, carrito, checkout),
portal vendedor (panel, productos, ventas) y API JSON de productos.
=============================================================================
"""
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
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import base64
import html as html_module
import io
import json
import logging

import folium
import qrcode
from folium.plugins import MarkerCluster
from django.core import signing

from .decorators import admin_required, buyer_required, seller_required
from .forms import SellerProductForm, SellerInventoryForm
from .models import (
    UserProfile, Company, Category, Product, Inventory,
    Address, Order, OrderItem, Payment, Shipment, Document,
    Cotizacion, CotizacionItem,
)
from .utils.email_sender import (
    enviar_bienvenida,
    enviar_cambio_estado,
    enviar_confirmacion_orden,
    enviar_verificacion_email,
)
from .utils.pdf_generator import (
    generar_cotizacion_pdf,
    generar_factura_pdf,
    generar_packing_list_pdf,
)

log = logging.getLogger(__name__)


def _normalize_dashboard_dias(raw):
    """
    Normaliza el período de gráficos del panel admin a 7, 30 o 90 días.

    Args:
        raw: Valor leído de query string (``días`` o ``periodo``), o None.

    Returns:
        int: 7, 30 o 90.
    """
    try:
        d = int(raw)
    except (TypeError, ValueError):
        d = 7
    if d not in (7, 30, 90):
        d = 7
    return d


def _parse_dashboard_dias(request):
    """
    Lee ``dias`` o, si falta, ``periodo`` (compatibilidad) del request GET.

    Args:
        request: HttpRequest.

    Returns:
        int: Días normalizados (7, 30 o 90).
    """
    raw = request.GET.get('dias')
    if raw is None:
        raw = request.GET.get('periodo')
    return _normalize_dashboard_dias(raw)


def _build_dashboard_charts_payload(dias, now=None):
    """
    Construye etiquetas y series diarias para Chart.js y conteos por estado.

    Por cada día natural (desde hace ``dias`` días hasta hoy, inclusive):
    ``ordenes_por_dia`` cuenta órdenes creadas ese día; ``ingresos_por_dia``
    suma ``Order.total`` de órdenes creadas ese día excluyendo canceladas.

    ``estados_data`` agrupa órdenes **creadas** en la ventana de ``dias``:
    ``paid`` incluye estados ``paid`` y ``packed`` para alinear la dona con
    los cinco estados pedidos en especificación (pending, paid, shipped,
    delivered, cancelled).

    Args:
        dias: Número de días calendario (7, 30 o 90).
        now: Momento de referencia (por defecto ``timezone.now()``).

    Returns:
        dict: ``chart_labels``, ``ordenes_por_dia`` (list[int]),
        ``ingresos_por_dia`` (list[float]), ``estados_data`` (dict),
        ``dias`` (int).
    """
    if now is None:
        now = timezone.now()

    dias = _normalize_dashboard_dias(dias)
    weekday_es = ('Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom')

    chart_labels = []
    ordenes_por_dia = []
    ingresos_por_dia = []

    for i in range(dias):
        day = (now - timedelta(days=dias - 1 - i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_next = day + timedelta(days=1)
        if dias == 7:
            chart_labels.append(weekday_es[day.weekday()])
        else:
            chart_labels.append(day.strftime('%d/%m'))

        ordenes_por_dia.append(
            Order.objects.filter(
                created_at__gte=day, created_at__lt=day_next
            ).count()
        )
        ing = (
            Order.objects.filter(
                created_at__gte=day, created_at__lt=day_next
            )
            .exclude(status='cancelled')
            .aggregate(t=Sum('total'))['t']
            or Decimal('0')
        )
        ingresos_por_dia.append(float(ing))

    window_start = (now - timedelta(days=dias - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    qs = Order.objects.filter(created_at__gte=window_start)
    by_status = {row['status']: row['c'] for row in qs.values('status').annotate(c=Count('id'))}
    estados_data = {
        'pending':   by_status.get('pending', 0),
        'paid':      by_status.get('paid', 0) + by_status.get('packed', 0),
        'shipped':   by_status.get('shipped', 0),
        'delivered': by_status.get('delivered', 0),
        'cancelled': by_status.get('cancelled', 0),
    }

    return {
        'chart_labels':    chart_labels,
        'ordenes_por_dia': ordenes_por_dia,
        'ingresos_por_dia': ingresos_por_dia,
        'estados_data':    estados_data,
        'dias':            dias,
    }


def _period_delta_pct(current, previous):
    """
    Texto corto de variación porcentual entre el período actual y el anterior.

    Args:
        current: Valor numérico del período reciente.
        previous: Valor del período inmediatamente anterior (misma duración).
    """
    try:
        cur = float(current)
        prev = float(previous)
    except (TypeError, ValueError):
        return "n/a"
    if prev <= 0:
        return "nuevo" if cur > 0 else "sin base"
    pct = (cur - prev) / prev * 100.0
    return f"{pct:+.1f}%"


# =============================================================================
# HELPERS
# =============================================================================

def _redirect_by_role(user):
    """
    URL de inicio tras login o al visitar la home autenticado.

    Los administradores deben ir a /dashboard/, nunca a / (home pública),
    para evitar ERR_TOO_MANY_REDIRECTS (home redirige de nuevo al mismo rol).
    """
    try:
        role = user.profile.role
    except Exception:
        role = None

    if user.is_superuser or role == 'admin':
        return reverse('dashboard')
    if role == 'seller':
        return reverse('portal_seller')
    return reverse('tienda')


# =============================================================================
# AUTENTICACIÓN
# =============================================================================

def login_view(request):
    """Login con redirección inteligente según rol."""
    if request.user.is_authenticated:
        return redirect(_redirect_by_role(request.user))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not (user.is_superuser or user.is_staff):
                try:
                    profile = user.profile
                    if not profile.email_verificado:
                        messages.warning(
                            request,
                            'Debes verificar tu email antes de iniciar sesión. '
                            'Revisa tu bandeja de entrada o solicita un nuevo email.',
                        )
                        return render(
                            request,
                            'core/login.html',
                            {
                                'mostrar_reenvio': True,
                                'email_pendiente': user.email,
                            },
                        )
                except UserProfile.DoesNotExist:
                    pass

            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.first_name or user.username}!')
            next_url = (request.GET.get('next') or '').strip()
            if next_url.startswith('//') or '://' in next_url:
                next_url = ''
            elif next_url.startswith('/'):
                home_path = reverse('home')
                login_path = reverse('login')
                if next_url in (home_path, '/') or next_url == login_path or next_url.startswith(login_path + '?'):
                    next_url = ''
            else:
                next_url = ''
            dest = next_url if next_url else _redirect_by_role(user)
            return redirect(dest)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')


def signup_view(request):
    """Registro público: crea User + UserProfile."""
    if request.user.is_authenticated:
        return redirect(_redirect_by_role(request.user))

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        username   = request.POST.get('username', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        role       = request.POST.get('role', 'buyer')
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')

        # Validaciones
        if not all([first_name, username, email, password1, password2]):
            messages.error(request, 'Todos los campos marcados con * son obligatorios.')
        elif password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
        elif len(password1) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe. Elige otro.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Ya existe una cuenta con ese correo.')
        elif role not in ('buyer', 'seller'):
            messages.error(request, 'Tipo de cuenta no válido.')
        else:
            # Crear usuario
            user = User.objects.create_user(
                username   = username,
                email      = email,
                password   = password1,
                first_name = first_name,
                last_name  = last_name,
            )
            UserProfile.objects.create(user=user, role=role, phone=phone)

            try:
                enviar_verificacion_email(user, request)
            except Exception as exc:
                log.exception('No se pudo enviar email de verificación: %s', exc)
                messages.warning(
                    request,
                    'Cuenta creada, pero no pudimos enviar el correo de verificación. '
                    'Contacta a soporte@tradeflow.pa.',
                )
                return redirect('login')

            messages.success(
                request,
                f'Cuenta creada. Revisa tu email {email} '
                f'para verificar tu cuenta antes de iniciar sesión.',
            )
            return redirect('login')

    return render(request, 'core/signup.html', {
        'role_choices': [('buyer', 'Comprador'), ('seller', 'Vendedor')],
        'selected_role': request.POST.get('role', 'buyer'),
    })


@login_required
def mi_perfil(request):
    """
    Vista del perfil del usuario autenticado.

    GET: Muestra información actual del perfil.
    POST: Actualiza nombre, apellido, email y teléfono, o cambia la contraseña.

    Incluye resumen de actividad según rol (buyer, seller, admin).
    """
    from django.contrib.auth import update_session_auth_hash

    profile = request.user.profile
    role = profile.role

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_info':
            request.user.first_name = request.POST.get('first_name', '').strip()
            request.user.last_name = request.POST.get('last_name', '').strip()
            request.user.email = request.POST.get('email', '').strip()
            profile.phone = request.POST.get('phone', '').strip()
            request.user.save()
            profile.save()
            messages.success(request, 'Perfil actualizado correctamente.')

        elif action == 'change_password':
            current = request.POST.get('current_password')
            new_pass = request.POST.get('new_password')
            confirm = request.POST.get('confirm_password')

            if not request.user.check_password(current):
                messages.error(request, 'La contraseña actual es incorrecta.')
            elif new_pass != confirm:
                messages.error(request, 'Las contraseñas nuevas no coinciden.')
            elif len(new_pass or '') < 8:
                messages.error(request, 'La contraseña debe tener mínimo 8 caracteres.')
            else:
                request.user.set_password(new_pass)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Contraseña cambiada exitosamente.')

        return redirect('mi_perfil')

    actividad = {}
    show_buyer = role == 'buyer'
    show_seller = role == 'seller'
    show_admin = role == 'admin' or request.user.is_superuser

    if show_buyer:
        actividad['total_ordenes'] = Order.objects.filter(buyer=request.user).count()
        actividad['ultima_orden'] = (
            Order.objects.filter(buyer=request.user).order_by('-created_at').first()
        )

    elif show_seller:
        empresas = Company.objects.filter(owner=request.user)
        actividad['total_productos'] = Product.objects.filter(
            company__in=empresas, is_active=True
        ).count()

    elif show_admin:
        actividad['total_usuarios'] = User.objects.filter(is_active=True).count()
        actividad['total_ordenes'] = Order.objects.count()

    return render(request, 'core/mi_perfil.html', {
        'profile': profile,
        'actividad': actividad,
        'titulo_pagina': 'Mi Perfil',
        'nav_activo': 'perfil',
        'show_buyer': show_buyer,
        'show_seller': show_seller,
        'show_admin': show_admin,
        'role_key': role,
    })


def home_view(request):
    if request.user.is_authenticated:
        return redirect(_redirect_by_role(request.user))
    from .models import Product
    productos_carrusel = list(
        Product.objects.filter(is_active=True)
        .select_related('company', 'category')
        .defer('company__owner')
        .order_by('-created_at')[:12]
    )
    productos = productos_carrusel[:6]
    empresas_carousel = (
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('-num_productos')[:8]
    )
    return render(request, 'core/home.html', {
        'productos_carrusel': productos_carrusel,
        'productos': productos,
        'empresas_carousel': empresas_carousel,
    })


# ── Sal firmado para QR de visitante ZLC (pre-registro) ─────────────────────
_QR_SALT = 'tradeflow.zlc.visitante'


def mapa_zlc(request):
    """
    Mapa interactivo (Leaflet vía Folium) de empresas registradas en la ZLC.

    Centro en Zona Libre de Colón (9.3667, -79.9000). Cada empresa es un
    marcador dentro de un cluster; color naranja si verificada y gris si no.
    El popup incluye nombre, categorías de productos activos, conteo y enlace
    al catálogo filtrado por empresa.

    Args:
        request: HttpRequest.

    Returns:
        HttpResponse: Plantilla con HTML del mapa embebido.
    """
    m = folium.Map(location=[9.3667, -79.9000], zoom_start=13, tiles='OpenStreetMap')
    cluster = MarkerCluster(name='Empresas ZLC').add_to(m)
    empresas = Company.objects.annotate(
        n_activos=Count('products', filter=Q(products__is_active=True))
    ).order_by('name')

    for c in empresas:
        lat = float(c.latitud) if c.latitud is not None else 9.3667
        lng = float(c.longitud) if c.longitud is not None else -79.9000
        cats = Category.objects.filter(
            products__company=c, products__is_active=True
        ).distinct()[:12]
        cat_txt = ', '.join(x.name for x in cats) or '—'
        nombre = html_module.escape(c.name)
        cat_txt_e = html_module.escape(cat_txt)
        catalog_url = request.build_absolute_uri(
            reverse('tienda') + '?empresa=' + str(c.pk)
        )
        catalog_url_e = html_module.escape(catalog_url)
        html_popup = (
            '<div style="min-width:220px;font-family:system-ui,sans-serif;font-size:13px;line-height:1.45;">'
            f'<strong style="color:#0F2A44;">{nombre}</strong><br>'
            f'<span style="color:#6B7A88;">Productos activos:</span> {c.n_activos}<br>'
            f'<span style="color:#6B7A88;">Categorías:</span> {cat_txt_e}<br>'
            f'<a href="{catalog_url_e}" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-block;margin-top:10px;padding:8px 14px;background:#F26522;'
            'color:#fff;border-radius:8px;text-decoration:none;font-weight:600;font-size:0.85rem;">'
            'Ver catálogo</a></div>'
        )
        icon_color = 'orange' if c.is_verified else 'gray'
        folium.Marker(
            location=[lat, lng],
            popup=folium.Popup(html_popup, max_width=340),
            tooltip=nombre,
            icon=folium.Icon(color=icon_color),
        ).add_to(cluster)

    map_html = m._repr_html_()
    return render(request, 'core/mapa_zlc.html', {
        'map_html':       map_html,
        'titulo_pagina':  'Mapa ZLC',
        'nav_activo':     'mapa_zlc',
    })


def visitante_zlc_verificacion(request):
    """
    Pantalla pública de verificación leyendo el token ``t`` firmado en la query.

    Muestra nombre, usuario y correo del comprador asociado al QR si el token
    es válido y no ha expirado.

    Args:
        request: HttpRequest (GET con ``t``).

    Returns:
        HttpResponse: Detalle o mensaje de error.
    """
    token = (request.GET.get('t') or '').strip()
    if not token:
        return render(
            request,
            'core/visitante_zlc_verificacion.html',
            {'error': 'Enlace incompleto o no válido.'},
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
            {'error': 'Código expirado o alterado. Solicita un nuevo QR en TradeFlow.'},
            status=404,
        )

    profile = getattr(subject, 'profile', None)
    return render(
        request,
        'core/visitante_zlc_verificacion.html',
        {'error': None, 'subject': subject, 'profile': profile},
    )


def _visitante_qr_verify_url(request) -> str:
    """Construye la URL absoluta firmada que se incrusta en el PNG del QR."""
    from urllib.parse import urlencode

    token = signing.dumps({'uid': request.user.pk}, salt=_QR_SALT)
    base = request.build_absolute_uri(reverse('visitante_zlc_verificacion'))
    return base + '?' + urlencode({'t': token})


def _qr_png_bytes(payload: str) -> bytes:
    """Genera imagen PNG del código QR con el texto o URL dado."""
    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0F2A44', back_color='#FFFFFF')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@login_required
def mi_qr(request):
    """
    Página del comprador con el QR grande, instrucciones y enlace de descarga.

    El QR apunta a la URL de verificación firmada para agilizar ingreso o
    validaciones en la Zona Libre de Colón.

    Args:
        request: HttpRequest (usuario autenticado).

    Returns:
        HttpResponse: Plantilla ``mi_qr.html``.
    """
    verify_url = _visitante_qr_verify_url(request)
    png = _qr_png_bytes(verify_url)
    b64 = base64.b64encode(png).decode('ascii')
    profile = getattr(request.user, 'profile', None)
    return render(request, 'core/mi_qr.html', {
        'verify_url':     verify_url,
        'qr_data_uri':    'data:image/png;base64,' + b64,
        'generated_at':   timezone.now(),
        'profile':        profile,
        'titulo_pagina':  'Mi código QR ZLC',
        'nav_activo':     'mi_qr',
    })


@login_required
def generar_qr_visitante(request):
    """
    Devuelve la imagen PNG del QR de visitante para descargar o incrustar.

    Args:
        request: HttpRequest.

    Returns:
        HttpResponse: ``image/png`` con ``Content-Disposition: attachment``.
    """
    verify_url = _visitante_qr_verify_url(request)
    png = _qr_png_bytes(verify_url)
    resp = HttpResponse(png, content_type='image/png')
    resp['Content-Disposition'] = 'attachment; filename="tradeflow-zlc-qr.png"'
    return resp


# =============================================================================
# DASHBOARD (solo admin)
# =============================================================================

@admin_required
def api_dashboard_stats(request):
    """
    Devuelve JSON con series diarias y conteos por estado para el dashboard admin.

    Se usa con ``fetch`` desde el template para cambiar 7 / 30 / 90 días sin
    recargar la página. Solo administradores autenticados.

    Query parameters:
        dias: 7, 30 o 90 (opcional; por defecto 7).

    Returns:
        JsonResponse: ``chart_labels``, ``ordenes_por_dia``, ``ingresos_por_dia``,
        ``estados_data``, ``dias``.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    dias = _normalize_dashboard_dias(request.GET.get('dias'))
    payload = _build_dashboard_charts_payload(dias)
    return JsonResponse(payload)


@admin_required
def dashboard(request):
    """
    Panel de administración con KPIs, selector de período (7 / 30 / 90 días) y
    gráficos Chart.js alimentados con datos reales del ORM.

    Variables de gráficos en contexto (además de JSON para el cliente):
    ``ordenes_por_dia``, ``ingresos_por_dia``, ``estados_data`` y
    ``chart_labels``, derivadas de :func:`_build_dashboard_charts_payload`.

    El parámetro GET ``dias`` (o ``periodo`` por compatibilidad) controla la
    ventana de KPIs y la carga inicial de los gráficos; cambios posteriores
    usan :func:`api_dashboard_stats` vía JavaScript.
    """
    hoy = timezone.now()
    dias = _parse_dashboard_dias(request)

    first_day = (hoy - timedelta(days=dias - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    inicio_actual = first_day
    inicio_anterior = first_day - timedelta(days=dias)
    inicio_prev_end = first_day

    total_ordenes = Order.objects.count()
    ordenes_semana = Order.objects.filter(created_at__gte=inicio_actual).count()
    ordenes_periodo_prev = Order.objects.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
    ).count()

    ingresos_total = Order.objects.filter(status='delivered').aggregate(t=Sum('total'))['t'] or Decimal('0')
    ingresos_semana = Order.objects.filter(
        status='delivered', created_at__gte=inicio_actual
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')
    ingresos_periodo_prev = Order.objects.filter(
        status='delivered',
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    total_productos = Product.objects.filter(is_active=True).count()
    total_empresas = Company.objects.count()
    ordenes_recientes = Order.objects.select_related('buyer').order_by('-created_at')[:10]

    clientes_activos = Order.objects.values('buyer').distinct().count()
    clientes_periodo = Order.objects.filter(created_at__gte=inicio_actual).values('buyer').distinct().count()
    clientes_periodo_prev = (
        Order.objects.filter(
            created_at__gte=inicio_anterior,
            created_at__lt=inicio_prev_end,
        )
        .values('buyer')
        .distinct()
        .count()
    )

    entregadas = Order.objects.filter(status='delivered').count()
    tasa_conversion = Decimal('0')
    if total_ordenes > 0:
        tasa_conversion = round(Decimal(100) * entregadas / total_ordenes, 1)

    tot_cur = Order.objects.filter(created_at__gte=inicio_actual).count()
    del_cur = Order.objects.filter(created_at__gte=inicio_actual, status='delivered').count()
    tasa_periodo = round(Decimal(100) * del_cur / tot_cur, 1) if tot_cur else Decimal('0')
    tot_prev = Order.objects.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
    ).count()
    del_prev = Order.objects.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
        status='delivered',
    ).count()
    tasa_periodo_prev = round(Decimal(100) * del_prev / tot_prev, 1) if tot_prev else Decimal('0')
    tasa_delta_pp = tasa_periodo - tasa_periodo_prev

    charts = _build_dashboard_charts_payload(dias, now=hoy)
    chart_labels = charts['chart_labels']
    ordenes_por_dia = charts['ordenes_por_dia']
    ingresos_por_dia = charts['ingresos_por_dia']
    estados_data = charts['estados_data']

    ordenes_b2b = Order.objects.filter(created_at__gte=inicio_actual, order_type='b2b').count()
    ordenes_b2c = Order.objects.filter(created_at__gte=inicio_actual, order_type='b2c').count()

    usuarios_plataforma = User.objects.filter(is_active=True).count()
    usuarios_login_periodo = User.objects.filter(
        is_active=True,
        last_login__isnull=False,
        last_login__gte=inicio_actual,
    ).count()

    actividad = []
    for o in Order.objects.select_related('buyer').order_by('-created_at')[:8]:
        actividad.append(
            {
                'ts': o.created_at,
                'icon': 'receipt_long',
                'titulo': f'Orden {o.order_number}',
                'detalle': (o.buyer.get_full_name() or o.buyer.username) + ' · ' + o.get_status_display(),
            }
        )
    for u in User.objects.order_by('-date_joined')[:6]:
        actividad.append(
            {
                'ts': u.date_joined,
                'icon': 'person_add',
                'titulo': f'Usuario {u.username}',
                'detalle': u.email or '—',
            }
        )
    actividad.sort(key=lambda x: x['ts'], reverse=True)
    actividad = actividad[:12]

    context = {
        'total_ordenes':        total_ordenes,
        'ordenes_semana':       ordenes_semana,
        'ordenes_delta_label':  _period_delta_pct(ordenes_semana, ordenes_periodo_prev),
        'ingresos_total':       ingresos_total,
        'ingresos_semana':      ingresos_semana,
        'ingresos_delta_label': _period_delta_pct(
            float(ingresos_semana), float(ingresos_periodo_prev)
        ),
        'total_productos':      total_productos,
        'total_empresas':       total_empresas,
        'ordenes_recientes':    ordenes_recientes,
        'chart_labels':         chart_labels,
        'ordenes_por_dia':      ordenes_por_dia,
        'ingresos_por_dia':     ingresos_por_dia,
        'estados_data':         estados_data,
        'chart_labels_json':    json.dumps(chart_labels),
        'ordenes_por_dia_json': json.dumps(ordenes_por_dia),
        'ingresos_por_dia_json': json.dumps(ingresos_por_dia),
        'estados_data_json':    json.dumps(estados_data),
        'charts_initial_json':  json.dumps(charts),
        'api_dashboard_stats_url': reverse('api_dashboard_stats'),
        'ordenes_b2b':          ordenes_b2b,
        'ordenes_b2c':          ordenes_b2c,
        'usuarios_plataforma':  usuarios_plataforma,
        'usuarios_login_periodo': usuarios_login_periodo,
        'actividad_reciente':   actividad,
        'clientes_activos':     clientes_activos,
        'clientes_periodo':     clientes_periodo,
        'clientes_delta_label': _period_delta_pct(clientes_periodo, clientes_periodo_prev),
        'tasa_conversion':      tasa_conversion,
        'tasa_periodo':         tasa_periodo,
        'tasa_delta_pp':        tasa_delta_pp,
        'tasa_delta_pp_fmt':    f'{tasa_delta_pp:+.1f}',
        'periodo_activo':       dias,
        'dias_activo':          dias,
        'titulo_pagina':        'Dashboard',
        'nav_activo':           'dashboard',
    }
    return render(request, 'core/dashboard.html', context)


# =============================================================================
# ÓRDENES (solo admin)
# =============================================================================

@admin_required
def lista_ordenes(request):
    ordenes = (
        Order.objects.select_related('buyer')
        .annotate(item_count=Count('items'))
        .order_by('-created_at')
    )
    buscar  = request.GET.get('buscar', '')
    estado  = request.GET.get('estado', '')

    if buscar:
        ordenes = ordenes.filter(
            Q(order_number__icontains=buscar) |
            Q(buyer__first_name__icontains=buscar) |
            Q(buyer__last_name__icontains=buscar) |
            Q(buyer__username__icontains=buscar)
        )
    if estado:
        ordenes = ordenes.filter(status=estado)

    paginator = Paginator(ordenes, 10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    from urllib.parse import urlencode

    filtros_q = {}
    if buscar:
        filtros_q['buscar'] = buscar
    if estado:
        filtros_q['estado'] = estado
    orden_filtros_query = urlencode(filtros_q)

    estado_opciones = [{'value': '', 'label': 'Todos los estados', 'selected': not bool(estado)}]
    for val, label in Order.STATUS_CHOICES:
        estado_opciones.append({
            'value':    val,
            'label':    label,
            'selected': bool(estado) and estado == val,
        })

    context = {
        'ordenes':             page_obj,
        'buscar':              buscar,
        'estado_actual':       estado,
        'estado_opciones':     estado_opciones,
        'orden_filtros_query': orden_filtros_query,
        'titulo_pagina':       'Gestión de Órdenes',
        'nav_activo':          'ordenes',
    }
    return render(request, 'core/ordenes.html', context)


@admin_required
def detalle_orden(request, pk):
    orden = get_object_or_404(
        Order.objects.select_related('buyer', 'ship_address')
                     .prefetch_related('items__product', 'documents'),
        pk=pk
    )
    otros_estados = [(v, lbl) for v, lbl in Order.STATUS_CHOICES if v != orden.status]
    try:
        pago = Payment.objects.get(order=orden)
    except Payment.DoesNotExist:
        pago = None
    try:
        envio = Shipment.objects.get(order=orden)
    except Shipment.DoesNotExist:
        envio = None
    context = {
        'orden':           orden,
        'pago':            pago,
        'envio':           envio,
        'otros_estados':   otros_estados,
        'titulo_pagina':   f'Orden {orden.order_number}',
        'nav_activo':      'ordenes',
    }
    return render(request, 'core/detalle_orden.html', context)


@admin_required
def cambiar_estado_orden(request, pk, estado):
    orden = get_object_or_404(Order, pk=pk)
    estados_validos = [e[0] for e in Order.STATUS_CHOICES]

    if estado in estados_validos:
        estado_anterior = orden.status
        orden.status = estado
        orden.save(update_fields=['status', 'updated_at'])
        if estado == 'delivered':
            pago = getattr(orden, 'payment', None)
            if pago and pago.status == 'pending':
                pago.status  = 'approved'
                pago.paid_at = timezone.now()
                pago.save(update_fields=['status', 'paid_at'])
        messages.success(request, f'Orden actualizada a "{orden.get_status_display()}".')
        try:
            enviar_cambio_estado(orden, estado_anterior)
        except Exception:
            log.exception('No se pudo enviar email de cambio de estado.')
    else:
        messages.error(request, 'Estado no válido.')

    return redirect('detalle_orden', pk=pk)


# =============================================================================
# WIZARD DE NUEVA ORDEN (solo admin)
# =============================================================================

@admin_required
def nueva_orden_paso1(request):
    request.session.pop('wizard_buyer_id',   None)
    request.session.pop('wizard_order_type', None)
    request.session.pop('wizard_items',      None)

    compradores = User.objects.filter(is_active=True).order_by('username')

    if request.method == 'POST':
        buyer_id   = request.POST.get('buyer_id')
        order_type = request.POST.get('order_type', 'b2c')
        if not buyer_id:
            messages.error(request, 'Debes seleccionar un comprador.')
        else:
            request.session['wizard_buyer_id']   = int(buyer_id)
            request.session['wizard_order_type'] = order_type
            return redirect('nueva_orden_paso2')

    return render(request, 'core/nueva_orden_paso1.html', {
        'compradores':   compradores,
        'order_types':   Order.ORDER_TYPE_CHOICES,
        'titulo_pagina': 'Nueva Orden — Paso 1',
        'nav_activo':    'ordenes',
        'paso_actual':   1,
    })


@admin_required
def nueva_orden_paso2(request):
    if not request.session.get('wizard_buyer_id'):
        messages.error(request, 'Debes completar el paso 1 primero.')
        return redirect('nueva_orden_paso1')

    productos  = (
        Product.objects.filter(is_active=True)
        .select_related('category', 'company', 'inventory')
        .defer('company__owner')
        .order_by('name')
    )
    categorias = Category.objects.all()

    buscar    = request.GET.get('buscar', '')
    categoria = request.GET.get('categoria', '')
    if buscar:
        productos = productos.filter(Q(name__icontains=buscar) | Q(sku__icontains=buscar))
    if categoria:
        productos = productos.filter(category__id=categoria)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'agregar':
            producto_id = request.POST.get('producto_id')
            cantidad    = int(request.POST.get('cantidad', 1))
            try:
                producto = Product.objects.select_related('inventory').get(
                    pk=producto_id, is_active=True
                )
            except Product.DoesNotExist:
                messages.error(request, 'Producto no encontrado.')
                return redirect('nueva_orden_paso2')

            disponible = producto.available_qty
            if cantidad < 1:
                messages.error(request, 'La cantidad debe ser al menos 1.')
            elif cantidad > disponible:
                messages.error(request, f'Stock insuficiente. Disponible: {disponible}.')
            else:
                items = request.session.get('wizard_items', [])
                encontrado = False
                for item in items:
                    if item['producto_id'] == int(producto_id):
                        nueva_cant = item['cantidad'] + cantidad
                        item['cantidad'] = min(nueva_cant, disponible)
                        item['subtotal'] = str(float(item['precio']) * item['cantidad'])
                        encontrado = True
                        break
                if not encontrado:
                    items.append({
                        'producto_id': int(producto_id),
                        'nombre':      producto.name,
                        'precio':      str(producto.unit_price),
                        'cantidad':    cantidad,
                        'subtotal':    str(float(producto.unit_price) * cantidad),
                    })
                request.session['wizard_items'] = items
                request.session.modified = True
                messages.success(request, f'"{producto.name}" agregado.')

        elif action == 'quitar':
            producto_id = int(request.POST.get('producto_id'))
            items = [
                i for i in request.session.get('wizard_items', [])
                if i['producto_id'] != producto_id
            ]
            request.session['wizard_items'] = items
            request.session.modified = True

        elif action == 'continuar':
            if not request.session.get('wizard_items'):
                messages.error(request, 'Agrega al menos un producto.')
            else:
                return redirect('nueva_orden_paso3')

        return redirect('nueva_orden_paso2')

    items_sesion  = request.session.get('wizard_items', [])
    total_carrito = sum(float(i['subtotal']) for i in items_sesion)

    return render(request, 'core/nueva_orden_paso2.html', {
        'productos':     productos,
        'categorias':    categorias,
        'buscar':        buscar,
        'cat_activa':    categoria,
        'items_carrito': items_sesion,
        'total_carrito': total_carrito,
        'titulo_pagina': 'Nueva Orden — Paso 2',
        'nav_activo':    'ordenes',
        'paso_actual':   2,
    })


@admin_required
def nueva_orden_paso3(request):
    from decimal import Decimal
    buyer_id   = request.session.get('wizard_buyer_id')
    order_type = request.session.get('wizard_order_type', 'b2c')
    items      = request.session.get('wizard_items', [])

    if not buyer_id or not items:
        messages.error(request, 'Sesión expirada. Inicia la orden de nuevo.')
        return redirect('nueva_orden_paso1')

    buyer       = get_object_or_404(User, pk=buyer_id)
    direcciones = Address.objects.filter(user=buyer)
    subtotal    = sum(float(i['subtotal']) for i in items)

    if request.method == 'POST':
        shipping_cost = Decimal(request.POST.get('shipping_cost', 0) or 0)
        address_id    = request.POST.get('address_id') or None
        notas         = request.POST.get('notas', '')
        metodo_pago   = request.POST.get('metodo_pago', 'mock')

        ship_address = None
        if address_id:
            try:
                ship_address = Address.objects.get(pk=address_id, user=buyer)
            except Address.DoesNotExist:
                pass

        orden = Order.objects.create(
            buyer=buyer, ship_address=ship_address,
            order_type=order_type, shipping_cost=shipping_cost,
            notes=notas, status='pending',
        )

        for item_data in items:
            try:
                producto = Product.objects.select_related('inventory').get(
                    pk=item_data['producto_id']
                )
                cantidad = item_data['cantidad']
                if producto.available_qty >= cantidad:
                    OrderItem.objects.create(
                        order=orden, product=producto,
                        qty=cantidad,
                        unit_price_snapshot=producto.unit_price,
                    )
                    if hasattr(producto, 'inventory'):
                        producto.inventory.reserve(cantidad)
                else:
                    messages.warning(
                        request,
                        f'Stock insuficiente para "{producto.name}", item omitido.'
                    )
            except Product.DoesNotExist:
                pass

        orden.recalculate_totals()
        orden.shipping_cost = shipping_cost
        orden.total = orden.subtotal + shipping_cost
        orden.save(update_fields=['shipping_cost', 'total'])

        Payment.objects.create(
            order=orden, provider=metodo_pago,
            status='approved' if metodo_pago == 'mock' else 'pending',
            amount=orden.total, currency='USD',
            paid_at=timezone.now() if metodo_pago == 'mock' else None,
            txn_ref=f'TF-{orden.order_number}',
        )
        if metodo_pago == 'mock':
            orden.status = 'paid'
            orden.save(update_fields=['status'])

        for key in ('wizard_buyer_id', 'wizard_order_type', 'wizard_items'):
            request.session.pop(key, None)

        messages.success(request, f'¡Orden {orden.order_number} creada exitosamente!')
        return redirect('detalle_orden', pk=orden.pk)

    return render(request, 'core/nueva_orden_paso3.html', {
        'buyer':         buyer,
        'order_type':    order_type,
        'items':         items,
        'subtotal':      subtotal,
        'direcciones':   direcciones,
        'metodos_pago':  Payment.PROVIDER_CHOICES,
        'titulo_pagina': 'Nueva Orden — Paso 3',
        'nav_activo':    'ordenes',
        'paso_actual':   3,
    })


# =============================================================================
# PRODUCTOS (admin)
# =============================================================================

@admin_required
def lista_productos(request):
    productos  = (
        Product.objects.select_related('company', 'category')
        .defer('company__owner')
        .prefetch_related('inventory')
        .order_by('name')
    )
    buscar    = request.GET.get('buscar', '')
    categoria = request.GET.get('categoria', '')

    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar) |
            Q(description__icontains=buscar) |
            Q(sku__icontains=buscar)
        )
    if categoria:
        productos = productos.filter(category__id=categoria)

    paginator  = Paginator(productos, 12)
    page_obj   = paginator.get_page(request.GET.get('page', 1))
    categorias = Category.objects.all()
    categorias_opciones = [
        {
            'id':       c.pk,
            'name':     c.name,
            'selected': bool(categoria and str(c.pk) == str(categoria)),
        }
        for c in categorias
    ]

    from urllib.parse import urlencode

    prod_filtros = {}
    if buscar:
        prod_filtros['buscar'] = buscar
    if categoria:
        prod_filtros['categoria'] = categoria
    producto_filtros_query = urlencode(prod_filtros)

    return render(request, 'core/productos.html', {
        'productos':              page_obj,
        'categorias_opciones':    categorias_opciones,
        'buscar':                 buscar,
        'cat_activa':             categoria,
        'producto_filtros_query': producto_filtros_query,
        'titulo_pagina':          'Catálogo de Productos',
        'nav_activo':             'productos',
    })


# =============================================================================
# EMPRESAS (admin)
# =============================================================================

@admin_required
def lista_empresas(request):
    empresas  = Company.objects.annotate(
        total_productos=Count('products')
    ).order_by('name')
    paginator = Paginator(empresas, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'core/empresas.html', {
        'empresas':      page_obj,
        'titulo_pagina': 'Empresas',
        'nav_activo':    'empresas',
    })


# =============================================================================
# PORTALES DE ROL (placeholder — se expanden el Día 3 y 4)
# =============================================================================

@buyer_required
def portal_buyer(request):
    """Portal del comprador — se completa el Lunes 14."""
    return render(request, 'core/portal_buyer_temp.html', {
        'titulo_pagina': 'Tienda TradeFlow',
    })


@seller_required
def portal_seller(request):
    """Dashboard del vendedor en /mi-tienda/ con métricas y ventas recientes."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    productos_qs = Product.objects.filter(company=company)
    total_productos = productos_qs.filter(is_active=True).count()
    bajo_stock = _seller_low_stock_count(company)

    ordenes_recientes = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')[:8]
    )

    ingresos_mes_items = OrderItem.objects.filter(
        product__company=company,
        order__status='delivered',
        order__created_at__gte=month_start,
    )
    ingresos_mes = ingresos_mes_items.aggregate(t=Sum('line_total'))['t'] or Decimal('0.00')

    hace_7 = now - timedelta(days=7)
    ordenes_semana = (
        Order.objects.filter(items__product__company=company, created_at__gte=hace_7)
        .distinct()
        .count()
    )

    context = {
        'company': company,
        'total_productos': total_productos,
        'bajo_stock': bajo_stock,
        'ingresos_mes': ingresos_mes,
        'ordenes_semana': ordenes_semana,
        'ordenes_recientes': ordenes_recientes,
        'titulo_pagina': 'Mi Tienda',
        'nav_activo': 'mi_tienda',
    }
    return render(request, 'core/portal_seller.html', context)


def _get_seller_company(user):
    """
    Devuelve la empresa cuyo propietario es el usuario autenticado, o None.
    """
    if not user.is_authenticated:
        return None
    return Company.objects.filter(owner=user).first()


def _seller_company_or_response(request, nav_activo='mi_tienda'):
    """
    Obtiene la empresa del vendedor o devuelve una respuesta HttpResponse
    con la plantilla de aviso si no hay empresa vinculada.
    """
    company = _get_seller_company(request.user)
    if company:
        return company, None
    messages.warning(
        request,
        'Tu cuenta no tiene una empresa vinculada. Contacta al administrador para asignarte una empresa en el sistema.',
    )
    ctx = {
        'titulo_pagina': 'Mi Tienda',
        'nav_activo':    nav_activo,
    }
    return None, render(request, 'core/seller_sin_empresa.html', ctx)


def _seller_low_stock_count(company):
    """
    Cuenta cuántos productos de la empresa tienen inventario en nivel bajo.
    """
    n = 0
    qs = Inventory.objects.filter(product__company=company).select_related('product')
    for inv in qs:
        if inv.is_low_stock:
            n += 1
    return n


@seller_required
def seller_dashboard(request):
    """
    Panel principal del vendedor: métricas de productos, stock y órdenes recientes.
    """
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    hoy         = timezone.now()
    hace_7_dias = hoy - timedelta(days=7)

    productos_qs = Product.objects.filter(company=company)
    total_productos  = productos_qs.count()
    activos          = productos_qs.filter(is_active=True).count()
    bajo_stock       = _seller_low_stock_count(company)

    ordenes_recientes = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')[:6]
    )

    ordenes_semana = (
        Order.objects.filter(
            items__product__company=company,
            created_at__gte=hace_7_dias,
        )
        .distinct()
        .count()
    )

    ventas_items = OrderItem.objects.filter(
        product__company=company,
        order__status__in=('paid', 'packed', 'shipped', 'delivered'),
        order__created_at__gte=hace_7_dias,
    )
    ventas_semana = ventas_items.aggregate(t=Sum('line_total'))['t'] or Decimal('0.00')

    context = {
        'company':           company,
        'total_productos':   total_productos,
        'productos_activos': activos,
        'bajo_stock':        bajo_stock,
        'ordenes_semana':    ordenes_semana,
        'ventas_semana':     ventas_semana,
        'ordenes_recientes': ordenes_recientes,
        'titulo_pagina':     'Panel de vendedor',
        'nav_activo':        'mi_tienda',
    }
    return render(request, 'core/seller_dashboard.html', context)


@seller_required
def seller_productos(request):
    """
    Lista los productos del catálogo de la empresa del vendedor con filtros y paginación.
    """
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    productos = (
        Product.objects.filter(company=company)
        .select_related('category', 'company')
        .defer('company__owner')
        .prefetch_related('inventory')
        .order_by('name')
    )

    buscar    = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar)
            | Q(description__icontains=buscar)
            | Q(sku__icontains=buscar)
        )
    if categoria:
        productos = productos.filter(category_id=categoria)

    paginator = Paginator(productos, 12)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'company':       company,
        'productos':     page_obj,
        'categorias':    Category.objects.all().order_by('name'),
        'buscar':        buscar,
        'cat_activa':    categoria,
        'titulo_pagina': 'Mis productos',
        'nav_activo':    'seller_productos',
    }
    return render(request, 'core/seller_productos.html', context)

@seller_required
def seller_mis_productos(request):
    """Alias con mismo contenido de lista de productos, usando template alterno."""
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp
    productos = (
        Product.objects.filter(company=company)
        .select_related('category', 'company')
        .defer('company__owner')
        .prefetch_related('inventory')
        .order_by('name')
    )
    buscar    = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar) |
            Q(description__icontains=buscar) |
            Q(sku__icontains=buscar)
        )
    if categoria:
        productos = productos.filter(category_id=categoria)
    paginator = Paginator(productos, 12)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'core/seller_mis_productos.html', {
        'company': company,
        'productos': page_obj,
        'categorias': Category.objects.all().order_by('name'),
        'buscar': buscar,
        'cat_activa': categoria,
        'titulo_pagina': 'Mis productos',
        'nav_activo': 'seller_productos',
    })


@seller_required
def seller_producto_nuevo(request):
    """
    Crea un producto nuevo e inventario asociado para la empresa del vendedor.
    """
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    product_form = SellerProductForm()
    inv_form     = SellerInventoryForm()

    if request.method == 'POST':
        product_form = SellerProductForm(request.POST, request.FILES)
        inv_form     = SellerInventoryForm(request.POST)
        if product_form.is_valid() and inv_form.is_valid():
            with transaction.atomic():
                product = product_form.save(commit=False)
                product.company = company
                product.save()
                inv = inv_form.save(commit=False)
                inv.product = product
                inv.reserved_qty = 0
                inv.save()
            messages.success(request, f'Producto "{product.name}" creado correctamente.')
            return redirect('seller_productos')
        messages.error(request, 'Revisa los datos del formulario.')

    context = {
        'company':        company,
        'product_form':   product_form,
        'inv_form':       inv_form,
        'titulo_pagina':  'Nuevo producto',
        'nav_activo':     'seller_productos',
        'es_edicion':     False,
    }
    return render(request, 'core/seller_producto_form.html', context)

@seller_required
def seller_agregar_producto(request):
    """Alias de creación de producto para ruta solicitada por especificación."""
    return seller_producto_nuevo(request)


@seller_required
def seller_producto_editar(request, pk):
    """
    Edita un producto existente de la empresa del vendedor y su inventario.
    """
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    product = get_object_or_404(
        Product.objects.select_related('company')
        .defer('company__owner')
        .prefetch_related('inventory'),
        pk=pk,
        company=company,
    )

    try:
        inventory = product.inventory
    except Inventory.DoesNotExist:
        inventory = Inventory(product=product, stock_qty=0, reserved_qty=0, low_stock_alert=5)
        inventory.save()

    product_form = SellerProductForm(request.POST or None, request.FILES or None, instance=product)
    inv_form     = SellerInventoryForm(request.POST or None, instance=inventory)

    if request.method == 'POST':
        if product_form.is_valid() and inv_form.is_valid():
            with transaction.atomic():
                product_form.save()
                inv_form.save()
            messages.success(request, 'Cambios guardados.')
            return redirect('seller_productos')
        messages.error(request, 'Revisa los datos del formulario.')

    context = {
        'company':        company,
        'product':        product,
        'product_form':   product_form,
        'inv_form':       inv_form,
        'titulo_pagina':  f'Editar: {product.name}',
        'nav_activo':     'seller_productos',
        'es_edicion':     True,
    }
    return render(request, 'core/seller_producto_form.html', context)

@seller_required
def seller_editar_producto(request, pk):
    """Alias de edición de producto para ruta solicitada por especificación."""
    return seller_producto_editar(request, pk)

@seller_required
def seller_toggle_producto(request, pk):
    """Activa/desactiva un producto del vendedor (solo POST con CSRF)."""
    if request.method != 'POST':
        return redirect('seller_mis_productos')
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp
    product = get_object_or_404(Product, pk=pk, company=company)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])
    estado = "activo" if product.is_active else "inactivo"
    messages.success(request, f'Producto \"{product.name}\" ahora está {estado}.')
    return redirect('seller_mis_productos')


@seller_required
def seller_ventas(request):
    """
    Lista las órdenes que incluyen al menos un producto de la empresa del vendedor.
    """
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    ordenes = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')
    )

    estado = request.GET.get('estado', '').strip()
    if estado:
        ordenes = ordenes.filter(status=estado)

    paginator = Paginator(ordenes, 10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'company':        company,
        'ordenes':        page_obj,
        'estado_actual':  estado,
        'status_choices': Order.STATUS_CHOICES,
        'titulo_pagina':  'Mis ventas',
        'nav_activo':     'seller_ventas',
    }
    return render(request, 'core/seller_ventas.html', context)

@seller_required
def seller_mis_ventas(request):
    """Alias de listado de ventas con template alterno y nombre pedido."""
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp
    ordenes = (
        Order.objects.filter(items__product__company=company)
        .distinct()
        .select_related('buyer')
        .order_by('-created_at')
    )
    estado = request.GET.get('estado', '').strip()
    if estado:
        ordenes = ordenes.filter(status=estado)
    paginator = Paginator(ordenes, 10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'core/seller_mis_ventas.html', {
        'company': company,
        'ordenes': page_obj,
        'estado_actual': estado,
        'status_choices': Order.STATUS_CHOICES,
        'titulo_pagina': 'Mis ventas',
        'nav_activo': 'seller_ventas',
    })

@seller_required
def seller_venta_detalle(request, pk):
    """
    Muestra el detalle de una orden limitado a las líneas de la empresa del vendedor.
    """
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    orden = get_object_or_404(
        Order.objects.select_related('buyer', 'ship_address'),
        pk=pk,
    )
    lineas = list(
        orden.items.filter(product__company=company)
        .select_related('product')
        .order_by('id')
    )
    if not lineas:
        raise Http404('Orden no encontrada o sin productos de tu empresa.')

    subtotal_vendedor = sum((li.line_total for li in lineas), Decimal('0.00'))

    context = {
        'company':            company,
        'orden':              orden,
        'lineas_vendedor':    lineas,
        'subtotal_vendedor':  subtotal_vendedor,
        'pago':               getattr(orden, 'payment', None),
        'titulo_pagina':      f'Venta {orden.order_number}',
        'nav_activo':         'seller_ventas',
    }
    return render(request, 'core/seller_venta_detalle.html', context)

@seller_required
def seller_detalle_venta(request, pk):
    """Alias de detalle de venta para el nombre solicitado en URLs."""
    return seller_venta_detalle(request, pk)

# =============================================================================
# API JSON
# =============================================================================

@login_required
def api_productos(request):
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
            'categoria': p.category.name if p.category else 'Sin categoría',
            'empresa':   p.company.name,
        }
        for p in productos[:20]
    ]
    return JsonResponse({'productos': data})


# ---------------------------------------------------------------------------
# HELPERS DE CARRITO
# ---------------------------------------------------------------------------

def _get_carrito(request):
    """
    Recupera el carrito desde la sesión.
    Devuelve un diccionario vacío si no existe.
    El ID del producto se usa como clave (string por limitación de JSON).
    """
    return request.session.get('carrito', {})


def _save_carrito(request, carrito):
    """
    Guarda el carrito en la sesión y marca la sesión como modificada.
    Necesario para que Django persista los cambios en sesiones de tipo dict.
    """
    request.session['carrito'] = carrito
    request.session.modified = True


def _calcular_total(carrito):
    """
    Suma los subtotales de todos los items del carrito.
    Retorna un Decimal con 2 decimales.
    """
    total = Decimal('0.00')
    for item in carrito.values():
        total += Decimal(item['subtotal'])
    return total


def _contar_items(carrito):
    """
    Retorna la cantidad total de unidades en el carrito.
    Usado para mostrar el badge del carrito en el navbar.
    """
    return sum(item['cantidad'] for item in carrito.values())


# ---------------------------------------------------------------------------
# TIENDA — Catálogo principal del comprador
# ---------------------------------------------------------------------------

@buyer_required
def tienda(request):
    """
    Muestra el catálogo de productos disponibles para el comprador.

    Funcionalidades:
        - Pestañas: por categoría (sidebar + grid) o por empresa (cards de empresa).
        - Búsqueda por nombre, descripción o SKU; filtros por categoría y empresa.
        - Paginación de 9 productos por página.
        - Solo productos activos.

    Contexto enviado al template:
        productos, categorias, empresas_catalogo, empresas_filtro,
        buscar, cat_activa, emp_activa, vista_tab, tienda_params,
        carrito_count, titulo_pagina, nav_activo.
    """
    productos = (
        Product.objects.filter(is_active=True)
        .select_related('company', 'category', 'inventory')
        .defer('company__owner')
        .order_by('name')
    )

    buscar    = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    empresa   = request.GET.get('empresa', '').strip()
    vista_tab = request.GET.get('vista', 'categoria').strip() or 'categoria'
    if vista_tab not in ('categoria', 'empresa'):
        vista_tab = 'categoria'

    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar)
            | Q(description__icontains=buscar)
            | Q(sku__icontains=buscar)
        )

    if categoria:
        productos = productos.filter(category__id=categoria)

    if empresa:
        productos = productos.filter(company__id=empresa)

    paginator = Paginator(productos, 9)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    categorias = Category.objects.all().order_by('name')
    carrito = _get_carrito(request)

    empresas_catalogo = (
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('name')
    )
    empresas_filtro = empresas_catalogo

    qcopy = request.GET.copy()
    qcopy.pop('page', None)
    tienda_params = qcopy.urlencode()

    q_cat = request.GET.copy()
    for k in ('page', 'vista', 'empresa'):
        q_cat.pop(k, None)
    q_cat['vista'] = 'categoria'
    url_tab_categoria = f"{reverse('tienda')}?{q_cat.urlencode()}"

    q_emp = request.GET.copy()
    for k in ('page', 'vista', 'categoria'):
        q_emp.pop(k, None)
    q_emp['vista'] = 'empresa'
    url_tab_empresa = f"{reverse('tienda')}?{q_emp.urlencode()}"

    context = {
        'productos': page_obj,
        'categorias': categorias,
        'empresas_catalogo': empresas_catalogo,
        'empresas_filtro': empresas_filtro,
        'buscar': buscar,
        'cat_activa': categoria,
        'emp_activa': empresa,
        'vista_tab': vista_tab,
        'tienda_params': tienda_params,
        'url_tab_categoria': url_tab_categoria,
        'url_tab_empresa': url_tab_empresa,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'Tienda TradeFlow',
        'nav_activo': 'tienda',
    }
    return render(request, 'core/tienda.html', context)


# ---------------------------------------------------------------------------
# CARRITO — Gestión del carrito de compras
# ---------------------------------------------------------------------------

@buyer_required
def agregar_al_carrito(request, producto_id):
    """
    Agrega un producto al carrito o incrementa su cantidad si ya existe.

    Método: POST únicamente (botón en la tarjeta del producto)
    Parámetro POST: cantidad (int, default=1)

    Validaciones:
        - Producto debe existir y estar activo
        - Cantidad debe ser >= 1
        - Cantidad total no puede superar el stock disponible

    Redirige de vuelta a la tienda después de agregar.
    """
    if request.method != 'POST':
        return redirect('tienda')

    cantidad = int(request.POST.get('cantidad', 1))

    # Obtener producto con su inventario en una sola consulta
    producto = get_object_or_404(
        Product.objects.select_related('inventory'),
        pk=producto_id,
        is_active=True
    )

    disponible = producto.available_qty

    # Validar cantidad
    if cantidad < 1:
        messages.error(request, 'La cantidad debe ser al menos 1.')
        return redirect('tienda')

    if disponible == 0:
        messages.error(request, f'"{producto.name}" no tiene stock disponible.')
        return redirect('tienda')

    # Actualizar carrito en sesión
    carrito     = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key in carrito:
        # El producto ya está en el carrito — sumar cantidades
        nueva_cantidad = carrito[producto_key]['cantidad'] + cantidad
        if nueva_cantidad > disponible:
            messages.warning(
                request,
                f'Solo hay {disponible} unidades disponibles de "{producto.name}".'
            )
            nueva_cantidad = disponible
        carrito[producto_key]['cantidad'] = nueva_cantidad
        carrito[producto_key]['subtotal'] = str(
            Decimal(carrito[producto_key]['precio']) * nueva_cantidad
        )
    else:
        # Producto nuevo en el carrito
        if cantidad > disponible:
            cantidad = disponible
            messages.warning(
                request,
                f'Solo hay {disponible} unidades disponibles. Se ajustó la cantidad.'
            )
        carrito[producto_key] = {
            'nombre':   producto.name,
            'precio':   str(producto.unit_price),
            'cantidad': cantidad,
            'subtotal': str(producto.unit_price * cantidad),
            'imagen':   producto.image.url if producto.image else '',
        }

    _save_carrito(request, carrito)
    messages.success(request, f'"{producto.name}" agregado al carrito.')
    return redirect('tienda')


@buyer_required
def quitar_del_carrito(request, producto_id):
    """
    Elimina un producto del carrito de compras.

    Método: POST (formulario con botón eliminar en carrito.html)
    Redirige de vuelta al carrito después de quitar.
    """
    if request.method != 'POST':
        return redirect('ver_carrito')

    carrito     = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key in carrito:
        nombre = carrito[producto_key]['nombre']
        del carrito[producto_key]
        _save_carrito(request, carrito)
        messages.info(request, f'"{nombre}" eliminado del carrito.')

    return redirect('ver_carrito')


@buyer_required
def ver_carrito(request):
    """
    Muestra el contenido actual del carrito de compras.

    Si el carrito está vacío, muestra un mensaje y un botón
    para volver a la tienda.

    Contexto:
        carrito      → dict con los items del carrito
        total        → Decimal con el total a pagar
        carrito_count→ Cantidad de unidades para el badge
    """
    carrito = _get_carrito(request)
    total   = _calcular_total(carrito)

    context = {
        'carrito':       carrito,
        'total':         total,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'Mi Carrito',
        'nav_activo':    'tienda',
    }
    return render(request, 'core/carrito.html', context)


# ---------------------------------------------------------------------------
# CHECKOUT — Confirmación de compra y creación de orden
# ---------------------------------------------------------------------------

@buyer_required
def checkout(request):
    """
    Proceso de confirmación de compra y generación de la orden.

    GET:  Muestra el formulario de checkout con resumen del carrito
          y opciones de dirección de envío.

    POST: Crea la orden, sus items, reserva el inventario y registra el pago.
          Limpia el carrito de la sesión al finalizar.
          Redirige a la confirmación de la orden creada.

    Campos del formulario POST:
        notas         → Instrucciones especiales (opcional)
        shipping_cost → Costo de envío en USD (default 0)

    Validaciones:
        - El carrito no puede estar vacío
        - Se verifica el stock disponible producto a producto al crear
        - Si un producto quedó sin stock, se omite con un warning
    """
    carrito = _get_carrito(request)

    # Redirigir si el carrito está vacío
    if not carrito:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('tienda')

    subtotal = _calcular_total(carrito)

    if request.method == 'POST':
        notas         = request.POST.get('notas', '').strip()
        shipping_cost = Decimal(request.POST.get('shipping_cost', '0') or '0')

        # Crear la cabecera de la orden
        orden = Order.objects.create(
            buyer         = request.user,
            order_type    = 'b2c',
            shipping_cost = shipping_cost,
            notes         = notas,
            status        = 'pending',
        )

        # Crear los items y reservar inventario
        items_creados = 0
        for prod_id, item_data in carrito.items():
            try:
                producto = (
                    Product.objects
                    .select_related('inventory')
                    .get(pk=int(prod_id), is_active=True)
                )
                cantidad = item_data['cantidad']

                if producto.available_qty >= cantidad:
                    OrderItem.objects.create(
                        order                = orden,
                        product              = producto,
                        qty                  = cantidad,
                        unit_price_snapshot  = producto.unit_price,
                    )
                    # Reservar el stock para que otros no lo compren
                    if hasattr(producto, 'inventory'):
                        producto.inventory.reserve(cantidad)
                    items_creados += 1
                else:
                    messages.warning(
                        request,
                        f'Stock insuficiente para "{producto.name}" — item omitido.'
                    )

            except Product.DoesNotExist:
                # El producto fue desactivado entre que se agregó y el checkout
                messages.warning(
                    request,
                    f'Un producto ya no está disponible y fue omitido.'
                )

        if items_creados == 0:
            # Ningún item pudo procesarse — cancelar la orden
            orden.delete()
            messages.error(
                request,
                'No se pudo completar la orden. Verifica el stock de los productos.'
            )
            return redirect('ver_carrito')

        # Calcular totales finales
        orden.recalculate_totals()
        orden.shipping_cost = shipping_cost
        orden.total = orden.subtotal + shipping_cost
        orden.save(update_fields=['shipping_cost', 'total'])

        # Registrar el pago (mock para demo)
        Payment.objects.create(
            order    = orden,
            provider = 'mock',
            status   = 'approved',
            amount   = orden.total,
            currency = 'USD',
            paid_at=timezone.now(),
            txn_ref  = f'TF-MOCK-{orden.order_number}',
        )
        orden.status = 'paid'
        orden.save(update_fields=['status'])

        # Limpiar el carrito de la sesión
        _save_carrito(request, {})
        messages.success(
            request,
            f'Orden {orden.order_number} creada exitosamente. ¡Gracias por tu compra!'
        )
        try:
            enviar_confirmacion_orden(orden)
        except Exception:
            log.exception('No se pudo enviar email de confirmación de orden.')
        return redirect('detalle_mi_orden', pk=orden.pk)

    context = {
        'carrito':       carrito,
        'subtotal':      subtotal,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'Confirmar Orden',
        'nav_activo':    'tienda',
    }
    return render(request, 'core/checkout.html', context)


# ---------------------------------------------------------------------------
# MIS ÓRDENES — Historial del comprador
# ---------------------------------------------------------------------------

@buyer_required
def mis_ordenes(request):
    """
    Muestra el historial de órdenes del comprador autenticado.

    Solo muestra las órdenes que pertenecen al usuario actual.
    Un buyer nunca puede ver las órdenes de otro usuario.

    Filtros disponibles (GET params):
        estado → Filtra por status de la orden

    Paginación: 8 órdenes por página.
    """
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
        'titulo_pagina':  'Mis Órdenes',
        'nav_activo':     'mis_ordenes',
    }
    return render(request, 'core/mis_ordenes.html', context)


@buyer_required
def detalle_mi_orden(request, pk):
    """
    Muestra el detalle de una orden específica del comprador.

    Seguridad: filtra por buyer=request.user para asegurarse
    de que el comprador solo pueda ver sus propias órdenes.
    Un usuario no puede acceder a la orden de otro con su ID.
    """
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
        'titulo_pagina': f'Orden {orden.order_number}',
        'nav_activo':    'mis_ordenes',
    }
    return render(request, 'core/detalle_mi_orden.html', context)


@login_required
def descargar_factura(request, orden_pk):
    """
    Genera y descarga la factura PDF de una orden.

    El comprador solo puede descargar sus propias órdenes. Los administradores
    pueden descargar cualquier orden.
    """
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


# ---------------------------------------------------------------------------
# COTIZACIONES — RFQ buyer / seller
# ---------------------------------------------------------------------------


@buyer_required
def solicitar_cotizacion(request):
    """
    El comprador solicita una cotización formal a una empresa.

    GET con parámetro empresa: muestra productos de esa empresa para indicar cantidades.
    POST: crea Cotizacion + CotizacionItem para cada línea con cantidad > 0.
    Genera número COT-YYYYMM-XXXX automáticamente al guardar.
    """
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
            messages.error(request, 'Selecciona una empresa.')
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
            messages.error(request, 'Indica al menos un producto con cantidad mayor a cero.')
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

        messages.success(request, f'Cotización {cot.numero} enviada a {empresa_dest.name}.')
        return redirect('detalle_cotizacion', pk=cot.pk)

    context = {
        'empresas': empresas,
        'empresa_obj': empresa_obj,
        'empresa_id': empresa_id,
        'productos_emp': productos_emp,
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': 'Nueva cotización',
        'nav_activo': 'mis_cotizaciones',
    }
    return render(request, 'core/cotizacion_form.html', context)


@buyer_required
def mis_cotizaciones(request):
    """
    Lista todas las cotizaciones del comprador con empresa, estado y fecha.
    """
    lista = (
        Cotizacion.objects.filter(buyer=request.user)
        .select_related('empresa', 'order')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    context = {
        'cotizaciones': lista,
        'carrito_count': _contar_items(_get_carrito(request)),
        'titulo_pagina': 'Mis cotizaciones',
        'nav_activo': 'mis_cotizaciones',
    }
    return render(request, 'core/mis_cotizaciones.html', context)


@buyer_required
def detalle_cotizacion(request, pk):
    """
    Detalle de cotización con ítems. Si está respondida, muestra precios del vendedor.
    Permite convertir en orden (POST acción convertir), rechazar (POST rechazar)
    o aceptar tras conversión (orden vinculada).
    """
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
            messages.info(request, 'Cotización marcada como rechazada.')
            return redirect('detalle_cotizacion', pk=cot.pk)

        if accion == 'convertir' and cot.estado == 'respondida' and not cot.order_id:
            items = list(cot.items.all())
            if not items or any(it.precio_ofertado is None for it in items):
                messages.error(request, 'La cotización no tiene precios completos para generar la orden.')
                return redirect('detalle_cotizacion', pk=cot.pk)

            addr = Address.objects.filter(user=request.user).order_by('-is_default', 'id').first()

            with transaction.atomic():
                orden = Order.objects.create(
                    buyer=request.user,
                    ship_address=addr,
                    order_type='b2c',
                    shipping_cost=Decimal('0.00'),
                    notes=f'Generada desde cotización {cot.numero}',
                    status='pending',
                )
                items_ok = 0
                for it in items:
                    prod = it.product
                    qty = it.cantidad_solicitada
                    if prod.available_qty < qty:
                        orden.delete()
                        messages.error(
                            request,
                            f'Stock insuficiente para "{prod.name}". No se creó la orden.',
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
                    messages.error(request, 'No se pudo crear la orden.')
                    return redirect('detalle_cotizacion', pk=cot.pk)

                orden.recalculate_totals()
                orden.save(update_fields=['subtotal', 'total', 'updated_at'])
                Payment.objects.create(
                    order=orden,
                    provider='mock',
                    status='approved',
                    amount=orden.total,
                    currency='USD',
                    paid_at=timezone.now(),
                    txn_ref=f'TF-MOCK-COT-{cot.numero}',
                )
                orden.status = 'paid'
                orden.save(update_fields=['status'])
                cot.order = orden
                cot.estado = 'aceptada'
                cot.save(update_fields=['order', 'estado', 'updated_at'])

            messages.success(request, f'Orden {orden.order_number} creada desde la cotización.')
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
        'titulo_pagina': f'Cotización {cot.numero}',
        'nav_activo': 'mis_cotizaciones',
    }
    return render(request, 'core/detalle_cotizacion.html', context)


@seller_required
def seller_cotizaciones(request):
    """
    Lista cotizaciones recibidas por la empresa del vendedor autenticado.
    """
    company, resp = _seller_company_or_response(request, 'seller_cotizaciones')
    if resp:
        return resp

    lista = (
        Cotizacion.objects.filter(empresa=company)
        .select_related('buyer', 'order')
        .annotate(n_items=Count('items'))
        .order_by('-created_at')
    )
    context = {
        'company': company,
        'cotizaciones': lista,
        'titulo_pagina': 'Cotizaciones recibidas',
        'nav_activo': 'seller_cotizaciones',
    }
    return render(request, 'core/seller_cotizaciones.html', context)


@seller_required
def seller_responder_cotizacion(request, pk):
    """
    El vendedor responde con precio unitario ofertado por ítem y notas para el comprador.
    """
    company, resp = _seller_company_or_response(request, 'seller_cotizaciones')
    if resp:
        return resp

    cot = get_object_or_404(
        Cotizacion.objects.prefetch_related(
            Prefetch(
                'items',
                queryset=CotizacionItem.objects.select_related('product').defer(
                    'product__company__owner'
                ),
            )
        ),
        pk=pk,
        empresa=company,
    )

    if request.method == 'POST':
        if cot.estado not in ('pendiente', 'respondida'):
            messages.warning(request, 'Esta cotización ya no admite cambios.')
            return redirect('seller_cotizaciones')

        notas_seller = request.POST.get('notas_seller', '').strip()
        items_list = list(cot.items.all())
        with transaction.atomic():
            for it in items_list:
                key = f'precio_{it.pk}'
                raw = request.POST.get(key, '').strip()
                if raw:
                    try:
                        it.precio_ofertado = Decimal(raw)
                    except (InvalidOperation, ValueError):
                        messages.error(request, f'Precio inválido en línea: {it.product.name}')
                        return redirect('seller_responder_cotizacion', pk=cot.pk)
                    it.save(update_fields=['precio_ofertado'])
            cot.notas_seller = notas_seller
            if items_list and all(x.precio_ofertado is not None for x in items_list):
                cot.estado = 'respondida'
            cot.save(update_fields=['notas_seller', 'estado', 'updated_at'])

        messages.success(request, 'Cotización actualizada.')
        return redirect('seller_cotizaciones')

    context = {
        'company': company,
        'cot': cot,
        'titulo_pagina': f'Responder {cot.numero}',
        'nav_activo': 'seller_cotizaciones',
    }
    return render(request, 'core/seller_responder_cotizacion.html', context)