"""Helpers for the configured TradeFlow demonstration administrator."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User


def saas_demo_username() -> str:
    """Return the normalized username configured for demonstration access.

    ``SAAS_READ_ONLY_DEMO_USERNAME`` remains as a deployment-compatible
    fallback so existing environments gain full access without an urgent
    configuration migration.
    """
    value = getattr(settings, "SAAS_DEMO_ADMIN_USERNAME", None)
    if value is None:
        value = getattr(settings, "SAAS_READ_ONLY_DEMO_USERNAME", "")
    return str(value).strip().casefold()


def read_only_saas_demo_username() -> str:
    """Return the demo username for backwards-compatible callers."""
    return saas_demo_username()


def _matches_configured_demo(user: User) -> bool:
    """Return whether an authenticated user matches the configured demo."""
    if not user or not getattr(user, "is_authenticated", False):
        return False

    configured_username = saas_demo_username()
    username = str(getattr(user, "username", "")).strip().casefold()
    return bool(configured_username and username == configured_username)


def user_is_demo_admin(user: User) -> bool:
    """Return whether the user is the configured demonstration admin."""
    return _matches_configured_demo(user)


def user_is_expo_demo_admin(user: User) -> bool:
    """Return demo-admin status for backwards-compatible callers."""
    return user_is_demo_admin(user)


def user_is_read_only_saas_demo(user: User) -> bool:
    """Return ``False`` because demonstration administration is writable."""
    return False
