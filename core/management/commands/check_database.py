"""Fail fast when DATABASE_URL is misconfigured (Railway / Supabase)."""
from django.core.management.base import BaseCommand

from core.utils.database_url import database_connection_hint
from core.utils.platform_health import check_database


class Command(BaseCommand):
    help = 'Verify PostgreSQL/Supabase connectivity before serving traffic.'

    def add_arguments(self, parser):
        """Add arguments."""
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Only print errors (for entrypoint scripts).',
        )

    def handle(self, *args, **options):
        """Handle."""
        quiet = bool(options['quiet'])
        result = check_database()
        if result['ok']:
            if not quiet:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Database OK ({result['latency_ms']} ms)"
                    )
                )
            return

        detail = result.get('detail', 'unknown error')
        hint = database_connection_hint(Exception(detail))
        self.stderr.write(self.style.ERROR(hint))
        raise SystemExit(1)
