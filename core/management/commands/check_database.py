"""Fail fast when DATABASE_URL cannot reach PostgreSQL/Supabase.

Ops: run from container entrypoints and CI before serving traffic.
Safe on production; exits non-zero when the DB is unreachable.
"""
from django.core.management.base import BaseCommand

from core.utils.database_url import database_connection_hint
from core.utils.platform_health import check_database


class Command(BaseCommand):
    """Verify database connectivity and print latency or a fix hint."""

    help = 'Verify PostgreSQL/Supabase connectivity before serving traffic.'

    def add_arguments(self, parser):
        """Register quiet mode for entrypoint scripts."""
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Only print errors (for entrypoint scripts).',
        )

    def handle(self, *args, **options):
        """Probe the default DB; exit 1 with a connection hint on failure."""
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
