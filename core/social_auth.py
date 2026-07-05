"""
TradeFlow Colón — OAuth helpers (Google / Microsoft via django-allauth).
"""
from __future__ import annotations

import logging
import re

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

log = logging.getLogger('tradeflow.social_auth')

USERNAME_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9._]{2,29}$')
ALLOWED_OAUTH_PROVIDERS = frozenset({'google', 'microsoft'})


def provider_is_enabled(provider: str) -> bool:
    if provider not in ALLOWED_OAUTH_PROVIDERS:
        return False
    providers = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
    app = providers.get(provider, {}).get('APP', {})
    return bool(app.get('client_id') and app.get('secret'))


def social_auth_enabled() -> bool:
    return any(provider_is_enabled(p) for p in ALLOWED_OAUTH_PROVIDERS)


def generate_username_from_email(email: str) -> str:
    """Build a unique username that satisfies USERNAME_REGEX."""
    local = (email or '').split('@')[0].lower()
    cleaned = re.sub(r'[^a-z0-9._]', '', local)
    if not cleaned or not re.match(r'^[a-z]', cleaned):
        cleaned = f'user{cleaned}' if cleaned else 'user'
    base = cleaned[:25]
    candidate = base
    n = 1
    while User.objects.filter(username=candidate).exists():
        suffix = str(n)
        candidate = f'{base[: max(1, 30 - len(suffix))]}{suffix}'
        n += 1
        if n > 9999:
            break
    if not USERNAME_REGEX.match(candidate):
        candidate = f'user{n}'
    return candidate


def setup_profile_and_application(user: User, role: str, phone: str = '') -> None:
    """Mirror signup_view profile + UserApplication creation (no activation)."""
    from core.models import UserApplication, UserProfile

    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': role, 'email_verificado': False},
    )
    profile.role = role
    if phone:
        profile.phone = phone
    # OAuth alta comprador: wizard pendiente solo en perfil recién creado
    if role == 'buyer' and created:
        profile.onboarding_completed_at = None
    update_fields = ['role']
    if phone:
        update_fields.append('phone')
    if role == 'buyer' and created:
        update_fields.append('onboarding_completed_at')
    profile.save(update_fields=update_fields)

    full_name = f'{user.first_name or ""} {user.last_name or ""}'.strip()
    app_status = 'approved' if role == 'buyer' else 'pending'
    UserApplication.objects.get_or_create(
        user=user,
        defaults={
            'full_name': full_name or user.username,
            'email': user.email or '',
            'phone': phone,
            'role': role,
            'company_name': '',
            'message': '',
            'status': app_status,
        },
    )


def user_needs_oauth_role(user: User) -> bool:
    from core.models import UserProfile

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return True
    return profile.role not in ('buyer', 'seller')


def should_auto_activate_user(user: User) -> bool:
    """Compradores (o sin perfil) no quedan bloqueados por is_active=False legacy."""
    if not user or not user.pk:
        return False
    try:
        role = user.profile.role
    except Exception:
        return True
    return role in (None, 'buyer')


def activate_user_if_eligible(user: User) -> bool:
    if user.is_active or not should_auto_activate_user(user):
        return False
    user.is_active = True
    user.save(update_fields=['is_active'])
    log.info('auto_activated_user user_id=%s', user.pk)
    return True


class TradeFlowAccountAdapter(DefaultAccountAdapter):
    """Disable allauth email signup; custom /signup/ handles registration."""

    def is_open_for_signup(self, request):
        return False

    def get_signup_redirect_url(self, request):
        return reverse('signup')

    def get_login_redirect_url(self, request):
        if request.session.get('oauth_needs_role'):
            return reverse('oauth_complete_signup')
        if request.session.get('oauth_signup_done'):
            return reverse('oauth_post_signup')
        return super().get_login_redirect_url(request)

    def pre_login(
        self,
        request,
        user,
        *,
        email_verification=None,
        signal_kwargs=None,
        email=None,
        signup=False,
        redirect_url=None,
    ):
        activate_user_if_eligible(user)
        if not user.is_active:
            return self.respond_user_inactive(request, user)
        return None

    def respond_user_inactive(self, request, user):
        from django.shortcuts import redirect

        try:
            role = user.profile.role
        except Exception:
            role = None
        if role == 'seller':
            return redirect('pending_approval')
        return redirect('oauth_post_signup')


class TradeFlowSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Cuentas OAuth existentes: reactivar compradores y completar perfil."""
        if not sociallogin.is_existing:
            return
        user = sociallogin.user
        activate_user_if_eligible(user)
        if not user_needs_oauth_role(user):
            return
        flow = request.session.get('oauth_flow', 'login')
        if flow == 'login':
            setup_profile_and_application(user, 'buyer')
            request.session['oauth_signup_done'] = True
            request.session.pop('oauth_needs_role', None)
        else:
            request.session['oauth_needs_role'] = user.pk

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        extra = sociallogin.account.extra_data or {}
        email = user.email or data.get('email') or extra.get('email') or ''
        if email and not user.username:
            user.username = generate_username_from_email(email)
        first = (
            data.get('first_name')
            or extra.get('given_name')
            or extra.get('givenName')
            or ''
        )
        last = (
            data.get('last_name')
            or extra.get('family_name')
            or extra.get('surname')
            or ''
        )
        if first:
            user.first_name = str(first)[:50]
        if last:
            user.last_name = str(last)[:50]
        return user

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        if not user.username and user.email:
            user.username = generate_username_from_email(user.email)
        user.set_unusable_password()
        user = super().save_user(request, sociallogin, form)

        role = request.session.pop('oauth_signup_role', None)
        flow = request.session.pop('oauth_flow', None) or 'signup'
        if role in ('buyer', 'seller'):
            setup_profile_and_application(user, role)
            request.session['oauth_signup_done'] = True
            request.session.pop('oauth_needs_role', None)
        elif flow == 'login':
            setup_profile_and_application(user, 'buyer')
            request.session['oauth_signup_done'] = True
            request.session.pop('oauth_needs_role', None)
        elif user_needs_oauth_role(user):
            request.session['oauth_needs_role'] = user.pk
        user.is_active = True
        user.save(update_fields=['is_active'])
        return user

    def get_signup_redirect_url(self, request, sociallogin):
        if request.session.get('oauth_signup_done'):
            return reverse('oauth_post_signup')
        if request.session.get('oauth_needs_role'):
            return reverse('oauth_complete_signup')
        return super().get_signup_redirect_url(request, sociallogin)

    def get_login_redirect_url(self, request):
        if request.session.get('oauth_needs_role'):
            return reverse('oauth_complete_signup')
        if request.session.get('oauth_signup_done'):
            return reverse('oauth_post_signup')
        return super().get_login_redirect_url(request)

    def is_open_for_signup(self, request, sociallogin):
        return social_auth_enabled()
