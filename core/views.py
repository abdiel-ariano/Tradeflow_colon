"""
=============================================================================
TRADEFLOW COLÓN — core/views.py  (v5 — Portal vendedor + Roles)
=============================================================================
Incluye: autenticación, admin, portal comprador (tienda, carrito, checkout),
portal vendedor (panel, productos, ventas) y API JSON de productos.
=============================================================================
"""
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

AUTH_MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'

NOMBRE_REGEX = re.compile(r"^[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s'\-]{2,50}$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9._]{2,29}$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

import folium
import qrcode
from folium.plugins import MarkerCluster
from django.core import signing

from .decorators import admin_required, buyer_required, catalog_access, seller_required
from .forms import SellerProductForm, SellerInventoryForm
from .email_service import enviar_codigo_verificacion as enviar_codigo_email
from .models import (
    UserProfile, Company, Category, Product, Inventory,
    Address, Order, OrderItem, Payment, Shipment, Document,
    Cotizacion, CotizacionItem, TransportCarrier, UserApplication,
    EmailVerification,
)
from .utils.email_sender import (
    enviar_bienvenida,
    enviar_cambio_estado,
    enviar_confirmacion_orden,
    enviar_orden_pendiente_vendedor,
    enviar_solicitud_recibida,
    enviar_solicitud_a_revisores,
    enviar_solicitud_decision,
)
from .utils.saas_billing import VolumeLimitExceeded, is_volume_limit_reached
from .utils.media_storage import product_image_url
from .utils.order_workflow import (
    accept_seller_order,
    reject_seller_order,
    seller_confirm_deadline,
    expire_pending_orders,
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


def _dashboard_calendar_days(dias, now=None):
    """
    Genera ventanas [inicio, fin) por día natural en la zona horaria del proyecto.

    Args:
        dias: Número de días (7, 30 o 90).
        now: Momento de referencia (aware); por defecto ``timezone.now()``.

    Returns:
        list[tuple]: Cada elemento es (day_start, day_end, label_str).
    """
    if now is None:
        now = timezone.now()
    dias = _normalize_dashboard_dias(dias)
    local_date = timezone.localtime(now).date()
    tzinfo = timezone.get_current_timezone()
    from .utils.chart_labels import chart_axis_label

    days = []
    for i in range(dias):
        day_date = local_date - timedelta(days=dias - 1 - i)
        day_start = timezone.make_aware(
            datetime.combine(day_date, time.min), tzinfo
        )
        day_end = day_start + timedelta(days=1)
        label = chart_axis_label(day_date, dias=dias)
        days.append((day_start, day_end, label))
    return days


def _build_dashboard_charts_payload(dias, now=None):
    """
    Construye etiquetas y series diarias para Chart.js y conteos por estado.

    Buckets por **medianoche local** (``TIME_ZONE``), no UTC naive con
    ``replace(hour=0)`` sobre ``now`` aware.

    ``estados_data`` agrupa órdenes **creadas** en la ventana de ``dias``;
    ``paid`` incluye ``packed``.
    """
    if now is None:
        now = timezone.now()

    from .utils.money_format import money_to_chart_float, quantize_money

    dias = _normalize_dashboard_dias(dias)
    calendar_days = _dashboard_calendar_days(dias, now=now)

    chart_labels = []
    ordenes_por_dia = []
    ingresos_por_dia = []

    for day_start, day_end, label in calendar_days:
        chart_labels.append(label)
        ordenes_por_dia.append(
            Order.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end
            ).count()
        )
        ing = (
            Order.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end
            )
            .exclude(status='cancelled')
            .aggregate(t=Sum('total'))['t']
            or Decimal('0')
        )
        ingresos_por_dia.append(money_to_chart_float(ing))

    window_start = calendar_days[0][0] if calendar_days else timezone.localtime(now)
    qs = Order.objects.filter(created_at__gte=window_start)
    by_status = {row['status']: row['c'] for row in qs.values('status').annotate(c=Count('id'))}
    # awaiting_seller se agrupa con pendiente en la dona para no perder volumen del período.
    estados_data = {
        'pending': (
            by_status.get('pending', 0)
            + by_status.get('awaiting_seller', 0)
        ),
        'paid':      by_status.get('paid', 0) + by_status.get('packed', 0),
        'shipped':   by_status.get('shipped', 0),
        'delivered': by_status.get('delivered', 0),
        'cancelled': by_status.get('cancelled', 0),
    }

    order_ids_period = list(
        qs.exclude(status='cancelled').values_list('id', flat=True)
    )
    items_period = OrderItem.objects.filter(order_id__in=order_ids_period)

    cat_rows = (
        items_period.values('product__category__name')
        .annotate(total=Sum('line_total'))
        .order_by('-total')[:6]
    )
    cat_grand = quantize_money(
        items_period.aggregate(t=Sum('line_total'))['t'] or 0
    )
    cat_grand_f = float(cat_grand)
    ventas_por_categoria = []
    for row in cat_rows:
        label = row['product__category__name'] or 'General'
        total_f = money_to_chart_float(row['total'] or 0)
        pct = round(100.0 * total_f / cat_grand_f, 1) if cat_grand_f > 0 else 0.0
        ventas_por_categoria.append({
            'label': label,
            'total': total_f,
            'pct': pct,
        })

    emp_rows = (
        items_period.values('product__company__name')
        .annotate(total=Sum('line_total'))
        .order_by('-total')[:8]
    )
    ventas_por_empresa = [
        {
            'label': row['product__company__name'] or 'No company',
            'total': money_to_chart_float(row['total'] or 0),
        }
        for row in emp_rows
    ]

    prod_rows = (
        items_period.values('product__name')
        .annotate(units=Sum('qty'))
        .order_by('-units')[:8]
    )
    productos_top = [
        {
            'label': row['product__name'] or 'Producto',
            'units': int(row['units'] or 0),
        }
        for row in prod_rows
    ]

    ordenes_por_tipo = {
        'b2b': qs.filter(order_type='b2b').count(),
        'b2c': qs.filter(order_type='b2c').count(),
    }

    period_label = _('Last %(n)s days') % {'n': dias}

    return {
        'chart_labels':         chart_labels,
        'ordenes_por_dia':      ordenes_por_dia,
        'ingresos_por_dia':     ingresos_por_dia,
        'estados_data':         estados_data,
        'ventas_por_categoria': ventas_por_categoria,
        'ventas_por_empresa':   ventas_por_empresa,
        'productos_top':        productos_top,
        'ordenes_por_tipo':     ordenes_por_tipo,
        'dias':                 dias,
        'period_label':         period_label,
    }


def _charts_json(payload):
    """Serializa el payload de gráficos del dashboard para plantilla o API."""
    return json.dumps(payload, ensure_ascii=False, cls=DjangoJSONEncoder)


def _dashboard_revenue_qs():
    """
    QuerySet base para KPIs de ingresos del dashboard admin.

    Si ``DASHBOARD_KPI_REVENUE_DELIVERED_ONLY`` es True, solo órdenes entregadas;
    si False (modo pruebas), todas las no canceladas.
    """
    if settings.DASHBOARD_KPI_REVENUE_DELIVERED_ONLY:
        return Order.objects.filter(status='delivered')
    return Order.objects.exclude(status='cancelled')


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

def _login_template_context(**extra):
    """
    Contexto común para la plantilla de login.

    Args:
        **extra: Claves adicionales (p. ej. mostrar_reenvio, email_pendiente).

    Returns:
        dict: Contexto para ``core/login.html``.
    """
    ctx = {
        'require_email_verification': settings.REQUIRE_EMAIL_VERIFICATION,
    }
    ctx.update(extra)
    return ctx


def login_view(request):
    """Login con redirección inteligente según rol."""
    if request.user.is_authenticated:
        return redirect(_redirect_by_role(request.user))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user, backend=AUTH_MODEL_BACKEND)

            try:
                profile = user.profile
                if user.is_active and profile.email_verificado and profile.role:
                    messages.success(
                        request,
                        f'Welcome, {user.first_name or user.username}!',
                    )
                    next_url = (request.GET.get('next') or '').strip()
                    if next_url.startswith('//') or '://' in next_url:
                        next_url = ''
                    elif next_url.startswith('/'):
                        home_path = reverse('home')
                        login_path = reverse('login')
                        if (
                            next_url in (home_path, '/')
                            or next_url == login_path
                            or next_url.startswith(login_path + '?')
                        ):
                            next_url = ''
                    else:
                        next_url = ''
                    dest = next_url if next_url else _redirect_by_role(user)
                    return redirect(dest)
            except UserProfile.DoesNotExist:
                pass

            from core.utils.access_gating import onboarding_redirect_name

            gate_route = onboarding_redirect_name(user)
            if gate_route:
                if settings.REQUIRE_EMAIL_VERIFICATION:
                    try:
                        if not user.profile.email_verificado:
                            messages.info(
                                request,
                                'Verify your email to access all features.',
                            )
                    except UserProfile.DoesNotExist:
                        pass
                return redirect(gate_route)

            messages.success(request, f'Welcome, {user.first_name or user.username}!')
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
            messages.error(request, 'Incorrect username or password.')

    return render(request, 'core/login.html', _login_template_context())


def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('login')


