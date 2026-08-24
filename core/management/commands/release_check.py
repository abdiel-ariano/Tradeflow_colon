"""Pre-deploy gate for critical settings, DB, email, and storage.

Ops: run in CI and before promoting staging to production. Fails on
missing SECRET_KEY / PUBLIC_BASE_URL or unreachable DB. Use
``--allow-debug`` only for local CI with DEBUG=True.
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.email_delivery import validate_email_infrastructure
from core.utils.platform_health import platform_health_payload


class Command(BaseCommand):
    """Validate environment readiness for staging or production release."""

    help = 'Check that the environment is ready for release (staging/prod).'

    def add_arguments(self, parser):
        """Register allow-debug for local CI where DEBUG=True is expected."""
        parser.add_argument(
            '--allow-debug',
            action='store_true',
            help='Do not treat DEBUG=True as a blocking warning in local CI.',
        )

    def handle(self, *args, **options):
        """Collect config warnings/errors and exit 1 when blockers remain."""
        errors = []
        warnings = validate_email_infrastructure()

        if settings.DEBUG and not options['allow_debug']:
            warnings.append('DEBUG=True (aceptable solo en local).')

        if 'sqlite' in settings.DATABASES['default'].get('ENGINE', ''):
            warnings.append('SQLite activo; producción debe usar DATABASE_URL (PostgreSQL/RDS).')

        backend = settings.STORAGES['default']['BACKEND']
        if 'FileSystemStorage' in backend and not settings.DEBUG:
            warnings.append('Media en disco local; configure AWS S3 o Supabase Storage para persistencia.')

        if not settings.DEBUG and not getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', True):
            errors.append(
                'REQUIRE_EMAIL_VERIFICATION=False en producción — active verificación de email.'
            )

        # Demo mode is intentional for investor/Expo deploys — warn, do not block.
        if getattr(settings, 'EXPO_DEMO_MODE', False):
            warnings.append(
                'EXPO_DEMO_MODE=True (bypass post-OTP activo). OK para demo; '
                'desactivar cuando el entorno sea solo producción real.'
            )
        if (
            not getattr(settings, 'EXPO_DEMO_MODE', False)
            and not getattr(settings, 'STAFF_MFA_REQUIRED', True)
            and not settings.DEBUG
        ):
            warnings.append(
                'STAFF_MFA_REQUIRED=False fuera de Expo demo. '
                'En producción real conviene exigir TOTP al staff.'
            )

        if not settings.DEBUG and getattr(settings, 'SERVE_LOCAL_MEDIA', False):
            warnings.append(
                'SERVE_LOCAL_MEDIA=True en producción; prefiera almacenamiento remoto persistente.'
            )

        required = ['SECRET_KEY', 'PUBLIC_BASE_URL']
        for key in required:
            if not getattr(settings, key, None):
                errors.append(f'Falta {key}')

        public_base_url = str(getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip()
        if public_base_url:
            parsed_base_url = urlsplit(public_base_url)
            has_path = parsed_base_url.path not in ('', '/')
            if (
                not settings.DEBUG
                and (
                    parsed_base_url.scheme != 'https'
                    or not parsed_base_url.netloc
                    or has_path
                    or parsed_base_url.query
                    or parsed_base_url.fragment
                )
            ):
                errors.append(
                    'PUBLIC_BASE_URL debe ser un origen HTTPS sin ruta, query ni fragmento '
                    '(ej. https://tradeflowcolon.com).'
                )

        provider_keys = {
            'Google': 'google',
            'Microsoft': 'microsoft',
            'LinkedIn': 'linkedin_oauth2',
        }
        provider_settings = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {}) or {}
        for provider_name, provider_key in provider_keys.items():
            app = (provider_settings.get(provider_key) or {}).get('APP') or {}
            has_client_id = bool(str(app.get('client_id') or '').strip())
            has_secret = bool(str(app.get('secret') or '').strip())
            if has_client_id != has_secret:
                errors.append(
                    f'OAuth {provider_name} incompleto: configure client_id y secret juntos.'
                )

        backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
        if not settings.DEBUG and not getattr(settings, 'EMAIL_USE_REAL_SMTP', False):
            if not getattr(settings, 'SUPABASE_CONFIGURED', False):
                errors.append(
                    'Configure SUPABASE_SERVICE_KEY o EMAIL_BACKEND SMTP en producción.'
                )

        payload = platform_health_payload(detailed=True)
        if not payload['database']['ok']:
            from core.utils.database_url import database_connection_hint

            errors.append(
                database_connection_hint(
                    Exception(payload['database'].get('detail') or 'unreachable')
                )
            )

        for w in warnings:
            self.stdout.write(self.style.WARNING(f'  ⚠ {w}'))
        for e in errors:
            self.stdout.write(self.style.ERROR(f'  ✗ {e}'))

        if errors:
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('Release check: OK'))
