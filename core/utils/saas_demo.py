"""Helpers for the configured TradeFlow SaaS demonstration account."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User


def saas_demo_username() -> str:
    """Return the normalized username configured for the SaaS demo."""
    value = getattr(settings, "SAAS_READ_ONLY_DEMO_USERNAME", "")
    return str(value).strip().casefold()


def read_only_saas_demo_username() -> str:
    """Return the demo username kept for backwards-compatible callers."""
    return saas_demo_username()


def _matches_configured_demo(user: User) -> bool:
    """Return whether an authenticated user matches the configured demo."""
    if not user or not getattr(user, "is_authenticated", False):
        return False

    configured_username = saas_demo_username()
    username = str(getattr(user, "username", "")).strip().casefold()
    return bool(configured_username and username == configured_username)


def user_is_expo_demo_admin(user: User) -> bool:
    """Return whether the configured demo has writable Expo admin access."""
    return bool(
        getattr(settings, "EXPO_DEMO_MODE", False)
        and _matches_configured_demo(user)
    )


def user_is_read_only_saas_demo(user: User) -> bool:
    """Return whether the configured demo must remain strictly read-only."""
    return bool(
        _matches_configured_demo(user)
        and not getattr(settings, "EXPO_DEMO_MODE", False)
    )
