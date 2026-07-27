"""Staff TOTP MFA setup and challenge views."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.utils.saas_demo import user_is_read_only_saas_demo
from core.utils.staff_mfa import (
    SESSION_BACKUP_CODES,
    clear_staff_mfa,
    encrypt_totp_secret,
    generate_backup_codes,
    generate_totp_secret,
    mark_session_mfa_ok,
    provisioning_uri,
    remaining_backup_codes,
    staff_mfa_required,
    store_backup_code_hashes,
    totp_decrypt_broken,
    user_has_staff_totp,
    user_is_staffish,
    user_needs_staff_mfa,
    user_needs_staff_mfa_setup,
    verify_staff_mfa_code,
    verify_totp,
)

log = logging.getLogger('tradeflow.security')


@login_required
@require_http_methods(['GET', 'POST'])
def staff_mfa_verify(request):
    """Challenge page after password login when staff TOTP is enabled."""
    if user_needs_staff_mfa_setup(request.user):
        next_url = request.GET.get('next') or ''
        url = reverse('staff_mfa_setup')
        if next_url.startswith('/') and not next_url.startswith('//'):
            url = f'{url}?next={next_url}'
        return redirect(url)

    if not user_needs_staff_mfa(request.user):
        mark_session_mfa_ok(request)
        return redirect('home')

    if not user_has_staff_totp(request.user):
        return redirect('staff_mfa_setup')

    decrypt_broken = totp_decrypt_broken(request.user)
    backups_left = remaining_backup_codes(request.user.profile)

    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        if verify_staff_mfa_code(request.user, code):
            mark_session_mfa_ok(request)
            if decrypt_broken:
                # Force re-enrollment after SECRET_KEY rotation / corrupt secret.
                clear_staff_mfa(request.user.profile)
                messages.warning(
                    request,
                    'Authenticator secret is invalid (often after SECRET_KEY rotation). '
                    'Set up MFA again. Keep your new backup codes safe.',
                )
                return redirect('staff_mfa_setup')
            messages.success(request, 'Two-factor verification successful.')
            next_url = request.GET.get('next') or request.POST.get('next') or ''
            if next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect('admin:index')
        messages.error(request, 'Invalid authentication or backup code. Try again.')

    return render(request, 'core/staff_mfa_verify.html', {
        'titulo_pagina': 'Two-factor authentication',
        'next': request.GET.get('next', ''),
        'decrypt_broken': decrypt_broken,
        'backups_left': backups_left,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def staff_mfa_setup(request):
    """Enable/disable staff TOTP and show one-time backup codes."""
    if user_is_read_only_saas_demo(request.user):
        request.session.pop('tf_totp_pending', None)
        mark_session_mfa_ok(request)
        messages.info(
            request,
            'This read-only demo account does not configure staff MFA.',
        )
        return redirect('admin_saas_dashboard')

    if not user_is_staffish(request.user):
        messages.error(request, 'Only staff accounts can configure MFA.')
        return redirect('mi_perfil')

    profile = request.user.profile
    pending_secret = request.session.get('tf_totp_pending')
    required = staff_mfa_required()
    once_codes = request.session.pop(SESSION_BACKUP_CODES, None)
    if once_codes is not None:
        request.session.modified = True

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
            import pyotp
            if not pyotp.TOTP(secret).verify(code, valid_window=1):
                messages.error(request, 'Code did not match. Scan again and retry.')
                return redirect('staff_mfa_setup')
            plain_backups = generate_backup_codes()
            profile.staff_totp_secret = encrypt_totp_secret(secret)
            profile.staff_totp_enabled = True
            profile.save(update_fields=['staff_totp_secret', 'staff_totp_enabled'])
            store_backup_code_hashes(profile, plain_backups)
            request.session.pop('tf_totp_pending', None)
            request.session[SESSION_BACKUP_CODES] = plain_backups
            request.session.modified = True
            mark_session_mfa_ok(request)
            messages.success(
                request,
                'Authenticator MFA enabled. Save your backup codes now — they are shown only once.',
            )
            return redirect('staff_mfa_setup')

        if action == 'regenerate_backups':
            code = (request.POST.get('code') or '').strip()
            if not profile.staff_totp_enabled or not verify_totp(request.user, code):
                # Backup codes also allowed if TOTP decrypt is broken.
                if not verify_staff_mfa_code(request.user, code):
                    messages.error(request, 'Enter a valid authenticator or backup code.')
                    return redirect('staff_mfa_setup')
            plain_backups = generate_backup_codes()
            store_backup_code_hashes(profile, plain_backups)
            request.session[SESSION_BACKUP_CODES] = plain_backups
            request.session.modified = True
            mark_session_mfa_ok(request)
            messages.success(request, 'New backup codes generated. Save them now.')
            return redirect('staff_mfa_setup')

        if action == 'disable':
            if required:
                messages.error(
                    request,
                    'Staff MFA is required on this environment and cannot be disabled.',
                )
                return redirect('staff_mfa_setup')
            code = (request.POST.get('code') or '').strip()
            if profile.staff_totp_enabled and not verify_staff_mfa_code(request.user, code):
                messages.error(request, 'Enter a valid code to disable MFA.')
                return redirect('staff_mfa_setup')
            clear_staff_mfa(profile)
            request.session.pop('tf_totp_pending', None)
            messages.success(request, 'Authenticator MFA disabled.')
            return redirect('mi_perfil')

    uri = provisioning_uri(request.user, pending_secret) if pending_secret else ''
    return render(request, 'core/staff_mfa_setup.html', {
        'titulo_pagina': 'Staff MFA',
        'enabled': profile.staff_totp_enabled,
        'pending_secret': pending_secret or '',
        'provisioning_uri': uri,
        'mfa_required': required,
        'next': request.GET.get('next', ''),
        'backup_codes_once': once_codes or [],
        'backups_left': remaining_backup_codes(profile),
        'decrypt_broken': totp_decrypt_broken(request.user) if profile.staff_totp_enabled else False,
    })