def signup_view(request):
    """Public registration: creates User + UserProfile."""
    if request.user.is_authenticated:
        return redirect(_redirect_by_role(request.user))

    if request.method == 'GET':
        return render(request, 'core/signup.html', {
            'role_choices': [('buyer', 'Buyer'), ('seller', 'Seller')],
            'selected_role': 'buyer',
            'form_first_name': '',
            'form_last_name': '',
            'form_email': '',
            'form_phone': '',
        })

    if request.method == 'POST':
        first_name = escape(request.POST.get('first_name', '').strip())
        last_name = escape(request.POST.get('last_name', '').strip())
        username = escape(request.POST.get('username', '').strip())
        email = request.POST.get('email', '').strip()
        phone = escape(request.POST.get('phone', '').strip())
        role = request.POST.get('role', 'buyer')
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        errores = []
        signup_ctx = {
            'role_choices': [('buyer', 'Buyer'), ('seller', 'Seller')],
            'selected_role': role if role in ('buyer', 'seller') else 'buyer',
            'form_first_name': request.POST.get('first_name', '').strip(),
            'form_last_name': request.POST.get('last_name', '').strip(),
            'form_email': email,
            'form_phone': phone,
        }

        if not all([first_name, username, email, password1, password2]):
            errores.append('All fields marked with * are required.')

        if not NOMBRE_REGEX.match(first_name):
            errores.append(
                'First name may only contain letters and spaces '
                '(minimum 2 characters, maximum 50).'
            )

        if last_name and not NOMBRE_REGEX.match(last_name):
            errores.append('Last name may only contain letters and spaces.')

        if not USERNAME_REGEX.match(username):
            errores.append(
                'Username must start with a letter and may only '
                'contain letters, numbers, dots, and '
                'underscores (3-30 characters).'
            )

        if not EMAIL_REGEX.match(email):
            errores.append('Enter a valid email address.')

        if len(password1) < 8:
            errores.append('Password must be at least 8 characters.')

        if password1.isdigit():
            errores.append('Password cannot be numbers only.')

        if password1.lower() in [
            'password', '12345678', 'qwerty123',
            'tradeflow', username.lower(),
        ]:
            errores.append(
                'Password is too common. Choose a stronger one.'
            )

        if password1 != password2:
            errores.append('Passwords do not match.')

        if errores:
            for error in errores:
                messages.error(request, error)
            return render(request, 'core/signup.html', signup_ctx)

        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists. Choose another.')
            return render(request, 'core/signup.html', signup_ctx)
        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with that email already exists.')
            return render(request, 'core/signup.html', signup_ctx)
        if role not in ('buyer', 'seller'):
            messages.error(request, 'Invalid account type.')
            return render(request, 'core/signup.html', signup_ctx)

        # Crear usuario
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )

        from .models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': role,
                'email_verificado': False,
            }
        )
        profile.role = role
        profile.save()

        # Create application record
        from .models import UserApplication
        UserApplication.objects.get_or_create(
            user=user,
            defaults={
                'full_name': f"{first_name} {last_name}".strip(),
                'email': email,
                'phone': phone,
                'role': role,
                'company_name': '',
                'message': '',
                'status': 'pending',
            }
        )

        if getattr(settings, 'EXPO_DEMO_MODE', False):
            user.is_active = True
            user.save(update_fields=['is_active'])
            login(request, user, backend=AUTH_MODEL_BACKEND)
            from core.views_onboarding import finalize_signup_with_otp

            return finalize_signup_with_otp(request, user)

        # Deactivate user until admin approves
        user.is_active = False
        user.save(update_fields=['is_active'])

        return redirect('pending_approval')

    return render(request, 'core/signup.html', {
        'role_choices': [('buyer', 'Buyer'), ('seller', 'Seller')],
        'selected_role': 'buyer',
        'form_first_name': '',
        'form_last_name': '',
        'form_email': '',
        'form_phone': '',
    })


def _redirect_after_email_verified(user):
    """Redirección post-verificación por rol (sin alterar login_view)."""
    try:
        role = user.profile.role
    except UserProfile.DoesNotExist:
        return redirect('tienda')
    if user.is_superuser or role == 'admin':
        return redirect('dashboard')
    if role == 'seller':
        return redirect('portal_seller')
    return redirect('tienda')


@login_required
def enviar_codigo(request):
    """Genera OTP, envía por Resend y redirige al formulario."""
    from core.auth_views import _email_verification_gate_active

    if not _email_verification_gate_active(request.user):
        messages.info(request, 'Email verification is disabled in this environment.')
        return redirect('tienda')

    try:
        profile = request.user.profile
        if profile.email_verified:
            messages.info(request, 'Your email is already verified.')
            return redirect('tienda')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Profile not found.')
        return redirect('signup')

    if not request.user.email:
        messages.error(request, 'Your account has no email address.')
        return redirect('verificar_codigo')

    verification = EmailVerification.generate_for(request.user)
    result = enviar_codigo_email(request.user.email, verification.code)
    if result.ok:
        messages.success(
            request,
            f'We sent a 6-digit code to {request.user.email}. Check your inbox and spam folder.',
        )
    else:
        messages.error(
            request,
            'We could not send the email. Check RESEND_API_KEY and DEFAULT_FROM_EMAIL in .env.',
        )
    return redirect('verificar_codigo')


# Alias legacy (rutas / onboarding anteriores)
enviar_codigo_verificacion = enviar_codigo


# OTP verificación segura — core/auth_views.py (django-axes, anti-replay, EXPO_DEMO_MODE)
from core.auth_views import verify_otp_view as verificar_codigo  # noqa: E402


def verificar_email(request, token):
    """
    Activa la cuenta si el token de verificación es válido.

    Si el email ya estaba verificado, informa al usuario. Invalida el token
    tras uso exitoso y envía correo de bienvenida.
    """
    try:
        profile = UserProfile.objects.select_related('user').get(
            token_verificacion=token,
        )
        if profile.email_verificado:
            messages.info(
                request,
                'Your email was already verified. You can log in.',
            )
        else:
            profile.email_verificado = True
            profile.token_verificacion = None
            profile.codigo_verificacion_email = ''
            profile.codigo_verificacion_expira = None
            profile.save(
                update_fields=[
                    'email_verificado',
                    'token_verificacion',
                    'codigo_verificacion_email',
                    'codigo_verificacion_expira',
                ]
            )
            enviar_bienvenida(profile.user)
            messages.success(
                request,
                'Email verified! Your account is active.',
            )
        if request.user.is_authenticated and request.user.pk == profile.user_id:
            from core.utils.access_gating import onboarding_redirect_name
            nxt = onboarding_redirect_name(request.user)
            return redirect(nxt or _redirect_by_role(profile.user))
        return redirect('login')

    except UserProfile.DoesNotExist:
        messages.error(
            request,
            'Verification link is invalid or has already been used.',
        )
        return redirect('login')


@login_required
def reenviar_verificacion(request):
    """
    Reenvía el correo de verificación al usuario autenticado no verificado.
    """
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        messages.info(
            request,
            'Email verification is disabled in this environment.',
        )
        return redirect('mi_perfil')

    profile = request.user.profile
    if not profile.email_verificado:
        return redirect('enviar_codigo')
    return redirect('mi_perfil')


def reenviar_verificacion_public(request):
    """
    Reenvía verificación por email sin sesión (formulario en login).
    """
    if not settings.REQUIRE_EMAIL_VERIFICATION:
        messages.info(
            request,
            'Email verification is disabled in this environment.',
        )
        return redirect('login')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            try:
                profile = user.profile
                if not profile.email_verificado:
                    messages.info(
                        request,
                        'Log in and use Resend code on the verification screen.',
                    )
                else:
                    messages.info(request, 'That account is already verified. You can log in.')
            except UserProfile.DoesNotExist:
                pass
        else:
            messages.warning(request, 'We could not find an account with that email.')
    return redirect('login')


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
            messages.success(request, 'Profile updated successfully.')

        elif action == 'change_password':
            current = request.POST.get('current_password')
            new_pass = request.POST.get('new_password')
            confirm = request.POST.get('confirm_password')

            if not request.user.check_password(current):
                messages.error(request, 'Current password is incorrect.')
            elif new_pass != confirm:
                messages.error(request, 'New passwords do not match.')
            elif len(new_pass or '') < 8:
                messages.error(request, 'Password must be at least 8 characters.')
            else:
                request.user.set_password(new_pass)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed successfully.')

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
        'titulo_pagina': 'My Profile',
        'nav_activo': 'perfil',
        'show_buyer': show_buyer,
        'show_seller': show_seller,
        'show_admin': show_admin,
        'role_key': role,
    })


def home_view(request):
    """
    Landing pública PreExpo: merchandising ORM, secciones CMS y stats reales.

    Usuarios autenticados redirigen a su panel; invitados ven la landing completa.
    """
    if request.user.is_authenticated:
        from core.utils.access_gating import onboarding_redirect_name

        gate_route = onboarding_redirect_name(request.user)
        if gate_route:
            return redirect(gate_route)
        return redirect(_redirect_by_role(request.user))

    from django.utils.translation import get_language

    from . import merchandising as merch

    lang = (get_language() or 'es')[:2]
    promo_sections = []
    for section in merch.active_home_sections():
        promo_sections.append({
            'section': section,
            'products': merch.resolve_section_products(section),
            'title': section.title_for_lang(lang),
            'subtitle': section.subtitle_for_lang(lang),
        })

    cms_types = {row['section'].section_type for row in promo_sections}
    show_daily_deals_strip = (
        'daily_deals' not in cms_types and len(merch.daily_deals(8)) >= 3
    )
    show_bestsellers_section = 'bestsellers' not in cms_types

    featured_qs = merch.active_products_base().filter(is_featured=True).select_related(
        'company', 'category',
    ).order_by('-merchandising_priority', '-created_at')[:8]
    if not featured_qs.exists():
        featured_qs = merch.active_products_base().select_related(
            'company', 'category',
        ).order_by('-created_at')[:8]

    bestsellers_list = merch.bestsellers(8)
    if not bestsellers_list:
        bestsellers_list = list(featured_qs[:8])

    empresas_home = list(
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('name')[:8]
    )
    if not empresas_home:
        empresas_home = merch.featured_companies_carousel(8)
    merch.spotlight_products_for_companies(empresas_home[:5], limit_per=3)

    empresas_premium, empresas_standard = merch.home_company_tiers(3, 8)
    trending = merch.trending_products(24)
    texture = merch.texture_products(12)

    return render(
        request,
        'core/home.html',
        {
            'stats': merch.home_stats(),
            'daily_deals': merch.daily_deals(8),
            'bestsellers': bestsellers_list,
            'featured_products': list(featured_qs),
            'trending_products': trending,
            'texture_products': texture,
            'carousel_products': merch.carousel_products(24),
            'catalog_breadth_products': merch.catalog_breadth_products(24),
            'empresas_carousel': empresas_home,
            'empresas_premium': empresas_premium,
            'empresas_standard': empresas_standard,
            'category_spotlights': merch.category_spotlights(4, 6),
            'promo_sections': promo_sections,
            'show_daily_deals_strip': show_daily_deals_strip,
            'show_bestsellers_section': show_bestsellers_section,
            'show_cart_actions': False,
        },
    )


@require_GET
def api_home_merchandising(request):
    """
    JSON público de merchandising home (cacheable) para integraciones ligeras.

    Returns:
        JsonResponse: ofertas, bestsellers, destacados y secciones CMS activas.
    """
    from django.core.cache import cache

    from . import merchandising as merch

    cache_key = 'tf_home_merch_v1'
    data = cache.get(cache_key)
    if data is None:
        sections = []
        for section in merch.active_home_sections():
            sections.append({
                'slug': section.slug,
                'type': section.section_type,
                'title_es': section.title_es,
                'title_en': section.title_en or section.title_es,
                'product_ids': [p.pk for p in merch.resolve_section_products(section)],
            })
        data = {
            'daily_deals': [p.pk for p in merch.daily_deals(12)],
            'bestsellers': [p.pk for p in merch.bestsellers(12)],
            'featured': [p.pk for p in merch.featured_products(12)],
            'sections': sections,
            'stats': merch.home_stats(),
        }
        cache.set(cache_key, data, 120)
    return JsonResponse(data)


