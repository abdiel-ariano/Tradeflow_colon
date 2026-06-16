"""Verifica que la Edge Function send-transactional-email existe en Supabase."""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.email_edge_probe import edge_function_url, probe_edge_function


class Command(BaseCommand):
    help = 'Comprueba SUPABASE_URL + Edge Function de correo (detecta 404 NOT_FOUND)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-test',
            action='store_true',
            help='Envía un correo de prueba real (no solo probe)',
        )

    def handle(self, *args, **options):
        self.stdout.write('=== TradeFlow — Edge Function de correo ===\n')
        self.stdout.write(f'SUPABASE_URL: {settings.SUPABASE_URL or "(vacío)"}')
        self.stdout.write(f'SUPABASE_EMAIL_FUNCTION: {settings.SUPABASE_EMAIL_FUNCTION}')
        self.stdout.write(f'SUPABASE_EMAIL_ENABLED: {settings.SUPABASE_EMAIL_ENABLED}')
        self.stdout.write(f'URL: {edge_function_url() or "(no construible)"}\n')

        result = probe_edge_function(dry_run=not options['send_test'])

        if result.get('status'):
            self.stdout.write(f'HTTP status: {result["status"]}')
        if result.get('detail'):
            self.stdout.write(f'Respuesta: {result["detail"][:400]}')

        if result.get('ok'):
            self.stdout.write(self.style.SUCCESS('\nOK — la Edge Function responde.'))
            return

        if result.get('hint'):
            self.stdout.write(self.style.WARNING(f'\n→ {result["hint"]}'))
        self.stdout.write(self.style.ERROR('\nFALLO — despliega la función antes de usar correo en Railway.'))
        self.stdout.write(
            '\nOpciones:\n'
            '  1) GitHub → Actions → "Deploy Supabase Edge Functions" → Run workflow\n'
            '     (secrets: SUPABASE_ACCESS_TOKEN, SUPABASE_PROJECT_REF, GMAIL_*)\n'
            '  2) Local: bash scripts/deploy_supabase_email.sh\n'
        )
        raise SystemExit(1)
