"""
Generate brand-colored placeholder images for products without images (offline).

Usage:
    python manage.py generate_placeholders
    python manage.py generate_placeholders --limit 20
"""

from __future__ import annotations

import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q
from PIL import Image, ImageDraw, ImageFont

from core.models import Product

BRAND_COLORS = [
    (15, 42, 68),    # navy
    (27, 59, 99),    # mid
    (46, 91, 138),   # blue
    (242, 101, 34),  # orange
]

FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
]


def product_initials(name: str) -> str:
    parts = [p for p in name.split() if p][:2]
    if not parts:
        return 'TF'
    return ''.join(word[0] for word in parts).upper()


def load_font(size: int = 60):
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


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

    def handle(self, *args, **options):
        limit = options['limit']
        force = options['force']

        qs = Product.objects.order_by('pk')
        if not force:
            qs = qs.filter(Q(image='') | Q(image__isnull=True))
        if limit > 0:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f'Generating placeholders for {total} product(s)')

        font = load_font()
        saved = 0

        for idx, product in enumerate(qs, start=1):
            color = BRAND_COLORS[product.pk % len(BRAND_COLORS)]
            img = Image.new('RGB', (400, 300), color)
            draw = ImageDraw.Draw(img)

            initials = product_initials(product.name)
            bbox = draw.textbbox((0, 0), initials, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (400 - text_width) / 2
            y = (300 - text_height) / 2
            draw.text((x, y), initials, fill=(255, 255, 255), font=font)

            from io import BytesIO

            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)

            filename = f'demo/product_{product.pk}.jpg'
            product.image.save(filename, ContentFile(buffer.read()), save=True)
            saved += 1
            self.stdout.write(
                self.style.SUCCESS(f'[{idx}/{total}] Generated placeholder for {product.name}')
            )

        self.stdout.write(self.style.SUCCESS(f'Done. Generated {saved} image(s).'))