def _assistant_system_prompt() -> str:
    from core.utils.saas_plan_catalog import build_saas_plans_ai_context

    return (
        "You are TradeFlow Colón's virtual assistant. TradeFlow Colón is a B2B/B2C "
        "marketplace for the Colón Free Zone in Panama — the world's second largest "
        "free trade zone. Help users with questions about: how to register, how to "
        "buy products, how to become a seller, seller SaaS plans and commissions, "
        "what is the Colón Free Zone, shipping and logistics, and general platform "
        "navigation. Be concise, professional, and always respond in the same "
        "language the user writes in. For seller plans use ONLY the data below; "
        "do not invent prices or commissions.\n\n"
        f"{build_saas_plans_ai_context()}"
    )

_ASSISTANT_FALLBACK = (
    "I'm sorry, the assistant is temporarily unavailable. Please try again in a "
    "moment, browse the store, or contact the support email shown on the site for help."
)


def _asistente_respuesta_html(text: str) -> str:
    safe = escape(text).replace('\n', '<br>')
    return (
        '<div class="tf-bot-card">'
        f'<p style="margin:0;line-height:1.55;">{safe}</p>'
        '</div>'
    )


def _asistente_json_payload(respuesta: str, *, ok: bool = True, status: int = 200):
    return JsonResponse(
        {
            'ok': ok,
            'respuesta': respuesta,
            'respuesta_html': _asistente_respuesta_html(respuesta),
        },
        status=status,
    )


@require_POST
def api_asistente(request):
    """
    Endpoint AJAX para el chat del asistente IA (Groq).

    POST body (JSON):
        mensaje: Pregunta del usuario.
        historial: Mensajes anteriores (opcional).

    Returns:
        JsonResponse: ``ok``, ``respuesta`` y ``respuesta_html``.
    """
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

    groq_api_key = (getattr(settings, 'GROQ_API_KEY', None) or '').strip()

    if not groq_api_key:
        logging.getLogger('tradeflow.ai').warning('api_asistente: GROQ_API_KEY not configured')
        return _asistente_json_payload(_ASSISTANT_FALLBACK)

    messages = [{'role': 'system', 'content': _assistant_system_prompt()}]
    if isinstance(historial, list):
        for item in historial[-6:]:
            if not isinstance(item, dict):
                continue
            role = item.get('role')
            content = (item.get('content') or '').strip()
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': content[:500]})

    if (
        not messages
        or messages[-1].get('role') != 'user'
        or messages[-1].get('content') != mensaje
    ):
        messages.append({'role': 'user', 'content': mensaje[:500]})

    try:
        from groq import Groq

        client = Groq(api_key=groq_api_key)
        model = getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant')
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
            temperature=0.5,
        )
        text = (response.choices[0].message.content or '').strip()
        if not text:
            raise ValueError('empty Groq response')
        return _asistente_json_payload(text)
    except Exception as exc:
        logging.getLogger('tradeflow.ai').warning(
            'api_asistente groq failed: %s', exc, exc_info=True,
        )
        return _asistente_json_payload(_ASSISTANT_FALLBACK)


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
            f'<span style="color:#6B7A88;">Active products:</span> {c.n_activos}<br>'
            f'<span style="color:#6B7A88;">Categories:</span> {cat_txt_e}<br>'
            f'<a href="{catalog_url_e}" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-block;margin-top:10px;padding:8px 14px;background:#F26522;'
            'color:#fff;border-radius:8px;text-decoration:none;font-weight:600;font-size:0.85rem;">'
            f'View catalog</a></div>'
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
        'map_html': map_html,
        'titulo_pagina': 'CFZ Map',
        'nav_activo': 'mapa_zlc',
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
        'titulo_pagina':  'My CFZ QR code',
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
        JsonResponse: payload de :func:`_build_dashboard_charts_payload`.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    dias = _normalize_dashboard_dias(request.GET.get('dias'))
    payload = _build_dashboard_charts_payload(dias)
    return JsonResponse(payload, encoder=DjangoJSONEncoder)


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

    revenue_qs = _dashboard_revenue_qs()
    ingresos_total = revenue_qs.aggregate(t=Sum('total'))['t'] or Decimal('0')
    ingresos_semana = revenue_qs.filter(created_at__gte=inicio_actual).aggregate(
        t=Sum('total')
    )['t'] or Decimal('0')
    ingresos_periodo_prev = revenue_qs.filter(
        created_at__gte=inicio_anterior,
        created_at__lt=inicio_prev_end,
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    ordenes_activas_periodo = (
        Order.objects.filter(created_at__gte=inicio_actual)
        .exclude(status='cancelled')
        .count()
    )
    ordenes_entregadas_periodo = Order.objects.filter(
        created_at__gte=inicio_actual, status='delivered'
    ).count()
    pct_entregadas_periodo = (
        round(Decimal(100) * ordenes_entregadas_periodo / ordenes_activas_periodo, 1)
        if ordenes_activas_periodo
        else Decimal('0')
    )

    dashboard_modo_pruebas = not settings.DASHBOARD_KPI_REVENUE_DELIVERED_ONLY
    if dashboard_modo_pruebas:
        kpi_ingresos_label = 'Period revenue (active orders)'
        kpi_ingresos_sub = 'All non-cancelled; delivery mark not required'
    else:
        kpi_ingresos_label = 'Delivered revenue (period)'
        kpi_ingresos_sub = 'Delivered orders only'

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

    from .utils.money_format import format_money_usd as _fmt_usd, quantize_money as _q_money

    ingresos_total = _q_money(ingresos_total)
    ingresos_semana = _q_money(ingresos_semana)

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
                'titulo': f'Order {o.order_number}',
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
        'charts_initial':       charts,
        'charts_initial_json':  _charts_json(charts),
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
        'periodo_label':        charts.get('period_label', ''),
        'titulo_pagina':        'Dashboard',
        'nav_activo':           'dashboard',
        'dashboard_modo_pruebas': dashboard_modo_pruebas,
        'kpi_ingresos_label':   kpi_ingresos_label,
        'kpi_ingresos_sub':     kpi_ingresos_sub,
        'ordenes_activas_periodo': ordenes_activas_periodo,
        'ordenes_entregadas_periodo': ordenes_entregadas_periodo,
        'pct_entregadas_periodo': pct_entregadas_periodo,
        'ingresos_semana_fmt': _fmt_usd(ingresos_semana),
        'ingresos_total_fmt': _fmt_usd(ingresos_total),
    }
    return render(request, 'core/dashboard.html', context)


# =============================================================================
# ÓRDENES (solo admin)
# =============================================================================

@admin_required
def lista_ordenes(request):
    ordenes = (
        Order.objects.select_related('buyer')
        .annotate(item_count=Count('items', distinct=True))
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

    estado_opciones = [{'value': '', 'label': 'All statuses', 'selected': not bool(estado)}]
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
        'titulo_pagina':       'Order management',
        'nav_activo':          'ordenes',
    }
    return render(request, 'core/ordenes.html', context)


@admin_required
def detalle_orden(request, pk):
    orden = get_object_or_404(
        Order.objects.select_related('buyer', 'ship_address').prefetch_related(
            Prefetch(
                'items',
                queryset=OrderItem.objects.select_related(
                    'product', 'product__company', 'product__category'
                ).order_by('id'),
            ),
            'documents',
        ),
        pk=pk,
    )
    # Materializar líneas en una lista para evitar inconsistencias con prefetch
    # o caché de relación inversa en plantillas con órdenes muy grandes (simulación anual).
    orden_items = list(orden.items.all())
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
        'orden_items':     orden_items,
        'pago':            pago,
        'envio':           envio,
        'otros_estados':   otros_estados,
        'titulo_pagina':   f'Order {orden.order_number}',
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
        messages.success(request, f'Order updated to "{orden.get_status_display()}".')
        try:
            enviar_cambio_estado(orden, estado_anterior)
        except Exception:
            log.exception('No se pudo enviar email de cambio de estado.')
    else:
        messages.error(request, 'Invalid status.')

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
            messages.error(request, 'You must select a buyer.')
        else:
            request.session['wizard_buyer_id']   = int(buyer_id)
            request.session['wizard_order_type'] = order_type
            return redirect('nueva_orden_paso2')

    return render(request, 'core/nueva_orden_paso1.html', {
        'compradores':   compradores,
        'order_types':   Order.ORDER_TYPE_CHOICES,
        'titulo_pagina': 'New order — Step 1',
        'nav_activo':    'ordenes',
        'paso_actual':   1,
    })


@admin_required
def nueva_orden_paso2(request):
    if not request.session.get('wizard_buyer_id'):
        messages.error(request, 'Complete step 1 first.')
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
                messages.error(request, 'Product not found.')
                return redirect('nueva_orden_paso2')

            disponible = producto.available_qty
            if cantidad < 1:
                messages.error(request, 'Quantity must be at least 1.')
            elif cantidad > disponible:
                messages.error(request, f'Insufficient stock. Available: {disponible}.')
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
                messages.success(request, f'"{producto.name}" added.')

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
                messages.error(request, 'Add at least one product.')
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
        'titulo_pagina': 'New order — Step 2',
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
        messages.error(request, 'Session expired. Start the order again.')
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
                        f'Insufficient stock for "{producto.name}", item skipped.'
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

        messages.success(request, f'Order {orden.order_number} created successfully!')
        return redirect('detalle_orden', pk=orden.pk)

    return render(request, 'core/nueva_orden_paso3.html', {
        'buyer':         buyer,
        'order_type':    order_type,
        'items':         items,
        'subtotal':      subtotal,
        'direcciones':   direcciones,
        'metodos_pago':  Payment.PROVIDER_CHOICES,
        'titulo_pagina': 'New order — Step 3',
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
        'titulo_pagina':          'Product catalog',
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
        'titulo_pagina': 'Companies',
        'nav_activo':    'empresas',
    })


# =============================================================================
# PORTALES DE ROL (placeholder — se expanden el Día 3 y 4)
# =============================================================================

@buyer_required
def portal_buyer(request):
    """Portal del comprador — se completa el Lunes 14."""
    return render(request, 'core/portal_buyer_temp.html', {
        'titulo_pagina': 'TradeFlow store',
    })


@seller_required
def seller_company_qr(request):
    """QR code linking to the seller company catalog in the public store."""
    try:
        company = Company.objects.get(owner=request.user)
    except Company.DoesNotExist:
        messages.error(request, 'No company linked to your account.')
        return redirect('portal_seller')

    catalog_url = request.build_absolute_uri(
        reverse('tienda') + f'?empresa={company.pk}'
    )
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(catalog_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0F2A44', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'core/seller_qr.html', {
        'company': company,
        'qr_base64': qr_base64,
        'catalog_url': catalog_url,
        'titulo_pagina': 'Company QR',
        'nav_activo': 'seller_qr',
    })


