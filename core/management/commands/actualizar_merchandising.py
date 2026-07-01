"""
=============================================================================
ACCIÓN: CREAR
DESTINO: core/management/commands/actualizar_merchandising.py
=============================================================================
Recalcula flags is_bestseller y desactiva promos vencidas.
=============================================================================
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from core.models import OrderItem, Product


class Command(BaseCommand):
    help = 'Recalcula bestsellers (30 días) y limpia promociones vencidas.'

    def handle(self, *args, **options):
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
