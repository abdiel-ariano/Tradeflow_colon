"""Seed ~12 months of CFZ marketplace activity into PostgreSQL.

Creates ZLC companies, products, dated orders, logistics, ads, SaaS
rows, and predictive snapshots via the enterprise year simulator.

Ops: local, CI, and disposable staging only. ``--clear`` deletes prior
simulation markers (RUC 8-1Y-SIM-*, TF-1YSIM-*, sim1y_*). Never run
``--clear`` against production buyer/seller data. Requires migrate.
"""
from django.core.management.base import BaseCommand

from core.utils.enterprise_year_simulator import (
    DatabaseSchemaNotReadyError,
    run_enterprise_year_seed,
)


class Command(BaseCommand):
    """Generate a reproducible year of enterprise marketplace data.

    Scale choices: demo (CI), standard, stress. Images stay off unless
    ``--with-images`` is passed.
    """

    help = (
        'Generate one year of enterprise data (companies, products, orders, '
        'logistics, ads, SaaS). Requires migrate. Default skips images '
        '(use --with-images). Markers: RUC 8-1Y-SIM-*, orders TF-1YSIM-*, '
        'users sim1y_*.'
    )

    def add_arguments(self, parser):
        """Register clear, scale, seed, and image flags."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete prior simulation rows (same prefixes) before seeding.',
        )
        parser.add_argument(
            '--scale',
            choices=['demo', 'standard', 'stress'],
            default='standard',
            help='demo=light (CI), standard=balanced, stress=high volume.',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='RNG seed for reproducibility.',
        )
        parser.add_argument(
            '--with-images',
            action='store_true',
            help='Generate local PNG placeholders under media/productos/.',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Force no images (default behavior).',
        )

    def handle(self, *args, **options):
        """Run the year simulator and exit non-zero on schema or seed errors."""
        self.stdout.write(self.style.NOTICE('TradeFlow — seed_enterprise_year'))
        skip_images = options['skip_images'] or not options['with_images']
        try:
            result = run_enterprise_year_seed(
                scale=options['scale'],
                seed=options['seed'],
                skip_images=skip_images,
                clear=options['clear'],
                stdout_write=lambda m: self.stdout.write(f'{m}\n'),
            )
        except DatabaseSchemaNotReadyError as exc:
            self.stdout.write(self.style.ERROR(str(exc)))
            raise SystemExit(1) from exc

        if not result.get('ok'):
            self.stdout.write(self.style.ERROR(f'Fallo: {result.get("errors")}'))
            raise SystemExit(1)
        self.stdout.write(
            self.style.SUCCESS(
                f'Done: companies={result.get("companies")} products={result.get("products")} '
                f'orders={result.get("orders")} buyers={result.get("buyers")}'
            )
        )
