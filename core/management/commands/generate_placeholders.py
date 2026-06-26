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
from core.utils.media_storage import local_media_file_exists


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
            help='Regenerate placeholders for every product',
        )
        parser.add_argument(
            '--repair-missing',
            action='store_true',
            help='Regenerate when image path is set but the local file is missing',
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
        repair_missing = options['repair_missing']
        storage_mode = options['storage']

        qs = Product.objects.order_by('pk')
        if force:
            pass
        elif repair_missing or storage_mode == 'local':
            candidates = []
            for product in qs.iterator():
                if not product.image:
                    candidates.append(product.pk)
                elif storage_mode == 'local' and not local_media_file_exists(product.image.name):
                    candidates.append(product.pk)
            qs = Product.objects.filter(pk__in=candidates).order_by('pk')
        else:
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
