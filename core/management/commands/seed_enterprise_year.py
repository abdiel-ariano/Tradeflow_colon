"""
Simulación persistente (PostgreSQL/Supabase vía ORM) de ~12 meses de operación
marketplace: empresas ZLC, productos, órdenes con fechas distribuidas, logística,
ads, SaaS y snapshots predictivos.

Requisito: python manage.py migrate

Uso típico (rápido, sin miles de descargas HTTP):
    python manage.py seed_enterprise_year --clear --scale=standard

Con imágenes placeholder (máx. ~48 en standard):
    python manage.py seed_enterprise_year --clear --scale=standard --with-images
"""
from django.core.management.base import BaseCommand

from core.utils.enterprise_year_simulator import (
    DatabaseSchemaNotReadyError,
    run_enterprise_year_seed,
)


class Command(BaseCommand):
    help = (
        'Genera datos enterprise de un año (empresas, productos, órdenes, logística, ads, SaaS). '
        'Requiere migrate. Por defecto no descarga imágenes (use --with-images). '
        'Marcadores: RUC 8-1Y-SIM-*, órdenes TF-1YSIM-*, usuarios sim1y_*.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Elimina datos generados por simulaciones anteriores (mismos prefijos) antes de sembrar.',
        )
        parser.add_argument(
            '--scale',
            choices=['demo', 'standard', 'stress'],
            default='standard',
            help='demo=ligero (CI), standard=equilibrado, stress=volumen alto.',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Semilla RNG para reproducibilidad.',
        )
        parser.add_argument(
            '--with-images',
            action='store_true',
            help='Descargar hasta N imágenes placeholder (lento; no recomendado en standard sin red).',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Forzar sin imágenes (comportamiento por defecto).',
        )

    def handle(self, *args, **options):
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
