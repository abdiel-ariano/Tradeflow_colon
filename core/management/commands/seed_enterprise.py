"""Bootstrap SaaS plans, demo webhooks, and company subscriptions.

Ops: local/staging or first-time empty production bootstrap only.
Do not re-run casually on live billing data; use verify_saas for checks.
"""
from django.core.management.base import BaseCommand

from core.models import Company
from core.utils.saas_platform import bootstrap_saas_datastore


class Command(BaseCommand):
    """Initialize enterprise plans and one subscription per company."""

    help = 'Initialize enterprise plans and per-company subscriptions'

    def handle(self, *args, **options):
        """Seed SaaS datastore with subscriptions and report company count."""
        health = bootstrap_saas_datastore(seed_subscriptions=True)
        count = health.get('companies_seeded', 0)
        if not health.get('ok'):
            self.stdout.write(self.style.ERROR(f'SaaS seed incompleto: {health.get("issues")}'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f'Enterprise seed: {count} empresas con suscripción.'))
