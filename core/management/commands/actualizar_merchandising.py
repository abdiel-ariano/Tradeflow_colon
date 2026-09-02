"""Refresh bestseller flags and clear expired product promotions.

Uses non-cancelled OrderItem volume over the last 30 days to mark the
top movers, then nulls promo fields past ``promo_ends_at``.

Ops: schedule daily on staging/production after orders exist. Safe to
re-run; invalidates merchandising cache afterward.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from core.models import OrderItem, Product


class Command(BaseCommand):
    """Recalculate bestsellers and clean expired promo prices."""

    help = 'Recalculate bestsellers (30 days) and clear expired promotions.'

    def handle(self, *args, **options):
        """Update is_bestseller, clear expired promos, invalidate cache."""
        now = timezone.now()
        since = now - timedelta(days=30)

        Product.objects.update(is_bestseller=False)

        top_rows = (
            OrderItem.objects.filter(order__created_at__gte=since)
            .exclude(order__status='cancelled')
            .values('product_id')
            .annotate(units=Sum('qty'))
            .order_by('-units')[:50]
        )
        top_ids = [r['product_id'] for r in top_rows if r['product_id']]
        updated = Product.objects.filter(pk__in=top_ids).update(is_bestseller=True)
        self.stdout.write(self.style.SUCCESS(f'Bestsellers marcados: {updated}'))

        expired = Product.objects.filter(
            promo_ends_at__lt=now,
            promo_price__isnull=False,
        )
        cleared = 0
        for p in expired:
            p.promo_price = None
            p.promo_starts_at = None
            p.promo_ends_at = None
            p.save(update_fields=['promo_price', 'promo_starts_at', 'promo_ends_at'])
            cleared += 1
        self.stdout.write(self.style.SUCCESS(f'Promos vencidas limpiadas: {cleared}'))

        from core.utils.tradeflow_cache import invalidate_merchandising_cache

        invalidate_merchandising_cache()
        self.stdout.write(self.style.SUCCESS('Cache de merchandising invalidada.'))
