"""Alinea el acceso de staff de Django Admin con perfiles ``admin`` de TradeFlow.

Los operadores necesitan ``is_staff`` más el grupo TradeFlow Administradores
para revisar solicitudes y checkouts de planes en la ZLC desde Admin.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def user_is_tradeflow_admin(user) -> bool:
    """Devuelve True para staff/superusuario activo con rol admin de TradeFlow."""
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
    """Asegura el grupo Admin con todos los permisos ``core`` para operadores ZLC."""
    group, _ = Group.objects.get_or_create(name='TradeFlow Administradores')
    perms = Permission.objects.filter(content_type__app_label='core')
    group.permissions.set(perms)
    return group


def sync_user_admin_access(user) -> None:
    """Concede ``is_staff`` y el grupo Admin cuando el perfil tiene rol admin.


    Mantiene Django Admin usable para operadores sin editar permisos a mano.
    """
    if not hasattr(user, 'profile'):
        return
    if user.profile.role != 'admin':
        return
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    group = ensure_tradeflow_admin_group()
    user.groups.add(group)
