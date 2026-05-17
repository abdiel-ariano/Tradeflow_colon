"""
=============================================================================
TRADEFLOW COLÓN — core/management/commands/verificar_cuentas_demo.py
=============================================================================
Marca cuentas demo (y opcionalmente todas) como email verificado para pruebas locales.
=============================================================================
"""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.models import UserProfile

DEMO_USERNAMES = ('demo_buyer', 'demo_seller', 'demo_admin')


class Command(BaseCommand):
    """
    Repara perfiles demo bloqueados por verificación de email pendiente.

    Por defecto solo actualiza demo_buyer, demo_seller y demo_admin.
    Con --todos marca todos los UserProfile (solo en DEBUG o con --force).
    """

    help = (
        'Marca email_verificado=True en cuentas demo (demo_buyer, demo_seller, '
        'demo_admin). Opción --todos para todos los perfiles.'
    )

    def add_arguments(self, parser):
        """Registra --todos y --force."""
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Marcar todos los perfiles existentes como verificados.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Permitir --todos aunque DEBUG sea False.',
        )

    def handle(self, *args, **options):
        """
        Ejecuta la verificación masiva de perfiles.

        Args:
            *args: Argumentos posicionales de Django.
            **options: ``todos``, ``force``.

        Returns:
            None
        """
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
