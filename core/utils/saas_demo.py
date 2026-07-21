"""Helpers for the configured read-only SaaS demonstration account."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User


def read_only_saas_demo_username() -> str:
    """Return the normalized username configured for the SaaS demo."""
    value = getattr(settings, 'SAAS_READ_ONLY_DEMO_USERNAME', '')
    return str(value).strip().casefold()


def user_is_read_only_saas_demo(user: User) -> bool:
    """Return whether the user is the configured read-only demo account."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    configured_username = read_only_saas_demo_username()
    username = str(getattr(user, 'username', '')).strip().casefold()
    return bool(configured_username and username == configured_username)