@seller_required
def seller_download_qr(request):
    """Download PNG QR for the seller company catalog URL."""
    try:
        company = Company.objects.get(owner=request.user)
    except Company.DoesNotExist:
        return redirect('portal_seller')

    catalog_url = request.build_absolute_uri(
        reverse('tienda') + f'?empresa={company.pk}'
    )
    qr = qrcode.QRCode(version=1, box_size=15, border=4)
    qr.add_data(catalog_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0F2A44', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    safe_name = re.sub(r'[^\w\-]+', '-', company.name).strip('-') or 'company'
    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="qr-{safe_name}.png"'
    return response


@seller_required
def portal_seller(request):
    """Dashboard premium del vendedor en /mi-tienda/."""
    import json as _json

    from .utils.order_workflow import expire_pending_orders
    from .utils.seller_analytics import seller_portal_dashboard

    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    expire_pending_orders()
    data = seller_portal_dashboard(company)

    return render(request, 'core/portal_seller.html', {
        'company': company,
        **data,
        'chart_revenue_labels_json': _json.dumps(data['chart_revenue_labels']),
        'chart_revenue_values_json': _json.dumps(data['chart_revenue_values']),
        'chart_status_labels_json': _json.dumps(data['chart_status_labels']),
        'chart_status_values_json': _json.dumps(data['chart_status_values']),
        'chart_week_labels_json': _json.dumps(data['chart_week_labels']),
        'chart_week_orders_json': _json.dumps(data['chart_week_orders']),
        'titulo_pagina': _('Seller dashboard'),
        'nav_activo': 'mi_tienda',
    })


@seller_required
@require_GET
def api_seller_dashboard(request):
    """Polling ligero para actualizaciones del panel seller."""
    from .utils.seller_analytics import seller_portal_dashboard

    company = _get_seller_company(request.user)
    if not company:
        return JsonResponse({'error': 'no_company'}, status=403)
    data = seller_portal_dashboard(company)
    return JsonResponse({
        'pending_confirm': data['pending_confirm'],
        'ordenes_semana': data['ordenes_semana'],
        'updated': False,
    })


@seller_required
@require_GET
def api_seller_order_timeline(request, pk):
    """Timeline logística JSON para polling / Supabase Realtime complemento."""
    company = _get_seller_company(request.user)
    if not company:
        return JsonResponse({'error': 'no_company'}, status=403)
    orden = get_object_or_404(
        Order.objects.select_related('shipment').prefetch_related('logistics_events'),
        pk=pk,
    )
    if not orden.items.filter(product__company=company).exists():
        raise Http404
    from .utils.order_timeline import build_order_timeline

    return JsonResponse(build_order_timeline(orden))


@seller_required
def seller_plan_consumo(request):
    """Dashboard de consumo SaaS y planes."""
    import logging

    saas_log = logging.getLogger('tradeflow.saas')

    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    from .utils.saas_billing import build_plan_page_context_safe
    from .utils.saas_platform import bootstrap_saas_for_company, get_saas_health

    health = bootstrap_saas_for_company(company)
    saas_log.info(
        'seller_plan_consumo company_id=%s plans=%s health_ok=%s issues=%s',
        company.pk,
        health.get('plans_count'),
        health.get('ok'),
        health.get('issues'),
    )

    ctx, page_error = build_plan_page_context_safe(company)
    ctx.update({
        'company': company,
        'titulo_pagina': _('TradeFlow growth'),
        'nav_activo': 'mi_tienda',
        'saas_health': health,
        'saas_page_error': page_error,
    })

    if not ctx.get('plans_available') and not page_error:
        saas_log.warning(
            'seller_plan_consumo empty_plan_cards company_id=%s plans_in_db=%s',
            company.pk,
            health.get('plans_count'),
        )

    return render(request, 'core/seller_plan_consumo.html', ctx)


@seller_required
@require_POST
def seller_dispatch_order(request, pk):
    """Despacho logístico 1-clic (webhook + timeline)."""
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp
    orden = get_object_or_404(
        Order.objects.select_related('shipment'),
        pk=pk,
    )
    if not orden.items.filter(product__company=company).exists():
        raise Http404
    from .utils.order_permissions import assert_can_dispatch

    try:
        assert_can_dispatch(orden, company)
    except PermissionError as exc:
        messages.error(request, str(exc))
        return redirect('seller_detalle_venta', pk=pk)
    from .utils.logistics_enterprise import enqueue_dispatch
    from .utils.saas_billing import plan_allows_feature

    if not plan_allows_feature(company, 'webhooks'):
        messages.info(
            request,
            _('Dispatch recorded internally. Enable Corporate Pro for partner webhooks.'),
        )
    enqueue_dispatch(orden, company, request.user)
    messages.success(request, _('Dispatch started. Tracking updated.'))
    if _request_wants_json(request):
        from .utils.order_timeline import build_order_timeline

        return JsonResponse({'ok': True, 'timeline': build_order_timeline(orden)})
    return redirect('seller_detalle_venta', pk=pk)


@seller_required
def seller_plan_checkout(request, plan_slug: str):
    """Pantalla de pago antes de activar un plan nuevo."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    if plan_slug == 'ecosistema_enterprise':
        return redirect(f'{reverse("solicitud_acceso")}?plan=enterprise')

    from .utils.saas_billing import build_checkout_context, get_or_create_subscription

    sub = get_or_create_subscription(company)
    from .enterprise_models import SaasPlan

    target = SaasPlan.objects.filter(slug=plan_slug, is_active=True).first()
    if not target:
        messages.error(request, _('Invalid plan.'))
        return redirect('seller_plan_consumo')
    if sub.plan.slug == plan_slug:
        messages.info(request, _('You already have this plan active.'))
        return redirect('seller_plan_consumo')
    if target.sort_order <= sub.plan.sort_order:
        messages.info(request, _('Select a plan higher than your current one.'))
        return redirect('seller_plan_consumo')

    try:
        ctx = build_checkout_context(company, plan_slug)
    except ValueError as exc:
        if 'commercial' in str(exc):
            return redirect(f'{reverse("solicitud_acceso")}?plan=enterprise')
        messages.error(request, _('Could not start checkout.'))
        return redirect('seller_plan_consumo')

    ctx.update({
        'company': company,
        'titulo_pagina': _('Plan payment'),
        'nav_activo': 'mi_tienda',
    })
    return render(request, 'core/seller_plan_checkout.html', ctx)


@seller_required
def seller_plan_checkout_resume(request):
    """Retoma un checkout pendiente."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp
    from .utils.saas_billing import get_pending_checkout

    pending = get_pending_checkout(company)
    if not pending:
        messages.info(request, _('You have no pending payments.'))
        return redirect('seller_plan_consumo')
    return redirect('seller_plan_checkout', plan_slug=pending.target_plan.slug)


@seller_required
@require_POST
def seller_plan_checkout_pay(request, plan_slug: str):
    """Confirma pago y activa plan en Supabase."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp

    from .utils.saas_billing import complete_plan_checkout, get_pending_checkout

    checkout = get_pending_checkout(company)
    if not checkout or checkout.target_plan.slug != plan_slug:
        messages.error(request, _('Invalid payment session. Choose your plan again.'))
        return redirect('seller_plan_consumo')

    provider = request.POST.get('payment_method', 'mock').strip() or 'mock'
    card_name = request.POST.get('card_name', '').strip()
    txn_ref = ''
    if provider == 'mock' and card_name:
        txn_ref = f'MOCK-{checkout.pk}'

    try:
        complete_plan_checkout(checkout, provider=provider, txn_ref=txn_ref)
    except ValueError:
        messages.error(request, _('Payment could not be completed.'))
        return redirect('seller_plan_checkout', plan_slug=plan_slug)

    messages.success(
        request,
        _('Payment confirmed. Plan %(name)s is active on your account.')
        % {'name': checkout.target_plan.name},
    )
    return redirect('seller_plan_consumo')


@seller_required
@require_POST
def seller_upgrade_plan(request):
    """Redirige al checkout (compatibilidad con formularios antiguos)."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp
    slug = request.POST.get('plan_slug', '').strip()
    if not slug:
        return redirect('seller_plan_consumo')
    return redirect('seller_plan_checkout', plan_slug=slug)


@seller_required
def seller_predictive_insights(request):
    """Panel IA predictiva — solo Ecosistema Enterprise."""
    company, resp = _seller_company_or_response(request, 'mi_tienda')
    if resp:
        return resp
    from .utils.saas_billing import plan_allows_feature
    from .utils.predictive_insights import get_predictive_dashboard, optional_groq_narrative
    import json as _json

    if not plan_allows_feature(company, 'predictive_ai'):
        return render(request, 'core/seller_insights_upgrade.html', {
            'company': company,
            'titulo_pagina': _('Predictive insights'),
            'nav_activo': 'seller_insights',
        })

    dashboard = get_predictive_dashboard(company)
    narrative = optional_groq_narrative(dashboard)
    return render(request, 'core/seller_insights.html', {
        'company': company,
        'insights': dashboard,
        'narrative': narrative,
        'chart_labels_json': _json.dumps(dashboard.get('daily_chart', {}).get('labels', [])),
        'chart_values_json': _json.dumps(dashboard.get('daily_chart', {}).get('values', [])),
        'titulo_pagina': _('Predictive insights'),
        'nav_activo': 'seller_insights',
    })


def _optimize_product_image_from_request(request, product_form, product):
    """Optimiza imagen subida antes de persistir (storage cloud-friendly).

    Si la imagen falla las validaciones de seguridad de
    `optimize_uploaded_image` (tamano > 10 MiB, formato no permitido,
    decompression bomb, archivo malformado), se muestra un mensaje al
    usuario y se guarda el producto SIN la imagen nueva (conservando la
    anterior si esta editando). Asi evitamos un 500 ante uploads invalidos.
    """
    if 'image' not in request.FILES:
        return product
    from django.core.exceptions import ValidationError as _ValidationError

    from .utils.media_storage import optimize_uploaded_image

    try:
        product.image = optimize_uploaded_image(request.FILES['image'])
    except _ValidationError as exc:
        detalle = exc.message if hasattr(exc, 'message') else (
            exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
        )
        messages.error(request, _('Imagen rechazada: %(detalle)s') % {'detalle': detalle})
    return product


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
        'Your account is not linked to a company yet. Please contact the administrator to assign your company.',
    )
    ctx = {
        'titulo_pagina': 'My store',
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
        'titulo_pagina':     'Seller dashboard',
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
        Product.objects.filter(company=company, is_active=True)
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
        'titulo_pagina': 'My products',
        'nav_activo':    'seller_productos',
    }
    return render(request, 'core/seller_productos.html', context)

