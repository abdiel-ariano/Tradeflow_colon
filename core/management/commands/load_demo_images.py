"""
Download demo product images and assign to products without images.

Usage:
    python manage.py load_demo_images
    python manage.py load_demo_images --limit 10
    python manage.py load_demo_images --storage local
    python manage.py load_demo_images --storage remote
    python manage.py load_demo_images --fallback placeholders
"""

from __future__ import annotations

import time

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Product
from core.utils.demo_product_images import (
    category_keyword,
    generate_placeholder_bytes,
    picsum_url,
    save_product_image_bytes,
    storage_mode_help,
)

RATE_LIMIT_SECONDS = 0.5


class Command(BaseCommand):
    help = 'Download demo product images and assign to products without images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max products to process (0 = all)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be downloaded without saving',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download even if an image file is already set',
        )
        parser.add_argument(
            '--storage',
            choices=['local', 'remote', 'auto'],
            default='local',
            help=storage_mode_help(),
        )
        parser.add_argument(
            '--fallback',
            choices=['none', 'placeholders'],
            default='placeholders',
            help='When download or upload fails: none (skip) or placeholders (PIL)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=RATE_LIMIT_SECONDS,
            help='Seconds between downloads (default 0.5)',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']
        force = options['force']
        storage_mode = options['storage']
        fallback = options['fallback']
        delay = max(0.0, options['delay'])

        qs = Product.objects.select_related('category').order_by('pk')
        if not force:
            qs = qs.filter(Q(image='') | Q(image__isnull=True))
        if limit > 0:
            qs = qs[:limit]

        products = list(qs)
        total = len(products)
        self.stdout.write(f'Found {total} product(s) to process (storage={storage_mode})')

        if dry_run:
            for product in products:
                keyword = category_keyword(product)
                self.stdout.write(f'  [dry-run] {product.name} ({keyword}) → {picsum_url(product)}')
            self.stdout.write(self.style.SUCCESS('Dry run complete.'))
            return

        saved = 0
        placeholder_saved = 0
        failed = 0

        for idx, product in enumerate(products, start=1):
            keyword = category_keyword(product)
            content = None

            try:
                response = requests.get(picsum_url(product), timeout=20, allow_redirects=True)
                if response.status_code == 200 and response.content:
                    content = response.content
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'[{idx}/{total}] HTTP {response.status_code} for {product.name}'
                        )
                    )
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f'[{idx}/{total}] Download failed for {product.name}: {exc}')
                )

            try:
                if content:
                    save_product_image_bytes(product, content, storage_mode=storage_mode)
                    saved += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[{idx}/{total}] Saved image for {product.name} ({keyword})'
                        )
                    )
                elif fallback == 'placeholders':
                    blob = generate_placeholder_bytes(product)
                    save_product_image_bytes(product, blob, storage_mode=storage_mode)
                    placeholder_saved += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[{idx}/{total}] Placeholder for {product.name} ({keyword})'
                        )
                    )
                else:
                    failed += 1
            except Exception as exc:
                if fallback == 'placeholders':
                    try:
                        blob = generate_placeholder_bytes(product)
                        save_product_image_bytes(product, blob, storage_mode='local')
                        placeholder_saved += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'[{idx}/{total}] Upload failed ({exc}); saved local placeholder for {product.name}'
                            )
                        )
                    except Exception as inner:
                        failed += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'[{idx}/{total}] Error for {product.name}: {inner}'
                            )
                        )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'[{idx}/{total}] Error for {product.name}: {exc}')
                    )

            if idx < total and delay:
                time.sleep(delay)

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Downloaded: {saved}, placeholders: {placeholder_saved}, failed: {failed}.'
            )
        )
        if storage_mode == 'local':
            self.stdout.write(
                'Images saved under MEDIA_ROOT/products/demo/. '
                'Use --storage remote to upload to Supabase when bucket permissions are configured.'
            )
