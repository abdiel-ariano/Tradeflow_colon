"""Smoke-test Supabase/Postgres, cloud storage, and Resend delivery.

Ops: safe on staging/production with ``--skip-email``. Sending a real
test message (``--email``) should use a controlled inbox, not customers.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from core.utils.email_delivery import deliver_mail, validate_email_infrastructure
from core.utils.platform_health import platform_health_payload


class Command(BaseCommand):
    """Verify database, media backend, and optional Resend mail path."""

    help = 'Test DATABASE_URL (Supabase), storage, and email (Resend).'

    def add_arguments(self, parser):
        """Register optional test recipient and email skip flag."""
        parser.add_argument(
            '--email',
            type=str,
            default='',
            help='Test recipient (default: DEFAULT_FROM_EMAIL)',
        )
        parser.add_argument(
            '--skip-email',
            action='store_true',
            help='Only test database and health',
        )

    def handle(self, *args, **options):
        """Print integration status and optionally send a Resend probe."""
        self.stdout.write('=== TradeFlow — verificación de integraciones ===\n')

        payload = platform_health_payload()
        engine = settings.DATABASES['default'].get('ENGINE', '')
        self.stdout.write(f'Base de datos: {engine}')
        if payload['database']['ok']:
            self.stdout.write(self.style.SUCCESS(
                f"  Conexión OK ({payload['database']['latency_ms']} ms)"
            ))
        elif 'sqlite' in engine:
            self.stdout.write(self.style.WARNING(
                '  SQLite activo. Para Supabase define DATABASE_URL en .env'
            ))
        else:
            self.stdout.write(self.style.ERROR(f"  Error DB: {payload['database']['detail']}"))
            raise SystemExit(1) from None

        storage = payload['storage']
        self.stdout.write(f"\nStorage: {storage['backend']}")
        if storage['cloud_persistent']:
            self.stdout.write(self.style.SUCCESS('  Supabase Storage configurado'))
        else:
            self.stdout.write(self.style.WARNING(
                '  Media local (MEDIA_ROOT). En producción use SUPABASE_SERVICE_KEY.'
            ))

        for w in validate_email_infrastructure():
            self.stdout.write(self.style.WARNING(f'  Email config: {w}'))

        if options['skip_email']:
            self.stdout.write(self.style.SUCCESS('\nVerificación parcial: OK'))
            return

        if not (getattr(settings, 'RESEND_API_KEY', '') or '').strip() and not settings.DEBUG:
            self.stdout.write(self.style.WARNING(
                '\nEmail no configurado. Añade RESEND_API_KEY=re_... en .env o Railway.'
            ))
            return

        to_addr = options['email'] or settings.DEFAULT_FROM_EMAIL
        if not to_addr:
            self.stdout.write(self.style.ERROR('  Indica --email'))
            raise SystemExit(1)

        base = settings.PUBLIC_BASE_URL.rstrip('/')
        html = (
            f'<p>TradeFlow Colón — prueba Resend.</p>'
            f'<p><img src="{base}/static/img/logo-icon-color.png" alt="TradeFlow" '
            f'width="80" style="max-height:40px;"></p>'
        )
        try:
            deliver_mail(
                subject='TradeFlow — prueba Resend',
                message='Si lees esto, Resend está configurado correctamente.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_addr],
                html_message=html,
                email_type='integration_test',
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(
                f'  Correo de prueba enviado a {to_addr} (registrado en EmailDeliveryLog)'
            ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  Error Resend: {exc}'))
            self.stdout.write(
                '  Revisa RESEND_API_KEY, dominio verificado en Resend → Domains '
                'y que DEFAULT_FROM_EMAIL use ese dominio.'
            )
            raise SystemExit(1) from exc

        self.stdout.write(self.style.SUCCESS('\nVerificación completa: OK'))
