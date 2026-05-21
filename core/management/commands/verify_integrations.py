"""
Verifica conexión a Supabase/Postgres y envío Gmail SMTP.

Uso:
  python manage.py verify_integrations
  python manage.py verify_integrations --email tu@gmail.com
"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Prueba DATABASE_URL (Supabase) y EMAIL (Gmail SMTP).'

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
            help='Solo probar base de datos',
        )

    def handle(self, *args, **options):
        self.stdout.write('=== TradeFlow — verificación de integraciones ===\n')

        engine = settings.DATABASES['default'].get('ENGINE', '')
        self.stdout.write(f'Base de datos: {engine}')
        if 'sqlite' in engine:
            self.stdout.write(self.style.WARNING(
                '  SQLite activo. Para Supabase define DATABASE_URL en .env'
            ))
        else:
            try:
                with connection.cursor() as cur:
                    cur.execute('SELECT 1')
                    ver = connection.cursor().connection.server_version
                self.stdout.write(self.style.SUCCESS(
                    f'  Conexión OK (PostgreSQL server_version={ver})'
                ))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  Error DB: {exc}'))
                raise SystemExit(1) from exc

        if options['skip_email']:
            return

        backend = settings.EMAIL_BACKEND
        self.stdout.write(f'\nEmail backend: {backend}')
        if 'console' in backend:
            self.stdout.write(self.style.WARNING(
                '  Consola activa. Para Gmail real configura:\n'
                '  EMAIL_HOST_USER=tu@gmail.com\n'
                '  EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx  (App Password)\n'
                '  EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend'
            ))
            return

        to_addr = options['email'] or settings.EMAIL_HOST_USER
        if not to_addr:
            self.stdout.write(self.style.ERROR('  Sin EMAIL_HOST_USER ni --email'))
            raise SystemExit(1)

        try:
            send_mail(
                subject='TradeFlow — prueba SMTP',
                message='Si lees esto, Gmail SMTP está configurado correctamente.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_addr],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(
                f'  Correo de prueba enviado a {to_addr}'
            ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  Error SMTP: {exc}'))
            self.stdout.write(
                '  Revisa App Password de Google (2FA) y '
                'https://myaccount.google.com/apppasswords'
            )
            raise SystemExit(1) from exc
