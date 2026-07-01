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
    assign_catalog_seed_image,
    category_keyword,
    generate_placeholder_bytes,
    picsum_url,
    save_product_image_bytes,
    storage_mode_help,
    use_runtime_picsum,
    variant_image_bytes,
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
            '--source',
            choices=['catalog-seeds', 'picsum', 'placeholders'],
            default='catalog-seeds',
            help='Image source: bundled category photos (default), remote picsum, or PIL placeholders',
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
        source = options['source']
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
                label = source
                if source == 'picsum':
                    label = picsum_url(product)
                self.stdout.write(f'  [dry-run] {product.name} ({keyword}) → {label}')
            self.stdout.write(self.style.SUCCESS('Dry run complete.'))
            return

        saved = 0
        placeholder_saved = 0
        failed = 0

        for idx, product in enumerate(products, start=1):
            keyword = category_keyword(product)
            content = None

            try:
                if source == 'catalog-seeds':
                    content = variant_image_bytes(product)
                elif source == 'placeholders':
                    content = generate_placeholder_bytes(product)
                elif source == 'picsum':
                    if not use_runtime_picsum():
                        self.stdout.write(
                            self.style.WARNING(
                                'picsum source requires TRADEFLOW_USE_PICSUM_RUNTIME or DEBUG=True'
                            )
                        )
                    response = requests.get(picsum_url(product), timeout=20, allow_redirects=True)
                    if response.status_code == 200 and response.content:
                        content = response.content

                if content:
                    if source == 'catalog-seeds' and storage_mode == 'local':
                        assign_catalog_seed_image(product)
                    else:
                        save_product_image_bytes(product, content, storage_mode=storage_mode)
                    saved += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[{idx}/{total}] Saved image for {product.name} ({keyword})'
                        )
                    )
                else:
                    blob = generate_placeholder_bytes(product)
                    save_product_image_bytes(product, blob, storage_mode='local')
                    placeholder_saved += 1
            except Exception as exc:
                try:
                    blob = generate_placeholder_bytes(product)
                    save_product_image_bytes(product, blob, storage_mode='local')
                    placeholder_saved += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'[{idx}/{total}] Fallback placeholder for {product.name}: {exc}'
                        )
                    )
                except Exception as inner:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'[{idx}/{total}] Error for {product.name}: {inner}')
                    )

            if source == 'picsum' and idx < total and delay:
                time.sleep(delay)

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Saved: {saved}, placeholders: {placeholder_saved}, failed: {failed}.'
            )
        )
