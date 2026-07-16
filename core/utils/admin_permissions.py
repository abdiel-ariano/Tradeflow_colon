"""Align Django Admin staff access with TradeFlow ``admin`` profiles.

Operators need ``is_staff`` plus the TradeFlow Administradores group so
CFZ support can review applications and plan checkouts in Admin.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def user_is_tradeflow_admin(user) -> bool:
    """Return True for active staff/superuser with TradeFlow admin role."""
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    if not user.is_staff:
        return False
    try:
        return user.profile.role == 'admin'
    except Exception:
        return False


def ensure_tradeflow_admin_group() -> Group:
    """Ensure Admin group with all ``core`` permissions for CFZ operators."""
    group, _ = Group.objects.get_or_create(name='TradeFlow Administradores')
    perms = Permission.objects.filter(content_type__app_label='core')
    group.permissions.set(perms)
    return group


def sync_user_admin_access(user) -> None:
    """Grant ``is_staff`` and Admin group when profile role is admin.
    
    
    Keeps Django Admin usable for operators without manual permission edits.
    """
    if not hasattr(user, 'profile'):
        return
    if user.profile.role != 'admin':
        return
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    group = ensure_tradeflow_admin_group()
    user.groups.add(group)
