"""
Sembrar planes SaaS, webhooks demo y suscripciones para empresas existentes.
"""
from django.core.management.base import BaseCommand

from core.models import Company
from core.utils.saas_platform import bootstrap_saas_datastore


class Command(BaseCommand):
    help = 'Inicializa planes enterprise y suscripciones por empresa'

    def handle(self, *args, **options):
        """Handle."""
        health = bootstrap_saas_datastore(seed_subscriptions=True)
        count = health.get('companies_seeded', 0)
        if not health.get('ok'):
            self.stdout.write(self.style.ERROR(f'SaaS seed incompleto: {health.get("issues")}'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f'Enterprise seed: {count} empresas con suscripción.'))
