"""Diagnóstico rápido de .env / Gmail (sin imprimir contraseñas)."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.email_config import smtp_configured


class Command(BaseCommand):
    help = 'Muestra si Django detecta SMTP Gmail desde .env'

    def handle(self, *args, **options):
        env_file = settings.BASE_DIR / '.env'
        self.stdout.write(f'.env existe: {env_file.is_file()} ({env_file})')
        self.stdout.write(f'EMAIL_HOST_USER: {settings.EMAIL_HOST_USER or "(vacío)"}')
        self.stdout.write(
            f'EMAIL_HOST_PASSWORD: {"(configurada)" if settings.EMAIL_HOST_PASSWORD else "(vacía)"}'
        )
        self.stdout.write(f'EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'EMAIL_SMTP_CONFIGURED: {getattr(settings, "EMAIL_SMTP_CONFIGURED", False)}')
        self.stdout.write(f'smtp_configured(): {smtp_configured()}')
        if smtp_configured():
            self.stdout.write(self.style.SUCCESS('OK — la pantalla de verificación NO debe mostrar aviso amarillo.'))
        else:
            self.stdout.write(
                self.style.ERROR(
                    'Falta Gmail en .env. Ejecuta: python scripts/bootstrap_dotenv.py --force --app-password "..."'
                )
            )
