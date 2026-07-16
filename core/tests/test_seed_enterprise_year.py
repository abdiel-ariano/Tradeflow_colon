"""seed_enterprise_year demo scale without product images.

Operators need a fast CFZ year of simulated sellers/orders for
analytics demos, with a clean clear path after the run.
"""
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
    """Assert schema readiness and demo seed/clear cycle."""

    def test_schema_ready_after_migrate(self):
        """ensure_database_schema_ready succeeds after migrations."""
        ensure_database_schema_ready()

    def test_demo_seed_and_clear(self):
        """Seed demo companies/orders then remove simulation rows."""
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