@seller_required
def seller_mis_productos(request):
    """Dashboard de productos con KPIs, gráfico y tabla filtrable."""
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp

    from .utils.seller_analytics import seller_products_dashboard

    productos = (
        Product.objects.filter(company=company)
        .select_related('category', 'company')
        .defer('company__owner')
        .prefetch_related('inventory')
    )
    dash = seller_products_dashboard(company)

    buscar = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    estado = request.GET.get('estado', 'activo').strip() or 'activo'
    stock_f = request.GET.get('stock', '').strip()
    orden = request.GET.get('orden', 'nombre')

    if buscar:
        productos = productos.filter(
            Q(name__icontains=buscar)
            | Q(description__icontains=buscar)
            | Q(sku__icontains=buscar)
        )
    if categoria:
        productos = productos.filter(category_id=categoria)
    if estado == 'activo':
        productos = productos.filter(is_active=True)
    elif estado == 'inactivo':
        productos = productos.filter(is_active=False)
    elif estado != 'todos':
        productos = productos.filter(is_active=True)
        estado = 'activo'

    vendidos_ids = set(
        OrderItem.objects.filter(product__company=company)
        .values_list('product_id', flat=True)
    )
    if stock_f == 'bajo':
        low_ids = []
        for inv in Inventory.objects.filter(product__company=company).select_related('product'):
            if inv.is_low_stock:
                low_ids.append(inv.product_id)
        productos = productos.filter(pk__in=low_ids or [0])
    elif stock_f == 'sin_ventas':
        productos = productos.exclude(pk__in=vendidos_ids)

    if orden == 'precio_asc':
        productos = productos.order_by('unit_price')
    elif orden == 'precio_desc':
        productos = productos.order_by('-unit_price')
    elif orden == 'stock':
        productos = productos.order_by('inventory__stock_qty')
    else:
        productos = productos.order_by('name')

    paginator = Paginator(productos, 15)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    import json as _json

    return render(request, 'core/seller_mis_productos.html', {
        'company': company,
        'productos': page_obj,
        'categorias': Category.objects.all().order_by('name'),
        'buscar': buscar,
        'cat_activa': categoria,
        'estado_filtro': estado,
        'stock_filtro': stock_f,
        'orden': orden,
        'dash': dash,
        'chart_cat_labels_json': _json.dumps(dash['chart_cat_labels']),
        'chart_cat_values_json': _json.dumps(dash['chart_cat_values']),
        'titulo_pagina': 'My products',
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
        if is_volume_limit_reached(company):
            messages.error(
                request,
                _(
                    "You have reached your plan's monthly limit. "
                    'Upgrade your plan before publishing new products.'
                ),
            )
            return redirect('seller_plan_consumo')
        product_form = SellerProductForm(request.POST, request.FILES)
        inv_form     = SellerInventoryForm(request.POST)
        if product_form.is_valid() and inv_form.is_valid():
            with transaction.atomic():
                product = product_form.save(commit=False)
                product.company = company
                product = _optimize_product_image_from_request(request, product_form, product)
                product.save()
                inv = inv_form.save(commit=False)
                inv.product = product
                inv.reserved_qty = 0
                inv.save()
            messages.success(request, f'Product "{product.name}" created successfully.')
            return redirect('seller_productos')
        messages.error(request, 'Please check the form data.')

    context = {
        'company':        company,
        'product_form':   product_form,
        'inv_form':       inv_form,
        'titulo_pagina':  'New product',
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
                product = product_form.save(commit=False)
                product = _optimize_product_image_from_request(request, product_form, product)
                product.save()
                inv_form.save()
            messages.success(request, 'Changes saved.')
            return redirect('seller_productos')
        messages.error(request, 'Please check the form data.')

    context = {
        'company':        company,
        'product':        product,
        'product_form':   product_form,
        'inv_form':       inv_form,
        'titulo_pagina':  f'Edit: {product.name}',
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
    """Activa/desactiva un producto del vendedor (POST; JSON para AJAX)."""
    if request.method != 'POST':
        return redirect('seller_mis_productos')
    company, resp = _seller_company_or_response(request, 'seller_productos')
    if resp:
        return resp
    product = get_object_or_404(Product, pk=pk, company=company)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])
    estado = _('active') if product.is_active else _('inactive')
    if _request_wants_json(request):
        from .utils.seller_analytics import seller_product_kpis

        kpis = seller_product_kpis(company)
        return JsonResponse({
            'ok': True,
            'id': product.pk,
            'is_active': product.is_active,
            'kpi_total': kpis['kpi_total'],
            'kpi_activos': kpis['kpi_activos'],
            'message': _('Product "%(name)s" is now %(estado)s.') % {
                'name': product.name,
                'estado': estado,
            },
        })
    messages.success(
        request,
        _('Product "%(name)s" is now %(estado)s.') % {'name': product.name, 'estado': estado},
    )
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
        'titulo_pagina':  'My sales',
        'nav_activo':     'seller_ventas',
    }
    return render(request, 'core/seller_ventas.html', context)

@seller_required
def seller_mis_ventas(request):
    """Dashboard de ventas con métricas, gráfico y exportación."""
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    from .utils.order_workflow import expire_pending_orders

    expire_pending_orders()

    from .utils.seller_analytics import seller_sales_dashboard

    import json as _json

    dash = seller_sales_dashboard(company, days=30)
    ordenes = dash['ordenes_qs']

    estado = request.GET.get('estado', '').strip()
    pago = request.GET.get('pago', '').strip()
    desde = request.GET.get('desde', '').strip()
    hasta = request.GET.get('hasta', '').strip()

    if estado:
        ordenes = ordenes.filter(status=estado)
    if desde:
        try:
            d = datetime.strptime(desde, '%Y-%m-%d').date()
            ordenes = ordenes.filter(created_at__date__gte=d)
        except ValueError:
            pass
    if hasta:
        try:
            d = datetime.strptime(hasta, '%Y-%m-%d').date()
            ordenes = ordenes.filter(created_at__date__lte=d)
        except ValueError:
            pass
    if pago == 'pagado':
        ordenes = ordenes.filter(status__in=('paid', 'packed', 'shipped', 'delivered'))
    elif pago == 'pendiente':
        ordenes = ordenes.filter(status='pending')

    paginator = Paginator(ordenes, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'core/seller_mis_ventas.html', {
        'company': company,
        'ordenes': page_obj,
        'estado_actual': estado,
        'pago_filtro': pago,
        'desde': desde,
        'hasta': hasta,
        'status_choices': Order.STATUS_CHOICES,
        'ventas_mes': dash['ventas_mes'],
        'ingresos_mes': dash['ingresos_mes'],
        'ticket_promedio': dash['ticket_promedio'],
        'chart_line_labels_json': _json.dumps(dash['chart_line_labels']),
        'chart_line_values_json': _json.dumps(dash['chart_line_values']),
        'titulo_pagina': 'Mis ventas',
        'nav_activo': 'seller_ventas',
    })


@seller_required
def seller_export_ventas_csv(request):
    """Exporta transacciones del vendedor a CSV."""
    import csv

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

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="ventas_{company.pk}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(['ID', 'Fecha', 'Cliente', 'Monto', 'Estado', 'Tipo'])
    for o in ordenes[:500]:
        sub = sum(
            li.line_total
            for li in o.items.filter(product__company=company)
        )
        writer.writerow([
            o.order_number,
            o.created_at.strftime('%Y-%m-%d %H:%M'),
            o.buyer.get_full_name() or o.buyer.username,
            sub,
            o.get_status_display(),
            o.get_order_type_display(),
        ])
    return response

@seller_required
def seller_venta_detalle(request, pk):
    """
    Muestra el detalle de una orden limitado a las líneas de la empresa del vendedor.
    """
    company, resp = _seller_company_or_response(request, 'seller_ventas')
    if resp:
        return resp

    orden = get_object_or_404(
        Order.objects.select_related(
            'buyer', 'ship_address', 'transport_carrier', 'confirming_company', 'shipment',
        ).prefetch_related('logistics_events'),
        pk=pk,
    )
    lineas = list(
        orden.items.filter(product__company=company)
        .select_related('product')
        .order_by('id')
    )
    if not lineas:
        raise Http404('Order not found or has no products from your company.')

    from .utils.order_permissions import get_seller_order_actions

    order_actions = get_seller_order_actions(orden, company)
    puede_confirmar = order_actions['can_confirm']

    if request.method == 'POST' and request.POST.get('accion') == 'despachar':
        messages.error(request, _('Use the dispatch button in the logistics section.'))
        return redirect('seller_detalle_venta', pk=pk)

    if request.method == 'POST' and puede_confirmar:
        accion = request.POST.get('accion', '')
        estado_prev = orden.status
        if accion == 'aceptar':
            try:
                accept_seller_order(orden)
            except VolumeLimitExceeded as exc:
                messages.error(
                    request,
                    _(
                        'Monthly plan limit reached (USD %(limit)s). '
                        'Upgrade your plan to confirm this sale of USD %(add)s.'
                    ) % {'limit': exc.limit, 'add': exc.additional},
                )
                return redirect('seller_plan_consumo')
            messages.success(request, _('Order confirmed. The buyer was notified.'))
            try:
                enviar_cambio_estado(orden, estado_prev)
                enviar_confirmacion_orden(orden)
            except Exception:
                log.exception('Email post-confirmación vendedor')
        elif accion == 'rechazar':
            reject_seller_order(orden)
            messages.warning(request, _('Order rejected. Reserved inventory was released.'))
            try:
                enviar_cambio_estado(orden, estado_prev)
            except Exception:
                log.exception('Email rechazo orden')
        return redirect('seller_detalle_venta', pk=pk)

    subtotal_vendedor = sum((li.line_total for li in lineas), Decimal('0.00'))

    from .utils.order_timeline import build_order_timeline

    context = {
        'company': company,
        'orden': orden,
        'lineas_vendedor': lineas,
        'subtotal_vendedor': subtotal_vendedor,
        'pago': getattr(orden, 'payment', None),
        'puede_confirmar': puede_confirmar,
        'order_actions': order_actions,
        'maps_url': orden.maps_url_buyer(),
        'titulo_pagina': f'Sale {orden.order_number}',
        'nav_activo': 'seller_ventas',
        'timeline_initial_json': json.dumps(build_order_timeline(orden)),
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
            'categoria': p.category.name if p.category else 'Uncategorized',
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


def _request_wants_json(request):
    """True si el cliente espera respuesta JSON (fetch/AJAX)."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


# ---------------------------------------------------------------------------
# TIENDA — Catálogo principal del comprador
# ---------------------------------------------------------------------------

def _tienda_pagination_slots(page_obj, on_each_side=2, on_ends=1):
    """
    Construye la lista de entradas para la paginación elidida del catálogo.

    Cada elemento es ``{'type': 'page', 'num': int}`` o ``{'type': 'ellipsis'}``.
    """
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


@catalog_access
def catalogo_publico(request):
    """Catálogo público read-only (sin login) — filtros + grid de productos."""
    from decimal import Decimal, InvalidOperation

    from django.db.models import Case, DecimalField, F, IntegerField, When

    from . import merchandising as merch

    catalogo_base = merch.active_products_base()
    stats = merch.home_stats()
    verified_empresas = (
        Company.objects.filter(is_verified=True, products__is_active=True)
        .distinct()
        .count()
    )

    buscar = request.GET.get('buscar', '').strip()
    categorias_sel = [c for c in request.GET.getlist('categoria') if c.strip()]
    empresa = request.GET.get('empresa', '').strip()
    precio_min = request.GET.get('precio_min', '').strip()
    precio_max = request.GET.get('precio_max', '').strip()
    solo_stock = request.GET.get('stock', '') in ('1', 'true', 'on')
    solo_stock_low = request.GET.get('stock_low', '') in ('1', 'true', 'on')
    solo_on_sale = request.GET.get('on_sale', '') in ('1', 'true', 'on')
    solo_verificado = request.GET.get('verificado', '') == '1'
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
        from .utils.ads_ranking import annotate_sponsored_score

        productos = annotate_sponsored_score(productos).order_by('-sponsored_score', 'name')
    else:
        productos = productos.order_by(orden_map[orden_key])

    total_resultados = productos.count()
    paginator = Paginator(productos, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    categorias = (
        Category.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('name')
    )

    empresas = (
        Company.objects.annotate(
            num_productos=Count('products', filter=Q(products__is_active=True)),
        )
        .filter(num_productos__gt=0)
        .order_by('name')
    )

    sugerencias = list(
        categorias.order_by('-num_productos').values_list('name', flat=True)[:5]
    )
    if not sugerencias:
        sugerencias = ['Electronics', 'Textiles', 'Logistics', 'Spare parts']

    qcopy = request.GET.copy()
    qcopy.pop('page', None)
    qcopy.pop('partial', None)
    catalogo_params = qcopy.urlencode()

    meta_description = (
        f'Explore {stats["productos"]} wholesale products from '
        f'{verified_empresas or stats["empresas"]} verified Colón Free Zone companies. '
        f'B2B catalog with transparent inventory on TradeFlow.'
    )

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
        'catalogo_stats': stats,
        'verified_empresas': verified_empresas,
        'total_resultados': total_resultados,
        'sugerencias': sugerencias,
        'pagination_slots': _tienda_pagination_slots(page_obj),
        'meta_description': meta_description,
        'titulo_pagina': 'Catalog',
        'nav_activo': 'catalogo',
        'category_spotlights': merch.category_spotlights(4, 4),
    }

    is_partial = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.GET.get('partial') == '1'
    )
    if is_partial:
        return render(request, 'core/catalogo_publico_partial.html', context)
    return render(request, 'core/catalogo_publico.html', context)


@catalog_access
def tienda(request):
    """
    Muestra el catálogo de productos disponibles para el comprador.

    Funcionalidades:
        - Pestañas: por categoría (sidebar + grid) o por empresa (cards de empresa).
        - Búsqueda por nombre, descripción o SKU; filtros por categoría y empresa.
        - Paginación de 12 productos por página.
        - Solo productos activos.

    Contexto enviado al template:
        productos, categorias, empresas_catalogo, empresas_filtro,
        buscar, cat_activa, emp_activa, vista_tab, tienda_params,
        carrito_count, titulo_pagina, nav_activo, tienda_stats, tab_urls,
        show_spotlights, spotlight_*.
    """
    from . import merchandising as merch
    from django.db import models as db_models

    def _tienda_tab_url(tab_name):
        q = request.GET.copy()
        q.pop('page', None)
        if tab_name == 'todos':
            q.pop('tab', None)
        else:
            q['tab'] = tab_name
        qs = q.urlencode()
        return f"{reverse('tienda')}?{qs}" if qs else reverse('tienda')

    is_guest = not request.user.is_authenticated
    if is_guest:
        role = None
    else:
        try:
            role = request.user.profile.role
        except Exception:
            role = None
    show_cart_actions = (
        not is_guest
        and (
            role == 'buyer'
            or role == 'admin'
            or request.user.is_superuser
        )
    )

    catalogo_base = merch.active_products_base()
    now = timezone.now()
    promo_q = (
        Q(promo_price__isnull=False)
        & Q(promo_price__lt=db_models.F('unit_price'))
        & (Q(promo_starts_at__isnull=True) | Q(promo_starts_at__lte=now))
        & (Q(promo_ends_at__isnull=True) | Q(promo_ends_at__gte=now))
    )
    tienda_stats = {
        'productos': catalogo_base.count(),
        'empresas': catalogo_base.values('company_id').distinct().count(),
        'categorias': catalogo_base.exclude(
            category__isnull=True,
        ).values('category_id').distinct().count(),
        'ofertas': catalogo_base.filter(promo_q).count(),
    }

    productos = catalogo_base
    tab_catalogo = request.GET.get('tab', '').strip()
    if not tab_catalogo:
        if request.GET.get('destacados') == '1':
            tab_catalogo = 'destacados'
        elif request.GET.get('ofertas') == '1':
            tab_catalogo = 'ofertas'
        else:
            tab_catalogo = 'todos'
    orden = request.GET.get('orden', 'nombre').strip() or 'nombre'

    buscar    = request.GET.get('buscar', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    empresa   = request.GET.get('empresa', '').strip()
    vista_tab = request.GET.get('vista', 'categoria').strip() or 'categoria'
    if request.GET.get('verificado') == '1':
        vista_tab = 'empresa'
    if vista_tab not in ('categoria', 'empresa'):
        vista_tab = 'categoria'

    if request.GET.get('verificado') == '1':
        productos = productos.filter(company__is_verified=True)

    if tab_catalogo == 'ofertas':
        productos = productos.filter(promo_q)
    elif tab_catalogo == 'bestsellers':
        ids = [p.pk for p in merch.bestsellers(48)]
        if ids:
            productos = productos.filter(pk__in=ids)
        else:
            productos = productos.filter(is_bestseller=True)
    elif tab_catalogo == 'destacados':
        productos = productos.filter(is_featured=True)

    from django.db.models import Case, When, DecimalField, F

    productos = productos.annotate(
        sort_price=Case(
            When(
                promo_price__isnull=False,
                promo_price__lt=F('unit_price'),
                then=F('promo_price'),
            ),
            default=F('unit_price'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )
    orden_map = {
        'precio_asc': 'sort_price',
        'precio_desc': '-sort_price',
        'nombre': 'name',
        'novedades': '-created_at',
    }
    orden_key = orden if orden in orden_map else 'nombre'
    if orden_key == 'nombre':
        from .utils.ads_ranking import annotate_sponsored_score

        productos = annotate_sponsored_score(productos).order_by('-sponsored_score', 'name')
    else:
        productos = productos.order_by(orden_map[orden_key])

    promo_banner = merch.active_home_sections()
    promo_banner = next(
        (s for s in promo_banner if s.section_type == 'seasonal_banner'),
        None,
    )

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

    show_spotlights = (
        vista_tab == 'categoria'
        and tab_catalogo == 'todos'
        and not buscar
        and not categoria
        and not empresa
    )
    if show_spotlights:
        spotlight_ofertas = merch.daily_deals(4)
        spotlight_bestsellers = merch.bestsellers(4)
        spotlight_destacados = merch.featured_products(4)
    else:
        spotlight_ofertas = []
        spotlight_bestsellers = []
        spotlight_destacados = []

    paginator = Paginator(productos, 12)
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
    if request.GET.get('verificado') == '1':
        empresas_catalogo = empresas_catalogo.filter(is_verified=True)
    empresas_filtro = empresas_catalogo

    qcopy = request.GET.copy()
    qcopy.pop('page', None)
    if tab_catalogo and tab_catalogo != 'todos':
        qcopy['tab'] = tab_catalogo
    if orden and orden != 'nombre':
        qcopy['orden'] = orden
    if categoria:
        qcopy['categoria'] = categoria
    if empresa:
        qcopy['empresa'] = empresa
    if buscar:
        qcopy['buscar'] = buscar
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

    empresas = empresas_filtro

    context = {
        'productos': page_obj,
        'categorias': categorias,
        'empresas': empresas,
        'empresas_catalogo': empresas_catalogo,
        'empresas_filtro': empresas_filtro,
        'buscar': buscar,
        'cat_activa': categoria,
        'emp_activa': empresa,
        'empresa_activa': empresa,
        'vista_tab': vista_tab,
        'tienda_params': tienda_params,
        'url_tab_categoria': url_tab_categoria,
        'url_tab_empresa': url_tab_empresa,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'TradeFlow store',
        'nav_activo': 'tienda',
        'tab_catalogo': tab_catalogo,
        'orden_activo': orden,
        'promo_banner': promo_banner,
        'show_cart_actions': show_cart_actions,
        'is_guest_catalog': is_guest,
        'tienda_stats': tienda_stats,
        'tab_urls': {
            'todos': _tienda_tab_url('todos'),
            'ofertas': _tienda_tab_url('ofertas'),
            'bestsellers': _tienda_tab_url('bestsellers'),
            'destacados': _tienda_tab_url('destacados'),
        },
        'show_spotlights': show_spotlights,
        'spotlight_ofertas': spotlight_ofertas,
        'spotlight_bestsellers': spotlight_bestsellers,
        'spotlight_destacados': spotlight_destacados,
        'productos_promo': merch.daily_deals(8),
        'tienda_pagination_slots': _tienda_pagination_slots(page_obj),
        'category_spotlights': merch.category_spotlights(4, 4),
        'buyer_store_landing': (
            not buscar
            and not categoria
            and not empresa
            and tab_catalogo in ('todos', '')
            and int(request.GET.get('page', 1) or 1) == 1
        ),
    }
    is_partial = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.GET.get('partial') == '1'
    )
    if is_partial:
        return render(request, 'core/tienda_catalog_partial.html', context)
    return render(request, 'core/tienda.html', context)


@catalog_access
def catalogo_producto_detail(request, pk):
    """Vista pública de detalle de producto (sin login requerido)."""
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
    show_cart_actions = (
        not is_guest
        and (role in ('buyer', 'admin') or request.user.is_superuser)
    )

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
    export_ready = bool(
        company.is_verified
        and (company.ruc or product.sku)
    )
    if product.available_qty <= 0:
        stock_status = 'out'
        stock_label = 'Out of stock'
    elif product.available_qty <= 5:
        stock_status = 'low'
        stock_label = f'Low stock ({product.available_qty} units)'
    else:
        stock_status = 'ok'
        stock_label = f'In stock ({product.available_qty} units)'

    img = product_image_url(product)
    if img:
        og_image = img if img.startswith('http') else request.build_absolute_uri(img)
    else:
        og_image = request.build_absolute_uri(static('images/placeholder-producto.svg'))

    meta_description = (
        product.description[:155].strip()
        if product.description
        else f'{product.name} from {company.name} in the Colón Free Zone — TradeFlow Colón.'
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
            'export_ready': export_ready,
            'stock_status': stock_status,
            'stock_label': stock_label,
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
        msg = _('Quantity must be at least 1.')
        if _request_wants_json(request):
            return JsonResponse({'ok': False, 'message': msg}, status=400)
        messages.error(request, msg)
        return redirect('tienda')

    if disponible == 0:
        msg = _('"%(name)s" has no stock available.') % {'name': producto.name}
        if _request_wants_json(request):
            return JsonResponse({'ok': False, 'message': msg}, status=400)
        messages.error(request, msg)
        return redirect('tienda')

    # Actualizar carrito en sesión
    carrito     = _get_carrito(request)
    producto_key = str(producto_id)

    if producto_key in carrito:
        # El producto ya está en el carrito — sumar cantidades
        nueva_cantidad = carrito[producto_key]['cantidad'] + cantidad
        if nueva_cantidad > disponible:
            warn_msg = _('Only %(qty)s units available for "%(name)s".') % {
                'qty': disponible,
                'name': producto.name,
            }
            if _request_wants_json(request):
                pass
            else:
                messages.warning(request, warn_msg)
            nueva_cantidad = disponible
        carrito[producto_key]['cantidad'] = nueva_cantidad
        carrito[producto_key]['subtotal'] = str(
            Decimal(carrito[producto_key]['precio']) * nueva_cantidad
        )
    else:
        # Producto nuevo en el carrito
        if cantidad > disponible:
            cantidad = disponible
            if not _request_wants_json(request):
                messages.warning(
                    request,
                    _('Only %(qty)s units available. Quantity was adjusted.') % {
                        'qty': disponible,
                    },
                )
        carrito[producto_key] = {
            'nombre':   producto.name,
            'precio':   str(producto.unit_price),
            'cantidad': cantidad,
            'subtotal': str(producto.unit_price * cantidad),
            'imagen':   product_image_url(producto) or '',
        }

    _save_carrito(request, carrito)
    ok_msg = _('"%(name)s" added to cart.') % {'name': producto.name}
    if _request_wants_json(request):
        return JsonResponse({
            'ok': True,
            'message': ok_msg,
            'carrito_count': _contar_items(carrito),
            'producto_id': producto_id,
            'cantidad_en_carrito': carrito[producto_key]['cantidad'],
        })
    messages.success(request, ok_msg)
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
        'titulo_pagina': 'My cart',
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
        messages.warning(request, 'Your cart is empty.')
        return redirect('tienda')

    subtotal = _calcular_total(carrito)

    transportistas = TransportCarrier.objects.filter(is_active=True).order_by('sort_order', 'name')
    auto_approve = getattr(settings, 'CHECKOUT_AUTO_APPROVE', False)

    if request.method == 'POST':
        notas = request.POST.get('notas', '').strip()
        carrier_id = request.POST.get('transport_carrier', '').strip()
        lat_raw = request.POST.get('buyer_latitude', '').strip()
        lng_raw = request.POST.get('buyer_longitude', '').strip()

        if not carrier_id:
            messages.error(request, _('Select a carrier to continue.'))
            return redirect('checkout')

        carrier = get_object_or_404(TransportCarrier, pk=carrier_id, is_active=True)

        try:
            buyer_lat = Decimal(lat_raw)
            buyer_lng = Decimal(lng_raw)
        except (InvalidOperation, ValueError):
            messages.error(
                request,
                _('Confirm your location with the Use my current location button.'),
            )
            return redirect('checkout')

        if not (-90 <= float(buyer_lat) <= 90 and -180 <= float(buyer_lng) <= 180):
            messages.error(request, _('Invalid location coordinates.'))
            return redirect('checkout')

        shipping_cost = carrier.base_shipping_cost

        orden = Order.objects.create(
            buyer=request.user,
            order_type='b2c',
            shipping_cost=shipping_cost,
            notes=notas,
            status='pending',
            transport_carrier=carrier,
            buyer_latitude=buyer_lat,
            buyer_longitude=buyer_lng,
            buyer_location_verified_at=timezone.now(),
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
                        f'Insufficient stock for "{producto.name}" — item skipped.'
                    )

            except Product.DoesNotExist:
                # El producto fue desactivado entre que se agregó y el checkout
                messages.warning(
                    request,
                    f'A product is no longer available and was skipped.'
                )

        if items_creados == 0:
            # Ningún item pudo procesarse — cancelar la orden
            orden.delete()
            messages.error(
                request,
                'Could not complete the order. Check product stock.'
            )
            return redirect('ver_carrito')

        orden.recalculate_totals()
        orden.shipping_cost = shipping_cost
        orden.total = orden.subtotal + shipping_cost
        orden.save(update_fields=['shipping_cost', 'total'])

        first_item = orden.items.select_related('product__company').first()
        confirming = first_item.product.company if first_item else None
        orden.confirming_company = confirming
        if confirming and not auto_approve:
            horas = getattr(confirming, 'order_confirm_hours', None) or 48
            orden.tiempo_confirmacion_horas = horas
            orden.seller_confirm_by = seller_confirm_deadline(confirming)
            orden.status = 'awaiting_seller'
            orden.seller_confirmation_status = 'pending'
            orden.save(update_fields=[
                'confirming_company', 'seller_confirm_by', 'tiempo_confirmacion_horas',
                'status', 'seller_confirmation_status', 'updated_at',
            ])
            Payment.objects.create(
                order=orden,
                provider='mock',
                status='pending',
                amount=orden.total,
                currency='USD',
            )
            _save_carrito(request, {})
            messages.success(
                request,
                _(
                    'Order %(num)s submitted. Awaiting company confirmation '
                    '(deadline %(fecha)s).'
                ) % {
                    'num': orden.order_number,
                    'fecha': orden.seller_confirm_by.strftime('%d/%m/%Y %H:%M'),
                },
            )
            try:
                enviar_cambio_estado(orden, 'pending')
                enviar_orden_pendiente_vendedor(orden)
            except Exception:
                log.exception('Email orden pendiente vendedor')
            from .models import Transportista
            if Transportista.objects.filter(estado='aprobado', activo=True).exists():
                return redirect('seleccionar_transportista', order_pk=orden.pk)
            return redirect('detalle_mi_orden', pk=orden.pk)

        Payment.objects.create(
            order=orden,
            provider='mock',
            status='approved',
            amount=orden.total,
            currency='USD',
            paid_at=timezone.now(),
            txn_ref=f'TF-MOCK-{orden.order_number}',
        )
        orden.status = 'paid'
        orden.seller_confirmation_status = 'accepted'
        orden.save(update_fields=['status', 'seller_confirmation_status'])

        _save_carrito(request, {})
        messages.success(
            request,
            _('Order %(num)s created successfully.') % {'num': orden.order_number},
        )
        try:
            enviar_confirmacion_orden(orden)
        except Exception:
            log.exception('No se pudo enviar email de confirmación de orden.')
        from .models import Transportista
        if Transportista.objects.filter(estado='aprobado', activo=True).exists():
            return redirect('seleccionar_transportista', order_pk=orden.pk)
        return redirect('detalle_mi_orden', pk=orden.pk)

    if not transportistas.exists():
        TransportCarrier.objects.get_or_create(
            code='zlc-express',
            defaults={
                'name': 'ZLC Express',
                'description': 'Colón Free Zone transport',
                'sort_order': 1,
                'base_shipping_cost': Decimal('15.00'),
            },
        )
        transportistas = TransportCarrier.objects.filter(is_active=True).order_by('sort_order', 'name')

    context = {
        'carrito': carrito,
        'subtotal': subtotal,
        'carrito_count': _contar_items(carrito),
        'titulo_pagina': 'Confirm order',
        'nav_activo': 'tienda',
        'transportistas': transportistas,
        'checkout_auto_approve': auto_approve,
    }
    return render(request, 'core/checkout.html', context)


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
        'titulo_pagina':  'My orders',
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
        'titulo_pagina': f'Order {orden.order_number}',
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


@login_required
def descargar_packing_list(request, orden_pk):
    """
    Descarga el packing list PDF de una orden.

    Mismas reglas de acceso que descargar_factura.
    """
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
    """
    Descarga la cotización formal en PDF (solo el comprador titular).
    """
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
    """Normaliza un nombre para comparar 'el mismo producto' entre empresas.

    Minúsculas, sin acentos y con espacios colapsados, de modo que
    'Café Premium' y 'cafe  premium' se consideren equivalentes.
    """
    base = (texto or '').strip().lower()
    base = ''.join(
        c for c in unicodedata.normalize('NFKD', base)
        if not unicodedata.combining(c)
    )
    return ' '.join(base.split())


def _empresas_con_producto(base_product, limite=25):
    """Devuelve [(company, product)] de empresas que venden el mismo producto.

    Como cada Product pertenece a una sola Company y no hay catálogo
    compartido, "el mismo producto" se determina por nombre normalizado o
    por SKU exacto. Se elige, por empresa, el producto activo más barato.
    """
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
    """Cotización automática: toda empresa que venda el producto responde sola.

    A partir de un producto base, busca el mismo producto en todas las
    empresas y crea una cotización ya respondida (estado='respondida') por
    cada empresa, con el precio de catálogo vigente. El comprador las compara
    al instante en lugar de esperar respuestas manuales.
    """
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
        return redirect('tienda')

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
    """Comparativa de las cotizaciones automáticas creadas en un mismo lote."""
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
        'titulo_pagina': 'My quotes',
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
                    order_type='b2c',
                    shipping_cost=Decimal('0.00'),
                    notes=f'Generated from quote {cot.numero}',
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

            messages.success(request, f'Order {orden.order_number} created from the quote.')
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


@seller_required
def seller_cotizaciones(request):
    """Pipeline Kanban + stats de cotizaciones del vendedor."""
    company, resp = _seller_company_or_response(request, 'seller_cotizaciones')
    if resp:
        return resp

    from .utils.seller_analytics import (
        cotizacion_monto_estimado,
        seller_quotes_dashboard,
    )

    dash = seller_quotes_dashboard(company)
    lista = dash['lista'].annotate(n_items=Count('items'))

    cot_rows = []
    for cot in lista[:50]:
        cot_rows.append({
            'obj': cot,
            'monto': cotizacion_monto_estimado(cot),
        })

    context = {
        'company': company,
        'cotizaciones': lista,
        'cot_rows': cot_rows,
        'kanban': dash['kanban'],
        'cotizaciones_mes': dash['cotizaciones_mes'],
        'tasa_conversion': dash['tasa_conversion'],
        'monto_cotizado': dash['monto_cotizado'],
        'titulo_pagina': 'Received quotes',
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
            messages.warning(request, 'This quote no longer accepts changes.')
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
                        messages.error(request, f'Invalid price on line: {it.product.name}')
                        return redirect('seller_responder_cotizacion', pk=cot.pk)
                    it.save(update_fields=['precio_ofertado'])
            cot.notas_seller = notas_seller
            if items_list and all(x.precio_ofertado is not None for x in items_list):
                cot.estado = 'respondida'
            cot.save(update_fields=['notas_seller', 'estado', 'updated_at'])

        messages.success(request, 'Quote updated.')
        return redirect('seller_cotizaciones')

    context = {
        'company': company,
        'cot': cot,
        'titulo_pagina': f'Respond to {cot.numero}',
        'nav_activo': 'seller_cotizaciones',
    }
    return render(request, 'core/seller_responder_cotizacion.html', context)


# =============================================================================
# SOLICITUD DE ACCESO (PreExpo / inversores)
# =============================================================================

def solicitud_acceso(request):
    """Formulario público de solicitud de acceso a TradeFlow."""
    plan_intent = request.GET.get('plan', '').strip().lower()
    if plan_intent == 'enterprise':
        plan_intent = 'ecosistema_enterprise'

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'buyer')
        company_name = request.POST.get('company_name', '').strip()
        message = request.POST.get('message', '').strip()
        req_plan = request.POST.get('requested_plan_slug', '').strip() or plan_intent

        if not full_name or not email:
            messages.error(request, _('Name and email are required.'))
        elif role not in ('buyer', 'seller'):
            messages.error(request, _('Invalid role.'))
        else:
            existing = UserApplication.objects.filter(
                email__iexact=email,
                status='pending',
            ).first()
            if existing:
                messages.info(
                    request,
                    _(
                        'You already have an application under review. '
                        'We will email you when it is approved.'
                    ),
                )
                if request.user.is_authenticated:
                    return redirect('onboarding_espera_aprobacion')
                return redirect('solicitud_acceso')

            app = UserApplication.objects.create(
                full_name=full_name,
                email=email,
                phone=phone,
                role=role,
                company_name=company_name,
                message=message,
                requested_plan_slug=req_plan[:40],
            )
            company_owner = _get_seller_company(request.user) if request.user.is_authenticated else None
            if req_plan == 'ecosistema_enterprise' and company_owner:
                from .utils.saas_billing import create_enterprise_commercial_request

                create_enterprise_commercial_request(
                    company_owner,
                    contact_name=full_name,
                    contact_email=email,
                    message=message,
                    user_application=app,
                )
            try:
                enviar_solicitud_recibida(app)
                enviar_solicitud_a_revisores(app)
            except Exception:
                log.exception('Email solicitud acceso')
                messages.warning(
                    request,
                    _(
                        'Application saved, but email could not be sent. '
                        'Configure RESEND_API_KEY and verify sender domain in Resend.'
                    ),
                )
            else:
                messages.success(
                    request,
                    _('Application submitted. Check your email for confirmation.'),
                )
            if request.user.is_authenticated:
                return redirect('onboarding_espera_aprobacion')
            return redirect('onboarding_solicitud_enviada')

    return render(request, 'core/solicitud_acceso.html', {
        'titulo_pagina': _('Access application'),
        'plan_intent': plan_intent,
        'is_enterprise_intent': plan_intent == 'ecosistema_enterprise',
    })


def revisar_solicitud(request, token, accion):
    """Aprueba o rechaza solicitud desde enlace del correo."""
    app = get_object_or_404(UserApplication, review_token=token)
    if app.status not in ('pending',):
        messages.info(request, _('This application has already been reviewed.'))
        return redirect('home')

    if accion == 'aprobar':
        aprobada = True
    elif accion == 'rechazar':
        aprobada = False
    else:
        raise Http404

    if aprobada and app.requested_plan_slug == 'ecosistema_enterprise':
        from .models import Company
        from .utils.saas_billing import approve_commercial_request

        company = Company.objects.filter(owner__email__iexact=app.email).first()
        if company:
            pending = company.plan_commercial_requests.filter(
                status__in=('pending', 'en_revision'),
                requested_plan__slug='ecosistema_enterprise',
            ).order_by('-created_at').first()
            if pending:
                approve_commercial_request(pending)
            else:
                from .utils.saas_billing import activate_company_plan

                try:
                    activate_company_plan(
                        company,
                        'ecosistema_enterprise',
                        source='commercial',
                        notes=f'user_application:{app.pk}',
                    )
                except ValueError:
                    log.exception('Enterprise activation on approve')

    from .utils.application_review import (
        aprobar_solicitud,
        mensaje_fallo_correo,
        rechazar_solicitud,
    )
    if aprobada:
        _, email_result = aprobar_solicitud(app, notificar=True)
    else:
        _, email_result = rechazar_solicitud(app, notificar=True)

    warn = mensaje_fallo_correo(email_result)
    if warn:
        messages.warning(request, warn)
    else:
        messages.success(request, _('Decision recorded and email sent to the applicant.'))
    return redirect('home')


@admin_required
def admin_saas_dashboard(request):
    """Panel React de planes SaaS, empresas e IA predictiva (admin)."""
    import logging

    log = logging.getLogger('tradeflow.saas')
    ctx = {'nav_activo': 'saas', 'saas_preview': None, 'saas_plans_count': 0}
    ctx['api_admin_saas_stats_url'] = reverse('api_admin_saas_stats')

    try:
        from core.enterprise_models import SaasPlan
        from core.utils.saas_admin_metrics import build_saas_admin_payload
        from core.utils.saas_platform import bootstrap_saas_datastore

        health = bootstrap_saas_datastore(seed_subscriptions=False)
        ctx['saas_plans_count'] = health.get('plans_count', 0)
        if health.get('ok'):
            ctx['saas_preview'] = build_saas_admin_payload()
        else:
            log.warning('admin_saas_dashboard health issues: %s', health.get('issues'))
    except Exception as exc:
        log.error('admin_saas_dashboard preview_failed: %s', exc, exc_info=True)

    log.info(
        'admin_saas_dashboard render plans=%s preview=%s',
        ctx['saas_plans_count'],
        bool(ctx['saas_preview']),
    )
    return render(request, 'core/admin_saas_dashboard.html', ctx)


@admin_required
def api_admin_saas_stats(request):
    """JSON agregado desde Supabase/ORM para el dashboard admin SaaS."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    from .utils.saas_admin_metrics import build_saas_admin_payload

    return JsonResponse(build_saas_admin_payload(), encoder=DjangoJSONEncoder)


@admin_required
def api_admin_saas_request_action(request, pk: int):
    """Aprueba o rechaza solicitud comercial de plan (POST)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    import json

    from .enterprise_models import CompanyPlanCommercialRequest
    from .utils.saas_billing import approve_commercial_request, reject_commercial_request

    try:
        body = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        body = {}
    action = (body.get('action') or request.POST.get('action') or '').strip().lower()

    req = CompanyPlanCommercialRequest.objects.filter(pk=pk).select_related(
        'company', 'requested_plan'
    ).first()
    if not req:
        return JsonResponse({'error': 'Application not found'}, status=404)
    if req.status not in ('pending', 'en_revision'):
        return JsonResponse({'error': 'Application has already been processed'}, status=400)

    if action == 'approve':
        approve_commercial_request(req)
        return JsonResponse({
            'ok': True,
            'status': 'approved',
            'message': f'Plan {req.requested_plan.name} activado para {req.company.name}.',
        })
    if action == 'reject':
        reject_commercial_request(req)
        return JsonResponse({
            'ok': True,
            'status': 'rejected',
            'message': f'Application from {req.company.name} rejected.',
        })
    return JsonResponse({'error': 'Invalid action'}, status=400)


# ── Application approval views ────────────────────────────────────────────────

def pending_approval_view(request):
    """Page shown after signup while account is pending admin approval."""
    return render(request, 'core/pending_approval.html')


@admin_required
def admin_applications_view(request):
    """Admin panel to review company access applications."""
    try:
        from .models import UserApplication
        status_filter = request.GET.get('status', '')
        applications = UserApplication.objects.all().order_by('-created_at')
        if status_filter:
            applications = applications.filter(status=status_filter)
        pending_count = UserApplication.objects.filter(status='pending').count()
        return render(request, 'core/admin_applications.html', {
            'applications': applications,
            'pending_count': pending_count,
            'current_filter': status_filter,
            'nav_activo': 'admin_applications',
        })
    except Exception as e:
        log.exception('Error in admin_applications_view: %s', e)
        raise


@admin_required
def approve_application_view(request, pk):
    """Approve a company application, activate the account and notify the user."""
    from .models import UserApplication
    from .utils.application_review import aprobar_solicitud, mensaje_fallo_correo
    if request.method == 'POST':
        try:
            app = UserApplication.objects.get(pk=pk)
            _, email_result = aprobar_solicitud(app, notificar=True)
            warn = mensaje_fallo_correo(email_result)
            if warn:
                messages.warning(request, warn)
            else:
                messages.success(
                    request,
                    'Application approved. The applicant has been notified by email.',
                )
        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')
    return redirect('admin_applications')


@admin_required
def reject_application_view(request, pk):
    """Reject a company application and notify the user."""
    from .models import UserApplication
    from .utils.application_review import mensaje_fallo_correo, rechazar_solicitud
    if request.method == 'POST':
        try:
            app = UserApplication.objects.get(pk=pk)
            _, email_result = rechazar_solicitud(app, notificar=True)
            warn = mensaje_fallo_correo(email_result)
            if warn:
                messages.warning(request, warn)
            else:
                messages.success(
                    request,
                    'Application rejected. The applicant has been notified by email.',
                )
        except UserApplication.DoesNotExist:
            messages.error(request, 'Application not found.')
    return redirect('admin_applications')


# =============================================================================
# PÁGINAS LEGALES (públicas)
# =============================================================================

def legal_terminos(request):
    """Terms of Use for the TradeFlow Colón marketplace."""
    return render(request, 'core/legal_terminos.html')


def legal_privacidad(request):
    """Privacy policy and data processing."""
    return render(request, 'core/legal_privacidad.html')


def legal_cookies(request):
    """Cookie policy and similar technologies."""
    return render(request, 'core/legal_cookies.html')
