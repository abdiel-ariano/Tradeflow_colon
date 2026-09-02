"""OAuth adapters and helpers for TradeFlow Colón social login.

Google, Microsoft, and LinkedIn authenticate the representative. New
accounts still complete the same B2B company-intent and verification flow as
password signups; OAuth must never recreate the retired consumer application.
"""
from __future__ import annotations

import logging
import re

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

log = logging.getLogger('tradeflow.social_auth')

USERNAME_REGEX = re.compile(r'^[a-zA-Z][a-zA-Z0-9._]{2,29}$')
ALLOWED_OAUTH_PROVIDERS = frozenset({'google', 'microsoft', 'linkedin'})
OAUTH_PROVIDER_ALIASES = {'linkedin': 'linkedin_oauth2'}
B2B_BUSINESS_ROLES = frozenset({'buyer', 'seller', 'both'})


def resolve_oauth_provider(provider: str) -> str:
    """Map a public provider slug to the django-allauth provider id."""
    return OAUTH_PROVIDER_ALIASES.get(provider, provider)


def provider_is_enabled(provider: str) -> bool:
    """Return True when the provider has client_id and secret configured."""
    if provider not in ALLOWED_OAUTH_PROVIDERS:
        return False
    resolved = resolve_oauth_provider(provider)
    providers = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
    app = providers.get(resolved, {}).get('APP', {})
    return bool(app.get('client_id') and app.get('secret'))


def social_auth_enabled() -> bool:
    """Return True when at least one OAuth provider is configured."""
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


def setup_b2b_profile(
    user: User,
    business_role: str,
    phone: str = '',
    *,
    privacy_accepted: bool = False,
) -> None:
    """Create the representative profile used by unified B2B onboarding.

    ``UserProfile.role`` remains a compatibility bridge for the existing
    portals. Company capability and authorization live in
    ``business_role_intent`` plus the company verification/membership models.
    No legacy ``UserApplication`` row is created.
    """
    from core.models import UserProfile

    if business_role not in B2B_BUSINESS_ROLES:
        raise ValueError('Unsupported B2B business role.')
    role = 'buyer' if business_role == 'buyer' else 'seller'

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': role, 'email_verificado': False},
    )
    profile.role = role
    profile.business_role_intent = business_role
    # B2B accounts go to company identity, never consumer preferences.
    profile.onboarding_completed_at = timezone.now()
    if phone:
        profile.phone = phone
    update_fields = [
        'role',
        'business_role_intent',
        'onboarding_completed_at',
    ]
    if phone:
        update_fields.append('phone')
    if privacy_accepted:
        from core.utils.privacy import PRIVACY_POLICY_VERSION

        profile.privacy_accepted_at = timezone.now()
        profile.privacy_policy_version = PRIVACY_POLICY_VERSION
        update_fields.extend(['privacy_accepted_at', 'privacy_policy_version'])
    profile.save(update_fields=update_fields)


def setup_profile_and_application(user: User, role: str, phone: str = '') -> None:
    """Compatibility alias for callers predating unified B2B onboarding."""
    setup_b2b_profile(user, role, phone)


def user_needs_oauth_role(user: User) -> bool:
    """Return True when the user lacks a buyer or seller role."""
    from core.models import UserProfile

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return True
    return profile.role not in ('buyer', 'seller')


def should_auto_activate_user(user: User) -> bool:
    """Allow buyers (or profile-less users) past legacy is_active=False."""
    if not user or not user.pk:
        return False
    try:
        role = user.profile.role
    except Exception:
        return True
    return role in (None, 'buyer')


def activate_user_if_eligible(user: User) -> bool:
    """Set is_active=True for eligible buyers; return whether changed."""
    if user.is_active or not should_auto_activate_user(user):
        return False
    user.is_active = True
    user.save(update_fields=['is_active'])
    log.info('auto_activated_user user_id=%s', user.pk)
    return True


class TradeFlowAccountAdapter(DefaultAccountAdapter):
    """Disable allauth email signup; custom /signup/ owns registration."""

    def is_open_for_signup(self, request):
        """Block allauth-native email signup forms."""
        return False

    def get_signup_redirect_url(self, request):
        """Send users to the TradeFlow custom signup page."""
        return reverse('signup')

    def get_login_redirect_url(self, request):
        """Route OAuth post-login through role-completion when needed."""
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
        """Activate eligible buyers before allauth continues login."""
        activate_user_if_eligible(user)
        if not user.is_active:
            return self.respond_user_inactive(request, user)
        return None

    def respond_user_inactive(self, request, user):
        """Redirect inactive sellers to pending approval, others to post-signup."""
        from django.shortcuts import redirect

        try:
            role = user.profile.role
        except Exception:
            role = None
        if role == 'seller':
            return redirect('pending_approval')
        return redirect('oauth_post_signup')


class TradeFlowSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Customize social login: usernames, roles, and redirect session flags."""

    def pre_social_login(self, request, sociallogin):
        """Reactivate returning accounts without inventing a business role."""
        if not sociallogin.is_existing:
            return
        user = sociallogin.user
        activate_user_if_eligible(user)
        if not user_needs_oauth_role(user):
            return
        request.session['oauth_needs_role'] = user.pk

    def populate_user(self, request, sociallogin, data):
        """Fill username and names from provider payload when missing."""
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
        """Persist OAuth user with unusable password and role application."""
        user = sociallogin.user
        if not user.username and user.email:
            user.username = generate_username_from_email(user.email)
        user.set_unusable_password()
        user = super().save_user(request, sociallogin, form)

        selected_business_role = request.session.pop(
            'oauth_selected_business_role',
            request.session.pop('oauth_signup_role', None),
        )
        request.session.pop('oauth_flow', None)
        if selected_business_role in B2B_BUSINESS_ROLES:
            request.session['oauth_selected_business_role'] = selected_business_role
        if user_needs_oauth_role(user):
            request.session['oauth_needs_role'] = user.pk
        user.is_active = True
        user.save(update_fields=['is_active'])
        return user

    def get_signup_redirect_url(self, request, sociallogin):
        """Send new social signups through post-signup or role completion."""
        if request.session.get('oauth_signup_done'):
            return reverse('oauth_post_signup')
        if request.session.get('oauth_needs_role'):
            return reverse('oauth_complete_signup')
        return super().get_signup_redirect_url(request, sociallogin)

    def get_login_redirect_url(self, request):
        """Honor OAuth session flags before the default login redirect."""
        if request.session.get('oauth_needs_role'):
            return reverse('oauth_complete_signup')
        if request.session.get('oauth_signup_done'):
            return reverse('oauth_post_signup')
        return super().get_login_redirect_url(request)

    def is_open_for_signup(self, request, sociallogin):
        """Allow social signup only when a provider is configured."""
        return social_auth_enabled()
