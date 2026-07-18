"""Purge aged security / email delivery audit rows (GDPR retention)."""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    """Delete EmailDeliveryLog / ApiAuditLog rows older than N days."""

    help = 'Purge email delivery and API audit logs older than --days (default 90).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        days = max(1, int(options['days']))
        cutoff = timezone.now() - timedelta(days=days)
        dry = options['dry_run']

        from core.enterprise_models import ApiAuditLog, EmailDeliveryLog

        email_qs = EmailDeliveryLog.objects.filter(created_at__lt=cutoff)
        api_qs = ApiAuditLog.objects.filter(created_at__lt=cutoff)
        n_email, n_api = email_qs.count(), api_qs.count()
        if dry:
            self.stdout.write(f'[dry-run] would delete email={n_email} api={n_api} before {cutoff}')
            return
        deleted_email, _ = email_qs.delete()
        deleted_api, _ = api_qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'Purged email_logs={deleted_email} api_logs={deleted_api} (older than {days}d)'
        ))
