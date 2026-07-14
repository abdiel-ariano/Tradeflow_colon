"""
=============================================================================
TRADEFLOW COLÓN — process_seller_subscriptions
=============================================================================
Job diario de ciclo de vida SaaS seller (sin Stripe).

EJECUCIÓN (Railway Cron / cron del SO)
--------------------------------------
    python manage.py process_seller_subscriptions

Railway → New → Cron Job (servicio separado o cron schedule):
    Schedule: 0 6 * * *   (06:00 UTC diario)
    Start command: python manage.py process_seller_subscriptions

LÓGICA IDEMPOTENTE
------------------
1. ``trialing`` con ``current_period_end < now`` → ``finalize_trial_period()``
2. ``active`` con ``current_period_end < now`` → ``mark_paid_period_elapsed()``
   (renovación: pasa a past_due + gracia; seller paga transferencia de nuevo)
3. ``past_due`` con ``grace_ends_at < now`` → ``apply_medium_churn()``
4. Emails de recordatorio de gracia (días restantes 4 y 1)

Seguro re-ejecutar: cada paso verifica estado antes de mutar.
=============================================================================
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.enterprise_models import CompanySubscription
from core.utils.seller_lifecycle import (
    apply_medium_churn,
    finalize_trial_period,
    grace_days_remaining,
    mark_paid_period_elapsed,
)

log = logging.getLogger('tradeflow.seller_lifecycle')


class Command(BaseCommand):
    help = (
        'Procesa vencimientos de trial, renovación activa y gracia '
        '(flujo propio sin Stripe).'
    )

    def handle(self, *args, **options):
        now = timezone.now()
        finalized = 0
        renewals = 0
        churned = 0
        reminders = 0

        # 1) Fin de trial gratuito → past_due + recomendación
        trialing_qs = CompanySubscription.objects.filter(
            status='trialing',
            current_period_end__lt=now,
        ).select_related('company', 'company__owner')

        for sub in trialing_qs:
            result = finalize_trial_period(sub.company)
            if result:
                finalized += 1
                self._maybe_send_trial_ended_email(sub.company)

        # 2) Periodo pagado vencido → past_due (pedir transferencia de renovación)
        active_qs = CompanySubscription.objects.filter(
            status='active',
            current_period_end__lt=now,
        ).select_related('company')

        for sub in active_qs:
            result = mark_paid_period_elapsed(sub.company)
            if result:
                renewals += 1
                self._maybe_send_trial_ended_email(sub.company)

        # 3) Gracia vencida → baja media
        past_due_qs = CompanySubscription.objects.filter(
            status='past_due',
            grace_ends_at__lt=now,
        ).select_related('company')

        for sub in past_due_qs:
            apply_medium_churn(sub.company)
            churned += 1

        # 4) Recordatorios en gracia
        grace_qs = CompanySubscription.objects.filter(
            status='past_due',
            grace_ends_at__gte=now,
        ).select_related('company', 'recommended_plan')

        for sub in grace_qs:
            days_left = grace_days_remaining(sub, now=now)
            if days_left in (4, 1):
                if self._maybe_send_grace_reminder(sub.company, days_left):
                    reminders += 1

        self.stdout.write(self.style.SUCCESS(
            'process_seller_subscriptions: '
            f'finalized={finalized} renewals={renewals} '
            f'churned={churned} reminders={reminders}',
        ))

    def _maybe_send_trial_ended_email(self, company) -> None:
        try:
            from core.utils.email_sender import enviar_trial_finalizado
            enviar_trial_finalizado(company)
        except Exception as exc:
            log.warning('trial_ended_email_failed company_id=%s: %s', company.pk, exc)

    def _maybe_send_grace_reminder(self, company, days_left: int) -> bool:
        try:
            from core.utils.email_sender import enviar_grace_recordatorio
            return enviar_grace_recordatorio(company, days_left)
        except Exception as exc:
            log.warning('grace_reminder_email_failed company_id=%s: %s', company.pk, exc)
            return False
