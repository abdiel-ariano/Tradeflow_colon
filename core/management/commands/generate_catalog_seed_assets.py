"""
Generate bundled category seed JPEGs in static/images/catalog-seeds/.

These assets are required for product cards without uploads (no runtime picsum).
Run once in CI/dev or after clone:

    python manage.py generate_catalog_seed_assets
"""

from __future__ import annotations

import io
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.utils.demo_product_images import CATALOG_SEED_FILES

# Category keyword → (top RGB, bottom RGB, accent RGB)
_SEED_PALETTES = {
    'electronics': ((15, 42, 68), (46, 91, 138), (242, 101, 34)),
    'textiles': ((55, 48, 107), (108, 92, 231), (255, 183, 77)),
    'beauty': ((120, 40, 80), (200, 90, 140), (255, 200, 210)),
    'home_appliances': ((30, 60, 55), (70, 120, 100), (180, 220, 200)),
    'toys': ((180, 60, 30), (240, 140, 50), (255, 220, 100)),
    'general': ((27, 59, 99), (70, 100, 140), (200, 210, 220)),
}


def _render_seed_jpeg(keyword: str, width: int = 800, height: int = 600) -> bytes:
    from PIL import Image, ImageDraw

    top, bottom, accent = _SEED_PALETTES.get(keyword, _SEED_PALETTES['general'])
    img = Image.new('RGB', (width, height), top)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    # Soft accent shapes — photo-like depth without external assets
    draw.ellipse((width * 0.55, height * 0.08, width * 0.95, height * 0.55), fill=accent)
    draw.ellipse((width * 0.05, height * 0.45, width * 0.55, height * 0.95), fill=tuple(
        min(255, c + 25) for c in bottom
    ))
    draw.rectangle(
        (int(width * 0.18), int(height * 0.22), int(width * 0.72), int(height * 0.78)),
        fill=tuple(min(255, c + 40) for c in top),
        outline=accent,
        width=3,
    )

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=88, optimize=True)
    return buffer.getvalue()


class Command(BaseCommand):
    help = 'Generate static/images/catalog-seeds/*.jpg bundled assets.'

    def add_arguments(self, parser):
        """Add arguments."""
        parser.add_argument('--force', action='store_true', help='Overwrite existing files')

    def handle(self, *args, **options):
        """Handle."""
        force = bool(options['force'])
        out_dir = Path(settings.BASE_DIR) / 'static' / 'images' / 'catalog-seeds'
        out_dir.mkdir(parents=True, exist_ok=True)

        written = 0
        for keyword, rel in CATALOG_SEED_FILES.items():
            dest = Path(settings.BASE_DIR) / 'static' / rel
            if dest.is_file() and not force:
                self.stdout.write(f'  skip {rel} (exists)')
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_render_seed_jpeg(keyword))
            written += 1
            self.stdout.write(self.style.SUCCESS(f'  wrote {rel}'))

        self.stdout.write(self.style.SUCCESS(f'Done. {written} file(s) written.'))
