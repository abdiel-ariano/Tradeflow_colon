"""Mark demo accounts as email-verified for local login testing.

Default targets demo_buyer, demo_seller, and demo_admin so
REQUIRE_EMAIL_VERIFICATION does not block walkthroughs.

Ops: local DEBUG only. ``--todos`` marks every profile and requires
``--force`` outside DEBUG — never use ``--todos --force`` on production.
"""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.models import UserProfile

DEMO_USERNAMES = ('demo_buyer', 'demo_seller', 'demo_admin')


class Command(BaseCommand):
    """Repair demo profiles blocked by pending email verification.

    By default only updates the three demo usernames. ``--todos`` marks
    all UserProfile rows (DEBUG or ``--force`` required).
    """

    help = (
        'Set email_verificado=True on demo accounts (demo_buyer, demo_seller, '
        'demo_admin). Option --todos for all profiles.'
    )

    def add_arguments(self, parser):
        """Register --todos and --force for bulk verification."""
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Mark all existing profiles as verified.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Allow --todos even when DEBUG is False.',
        )

    def handle(self, *args, **options):
        """Verify demo profiles, or all profiles when --todos is set."""
        marcar_todos = options['todos']
        force = options['force']

        if marcar_todos and not settings.DEBUG and not force:
            raise CommandError(
                'Usar --todos fuera de DEBUG requiere --force explícito. '
                'Solo para entornos de desarrollo controlados.'
            )

        if marcar_todos:
            self.stdout.write(
                self.style.WARNING(
                    'Marcando TODOS los perfiles como email_verificado=True…'
                )
            )
            updated = UserProfile.objects.update(
                email_verificado=True,
                token_verificacion=None,
            )
            self.stdout.write(self.style.SUCCESS(f'  Perfiles actualizados: {updated}'))
            return

        count = 0
        for username in DEMO_USERNAMES:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stdout.write(self.style.WARNING(f'  {username} — no existe'))
                continue
            prof, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'buyer',
                    'email_verificado': True,
                    'token_verificacion': None,
                },
            )
            if not created:
                prof.email_verificado = True
                prof.token_verificacion = None
                prof.save(update_fields=['email_verificado', 'token_verificacion'])
            count += 1
            self.stdout.write(self.style.SUCCESS(f'  {username} — verificado'))

        self.stdout.write(self.style.SUCCESS(f'\nListo: {count} cuenta(s) demo reparada(s).'))
