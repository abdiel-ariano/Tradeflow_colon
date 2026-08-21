"""OAuth entry points and B2B role completion for marketplace auth."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from core.social_auth import (
    ALLOWED_OAUTH_PROVIDERS,
    B2B_BUSINESS_ROLES,
    provider_is_enabled,
    setup_b2b_profile,
    user_needs_oauth_role,
)


def _redirect_to_provider_login(provider: str) -> HttpResponse:
    """Send the browser to allauth's provider login URL."""
    from core.social_auth import resolve_oauth_provider

    return redirect(f'/accounts/{resolve_oauth_provider(provider)}/login/')


def _redirect_with_query(request: HttpRequest, route_name: str) -> HttpResponse:
    """Forward to a TradeFlow named route, preserving the query string."""
    url = reverse(route_name)
    qs = request.META.get('QUERY_STRING', '')
    if qs:
        url = f'{url}?{qs}'
    return redirect(url)


def _store_oauth_next(request: HttpRequest) -> None:
    """Stash a same-origin ``?next=`` for post-OAuth marketplace return."""
    next_url = (request.GET.get('next') or '').strip()
    if next_url.startswith('/') and '://' not in next_url and not next_url.startswith('//'):
        request.session['oauth_next'] = next_url
        request.session.modified = True


@require_GET
def redirect_accounts_inactive(request: HttpRequest) -> HttpResponse:
    """Replace allauth's inactive page with TradeFlow gating."""
    if request.user.is_authenticated:
        from core.social_auth import activate_user_if_eligible

        activate_user_if_eligible(request.user)
        if request.user.is_active:
            return redirect('oauth_post_signup')
        try:
            if request.user.profile.role == 'seller':
                return redirect('pending_approval')
        except Exception:
            pass
        return redirect('oauth_post_signup')
    messages.info(
        request,
        'Inicia sesión de nuevo para continuar con la verificación de email.',
    )
    return redirect('login')


@require_GET
def redirect_accounts_login(request: HttpRequest) -> HttpResponse:
    """Map ``/accounts/login/`` to TradeFlow ``login``."""
    return _redirect_with_query(request, 'login')


@require_GET
def redirect_accounts_signup(request: HttpRequest) -> HttpResponse:
    """Map ``/accounts/signup/`` to the unified TradeFlow signup."""
    return _redirect_with_query(request, 'signup')


@require_GET
def oauth_begin_signup(request: HttpRequest, provider: str) -> HttpResponse:
    """Start OAuth while preserving the selected company capability."""
    if provider not in ALLOWED_OAUTH_PROVIDERS:
        raise Http404
    if not provider_is_enabled(provider):
        messages.error(request, 'El inicio de sesión social no está configurado todavía.')
        return redirect('signup')
    business_role = (
        request.GET.get('business_role')
        or request.GET.get('role')
        or 'both'
    ).strip().lower()
    if business_role not in B2B_BUSINESS_ROLES:
        business_role = 'both'
    request.session['oauth_selected_business_role'] = business_role
    request.session['oauth_flow'] = 'signup'
    request.session.modified = True
    _store_oauth_next(request)
    return _redirect_to_provider_login(provider)


@require_GET
def oauth_begin_login(request: HttpRequest, provider: str) -> HttpResponse:
    """Start OAuth login without inventing a role for a new account."""
    if provider not in ALLOWED_OAUTH_PROVIDERS:
        raise Http404
    if not provider_is_enabled(provider):
        messages.error(request, 'El inicio de sesión social no está configurado todavía.')
        return redirect('login')
    request.session.pop('oauth_signup_role', None)
    request.session.pop('oauth_selected_business_role', None)
    request.session['oauth_flow'] = 'login'
    request.session.modified = True
    _store_oauth_next(request)
    return _redirect_to_provider_login(provider)


@login_required
@require_http_methods(['GET', 'POST'])
def oauth_complete_signup(request: HttpRequest) -> HttpResponse:
    """Collect B2B capability and privacy acceptance after social auth."""
    if not user_needs_oauth_role(request.user):
        request.session.pop('oauth_needs_role', None)
        return redirect('oauth_post_signup')

    selected = request.session.get('oauth_selected_business_role', 'both')
    if selected not in B2B_BUSINESS_ROLES:
        selected = 'both'

    if request.method == 'POST':
        selected = (request.POST.get('business_role') or '').strip().lower()
        accepts_privacy = request.POST.get('accept_privacy') in (
            '1', 'on', 'true', 'yes',
        )
        if selected not in B2B_BUSINESS_ROLES:
            messages.error(request, 'Selecciona cómo usará TradeFlow tu empresa.')
        elif not accepts_privacy:
            messages.error(
                request,
                'Debes aceptar la política de privacidad y los términos para continuar.',
            )
        else:
            setup_b2b_profile(
                request.user,
                selected,
                privacy_accepted=True,
            )
            request.session.pop('oauth_needs_role', None)
            request.session.pop('oauth_selected_business_role', None)
            request.session['oauth_signup_done'] = True
            request.session.modified = True
            return redirect('oauth_post_signup')

    return render(
        request,
        'core/oauth_complete_signup.html',
        {'selected_business_role': selected},
    )


@login_required
@require_GET
def oauth_post_signup(request: HttpRequest) -> HttpResponse:
    """Issue OTP and route the representative to company verification."""
    from django.contrib.auth import login

    from core.utils.access_gating import email_verification_required
    from core.views import AUTH_MODEL_BACKEND
    from core.views_onboarding import finalize_signup_with_otp

    user = request.user
    request.session.pop('oauth_signup_done', None)
    request.session.pop('oauth_needs_role', None)

    if user_needs_oauth_role(user):
        return redirect('oauth_complete_signup')

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])

    login(request, user, backend=AUTH_MODEL_BACKEND)

    if email_verification_required(user):
        return finalize_signup_with_otp(request, user)

    next_url = request.session.pop('oauth_next', None)
    if next_url:
        return redirect(next_url)

    from core.auth_views import _redirect_by_role
    from core.utils.access_gating import onboarding_redirect_name

    gate = onboarding_redirect_name(user, scope='restricted')
    if gate:
        return redirect(gate)

    return redirect(_redirect_by_role(user))
