"""home_stats() — métricas reales del hero."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.merchandising import home_stats_uncached
from core.models import Category, Company, Inventory, Order, Product, UserProfile


@override_settings(
    DEBUG=True,
    SECURE_SSL_REDIRECT=False,
    AXES_ENABLED=False,
)
class HomeStatsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='CFZ Demo', is_verified=True)
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name='Widget',
            sku='W-1',
            unit_price='100.00',
            currency='USD',
            is_active=True,
        )
        Inventory.objects.create(product=self.product, stock_qty=10, reserved_qty=0)

    def test_home_stats_returns_real_counts(self):
        buyer = User.objects.create_user('buyer_stats', 'buyer@test.pa', 'Test1234!')
        UserProfile.objects.create(user=buyer, role='buyer', email_verificado=True)
        Order.objects.create(buyer=buyer, status='delivered', total='250.00')

        stats = home_stats_uncached()

        self.assertEqual(stats['empresas_verificadas'], 1)
        self.assertEqual(stats['productos'], 1)
        self.assertEqual(stats['ordenes_completadas'], 1)
        self.assertEqual(stats['categorias'], 1)
        self.assertIn('gmv_30d_fmt', stats)
        self.assertTrue(stats['gmv_30d_fmt'].startswith('USD'))
