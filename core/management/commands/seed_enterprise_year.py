"""
Simulación persistente (PostgreSQL/Supabase vía ORM) de ~12 meses de operación
marketplace: empresas ZLC, productos, órdenes con fechas distribuidas, logística,
ads, SaaS y snapshots predictivos.

Uso típico (Supabase):
    python manage.py seed_enterprise_year --clear --scale=standard

CI / rápido:
    python manage.py seed_enterprise_year --clear --scale=demo --skip-images
"""
from django.core.management.base import BaseCommand

from core.utils.enterprise_year_simulator import run_enterprise_year_seed


class Command(BaseCommand):
    help = (
        'Genera datos enterprise de un año (empresas, productos, órdenes, logística, ads, SaaS). '
        'Marcadores de limpieza: RUC 8-1Y-SIM-*, órdenes TF-1YSIM-*, usuarios sim1y_*.'
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
            '--skip-images',
            action='store_true',
            help='No descargar imágenes placeholder (más rápido).',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('TradeFlow — seed_enterprise_year'))
        result = run_enterprise_year_seed(
            scale=options['scale'],
            seed=options['seed'],
            skip_images=options['skip_images'],
            clear=options['clear'],
            stdout_write=lambda m: self.stdout.write(f'{m}\n'),
        )
        if not result.get('ok'):
            self.stdout.write(self.style.ERROR(f'Fallo: {result.get("errors")}'))
            raise SystemExit(1)
        self.stdout.write(
            self.style.SUCCESS(
                f'Listo: empresas={result.get("companies")} productos={result.get("products")} '
                f'órdenes={result.get("orders")} compradores={result.get("buyers")}'
            )
        )
