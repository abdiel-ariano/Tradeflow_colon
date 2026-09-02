"""Audit product media paths, on-disk files, and resolvable image URLs.

Detects missing ``Product.image`` values, absent local files, empty URLs,
and legacy S3-signed Supabase links that break catalog cards.

Ops: safe read-only check on any environment. Use before/after media
migrations or when marketplace thumbnails look broken.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Product
from core.utils.media_storage import is_remote_media_storage, local_media_file_exists, product_image_url


def _url_without_query(url: str) -> str:
    """Redact signed query parameters before writing media URLs to logs."""
    parts = urlsplit(url or '')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))


class Command(BaseCommand):
    """Report product image health for local and remote storage backends."""

    help = 'Check Product.image paths, on-disk files, and resolvable image URLs'

    def add_arguments(self, parser):
        """Register limit, missing-detail, and placeholder audit flags."""
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
        parser.add_argument(
            '--audit-placeholders',
            action='store_true',
            help='Count DB rows pointing to placeholder_* paths (may be missing in remote storage)',
        )

    def handle(self, *args, **options):
        """Scan products and print media storage diagnostics."""
        limit = int(options['limit'] or 0)
        show_missing = bool(options['show_missing'])
        audit_placeholders = bool(options['audit_placeholders'])

        qs = Product.objects.order_by('pk')
        if limit > 0:
            qs = qs[:limit]

        total = qs.count()
        with_image = 0
        file_ok = 0
        url_ok = 0
        bad_s3_urls = 0
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
            elif not is_remote_media_storage():
                missing_file.append(product)

            resolved = product_image_url(product)
            if resolved:
                url_ok += 1
                if 'AWSAccessKeyId=service_role' in resolved or '/storage/v1/s3/' in resolved:
                    bad_s3_urls += 1
            else:
                bad_url.append(product)

        self.stdout.write(self.style.NOTICE('TradeFlow — verify_media'))
        self.stdout.write(f'MEDIA_ROOT: {settings.MEDIA_ROOT}')
        self.stdout.write(f'MEDIA_URL:  {settings.MEDIA_URL}')
        self.stdout.write(f'Storage:    {settings.STORAGES.get("default", {}).get("BACKEND", "?")}')
        self.stdout.write(f'SUPABASE_STORAGE_PUBLIC: {getattr(settings, "SUPABASE_STORAGE_PUBLIC", "?")}')
        self.stdout.write(f'Products inspected: {total}')
        self.stdout.write(f'  with image field set: {with_image}')
        self.stdout.write(f'  file exists on disk:  {file_ok}')
        self.stdout.write(f'  resolvable URL:       {url_ok}')
        self.stdout.write(f'  invalid S3-style URLs:{bad_s3_urls}')
        self.stdout.write(f'  missing image field:  {len(missing_field)}')
        self.stdout.write(f'  missing local file:   {len(missing_file)}')
        self.stdout.write(f'  empty/bad URL:        {len(bad_url)}')

        placeholder_qs = Product.objects.filter(
            Q(image__icontains='placeholder_') | Q(image__icontains='productos/placeholders/')
        )
        placeholder_count = placeholder_qs.count()
        self.stdout.write(
            f'  DB rows with placeholder_* path: {placeholder_count} '
            '(may need upload to remote storage or reset to empty for SVG fallback)'
        )

        if audit_placeholders or placeholder_count:
            sample = placeholder_qs.order_by('pk').first()
            if sample and sample.image:
                rel = sample.image.name.replace('\\', '/')
                self.stdout.write(f'  Sample path: {rel}')
                self.stdout.write(
                    f'  Resolved URL: {_url_without_query(product_image_url(sample))}'
                )

        productos_dir = Path(settings.MEDIA_ROOT) / 'productos'
        if productos_dir.is_dir():
            files = list(productos_dir.rglob('*'))
            file_count = sum(1 for f in files if f.is_file())
            total_bytes = sum(f.stat().st_size for f in files if f.is_file())
            self.stdout.write(
                f'media/productos/: {file_count} file(s), {total_bytes:,} bytes total'
            )
        elif is_remote_media_storage():
            self.stdout.write('media/productos/: local dir absent (remote object storage)')
        else:
            self.stdout.write(self.style.WARNING('media/productos/ directory does not exist'))

        if show_missing:
            for product in missing_field[:50]:
                self.stdout.write(f'  [no field] #{product.pk} {product.name}')
            for product in missing_file[:50]:
                self.stdout.write(
                    f'  [no local file] #{product.pk} {product.name} → {product.image.name}'
                )
            for product in bad_url[:50]:
                self.stdout.write(f'  [bad url] #{product.pk} {product.name}')

        if bad_s3_urls:
            self.stdout.write(
                self.style.ERROR(
                    'Detected legacy S3-signed URLs. Deploy SupabaseMediaStorage and restart.'
                )
            )
        elif missing_field and not is_remote_media_storage():
            self.stdout.write(
                self.style.WARNING(
                    'Run: python manage.py regenerate_product_images --missing-only'
                )
            )
        elif url_ok and not bad_s3_urls:
            self.stdout.write(self.style.SUCCESS('Image URL generation looks correct.'))
