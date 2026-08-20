"""Email OTP verification for TradeFlow Colón marketplace access.

Hosts ``verify_otp_view`` (wired as ``verificar_codigo`` from
``core.views`` / ``core.views.auth_session``). Kept in this dedicated
module so OTP/Axes concerns stay separate from the modular
``core.views`` package.

OTP gates checkout, guest-to-buyer cart handoff, and seller portal
entry after signup or OAuth.
"""
from __future__ import annotations

import logging
import re

from axes.decorators import axes_dispatch
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from core.utils.access_gating import normalize_path, safe_intent_next, user_needs_otp_verification
from core.utils.email_config import explain_email_failure
from core.utils.otp_delivery import ensure_otp_sent

from core.utils.email_sender import enviar_bienvenida
from core.utils.otp_axes import (
    otp_axes_is_locked,
    otp_axes_lockout_response,
    otp_axes_record_failure,
    otp_axes_reset,
)
from core.utils.otp_verification import verify_user_otp

log = logging.getLogger('tradeflow.auth')
security_log = logging.getLogger('tradeflow.security')

AUTH_MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'
OTP_CODE_PATTERN = re.compile(r'^\d{6}$')


def _wants_json(request: HttpRequest) -> bool:
    """Return True when the client expects a JSON OTP response."""
    if request.GET.get('format') == 'json':
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


def _redirect_by_role(user) -> str:
    """Pick post-OTP home: admin dashboard, seller portal, or catalog.

    Sellers and buyers may still need company or preference onboarding
    before reaching marketplace routes.
    """
    from django.urls import reverse

    from core.utils.access_gating import buyer_onboarding_redirect_name

    from core.utils.access_gating import b2b_company_onboarding_redirect_name

    company_route = b2b_company_onboarding_redirect_name(user)
    if company_route:
        return reverse(company_route)

    try:
        role = user.profile.role
    except Exception:
        role = 'buyer'
    if role == 'admin' or user.is_superuser:
        return reverse('dashboard')
    if role == 'seller':
        from core.utils.access_gating import seller_onboarding_redirect_name
        seller_route = seller_onboarding_redirect_name(user)
        if seller_route:
            return reverse(seller_route)
        return reverse('portal_seller')
    buyer_route = buyer_onboarding_redirect_name(user)
    if buyer_route:
        return reverse(buyer_route)
    return reverse('catalogo_publico')


def _verify_context(request: HttpRequest) -> dict[str, str]:
    """Build template context for the OTP form (masked email, next)."""
    masked = request.user.email or ''
    if '@' in masked:
        local, domain = masked.split('@', 1)
        if len(local) > 2:
            masked = f'{local[0]}***{local[-1]}@{domain}'
    next_url = safe_intent_next(request)
    verify_for_checkout = bool(
        next_url and normalize_path(next_url.split('?', 1)[0]).startswith('/checkout')
    )
    return {
        'masked_email': masked,
        'next_url': next_url,
        'verify_for_checkout': verify_for_checkout,
    }


def _post_verify_destination(request: HttpRequest, user) -> str:
    """Prefer safe ``?next=``, else role-based marketplace home."""
    next_url = safe_intent_next(request)
    if next_url:
        return next_url
    return _redirect_by_role(user)


def _json_error(error_code: str, detail: str, status: int = 400) -> JsonResponse:
    """Return a structured OTP failure body for AJAX clients."""
    return JsonResponse({'ok': False, 'error': error_code, 'detail': detail}, status=status)


def _email_verification_gate_active(user) -> bool:
    """Return True when OTP is still required for this account."""
    from core.utils.access_gating import email_verification_required

    return email_verification_required(user)


@login_required
@axes_dispatch
@require_http_methods(['GET', 'POST'])
def verify_otp_view(request: HttpRequest) -> HttpResponse:
    """Verify the six-digit email OTP (GET form / POST code).

    Used by marketplace routes named ``verificar_codigo`` and
    ``verify_otp``. Axes locks after repeated failures; a successful
    code is single-use. After verify, users continue to ``?next=``
    (often checkout) or role onboarding / guest catalog.
    """
    if not _email_verification_gate_active(request.user):
        dest = _post_verify_destination(request, request.user)
        if _wants_json(request):
            return JsonResponse({'ok': True, 'redirect': dest})
        return redirect(dest)

    try:
        profile = request.user.profile
    except Exception:
        from core.social_auth import user_needs_oauth_role

        if user_needs_oauth_role(request.user):
            return redirect('oauth_complete_signup')
        if _wants_json(request):
            return _json_error('profile_missing', 'User profile not found.', 400)
        from django.contrib import messages

        messages.error(request, 'Profile not found.')
        return redirect('signup')

    if profile.email_verified:
        dest = _post_verify_destination(request, request.user)
        if _wants_json(request):
            return JsonResponse({'ok': True, 'redirect': dest, 'already_verified': True})
        return redirect(dest)

    username = request.user.username
    if otp_axes_is_locked(request, username):
        security_log.warning('otp_verify_locked user=%s', username)
        return otp_axes_lockout_response(request, username, as_json=_wants_json(request))

    if request.method == 'GET':
        ctx = _verify_context(request)
        ok, status = ensure_otp_sent(request, request.user)
        if ok and status == 'sent':
            from django.contrib import messages

            messages.success(
                request,
                _('We sent a 6-digit code to %(email)s. Check your inbox and spam folder.')
                % {'email': request.user.email},
            )
        elif not ok and status not in ('no_email',):
            from django.contrib import messages

            messages.error(request, explain_email_failure(status))
        return render(request, 'core/verificar_codigo.html', ctx)

    raw = (request.POST.get('codigo') or request.POST.get('code') or '').strip()
    if not OTP_CODE_PATTERN.fullmatch(raw):
        otp_axes_record_failure(request, username)
        if _wants_json(request):
            return _json_error('invalid_format', _('Enter a 6-digit code.'))
        from django.contrib import messages

        messages.error(request, _('Enter a 6-digit code.'))
        return render(request, 'core/verificar_codigo.html', _verify_context(request))

    result = verify_user_otp(request.user, raw)
    if not result.ok:
        failures = otp_axes_record_failure(request, username)
        if otp_axes_is_locked(request, username):
            return otp_axes_lockout_response(request, username, as_json=_wants_json(request))
        detail = result.detail or 'Invalid or expired code.'
        if _wants_json(request):
            return _json_error(
                result.error_code or 'invalid_or_expired',
                detail,
                status=400,
            )
        from django.contrib import messages

        messages.error(request, detail)
        return render(
            request,
            'core/verificar_codigo.html',
            {**_verify_context(request), 'failures': failures},
        )

    otp_axes_reset(username, request)
    login(request, request.user, backend=AUTH_MODEL_BACKEND)

    # Refresh ORM after OTP transaction so access gates see verified state.
    request.user.refresh_from_db()
    try:
        request.user.profile.refresh_from_db()
    except Exception:
        pass

    try:
        enviar_bienvenida(request.user)
    except Exception:
        log.exception('welcome_email_after_otp user_id=%s', request.user.pk)

    dest = _post_verify_destination(request, request.user)
    from core.utils.access_gating import onboarding_redirect_name

    gate = onboarding_redirect_name(request.user, scope='restricted')
    if gate and not safe_intent_next(request):
        from django.urls import reverse

        dest = reverse(gate)

    if _wants_json(request):
        return JsonResponse(
            {
                'ok': True,
                'redirect': dest,
                'role': result.role,
            },
        )

    from django.contrib import messages

    messages.success(request, _('Email verified! You can continue now.'))
    return redirect(dest)
