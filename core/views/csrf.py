"""Friendly CSRF failure handling for marketplace auth forms.

Raw Django 403 pages confuse Expo demos when a stale ``csrftoken`` cookie
or blocked third-party storage aborts login. Redirect back to a safe GET
so the next attempt gets a fresh token.
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.csrf import csrf_failure as django_csrf_failure

log = logging.getLogger('tradeflow.security')

# Paths that should bounce to login (or referer) instead of a bare 403 page.
_AUTH_PATH_MARKERS = (
    '/login',
    '/signup',
    '/registro',
    '/password-reset',
    '/password_reset',
    '/i18n/setlang',
    '/reenviar-verificacion',
    '/verificar',
    '/staff-mfa',
)


def _is_auth_path(path: str) -> bool:
    """Return True when the failed POST looks like an auth/session form."""
    normalized = (path or '').rstrip('/') or '/'
    return any(marker in normalized for marker in _AUTH_PATH_MARKERS)


def csrf_failure(request, reason=''):
    """Log CSRF failures and recover auth POSTs with a refresh message.

    Non-auth endpoints keep Django's default CSRF failure response so API
    clients still see a clear 403.
    """
    path = getattr(request, 'path', '') or ''
    log.warning(
        'CSRF verification failed path=%s method=%s reason=%s',
        path,
        getattr(request, 'method', ''),
        reason or 'unknown',
    )

    if request.method == 'POST' and _is_auth_path(path):
        messages.error(
            request,
            _(
                'Security check expired. Refresh the page and sign in again. '
                'If it keeps failing, clear cookies for this site.'
            ),
        )
        referer = request.META.get('HTTP_REFERER', '')
        if referer and url_has_allowed_host_and_scheme(
            url=referer,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(referer)
        return redirect(reverse('login'))

    return django_csrf_failure(request, reason=reason)
