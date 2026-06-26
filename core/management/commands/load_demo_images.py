"""
Download demo product images from Picsum and assign to products without images.

Usage:
    python manage.py load_demo_images
    python manage.py load_demo_images --limit 10
    python manage.py load_demo_images --dry-run
"""

from __future__ import annotations

import re
import time

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Product

# Category keyword hints (matched against Category.name, case-insensitive).
CATEGORY_IMAGES = {
    'textiles': ['textile', 'fabric', 'clothing', 'uniform', 'apparel'],
    'electronics': ['electronic', 'gadget', 'computer', 'phone', 'tech'],
    'home_appliances': ['appliance', 'kitchen', 'home', 'household'],
    'beauty': ['beauty', 'cosmetic', 'perfume', 'fragrance', 'personal care'],
    'toys': ['toy', 'game', 'children'],
    'general': ['wholesale', 'bulk', 'merchandise', 'general'],
}

PICSUM_SIZE = '400/300'
RATE_LIMIT_SECONDS = 0.5


def category_keyword(product: Product) -> str:
    """Pick the best keyword bucket for a product's category name."""
    if not product.category_id or not product.category:
        return 'general'
    cat_name = product.category.name.lower()
    for key, hints in CATEGORY_IMAGES.items():
        if key.replace('_', ' ') in cat_name or key in cat_name:
            return key
        if any(hint in cat_name for hint in hints):
            return key
    return 'general'


def seed_slug(product: Product) -> str:
    """Stable seed so the same product always gets the same remote image."""
    raw = f'{product.pk}_{product.name[:40]}'
    return re.sub(r'[^a-zA-Z0-9_-]', '_', raw)


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

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']
        force = options['force']

        qs = Product.objects.select_related('category').order_by('pk')
        if not force:
            qs = qs.filter(Q(image='') | Q(image__isnull=True))

        if limit > 0:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f'Found {total} product(s) to process')

        if dry_run:
            for product in qs:
                seed = seed_slug(product)
                keyword = category_keyword(product)
                url = f'https://picsum.photos/seed/{seed}/{PICSUM_SIZE}'
                self.stdout.write(f'  [dry-run] {product.name} ({keyword}) → {url}')
            self.stdout.write(self.style.SUCCESS('Dry run complete.'))
            return

        saved = 0
        failed = 0

        for idx, product in enumerate(qs, start=1):
            seed = seed_slug(product)
            url = f'https://picsum.photos/seed/{seed}/{PICSUM_SIZE}'
            keyword = category_keyword(product)

            try:
                response = requests.get(url, timeout=15, allow_redirects=True)
                if response.status_code != 200:
                    self.stdout.write(
                        self.style.WARNING(
                            f'[{idx}/{total}] HTTP {response.status_code} for {product.name}'
                        )
                    )
                    failed += 1
                    continue

                filename = f'demo/product_{product.pk}.jpg'
                product.image.save(filename, ContentFile(response.content), save=True)
                saved += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[{idx}/{total}] Saved image for {product.name} ({keyword})'
                    )
                )
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'[{idx}/{total}] Error for {product.name}: {exc}')
                )

            if idx < total:
                time.sleep(RATE_LIMIT_SECONDS)

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Saved: {saved}, failed: {failed}. Media root: {settings.MEDIA_ROOT}'
            )
        )
