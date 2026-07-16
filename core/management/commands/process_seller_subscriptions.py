"""Advance seller SaaS subscription lifecycle without Stripe.

Daily job for trial end, paid-period renewal into grace, medium churn,
and grace reminder emails on the CFZ seller billing flow.

Ops: schedule on Railway/OS cron (e.g. 06:00 UTC). Safe to re-run;
each step checks status before mutating. Suitable for staging and
production when seller subscriptions are live.
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
    """Process expired trials, renewals, grace windows, and reminders.

    Idempotent steps:
    1. ``trialing`` past ``current_period_end`` → finalize trial.
    2. ``active`` past period end → past_due with grace.
    3. ``past_due`` past ``grace_ends_at`` → medium churn.
    4. Grace reminders when 4 or 1 days remain.
    """

    help = (
        'Process trial expirations, active renewals, and grace churn '
        '(in-house flow without Stripe).'
    )

    def handle(self, *args, **options):
        """Run one full subscription lifecycle pass and print counts."""
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
        """Send trial-ended mail; log and continue on failure."""
        try:
            from core.utils.email_sender import enviar_trial_finalizado
            enviar_trial_finalizado(company)
        except Exception as exc:
            log.warning('trial_ended_email_failed company_id=%s: %s', company.pk, exc)

    def _maybe_send_grace_reminder(self, company, days_left: int) -> bool:
        """Send grace reminder; return False if delivery fails."""
        try:
            from core.utils.email_sender import enviar_grace_recordatorio
            return enviar_grace_recordatorio(company, days_left)
        except Exception as exc:
            log.warning('grace_reminder_email_failed company_id=%s: %s', company.pk, exc)
            return False
