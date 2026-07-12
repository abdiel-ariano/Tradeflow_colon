"""Tests del comando seed_enterprise_year (escala demo, sin imágenes)."""
from django.core.management import call_command
from django.test import TestCase

from core.models import Company, Order, Product
from core.utils.enterprise_year_simulator import (
    ORDER_NUM_PREFIX,
    SIM_RUC_PREFIX,
    clear_enterprise_year_simulation,
    ensure_database_schema_ready,
)


class SeedEnterpriseYearTests(TestCase):
    def test_schema_ready_after_migrate(self):
        """Test schema ready after migrate."""
        ensure_database_schema_ready()

    def test_demo_seed_and_clear(self):
        """Test demo seed and clear."""
        clear_enterprise_year_simulation()
        call_command(
            'seed_enterprise_year',
            '--clear',
            '--scale=demo',
            '--skip-images',
            '--seed=99',
        )
        self.assertTrue(Company.objects.filter(ruc__startswith=SIM_RUC_PREFIX).exists())
        self.assertTrue(Product.objects.filter(company__ruc__startswith=SIM_RUC_PREFIX).exists())
        self.assertTrue(Order.objects.filter(order_number__startswith=ORDER_NUM_PREFIX).exists())

        clear_enterprise_year_simulation()
        self.assertEqual(Company.objects.filter(ruc__startswith=SIM_RUC_PREFIX).count(), 0)
        self.assertEqual(Order.objects.filter(order_number__startswith=ORDER_NUM_PREFIX).count(), 0)
