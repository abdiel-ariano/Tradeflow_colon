"""
Repair legacy seeded catalog rows: strip lot suffixes and rebalance stock.

Safe to re-run. Targets products whose names still contain the old lot pattern.
"""
from __future__ import annotations

import random
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Inventory, Product
from core.utils.product_seed_naming import strip_lot_suffix
from core.utils.product_stock_seed import realistic_stock_qty

_LOT_PATTERN = re.compile(r'lot\s+\d+', re.IGNORECASE)


class Command(BaseCommand):
    help = 'Remove lot-based product names and redistribute stock for seeded catalog credibility.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print changes without saving.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        rng = random.Random(42)
        renamed = 0
        restocked = 0

        with transaction.atomic():
            for product in Product.objects.select_related('inventory', 'company').iterator():
                new_name = strip_lot_suffix(product.name)
                name_changed = new_name != product.name and _LOT_PATTERN.search(product.name)

                inv = getattr(product, 'inventory', None)
                stock_changed = False
                new_stock = None
                if inv and inv.stock_qty >= 200:
                    # Rebalance only obviously uniform high seed stock.
                    tier = 1 if getattr(product.company, 'is_featured', False) else 2
                    new_stock = realistic_stock_qty(rng, tier=tier)
                    stock_changed = abs(new_stock - inv.stock_qty) > 50

                if not name_changed and not stock_changed:
                    continue

                if dry_run:
                    if name_changed:
                        self.stdout.write(f'  rename: {product.name!r} -> {new_name!r}')
                    if stock_changed and inv:
                        self.stdout.write(f'  stock {product.pk}: {inv.stock_qty} -> {new_stock}')
                    continue

                if name_changed:
                    product.name = new_name
                    product.save(update_fields=['name'])
                    renamed += 1

                if stock_changed and inv and new_stock is not None:
                    inv.stock_qty = new_stock
                    inv.low_stock_alert = max(5, min(new_stock // 10, 25))
                    inv.save(update_fields=['stock_qty', 'low_stock_alert'])
                    restocked += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Renamed {renamed}, restocked {restocked}'
                + (' (dry-run)' if dry_run else '')
            )
        )
