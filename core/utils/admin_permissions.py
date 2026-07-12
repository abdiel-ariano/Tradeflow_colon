"""
Permisos del sitio Django Admin alineados con el rol ``admin`` de TradeFlow.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def user_is_tradeflow_admin(user) -> bool:
    """User is tradeflow admin."""
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
    """Grupo con todos los permisos de ``core`` para operadores TradeFlow."""
    group, _ = Group.objects.get_or_create(name='TradeFlow Administradores')
    perms = Permission.objects.filter(content_type__app_label='core')
    group.permissions.set(perms)
    return group


def sync_user_admin_access(user) -> None:
    """
    Staff + grupo de permisos para usuarios con rol admin en el perfil.
    """
    if not hasattr(user, 'profile'):
        return
    if user.profile.role != 'admin':
        return
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    group = ensure_tradeflow_admin_group()
    user.groups.add(group)
