"""
Delete classic 3-product demo companies from cargar_demo seed.

Targets named demo trio only (never blind Count=3 deletes).
Idempotent: safe to re-run when companies are already gone.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from core.models import Company, Product

# Classic sparse demo companies from cargar_demo.EMPRESAS (3 products each).
SPARSE_DEMO_COMPANY_NAMES = (
    'TechZone Colón S.A.',
    'Textiles Internacionales ZLC',
    'Fragancias del Mundo Ltda.',
)


class Command(BaseCommand):
    help = (
        'Delete named 3-product demo companies (TechZone / Textiles / Fragancias) '
        'and their products. Idempotent; use --dry-run to preview.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List matching companies without deleting.',
        )
        parser.add_argument(
            '--include-extra-named',
            action='store_true',
            help=(
                'Also delete other companies that both match exactly 3 products '
                'and whose name contains TechZone, Textiles Internacionales, or Fragancias del Mundo.'
            ),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        include_extra = options['include_extra_named']

        qs = Company.objects.filter(name__in=SPARSE_DEMO_COMPANY_NAMES)
        companies = list(qs.annotate(product_count=Count('products')))

        if include_extra:
            extra = (
                Company.objects.exclude(pk__in=[c.pk for c in companies])
                .annotate(product_count=Count('products'))
                .filter(product_count=3)
                .filter(
                    name__iregex=r'(TechZone|Textiles Internacionales|Fragancias del Mundo)'
                )
            )
            companies.extend(list(extra))

        if not companies:
            self.stdout.write(self.style.SUCCESS('No matching sparse demo companies found.'))
            return

        for company in companies:
            label = (
                f'{company.name} (id={company.pk}, products={company.product_count})'
            )
            if dry_run:
                self.stdout.write(f'[dry-run] would delete {label}')
                continue
            # Product.company uses PROTECT — delete products before the company.
            with transaction.atomic():
                deleted_products, _ = Product.objects.filter(company=company).delete()
                company.delete()
            self.stdout.write(
                self.style.WARNING(f'Deleted {label} (+{deleted_products} product rows)')
            )

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(f'{len(companies)} company(ies) matched; no changes written.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Removed {len(companies)} sparse demo company(ies).')
            )
