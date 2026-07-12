"""Verifica que Resend esté configurado para envío de correo."""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Comprueba RESEND_API_KEY y DEFAULT_FROM_EMAIL'

    def handle(self, *args, **options):
        """Handle."""
        key = (getattr(settings, 'RESEND_API_KEY', '') or '').strip()
        from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip()

        self.stdout.write(f'RESEND_API_KEY: {"(ok)" if key else "(vacía)"}')
        self.stdout.write(f'DEFAULT_FROM_EMAIL: {from_email or "(vacío)"}')

        if not key:
            self.stdout.write(self.style.ERROR(
                'RESEND_API_KEY no configurada.\n'
                '  1. Crea una API key en https://resend.com/api-keys\n'
                '  2. Verifica tu dominio en Resend → Domains\n'
                '  3. Pon RESEND_API_KEY=re_... en Railway o .env'
            ))
            return

        if not from_email:
            self.stdout.write(self.style.WARNING(
                'DEFAULT_FROM_EMAIL vacío — Resend puede rechazar el envío.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Resend listo. Prueba: python manage.py verify_integrations --email tu@dominio.com'
            ))
