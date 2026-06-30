"""
Verify product media files exist on disk and Product.image.url resolves.

Usage:
    python manage.py verify_media
    python manage.py verify_media --limit 20
    python manage.py verify_media --show-missing
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Product
from core.utils.media_storage import local_media_file_exists, product_image_url


class Command(BaseCommand):
    help = 'Check Product.image paths, on-disk files, and resolvable image URLs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Only inspect the first N products (0 = all)',
        )
        parser.add_argument(
            '--show-missing',
            action='store_true',
            help='Print each product missing an image or file',
        )

    def handle(self, *args, **options):
        limit = int(options['limit'] or 0)
        show_missing = bool(options['show_missing'])

        qs = Product.objects.order_by('pk')
        if limit > 0:
            qs = qs[:limit]

        total = qs.count()
        with_image = 0
        file_ok = 0
        url_ok = 0
        missing_field: list[Product] = []
        missing_file: list[Product] = []
        bad_url: list[Product] = []

        for product in qs.iterator():
            if not product.image:
                missing_field.append(product)
                continue
            with_image += 1
            rel = product.image.name.replace('\\', '/')
            if local_media_file_exists(rel):
                file_ok += 1
            else:
                missing_file.append(product)

            resolved = product_image_url(product) or product.image.url
            if resolved and resolved.startswith(settings.MEDIA_URL):
                url_ok += 1
            elif resolved:
                url_ok += 1
            else:
                bad_url.append(product)

        self.stdout.write(self.style.NOTICE('TradeFlow — verify_media'))
        self.stdout.write(f'MEDIA_ROOT: {settings.MEDIA_ROOT}')
        self.stdout.write(f'MEDIA_URL:  {settings.MEDIA_URL}')
        self.stdout.write(f'Products inspected: {total}')
        self.stdout.write(f'  with image field set: {with_image}')
        self.stdout.write(f'  file exists on disk:  {file_ok}')
        self.stdout.write(f'  resolvable URL:       {url_ok}')
        self.stdout.write(f'  missing image field:  {len(missing_field)}')
        self.stdout.write(f'  missing file on disk: {len(missing_file)}')
        self.stdout.write(f'  empty/bad URL:        {len(bad_url)}')

        productos_dir = Path(settings.MEDIA_ROOT) / 'productos'
        if productos_dir.is_dir():
            files = list(productos_dir.rglob('*'))
            file_count = sum(1 for f in files if f.is_file())
            total_bytes = sum(f.stat().st_size for f in files if f.is_file())
            self.stdout.write(
                f'media/productos/: {file_count} file(s), {total_bytes:,} bytes total'
            )
        else:
            self.stdout.write(self.style.WARNING('media/productos/ directory does not exist'))

        if show_missing:
            for product in missing_field[:50]:
                self.stdout.write(f'  [no field] #{product.pk} {product.name}')
            for product in missing_file[:50]:
                self.stdout.write(
                    f'  [no file]  #{product.pk} {product.name} → {product.image.name}'
                )

        if missing_field or missing_file:
            self.stdout.write(
                self.style.WARNING(
                    'Run: python manage.py regenerate_product_images --missing-only'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('All inspected products have media files.'))
