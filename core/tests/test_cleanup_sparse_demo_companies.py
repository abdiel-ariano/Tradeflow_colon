"""cleanup_sparse_demo_companies management command.

Removes named sparse demo CFZ sellers so production-like seeds keep
credible catalog density without leftover thin storefronts.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import Company, Inventory, Product


class CleanupSparseDemoCompaniesTests(TestCase):
    """Assert dry-run safety, deletion scope, and idempotent reruns."""

    def setUp(self):
        """Seed a keep company plus three named sparse demo companies."""
        self.keep = Company.objects.create(
            name='Keep Co ZLC',
            ruc='8-NT-9-999999',
            is_verified=True,
        )
        for i in range(5):
            p = Product.objects.create(
                company=self.keep,
                name=f'Keep product {i}',
                unit_price=10,
                is_active=True,
            )
            Inventory.objects.create(product=p, stock_qty=10)

        self.demo_names = (
            'TechZone Colón S.A.',
            'Textiles Internacionales ZLC',
            'Fragancias del Mundo Ltda.',
        )
        for idx, name in enumerate(self.demo_names):
            co = Company.objects.create(
                name=name,
                ruc=f'8-NT-2-00000{idx}',
                is_verified=True,
            )
            for j in range(3):
                p = Product.objects.create(
                    company=co,
                    name=f'{name} product {j}',
                    unit_price=20,
                    is_active=True,
                )
                Inventory.objects.create(product=p, stock_qty=5)

    def test_dry_run_does_not_delete(self):
        """Dry-run leaves demo companies and the keep company untouched."""
        out = StringIO()
        call_command('cleanup_sparse_demo_companies', dry_run=True, stdout=out)
        self.assertEqual(Company.objects.filter(name__in=self.demo_names).count(), 3)
        self.assertTrue(Company.objects.filter(pk=self.keep.pk).exists())

    def test_deletes_named_demo_companies_and_products(self):
        """Live run deletes named demos but preserves denser keep stock."""
        out = StringIO()
        call_command('cleanup_sparse_demo_companies', stdout=out)
        self.assertEqual(Company.objects.filter(name__in=self.demo_names).count(), 0)
        self.assertTrue(Company.objects.filter(pk=self.keep.pk).exists())
        self.assertEqual(self.keep.products.count(), 5)

    def test_idempotent(self):
        """Second run reports no matching sparse demos remain."""
        call_command('cleanup_sparse_demo_companies', stdout=StringIO())
        out = StringIO()
        call_command('cleanup_sparse_demo_companies', stdout=out)
        self.assertIn('No matching sparse demo companies found', out.getvalue())
