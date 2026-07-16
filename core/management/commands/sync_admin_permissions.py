"""Sync Django Admin staff flags for TradeFlow admin-role users.

Ops: safe after promoting a UserProfile to role=admin, or in deploy
hooks. Idempotent; may run on production when admin access drifts.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.utils.admin_permissions import ensure_tradeflow_admin_group, sync_user_admin_access


class Command(BaseCommand):
    """Grant is_staff and core.* permissions to role=admin profiles."""

    help = 'Assign is_staff and core permissions to users with profile role=admin'

    def add_arguments(self, parser):
        """Register optional single-username filter."""
        parser.add_argument(
            '--username',
            type=str,
            help='Only this Django username',
        )

    def handle(self, *args, **options):
        """Ensure admin group exists and sync matching admin users."""
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
