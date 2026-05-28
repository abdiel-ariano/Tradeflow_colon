"""Diagnóstico de correo Resend (sin mostrar la API key)."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.email_config import smtp_configured


class Command(BaseCommand):
    help = 'Comprueba configuración Resend / django-anymail'

    def handle(self, *args, **options):
        env_path = settings.BASE_DIR / '.env'
        self.stdout.write(f'.env existe: {env_path.is_file()} ({env_path})')
        key = (getattr(settings, 'ANYMAIL', {}) or {}).get('RESEND_API_KEY', '')
        self.stdout.write(
            f'RESEND_API_KEY: {"(configurada)" if (key or "").strip() else "(vacía)"}'
        )
        self.stdout.write(f'EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'smtp_configured(): {smtp_configured()}')
        if smtp_configured():
            self.stdout.write(self.style.SUCCESS(
                'OK — los correos saldrán por Resend (anymail).'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'Añade RESEND_API_KEY=re_... en .env y reinicia runserver.'
            ))
