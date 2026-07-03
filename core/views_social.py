"""
OAuth entry points and post-signup role completion (/signup/, /login/).
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from core.social_auth import (
    ALLOWED_OAUTH_PROVIDERS,
    provider_is_enabled,
    setup_profile_and_application,
    social_auth_enabled,
    user_needs_oauth_role,
)


def _redirect_to_provider_login(provider: str) -> HttpResponse:
    return redirect(f'/accounts/{provider}/login/')


@require_GET
def oauth_begin_signup(request: HttpRequest, provider: str) -> HttpResponse:
    if provider not in ALLOWED_OAUTH_PROVIDERS:
        raise Http404
    if not provider_is_enabled(provider):
        messages.error(request, 'El inicio de sesión social no está configurado todavía.')
        return redirect('signup')
    role = request.GET.get('role', 'buyer')
    if role not in ('buyer', 'seller'):
        role = 'buyer'
    request.session['oauth_signup_role'] = role
    request.session['oauth_flow'] = 'signup'
    request.session.modified = True
    return _redirect_to_provider_login(provider)


@require_GET
def oauth_begin_login(request: HttpRequest, provider: str) -> HttpResponse:
    if provider not in ALLOWED_OAUTH_PROVIDERS:
        raise Http404
    if not provider_is_enabled(provider):
        messages.error(request, 'El inicio de sesión social no está configurado todavía.')
        return redirect('login')
    request.session.pop('oauth_signup_role', None)
    request.session['oauth_flow'] = 'login'
    request.session.modified = True
    return _redirect_to_provider_login(provider)


@login_required
@require_http_methods(['GET', 'POST'])
def oauth_complete_signup(request: HttpRequest) -> HttpResponse:
    """New OAuth users who started from /login/ must pick buyer/seller."""
    if not user_needs_oauth_role(request.user):
        request.session.pop('oauth_needs_role', None)
        return redirect('oauth_post_signup')

    if request.method == 'POST':
        role = request.POST.get('role', 'buyer')
        if role not in ('buyer', 'seller'):
            role = 'buyer'
        setup_profile_and_application(request.user, role)
        request.session.pop('oauth_needs_role', None)
        request.session['oauth_signup_done'] = True
        request.session.modified = True
        return redirect('oauth_post_signup')

    return render(
        request,
        'core/oauth_complete_signup.html',
        {
            'selected_role': 'buyer',
        },
    )


@login_required
@require_GET
def oauth_post_signup(request: HttpRequest) -> HttpResponse:
    """Activation + OTP redirect — same outcomes as manual signup_view."""
    from django.conf import settings
    from django.contrib.auth import login

    from core.views import AUTH_MODEL_BACKEND
    from core.views_onboarding import finalize_signup_with_otp

    user = request.user
    request.session.pop('oauth_signup_done', None)
    request.session.pop('oauth_needs_role', None)

    if user_needs_oauth_role(user):
        return redirect('oauth_complete_signup')

    if getattr(settings, 'EXPO_DEMO_MODE', False):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
        login(request, user, backend=AUTH_MODEL_BACKEND)
        return finalize_signup_with_otp(request, user)

    user.is_active = False
    user.save(update_fields=['is_active'])
    return redirect('pending_approval')
