"""Diagnose SaaS datastore health and optionally seed default plans.

Ops: safe health check on any environment. ``--seed`` writes plans and
per-company subscriptions — use on local/staging or empty production
bootstrap only, not as a routine prod cron.
"""
from django.core.management.base import BaseCommand

from core.utils.saas_platform import bootstrap_saas_datastore, get_saas_health


class Command(BaseCommand):
    """Report SaaS plans, subscriptions, usage, and checkout table readiness."""

    help = 'SaaS diagnostics: plans, subscriptions, usage, and checkout migration'

    def add_arguments(self, parser):
        """Register optional bootstrap seeding of plans and subscriptions."""
        parser.add_argument(
            '--seed',
            action='store_true',
            help='Run ensure_default_plans and per-company subscriptions',
        )

    def handle(self, *args, **options):
        """Print SaaS health; auto-bootstrap plans when count is zero."""
        if options['seed']:
            health = bootstrap_saas_datastore(seed_subscriptions=True)
        else:
            health = get_saas_health()
            if health['plans_count'] == 0:
                self.stdout.write(self.style.WARNING('Sin planes — ejecutando ensure_default_plans…'))
                health = bootstrap_saas_datastore(seed_subscriptions=False)

        self.stdout.write(f"OK: {health.get('ok')}")
        self.stdout.write(f"Planes activos: {health.get('plans_count')}")
        self.stdout.write(f"Suscripciones: {health.get('subscriptions_count')}")
        self.stdout.write(f"Uso facturación: {health.get('billing_usage_count')}")
        self.stdout.write(f"Tabla checkout: {health.get('checkout_table_ready')}")
        if health.get('issues'):
            self.stdout.write(self.style.WARNING(f"Issues: {', '.join(health['issues'])}"))
        if not health.get('ok'):
            self.stdout.write(
                self.style.ERROR(
                    'Corrija: python manage.py migrate && python manage.py verify_saas --seed',
                ),
            )
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('SaaS datastore listo.'))
