"""catalog_breadth_products() samples diverse home catalog rows.

Home merchandising should mix CFZ categories instead of flooding one
vertical, while still filling the requested card limit.
"""
from django.test import TestCase

from core.merchandising import catalog_breadth_products
from core.models import Category, Company, Product


class CatalogBreadthProductsTests(TestCase):
    """Assert category mix, dedupe, and limit fill for breadth sampling."""

    def setUp(self):
        """Create two verified companies and three category buckets."""
        self.company_a = Company.objects.create(name='Alpha Trading', is_verified=True)
        self.company_b = Company.objects.create(name='Beta Imports', is_verified=True)
        self.cat_electronics = Category.objects.create(name='Electronics')
        self.cat_textiles = Category.objects.create(name='Textiles')
        self.cat_beauty = Category.objects.create(name='Beauty')

    def _product(self, company, category, name, sku):
        """Create an active product in the given company and category."""
        return Product.objects.create(
            company=company,
            category=category,
            name=name,
            sku=sku,
            unit_price='50.00',
            currency='USD',
            is_active=True,
        )

    def test_returns_products_from_multiple_categories(self):
        """Breadth sample spans multiple categories when inventory allows."""
        self._product(self.company_a, self.cat_electronics, 'USB Hub', 'E-1')
        self._product(self.company_a, self.cat_electronics, 'Cable Pack', 'E-2')
        self._product(self.company_b, self.cat_textiles, 'Cotton Roll', 'T-1')
        self._product(self.company_b, self.cat_beauty, 'Lip Balm Set', 'B-1')

        items = catalog_breadth_products(limit=4, per_category=1)

        self.assertEqual(len(items), 4)
        category_ids = {p.category_id for p in items}
        self.assertGreaterEqual(len(category_ids), 3)

    def test_deduplicates_products(self):
        """Returned product primary keys are unique within the sample."""
        self._product(self.company_a, self.cat_electronics, 'Widget', 'W-1')

        items = catalog_breadth_products(limit=8, per_category=2)

        pks = [p.pk for p in items]
        self.assertEqual(len(pks), len(set(pks)))

    def test_fills_to_limit_when_few_categories(self):
        """When categories are scarce, the helper still fills up to limit."""
        for i in range(6):
            self._product(
                self.company_a,
                self.cat_electronics,
                f'Gadget {i}',
                f'G-{i}',
            )

        items = catalog_breadth_products(limit=5, per_category=2)

        self.assertEqual(len(items), 5)
