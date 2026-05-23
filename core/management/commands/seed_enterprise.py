"""
Sembrar planes SaaS, webhooks demo y suscripciones para empresas existentes.
"""
from django.core.management.base import BaseCommand

from core.models import Company
from core.utils.saas_billing import ensure_default_plans, get_or_create_subscription
from core.utils.ads_ranking import ensure_ad_credits


class Command(BaseCommand):
    help = 'Inicializa planes enterprise y suscripciones por empresa'

    def handle(self, *args, **options):
        ensure_default_plans()
        count = 0
        for company in Company.objects.filter(owner__isnull=False).distinct():
            sub = get_or_create_subscription(company)
            ensure_ad_credits(company, sub.plan.ad_credits_monthly)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Enterprise seed: {count} empresas con suscripción.'))
