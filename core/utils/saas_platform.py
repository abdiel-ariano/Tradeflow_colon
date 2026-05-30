"""
Diagnóstico y bootstrap SaaS (PostgreSQL/Supabase vía ORM).
"""
from __future__ import annotations

import logging

from django.db import connection
from django.db.utils import DatabaseError, OperationalError, ProgrammingError

from core.enterprise_models import CompanyBillingUsage, CompanySubscription, SaasPlan
from core.models import Company

log = logging.getLogger('tradeflow.saas')


def _table_exists(table_name: str) -> bool:
    try:
        return table_name in connection.introspection.table_names()
    except DatabaseError as exc:
        log.warning('saas_introspection_failed table=%s err=%s', table_name, exc)
        return False


def get_saas_health() -> dict:
    """
    Estado real del datastore SaaS (sin mocks).
    """
    health = {
        'ok': True,
        'plans_count': 0,
        'subscriptions_count': 0,
        'billing_usage_count': 0,
        'checkout_table_ready': _table_exists('core_companyplancheckout'),
        'issues': [],
    }
    try:
        health['plans_count'] = SaasPlan.objects.filter(is_active=True).count()
        health['subscriptions_count'] = CompanySubscription.objects.count()
        health['billing_usage_count'] = CompanyBillingUsage.objects.count()
    except (OperationalError, ProgrammingError) as exc:
        health['ok'] = False
        health['issues'].append(f'orm_error:{exc.__class__.__name__}')
        log.error('saas_health_orm_failed: %s', exc, exc_info=True)
        return health

    if health['plans_count'] == 0:
        health['ok'] = False
        health['issues'].append('no_active_plans')
    if not health['checkout_table_ready']:
        health['issues'].append('migration_0017_pending')

    return health


def bootstrap_saas_datastore(*, seed_subscriptions: bool = False) -> dict:
    """
    Garantiza planes por defecto en DB. Opcionalmente suscripciones para todas las empresas.
    """
    from core.utils.saas_billing import ensure_default_plans, get_or_create_subscription
    from core.utils.ads_ranking import ensure_ad_credits

    health = get_saas_health()
    if health['plans_count'] == 0 or 'no_active_plans' in health['issues']:
        log.warning('saas_bootstrap: seeding default plans (count was %s)', health['plans_count'])
        ensure_default_plans()
        health = get_saas_health()

    if seed_subscriptions and health['ok']:
        seeded = 0
        for company in Company.objects.filter(owner__isnull=False).distinct():
            try:
                sub = get_or_create_subscription(company)
                ensure_ad_credits(company, sub.plan.ad_credits_monthly)
                seeded += 1
            except Exception as exc:
                log.error(
                    'saas_subscription_seed_failed company_id=%s: %s',
                    company.pk,
                    exc,
                    exc_info=True,
                )
        health['companies_seeded'] = seeded
        log.info('saas_bootstrap: subscriptions ensured for %s companies', seeded)

    if not health['checkout_table_ready']:
        log.error(
            'saas_bootstrap: tabla core_companyplancheckout ausente — ejecute migrate (0017_plan_checkout)',
        )
        health['ok'] = False

    log.info(
        'saas_health plans=%s subs=%s usage=%s checkout_table=%s ok=%s',
        health['plans_count'],
        health['subscriptions_count'],
        health['billing_usage_count'],
        health['checkout_table_ready'],
        health['ok'],
    )
    return health


def bootstrap_saas_for_company(company: Company) -> dict:
    """Bootstrap global + suscripción de la empresa solicitante."""
    health = bootstrap_saas_datastore(seed_subscriptions=False)
    if not health.get('ok'):
        return health
    try:
        from core.utils.saas_billing import get_or_create_subscription, refresh_billing_usage

        get_or_create_subscription(company)
        refresh_billing_usage(company)
        health['company_subscription_ok'] = True
    except Exception as exc:
        health['ok'] = False
        health['company_subscription_ok'] = False
        health['issues'].append(f'company_sub:{exc.__class__.__name__}')
        log.error(
            'saas_company_bootstrap_failed company_id=%s: %s',
            company.pk,
            exc,
            exc_info=True,
        )
    return health
