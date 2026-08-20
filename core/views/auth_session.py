"""Sesión de usuario: login, signup, verificación de email/OTP y perfil."""
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
from django.views.decorators.csrf import ensure_csrf_cookie

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

from .common import (
    AUTH_MODEL_BACKEND,
    EMAIL_REGEX,
    NOMBRE_REGEX,
    USERNAME_REGEX,
    _login_template_context,
    _redirect_by_role,
    _safe_next_url,
    log,
)

@never_cache
@ensure_csrf_cookie
def login_view(request):
    """Authenticate and route by role, OTP gate, or safe ``?next=``.
    
    Protected destinations may force ``verificar_codigo`` before
    checkout or other marketplace routes. ``ensure_csrf_cookie`` keeps
    Expo / CFZ demos from posting a login form without a csrftoken cookie.
    """
    from core.utils.access_gating import user_needs_role_completion

    if request.user.is_authenticated:
        if user_needs_role_completion(request.user):
            return redirect('oauth_complete_signup')
        next_url = _safe_next_url(request)
        if next_url:
            return redirect(next_url)
        return redirect(_redirect_by_role(request.user))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user, backend=AUTH_MODEL_BACKEND)
            messages.success(
                request,
                f'Welcome, {user.first_name or user.username}!',
            )
            from core.utils.staff_mfa import (
                clear_session_mfa,
                user_needs_staff_mfa,
                user_needs_staff_mfa_setup,
            )

            clear_session_mfa(request)
            if user_needs_staff_mfa(user):
                next_url = _safe_next_url(request) or _redirect_by_role(user)
                mfa_name = (
                    'staff_mfa_setup'
                    if user_needs_staff_mfa_setup(user)
                    else 'staff_mfa_verify'
                )
                return redirect(reverse(mfa_name) + f'?next={next_url}')
            # Incomplete OAuth/legacy accounts lack UserProfile — send them to
            # role completion before any base.html shell that used to 500 on
            # request.user.profile.
            if user_needs_role_completion(user):
                return redirect('oauth_complete_signup')
            next_url = _safe_next_url(request)
            if next_url:
                from core.utils.access_gating import is_protected_path, onboarding_redirect_name

                if is_protected_path(next_url):
                    gate_route = onboarding_redirect_name(user, scope='restricted')
                    if gate_route:
                        from urllib.parse import urlencode
                        from core.utils.access_gating import should_inline_verify_at_checkout

                        messages.info(
                            request,
                            _('Verify your email to access checkout and orders.'),
                        )
                        if should_inline_verify_at_checkout(next_url, gate_route):
                            return redirect(next_url)
                        gate_target = reverse(gate_route)
                        if gate_route == 'verificar_codigo':
                            return redirect(f'{gate_target}?{urlencode({"next": next_url})}')
                        return redirect(gate_route)
                return redirect(next_url)
            return redirect(_redirect_by_role(user))
        else:
            messages.error(request, 'Incorrect username or password.')

    return render(request, 'core/login.html', _login_template_context())


def logout_view(request):
    """Log out, flush the session, and return to login."""
    from core.utils.staff_mfa import clear_session_mfa

    clear_session_mfa(request)
    logout(request)
    request.session.flush()
    return redirect('login')


def _process_signup(request, forced_role=None, error_template='core/signup.html'):
    """Create User + UserProfile from signup POST and start OTP.
    
    ``forced_role`` locks buyer or seller signup URLs. On success,
    ``finalize_signup_with_otp`` sends the six-digit code.
    """
    first_name = escape(request.POST.get('first_name', '').strip())
    last_name = escape(request.POST.get('last_name', '').strip())
    username = escape(request.POST.get('username', '').strip())
    email = request.POST.get('email', '').strip()
    phone = escape(request.POST.get('phone', '').strip())
    if forced_role is not None:
        role = forced_role
    else:
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

    accept_privacy = request.POST.get('accept_privacy') in ('1', 'on', 'true', 'yes')
    if not accept_privacy:
        errores.append(
            'You must accept the Privacy Policy, Terms of use, and '
            'Security & Usage Policy to create an account.'
        )

    if errores:
        for error in errores:
            messages.error(request, error)
        return render(request, error_template, signup_ctx)

    if User.objects.filter(username=username).exists():
        messages.error(request, f'Username "{username}" already exists. Choose another.')
        return render(request, error_template, signup_ctx)
    if User.objects.filter(email=email).exists():
        messages.error(request, 'An account with that email already exists.')
        return render(request, error_template, signup_ctx)
    if role not in ('buyer', 'seller'):
        messages.error(request, 'Invalid account type.')
        return render(request, error_template, signup_ctx)

    # Crear usuario
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password1,
        first_name=first_name,
        last_name=last_name,
    )

    from ..models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'role': role,
            'email_verificado': False,
        }
    )
    profile.role = role
    # Compradores nuevos deben completar el wizard de personalización post-registro
    if role == 'buyer':
        profile.onboarding_completed_at = None
    from core.utils.privacy import PRIVACY_POLICY_VERSION
    from django.utils import timezone as _tz
    profile.privacy_accepted_at = _tz.now()
    profile.privacy_policy_version = PRIVACY_POLICY_VERSION
    profile.marketing_opt_in = request.POST.get('marketing_opt_in') in ('1', 'on', 'true', 'yes')
    profile.save()

    # Create application record — buyer and seller start pending until admin review
    from ..models import UserApplication
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

    user.is_active = True
    user.save(update_fields=['is_active'])
    login(request, user, backend=AUTH_MODEL_BACKEND)
    from core.views_onboarding import finalize_signup_with_otp

    return finalize_signup_with_otp(request, user)


