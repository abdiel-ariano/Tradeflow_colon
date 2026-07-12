"""
Assign bundled category seed photographs to products without images.

Seeds live in static/images/catalog-seeds/ (committed assets).
Each product gets a cropped variant so grids do not look cloned.

Usage:
    python manage.py seed_catalog_images
    python manage.py seed_catalog_images --limit 50
    python manage.py seed_catalog_images --force
    python manage.py seed_catalog_images --storage remote
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Product
from core.utils.demo_product_images import (
    assign_catalog_seed_image,
    category_keyword,
    save_product_image_bytes,
    storage_mode_help,
    variant_image_bytes,
)
from core.utils.media_storage import local_media_file_exists


class Command(BaseCommand):
    help = 'Assign real category seed photos to products (bundled static assets, no runtime picsum).'

    def add_arguments(self, parser):
        """Add arguments."""
        parser.add_argument('--limit', type=int, default=0, help='Max products (0 = all)')
        parser.add_argument('--force', action='store_true', help='Replace existing images')
        parser.add_argument(
            '--storage',
            choices=['local', 'remote', 'auto'],
            default='local',
            help=storage_mode_help(),
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        """Handle."""
        limit = int(options['limit'] or 0)
        force = bool(options['force'])
        storage_mode = options['storage']
        dry_run = bool(options['dry_run'])

        qs = Product.objects.select_related('category').order_by('pk')
        if not force:
            targets = []
            for product in qs.iterator():
                if not product.image:
                    targets.append(product.pk)
                elif not local_media_file_exists(product.image.name):
                    targets.append(product.pk)
            qs = Product.objects.filter(pk__in=targets).select_related('category').order_by('pk')

        if limit > 0:
            qs = qs[:limit]

        products = list(qs)
        total = len(products)
        self.stdout.write(f'Seeding catalog images for {total} product(s) (storage={storage_mode})')

        if dry_run:
            for product in products:
                self.stdout.write(f'  [dry-run] {product.name} → {category_keyword(product)}')
            return

        saved = 0
        failed = 0
        for idx, product in enumerate(products, start=1):
            try:
                if storage_mode == 'local':
                    rel = assign_catalog_seed_image(product)
                else:
                    content = variant_image_bytes(product)
                    rel = save_product_image_bytes(product, content, storage_mode=storage_mode)
                saved += 1
                if idx <= 5 or idx == total or idx % 100 == 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[{idx}/{total}] {product.name} ({category_keyword(product)}) → {rel}'
                        )
                    )
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'[{idx}/{total}] Failed for {product.name}: {exc}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Done. Seeded: {saved}, failed: {failed}.')
        )
