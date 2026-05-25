"""
Sincroniza permisos Django Admin para usuarios con rol admin en TradeFlow.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.utils.admin_permissions import ensure_tradeflow_admin_group, sync_user_admin_access


class Command(BaseCommand):
    help = 'Asigna is_staff y permisos core a usuarios con perfil role=admin'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Solo este usuario (username Django)',
        )

    def handle(self, *args, **options):
        ensure_tradeflow_admin_group()
        qs = User.objects.select_related('profile')
        username = options.get('username')
        if username:
            qs = qs.filter(username=username)

        updated = 0
        for user in qs:
            try:
                if user.profile.role != 'admin':
                    continue
            except Exception:
                continue
            sync_user_admin_access(user)
            updated += 1
            self.stdout.write(f'  OK: {user.username} (staff + permisos core)')

        if username and updated == 0:
            self.stdout.write(
                self.style.WARNING(
                    f'No se actualizó {username}: no existe o no tiene role=admin en UserProfile.',
                ),
            )
        else:
            self.stdout.write(self.style.SUCCESS(f'Usuarios admin sincronizados: {updated}'))
