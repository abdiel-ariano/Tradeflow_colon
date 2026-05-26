"""
Verifica conexión a Supabase/Postgres, storage cloud y envío Gmail SMTP.

Uso:
  python manage.py verify_integrations
  python manage.py verify_integrations --email tu@gmail.com
  python manage.py verify_integrations --skip-email
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from core.utils.email_delivery import deliver_mail, validate_email_infrastructure
from core.utils.platform_health import platform_health_payload


class Command(BaseCommand):
    help = 'Prueba DATABASE_URL (Supabase), storage y EMAIL (Gmail SMTP).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='',
            help='Correo de prueba (default: EMAIL_HOST_USER)',
        )
        parser.add_argument(
            '--skip-email',
            action='store_true',
            help='Solo probar base de datos y health',
        )

    def handle(self, *args, **options):
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

        if not getattr(settings, 'EMAIL_USE_REAL_SMTP', False):
            self.stdout.write(self.style.WARNING(
                '\nSMTP no activo. Configure uno de:\n'
                '  EMAIL_RESEND_API_KEY=re_...  (Resend, recomendado)\n'
                '  EMAIL_SENDGRID_API_KEY=SG... (SendGrid)\n'
                '  EMAIL_HOST_USER + EMAIL_HOST_PASSWORD (Gmail App Password)\n'
                '  Ver docs/ENTERPRISE_EMAIL.md'
            ))
            return

        to_addr = options['email'] or settings.EMAIL_HOST_USER
        if not to_addr:
            self.stdout.write(self.style.ERROR('  Sin EMAIL_HOST_USER ni --email'))
            raise SystemExit(1)

        base = settings.PUBLIC_BASE_URL.rstrip('/')
        html = (
            f'<p>TradeFlow Colón — prueba SMTP.</p>'
            f'<p><img src="{base}/static/img/logo-icon-color.png" alt="TradeFlow" '
            f'width="80" style="max-height:40px;"></p>'
        )
        try:
            deliver_mail(
                subject='TradeFlow — prueba SMTP',
                message='Si lees esto, Gmail SMTP está configurado correctamente.',
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
            self.stdout.write(self.style.ERROR(f'  Error SMTP: {exc}'))
            self.stdout.write(
                '  Revisa App Password de Google (2FA) y '
                'https://myaccount.google.com/apppasswords'
            )
            raise SystemExit(1) from exc

        self.stdout.write(self.style.SUCCESS('\nVerificación completa: OK'))
