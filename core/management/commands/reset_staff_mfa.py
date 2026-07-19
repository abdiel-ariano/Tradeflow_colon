"""Clear staff TOTP MFA for a user (recovery after lockout / SECRET_KEY rotation)."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.utils.staff_mfa import clear_staff_mfa, user_is_staffish


class Command(BaseCommand):
    """Reset staff MFA so the user can enroll again at /staff-mfa/setup/."""

    help = (
        'Clear TOTP secret and backup codes for a staff/admin user. '
        'Use when SECRET_KEY rotation broke decrypt and backup codes are exhausted.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            help='Username of the staff/admin account to reset',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip interactive confirmation',
        )

    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.select_related('profile').get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'User "{username}" not found.') from exc

        if not user_is_staffish(user):
            raise CommandError(f'User "{username}" is not staff/admin.')

        profile = user.profile
        if not options['yes']:
            self.stdout.write(
                self.style.WARNING(
                    f'This will clear MFA for {username} '
                    f'(enabled={profile.staff_totp_enabled}).'
                )
            )
            confirm = input('Type yes to continue: ').strip().lower()
            if confirm != 'yes':
                raise CommandError('Aborted.')

        clear_staff_mfa(profile)
        self.stdout.write(
            self.style.SUCCESS(
                f'MFA cleared for {username}. They must enroll again at /staff-mfa/setup/.'
            )
        )