@never_cache
def signup_view(request):
    """Legacy ``/signup/`` → Figma buyer signup (seller uses ``/signup/vendedor/``)."""
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        role = (request.POST.get('role') or 'buyer').strip().lower()
        if role == 'seller':
            return redirect('signup_seller')
        return _process_signup(
            request, forced_role='buyer', error_template='core/signup_buyer.html'
        )
    return redirect('signup_buyer')


@never_cache
def signup_buyer_view(request):
    """Buyer-only signup entry before OTP and catalog onboarding."""
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        return _process_signup(request, forced_role='buyer', error_template='core/signup_buyer.html')
    return render(request, 'core/signup_buyer.html', {
        'form_first_name': '', 'form_last_name': '', 'form_email': '', 'form_phone': '',
    })


@never_cache
def signup_seller_view(request):
    """Seller-only signup entry before OTP and company onboarding."""
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        return _process_signup(request, forced_role='seller', error_template='core/signup_seller.html')
    return render(request, 'core/signup_seller.html', {
        'form_first_name': '', 'form_last_name': '', 'form_email': '', 'form_phone': '',
    })


def _redirect_after_email_verified(user):
    """Post-OTP destination by role, including buyer/seller wizards."""
    from django.urls import reverse

    from core.utils.access_gating import buyer_onboarding_redirect_name

    try:
        role = user.profile.role
    except UserProfile.DoesNotExist:
        return redirect('catalogo_publico')
    if user.is_superuser or role == 'admin':
        return redirect('dashboard')
    if role == 'seller':
        return redirect('portal_seller')
    buyer_route = buyer_onboarding_redirect_name(user)
    if buyer_route:
        return redirect(buyer_route)
    return redirect('catalogo_publico')


@login_required
def enviar_codigo(request):
    """Generate a six-digit OTP, email it via Resend, and open the form."""
    from core.auth_views import _email_verification_gate_active
    from core.utils.email_config import explain_email_failure
    from core.utils.otp_delivery import ensure_otp_sent

    if not _email_verification_gate_active(request.user):
        messages.info(request, 'Email verification is disabled in this environment.')
        return redirect('catalogo_publico')

    try:
        profile = request.user.profile
        if profile.email_verified:
            messages.info(request, 'Your email is already verified.')
            return redirect('catalogo_publico')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Profile not found.')
        return redirect('signup')

    if not request.user.email:
        messages.error(request, 'Your account has no email address.')
        return redirect('verificar_codigo')

    ok, status = ensure_otp_sent(request, request.user, force=True)
    if ok:
        messages.success(
            request,
            _('We sent a 6-digit code to %(email)s. Check your inbox and spam folder.')
            % {'email': request.user.email},
        )
    else:
        messages.error(request, explain_email_failure(status))
    from urllib.parse import urlencode

    from core.utils.access_gating import safe_intent_next

    next_url = safe_intent_next(request)
    if next_url:
        return redirect(f"{reverse('verificar_codigo')}?{urlencode({'next': next_url})}")
    return redirect('verificar_codigo')


# Alias legacy (rutas / onboarding anteriores)
enviar_codigo_verificacion = enviar_codigo


# OTP verificación segura — core/auth_views.py (django-axes, anti-replay, EXPO_DEMO_MODE)
from core.auth_views import verify_otp_view as verificar_codigo


def verificar_email(request, token):
    """Activate the account when a legacy email verification token is valid."""
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
    """Resend verification email to the authenticated unverified user."""
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


@never_cache
def reenviar_verificacion_public(request):
    """Resend verification by email without a session (login form)."""
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
    """Show and update the authenticated user profile."""
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

        elif action == 'marketing_prefs':
            profile.marketing_opt_in = request.POST.get('marketing_opt_in') in (
                '1', 'on', 'true', 'yes',
            )
            profile.save(update_fields=['marketing_opt_in'])
            messages.success(request, 'Communication preferences saved.')

        elif action == 'export_data':
            from core.utils.privacy import export_user_json_bytes

            payload = export_user_json_bytes(request.user)
            response = HttpResponse(payload, content_type='application/json')
            response['Content-Disposition'] = (
                f'attachment; filename="tradeflow-data-{request.user.pk}.json"'
            )
            return response

        elif action == 'delete_account':
            confirm = (request.POST.get('confirm_delete') or '').strip().upper()
            if confirm != 'DELETE':
                messages.error(
                    request,
                    'Type DELETE to confirm account anonymization.',
                )
            else:
                from django.contrib.auth import logout as auth_logout

                from core.utils.privacy import anonymize_user

                anonymize_user(request.user)
                auth_logout(request)
                messages.success(
                    request,
                    'Your account has been anonymized and signed out.',
                )
                return redirect('home')

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
