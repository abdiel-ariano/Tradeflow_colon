"""
Regenerate product images for existing catalog rows (does not delete products).

Usage:
    python manage.py regenerate_product_images
    python manage.py regenerate_product_images --limit 50
    python manage.py regenerate_product_images --missing-only
    python manage.py regenerate_product_images --force
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Product
from core.utils.demo_product_images import assign_product_image, placeholder_relative_path
from core.utils.media_storage import local_media_file_exists


class Command(BaseCommand):
    help = (
        'Generate local PNG product images under media/productos/ for existing products. '
        'Only updates Product.image; does not delete catalog data.'
    )

    def add_arguments(self, parser):
        """Add arguments."""
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max products to process (0 = all matching targets)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate images even when Product.image is already set',
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Only products with no image or a missing file on disk (default behaviour)',
        )

    def handle(self, *args, **options):
        """Handle."""
        limit = int(options['limit'] or 0)
        force = bool(options['force'])
        missing_only = bool(options['missing_only']) or not force

        qs = Product.objects.order_by('pk')
        if force:
            targets = list(qs)
        else:
            targets = []
            for product in qs.iterator():
                if not product.image:
                    targets.append(product)
                elif missing_only and not local_media_file_exists(product.image.name):
                    targets.append(product)
                elif not missing_only:
                    targets.append(product)

        if limit > 0:
            targets = targets[:limit]

        total = len(targets)
        if total == 0:
            self.stdout.write(self.style.WARNING('No products need image regeneration.'))
            return

        out_dir = Path(settings.MEDIA_ROOT) / 'productos'
        out_dir.mkdir(parents=True, exist_ok=True)
        self.stdout.write(
            self.style.NOTICE(
                f'Regenerating images for {total} product(s) → {out_dir}'
            )
        )

        saved = 0
        failed = 0

        for idx, product in enumerate(targets, start=1):
            try:
                rel_path = assign_product_image(product)
                product.image = rel_path
                product.save(update_fields=['image'])
                saved += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[{idx}/{total}] Generated image for {product.name} → {rel_path}'
                    )
                )
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'[{idx}/{total}] Failed for {product.name}: {exc}'
                    )
                )

        sample_path = placeholder_relative_path(targets[0]) if targets else 'productos/placeholders/…'
        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {saved} generated, {failed} failed. Example path: {sample_path}'
            )
        )
