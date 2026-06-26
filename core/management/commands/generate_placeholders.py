"""
Generate brand-colored placeholder images for products without images (offline).

Usage:
    python manage.py generate_placeholders
    python manage.py generate_placeholders --limit 20
    python manage.py generate_placeholders --storage local
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Product
from core.utils.demo_product_images import (
    generate_placeholder_bytes,
    save_product_image_bytes,
    storage_mode_help,
)


class Command(BaseCommand):
    help = 'Generate colored placeholder images for products without images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max products to process (0 = all)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate even when an image is already set',
        )
        parser.add_argument(
            '--storage',
            choices=['local', 'remote', 'auto'],
            default='local',
            help=storage_mode_help(),
        )

    def handle(self, *args, **options):
        limit = options['limit']
        force = options['force']
        storage_mode = options['storage']

        qs = Product.objects.order_by('pk')
        if not force:
            qs = qs.filter(Q(image='') | Q(image__isnull=True))
        if limit > 0:
            qs = qs[:limit]

        products = list(qs)
        total = len(products)
        self.stdout.write(f'Generating placeholders for {total} product(s) (storage={storage_mode})')

        saved = 0
        failed = 0

        for idx, product in enumerate(products, start=1):
            try:
                blob = generate_placeholder_bytes(product)
                save_product_image_bytes(product, blob, storage_mode=storage_mode)
                saved += 1
                self.stdout.write(
                    self.style.SUCCESS(f'[{idx}/{total}] Generated placeholder for {product.name}')
                )
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'[{idx}/{total}] Error for {product.name}: {exc}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Done. Generated {saved} image(s), failed: {failed}.')
        )
