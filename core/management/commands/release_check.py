"""
Validación pre-deploy: variables críticas, DB, SMTP y storage cloud.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.email_delivery import validate_email_infrastructure
from core.utils.platform_health import platform_health_payload


class Command(BaseCommand):
    help = 'Comprueba que el entorno está listo para release (staging/prod).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--allow-debug',
            action='store_true',
            help='No tratar DEBUG=True como advertencia bloqueante en CI local.',
        )

    def handle(self, *args, **options):
        errors = []
        warnings = validate_email_infrastructure()

        if settings.DEBUG and not options['allow_debug']:
            warnings.append('DEBUG=True (aceptable solo en local).')

        if 'sqlite' in settings.DATABASES['default'].get('ENGINE', ''):
            warnings.append('SQLite activo; producción debe usar DATABASE_URL (Supabase).')

        backend = settings.STORAGES['default']['BACKEND']
        if 'FileSystemStorage' in backend and not settings.DEBUG:
            warnings.append('Media en disco local; configure Supabase Storage para persistencia.')

        required = ['SECRET_KEY', 'PUBLIC_BASE_URL']
        for key in required:
            if not getattr(settings, key, None):
                errors.append(f'Falta {key}')

        backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
        if not settings.DEBUG and not getattr(settings, 'EMAIL_USE_REAL_SMTP', False):
            if not getattr(settings, 'SUPABASE_CONFIGURED', False):
                errors.append(
                    'Configure SUPABASE_SERVICE_KEY o EMAIL_BACKEND SMTP en producción.'
                )

        payload = platform_health_payload()
        if not payload['database']['ok']:
            errors.append(f"DB: {payload['database']['detail']}")

        for w in warnings:
            self.stdout.write(self.style.WARNING(f'  ⚠ {w}'))
        for e in errors:
            self.stdout.write(self.style.ERROR(f'  ✗ {e}'))

        if errors:
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('Release check: OK'))
