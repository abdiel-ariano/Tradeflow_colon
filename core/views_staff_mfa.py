"""Staff TOTP MFA setup and challenge views."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.utils.staff_mfa import (
    encrypt_totp_secret,
    generate_totp_secret,
    mark_session_mfa_ok,
    provisioning_uri,
    user_needs_staff_mfa,
    verify_totp,
)

log = logging.getLogger('tradeflow.security')


def _is_staffish(user) -> bool:
    if user.is_staff or user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role == 'admin')


@login_required
@require_http_methods(['GET', 'POST'])
def staff_mfa_verify(request):
    """Challenge page after password login when staff TOTP is enabled."""
    if not user_needs_staff_mfa(request.user):
        mark_session_mfa_ok(request)
        return redirect('home')

    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        if verify_totp(request.user, code):
            mark_session_mfa_ok(request)
            messages.success(request, 'Two-factor verification successful.')
            next_url = request.GET.get('next') or request.POST.get('next') or ''
            if next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect('dashboard')
        messages.error(request, 'Invalid authentication code. Try again.')

    return render(request, 'core/staff_mfa_verify.html', {
        'titulo_pagina': 'Two-factor authentication',
        'next': request.GET.get('next', ''),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def staff_mfa_setup(request):
    """Enable/disable staff TOTP from My Profile (staff/admin only)."""
    if not _is_staffish(request.user):
        messages.error(request, 'Only staff accounts can configure MFA.')
        return redirect('mi_perfil')

    profile = request.user.profile
    pending_secret = request.session.get('tf_totp_pending')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'start':
            secret = generate_totp_secret()
            request.session['tf_totp_pending'] = secret
            request.session.modified = True
            return redirect('staff_mfa_setup')

        if action == 'confirm':
            secret = request.session.get('tf_totp_pending') or ''
            code = (request.POST.get('code') or '').strip()
            if not secret:
                messages.error(request, 'Start MFA setup again.')
                return redirect('staff_mfa_setup')
            # Temporarily assign for verify helper — use plaintext against pyotp.
            import pyotp
            if not pyotp.TOTP(secret).verify(code, valid_window=1):
                messages.error(request, 'Code did not match. Scan again and retry.')
                return redirect('staff_mfa_setup')
            profile.staff_totp_secret = encrypt_totp_secret(secret)
            profile.staff_totp_enabled = True
            profile.save(update_fields=['staff_totp_secret', 'staff_totp_enabled'])
            request.session.pop('tf_totp_pending', None)
            mark_session_mfa_ok(request)
            messages.success(request, 'Authenticator MFA enabled for your staff account.')
            return redirect('mi_perfil')

        if action == 'disable':
            code = (request.POST.get('code') or '').strip()
            if profile.staff_totp_enabled and not verify_totp(request.user, code):
                messages.error(request, 'Enter a valid code to disable MFA.')
                return redirect('staff_mfa_setup')
            profile.staff_totp_secret = ''
            profile.staff_totp_enabled = False
            profile.save(update_fields=['staff_totp_secret', 'staff_totp_enabled'])
            request.session.pop('tf_totp_pending', None)
            messages.success(request, 'Authenticator MFA disabled.')
            return redirect('mi_perfil')

    uri = provisioning_uri(request.user, pending_secret) if pending_secret else ''
    return render(request, 'core/staff_mfa_setup.html', {
        'titulo_pagina': 'Staff MFA',
        'enabled': profile.staff_totp_enabled,
        'pending_secret': pending_secret or '',
        'provisioning_uri': uri,
    })
