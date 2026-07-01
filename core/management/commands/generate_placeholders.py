"""
Generate brand-colored PNG placeholder images for products without images.

Usage:
    python manage.py generate_placeholders
    python manage.py generate_placeholders --limit 20
    python manage.py generate_placeholders --storage local
    python manage.py generate_placeholders --force
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Product
from core.utils.demo_product_images import (
    generate_placeholder_bytes,
    placeholder_relative_path,
    save_placeholder_for_product,
    storage_mode_help,
    write_local_image,
)
from core.utils.media_storage import local_media_file_exists


class Command(BaseCommand):
    help = 'Generate 400×400 PNG placeholders with brand gradient and product initials'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max products to process (0 = all missing images)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate placeholders even when image is already set',
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
        limit = int(options['limit'] or 0)
        force = bool(options['force'])
        repair_missing = bool(options['repair_missing'])
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
        if total == 0:
            self.stdout.write(self.style.WARNING('No products need placeholders.'))
            return

        out_dir = Path(settings.MEDIA_ROOT) / 'productos' / 'placeholders'
        out_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f'Generating placeholders for {total} product(s) → {out_dir}')

        saved = 0
        failed = 0

        for idx, product in enumerate(products, start=1):
            try:
                blob = generate_placeholder_bytes(product)
                rel_path = placeholder_relative_path(product)

                if storage_mode == 'local':
                    write_local_image(rel_path, blob)
                    product.image = rel_path
                    product.save(update_fields=['image'])
                else:
                    rel_path = save_placeholder_for_product(
                        product,
                        blob,
                        storage_mode=storage_mode,
                    )
                    product.refresh_from_db(fields=['image'])

                saved += 1
                if idx <= 5 or idx == total or idx % 100 == 0:
                    self.stdout.write(
                        self.style.SUCCESS(f'[{idx}/{total}] {product.name} → {rel_path}')
                    )
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'[{idx}/{total}] Error for {product.name}: {exc}')
                )

        remaining = Product.objects.filter(Q(image='') | Q(image__isnull=True)).count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Generated {saved} placeholder(s) in {out_dir}. Failed: {failed}. '
                f'Products still without image: {remaining}.'
            )
        )
