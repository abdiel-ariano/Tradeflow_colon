"""Diagnóstico de correo: Resend + consola DEBUG."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.email_config import smtp_configured
from core.utils.email_delivery import validate_email_infrastructure


class Command(BaseCommand):
    help = 'Comprueba RESEND_API_KEY y DEFAULT_FROM_EMAIL para envío de correos'

    def handle(self, *args, **options):
        """Handle."""
        env_path = settings.BASE_DIR / '.env'
        self.stdout.write(f'.env existe: {env_path.is_file()} ({env_path})')
        key = (getattr(settings, 'RESEND_API_KEY', '') or '').strip()
        self.stdout.write(
            f'RESEND_API_KEY: {"(configurada)" if key else "(vacía)"}'
        )
        self.stdout.write(f'EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'smtp_configured(): {smtp_configured()}')

        for warning in validate_email_infrastructure():
            self.stdout.write(self.style.WARNING(f'  {warning}'))

        if smtp_configured():
            self.stdout.write(self.style.SUCCESS(
                'OK — Resend (o consola DEBUG) puede enviar correos.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'Configura RESEND_API_KEY=re_... en .env o Railway '
                '(resend.com/api-keys; verifica dominio en Resend → Domains).'
            ))
