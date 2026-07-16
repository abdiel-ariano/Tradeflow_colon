"""Send a registration-style verification email for one DB user.

Ops: local/staging mail pipeline tests only. Target a controlled inbox;
do not blast production buyers.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from core.utils.email_config import smtp_configured
from core.utils.email_sender import enviar_verificacion_email


class Command(BaseCommand):
    """Deliver one verification email via the same path as signup."""

    help = 'Send verification email to a user (Resend)'

    def add_arguments(self, parser):
        """Register email or username lookup for the recipient user."""
        parser.add_argument('--email', type=str, help='User email in DB')
        parser.add_argument('--username', type=str, help='Django username in DB')

    def handle(self, *args, **options):
        """Locate the user, build a fake request, and send verification."""
        email = (options.get('email') or '').strip()
        username = (options.get('username') or '').strip()
        if not email and not username:
            raise CommandError('Indica --email o --username')

        qs = User.objects.all()
        if email:
            qs = qs.filter(email__iexact=email)
        if username:
            qs = qs.filter(username=username)
        user = qs.first()
        if not user:
            raise CommandError('Usuario no encontrado')

        self.stdout.write(f'smtp_configured={smtp_configured()}')
        self.stdout.write(f'Enviando a: {user.email}')

        request = RequestFactory().get('/')
        request.META['HTTP_HOST'] = '127.0.0.1:8000'
        request.META['SERVER_NAME'] = '127.0.0.1'
        request.META['SERVER_PORT'] = '8000'

        try:
            result = enviar_verificacion_email(user, request)
        except Exception as exc:
            raise CommandError(f'Falló el envío: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(
            f"OK channel={result['channel']} code={result['code']} to={result['recipient']}"
        ))
        if result['channel'] != 'resend':
            self.stdout.write(self.style.WARNING(
                'Configura RESEND_API_KEY=re_... en .env o Railway'
            ))
        self.stdout.write(f"URL: {result['link']}")
