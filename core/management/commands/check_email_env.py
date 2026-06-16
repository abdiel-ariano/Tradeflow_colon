"""Diagnóstico de correo: Supabase + fallback Django."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.email_config import smtp_configured
from core.utils.email_edge_probe import edge_function_url, probe_edge_function


class Command(BaseCommand):
    help = 'Comprueba Supabase y EMAIL_BACKEND para envío de códigos'

    def handle(self, *args, **options):
        env_path = settings.BASE_DIR / '.env'
        self.stdout.write(f'.env existe: {env_path.is_file()} ({env_path})')
        self.stdout.write(f'SUPABASE_URL: {"(ok)" if settings.SUPABASE_URL else "(vacío)"}')
        self.stdout.write(
            f'SUPABASE_SERVICE_KEY: {"(configurada)" if settings.SUPABASE_SERVICE_KEY else "(vacía)"}'
        )
        self.stdout.write(f'SUPABASE_EMAIL_ENABLED: {settings.SUPABASE_EMAIL_ENABLED}')
        self.stdout.write(f'SUPABASE_EMAIL_FUNCTION: {settings.SUPABASE_EMAIL_FUNCTION}')
        self.stdout.write(f'Edge URL: {edge_function_url() or "(vacío)"}')
        self.stdout.write(f'EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'smtp_configured(): {smtp_configured()}')

        if settings.SUPABASE_CONFIGURED and settings.SUPABASE_EMAIL_ENABLED:
            probe = probe_edge_function(dry_run=True)
            if probe.get('ok') or probe.get('status') == 400:
                self.stdout.write(self.style.SUCCESS('Edge Function: responde (desplegada)'))
            elif probe.get('hint'):
                self.stdout.write(self.style.ERROR(f'Edge Function: {probe["hint"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'Edge Function: {probe.get("detail", "?")[:200]}'))

        if smtp_configured():
            self.stdout.write(self.style.SUCCESS(
                'OK — Supabase y/o Django pueden enviar correos.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'Configura SUPABASE_* o un EMAIL_BACKEND SMTP en .env'
            ))
